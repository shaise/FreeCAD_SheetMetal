########################################################################
#
#  SheetMetalBendCuts.py
#
#  Copyright 2026
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
########################################################################
"""Geometry helpers for laser "cold bending" / hinge-cutting relief patterns.

This module is a pure post-process of the data the unfolder already
produces: given a list of straight bend-line edges (as ``BendInfo``-like
objects exposing a ``.line`` attribute) it produces the *cut* geometry of
a broken/segmented line along each bend, leaving gaps for the uncut
material bridges that hold the part together for hand-folding.

Deliberately, this module only depends on ``Part``/``FreeCAD`` primitives
and a minimal duck-typed ``BendInfo`` (an object with a ``.line``
Part.Edge attribute). It does not import ``SheetMetalNewUnfolder`` or
``SheetMetalUnfolder``, and it never touches fold/bend/solid geometry of
the sheet metal feature tree - it only ever reads a straight edge and
returns new, unrelated cut edges.
"""

import FreeCAD
import Part

eps = 1e-7

# Flip this to True from the Python console (`import SheetMetalBendCuts;
# SheetMetalBendCuts.DEBUG = True`) to get diagnostic prints from both
# this module and the calling code in SheetMetalUnfoldCmd.py during the
# next Unfold recompute.
DEBUG = False


class BareEdgeBendInfo:
    """Minimal adapter so a plain Part.Edge can be used wherever a
    BendInfo-like object (only needs a `.line` attribute) is expected.

    Useful for callers (e.g. a future old-unfolder integration) that only
    have raw bend edges rather than full BendInfo objects from the new
    unfolder.
    """

    def __init__(self, edge):
        self.line = edge


###################################################################################################
# 1. Segmenting a bend line into cut/bridge spans
###################################################################################################

def segment_bend_line(length, max_cut, max_material, edge_offset):
    """Return a list of (start, end, is_cut) spans along a 1D line of the
    given length, alternating cut/bridge, starting and ending with a cut
    segment, respecting max_cut / max_material and leaving edge_offset
    untouched at both ends.

    Cut segments are kept as close to `max_cut` as possible; the leftover
    length is absorbed by the bridges (up to `max_material`). If even the
    minimum number of bridge-separated cuts would still need bridges
    longer than `max_material`, more (shorter) cuts are added. If cuts at
    `max_cut` would already overshoot the usable length, cuts are instead
    shrunk evenly and bridges collapse to zero length.

    Returns an empty list if the bend line is too short to fit even a
    single cut segment inside the edge offsets.
    """
    if max_cut <= eps:
        return []

    usable = length - 2.0 * edge_offset
    if usable <= eps:
        return []

    if usable <= max_cut + eps:
        # Whole usable length fits in a single cut segment.
        return [(edge_offset, edge_offset + usable, True)]

    # Need n >= 2 cut segments with (n - 1) bridges between them.
    n = 2
    cut_len = max_cut
    bridge_len = 0.0
    while True:
        bridge_total = usable - n * max_cut
        if bridge_total <= eps:
            # Cuts at their maximum length alone would already meet or
            # exceed the usable length - shrink the cuts evenly instead
            # and collapse the bridges to zero length.
            cut_len = usable / n
            bridge_len = 0.0
            break
        bridge_len_candidate = bridge_total / (n - 1)
        if bridge_len_candidate <= max_material + eps:
            cut_len = max_cut
            bridge_len = bridge_len_candidate
            break
        n += 1

    spans = []
    pos = edge_offset
    for i in range(n):
        spans.append((pos, pos + cut_len, True))
        pos += cut_len
        if i < n - 1:
            spans.append((pos, pos + bridge_len, False))
            pos += bridge_len
    return spans


###################################################################################################
# 2. Turning spans into geometry on a real bend edge
###################################################################################################

