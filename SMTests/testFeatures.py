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


"""Geometry regression tests for every feature and its main options.

Each case builds a feature, checks that it recomputes into one valid
solid and compares volume, area, element counts and bound box with the
reference values in data/featureGeometry.json. The reference values were
recorded from the code, not derived by hand, so a difference means the
geometry changed, not necessarily that it is wrong; where the value is easy
to derive, the case also checks it directly.

After an intended geometry change, regenerate the reference values with

    flatpak run --env=SM_UPDATE_GOLDEN=1 --command=FreeCADCmd \\
        org.freecad.FreeCAD -t SMTests.testFeatures

and review the diff of data/featureGeometry.json.
"""

import json
import math
import os
import unittest

import FreeCAD
import Part
from FreeCAD import Vector

import ExtrudedCutout
import SheetMetalBaseShapeCmd
import SheetMetalBend
import SheetMetalCornerReliefCmd
import SheetMetalExtendCmd
import SheetMetalFoldCmd
import SheetMetalFormingCmd
import SheetMetalFromSolid
import SheetMetalHem
import SheetMetalJunction
import SheetMetalRelief
import SheetMetalUnfoldCmd
import SketchOnSheetMetalCmd
from SMTests.helpers import (
    THK,
    TOL,
    addFeature,
    assertRecomputed,
    backEdge,
    cornerBendEdges,
    findElement,
    findVertex,
    isLine,
    makeCornerWall,
    makePlate,
    makeWall,
    rightEdge,
    topEdge,
    topFace,
)

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "data", "featureGeometry.json")
UPDATE_GOLDEN = bool(os.environ.get("SM_UPDATE_GOLDEN"))
REL_TOL = 1e-6
PLATE_VOLUME = 100 * 50 * THK


def measure(shape):
    bb = shape.BoundBox
    return {
        "volume": shape.Volume,
        "area": shape.Area,
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
        "boundBox": [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax],
    }


