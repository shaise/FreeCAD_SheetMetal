# -*- coding: utf-8 -*-
# #######################################################################
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
# #######################################################################

"""Tests for wall outlines (Edit Outline): a Make Wall wall with a custom outline.

An outline sketch is an open chain drawn in its own 2D frame: x along the
attachment edge from its start, y up the wall from the reference line. Closing
lines join its loose ends to the bend ends, straight in the flat pattern, and
the bend follows the outline.

Expected values come from formulas: with K-factor 0.5 a sheet keeps its volume
when folded, so a wall's volume is thickness x (plate area + outline area in
the flat pattern) minus the reliefs.

Run with:  FreeCADCmd -t TestSheetMetal
"""

import math
import unittest

import FreeCAD
import Part
from FreeCAD import Vector

import SheetMetalCmd
import SheetMetalTools
import SheetMetalUnfoldCmd
from SMTests.testFeatures import (
    PLATE_L,
    PLATE_VOLUME,
    PLATE_W,
    THK,
    FeatureTestCase,
    add_wall,
    face_name,
    is_flat_face,
    make_plate,
)

RADIUS, K = 1.0, 0.5
RELIEF_VOLUME = 0.8 * 1.0 * THK  # default relief width x depth x thickness


def bend_allowance(angle_deg=90.0, radius=RADIUS, k=K):
    return math.radians(angle_deg) * (radius + k * THK)


