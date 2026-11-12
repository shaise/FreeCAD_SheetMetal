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


"""Flat pattern accuracy of both unfolders.

The expected flat length is computed independently from the folded shape:
the lengths of the flat segments plus, for each bend, the bend allowance
angle * (r + k * t), with r the inner radius and k the ANSI K-factor
(DIN K-factors are twice the ANSI value).
"""

import math
import unittest

import FreeCAD

import SheetMetalNewUnfolder
import SheetMetalTools
import SheetMetalUnfoldCmd
from SheetMetalLookup import interpolate_csv
from SMTests.helpers import THK, TOL, backEdge, makePlate, makeWall, topEdge, topFace

# Length tolerance of the flat pattern, in mm.
FLAT_TOL = 1e-3
# Width of the plate along the bend lines.
WIDTH = 100.0


def isPlateFace(face):
    return abs(abs(face.normalAt(0, 0).z) - 1) < TOL


def expectedFlatLength(shape, radius, kAnsi):
    """Flat length across the bends, from the folded shape of a plate with
    walls along X: plate flat + for each bend, its allowance + leg flat."""
    plate = shape.getElement(topFace(shape))
    length = plate.Area / WIDTH
    inner = [f for f in shape.Faces if f.Surface.TypeId == "Part::GeomCylinder"
             and abs(f.Surface.Radius - radius) < TOL]
    for bend in inner:
        umin, umax, _vmin, _vmax = bend.ParameterRange
        length += (umax - umin) * (radius + kAnsi * THK)
        legs = [f for f in shape.Faces if f.Surface.TypeId == "Part::GeomPlane"
                and abs(f.normalAt(0, 0).x) < TOL and not isPlateFace(f)
                and any(e.isSame(be) for e in f.Edges for be in bend.Edges)]
        length += legs[0].Area / WIDTH
    return length


class UnfoldAccuracyBase:
    """Mixin; subclasses select the unfolder with OLD_UNFOLDER."""

    OLD_UNFOLDER = False

    def setUp(self):
        self.oldSetting = SheetMetalTools.params.GetBool("UseOldUnfolder", False)
        SheetMetalTools.params.SetBool("UseOldUnfolder", self.OLD_UNFOLDER)
        self.doc = FreeCAD.newDocument("TestUnfoldAccuracy")
        self.sketch, self.base = makePlate(self.doc)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)
        SheetMetalTools.params.SetBool("UseOldUnfolder", self.oldSetting)

    def unfold(self, folded, kFactor=0.5, standard="ansi", sheet=None):
        obj = self.doc.addObject("Part::FeaturePython", "Unfold")
        SheetMetalUnfoldCmd.SMUnfold(obj, folded, [topFace(folded.Shape)])
        obj.GenerateSketch = False
        obj.KFactor = kFactor
        obj.KFactorStandard = standard
        obj.MaterialSheet = sheet.Name if sheet else "_manual"
        self.doc.recompute()
        self.assertFalse("Invalid" in obj.State, "unfold failed")
        shape = obj.Shape
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        # The flat pattern lies in the plane of the plate.
        self.assertAlmostEqual(shape.BoundBox.ZLength, THK, delta=FLAT_TOL)
        self.assertAlmostEqual(shape.BoundBox.XLength, WIDTH, delta=FLAT_TOL)
        return shape

    def checkWall(self, kFactor=0.5, standard="ansi", **wallProps):
        wall = makeWall(self.doc, self.base, [backEdge(self.base.Shape)])
        for prop, value in wallProps.items():
            setattr(wall, prop, value)
        self.doc.recompute()
        kAnsi = kFactor / 2 if standard == "din" else kFactor
        expected = expectedFlatLength(wall.Shape, wall.radius.Value, kAnsi)
        flat = self.unfold(wall, kFactor, standard)
        self.assertAlmostEqual(flat.BoundBox.YLength, expected, delta=FLAT_TOL)

    def testRightAngle(self):
        self.checkWall()

    def testKFactors(self):
        for kFactor in (0.0, 0.33, 0.44, 1.0):
            with self.subTest(kFactor=kFactor):
                self.checkWall(kFactor)

    def testDinKFactor(self):
        self.checkWall(0.8, "din")

    def testRadii(self):
        for radius in (0.5, 2.0, 6.0):
            with self.subTest(radius=radius):
                self.checkWall(0.4, radius=radius)

    def testAngles(self):
        for angle in (30.0, 45.0, 120.0, 150.0):
            with self.subTest(angle=angle):
                self.checkWall(0.4, angle=angle)

    def testBendTypes(self):
        for bendType in ("Material Outside", "Material Inside", "Thickness Outside"):
            with self.subTest(bendType=bendType):
                self.checkWall(0.4, BendType=bendType)

    def testDownwardBend(self):
        self.checkWall(0.4, invert=True)

    def testUProfile(self):
        front = topEdge(self.base.Shape, lambda b: abs(b.YMin) < TOL and abs(b.YMax) < TOL)
        back = backEdge(self.base.Shape)
        wall = makeWall(self.doc, self.base, [front, back])
        self.doc.recompute()
        expected = expectedFlatLength(wall.Shape, wall.radius.Value, 0.4)
        flat = self.unfold(wall, 0.4)
        self.assertAlmostEqual(flat.BoundBox.YLength, expected, delta=FLAT_TOL)


