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

"""Builders and lookups shared by the SheetMetal tests."""

import FreeCAD
import Part
from FreeCAD import Vector

import SheetMetalBaseCmd
import SheetMetalCmd

TOL = 1e-4
THK = 2.0
# Outline of the 100 x 50 base plate used by most tests.
PLATE = [(0, 0, 0), (100, 0, 0), (100, 50, 0), (0, 50, 0)]


def makeSketch(doc, points, name="Sketch"):
    sketch = doc.getObject(name) or doc.addObject("Sketcher::SketchObject", name)
    setSketchPolygon(sketch, points)
    return sketch


def setSketchPolygon(sketch, points):
    sketch.deleteAllGeometry()
    for p1, p2 in zip(points, points[1:] + points[:1]):
        sketch.addGeometry(Part.LineSegment(Vector(*p1), Vector(*p2)))


def makeBase(doc, sketch):
    obj = doc.addObject("Part::FeaturePython", "BaseBend")
    SheetMetalBaseCmd.SMBaseBend(obj, sketch)
    obj.Thickness = THK
    obj.Radius = 1.0
    obj.BendSide = "Outside"
    obj.MidPlane = False
    obj.Reverse = False
    return obj


def makeWall(doc, base, subNames, name="Bend"):
    obj = doc.addObject("Part::FeaturePython", name)
    SheetMetalCmd.SMBendWall(obj, base, subNames)
    obj.radius = 1.0
    obj.length = 20.0
    obj.angle = 90.0
    obj.gap1 = 0.0
    obj.gap2 = 0.0
    obj.invert = False
    obj.BendType = "Material Outside"
    obj.LengthSpec = "Leg"
    return obj


def findElement(shape, kind, predicate):
    """Return the name of the single element of the given kind that
    satisfies the predicate."""
    elements = shape.Edges if kind == "Edge" else shape.Faces
    names = [f"{kind}{i + 1}" for i, e in enumerate(elements) if predicate(e)]
    if len(names) != 1:
        raise AssertionError(f"expected one matching {kind}, found {names}")
    return names[0]


def isLine(edge):
    return edge.Curve.TypeId == "Part::GeomLine"


def findVertex(shape, point):
    names = [f"Vertex{i + 1}" for i, v in enumerate(shape.Vertexes)
             if (v.Point - point).Length < TOL]
    if len(names) != 1:
        raise AssertionError(f"expected one vertex at {point}, found {names}")
    return names[0]


def makeCornerWall(doc, base):
    """One wall on the y=50 and x=100 top edges of the plate, with gaps so
    the two bends leave room for a corner relief."""
    edges = [findElement(base.Shape, "Edge", lambda e, p=p: isLine(e) and p(e.BoundBox)
                         and abs(e.BoundBox.ZMin - THK) < TOL)
             for p in (lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL,
                       lambda b: abs(b.XMin - 100) < TOL and abs(b.XMax - 100) < TOL)]
    wall = makeWall(doc, base, edges, "CornerWall")
    wall.gap1 = wall.gap2 = 1.0
    doc.recompute()
    return wall


def cornerBendEdges(shape):
    """The two edges where the bends start on the plate's top face."""
    names = []
    for i, e in enumerate(shape.Edges):
        surfaces = {type(f.Surface).__name__ for f in shape.ancestorsOfType(e, Part.Face)}
        if (isLine(e) and surfaces == {"Plane", "Cylinder"}
                and abs(e.BoundBox.ZMin - THK) < TOL and abs(e.BoundBox.ZMax - THK) < TOL):
            names.append(f"Edge{i + 1}")
    if len(names) != 2:
        raise AssertionError(f"expected two bend edges, found {names}")
    return names


def makePlate(doc):
    """The 100 x 50 x THK base plate from a sketch; returns (sketch, base)."""
    sketch = makeSketch(doc, PLATE)
    base = makeBase(doc, sketch)
    doc.recompute()
    return sketch, base


def topEdge(shape, predicate):
    """The straight edge on the top face (z = THK) whose bound box matches."""
    return findElement(shape, "Edge", lambda e: isLine(e) and abs(e.BoundBox.ZMin - THK) < TOL
                       and abs(e.BoundBox.ZMax - THK) < TOL and predicate(e.BoundBox))


def backEdge(shape):
    """Top edge of the plate along X at y = 50."""
    return topEdge(shape, lambda b: abs(b.YMin - 50) < TOL and abs(b.YMax - 50) < TOL)


def rightEdge(shape):
    """Top edge of the plate along Y at x = 100."""
    return topEdge(shape, lambda b: abs(b.XMin - 100) < TOL and abs(b.XMax - 100) < TOL)


def topFace(shape):
    """The planar face at z = THK."""
    return findElement(shape, "Face", lambda f: abs(f.BoundBox.ZMin - THK) < TOL
                       and abs(f.BoundBox.ZMax - THK) < TOL)


def addFeature(doc, name, cls, *args):
    """Create a Part::FeaturePython with the given proxy class."""
    obj = doc.addObject("Part::FeaturePython", name)
    cls(obj, *args)
    return obj


def assertRecomputed(test, doc, *objs):
    """Recompute and check that every obj recomputed into one valid solid."""
    doc.recompute()
    for obj in objs:
        test.assertFalse("Invalid" in obj.State, f"{obj.Name} failed to recompute")
        test.assertTrue(obj.Shape.isValid(), f"{obj.Name} shape is invalid")
        test.assertEqual(len(obj.Shape.Solids), 1, f"{obj.Name} is not one solid")
