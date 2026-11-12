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

"""Topological naming (TNP) regression tests.

Each test builds a small feature chain, records the geometry every
sub-element reference points at, changes something upstream and checks
that the references still resolve to the same geometry. See docs/TNP.md.
"""

import unittest

import FreeCAD
import Part
from FreeCAD import Vector

from SMTests.helpers import (
    PLATE,
    THK,
    TOL,
    cornerBendEdges,
    findElement,
    findVertex,
    isLine,
    makeBase,
    makeCornerWall,
    makeSketch,
    makeWall,
)

def edgeSignature(edge):
    """Infinite-line signature of a straight edge: (direction, point)."""
    d = edge.Vertexes[1].Point - edge.Vertexes[0].Point
    d.normalize()
    if d.x < -TOL or (abs(d.x) < TOL and (d.y < -TOL or (abs(d.y) < TOL and d.z < 0))):
        d = -d
    return d, edge.Vertexes[0].Point


def sameLine(edge, signature):
    d0, p0 = signature
    d, _p = edgeSignature(edge)
    if (d - d0).Length > TOL:
        return False
    # distance of every vertex of edge to the reference line
    return all(v.Point.distanceToLine(p0, d0) < TOL for v in edge.Vertexes)


def resolve(obj):
    """Element the first sub-element reference of obj resolves to now."""
    linked, subs = obj.baseObject
    return linked.Shape.getElement(subs[0])


class TestTNPWalls(unittest.TestCase):
    """Wall on a base plate, and a second wall on the first wall."""

    PLATE = PLATE

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestTNP")
        self.sketch = makeSketch(self.doc, self.PLATE)
        self.base = makeBase(self.doc, self.sketch)
        self.doc.recompute()

        # Top edge of the plate along X at y=50.
        edge1 = findElement(
            self.base.Shape,
            "Edge",
            lambda e: isLine(e)
            and abs(e.BoundBox.YMin - 50) < TOL
            and abs(e.BoundBox.YMax - 50) < TOL
            and abs(e.BoundBox.ZMin - THK) < TOL
            and e.BoundBox.XLength > 1,
        )
        self.wall1 = makeWall(self.doc, self.base, [edge1], "Wall1")
        self.doc.recompute()
        self.assertTrue(self.wall1.Shape.isValid())
        self.sig1 = edgeSignature(self.base.Shape.getElement(edge1))

        # The far (top) edge of Wall1 on its outer side, parallel to X.
        shape = self.wall1.Shape
        zmax = shape.BoundBox.ZMax
        ymax = shape.BoundBox.YMax
        edge2 = findElement(
            shape,
            "Edge",
            lambda e: isLine(e)
            and e.BoundBox.XLength > 1
            and abs(e.BoundBox.ZMin - zmax) < TOL
            and abs(e.BoundBox.YMin - ymax) < TOL,
        )
        self.wall2 = makeWall(self.doc, self.wall1, [edge2], "Wall2")
        self.doc.recompute()
        self.assertTrue(self.wall2.Shape.isValid())
        self.sig2 = edgeSignature(shape.getElement(edge2))

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def recompute(self):
        self.doc.recompute()
        for obj in (self.base, self.wall1, self.wall2):
            self.assertFalse("Invalid" in obj.State, f"{obj.Name} failed to recompute")
            self.assertTrue(obj.Shape.isValid(), f"{obj.Name} shape invalid")

    def assertRefs(self):
        self.assertTrue(sameLine(resolve(self.wall1), self.sig1), "Wall1 moved to another edge")
        self.assertTrue(sameLine(resolve(self.wall2), self.sig2), "Wall2 moved to another edge")

    def testRecomputeIsStable(self):
        self.doc.recompute()
        self.assertRefs()

    def testLongerBase(self):
        # Move the right side of the plate: the referenced edge only gets longer.
        self.sketch.moveGeometry(0, 2, Vector(120, 0, 0))
        self.sketch.moveGeometry(1, 1, Vector(120, 0, 0))
        self.sketch.moveGeometry(1, 2, Vector(120, 50, 0))
        self.sketch.moveGeometry(2, 1, Vector(120, 50, 0))
        self.recompute()
        self.assertRefs()

    def testChamferedBase(self):
        # Chamfer the corner far from the referenced edge. This adds an edge
        # and a face to the plate, so element indices shift.
        self.sketch.moveGeometry(0, 1, Vector(10, 0, 0))
        self.sketch.moveGeometry(3, 2, Vector(0, 10, 0))
        self.sketch.addGeometry(Part.LineSegment(Vector(0, 10, 0), Vector(10, 0, 0)))
        self.recompute()
        self.assertRefs()

    def testChamferNearReference(self):
        # Chamfer a corner touching the referenced edge: it gets shorter.
        self.sketch.moveGeometry(2, 2, Vector(10, 50, 0))
        self.sketch.moveGeometry(3, 1, Vector(0, 40, 0))
        self.sketch.addGeometry(Part.LineSegment(Vector(10, 50, 0), Vector(0, 40, 0)))
        self.recompute()
        self.assertRefs()

    def testWall1Length(self):
        self.wall1.length = 35.0
        self.recompute()
        # Wall2 sits on Wall1's far edge, which moved up by 15.
        d, p = self.sig2
        self.sig2 = (d, p + Vector(0, 0, 15))
        self.assertRefs()

    def testWall1Gaps(self):
        # Gaps add relief cuts to Wall1, which changes its topology.
        self.wall1.gap1 = 5.0
        self.wall1.gap2 = 5.0
        self.recompute()
        self.assertRefs()

    def testWall1ReliefType(self):
        self.wall1.gap1 = 5.0
        self.recompute()
        self.wall1.reliefType = "Round"
        self.recompute()
        self.assertRefs()

    def testWall1Unfold(self):
        self.wall1.unfold = True
        self.recompute()
        self.wall1.unfold = False
        self.recompute()
        self.assertRefs()


