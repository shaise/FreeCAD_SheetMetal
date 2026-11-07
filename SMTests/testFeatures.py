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

"""Feature-level tests: build sheet metal models from scratch and check the result.

Expected values come from closed-form formulas wherever the geometry allows it
(volumes of plates, bends and walls, bend allowance). Shapes that are awkward to
describe by formula use golden values recorded from upstream commit cbf6595.

Run with:  FreeCADCmd -t TestSheetMetal
"""

import math
import unittest

import FreeCAD
import Part
from FreeCAD import Vector

import SheetMetalBaseCmd
import SheetMetalBaseShapeCmd
import SheetMetalBend
import SheetMetalCmd
import SheetMetalHem
import SheetMetalJunction
import SheetMetalUnfoldCmd

# Plate used by most wall tests: 50 x 100 mm, 2 mm thick, lying on XY.
PLATE_W, PLATE_L, THK = 50.0, 100.0, 2.0
PLATE_VOLUME = PLATE_W * PLATE_L * THK
# The wall is added along the long edge at x = PLATE_W.
WALL_EDGE_TOP = ((PLATE_W, 0.0, THK), (PLATE_W, PLATE_L, THK))
WALL_EDGE_BOTTOM = ((PLATE_W, 0.0, 0.0), (PLATE_W, PLATE_L, 0.0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bend_volume(angle_deg, radius, thickness, width):
    """Volume of a bend: an annular sector of the given angle."""
    ring = (radius + thickness) ** 2 - radius ** 2
    return math.pi * ring * width * angle_deg / 360.0


def polyline_sketch(doc, points, closed=True, name="Sketch"):
    sketch = doc.addObject("Sketcher::SketchObject", name)
    ends = points[1:] + (points[:1] if closed else [])
    for start, end in zip(points, ends):
        sketch.addGeometry(Part.LineSegment(Vector(*start), Vector(*end)))
    return sketch


def make_base_wall(doc, sketch, thickness=THK, radius=1.0, length=None):
    base = doc.addObject("Part::FeaturePython", "BaseBend")
    SheetMetalBaseCmd.SMBaseBend(base, sketch)
    base.Thickness = thickness
    base.Radius = radius
    if length is not None:
        base.Length = length
    doc.recompute()
    return base


def make_plate(doc):
    corners = [(0, 0, 0), (PLATE_W, 0, 0), (PLATE_W, PLATE_L, 0), (0, PLATE_L, 0)]
    return make_base_wall(doc, polyline_sketch(doc, corners))


def edge_name(shape, end_a, end_b):
    """Find a straight edge by its end points (order does not matter)."""
    wanted = {tuple(round(c, 6) for c in end_a), tuple(round(c, 6) for c in end_b)}
    for i, edge in enumerate(shape.Edges):
        ends = {tuple(round(c, 6) for c in v.Point) for v in edge.Vertexes}
        if ends == wanted:
            return f"Edge{i + 1}"
    raise LookupError(f"No edge between {end_a} and {end_b}")


def face_name(shape, predicate):
    for i, face in enumerate(shape.Faces):
        if predicate(face):
            return f"Face{i + 1}"
    raise LookupError("No matching face")


def is_flat_face(normal_z):
    def predicate(face):
        return (face.Surface.TypeId == "Part::GeomPlane"
                and abs(face.normalAt(0, 0).z - normal_z) < 1e-6
                and face.Area > 100)
    return predicate


def add_wall(doc, base, edge=WALL_EDGE_TOP, **props):
    wall = doc.addObject("Part::FeaturePython", "Wall")
    SheetMetalCmd.SMBendWall(wall, base, [edge_name(base.Shape, *edge)])
    wall.length = 20.0
    wall.radius = 1.0
    for name, value in props.items():
        setattr(wall, name, value)
    doc.recompute()
    return wall


SM_PARAMS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
# Saved settings that change what a new feature looks like: the defaults
# each command remembers (Length Spec, Bend Type, radius...) and the
# unfolder choice. Tests run with the built-in values instead.
_PARAM_KINDS = {"String": "String", "Float": "Float", "Boolean": "Bool",
                "Integer": "Int", "Unsigned": "Unsigned"}


def _is_isolated_param(name):
    return name.startswith("default") or name == "UseOldUnfolder"


class FeatureTestCase(unittest.TestCase):
    """Gives each test its own document, common shape assertions, and
    SheetMetal's built-in defaults instead of the user's saved ones."""

    def setUp(self):
        self._saved_params = [entry for entry in (SM_PARAMS.GetContents() or [])
                              if _is_isolated_param(entry[1]) and entry[0] in _PARAM_KINDS]
        for kind, name, _value in self._saved_params:
            getattr(SM_PARAMS, "Rem" + _PARAM_KINDS[kind])(name)
        self.doc = FreeCAD.newDocument(self.__class__.__name__)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)
        # Drop whatever the test left behind, then put the user's back.
        for kind, name, _value in (SM_PARAMS.GetContents() or []):
            if _is_isolated_param(name) and kind in _PARAM_KINDS:
                getattr(SM_PARAMS, "Rem" + _PARAM_KINDS[kind])(name)
        for kind, name, value in self._saved_params:
            getattr(SM_PARAMS, "Set" + _PARAM_KINDS[kind])(name, value)

    def assertValidSheet(self, obj):
        self.assertNotIn("Invalid", obj.State, f"{obj.Name} failed to recompute")
        self.assertTrue(obj.Shape.isValid(), f"{obj.Name} has an invalid shape")
        self.assertEqual(len(obj.Shape.Solids), 1, f"{obj.Name} is not a single solid")

    def assertBounds(self, shape, expected, places=3):
        box = shape.BoundBox
        actual = (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
        for axis, a, e in zip(("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"), actual, expected):
            if e is not None:
                self.assertAlmostEqual(a, e, places=places, msg=axis)


# ---------------------------------------------------------------------------
# Base walls
# ---------------------------------------------------------------------------

class TestBaseWall(FeatureTestCase):

    def test_closed_sketch_makes_flat_plate(self):
        """A closed outline becomes a plate; inner loops become holes."""
        outline = [(0, 0, 0), (60, 0, 0), (60, 40, 0), (0, 40, 0)]
        hole = [(20, 10, 0), (40, 10, 0), (40, 30, 0), (20, 30, 0)]
        cases = [
            ("rectangle", [outline], 60 * 40 * THK),
            ("rectangle with hole", [outline, hole], (60 * 40 - 20 * 20) * THK),
        ]
        for label, loops, volume in cases:
            with self.subTest(label):
                sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
                for loop in loops:
                    for start, end in zip(loop, loop[1:] + loop[:1]):
                        sketch.addGeometry(Part.LineSegment(Vector(*start), Vector(*end)))
                base = make_base_wall(self.doc, sketch)
                self.assertValidSheet(base)
                self.assertAlmostEqual(base.Shape.Volume, volume, places=3)
                self.assertBounds(base.Shape, (0, 0, 0, 60, 40, THK))

    def test_open_profile_makes_bent_channel(self):
        """An open profile is extruded with a bend at every corner.

        The centre line is each segment shortened by the corner radius of the
        sketch line at every bend it touches, plus a quarter circle at
        radius + thickness / 2 per bend.

        With BendSide = Outside, the material goes on a fixed side of the
        drawing direction: a profile drawn clockwise has the sketch as its outer
        skin (corner radius r + t), the same profile drawn anticlockwise has it
        as the inner skin (corner radius r).
        """
        thickness, radius, length = 1.0, 1.0, 50.0
        outer_r = radius + thickness
        quarter = math.pi / 2 * (radius + thickness / 2)
        cases = [
            # label, profile points, centre-line length
            ("L clockwise", [(40, 0, 0), (0, 0, 0), (0, 30, 0)],
             (30 - outer_r) + (40 - outer_r) + quarter),
            ("L anticlockwise", [(0, 30, 0), (0, 0, 0), (40, 0, 0)],
             (30 - radius) + (40 - radius) + quarter),
            ("U clockwise", [(0, 0, 0), (0, 30, 0), (40, 30, 0), (40, 0, 0)],
             2 * (30 - outer_r) + (40 - 2 * outer_r) + 2 * quarter),
        ]
        for label, points, centre_line in cases:
            with self.subTest(label):
                sketch = polyline_sketch(self.doc, points, closed=False)
                base = make_base_wall(self.doc, sketch, thickness, radius, length)
                self.assertValidSheet(base)
                self.assertAlmostEqual(base.Shape.Volume,
                                       centre_line * thickness * length, places=2)
                self.assertAlmostEqual(base.Shape.BoundBox.ZLength, length, places=3)


# ---------------------------------------------------------------------------
# Make Wall (SMBendWall)
# ---------------------------------------------------------------------------

class TestMakeWall(FeatureTestCase):

    def setUp(self):
        super().setUp()
        self.plate = make_plate(self.doc)

    def test_orientation(self):
        """Edge side, invert, sign and size of the angle decide where the wall goes.

        The wall bends towards the face of the selected edge: the top edge sends
        it up, the bottom edge down.
        """
        r = 1.0
        straight = 20.0 * THK * PLATE_L
        cases = [
            # label, edge, props, angle for volume, (ZMin, ZMax)
            ("top edge goes up", WALL_EDGE_TOP, {}, 90, (0, THK + r + 20)),
            ("bottom edge goes down", WALL_EDGE_BOTTOM, {}, 90, (-(r + 20), THK)),
            ("invert flips", WALL_EDGE_TOP, {"invert": True}, 90, (-(r + 20), THK)),
            ("negative angle flips", WALL_EDGE_TOP, {"angle": -90}, 90, (-(r + 20), THK)),
            ("45 degrees", WALL_EDGE_TOP, {"angle": 45}, 45, (0, None)),
            ("135 degrees", WALL_EDGE_TOP, {"angle": 135}, 135, (0, None)),
            ("zero radius", WALL_EDGE_TOP, {"radius": 0.0}, 90, (0, THK + 20)),
        ]
        for label, edge, props, angle, (zmin, zmax) in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, edge, **props)
                self.assertValidSheet(wall)
                radius = props.get("radius", r)
                expected = PLATE_VOLUME + bend_volume(angle, radius, THK, PLATE_L) + straight
                self.assertAlmostEqual(wall.Shape.Volume, expected, places=2)
                self.assertBounds(wall.Shape, (0, 0, zmin, None, PLATE_L, zmax))

    def test_wall_position(self):
        """BendType moves the bend relative to the edge and trims the plate to suit."""
        r = 1.0
        full = PLATE_VOLUME + bend_volume(90, r, THK, PLATE_L) + 20.0 * THK * PLATE_L
        cases = [
            # label, removed plate strip width, XMax
            ("Material Outside", 0.0, PLATE_W + r + THK),
            ("Thickness Outside", r, PLATE_W + THK),
            ("Material Inside", r + THK, PLATE_W),
        ]
        for label, strip, xmax in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, BendType=label)
                self.assertValidSheet(wall)
                self.assertAlmostEqual(wall.Shape.Volume,
                                       full - strip * THK * PLATE_L, places=2)
                self.assertAlmostEqual(wall.Shape.BoundBox.XMax, xmax, places=3)

    def test_length_spec(self):
        """LengthSpec decides where the 20 mm length is measured from."""
        r = 1.0
        cases = [
            # label, straight wall length, ZMax
            ("Leg", 20.0, THK + r + 20.0),
            ("Inner Sharp", 20.0 - r, THK + 20.0),
            ("Outer Sharp", 20.0 - (r + THK), 20.0),
            ("Tangential", 20.0 - (r + THK), 20.0),
        ]
        for label, straight, zmax in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, LengthSpec=label)
                self.assertValidSheet(wall)
                expected = (PLATE_VOLUME + bend_volume(90, r, THK, PLATE_L)
                            + straight * THK * PLATE_L)
                self.assertAlmostEqual(wall.Shape.Volume, expected, places=2)
                self.assertAlmostEqual(wall.Shape.BoundBox.ZMax, zmax, places=3)

    def test_gaps_and_extends(self):
        """Gaps shorten bend and wall; extends lengthen only the wall."""
        r = 1.0
        bend = bend_volume(90, r, THK, PLATE_L)
        cases = [
            # label, props, (YMin, YMax) of the result, expected volume or None
            ("extend both ends", {"extend1": 5.0, "extend2": 5.0}, (-5.0, PLATE_L + 5.0),
             PLATE_VOLUME + bend + 20.0 * THK * (PLATE_L + 10.0)),
            # Gaps add relief cuts, so only check the wall stays within the gaps.
            ("gaps at both ends", {"gap1": 10.0, "gap2": 5.0}, (0.0, PLATE_L), None),
        ]
        for label, props, (ymin, ymax), volume in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, self.plate, **props)
                self.assertValidSheet(wall)
                self.assertBounds(wall.Shape, (None, ymin, None, None, ymax, None))
                if volume is not None:
                    self.assertAlmostEqual(wall.Shape.Volume, volume, places=2)
                else:
                    # Everything above the plate lies between the two gaps.
                    upper = wall.Shape.common(Part.makeBox(
                        PLATE_W + 10, PLATE_L + 10, 30, Vector(0, -5, THK + 0.01)))
                    self.assertAlmostEqual(upper.BoundBox.YMin, 10.0, places=3)
                    self.assertAlmostEqual(upper.BoundBox.YMax, PLATE_L - 5.0, places=3)

    def test_closed_sketch_wall(self):
        """#601: a closed sketch on the plate's edge face builds a valid wall.

        Crashed until 9d6bae8. The wall's outline isn't checked here, because
        this mode is due to be replaced (see the Edit Wall Outline prototype).
        """
        thin_face = face_name(self.plate.Shape, lambda f: f.normalAt(0, 0).x > 0.99)
        sketch = self.doc.addObject("Sketcher::SketchObject", "WallOutline")
        sketch.AttachmentSupport = [(self.plate, thin_face)]
        sketch.MapMode = "FlatFace"
        outline = [(0, 0, 0), (PLATE_L, 0, 0), (PLATE_L, 15, 0), (0, 15, 0)]
        for start, end in zip(outline, outline[1:] + outline[:1]):
            sketch.addGeometry(Part.LineSegment(Vector(*start), Vector(*end)))
        self.doc.recompute()
        wall = add_wall(self.doc, self.plate, Sketch=sketch)
        self.assertValidSheet(wall)


