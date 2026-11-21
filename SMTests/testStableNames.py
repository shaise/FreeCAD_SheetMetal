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

"""Name stability of the features that tag their tool shapes.

The criterion of SMTests/testBendToponaming.py applied to Hem, Base shape,
Relief, From solid and Unfold (docs/simple-resolver.md section 5.4): all
elements named, names equal after recompute, after save and reopen, and
the same set of names after an upstream dimension change.
"""

import os
import tempfile
import unittest

import FreeCAD
import Part
import Sketcher
from FreeCAD import Vector

from SMTests.helpers import THK, TOL, addFeature, findElement, findVertex, makeBase, makeWall

HAS_TOPONAMING = hasattr(Part.Shape, "ElementMap")


def makeParametricPlate(doc):
    """The 100 x 50 x THK plate from a dimensioned sketch, so its size can
    change without renaming the sketch geometry. Returns (sketch, base,
    index of the width constraint)."""
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    points = [Vector(0, 0, 0), Vector(100, 0, 0), Vector(100, 50, 0), Vector(0, 50, 0)]
    for a, b in zip(points, points[1:] + points[:1]):
        sketch.addGeometry(Part.LineSegment(a, b))
    for i in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sketch.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sketch.addConstraint(Sketcher.Constraint("Vertical", 1))
    sketch.addConstraint(Sketcher.Constraint("Vertical", 3))
    sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 0))
    width = sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 50))
    sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 100))
    base = makeBase(doc, sketch)
    doc.recompute()
    return sketch, base, width


def plateEdge(shape, predicate):
    """The straight top edge (z = THK) of the plate whose bound box matches."""
    return findElement(shape, "Edge", lambda e: e.Curve.TypeId == "Part::GeomLine"
                       and abs(e.BoundBox.ZMin - THK) < TOL and abs(e.BoundBox.ZMax - THK) < TOL
                       and predicate(e.BoundBox))


class StableNames:
    """Mixin: build() creates the feature under test (self.feature) and
    whatever is upstream of it; change() changes an upstream dimension."""

    def build(self):
        raise NotImplementedError

    def change(self):
        raise NotImplementedError

    def setUp(self):
        self.doc = FreeCAD.newDocument(type(self).__name__)
        self.build()
        self.doc.recompute()
        # Names inherited from upstream settle once after creation (a
        # duplicate-name postfix is dropped).
        self.recompute()

    def tearDown(self):
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)

    def names(self):
        """Indexed name -> mapped name of the feature's shape."""
        return {v: k for k, v in self.feature.Shape.ElementMap.items()}

    def assertValid(self):
        self.assertNotIn("Invalid", self.feature.State, self.feature.Name)
        self.assertTrue(self.feature.isValid(), self.feature.getStatusString())

    def recompute(self):
        self.feature.touch()
        self.doc.recompute()
        self.assertValid()

    def testAllElementsNamed(self):
        shape = self.feature.Shape
        total = len(shape.Faces) + len(shape.Edges) + len(shape.Vertexes)
        self.assertGreater(total, 0)
        unnamed = [n for n in (f"{kind}{i + 1}" for kind, elements in
                               (("Face", shape.Faces), ("Edge", shape.Edges),
                                ("Vertex", shape.Vertexes)) for i in range(len(elements)))
                   if n not in self.names()]
        self.assertEqual(unnamed, [])

    def testNamesStableOnRecompute(self):
        before = self.names()
        self.recompute()
        self.assertEqual(before, self.names())

    def testNamesSurviveSaveAndReopen(self):
        before = self.names()
        name = self.feature.Name
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "StableNames.FCStd")
            self.doc.saveAs(path)
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None
            self.doc = FreeCAD.openDocument(path)
            self.feature = self.doc.getObject(name)
            self.assertEqual(before, self.names(), "loaded")
            self.recompute()
            self.assertEqual(before, self.names(), "recomputed")

    def testNamesSurviveUpstreamChange(self):
        # Indices may change with the dimension; the set of names must not.
        before = set(self.names().values())
        self.change()
        self.doc.recompute()
        self.assertValid()
        self.assertEqual(before, set(self.names().values()))


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestHemStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalHem

        self.sketch, base, self.width = makeParametricPlate(self.doc)
        edge = plateEdge(base.Shape, lambda b: abs(b.XMin - 100) < TOL and abs(b.XMax - 100) < TOL)
        self.feature = addFeature(self.doc, "Hem", SheetMetalHem.SMHem, base, [edge])

    def change(self):
        self.sketch.setDatum(self.width, FreeCAD.Units.Quantity("60 mm"))


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestBaseShapeStableNames(StableNames, unittest.TestCase):
    # Base shape has nothing upstream; its own dimension is the change.
    shapeType = "Hat"

    def build(self):
        import SheetMetalBaseShapeCmd

        self.feature = addFeature(self.doc, "BaseShape", SheetMetalBaseShapeCmd.SMBaseShape)
        self.feature.shapeType = self.shapeType

    def change(self):
        self.feature.length = self.feature.length.Value + 10