def unnamedElements(shape):
    """Index names of all faces, edges and vertices without a mapped name."""
    named = set(shape.ElementMap.values())
    unnamed = []
    for kind, elements in (("Face", shape.Faces), ("Edge", shape.Edges),
                           ("Vertex", shape.Vertexes)):
        unnamed += [f"{kind}{i + 1}" for i in range(len(elements))
                    if f"{kind}{i + 1}" not in named]
    return unnamed


class TestTNPCoverage(unittest.TestCase):
    """Every element of a feature's output must have a mapped name,
    otherwise references to it are plain indices (see docs/TNP.md)."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestTNPCoverage")
        self.sketch = makeSketch(self.doc, TestTNPWalls.PLATE)
        self.base = makeBase(self.doc, self.sketch)
        self.doc.recompute()

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def plateEdge(self, predicate):
        return findElement(self.base.Shape, "Edge", lambda e: isLine(e) and predicate(e.BoundBox))

    def plateFace(self, predicate):
        return findElement(self.base.Shape, "Face", lambda f: predicate(f.BoundBox))

    def assertFullyNamed(self, obj):
        self.doc.recompute()
        self.assertFalse("Invalid" in obj.State, f"{obj.Name} failed to recompute")
        self.assertEqual(unnamedElements(obj.Shape), [])

    def addFeature(self, name, cls, *args):
        obj = self.doc.addObject("Part::FeaturePython", name)
        cls(obj, *args)
        return obj

    def testBase(self):
        self.assertFullyNamed(self.base)

    def testWall(self):
        edge = self.plateEdge(lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL
                              and abs(b.ZMin - THK) < TOL)
        wall = makeWall(self.doc, self.base, [edge])
        self.assertFullyNamed(wall)
        wall.gap1 = 5.0
        wall.unfold = True
        self.assertFullyNamed(wall)

    def testHem(self):
        import SheetMetalHem

        edge = self.plateEdge(lambda b: abs(b.XMin - 100) < TOL and abs(b.XMax - 100) < TOL
                              and abs(b.ZMin - THK) < TOL)
        self.assertFullyNamed(self.addFeature("Hem", SheetMetalHem.SMHem, self.base, [edge]))

    def testExtend(self):
        import SheetMetalExtendCmd

        face = self.plateFace(lambda b: abs(b.XMin - 100) < TOL and abs(b.XMax - 100) < TOL)
        extend = self.addFeature("Extend", SheetMetalExtendCmd.SMExtrudeWall, self.base, [face])
        self.assertFullyNamed(extend)

    def testFold(self):
        import SheetMetalFoldCmd

        line = self.doc.addObject("Sketcher::SketchObject", "FoldLine")
        line.Placement.Base = Vector(0, 0, THK)
        line.addGeometry(Part.LineSegment(Vector(50, -10, 0), Vector(50, 60, 0)))
        self.doc.recompute()
        face = self.plateFace(lambda b: abs(b.ZMin - THK) < TOL and abs(b.ZMax - THK) < TOL)
        fold = self.addFeature("Fold", SheetMetalFoldCmd.SMFoldWall, self.base, [face], line)
        self.assertFullyNamed(fold)

    def testExtrudedCutout(self):
        import ExtrudedCutout

        circle = self.doc.addObject("Sketcher::SketchObject", "CutSketch")
        circle.Placement.Base = Vector(0, 0, THK)
        circle.addGeometry(Part.Circle(Vector(30, 25, 0), Vector(0, 0, 1), 5))
        self.doc.recompute()
        face = self.plateFace(lambda b: abs(b.ZMin - THK) < TOL and abs(b.ZMax - THK) < TOL)
        cutout = self.addFeature("Cutout", ExtrudedCutout.ExtrudedCutout, circle,
                                 (self.base, [face]))
        self.assertFullyNamed(cutout)

    def testBaseShape(self):
        import SheetMetalBaseShapeCmd

        self.assertFullyNamed(self.addFeature("BaseShape", SheetMetalBaseShapeCmd.SMBaseShape))

    def testJunction(self):
        import SheetMetalJunction

        box = self.doc.addObject("Part::Box", "Box")
        box.Length = box.Width = box.Height = 30
        self.doc.recompute()
        edge = findElement(box.Shape, "Edge", lambda e: abs(e.BoundBox.XMin - 30) < TOL
                           and abs(e.BoundBox.YMin - 30) < TOL)
        self.assertFullyNamed(self.addFeature("Junction", SheetMetalJunction.SMJunction,
                                              box, [edge]))

    def testSolidBend(self):
        import SheetMetalBend

        lsolid = self.doc.addObject("Part::Feature", "LSolid")
        lsolid.Shape = Part.makeBox(40, 30, 2).fuse(Part.makeBox(2, 30, 40)).removeSplitter()
        self.doc.recompute()
        edge = findElement(lsolid.Shape, "Edge", lambda e: isLine(e)
                           and abs(e.BoundBox.XMin - 2) < TOL and abs(e.BoundBox.XMax - 2) < TOL
                           and abs(e.BoundBox.ZMin - 2) < TOL and abs(e.BoundBox.ZMax - 2) < TOL)
        self.assertFullyNamed(self.addFeature("SolidBend", SheetMetalBend.SMSolidBend,
                                              lsolid, [edge]))

    def testRelief(self):
        import SheetMetalRelief

        box = self.doc.addObject("Part::Box", "Box")
        self.doc.recompute()
        vertex = findVertex(box.Shape, Vector(10, 10, 10))
        self.assertFullyNamed(self.addFeature("Relief", SheetMetalRelief.SMRelief, box, [vertex]))

    def testCornerRelief(self):
        import SheetMetalCornerReliefCmd

        wall = makeCornerWall(self.doc, self.base)
        relief = self.addFeature("CornerRelief", SheetMetalCornerReliefCmd.SMCornerRelief,
                                 wall, cornerBendEdges(wall.Shape))
        relief.ReliefSketch = "Square"
        self.assertFullyNamed(relief)

    def testWrapCutout(self):
        import SketchOnSheetMetalCmd

        edge = self.plateEdge(lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL
                              and abs(b.ZMin - THK) < TOL)
        wall = makeWall(self.doc, self.base, [edge])
        self.doc.recompute()
        face = findElement(wall.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - THK) < TOL
                           and abs(f.BoundBox.ZMax - THK) < TOL)
        circle = self.doc.addObject("Sketcher::SketchObject", "CutSketch")
        circle.Placement.Base = Vector(0, 0, THK)
        circle.addGeometry(Part.Circle(Vector(50, 52, 0), Vector(0, 0, 1), 4))
        self.doc.recompute()
        self.assertFullyNamed(self.addFeature("Wrap", SketchOnSheetMetalCmd.SMSketchOnSheet,
                                              wall, [face], circle))

    def testForming(self):
        import SheetMetalFormingCmd

        tool = self.doc.addObject("Part::Cylinder", "Tool")
        tool.Radius = 5
        tool.Height = 3
        tool.Placement.Base = Vector(30, 25, THK)
        self.doc.recompute()
        toolFace = findElement(tool.Shape, "Face", lambda f: abs(f.BoundBox.ZMax - THK) < TOL)
        face = self.plateFace(lambda b: abs(b.ZMin - THK) < TOL and abs(b.ZMax - THK) < TOL)
        self.assertFullyNamed(self.addFeature("Forming", SheetMetalFormingCmd.SMBendWall,
                                              self.base, [face], tool, [toolFace]))

    def testFromSolid(self):
        import SheetMetalFromSolid

        box = self.doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 40, 30, 20
        self.doc.recompute()
        top = findElement(box.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - 20) < TOL)
        self.assertFullyNamed(self.addFeature("FromSolid", SheetMetalFromSolid.SMFromSolid,
                                              box, [top]))

    def testUnfold(self):
        import SheetMetalUnfoldCmd

        edge = self.plateEdge(lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL
                              and abs(b.ZMin - THK) < TOL)
        wall = makeWall(self.doc, self.base, [edge])
        self.doc.recompute()
        face = findElement(wall.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - THK) < TOL
                           and abs(f.BoundBox.ZMax - THK) < TOL)
        self.assertFullyNamed(self.addFeature("Unfold", SheetMetalUnfoldCmd.SMUnfold,
                                              wall, [face]))


class TestTNPReferences(unittest.TestCase):
    """A reference to an element a feature creates must follow that element
    when something upstream changes."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestTNPReferences")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def assertReferenceFollows(self, obj, predicate, change):
        """Reference the single face of obj matching predicate, apply change
        and check the reference still resolves to a face matching it."""
        self.doc.recompute()
        faces = [f"Face{i + 1}" for i, f in enumerate(obj.Shape.Faces) if predicate(f, obj.Shape)]
        self.assertEqual(len(faces), 1, f"predicate matches {faces}")
        ref = self.doc.addObject("App::FeaturePython", "Ref")
        ref.addProperty("App::PropertyLinkSub", "Link")
        ref.Link = (obj, faces)
        self.doc.recompute()
        change()
        self.doc.recompute()
        self.assertFalse("Invalid" in obj.State, f"{obj.Name} failed to recompute")
        sub = ref.Link[1][0]
        self.assertFalse(sub.startswith("?"), f"lost reference {sub}")
        self.assertTrue(predicate(obj.Shape.getElement(sub), obj.Shape),
                        f"{faces[0]} -> {sub} is another face")

    def testReliefSize(self):
        import SheetMetalRelief

        box = self.doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 40, 30, 20
        self.doc.recompute()
        relief = self.doc.addObject("Part::FeaturePython", "Relief")
        SheetMetalRelief.SMRelief(relief, box, [findVertex(box.Shape, Vector(0, 0, 20)),
                                                findVertex(box.Shape, Vector(40, 30, 20))])
        self.doc.recompute()
        # A pocket face of the relief at (40, 30, 20).
        pocket = findElement(relief.Shape, "Face", lambda f: f.BoundBox.XMin > 37.5
                             and f.BoundBox.YMin > 27.5 and abs(f.BoundBox.XLength) < TOL)
        normal = relief.Shape.getElement(pocket).normalAt(0, 0)

        def predicate(f, _shape):
            return ((f.normalAt(0, 0) - normal).Length < TOL and f.BoundBox.XMin > 36
                    and f.BoundBox.YMin > 26 and abs(f.BoundBox.XLength) < TOL)

        def change():
            relief.relief = 3.0

        self.assertReferenceFollows(relief, predicate, change)

    def testFromSolidLength(self):
        import SheetMetalFromSolid

        box = self.doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 40, 30, 20
        self.doc.recompute()
        top = findElement(box.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - 20) < TOL)
        sheet = self.doc.addObject("Part::FeaturePython", "FromSolid")
        SheetMetalFromSolid.SMFromSolid(sheet, box, [top])

        def predicate(f, _shape):
            # Outer bend face along X at the bottom of the y=30 side.
            return (f.Surface.TypeId == "Part::GeomCylinder" and f.BoundBox.YMin > 25
                    and f.BoundBox.ZMax < 5 and f.BoundBox.XLength > 20
                    and f.Surface.Radius > 1.5)

        def change():
            box.Length = 60

        self.assertReferenceFollows(sheet, predicate, change)

    def makeUnfold(self):
        import SheetMetalUnfoldCmd

        self.sketch = makeSketch(self.doc, TestTNPWalls.PLATE)
        base = makeBase(self.doc, self.sketch)
        self.doc.recompute()
        edge = findElement(base.Shape, "Edge", lambda e: isLine(e)
                           and abs(e.BoundBox.YMin - 50) < TOL and abs(e.BoundBox.YMax - 50) < TOL
                           and abs(e.BoundBox.ZMin - THK) < TOL)
        self.wall = makeWall(self.doc, base, [edge])
        self.doc.recompute()
        face = findElement(self.wall.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - THK) < TOL
                           and abs(f.BoundBox.ZMax - THK) < TOL)
        unfold = self.doc.addObject("Part::FeaturePython", "Unfold")
        SheetMetalUnfoldCmd.SMUnfold(unfold, self.wall, [face])
        return unfold

    @staticmethod
    def flatSide(side):
        """Predicate for the outer side face of the flat pattern at y min
        or y max."""
        def predicate(f, shape):
            y = shape.BoundBox.YMin if side < 0 else shape.BoundBox.YMax
            return (f.Surface.TypeId == "Part::GeomPlane"
                    and abs(f.BoundBox.YMin - y) < TOL and abs(f.BoundBox.YMax - y) < TOL)
        return predicate

    def testUnfoldChamferedBase(self):
        unfold = self.makeUnfold()

        def change():
            self.sketch.moveGeometry(0, 1, Vector(10, 0, 0))
            self.sketch.moveGeometry(3, 2, Vector(0, 10, 0))
            self.sketch.addGeometry(Part.LineSegment(Vector(0, 10, 0), Vector(10, 0, 0)))

        self.assertReferenceFollows(unfold, self.flatSide(-1), change)

    def testUnfoldWallLength(self):
        unfold = self.makeUnfold()

        def change():
            self.wall.length = 35.0

        self.assertReferenceFollows(unfold, self.flatSide(1), change)