# ---------------------------------------------------------------------------
# Other features
# ---------------------------------------------------------------------------

class TestUnfold(FeatureTestCase):

    def test_bend_allowance(self):
        """Flat length = plate + wall + bend allowance, BA = angle * (r + K * t)."""
        cases = [
            # label, K-factor, bend radius
            ("K 0.5", 0.5, 1.0),
            ("K 0.3", 0.3, 1.0),
            ("K 0.5, larger radius", 0.5, 3.0),
        ]
        for label, k, radius in cases:
            with self.subTest(label):
                wall = add_wall(self.doc, make_plate(self.doc), radius=radius)
                unfold = self.doc.addObject("Part::FeaturePython", "Unfold")
                SheetMetalUnfoldCmd.SMUnfold(unfold, wall, [face_name(wall.Shape, is_flat_face(1))])
                unfold.MaterialSheet = "_manual"
                unfold.KFactor = k
                self.doc.recompute()
                self.assertValidSheet(unfold)
                allowance = math.pi / 2 * (radius + k * THK)
                flat = PLATE_W + 20.0 + allowance
                self.assertBounds(unfold.Shape, (0, 0, 0, flat, PLATE_L, THK))


class TestBaseShape(FeatureTestCase):

    def test_shape_types(self):
        """Every preset builds one valid solid of the requested size.

        Volumes are golden values recorded from upstream cbf6595.
        """
        width, length, height, flange, thickness = 40.0, 60.0, 20.0, 5.0, 1.0
        cases = [
            # shapeType, (XLength, YLength, ZLength), volume
            ("Flat", (length, width, thickness), length * width * thickness),
            ("L-Shape", (length, width, height), 3501.372),
            ("U-Shape", (length, width, height), 4602.743),
            ("Tub", (length, width, height), 5891.140),
            ("Hat", (length + 2 * flange, width + 2 * flange, height), 6852.044),
            ("Box", (length, width, height), 6609.195),
        ]
        for shape_type, size, volume in cases:
            with self.subTest(shape_type):
                obj = self.doc.addObject("Part::FeaturePython", "BaseShape")
                SheetMetalBaseShapeCmd.SMBaseShape(obj)
                obj.shapeType = shape_type
                obj.thickness, obj.radius = thickness, 1.0
                obj.width, obj.length, obj.height = width, length, height
                obj.flangeWidth = flange
                self.doc.recompute()
                self.assertValidSheet(obj)
                box = obj.Shape.BoundBox
                for actual, expected in zip((box.XLength, box.YLength, box.ZLength), size):
                    self.assertAlmostEqual(actual, expected, places=3)
                self.assertAlmostEqual(obj.Shape.Volume, volume, places=2)