class TestBaseShapeBoxStableNames(TestBaseShapeStableNames):
    shapeType = "Box"


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestReliefStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalRelief

        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length, self.box.Width, self.box.Height = 40, 30, 20
        self.doc.recompute()
        vertices = [findVertex(self.box.Shape, Vector(40, 30, 20)),
                    findVertex(self.box.Shape, Vector(0, 30, 20))]
        self.feature = addFeature(self.doc, "Relief", SheetMetalRelief.SMRelief, self.box,
                                  vertices)

    def change(self):
        self.box.Length = 50


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestFromSolidStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalFromSolid

        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length, self.box.Width, self.box.Height = 40, 30, 20
        self.doc.recompute()
        top = findElement(self.box.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - 20) < TOL)
        self.feature = addFeature(self.doc, "FromSolid", SheetMetalFromSolid.SMFromSolid,
                                  self.box, [top])

    def change(self):
        self.box.Height = 25


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestUnfoldStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalUnfoldCmd

        self.sketch, base, self.width = makeParametricPlate(self.doc)
        edge = plateEdge(base.Shape, lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL)
        wall = makeWall(self.doc, base, [edge], "Wall")
        self.doc.recompute()
        top = findElement(wall.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - THK) < TOL
                          and abs(f.BoundBox.ZMax - THK) < TOL)
        self.feature = addFeature(self.doc, "Unfold", SheetMetalUnfoldCmd.SMUnfold, wall, [top])
        self.feature.GenerateSketch = False

    def change(self):
        self.sketch.setDatum(self.width, FreeCAD.Units.Quantity("60 mm"))


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestJunctionStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalJunction

        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length = self.box.Width = self.box.Height = 30
        self.doc.recompute()
        edge = findElement(self.box.Shape, "Edge", lambda e: abs(e.BoundBox.XMin - 30) < TOL
                           and abs(e.BoundBox.YMin - 30) < TOL)
        self.feature = addFeature(self.doc, "Junction", SheetMetalJunction.SMJunction,
                                  self.box, [edge])

    def change(self):
        self.box.Height = 40


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestSolidBendStableNames(StableNames, unittest.TestCase):
    def build(self):
        import SheetMetalBend

        # A refined L of two boxes, bent along the inner corner edge.
        self.flange = self.doc.addObject("Part::Box", "Flange")
        self.flange.Length, self.flange.Width, self.flange.Height = 40, 30, 2
        web = self.doc.addObject("Part::Box", "Web")
        web.Length, web.Width, web.Height = 2, 30, 40
        lsolid = self.doc.addObject("Part::MultiFuse", "LSolid")
        lsolid.Shapes = [self.flange, web]
        lsolid.Refine = True
        self.doc.recompute()
        edge = findElement(lsolid.Shape, "Edge", lambda e: e.Curve.TypeId == "Part::GeomLine"
                           and abs(e.BoundBox.XMin - 2) < TOL and abs(e.BoundBox.XMax - 2) < TOL
                           and abs(e.BoundBox.ZMin - 2) < TOL and abs(e.BoundBox.ZMax - 2) < TOL)
        self.feature = addFeature(self.doc, "SolidBend", SheetMetalBend.SMSolidBend, lsolid,
                                  [edge])

    def change(self):
        self.flange.Length = 50
