# Topological naming (TNP) in SheetMetal

This is a reference for how FreeCAD 1.1+ keeps references to faces, edges
and vertices stable, what SheetMetal has to do to take part in it, and how
to debug a reference that jumps. Everything here was checked against
FreeCAD 1.1.4 (flatpak) and the FreeCAD `main` source; file references are
relative to the FreeCAD source tree.

## 1. The problem

A feature such as a Wall stores its selection as `baseObject = (Base,
["Edge10"])`. `Edge10` is only an index into the base shape's edge list.
When anything upstream changes (sketch edited, a gap added, a relief type
changed...) the base is rebuilt and its edges may be numbered differently,
so `Edge10` now names some other edge and the wall is built in the wrong
place.

## 2. How FreeCAD mitigates it

### 2.1 Element maps and mapped names

Every `Part.Shape` (`TopoShape`, see `src/App/ComplexGeoData.pyi`) can
carry:

| attribute         | meaning                                                          |
|-------------------|------------------------------------------------------------------|
| `Tag`             | integer identifying the shape's origin; for a feature's output it is the object's `ID` |
| `Hasher`          | the document's `StringHasher`, compresses long names             |
| `ElementMap`      | dict `{mappedName: indexedName}`, e.g. `{"Edge10;:H-304497de,E;:H,E": "Edge27"}` |
| `ElementMapSize`  | number of entries                                                |
| `ElementMapVersion` | version string of the naming algorithm                         |

A *mapped name* encodes the history of an element: which source element it
came from, by which operation, and the tag of the source shape. Examples
from a real SheetMetal model:

```
;g3;SKT;:Hd2d,E;:G;XTR;:Hd2d:7,F;:U;XTR;:Hd2d:7,E;:H,E
  g3        sketch geometry #3            (geometry IDs, not indices)
  SKT       made by a sketch
  :G;XTR    face *generated* from it by an extrusion
  :U;XTR    an *upper* (child) edge of that face
  :Hd2d     source tag 0xd2d (the sketch object's ID)

Edge10;:H-304497de,E
  Edge10 of a tool shape whose Tag is -0x304497de (see section 3.2)
```

Common operation codes (`src/Mod/Part/App/TopoShapeOpCode.h`): `FUS` fuse,
`CUT`, `CMN` common, `XTR` extrude, `RVL` revolve, `FLT` fillet, `THK`
thickness, `OFS` offset, `XFM` transform, `SKT` sketch, `FAC` face maker.
Markers: `:M` modified, `:G` generated, `:U` upper element, `:H` tag.

An element that has no entry in the map is *unnamed*. It can still be
addressed by its index name, but nothing protects that index.

### 2.2 How references are stored and updated

`App::PropertyLinkSub` (and `LinkSubList`, `XLinkSub`...) store each
sub-element as a *ShadowSub* pair: mapped name plus index name. In the
saved document:

```xml
<LinkSub value="Wall1" count="1">
    <Sub value="Edge27" shadow=";Edge10;:H-304497de,E;:H,E.Edge27"/>
</LinkSub>
```

Python only sees the index part: `obj.baseObject` → `(Wall1, ['Edge27'])`.

When the linked object's shape changes, `GeoFeature::updateElementReference`
calls `PropertyLinkBase::updateElementReferences`
(`src/App/GeoFeature.cpp`, `src/App/PropertyLinks.cpp`
`_updateElementReference`). For every link into that object it looks up
the stored **mapped** name in the new shape and rewrites the index part to
wherever that element is now. This is the whole mechanism. It only works
if:

1. the referenced element had a mapped name when the link was created or
   last updated (otherwise the shadow holds no mapped name and the plain
   index is kept), and
2. the new shape produces **the same mapped name** for the same element.

If the mapped name cannot be found in the new shape, FreeCAD logs

```
<PropertyLinks> ... missing element reference Doc#Base ;g3;SKT;...Edge10
```

and the index part becomes `?Edge10` (leading `?` = lost).

So the responsibility of every feature is: **produce an output shape in
which every face, edge and vertex has a stable mapped name.**

### 2.3 Which operations create names

Names are created by FreeCAD's element-map-aware makers. In Python these
are the regular `TopoShape` methods; they name result elements from the
history of *inputs that have a non-zero `Tag` or an element map*
(`TopoShape::canMapElement`, `src/Mod/Part/App/TopoShapeExpansion.cpp`):