class TestHem(FeatureTestCase):

    def test_hem_types(self):
        """Each hem folds back over the top of the plate.

        Flat is checked by formula (zero radius, 180-degree bend, return length
        width - thickness); the others use golden values from upstream cbf6595.
        """
        flat = PLATE_VOLUME + bend_volume(180, 0.0, THK, PLATE_L) + (10.0 - THK) * THK * PLATE_L
        cases = [
            # HemType, volume, (XMax, ZMax)
            ("Flat", flat, (PLATE_W + THK, 2 * THK)),
            ("Open", 12442.478, (PLATE_W + 2.5, 5.0)),
            ("Teardrop", 12658.624, (PLATE_W + 3.0, 6.0)),
            ("Rolled", 12020.890, (PLATE_W + 3.0, 6.0)),
        ]
        plate = make_plate(self.doc)
        for hem_type, volume, (xmax, zmax) in cases:
            with self.subTest(hem_type):
                hem = self.doc.addObject("Part::FeaturePython", "Hem")
                SheetMetalHem.SMHem(hem, plate, [edge_name(plate.Shape, *WALL_EDGE_TOP)])
                hem.HemType = hem_type
                self.doc.recompute()
                self.assertValidSheet(hem)
                self.assertAlmostEqual(hem.Shape.Volume, volume, places=2)
                self.assertBounds(hem.Shape, (0, 0, 0, xmax, PLATE_L, zmax))


