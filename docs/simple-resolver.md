# A simple resolver for lost references, and tags that help it

Background on FreeCAD's naming is in
[TNP.md](TNP.md). This replaces the scored resolver planned on the
`reference-recovery` branch (`docs/tnp_fix/`) with something that can be
implemented and reviewed in one sitting, and changes the tag key so the
resolver has stable evidence to work with.

## 1. Principle

A lost reference (`?Edge98`) is recovered only when **two independent
sources agree**, or when one source is unambiguous by construction.
Everything else is **refused**: the feature stops with a message asking
the user to re-select. No scores, no thresholds to calibrate, no modes.

A wrong element is far worse than a refusal. Today a lost reference
silently uses its old index, which after a change points at an arbitrary
element (`getElementFromTNP`).

## 2. Evidence

| source | where it comes from | cost |
|---|---|---|
| **saved mapped name** | the `shadow` attribute FreeCAD stores with every sub (read via `dumpPropertyContent`, as `smGetShadowNames` on `reference-recovery` does) | free |
| **tag lineage** | the `:H<tag>` segments of that name, decodable once tags are packed (section 5) | free |
| **recorded geometry** | the carrier of the element (line / circle / plane / cylinder / point) and its extent, stored as JSON in a hidden `smRefGeometry` property whenever the reference is followed normally | ~150 bytes per reference |

The geometry signature stays the v1 format of `smGeometrySignature`. No
topology fingerprint, no neighbour names.

## 3. Algorithm

For each sub of the link property:

0. **Followed**: FreeCAD found the name. Use it and record its geometry.
1. **Lost**: collect
   * `N` = name candidates: elements whose mapped name is a copy (`:H`)
     or modification (`:M`, `:M2`) of the longest specific prefix of the
     old name (the shortening loop of `smHistoryCandidates`, splitting on
     `;` only outside parentheses), or that carry the same packed tag and
     tool element (section 5.3);
   * `G` = geometry candidates: elements on the recorded carrier that
     overlap the old extent (lines: collinear and overlapping; arcs: same
     circle; faces: same plane or cylinder and the face's bound box
     inside the old one, enlarged by the tolerance).
2. Decide, first rule that applies:

| # | condition | result | label |
|---|---|---|---|
| R1 | geometry recorded, `N ∩ G` non-empty | `N ∩ G` | `history+geometry` |
| R2 | geometry recorded, `N` non-empty, `N ∩ G` empty | **refuse** | history contradicts geometry |
| R3 | geometry recorded, `N` empty, `G` non-empty | `G` | `geometry` |
| R4 | no geometry, `N` non-empty and consistent (below) | `N` | `history` |
| R5 | otherwise | **refuse** | |

*Consistent* (R4) means that all of `N` are results of one operation
(same prefix, markers from `:M`, `:M2`, ...) and lie on one carrier among
themselves: collinear edges, coplanar faces. That is the split-edge case,
recognisable without recorded geometry. Unrelated descendants are
refused.

3. **Several elements** (a split edge): callers that use all elements
   get all of them, largest first; the three callers that index `[0]`
   (`ExtrudedCutout`, `SheetMetalFormingCmd`, `SheetMetalUnfoldCmd`) get
   the largest piece. No caller changes.
4. **Refusal** raises `SheetMetalTools.SMException` with
   `"{feature}: lost {Edge98} of {base}; re-select it"`. FreeCAD marks the
   feature invalid, keeps its previous shape and shows the message. A
   preference `Mod/SheetMetal/RefRecoveryFallback` (default off) restores
   the old-index behaviour for anyone who depends on it.
5. **Recorded geometry is not overwritten by a recovery.** It is only
   written when FreeCAD followed the name, so it stays anchored to what
   the user selected. The link property is not rewritten either, so
   undoing the change brings the original reference back.

The warning for a recovery names the rule:
`Wall2: lost Edge98 of Hole, using Edge101 + Edge105 (history+geometry)`.

### What this deliberately does not handle

* An element that **moved and was renamed** in the same change (R2:
  refused). Pure moves keep their names in most cases, and FreeCAD
  follows them.
* **Merges** (a refine step joins the element with a neighbour) and
  **type changes** (a fillet turns a line into an arc): refused.
* A **confidence number**: the label says which rule fired.

