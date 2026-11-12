"""Run with FreeCAD's Test framework, or unittest in the FreeCAD console."""
import unittest

import FreeCAD
import Part

Vector = FreeCAD.Vector


def _l_bracket():
    """90-degree bend, thickness 1 mm, inside radius 2 mm, 20 mm wide.
    Flange A: x 2..3 (outer face +x). Flange B: y 2..3 (outer face +y)."""
    bend = Part.makeCylinder(3, 20).cut(Part.makeCylinder(2, 20))
    bend = bend.common(Part.makeBox(3, 3, 20))
    return bend.multiFuse([
        Part.makeBox(1, 30, 20, Vector(2, -30, 0)),
        Part.makeBox(30, 1, 20, Vector(-30, 2, 0)),
    ]).removeSplitter()


def _circles(sketch):
    return [(g.Center, g.Radius) for g in sketch.Geometry
            if type(g).__name__ == "Circle"]


class TestUnfoldMarkings(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("UnfoldMarkings")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def _unfold(self, shape, name, marks=()):
        from SheetMetalUnfoldCmd import SMUnfold

        part = self.doc.addObject("Part::Feature", name)
        part.Shape = shape
        face = next("Face" + str(i + 1) for i, f in enumerate(shape.Faces)
                    if f.Surface.TypeId == "Part::GeomPlane"
                    and f.normalAt(0, 0).x > .99 and f.Area > 100)
        obj = self.doc.addObject("Part::FeaturePython", name + "_Unfold")
        SMUnfold(obj, part, [face])
        obj.MaterialSheet = "_manual"
        obj.GenerateSketch = True
        obj.SeparateSketchLayers = True
        obj.MarkingSketches = list(marks)
        self.doc.recompute()
        self.assertNotIn("Invalid", obj.State)
        layers = {}
        for n in obj.UnfoldSketches:
            sk = self.doc.getObject(n)
            layers[sk.Label.split("_Sketch")[-1].lstrip("_") or "Outline"] = sk
        return obj, layers

    def _mark(self, name, center, normal, radius=1.5):
        feat = self.doc.addObject("Part::Feature", name)
        feat.Shape = Part.makeCircle(radius, center, normal)
        return feat

    def test_marks_match_real_holes(self):
        bracket = _l_bracket()
        # Reference: real holes through the second flange and the root flange.
        holes = bracket.cut(Part.makeCylinder(1.5, 10, Vector(-15, -2, 10), Vector(0, 1, 0)))
        holes = holes.cut(Part.makeCylinder(1.5, 10, Vector(-2, -12, 7), Vector(1, 0, 0)))
        _ref, ref_layers = self._unfold(holes, "Ref")
        expected = sorted(_circles(ref_layers["Holes"]), key=lambda c: c[0].x)
        self.assertEqual(len(expected), 2)

        marks = [
            self._mark("OnBendFlange", Vector(-15, 3, 10), Vector(0, 1, 0)),
            self._mark("OnRootFlange", Vector(3, -12, 7), Vector(1, 0, 0)),
            self._mark("BackSide", Vector(-15, 2, 10), Vector(0, 1, 0), 2.5),
            self._mark("Floating", Vector(-15, 10, 10), Vector(0, 1, 0)),
        ]
        solid = self.doc.addObject("Part::Box", "NotASketch")  # Must be ignored.
        obj, layers = self._unfold(bracket, "Part", marks + [solid])
        self.assertNotIn("Holes", layers)  # Markings never become cut geometry.
        front = sorted(_circles(layers["Marks"]), key=lambda c: c[0].x)
        self.assertEqual(len(front), 2)
        for (c, r), (ec, er) in zip(front, expected):
            self.assertAlmostEqual(r, er)
            self.assertLess(c.distanceToPoint(ec), 1e-6)

        back = _circles(layers["BackMarks"])
        self.assertEqual(len(back), 1)
        self.assertAlmostEqual(back[0][1], 2.5)
        bend_flange_hole = min(expected, key=lambda c: c[0].distanceToPoint(back[0][0]))
        self.assertLess(back[0][0].distanceToPoint(bend_flange_hole[0]), 1e-6)

        # Changing a marking sketch updates the unfold.
        marks[0].Shape = Part.makeCircle(1, Vector(-15, 3, 10), Vector(0, 1, 0))
        self.doc.recompute()
        marks_layer = next(s for s in map(self.doc.getObject, obj.UnfoldSketches)
                           if s.Label.endswith("_Sketch_Marks"))
        radii = sorted(r for _c, r in _circles(marks_layer))
        self.assertAlmostEqual(radii[0], 1)

    def test_sketch_inside_body(self):
        """Unfold outside the Body, marking sketch inside it (link scope and
        placements), plus migration of the first, locally scoped property."""
        import Sketcher
        from SheetMetalUnfoldCmd import SMUnfold

        bracket = _l_bracket()
        ref_shape = bracket.cut(
            Part.makeCylinder(1.5, 10, Vector(-15, -2, 10), Vector(0, 1, 0)))
        _ref, ref_layers = self._unfold(ref_shape, "Ref")
        (expected, _r), = _circles(ref_layers["Holes"])

        body = self.doc.addObject("PartDesign::Body", "Body")
        body.Placement = FreeCAD.Placement(Vector(100, 50, -20),
                                           FreeCAD.Rotation(Vector(1, 2, 3), 33))
        fold = body.newObject("PartDesign::Feature", "Fold")
        fold.Shape = bracket
        sketch = body.newObject("Sketcher::SketchObject", "Bolzen")
        # Sketch plane = outer face of the bent flange (y = 3).
        sketch.Placement = FreeCAD.Placement(Vector(0, 3, 0),
                                             FreeCAD.Rotation(Vector(1, 0, 0), -90))
        sketch.addGeometry(Part.Circle(Vector(-15, -10, 0), Vector(0, 0, 1), 1.5))
        self.doc.recompute()

        face = next("Face" + str(i + 1) for i, f in enumerate(bracket.Faces)
                    if f.Surface.TypeId == "Part::GeomPlane"
                    and f.normalAt(0, 0).x > .99 and f.Area > 100)
        obj = self.doc.addObject("Part::FeaturePython", "Body_Unfold")
        SMUnfold(obj, body, [face])
        self.assertEqual(obj.getTypeIdOfProperty("MarkingSketches"),
                         "App::PropertyLinkListGlobal")
        # Simulate an object created with the first (local scope) version.
        obj.removeProperty("MarkingSketches")
        obj.addProperty("App::PropertyLinkList", "MarkingSketches")
        obj.MarkingSketches = [sketch]
        obj.MaterialSheet = "_manual"
        obj.GenerateSketch = True
        obj.SeparateSketchLayers = True
        self.doc.recompute()
        self.assertNotIn("Invalid", obj.State)
        self.assertEqual(obj.getTypeIdOfProperty("MarkingSketches"),
                         "App::PropertyLinkListGlobal")
        self.assertEqual(obj.MarkingSketches, [sketch])
        layer = next(s for s in map(self.doc.getObject, obj.UnfoldSketches)
                     if s.Label.endswith("_Sketch_Marks"))
        (center, radius), = _circles(layer)
        self.assertAlmostEqual(radius, 1.5)
        self.assertLess(center.distanceToPoint(expected), 1e-6)

    def test_merged_sketch_and_curves(self):
        bracket = _l_bracket()
        ellipse = Part.Ellipse(Vector(-15, 3, 10), 4, 2)
        ellipse.Axis = Vector(0, 1, 0)
        mark = self.doc.addObject("Part::Feature", "Ellipse")
        mark.Shape = ellipse.toShape()
        obj, layers = self._unfold(bracket, "Part", [mark])
        polyline = layers["Marks"].Shape
        self.assertGreater(len(polyline.Edges), 10)
        self.assertTrue(all(e.Curve.TypeId == "Part::GeomLine" for e in polyline.Edges))
        self.assertAlmostEqual(polyline.Length, mark.Shape.Length, delta=0.05)

        obj.SeparateSketchLayers = False
        self.doc.recompute()
        labels = [self.doc.getObject(n).Label for n in obj.UnfoldSketches]
        self.assertFalse([n for n in labels if "Marks" in n])
        merged = self.doc.getObject(obj.UnfoldSketches[0]).Shape
        self.assertAlmostEqual(merged.common(polyline).Length, polyline.Length, places=5)


if __name__ == "__main__":
    unittest.main()