def build_relief_cuts_for_bend(bend_info, max_cut, max_material, edge_offset,
                                profile_points=None):
    """bend_info: object with a `.line` attribute (a straight Part.Edge),
       e.g. SheetMetalNewUnfolder.BendInfo or BareEdgeBendInfo.
    profile_points: optional normalized 2D point list (see
                  `normalize_profile_sketch`) or None for a plain
                  straight cut.
    Returns a Part.Compound of the *cut* geometry only (bridges are gaps,
    i.e. no geometry is emitted for them - that's what leaves the
    material connected), or None if the bend line is too short to fit
    any relief cut at all (caller should keep the plain solid bend line
    for that bend instead).
    """
    edge = bend_info.line
    length = edge.Length
    spans = segment_bend_line(length, max_cut, max_material, edge_offset)
    if DEBUG:
        FreeCAD.Console.PrintMessage(
            f"[BendCuts] bend length={length:.4f} edge midpoint={edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))} "
            f"-> {len(spans)} span(s): {[(round(s, 3), round(e, 3), c) for s, e, c in spans]}\n")
    if not spans:
        return None
    cut_shapes = []
    for start, end, is_cut in spans:
        if not is_cut:
            continue
        p1 = edge.valueAt(edge.FirstParameter + start)
        p2 = edge.valueAt(edge.FirstParameter + end)
        if profile_points is None:
            cut_shapes.append(Part.makeLine(p1, p2))
        else:
            placed = _place_profile_on_span(profile_points, p1, p2)
            if placed is not None:
                cut_shapes.append(placed)
    if not cut_shapes:
        return None
    return Part.makeCompound(cut_shapes)


def build_relief_cuts(bend_infodata, max_cut, max_material, edge_offset,
                       profile_points=None):
    """Build relief-cut geometry for a whole list of bends at once.

    Returns a tuple (cut_compound, fallback_edges):
      - cut_compound: Part.Compound of all relief-cut geometry (across
        every bend that was long enough for the requested pattern).
      - fallback_edges: list of the original, full-length Part.Edge bend
        lines for any bend that was too short to fit even a single cut
        segment inside the requested edge offsets. The caller can render
        these as plain solid bend lines instead so that short bends are
        not silently left without any visual/exportable indication.
    """
    cut_shapes = []
    fallback_edges = []
    for bend_info in bend_infodata:
        shape = build_relief_cuts_for_bend(
            bend_info, max_cut, max_material, edge_offset, profile_points)
        if shape is None:
            fallback_edges.append(bend_info.line)
        else:
            cut_shapes.append(shape)
    return Part.makeCompound(cut_shapes), fallback_edges


###################################################################################################
# 3. Custom relief shape from a sketch
###################################################################################################

def validate_profile_sketch(sketch):
    """Validate that `sketch` can be used as a bend-relief profile.

    Returns (True, "") if valid, or (False, message) describing why not.
    """
    if sketch is None:
        return False, "no profile sketch selected"
    if not hasattr(sketch, "Shape") or sketch.Shape is None:
        return False, "selected object has no usable shape"
    wires = sketch.Shape.Wires
    if len(wires) != 1:
        return False, f"sketch must contain exactly one wire (found {len(wires)})"
    wire = wires[0]
    if wire.isClosed():
        return False, "profile wire must be open (a closed wire can't be tiled along a cut)"
    bbox = wire.BoundBox
    if bbox.XLength < eps:
        return False, "profile wire has zero length along its local X axis"
    if bbox.ZLength > 1e-3:
        return False, "profile wire must be planar, drawn flat in the XY plane"
    return True, ""