class TestSolidToSheet(FeatureTestCase):

    def test_shell_box_to_unfold(self):
        """Open box shell -> Junction -> Bend -> Unfold keeps the material volume."""
        thickness = 1.0
        solid = Part.makeBox(40, 30, 20)
        top = next(f for f in solid.Faces if f.normalAt(0, 0).z > 0.99)
        shell = self.doc.addObject("Part::Feature", "Shell")
        shell.Shape = solid.makeThickness([top], -thickness, 1e-4)

        def corner_edges(shape):
            names = []
            for i, e in enumerate(shape.Edges):
                a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
                if abs(a.z - b.z) > 19 and round(a.x, 6) in (0, 40) and round(a.y, 6) in (0, 30):
                    names.append(f"Edge{i + 1}")
            return names

        junction = self.doc.addObject("Part::FeaturePython", "Junction")
        SheetMetalJunction.SMJunction(junction, shell, corner_edges(shell.Shape))
        self.doc.recompute()
        self.assertValidSheet(junction)

        # Outer bottom edges: the bend finds the matching inner edge itself.
        bottom = [f"Edge{i + 1}" for i, e in enumerate(junction.Shape.Edges)
                  if all(abs(v.Point.z) < 1e-6 for v in e.Vertexes) and e.Length > 5]
        bend = self.doc.addObject("Part::FeaturePython", "Bend")
        SheetMetalBend.SMSolidBend(bend, junction, bottom)
        self.doc.recompute()
        self.assertValidSheet(bend)

        unfold = self.doc.addObject("Part::FeaturePython", "Unfold")
        SheetMetalUnfoldCmd.SMUnfold(unfold, bend, [face_name(bend.Shape, is_flat_face(-1))])
        unfold.MaterialSheet = "_manual"
        unfold.KFactor = 0.5
        self.doc.recompute()
        self.assertValidSheet(unfold)
        self.assertAlmostEqual(unfold.Shape.BoundBox.ZLength, thickness, places=3)
        # With K = 0.5 the neutral fibre is the centre line, so volume is kept.
        self.assertAlmostEqual(unfold.Shape.Volume, bend.Shape.Volume, places=2)