class TestUnfoldAccuracy(UnfoldAccuracyBase, unittest.TestCase):
    """The default (V2) unfolder."""

    def makeKFactorSheet(self, rows, standard="ANSI"):
        sheet = self.doc.addObject("Spreadsheet::Sheet", "Material")
        sheet.set("A1", "Radius / Thickness")
        sheet.set("B1", f"K-factor ({standard})")
        for i, (ratio, kFactor) in enumerate(rows):
            sheet.set(f"A{i + 2}", str(ratio))
            sheet.set(f"B{i + 2}", str(kFactor))
        sheet.recompute()
        return sheet

    def testMaterialSheetInterpolates(self):
        # r / t = 4 / 2 = 2 lies in the second segment of the table:
        # k = 0.4 + (0.5 - 0.4) * (2 - 1) / (4 - 1).
        sheet = self.makeKFactorSheet([(0.5, 0.3), (1, 0.4), (4, 0.5)])
        wall = makeWall(self.doc, self.base, [backEdge(self.base.Shape)])
        wall.radius = 4.0
        self.doc.recompute()
        expected = expectedFlatLength(wall.Shape, 4.0, 0.4 + 0.1 / 3)
        flat = self.unfold(wall, sheet=sheet)
        self.assertAlmostEqual(flat.BoundBox.YLength, expected, delta=FLAT_TOL)


class TestOldUnfolderAccuracy(UnfoldAccuracyBase, unittest.TestCase):
    """The V1 unfolder (preference UseOldUnfolder)."""

    OLD_UNFOLDER = True


class TestBendAllowanceCalculator(unittest.TestCase):
    """K-factor lookup of the V2 unfolder."""

    def calculator(self, ratios, kFactors, standard="ANSI"):
        bac = SheetMetalNewUnfolder.BendAllowanceCalculator()
        bac.k_factor_standard = bac.KFactorStandard[standard]
        bac.radius_thickness_values = ratios
        bac.k_factor_values = kFactors
        return bac

    def testSingleValue(self):
        bac = SheetMetalNewUnfolder.BendAllowanceCalculator.from_single_value(0.42, "ansi")
        for radius in (0.1, 2.0, 50.0):
            self.assertAlmostEqual(bac.get_k_factor(radius, 2.0), 0.42)

    def testDinIsHalvedToAnsi(self):
        bac = SheetMetalNewUnfolder.BendAllowanceCalculator.from_single_value(0.8, "din")
        self.assertAlmostEqual(bac.get_k_factor(2.0, 2.0), 0.4)

    def testTableClampsOutsideRange(self):
        bac = self.calculator([0.5, 1.0, 4.0], [0.3, 0.4, 0.5])
        self.assertAlmostEqual(bac.get_k_factor(0.5, 2.0), 0.3)  # r/t = 0.25
        self.assertAlmostEqual(bac.get_k_factor(10.0, 2.0), 0.5)  # r/t = 5

    def testTableInterpolatesEverySegment(self):
        bac = self.calculator([0.5, 1.0, 4.0], [0.3, 0.4, 0.5])
        for ratio, expected in ((0.75, 0.35), (1.0, 0.4), (2.0, 0.4 + 0.1 / 3),
                                (3.0, 0.4 + 0.2 / 3), (4.0, 0.5)):
            with self.subTest(ratio=ratio):
                self.assertAlmostEqual(bac.get_k_factor(ratio * 2.0, 2.0), expected)

    def testBendAllowance(self):
        bac = SheetMetalNewUnfolder.BendAllowanceCalculator.from_single_value(0.4, "ansi")
        up = SheetMetalNewUnfolder.BendDirection.UP
        allowance = bac.get_bend_allowance(up, 3.0, 2.0, math.pi / 2)
        self.assertAlmostEqual(allowance, math.pi / 2 * (3.0 + 0.4 * 2.0))


class TestInterpolateCsv(unittest.TestCase):
    """K-factor lookup by thickness from a CSV material file."""

    def testInterpolation(self):
        thicknesses, kFactors = [1.0, 2.0, 4.0], [0.3, 0.4, 0.5]
        for thickness, expected in ((0.5, 0.3), (1.5, 0.35), (3.0, 0.45), (9.0, 0.5)):
            with self.subTest(thickness=thickness):
                self.assertAlmostEqual(interpolate_csv(thickness, thicknesses, kFactors),
                                       expected)
