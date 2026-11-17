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

"""Name stability of Bend (SMBendWall) in a PartDesign body.

"""

import os
import re
import tempfile
import unittest

import FreeCAD
import Part
import Sketcher

HAS_TOPONAMING = hasattr(Part.Shape, "ElementMap")


@unittest.skipUnless(HAS_TOPONAMING, "needs FreeCAD with toponaming support")
class TestBendToponaming(unittest.TestCase):
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
        # (a duplicate-name postfix is dropped).
        self._recompute()

    def tearDown(self):
        if self.doc is not None:
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

    @staticmethod
    def _toolTags(obj):
        """Decoded packed tags in the element names of obj, by mapped name."""
        from SheetMetalTools import smDecodeToolTag

        tags = {}
        for name in obj.Shape.ElementMap:
            for tag in re.findall(r":H(-[0-9a-fA-F]+)", name):
                fields = smDecodeToolTag(int(tag, 16))
                if fields:
                    tags.setdefault(name, []).append(fields)
        return tags

    def _assertValid(self, *objs):
        for obj in objs:
            self.assertNotIn("Invalid", obj.State, obj.Name)
            self.assertTrue(obj.isValid(), obj.getStatusString())

    def _recompute(self):
        for obj in (self.bend1, self.bend2):
            obj.touch()
        self.doc.recompute()
        self._assertValid(self.bend1, self.bend2)

    def testAllElementsNamed(self):
        for obj in (self.bend1, self.bend2):
            shape = obj.Shape
            total = len(shape.Faces) + len(shape.Edges) + len(shape.Vertexes)
            self.assertEqual(len(self._names(obj)), total, obj.Name)

    def testNamesStableOnRecompute(self):
        before = {obj.Name: self._names(obj) for obj in (self.bend1, self.bend2)}
        self._recompute()
        for obj in (self.bend1, self.bend2):
            self.assertEqual(before[obj.Name], self._names(obj), obj.Name)

    def testNamesSurviveSketchChange(self):
        # Indices may change with the width; the set of names must not.
        before = {obj.Name: set(self._names(obj).values()) for obj in (self.bend1, self.bend2)}
        self.sketch.setDatum(self.widthConstraint, FreeCAD.Units.Quantity("120 mm"))
        self.doc.recompute()
        self._assertValid(self.bend1, self.bend2)
        for obj in (self.bend1, self.bend2):
            self.assertEqual(before[obj.Name], set(self._names(obj).values()), obj.Name)

    def testNamesSurviveSaveAndReopen(self):
        before = {obj.Name: self._names(obj) for obj in (self.bend1, self.bend2)}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "BendToponaming.FCStd")
            self.doc.saveAs(path)
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None
            self.doc = FreeCAD.openDocument(path)
            self.bend1 = self.doc.getObject("Bend1")
            self.bend2 = self.doc.getObject("Bend2")
            for obj in (self.bend1, self.bend2):
                self.assertEqual(before[obj.Name], self._names(obj), obj.Name + " (loaded)")
            self._recompute()
            for obj in (self.bend1, self.bend2):
                self.assertEqual(before[obj.Name], self._names(obj), obj.Name + " (recomputed)")

    def testTagsCarryTheFeatureId(self):
        # The tools of each Bend are tagged with the Bend's own object ID,
        # not with anything derived from upstream names.
        for obj in (self.bend1, self.bend2):
            own = [f for fields in self._toolTags(obj).values() for f in fields
                   if f["featureId"] == obj.ID]
            self.assertTrue(own, obj.Name)
            self.assertTrue(all(f["slot"] == 0 and f["piece"] == 0 for f in own), obj.Name)

    def testWallNamesSurviveGapChange(self):
        # Removing the gaps removes the relief tools; the wall and bend
        # tools keep their roles, so their faces keep their names.
        from SheetMetalCmd import smRoleBend, smRoleWall

        def wallNames():
            return {name for name, fields in self._toolTags(self.bend1).items()
                    if name.endswith(",F") and any(
                        f["featureId"] == self.bend1.ID and f["role"] in (smRoleWall, smRoleBend)
                        for f in fields)}

        before = wallNames()
        self.assertTrue(before)
        self.bend1.gap1 = self.bend1.gap2 = 0
        self.doc.recompute()
        self._assertValid(self.bend1, self.bend2)
        self.assertEqual(before, wallNames())


class TestToolShapeTag(unittest.TestCase):
    """Packed tags (SheetMetalTools.smToolTag) are unique, decodable, and
    fit 31 bits on every platform. Adapted from Simon Huwyler's branch."""

    def testUniqueAndDecodable(self):
        from SheetMetalTools import smDecodeToolTag, smToolTag

        tags = set()
        for featureId in (1, 2, 1000, 32767):
            for segment in (0, 1, 15):
                for slot in (0, 1, 31):
                    for piece in (0, 3):
                        for role in (0, 1, 15):
                            tag = smToolTag(featureId, slot, role, segment, piece)
                            self.assertLess(tag, 0)
                            self.assertGreaterEqual(tag, -(2**31 - 1))
                            self.assertEqual(smDecodeToolTag(tag), {
                                "featureId": featureId, "segment": segment, "slot": slot,
                                "piece": piece, "role": role})
                            tags.add(tag)
        self.assertEqual(len(tags), 4 * 3 * 3 * 2 * 3)

    def testOutOfRangeIsZero(self):
        from SheetMetalTools import smToolTag

        self.assertEqual(smToolTag(0, 0, 1), 0)
        self.assertEqual(smToolTag(1 << 15, 0, 1), 0)
        self.assertEqual(smToolTag(5, 32, 1), 0)
        self.assertEqual(smToolTag(5, 0, 16), 0)
        self.assertEqual(smToolTag(5, 0, 1, segment=16), 0)
        self.assertEqual(smToolTag(5, 0, 1, piece=4), 0)

    def testFallbacksAreHashedAndDisjoint(self):
        import Part
        from SheetMetalTools import smDecodeToolTag, smTagFeatureTool, smTagTool

        def tagOf(tag):
            return tag(Part.makeBox(1, 1, 1)).Tag

        hashed = [tagOf(lambda t: smTagFeatureTool(t, 1 << 15, 0, 1)),  # ID out of range
                  tagOf(lambda t: smTagFeatureTool(t, None, 0, 1, fallbackKey="Edge1")),
                  tagOf(lambda t: smTagTool(t, "Edge1", "role"))]
        for tag in hashed:
            self.assertLess(tag, 0)
            self.assertTrue(2**29 <= -tag < 2**30, hex(tag))
            self.assertIsNone(smDecodeToolTag(tag))
        # Same fields, same tag on every call.
        self.assertEqual(hashed[0], tagOf(lambda t: smTagFeatureTool(t, 1 << 15, 0, 1)))