| map-aware (keep / create names)                                  | notes |
|-------------------------------------------------------------------|-------|
| `fuse`, `multiFuse`, `cut`, `common`, `generalFuse`, `removeSplitter` | `noElementMap=True` opts out (analysis geometry) |
| `extrude`, `revolve`, `makeFillet`, `makeChamfer`, `makeThickness`, `makeOffsetShape` | |
| `Part.makeFace(wires, "Part::FaceMakerBullseye")`                | inputs must be wires; names come from the wires' maps |
| `copy()`, `transformed()`, `translated()`, `rotated()`           | keep the map |
| `mapSubElement(shape)`                                           | copies names of *shared* sub-shapes (same `TShape`) from a tagged shape, see 3.4 |

Shapes built from scratch have `Tag == 0` and no map, and contribute
*unnamed* elements to any boolean they take part in:
`Part.Face(wire)`, `Part.makeLine`, `Part.LineSegment(...).toShape()`,
`Part.makeBox`, `Part.makePolygon`, `edge.Curve.toShape()` ...

`shape.getElement("Edge3")` returns the sub-shape with `Tag == 0` and no
map; building new geometry from it loses the history too.

`Part::Feature` re-tags the shape assigned to `obj.Shape` with `obj.ID`
(`src/Mod/Part/App/PartFeature.cpp`), so names created inside `execute()`
are kept, prefixed by the feature's tag.

### 2.4 Things that do *not* work (FreeCAD 1.1.4)