These are the cases the scored resolver tried to win with weights and
calibration. Refusing them keeps the wrong-answer rate at "only when name
history and geometry agree on the wrong element", which needs a
coincidence on both sources.

### Known risks

* R3 (geometry only) trusts the recorded carrier. If a different element
  now lies on the old line and the referenced one is gone, it is taken.
  This needs the old element to vanish *and* another to appear exactly
  on its carrier, overlapping its old extent.
* Old documents have no recorded geometry until their first recompute
  with a followed reference. Until then only R4 can recover.

## 4. Implementation

Start from `1798f05` on `reference-recovery` (*Recover lost references by
name history and geometry*, +271 lines in `SheetMetalTools.py`, one-line
changes in 13 callers). It already has the shadow-name reader, the
shortening loop, the geometry signature and matching, the hidden property
and the caller wiring. Changes on top:

1. Replace `found = matching or found` (the known source of wrong answers)
   by the table in section 3.
2. Split names on `;` only at parenthesis depth 0.
3. Add the consistency check of R4 and the `SMException` refusal with
   the fallback preference.
4. Faces in `G`: bound box inside the old one instead of merely
   intersecting it.
5. Tag-lineage candidates (section 5.3) once the tag key is changed.

Expected size: about +60 lines over `1798f05`.

### Tests

* From `1798f05`: `TestTNPRecovery.testSplitEdgeIsFollowed`,
  `testOriginalEdgeReturns`.
* Add `SMTests/data/HoleSplitsEdge.FCStd` (from `7b73b2a`) and sweep
  `Hole.Diameter` 10…60: correct or refused, never another edge; D = 30,
  36, 40 give both pieces; D = 50 gives the remnant.
* R2: record geometry, then move *and* split the edge: the feature is
  invalid, its message names the reference.
* R4: no recorded geometry, split edge: both pieces. Two unrelated
  descendants: refused.
* Fallback preference on: old index, as today.

## 5. Tags

### 5.1 What tags are for

A tool shape built from scratch (`Part.Face`, `extrude`, `makeBox`...) has
`Tag == 0`. In a boolean, its elements then get no name, or a name built
from their neighbours (`;:U`, `;:L`, `;D` markers). Neighbour-based names
change when the neighbourhood changes (TNP.md 3.3), so references to wall
faces, bend faces or relief faces break on unrelated edits. A non-zero tag
names every element of the tool `<tool element>;:H<tag>`. The tag has to
be

1. non-zero and the same on every recompute;
2. unique among the tools of one boolean (otherwise `;D` duplicates);
3. **unchanged by upstream edits** — the property that matters for
   recovery;
4. the same on every platform: tags are not saved, they are recomputed,
   so a platform-dependent tag changes all names when a document is
   opened on another OS.

### 5.2 The two keys compared

| | ours (`smTagTool`, `479cc0d`) | Huwyler (`smToolShapeTag`) |
|---|---|---|
| key | crc32 of the selected element's **mapped name** + role, 30 bits | **feature ID**, sketch segment, edge index, role, bit-packed |
| stable on recompute, save/reopen, sketch dimension | yes (the adopted `TestBendToponaming` passes) | yes |
| unique | probabilistic (crc32); two features on the same element with the same role collide | yes |
| survives an upstream change of the selected element's name | **no**: new name → new tag → every element of the wall renamed → references *into* the wall lost as well | yes |
| survives adding or removing a selected edge | yes | no: later edges shift index |
| survives a split of the selected edge (one sub → two pieces) | no (two new names) | no (later indices shift) |
| platform | 30 bits, same everywhere | 32-bit `long` on Windows: tags fall back to 0 above feature ID 32767, so names differ between platforms |
| decodable | no | yes |

The decisive row is the fourth. When the resolver recovers a split base
edge of a Wall, our key gives the Wall new tags, so every reference into
the Wall is lost one level further down. The resolver fixes one loss and
causes the next. A key that ignores the upstream name stops that.

### 5.3 Adopted key: packed, decodable, upstream-independent

Implemented in `SheetMetalTools.smToolTag` / `smTagFeatureTool` /
`smDecodeToolTag`, used by `smBend` (Wall, Hem, Base shape) and Relief;
details in TNP.md 3.2.