def _discretize_wire_to_points(wire, curve_samples=24):
    """Convert `wire` into an ordered list of FreeCAD.Vector points (a
    polyline approximation): straight edges contribute their exact
    endpoints (no approximation), curved edges (arcs, splines, ...) are
    approximated with `curve_samples` points.

    This is deliberately lossy for curved edges, but it means the result
    is always plain straight-line geometry - see `_place_profile_on_span`
    for why that matters (SheetMetalNewUnfolder.SketchExtraction.
    edges_to_sketch_object() only accepts Part::GeomLine / GeomCircle
    edges; anything else, including a BSplineCurve, raises a RuntimeError
    when the sketch object gets created).

    Edges are stitched together in wire-traversal order regardless of
    each individual edge's own start/end orientation.
    """
    edges = list(wire.OrderedEdges) if hasattr(wire, "OrderedEdges") else list(wire.Edges)
    points = []
    for edge in edges:
        start = edge.firstVertex().Point
        end = edge.lastVertex().Point
        if edge.Curve.TypeId == "Part::GeomLine":
            edge_points = [start, end]
        else:
            edge_points = list(edge.discretize(Number=max(curve_samples, 2)))
            if edge_points[0].distanceToPoint(end) < edge_points[0].distanceToPoint(start):
                edge_points.reverse()
        if points:
            # Orient this edge's points to continue from the last point
            # already collected, regardless of the edge's own
            # start/end direction.
            if edge_points[0].distanceToPoint(points[-1]) > edge_points[-1].distanceToPoint(points[-1]):
                edge_points.reverse()
            if edge_points[0].distanceToPoint(points[-1]) < eps:
                edge_points = edge_points[1:]
        points.extend(edge_points)
    return points


def normalize_profile_sketch(sketch, curve_samples=24):
    """Extract the sketch's single wire as an ordered polyline (see
    `_discretize_wire_to_points`) and rescale it *along X only* so it
    spans exactly x in [0, 1].

    This is what makes it "tileable": the caller doesn't care about its
    real-world X size, only its shape, because it gets stretched to fit
    each individual cut span - see `_place_profile_on_span`. Y is left
    untouched, in the sketch's original real-world units, so features
    like dogbone/chevron depth stay a fixed physical size regardless of
    how long an individual cut segment ends up being.

    Returns a list of FreeCAD.Vector points (x in [0, 1], y in the
    sketch's real-world units, z = 0). Caller is expected to have already
    validated the sketch with `validate_profile_sketch`.
    """
    wire = sketch.Shape.Wires[0]
    points = _discretize_wire_to_points(wire, curve_samples)
    xs = [p.x for p in points]
    x_min, x_max = min(xs), max(xs)
    x_range = x_max - x_min
    scale = 1.0 / x_range if x_range > eps else 1.0
    return [FreeCAD.Vector((p.x - x_min) * scale, p.y, 0.0) for p in points]


def _place_profile_on_span(unit_points, p1, p2):
    """Stretch `unit_points` (x in [0, 1], y in real-world units - see
    `normalize_profile_sketch`) along its X axis to span `p1` -> `p2`,
    then rotate/translate it into place.

    Only the X axis is stretched; Y is carried over unchanged so a
    dogbone/chevron/etc. keeps a consistent physical depth no matter how
    long the individual cut segment is.

    Builds the result by hand (plain vector math -> Part.LineSegment
    edges) rather than via Shape.transformGeometry(): OCCT's general
    (non-uniform) affine curve transform can't represent even a straight
    Part::GeomLine directly and silently rebuilds it as a
    Part::GeomBSplineCurve instead, which
    SketchExtraction.edges_to_sketch_object() then rejects. Doing the
    placement ourselves guarantees the output is always plain lines.
    """
    span_vec = p2 - p1
    span_len = span_vec.Length
    if span_len < eps or len(unit_points) < 2:
        return None
    direction = span_vec.normalize()
    perp = FreeCAD.Vector(-direction.y, direction.x, 0.0)  # +90 deg in XY

    world_points = [p1 + direction * (pt.x * span_len) + perp * pt.y for pt in unit_points]

    edges = []
    for a, b in zip(world_points, world_points[1:]):
        if a.distanceToPoint(b) > eps:
            edges.append(Part.makeLine(a, b))
    if not edges:
        return None
    return Part.makeCompound(edges)
