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


"""Save / reload tests.

Every feature of the geometry tests is built into one document, which is
saved, closed, reopened and fully recomputed. Proxies, properties, links
and geometry must come back unchanged.
"""

import os
import shutil
import tempfile
import unittest
import zipfile

import FreeCAD

from SMTests.helpers import TOL, findElement, isLine, makePlate, makeWall
from SMTests.testFeatures import CASES


def snapshot(doc):
    """What must survive a save and reload, per object name."""
    state = {}
    for obj in doc.Objects:
        if not obj.isDerivedFrom("Part::Feature"):
            continue
        links = getattr(obj, "baseObject", None)
        state[obj.Name] = {
            "proxy": type(obj.Proxy).__name__ if hasattr(obj, "Proxy") else None,
            "volume": obj.Shape.Volume,
            "faces": len(obj.Shape.Faces),
            "links": (links[0].Name, list(links[1])) if links else None,
        }
    return state


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="SMTestPersistence")
        self.doc = FreeCAD.newDocument("TestPersistence")
        self.path = os.path.join(self.dir, "persistence.FCStd")

    def tearDown(self):
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)
        shutil.rmtree(self.dir, ignore_errors=True)

    def reload(self):
        self.doc.saveAs(self.path)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = None
        self.doc = FreeCAD.openDocument(self.path)

    def recomputeAll(self):
        for obj in self.doc.Objects:
            obj.touch()
        self.doc.recompute()
        invalid = [obj.Name for obj in self.doc.Objects if "Invalid" in obj.State]
        self.assertEqual(invalid, [], "objects failed to recompute after reload")

    def testAllFeatures(self):
        _sketch, base = makePlate(self.doc)
        for name, build in CASES.items():
            with self.subTest(case=name):
                build(self.doc, base)
        self.doc.recompute()
        before = snapshot(self.doc)
        self.assertGreaterEqual(len(before), len(CASES), "not every case was built")

        self.reload()
        self.assertEqual(snapshot(self.doc).keys(), before.keys())
        self.recomputeAll()
        after = snapshot(self.doc)
        for name, want in before.items():
            got = after[name]
            with self.subTest(object=name):
                self.assertEqual(got["proxy"], want["proxy"])
                self.assertEqual(got["links"], want["links"])
                self.assertEqual(got["faces"], want["faces"])
                self.assertAlmostEqual(got["volume"], want["volume"],
                                       delta=1e-6 * max(1.0, want["volume"]))

    def testTopologicalNamesAreSaved(self):
        # Wall2 references an edge Wall1 creates. After reloading, a change
        # to Wall1 that renumbers its edges must still be followed, which
        # needs the mapped name saved with the link (see docs/TNP.md).
        _sketch, base = makePlate(self.doc)
        edge1 = findElement(base.Shape, "Edge", lambda e: isLine(e)
                            and abs(e.BoundBox.YMin - 50) < TOL
                            and abs(e.BoundBox.YMax - 50) < TOL
                            and abs(e.BoundBox.ZMin - 2) < TOL)
        wall1 = makeWall(self.doc, base, [edge1], "Wall1")
        self.doc.recompute()
        shape = wall1.Shape
        zmax, ymax = shape.BoundBox.ZMax, shape.BoundBox.YMax

        def farEdge(e):
            return (isLine(e) and e.BoundBox.XLength > 1 and abs(e.BoundBox.ZMin - zmax) < TOL
                    and abs(e.BoundBox.YMin - ymax) < TOL)

        makeWall(self.doc, wall1, [findElement(shape, "Edge", farEdge)], "Wall2")
        self.doc.recompute()

        self.reload()
        with zipfile.ZipFile(self.path) as archive:
            xml = archive.read("Document.xml").decode("utf-8")
        self.assertIn("shadow=", xml)

        wall1 = self.doc.getObject("Wall1")
        wall1.gap1 = wall1.gap2 = 5.0
        self.doc.recompute()
        sub = self.doc.getObject("Wall2").baseObject[1][0]
        self.assertFalse(sub.startswith("?"), f"lost reference {sub}")
        self.assertTrue(farEdge(wall1.Shape.getElement(sub)), f"{sub} is another edge")