```
tag = -(1 << 30 | featureId << 15 | segment << 11 | slot << 6 | piece << 4 | role)
      featureId 15 bits, segment 4, slot 5, piece 2, role 4  -> < 2³¹ on every platform
```

* `featureId` = `fp.ID` (unique per document, never reused, saved).
* `segment` = sketch segment of a wall profile (Wall and Hem call
  `smBend` once per segment), or the stage of Base shape. This field is
  Huwyler's; the original proposal missed it.
* `slot` = position of the selected element. Once the resolver exists it
  must be the position of the sub in the **link property**, not in the
  resolved list, so splitting sub 0 into two pieces does not shift sub 1.
* `piece` = index of the piece when the resolver returned several
  elements for one sub (0 until then).
* `role` = what the tool is, a fixed constant per kind of tool
  (`smRoleWall`, `smRoleBend`, `smRoleRelief1`, ...). The previous key
  numbered cut tools by their position in the list, so a relief
  appearing renamed the cut tools after it.
* Out of range (feature ID ≥ 2¹⁵, more than 16 segments, 32 selected
  elements, 4 pieces or 16 roles): a hashed tag of the same fields in the
  disjoint range with bit 29 set. Never 0, the same on every platform,
  and still upstream-independent; only decoding is lost. Huwyler's
  version falls back to 0 (untagged) instead, and to 0 for feature IDs
  above 32767 only on Windows.

Because the tag can be decoded, a name like `Face3;:M;CUT;:H...;:H-1a2c5,F`
tells the resolver *"tool face 3 of the wall built for sub 0 of feature
1234"*, regardless of what happened to the face afterwards. That gives a
third, cheap source of name candidates for R1/R4: elements whose names
contain the same tag with the same tool element. Unlike the shortening
loop, this match does not stop at the first changed operation. It also
gives messages a readable origin ("wall face of Bend1").

Migration costs nothing now: `479cc0d` is not upstream, so no user
document has these names yet. Once it is released, any key change renames
every tagged element once (references then go through the resolver; the
geometry is unchanged, so R3 or FreeCAD's own vertex search finds them).
The key should therefore be settled **before** the tagging is proposed
upstream.

### 5.4 Which features to tag

Tag where the user picks the next reference: faces and edges a later
wall, sketch or unfold attaches to.

| feature | tool geometry built from scratch | referenced downstream | action |
|---|---|---|---|
| Wall / Hem / Base shape (`smBend`) | wall, bend, offset, relief, cut, perforation | very often (next wall, sketches, unfold base face) | packed key (done). The "Not all input shapes are mappable" log warnings are *not* caused by the untagged inputs of `common`: tagging them left the count unchanged (58 in `testAllElementsNamed`), so their source is still open |
| Unfold (V2) | flat pattern wires | often (sketches on the flat, TechDraw) | tagged by source edge; keep, key = feature ID + source-edge slot |
| From solid | shell faces, bend faces | often | tagged by source element; keep |
| Relief | relief cut tool | sometimes | packed key (done) |
| Junction, Solid bend | cut box, bend cylinder | rarely | check with a stable-name test like `TestBendToponaming`; tag only if it fails |
| Extend, Fold | none (extrudes or rotates existing named faces) | | nothing to do |
| Base, Extruded cutout, Wrap cutout, Corner relief, Forming | none (names come from sketches or tool objects) | | nothing to do |

The criterion per feature is the adopted test: all elements named, names
equal after recompute, after save and reopen, and after an upstream
dimension change. Add one such test per tagged feature.

## 6. Order

1. Adopted Huwyler tests in `SMTests/testBendToponaming.py` (done).
2. Packed tag key (5.3) in `SheetMetalTools`, used by `smBend` and
   Relief; Huwyler's `TestToolShapeTag` adapted to the 31-bit format
   (done).
3. Resolver (sections 3–4) on top of `1798f05`, with the tests in 4
   (done: `smResolveSubElementSlots` / `smFindLostElement`, tests
   `TestTNPRecovery`, `TestTNPResolverRules`, `TestTNPHoleSplitsEdge`).
   Wall, Hem and Relief tag their tools with the slot and piece the
   resolver returns.
4. Tag-lineage candidates (5.3) (done: `smLineageCandidates`).
5. Stable-name tests for Hem, Base shape, Relief, From solid, Unfold.
6. Update TNP.md 3.2 (key) and 5 (status).