* **`TopoShape.mapShapes(generated, modified, op)` from Python produces no
  names** — verified with tagged sources, untagged sources, whole-shape and
  sub-shape destinations, with and without a hasher. FreeCAD's own test for
  it is commented out (`src/Mod/Part/parttests/TopoShapeTest.py`,
  `testTopoShapeMapShapes`: "what this method is supposed to do remains a
  mystery; so far, it just wipes out the elementMap"). The five calls in
  SheetMetal (`smMakeReliefFace`, `smMakeFace`, `LineExtend`,
  `smMakePerforationFace`, `SheetMetalExtendCmd`) are no-ops. Do not rely on
  it; use tagged tools (3.2) instead.
* **The Python proxy hook `getElementMapVersion(self, fp, ver, prop,
  restored)` is never called.** It was part of the LinkStage3 API; FreeCAD
  1.x calls only the C++ `DocumentObject::getElementMapVersion`. There is no
  way for a Python feature to bump its element map version. The copies in
  SheetMetal were removed.
* **`shape.makeWires(op)` and `Part.Wire(edges)` are not map-aware.** The
  Python `makeWires` calls the old `TopoShape::makeWires`, not
  `makeElementWires`, whatever its docstring says. `Part.Wire` also
  replaces most edges with copies (only the first edge stays shared).
  A compound (`Part.makeCompound`) drops the tags of its children.
* **`mapSubElement([shape1, shape2...])` names elements by their position
  in the list**, not by their own names, so the result depends on order.
  Call it once per shape (see 3.4).
* Recreating sketch geometry (delete + add) gives it new geometry IDs, so
  everything derived from it gets new names. This is expected; edits that
  move or trim existing geometry keep the IDs.
* **A face whose modification history changes gets a new name.** A mapped
  name records every operation that modified the element, and long names
  are stored as a hash (`#15:1;:M;FUS...`). If an option change makes an
  extra operation modify a face (e.g. Wall gaps add relief cuts to the
  plate's top face), the face's name changes and references to it are
  lost. FreeCAD 1.1 then tries a geometric search
  (`Part::Feature::searchElementCache`), which needs the old element's
  vertices to be unchanged, so it fails when the face itself was cut.
  FreeCAD `main` adds a tolerance-based fallback (`rescueDriftedElement` in
  `src/App/PropertyLinks.cpp`). SheetMetal cannot avoid this; features fall
  back to the old index with a warning (`getElementFromTNP`).

## 3. Rules for SheetMetal code

### 3.1 Checklist

1. Start from the linked object's shape (`fp.baseObject[0].Shape`, tagged
   with its ID). `.copy()` is fine, it keeps the map.
2. Every solid built from scratch that is fused/cut into the result must be
   tagged with `SheetMetalTools.smTagTool(tool, key, role)` right before the
   boolean.
3. Combine with map-aware booleans; never rebuild the result from raw faces
   (`Part.Solid(Part.Shell(faces))`) unless you re-establish the names.
4. Never persist an element by index (`shape.Faces[i]`, a stored integer);
   persist names in a `PropertyLinkSub`.
5. Never strip the reference: pass the name from the property to
   `shape.getElement()` as is. `getElement` also accepts mapped names.
   A leading `?` means the reference is lost;
   `SheetMetalTools.getElementFromTNP` warns about it and falls back to the
   index.
6. Add a case to `SMTests/testTNP.py` for each feature you touch: a
   coverage test, and a reference test that changes something upstream.
   Full coverage alone is not enough, see 3.3.

### 3.2 Tagged tools

`SheetMetalTools.smTagTool(tool, *key)` sets
`tool.Tag = -(crc32("/".join(key)) & 0x3FFFFFFF) - 2`. Booleans then name
every element of the tool as `<element of tool>;:H<tag>,...`, e.g.
`Face3;:H-1a2b3c,F`.

Choosing the key:

* It must **not** depend on element indices of the result, otherwise the
  names change whenever the indices do. Use
  `SheetMetalTools.smElementKey(baseShape, selectedName)`: the mapped name
  of the selected element (falls back to the index name if it has none).
* Add a role string unique within the feature (`"SMBendWall"`,
  `"SMBend"`, `"SMBendCut", j` ...). Two tools with the same key in one
  shape would get colliding names.
* Use the same role for the same geometry in different modes (e.g. folded
  vs. unfolded wall) so references survive toggling the mode.

Negative tags never collide with document object IDs, so
`getElementHistory()` on these names simply finds no source object.

The element order *inside* a tool must be deterministic, which it is for
geometry built by the same code path (an extruded 4-edge face always has
its 6 faces in the same order).

### 3.3 Named is not the same as stable

A boolean with an *untagged* tool still names most of the new faces, but
from their neighbours: upper/lower-element combinations (`;:U`, `;:L`) and
duplicate markers (`;D1d6c`), e.g.

```
Face4;:M;CUT;:Hc8d:7,F;:U2;CUT;:Hc8d:8,E;:L(Face4;:M;CUT;...|...);CUT;...
```

These names change when the neighbourhood changes. In
`TestTNPReferences.testReliefSize` a reference to a relief pocket face was
lost when only the relief size changed. With a tagged tool the name is
`Face5;:M;CUT;:H-30bd5e1e:7,F` and survives. So tag tools even when the
coverage test already passes.

Faces built from a tagged sketch (wrap cutout, corner relief from a
sketch) or from a tagged feature (forming tool) already have good names
(`#4c:2;:M;CUT...`, `#5a:1;D1910...`); there is no need to re-tag them.
A forming tool placed at several sketch points gives the copies the same
tag, which FreeCAD disambiguates with `;D` markers in placement order.

### 3.4 Naming loose edges (flat patterns, shells)

When a shape is assembled from loose edges or faces, every piece has to be
tagged with the element it comes from:

* **Faces → shell** (From solid): tag every face before
  `Part.makeShell(faces)`, which is map-aware for a list of tagged faces.
* **Edges → wires → face** (Unfold): edges cannot be named through
  `Part.Wire` or `makeWires` (2.4). Build the wires as usual, then for each
  wire edge make a single-edge holder wire with the tag and map it:

  ```python
  for edge in wire.Edges:
      holder = SheetMetalTools.smTagTool(Part.Wire(edge), key, role)
      wire.mapSubElement(holder)      # edge is shared, so it gets the name
  face = Part.makeFace(wires, "Part::FaceMakerBullseye")
  solid = face.extrude(direction)     # side faces: 'Edge1;:H<tag>,E;:G;XTR...'
  ```

  The holder makes the name `Edge1;:H<tag>` independent of the edge's
  position in the wire. `SheetMetalNewUnfolder.name_flat_pattern_wires`
  does this; it matches each cleaned up edge back to the sketch line it
  came from by midpoint, and uses the mapped name of that line's source
  edge in the folded shape as the key.

### 3.5 Migration of existing documents

Tagging does not change geometry or element order, so opening an old
document and recomputing yields the same indices. On that recompute the
links into the feature pick up the new mapped names. References that were
already wrong in the saved file stay wrong.

## 4. Debugging recipe

```python
obj = App.ActiveDocument.Wall2
linked, subs = obj.baseObject
shape = linked.Shape
name = subs[0]                                   # 'Edge27' or '?Edge27'
shape.getElementMappedName(name)                 # '' => unnamed, fragile
shape.getElementIndexedName(mapped)              # reverse lookup
shape.getElementHistory(mapped)                  # (sourceTag, sourceName, [...])

# naming coverage of a feature's output
vals = set(shape.ElementMap.values())
[f"Face{i+1}" for i in range(len(shape.Faces)) if f"Face{i+1}" not in vals]
```

* Look for `missing element reference` lines in the report view; they show
  the mapped name that could not be found.
* Unzip the `.FCStd` and grep `Document.xml` for `shadow=` to see what was
  stored.
* `SMTests/testTNP.py` builds chains, records the geometry a reference
  points at, changes something upstream and checks the reference still
  points at the same geometry. Run with

  ```
  flatpak run --command=FreeCADCmd org.freecad.FreeCAD -t SMTests.testTNP
  ```

## 5. Status per feature

*Coverage* = every face/edge/vertex of the output has a mapped name
(`TestTNPCoverage`); *refs* = references into the output survive upstream
changes (`TestTNPWalls`, `TestTNPReferences`, or a manual probe). All
tests are in `SMTests/testTNP.py`.

| feature (file)                                     | status |
|----------------------------------------------------|--------|
| Base (`SheetMetalBaseCmd.py`)                      | coverage, refs (names come from the sketch) |
| Wall (`SheetMetalCmd.py`, `smBend`)                | tagged tools; coverage, refs (was 9/14 faces named) |
| Hem (`SheetMetalHem.py`, uses `smBend`)            | coverage (was 8/12) |
| Base shape (`SheetMetalBaseShapeCmd.py`, uses `smBend`) | coverage (was 5/14) |
| Fold (`SheetMetalFoldCmd.py`)                      | coverage (already) |
| Extend (`SheetMetalExtendCmd.py`)                  | coverage (already) |
| Extruded cutout (`ExtrudedCutout.py`)              | coverage (already) |
| Junction (`SheetMetalJunction.py`)                 | coverage (already) |
| Solid bend (`SheetMetalBend.py`)                   | coverage (already) |
| Unfold, V2 unfolder (`SheetMetalNewUnfolder.py`)   | flat pattern edges tagged with their folded source edge (3.4); coverage, refs (was 0 % named). Its own reference into the folded part falls back to the old index when lost |
| Unfold, V1 unfolder (`SheetMetalUnfolder.py`)      | not named; only used when NetworkX is missing or the old unfolder is selected |
| Relief (`SheetMetalRelief.py`)                     | tagged tool; coverage, refs (names were neighbour-based and broke on a size change) |
| From solid (`SheetMetalFromSolid.py`)              | shell faces tagged with their source face / edge; coverage, refs (names had `;D` duplicates and broke on a box size change) |
| Corner relief (`SheetMetalCornerReliefCmd.py`)     | coverage, refs (manual probe, size change) |
| Wrap cutout (`SketchOnSheetMetalCmd.py`)           | coverage, refs (manual probe, deleting another circle); names come from the sketch |
| Forming (`SheetMetalFormingCmd.py`)                | coverage, refs (manual probe, deleting another placement point); names come from the tool object |
| Any feature on a face whose modification history changes | lost, see 2.4 (FreeCAD limitation) |

## 6. Transparent previews (FreeCAD > 1.1)

FreeCAD `main` has `Part::PreviewExtensionPython` (App) and
`PartGui::ViewProviderPreviewExtensionPython` (Gui), used by PartDesign to
show the geometry a feature adds in a semi-transparent colour.
**They are not registered in FreeCAD 1.1.4**, so any use must be
feature-detected (`try: obj.addExtension(...)`).

* App proxy hooks: `recomputePreview(self, ext)` fills
  `ext.ExtendedObject.PreviewShape`; `mustRecomputePreview(self, ext)`.
* Newer (Aug 2026, main only): `obj.updatePreview()`,
  `obj.invalidatePreview()`, `obj.isPreviewFresh()`.
* View provider: `vobj.showPreview(bool)`, `vobj.isPreviewEnabled()`,
  proxy hooks `attachPreview`, `updatePreview`, `getPreviewShape(self,
  vext)`; newer: `PreviewRootNode`, `PreviewShapeNode`,
  `updatePreviewShape(shape, node)`.
* Reference usage: `src/Mod/Part/TestPartPreview.py`.