def shoelace(points):
    return abs(sum(x1 * y2 - x2 * y1
                   for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2


def outline_area(chain, bend_start, bend_end, rise):
    """Area of the outline in the flat pattern, for a chain drawn left to right."""
    lifted = [(x, y + rise) for x, y in chain]
    return shoelace([(bend_start, 0.0)] + lifted + [(bend_end, 0.0)])


def outline_sketch(doc, points):
    """An open polyline in the outline sketch's own 2D frame."""
    sketch = doc.addObject("Sketcher::SketchObject", "Outline")
    for start, end in zip(points, points[1:]):
        sketch.addGeometry(Part.LineSegment(Vector(*start, 0), Vector(*end, 0)))
    return sketch


def unfold(doc, wall, old_unfolder):
    """Unfold with the old or the new unfolder, from the plate's top face."""
    params = SheetMetalTools.params
    previous = params.GetBool("UseOldUnfolder", False)
    params.SetBool("UseOldUnfolder", old_unfolder)
    try:
        flat = doc.addObject("Part::FeaturePython", "Unfold")
        SheetMetalUnfoldCmd.SMUnfold(flat, wall, [face_name(wall.Shape, is_flat_face(1))])
        flat.MaterialSheet = "_manual"
        flat.KFactor = K
        doc.recompute()
        return flat
    finally:
        params.SetBool("UseOldUnfolder", previous)


def upper_part(wall, above=10.0):
    """The part of the wall well above the plate."""
    return wall.Shape.common(Part.makeBox(200, 400, 200, Vector(-50, -150, above)))


class TestWallOutline(FeatureTestCase):

    def setUp(self):
        super().setUp()
        self.plate = make_plate(self.doc)

    def outline_wall(self, chain, **props):
        """A wall with an outline sketch of this chain, its bend ends at the wall's gaps."""
        wall = add_wall(self.doc, self.plate, **props)
        sketch = outline_sketch(self.doc, chain)
        SheetMetalCmd.smAddBendEndPoints(sketch, wall)
        wall.OutlineSketch = sketch
        self.doc.recompute()
        return wall

    def test_starting_sketch_keeps_the_wall(self):
        """An unchanged starting sketch gives exactly the plain wall back."""
        cases = [
            ("Leg", {}),
            ("Outer Sharp", {"LengthSpec": "Outer Sharp"}),
            ("Inner Sharp", {"LengthSpec": "Inner Sharp"}),
            ("Tangential", {"LengthSpec": "Tangential"}),
            ("Material Inside", {"BendType": "Material Inside"}),
            ("Thickness Outside", {"BendType": "Thickness Outside"}),
            ("Offset", {"BendType": "Offset", "offset": 2.0}),
            ("Invert", {"invert": True}),
            ("negative angle", {"angle": -90.0}),
            ("45 degrees", {"angle": 45.0}),
            ("135 degrees, Outer Sharp", {"angle": 135.0, "LengthSpec": "Outer Sharp"}),
            ("gaps", {"gap1": 5.0, "gap2": 10.0}),
            ("extends", {"gap1": 8.0, "gap2": 8.0, "extend1": 3.0, "extend2": -2.0}),
            ("negative gaps", {"gap1": -5.0, "gap2": -3.0, "extend1": 5.0}),
        ]
        for label, props in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, **props)
                plain = wall.Shape.copy()
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                self.doc.recompute()
                self.assertValidSheet(wall)
                self.assertEqual(sketch.solve(), 0, "starting sketch doesn't solve")
                self.assertLess(plain.cut(wall.Shape).Volume, 0.01)
                self.assertLess(wall.Shape.cut(plain).Volume, 0.01)
                # Same faces too: no extra seams or slivers on the bend.
                self.assertEqual(len(wall.Shape.Faces), len(plain.Faces), "face count")
                self.assertEqual(len(wall.Shape.Edges), len(plain.Edges), "edge count")
                # The bend is wrapped from B-splines, so allow a tiny volume difference.
                self.assertAlmostEqual(wall.Shape.Volume, plain.Volume, delta=plain.Volume * 1e-4)

    def test_making_the_starting_sketch_reports_no_errors(self):
        """Edit Outline never builds the wall from a half-made sketch."""
        errors = []
        original = SheetMetalCmd.SMWallOutline.__init__

        def recording(outline, sketch):
            try:
                original(outline, sketch)
            except Exception as error:
                errors.append(str(error))
                raise

        SheetMetalCmd.SMWallOutline.__init__ = recording
        try:
            wall = add_wall(self.doc, self.plate, gap1=5.0, extend1=2.0)
            SheetMetalCmd.smCreateWallOutlineSketch(wall)
            SheetMetalCmd.smRefreshWallOutlineTilt(wall)
            self.doc.recompute()
        finally:
            SheetMetalCmd.SMWallOutline.__init__ = original
        self.assertEqual(errors, [])
        self.assertValidSheet(wall)

    def test_panel_values_give_the_plain_wall(self):
        """Setting Gap A/B and Extend A/B on a wall with an outline sketch, as the task panel
        does, gives exactly the wall Make Wall makes with the same values.

        A negative Extend is set on the wall only; the wall applies it where
        the flat part starts.
        """
        fields = {"gap1": "GapA", "gap2": "GapB", "extend1": "ExtendA", "extend2": "ExtendB"}
        cases = [
            ({"gap1": 5.0, "gap2": 10.0}, "Leg"),
            ({"extend1": 3.0, "extend2": 2.0}, "Leg"),
            ({"gap1": 5.0, "extend1": 2.0}, "Leg"),
            ({"gap1": 5.0, "gap2": 10.0}, "Outer Sharp"),
            ({"extend1": 3.0, "extend2": 2.0}, "Outer Sharp"),
            ({"gap1": 5.0, "extend1": 2.0}, "Outer Sharp"),
            ({"gap1": 5.0, "extend1": -2.0}, "Outer Sharp"),
        ]
        for values, spec in cases:
            with self.subTest(values=values, spec=spec):
                plain = add_wall(self.doc, self.plate, LengthSpec=spec, **values).Shape
                wall = add_wall(self.doc, self.plate, LengthSpec=spec)
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                for prop, value in values.items():
                    setattr(wall, prop, value)
                    if prop in fields:
                        if prop.startswith("extend"):
                            value = max(value, 0.0)
                        sketch.setDatum(SheetMetalCmd.smFindNamedConstraint(sketch, fields[prop]),
                                        FreeCAD.Units.Quantity(value, FreeCAD.Units.Length))
                self.doc.recompute()
                self.assertValidSheet(wall)
                self.assertLess(plain.cut(wall.Shape).Volume + wall.Shape.cut(plain).Volume, 0.01)
                self.assertEqual(len(wall.Shape.Faces), len(plain.Faces), "face count")

    def test_extends_follow_the_wall(self):
        """Extends stay exact when the line the flat part starts on moves
        (radius, angle, Length Spec) or Length changes. A negative Extend
        stays on the wall and starts where the flat part starts.
        """
        starts = [
            ("negative Extend A", {"gap1": 5.0, "extend1": -2.0}),
            ("negative Extend B", {"gap2": 6.0, "extend2": -3.0}),
            ("positive Extend B", {"extend2": 3.0}),
        ]
        changes = [
            ("Length 20->30", {"length": 30.0}),
            ("radius 1->3", {"radius": 3.0}),
            ("angle 90->60", {"angle": 60.0}),
            ("Length Spec Leg", {"LengthSpec": "Leg"}),
        ]
        for slabel, start in starts:
            for clabel, change in changes:
                with self.subTest(start=slabel, change=clabel):
                    base = dict(start, LengthSpec="Outer Sharp")
                    plain = add_wall(self.doc, self.plate, **dict(base, **change)).Shape
                    wall = add_wall(self.doc, self.plate, **base)
                    sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                    for prop, value in change.items():
                        setattr(wall, prop, value)
                        if prop == "length":  # the task panel also edits the sketch's Length
                            sketch.setDatum(SheetMetalCmd.smFindNamedConstraint(sketch, "Length"),
                                            FreeCAD.Units.Quantity(value, FreeCAD.Units.Length))
                    self.doc.recompute()
                    self.assertValidSheet(wall)
                    self.assertLess(plain.cut(wall.Shape).Volume + wall.Shape.cut(plain).Volume, 0.01)
                    self.assertEqual(len(wall.Shape.Faces), len(plain.Faces), "face count")

    def test_outline_walls_have_no_miters(self):
        """A wall with an outline sketch ignores its miter settings: angled sides are drawn in
        the sketch. Edit Outline isn't offered while a wall has miters, so it
        never changes the wall."""
        tee = [(0, 0), (0, 10), (-10, 10), (-10, 20), (110, 20), (110, 10), (100, 10), (100, 0)]
        unmitered = self.outline_wall(tee).Shape.Volume
        for angle in (10.0, -10.0):
            with self.subTest(f"miter angles of {angle} are ignored"):
                wall = self.outline_wall(tee, AutoMiter=False, miterangle1=angle, miterangle2=angle)
                self.assertValidSheet(wall)
                self.assertAlmostEqual(wall.Shape.Volume, unmitered, delta=0.01)
                self.assertEqual(wall.getEditorMode("miterangle1"), ["Hidden"])
        cases = [
            ("auto miter", {}, False),
            ("manual miter of 0", {"AutoMiter": False}, False),
            ("manual miter", {"AutoMiter": False, "miterangle1": 20.0}, True),
            ("negative miter", {"AutoMiter": False, "miterangle2": -15.0}, True),
        ]
        for label, props, refused in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, **props)
                reason = SheetMetalCmd.smWallOutlineUnavailableReason(wall)
                self.assertEqual("no miters" in reason, refused, reason)

    def test_starting_sketch_stands_on_the_wall(self):
        """Edit Outline shows the sketch on the wall's flat part (ADR 0001)."""
        for label, props in [("90", {}), ("45", {"angle": 45.0}), ("135", {"angle": 135.0}),
                             ("Invert", {"invert": True}),
                             ("Outer Sharp", {"LengthSpec": "Outer Sharp"})]:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, **props)
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                top = max(sketch.Shape.Edges,
                          key=lambda e: e.CenterOfMass.distanceToPoint(self.plate.Shape.CenterOfMass))
                self.assertLess(wall.Shape.distToShape(Part.Vertex(top.CenterOfMass))[0], 1e-6)

    def test_starting_sketch_is_seen_from_outside(self):
        """The sketch is seen from the outside of the bend, looking back at the
        edge. Invert keeps the same side (so the sketch never mirrors), which
        then shows the inside.
        """
        s45 = math.sqrt(0.5)
        top_right = ((PLATE_W, 0, THK), (PLATE_W, PLATE_L, THK))
        cases = [
            # label, edge, props, direction the viewer looks from
            ("top edge, up", top_right, {}, (1, 0, 0)),
            ("top edge, inverted", top_right, {"invert": True}, (-1, 0, 0)),
            ("bottom edge, down", ((PLATE_W, 0, 0), (PLATE_W, PLATE_L, 0)), {}, (1, 0, 0)),
            ("bottom rear edge, down", ((0, PLATE_L, 0), (PLATE_W, PLATE_L, 0)), {}, (0, 1, 0)),
            ("other side of the plate", ((0, 0, THK), (0, PLATE_L, THK)), {}, (-1, 0, 0)),
            ("45 degrees", top_right, {"angle": 45.0}, (s45, 0, -s45)),
            ("135 degrees", top_right, {"angle": 135.0}, (s45, 0, s45)),
        ]
        for label, edge, props, expected in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, edge=edge, **props)
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                normal = sketch.getGlobalPlacement().Rotation.multVec(Vector(0, 0, 1))
                self.assertGreater(normal.dot(Vector(*expected)), 0.999, f"normal {normal}")
                self.assertEqual(sketch.solve(), 0)
                self.assertValidSheet(wall)

    def test_knows_when_the_sketch_faces_the_inside(self):
        """Invert or a negative angle (but not both) leaves the sketch facing the
        inside of the bend. Edit Outline then turns the camera around, so the
        outline is always edited from the outside.
        """
        cases = [{}, {"invert": True}, {"angle": -90.0}, {"invert": True, "angle": -90.0},
                 {"angle": 45.0, "invert": True}, {"angle": -135.0},
                 {"edge": ((PLATE_W, 0, 0), (PLATE_W, PLATE_L, 0)), "invert": True}]
        for props in cases:
            with self.subTest(**{k: v for k, v in props.items() if k != "edge"},
                              bottom_edge="edge" in props):
                wall = add_wall(self.doc, self.plate, **props)
                placement = SheetMetalCmd.smCreateWallOutlineSketch(wall).getGlobalPlacement()
                bend = next(f.Surface for f in wall.Shape.Faces
                            if isinstance(f.Surface, Part.Cylinder))
                # The sketch's plane is on the side of the bend axis away from
                # the bend's center; Sketcher looks from the sketch's +z side.
                offset = placement.Base - bend.Center
                normal = placement.Rotation.multVec(Vector(0, 0, 1))
                faces_inside = normal.dot(offset) < 0
                self.assertEqual(SheetMetalCmd.smOutlineFacesInside(wall), faces_inside)

    def test_stale_frame_from_an_older_file(self):
        """Edit Outline uses the wall as it is now, not the frame a file stored.

        A wall loaded from a file isn't recomputed until something changes,
        so its stored frame can come from older code.
        """
        wall = add_wall(self.doc, self.plate)
        stale = FreeCAD.Placement(Vector(0, 0, 0), FreeCAD.Rotation(Vector(0, 0, 1), 180))
        wall.OutlineFrame = stale
        sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
        normal = sketch.getGlobalPlacement().Rotation.multVec(Vector(0, 0, 1))
        self.assertGreater(normal.dot(Vector(1, 0, 0)), 0.999, f"normal {normal}")
        wall.OutlineFrame = stale
        SheetMetalCmd.smRefreshWallOutlineTilt(wall)
        self.doc.recompute()
        normal = sketch.getGlobalPlacement().Rotation.multVec(Vector(0, 0, 1))
        self.assertGreater(normal.dot(Vector(1, 0, 0)), 0.999, f"after refresh {normal}")

    def test_sketch_stays_put_when_the_viewing_side_changes(self):
        """Invert changes which side the sketch is seen from, but never mirrors it.

        The sketch's direction along the edge doesn't depend on Invert.
        """
        wall = add_wall(self.doc, self.plate, gap1=5.0, gap2=20.0)
        sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
        before = upper_part(wall).BoundBox
        wall.invert = True
        self.doc.recompute()
        SheetMetalCmd.smRefreshWallOutlineTilt(wall)
        self.doc.recompute()
        self.assertValidSheet(wall)
        self.assertEqual(sketch.solve(), 0)
        lower = wall.Shape.common(Part.makeBox(200, 400, 200, Vector(-50, -150, -210))).BoundBox
        self.assertAlmostEqual(lower.YMin, before.YMin, places=3)
        self.assertAlmostEqual(lower.YMax, before.YMax, places=3)

    def test_custom_outlines(self):
        """Each outline gives the volume its flat pattern says, and a valid solid.

        Chains are listed left to right. Plate edge 0..100, Leg unless noted.
        """
        ba = bend_allowance()
        outer = (RADIUS + THK)  # Outer Sharp setback at 90 degrees
        cases = [
            # label, chain, props, bend span, reliefs
            ("one end dragged past the corner (Creo)",
             [(-5, 12), (-5, 20), (100, 20), (100, 0)], {}, (0, 100), 0),
            ("centred tab: loose ends on the reference line narrow the bend",
             [(30, 0), (30, 15), (70, 15), (70, 0)], {}, (30, 70), 2),
            ("one corner notched",
             [(0, 0), (0, 20), (80, 20), (80, 12), (100, 12), (100, 0)], {}, (0, 100), 0),
            ("tapered: closing lines angle through the bend",
             [(20, 18), (80, 18)], {}, (0, 100), 0),
            ("taper with Outer Sharp",
             [(20, 18), (80, 18)], {"LengthSpec": "Outer Sharp"}, (0, 100), 0),
            ("arc on top",
             None, {}, (0, 100), 0),
        ]
        for label, chain, props, span, reliefs in cases:
            with self.subTest(label):
                setback = outer if props.get("LengthSpec") == "Outer Sharp" else 0.0
                if chain is None:
                    wall = add_wall(self.doc, self.plate, **props)
                    sketch = self.doc.addObject("Sketcher::SketchObject", "Outline")
                    sketch.addGeometry(Part.LineSegment(Vector(0, 0, 0), Vector(0, 10, 0)))
                    sketch.addGeometry(Part.ArcOfCircle(
                        Part.Circle(Vector(50, 10, 0), Vector(0, 0, 1), 50), 0, math.pi))
                    sketch.addGeometry(Part.LineSegment(Vector(100, 10, 0), Vector(100, 0, 0)))
                    SheetMetalCmd.smAddBendEndPoints(sketch, wall)
                    wall.OutlineSketch = sketch
                    self.doc.recompute()
                    area = 100 * (10 + ba - setback) + math.pi * 50 ** 2 / 2
                else:
                    wall = self.outline_wall(chain, **props)
                    area = outline_area(chain, *span, ba - setback)
                self.assertValidSheet(wall)
                expected = PLATE_VOLUME + area * THK - reliefs * RELIEF_VOLUME
                self.assertAlmostEqual(wall.Shape.Volume, expected, delta=expected * 2e-4)

    def assertFlatOutline(self, chain, span, reliefs, old_unfolder):
        ba = bend_allowance()
        wall = self.outline_wall(chain)
        flat = unfold(self.doc, wall, old_unfolder)
        self.assertValidSheet(flat)
        expected = PLATE_VOLUME + outline_area(chain, *span, ba) * THK - reliefs * RELIEF_VOLUME
        self.assertAlmostEqual(flat.Shape.Volume, expected, delta=expected * 2e-4)
        self.assertAlmostEqual(flat.Shape.BoundBox.ZLength, THK, places=3)
        top = max(y for _x, y in chain)
        self.assertAlmostEqual(flat.Shape.BoundBox.XLength, PLATE_W + ba + top, places=2)

    def test_unfolders_give_the_outline(self):
        """Unfolding a wall with an outline sketch gives the plate plus the outline, flat.

        The old unfolder is only checked on square bend ends: see
        test_old_unfolder_angled_bend_ends.
        """
        cases = [
            # label, chain, bend span, reliefs, also check the old unfolder
            ("Creo drag", [(-5, 12), (-5, 20), (100, 20), (100, 0)], (0, 100), 0, False),
            ("centred tab", [(30, 0), (30, 15), (70, 15), (70, 0)], (30, 70), 2, True),
            ("taper", [(20, 18), (80, 18)], (0, 100), 0, False),
        ]
        for label, chain, span, reliefs, check_old in cases:
            for old in (False, True) if check_old else (False,):
                with self.subTest(label, unfolder="old" if old else "new"):
                    self.assertFlatOutline(chain, span, reliefs, old)

    @unittest.expectedFailure
    def test_old_unfolder_angled_bend_ends(self):
        """Known gap: the old unfolder leaves a bend with angled ends 0.2 mm out of flat."""
        self.assertFlatOutline([(20, 18), (80, 18)], (0, 100), 0, True)

    def test_same_flat_part_at_any_angle(self):
        """With Leg, the flat part above the bend is the same at 45, 90 and 135 degrees."""
        chain = [(0, 0), (0, 20), (80, 20), (80, 12), (100, 12), (100, 0)]
        for angle in (45.0, 90.0, 135.0):
            with self.subTest(angle=angle):
                wall = self.outline_wall(chain, angle=angle)
                flat = unfold(self.doc, wall, False)
                ba = bend_allowance(angle)
                expected = PLATE_VOLUME + outline_area(chain, 0, 100, ba) * THK
                self.assertAlmostEqual(flat.Shape.Volume, expected, delta=expected * 2e-4)
                self.assertAlmostEqual(flat.Shape.BoundBox.XLength, PLATE_W + ba + 20, places=2)

    def test_outer_sharp_height_ignores_the_radius(self):
        """With Outer Sharp the outline's height is measured from the edge line."""
        tops = []
        for radius in (1.0, 3.0):
            wall = self.outline_wall([(0, 0), (0, 20), (100, 20), (100, 0)],
                                    LengthSpec="Outer Sharp", radius=radius)
            self.assertValidSheet(wall)
            tops.append(wall.Shape.BoundBox.ZMax)
        self.assertAlmostEqual(tops[0], tops[1], places=3)

    def test_length_spec_adds_no_seams(self):
        """Every Length Spec gives the wall the same faces as Leg.

        A setback puts the reference line inside the bend in the flat pattern,
        so a loose end on it meets its closing line partway along a bend end.
        That bend end must still be one face, not two with a seam between.
        """
        chains = [
            ("one end dragged past the corner (Creo)",
             [(-5, 12), (-5, 20), (100, 20), (100, 0)]),
            ("notched, other end dragged",
             [(-5, 12), (-5, 20), (80, 20), (80, 12), (100, 12), (100, 0)]),
        ]
        for label, chain in chains:
            leg = len(self.outline_wall(chain).Shape.Faces)
            for spec in ("Outer Sharp", "Inner Sharp", "Tangential"):
                with self.subTest(label, LengthSpec=spec):
                    wall = self.outline_wall(chain, LengthSpec=spec)
                    self.assertValidSheet(wall)
                    self.assertEqual(len(wall.Shape.Faces), leg, "face count")

    def test_flat_part_steps_out_past_a_bend_end(self):
        """A loose end on the reference line past a bend end keeps that bend end
        square: outside it, nothing below where the flat part starts is kept,
        whatever the sketch does down there (ADR 0002).

        With a setback, these chains turn below where the flat part starts.
        """
        simple = [(-10, 0), (-10, 20), (100, 20), (100, 0)]
        variants = [
            ("notch", [(-3, 0), (-3, 0.5), (-10, 0.5), (-10, 20), (100, 20), (100, 0)]),
            ("slant", [(-3, 0), (-10, 0.5), (-10, 20), (100, 20), (100, 0)]),
        ]
        for spec in ("Outer Sharp", "Inner Sharp", "Tangential"):
            plain = self.outline_wall(simple, LengthSpec=spec).Shape
            for label, chain in variants:
                with self.subTest(label, LengthSpec=spec):
                    wall = self.outline_wall(chain, LengthSpec=spec)
                    self.assertValidSheet(wall)
                    self.assertLess(plain.cut(wall.Shape).Volume + wall.Shape.cut(plain).Volume,
                                    0.01)
                    self.assertEqual(len(wall.Shape.Faces), len(plain.Faces), "face count")

    def test_wall_follows_a_shorter_edge(self):
        """The starting sketch's right side follows the far end of the edge (Q16)."""
        wall = add_wall(self.doc, self.plate, gap2=5.0, extend2=2.0)
        SheetMetalCmd.smCreateWallOutlineSketch(wall)
        sketch = self.plate.BendSketch
        short = PLATE_L - 20
        sketch.moveGeometry(1, 2, Vector(PLATE_W, short, 0))
        sketch.moveGeometry(2, 1, Vector(PLATE_W, short, 0))
        sketch.moveGeometry(2, 2, Vector(0, short, 0))
        sketch.moveGeometry(3, 1, Vector(0, short, 0))
        self.doc.recompute()
        self.assertValidSheet(wall)
        self.assertAlmostEqual(upper_part(wall).BoundBox.YMax, short - 5.0 + 2.0, places=3)

    def test_gap_moves_bend_end_and_side_together(self):
        """Changing Gap 1 and the sketch's Gap1 keeps Extend 1 (Q17)."""
        wall = add_wall(self.doc, self.plate, gap1=4.0, extend1=1.0)
        sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
        wall.gap1 = 10.0
        sketch.setDatum(SheetMetalCmd.smFindNamedConstraint(sketch, "GapA"),
                        FreeCAD.Units.Quantity(10.0, FreeCAD.Units.Length))
        self.doc.recompute()
        self.assertValidSheet(wall)
        self.assertAlmostEqual(upper_part(wall).BoundBox.YMin, 10.0 - 1.0, places=3)

    def test_gap_is_where_the_bend_end_point_is(self):
        """Gap A/B are where the sketch's bend-end points are, so the wall's own
        gap doesn't count (and is hidden). Deleting a Gap dimension changes
        nothing; the panel field then moves the point instead, and the side
        tied to it by Extend moves too.
        """
        def difference(a, b):
            return a.cut(b).Volume + b.cut(a).Volume

        for side, gap, extend in (("A", "gap1", "extend1"), ("B", "gap2", "extend2")):
            with self.subTest(side):
                wall = add_wall(self.doc, self.plate, **{gap: 4.0, extend: 1.0})
                plain = wall.Shape.copy()
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                self.assertAlmostEqual(SheetMetalCmd.smOutlineSketchGap(wall, side), 4.0)
                setattr(wall, gap, 20.0)
                self.doc.recompute()
                self.assertEqual(wall.getEditorMode(gap), ["Hidden"])
                self.assertLess(difference(plain, wall.Shape), 0.01)
                sketch.delConstraint(SheetMetalCmd.smFindNamedConstraint(sketch, "Gap" + side))
                self.doc.recompute()
                self.assertValidSheet(wall)
                self.assertLess(difference(plain, wall.Shape), 0.01)
                self.assertTrue(SheetMetalCmd.smMoveOutlineBendEnd(wall, side, 10.0))
                self.doc.recompute()
                self.assertValidSheet(wall)
                self.assertAlmostEqual(SheetMetalCmd.smOutlineSketchGap(wall, side), 10.0)
                moved = add_wall(self.doc, self.plate, **{gap: 10.0, extend: 1.0}).Shape
                self.assertLess(difference(moved, wall.Shape), 0.01)
                # Past the end of the edge, as a negative gap allows.
                SheetMetalCmd.smMoveOutlineBendEnd(wall, side, -3.0)
                self.doc.recompute()
                self.assertValidSheet(wall)
                past = add_wall(self.doc, self.plate, **{gap: -3.0, extend: 1.0}).Shape
                self.assertLess(difference(past, wall.Shape), 0.01)

    def test_length_survives_editing_a_top_corner(self):
        """Trimming or rounding either top corner keeps the Length dimension.

        Sketcher's Trim drops a point-to-line distance when it trims away the
        part of the line nearest the point, so Length is measured from the
        middle of the bend span.
        """
        height, ba = 20.0, bend_allowance()
        chamfer = 6 * 6 / 2       # corner cut off by a line through (0, 14) and (6, 20)
        rounding = 9 - math.pi * 9 / 4  # corner removed by a 3 mm fillet
        cases = [
            ("trim top-left", 1, "trim", chamfer),
            ("trim top-right", -1, "trim", chamfer),
            ("round top-left", 1, "fillet", rounding),
            ("round top-right", -1, "fillet", rounding),
        ]
        for label, side, edit, removed in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate)
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)

                def at(x, y):
                    """A point measured inwards from the corner on this side."""
                    return Vector(x if side == 1 else 100 - x, y, 0)

                def geometry_at(point):
                    return min((i for i, g in enumerate(sketch.Geometry)
                                if not isinstance(g, Part.Point)),
                               key=lambda i: sketch.Geometry[i].toShape().distToShape(
                                   Part.Vertex(point))[0])

                if edit == "trim":
                    sketch.addGeometry(Part.LineSegment(at(-2, height - 8), at(8, height + 2)))
                    for pick in (at(0, height - 2), at(2, height),
                                 at(-1, height - 7), at(7, height + 1)):
                        sketch.trim(geometry_at(pick), pick)
                else:
                    top, corner_side = geometry_at(at(50, height)), geometry_at(at(0, 5))
                    sketch.fillet(top, corner_side, at(5, height), at(0, height - 5), 3.0)
                self.doc.recompute()
                index = SheetMetalCmd.smFindNamedConstraint(sketch, "Length")
                self.assertIsNotNone(index, "the Length dimension was deleted")
                self.assertValidSheet(wall)
                area = 100 * (height + ba) - removed
                self.assertAlmostEqual(wall.Shape.Volume, PLATE_VOLUME + area * THK, delta=2.0)
                before = wall.Shape.BoundBox.ZMax
                sketch.setDatum(index, FreeCAD.Units.Quantity(25.0, FreeCAD.Units.Length))
                self.doc.recompute()
                self.assertValidSheet(wall)
                self.assertAlmostEqual(wall.Shape.BoundBox.ZMax - before, 5.0, places=4)

    def test_removing_the_sketch_gives_the_plain_wall_back(self):
        wall = add_wall(self.doc, self.plate)
        plain_volume = wall.Shape.Volume
        sketch = outline_sketch(self.doc, [(30, 0), (30, 15), (70, 15), (70, 0)])
        SheetMetalCmd.smAddBendEndPoints(sketch, wall)
        wall.OutlineSketch = sketch
        self.doc.recompute()
        self.assertNotAlmostEqual(wall.Shape.Volume, plain_volume, places=0)
        self.doc.removeObject(sketch.Name)
        self.doc.recompute()
        self.assertIsNone(wall.OutlineSketch)
        self.assertAlmostEqual(wall.Shape.Volume, plain_volume, places=3)
        self.assertEqual(wall.getEditorMode("length"), [])

    def test_perforated_outline(self):
        """Perforation still cuts the bend of a wall with an outline sketch (Q20)."""
        chain = [(30, 0), (30, 15), (70, 15), (70, 0)]
        solid = self.outline_wall(chain).Shape.Volume
        wall = self.outline_wall(chain, Perforate=True)
        self.assertValidSheet(wall)
        self.assertLess(wall.Shape.Volume, solid - 1.0)

    def test_errors(self):
        """Bad outline sketches fail with a clear message, not a traceback."""
        cases = [
            ("closed", [(0, 0), (0, 10), (100, 10), (100, 0), (0, 0)], {}, "must be open"),
            ("dips onto the sheet", [(0, 0), (0, 10), (50, -2), (100, 10), (100, 0)], {},
             "dips below the reference line"),
            ("closing line crosses the sketch",
             [(60, 10), (60, 3), (20, 3), (20, 20), (100, 20), (100, 0)], {}, "crosses"),
            ("slot splits the bend",
             [(0, 0), (0, 20), (100, 20), (100, 0), (60, 0), (60, 10), (40, 10), (40, 0)],
             {"LengthSpec": "Outer Sharp"}, "splits the bend"),
            ("negative Extend cuts away the flat part", [(0, 0), (0, 20), (100, 20), (100, 0)],
             {"extend1": -150.0}, "whole flat part"),
        ]
        for label, chain, props, message in cases:
            with self.subTest(label):
                wall = self.outline_wall(chain, **props)
                self.assertIn("Invalid", wall.State)
                self.assertIn(message, wall.getStatusString())
        missing = "(Gap A) is missing from the outline sketch"
        off_line = "(Gap A) is no longer held on the outline sketch's reference line"
        with self.subTest("bend-end point deleted"):
            wall = add_wall(self.doc, self.plate)
            sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
            sketch.delGeometry(SheetMetalCmd.smOutlineBendEnd(sketch, "A")[0])
            self.doc.recompute()
            self.assertIn(missing, wall.getStatusString())
            self.assertFalse(SheetMetalCmd.smMoveOutlineBendEnd(wall, "A", 5.0))
        for kept, deleted in (("GapA", "ExtendA"), ("ExtendA", "GapA")):
            with self.subTest("bend-end point let off the line", kept=kept):
                wall = add_wall(self.doc, self.plate)
                sketch = SheetMetalCmd.smCreateWallOutlineSketch(wall)
                for name in ("BendEndA", deleted):
                    sketch.delConstraint(SheetMetalCmd.smFindNamedConstraint(sketch, name))
                self.doc.recompute()
                self.assertIn(off_line, wall.getStatusString())
        with self.subTest("sketch without bend-end points"):
            wall = add_wall(self.doc, self.plate)
            wall.OutlineSketch = outline_sketch(self.doc, [(0, 0), (0, 10), (100, 10), (100, 0)])
            self.doc.recompute()
            self.assertIn(missing, wall.getStatusString())
        with self.subTest("two pieces"):
            wall = add_wall(self.doc, self.plate)
            sketch = outline_sketch(self.doc, [(0, 0), (0, 10)])
            sketch.addGeometry(Part.LineSegment(Vector(100, 0, 0), Vector(100, 10, 0)))
            wall.OutlineSketch = sketch
            self.doc.recompute()
            self.assertIn("one connected chain", wall.getStatusString())
        with self.subTest("wall on two edges"):
            from SMTests.testFeatures import edge_name
            wall = self.doc.addObject("Part::FeaturePython", "Wall2")
            SheetMetalCmd.SMBendWall(wall, self.plate, [
                edge_name(self.plate.Shape, (PLATE_W, 0, THK), (PLATE_W, PLATE_L, THK)),
                edge_name(self.plate.Shape, (0, 0, THK), (0, PLATE_L, THK))])
            self.doc.recompute()
            self.assertIn("one edge", SheetMetalCmd.smWallOutlineUnavailableReason(wall))
            wall.OutlineSketch = outline_sketch(self.doc, [(0, 0), (0, 10), (100, 10), (100, 0)])
            self.doc.recompute()
            self.assertIn("exactly one edge", wall.getStatusString())
