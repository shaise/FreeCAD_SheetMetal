"""Run with FreeCAD's Test framework, or unittest in the FreeCAD console."""
import unittest

import FreeCAD
import Part
import Sketcher

HAS_TOPONAMING = hasattr(Part.Shape, "ElementMap")


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestBendToponaming(unittest.TestCase):
    """Bend (SMBendWall) must give every element a reproducible name, so that
    downstream references (sketches, assembly joints, ...) survive recomputes
    and parameter changes."""

    def setUp(self):
        from SheetMetalBaseCmd import SMBaseBend
        from SheetMetalCmd import SMBendWall

        self.doc = FreeCAD.newDocument("BendToponaming")
        body = self.doc.addObject("PartDesign::Body", "Body")

        # Parametric 100 x 60 rectangle -> closed-sketch base plate.
        self.sketch = sk = body.newObject("Sketcher::SketchObject", "Sketch")
        pts = [FreeCAD.Vector(x, y, 0) for x, y in ((-50, -30), (50, -30), (50, 30), (-50, 30))]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            sk.addGeometry(Part.LineSegment(a, b))
        for i in range(4):
            sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
        sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
        sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
        sk.addConstraint(Sketcher.Constraint("Vertical", 1))
        sk.addConstraint(Sketcher.Constraint("Vertical", 3))
        sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, -50))
        sk.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, -30))
        self.widthConstraint = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 100))
        sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 60))
        self.doc.recompute()

        base = body.newObject("PartDesign::FeaturePython", "BaseBend")
        SMBaseBend(base, sk)
        base.Thickness = 1.5
        self.doc.recompute()

        # Two chained bends with gaps, so relief cuts are produced too.
        self.bend1 = body.newObject("PartDesign::FeaturePython", "Bend1")
        SMBendWall(self.bend1, base, [self._topEdgeAtX(base, 50)])
        self.bend1.gap1 = self.bend1.gap2 = 3
        self.bend1.reliefw = 1.5
        self.bend1.reliefd = 2
        self.doc.recompute()
        self.bend2 = body.newObject("PartDesign::FeaturePython", "Bend2")
        SMBendWall(self.bend2, self.bend1, [self._topEdgeAtX(self.bend1, -50)])
        self.bend2.gap1 = self.bend2.gap2 = 3
        self.doc.recompute()
        # Names inherited from the base feature settle once after creation
        # (a duplicate-name postfix is dropped); this happens without this
        # fix too and is out of scope here.
        self._recompute()

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def _topEdgeAtX(self, obj, x):
        for i, e in enumerate(obj.Shape.Edges):
            bb = e.BoundBox
            if abs(bb.XMin - x) < 1e-6 and abs(bb.XMax - x) < 1e-6 and abs(bb.ZMin - 1.5) < 1e-6:
                return "Edge" + str(i + 1)
        self.fail("top edge not found")

    @staticmethod
    def _names(obj):
        """Indexed name -> mapped name."""
        return {v: k for k, v in obj.Shape.ElementMap.items()}

    def _recompute(self):
        for obj in (self.bend1, self.bend2):
            obj.touch()
        self.doc.recompute()
        for obj in (self.bend1, self.bend2):
            self.assertTrue(obj.isValid(), obj.getStatusString())

    def test_all_elements_named(self):
        for obj in (self.bend1, self.bend2):
            shape = obj.Shape
            total = len(shape.Faces) + len(shape.Edges) + len(shape.Vertexes)
            self.assertEqual(len(self._names(obj)), total, obj.Name)

    def test_names_stable_on_recompute(self):
        before = {obj.Name: self._names(obj) for obj in (self.bend1, self.bend2)}
        self._recompute()
        for obj in (self.bend1, self.bend2):
            self.assertEqual(before[obj.Name], self._names(obj), obj.Name)

    def test_names_survive_sketch_change(self):
        before = {obj.Name: set(self._names(obj).values()) for obj in (self.bend1, self.bend2)}
        self.sketch.setDatum(self.widthConstraint, FreeCAD.Units.Quantity("120 mm"))
        self.doc.recompute()
        for obj in (self.bend1, self.bend2):
            self.assertTrue(obj.isValid(), obj.getStatusString())
            self.assertEqual(before[obj.Name], set(self._names(obj).values()), obj.Name)