def loadGolden():
    try:
        with open(GOLDEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


# ---------------------------------------------------------------------------
# Case builders. Each takes (doc, base) and returns the feature to check;
# base is the 100 x 50 x THK plate.
# ---------------------------------------------------------------------------

def wall(**props):
    def build(doc, base):
        obj = makeWall(doc, base, [backEdge(base.Shape)], "Wall")
        for prop, value in props.items():
            setattr(obj, prop, value)
        return obj
    return build


def cornerWall(doc, base):
    return makeCornerWall(doc, base)


def chainedWall(doc, base):
    first = makeWall(doc, base, [backEdge(base.Shape)], "Wall1")
    doc.recompute()
    shape = first.Shape
    edge = findElement(shape, "Edge", lambda e: isLine(e) and e.BoundBox.XLength > 1
                       and abs(e.BoundBox.ZMin - shape.BoundBox.ZMax) < TOL
                       and abs(e.BoundBox.YMin - shape.BoundBox.YMax) < TOL)
    return makeWall(doc, first, [edge], "Wall2")


def hem(**props):
    def build(doc, base):
        obj = addFeature(doc, "Hem", SheetMetalHem.SMHem, base, [rightEdge(base.Shape)])
        for prop, value in props.items():
            setattr(obj, prop, value)
        return obj
    return build


def extend(**props):
    def build(doc, base):
        face = findElement(base.Shape, "Face", lambda f: abs(f.BoundBox.XMin - 100) < TOL
                           and abs(f.BoundBox.XMax - 100) < TOL)
        obj = addFeature(doc, "Extend", SheetMetalExtendCmd.SMExtrudeWall, base, [face])
        for prop, value in props.items():
            setattr(obj, prop, value)
        return obj
    return build


def fold(**props):
    def build(doc, base):
        line = doc.addObject("Sketcher::SketchObject", "FoldLine")
        line.Placement.Base = Vector(0, 0, THK)
        line.addGeometry(Part.LineSegment(Vector(50, -10, 0), Vector(50, 60, 0)))
        doc.recompute()
        obj = addFeature(doc, "Fold", SheetMetalFoldCmd.SMFoldWall, base,
                         [topFace(base.Shape)], line)
        for prop, value in props.items():
            setattr(obj, prop, value)
        return obj
    return build


def baseShape(shapeType):
    def build(doc, _base):
        obj = addFeature(doc, "BaseShape", SheetMetalBaseShapeCmd.SMBaseShape)
        obj.shapeType = shapeType
        return obj
    return build


def cutout(doc, base):
    circle = doc.addObject("Sketcher::SketchObject", "CutSketch")
    circle.Placement.Base = Vector(0, 0, THK)
    circle.addGeometry(Part.Circle(Vector(30, 25, 0), Vector(0, 0, 1), 5))
    doc.recompute()
    return addFeature(doc, "Cutout", ExtrudedCutout.ExtrudedCutout, circle,
                      (base, [topFace(base.Shape)]))


def relief(doc, _base):
    box = doc.addObject("Part::Box", "Box")
    box.Length, box.Width, box.Height = 40, 30, 20
    doc.recompute()
    return addFeature(doc, "Relief", SheetMetalRelief.SMRelief, box,
                      [findVertex(box.Shape, Vector(40, 30, 20))])


def cornerRelief(reliefType):
    def build(doc, base):
        corner = makeCornerWall(doc, base)
        obj = addFeature(doc, "CornerRelief", SheetMetalCornerReliefCmd.SMCornerRelief, corner,
                         cornerBendEdges(corner.Shape))
        obj.ReliefSketch = reliefType
        return obj
    return build


def wrapCutout(doc, base):
    obj = makeWall(doc, base, [backEdge(base.Shape)])
    doc.recompute()
    circle = doc.addObject("Sketcher::SketchObject", "CutSketch")
    circle.Placement.Base = Vector(0, 0, THK)
    circle.addGeometry(Part.Circle(Vector(50, 52, 0), Vector(0, 0, 1), 4))
    doc.recompute()
    return addFeature(doc, "Wrap", SketchOnSheetMetalCmd.SMSketchOnSheet, obj,
                      [topFace(obj.Shape)], circle)


def forming(doc, base):
    tool = doc.addObject("Part::Cylinder", "Tool")
    tool.Radius, tool.Height = 5, 3
    tool.Placement.Base = Vector(30, 25, THK)
    doc.recompute()
    toolFace = findElement(tool.Shape, "Face", lambda f: abs(f.BoundBox.ZMax - THK) < TOL)
    return addFeature(doc, "Forming", SheetMetalFormingCmd.SMBendWall, base,
                      [topFace(base.Shape)], tool, [toolFace])


def junction(doc, _base):
    box = doc.addObject("Part::Box", "Box")
    box.Length = box.Width = box.Height = 30
    doc.recompute()
    edge = findElement(box.Shape, "Edge", lambda e: abs(e.BoundBox.XMin - 30) < TOL
                       and abs(e.BoundBox.YMin - 30) < TOL)
    return addFeature(doc, "Junction", SheetMetalJunction.SMJunction, box, [edge])


def solidBend(doc, _base):
    lsolid = doc.addObject("Part::Feature", "LSolid")
    lsolid.Shape = Part.makeBox(40, 30, 2).fuse(Part.makeBox(2, 30, 40)).removeSplitter()
    doc.recompute()
    edge = findElement(lsolid.Shape, "Edge", lambda e: isLine(e)
                       and abs(e.BoundBox.XMin - 2) < TOL and abs(e.BoundBox.XMax - 2) < TOL
                       and abs(e.BoundBox.ZMin - 2) < TOL and abs(e.BoundBox.ZMax - 2) < TOL)
    return addFeature(doc, "SolidBend", SheetMetalBend.SMSolidBend, lsolid, [edge])


def fromSolid(doc, _base):
    box = doc.addObject("Part::Box", "Box")
    box.Length, box.Width, box.Height = 40, 30, 20
    doc.recompute()
    top = findElement(box.Shape, "Face", lambda f: abs(f.BoundBox.ZMin - 20) < TOL)
    return addFeature(doc, "FromSolid", SheetMetalFromSolid.SMFromSolid, box, [top])


def unfold(doc, base):
    obj = makeWall(doc, base, [backEdge(base.Shape)])
    doc.recompute()
    flat = addFeature(doc, "Unfold", SheetMetalUnfoldCmd.SMUnfold, obj, [topFace(obj.Shape)])
    flat.GenerateSketch = False
    return flat


def base(_doc, plate):
    return plate


CASES = {
    "Base": base,
    "Wall": wall(),
    **{f"Wall_BendType_{t.replace(' ', '')}": wall(BendType=t)
       for t in ("Material Inside", "Thickness Outside")},
    **{f"Wall_LengthSpec_{s.replace(' ', '')}": wall(LengthSpec=s)
       for s in ("Outer Sharp", "Inner Sharp", "Tangential")},
    "Wall_Angle45": wall(angle=45.0),
    "Wall_Angle135": wall(angle=135.0),
    "Wall_Radius3": wall(radius=3.0),
    "Wall_Invert": wall(invert=True),
    "Wall_GapsRectangleRelief": wall(gap1=5.0, gap2=5.0),
    "Wall_GapsRoundRelief": wall(gap1=5.0, gap2=5.0, reliefType="Round"),
    "Wall_Extend": wall(extend1=5.0, extend2=5.0),
    # Miter angles only apply without automatic mitering.
    "Wall_Miter": wall(AutoMiter=False, miterangle1=20.0, miterangle2=20.0),
    "Wall_Offset": wall(BendType="Offset", offset=10.0),
    "Wall_NegativeOffset": wall(BendType="Offset", offset=-2.0),
    "Wall_Perforate": wall(Perforate=True),
    "Wall_Unfold": wall(unfold=True),
    "Wall_Corner": cornerWall,
    "Wall_Chained": chainedWall,
    **{f"Hem_{t}": hem(HemType=t) for t in ("Flat", "Open", "Teardrop", "Rolled")},
    "Hem_Invert": hem(invert=True),
    "Hem_Unfold": hem(unfold=True),
    "Extend": extend(),
    "Extend_Length20": extend(length=20.0),
    "Extend_Gaps": extend(gap1=10.0, gap2=10.0),
    "Fold": fold(),
    "Fold_Angle45": fold(angle=45.0),
    "Fold_Invert": fold(invert=True),
    **{f"Fold_Position_{p.split()[0]}": fold(Position=p)
       for p in ("middle", "backward", "forward")},
    "Fold_Unfold": fold(unfold=True),
    **{f"BaseShape_{t.replace('-', '')}": baseShape(t)
       for t in ("Flat", "L-Shape", "U-Shape", "Tub", "Hat", "Box")},
    "ExtrudedCutout": cutout,
    "Relief": relief,
    "CornerRelief_Circle": cornerRelief("Circle"),
    "CornerRelief_Square": cornerRelief("Square"),
    "WrapCutout": wrapCutout,
    "Forming": forming,
    "Junction": junction,
    "SolidBend": solidBend,
    "FromSolid": fromSolid,
    "Unfold": unfold,
}



def wallVolume(radius=1.0, leg=20.0, angle=90.0):
    """Plate plus a 100 long wall: bend sector between radius and
    radius + THK, plus a straight leg of the given length."""
    sector = math.radians(angle) / 2 * ((radius + THK) ** 2 - radius ** 2)
    return PLATE_VOLUME + 100 * (sector + leg * THK)


# Directly derived values: case -> volume.
EXPECTED_VOLUME = {
    "Base": PLATE_VOLUME,
    "Wall": wallVolume(),
    "Wall_Radius3": wallVolume(radius=3.0),
    "Wall_Angle45": wallVolume(angle=45.0),
    "Wall_Angle135": wallVolume(angle=135.0),
    # With K = 0.5 the neutral fibre is the middle of the sheet, so the flat
    # pattern has the same volume as the folded part.
    "Wall_Unfold": wallVolume(),
    "Unfold": wallVolume(),
    "Fold_Unfold": PLATE_VOLUME,
    "ExtrudedCutout": PLATE_VOLUME - math.pi * 5 ** 2 * THK,
    "Extend": PLATE_VOLUME + 10 * 50 * THK,
    "Extend_Length20": PLATE_VOLUME + 20 * 50 * THK,
}


class TestFeatureGeometry(unittest.TestCase):
    golden = {}
    recorded = {}

    @classmethod
    def setUpClass(cls):
        cls.golden = loadGolden()
        cls.recorded = {}

    @classmethod
    def tearDownClass(cls):
        if UPDATE_GOLDEN and cls.recorded:
            golden = loadGolden()
            golden.update(cls.recorded)
            with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
                json.dump(dict(sorted(golden.items())), f, indent=1)
                f.write("\n")

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestFeatureGeometry")
        _sketch, self.base = makePlate(self.doc)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def checkCase(self, name):
        obj = CASES[name](self.doc, self.base)
        assertRecomputed(self, self.doc, obj)
        values = measure(obj.Shape)
        if name in EXPECTED_VOLUME:
            self.assertAlmostEqual(values["volume"], EXPECTED_VOLUME[name], places=6)
        if UPDATE_GOLDEN:
            self.recorded[name] = values
            return
        golden = self.golden.get(name)
        if golden is None:
            self.fail(f"no reference values for {name}; run with SM_UPDATE_GOLDEN=1")
        for key in ("volume", "area"):
            self.assertAlmostEqual(values[key], golden[key],
                                   delta=REL_TOL * max(1.0, abs(golden[key])), msg=key)
        for key in ("faces", "edges", "vertices"):
            self.assertEqual(values[key], golden[key], key)
        for got, want in zip(values["boundBox"], golden["boundBox"]):
            self.assertAlmostEqual(got, want, delta=TOL, msg="boundBox")


def _addCase(name):
    def test(self):
        self.checkCase(name)
    test.__name__ = f"test_{name}"
    test.__doc__ = f"Geometry of {name}."
    setattr(TestFeatureGeometry, test.__name__, test)


for _name in CASES:
    _addCase(_name)
