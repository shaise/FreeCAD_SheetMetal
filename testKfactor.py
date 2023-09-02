# ***********************************************************************
# *                                                                     *
# * Copyright (c) 2023 Ondsel                                           *
# *                                                                     *
# ***********************************************************************

import unittest
import FreeCAD
from SheetMetalKfactor import KFactorLookupTable


class TestKFactor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def test_00(self):

        doc = FreeCAD.newDocument()
        sheet = doc.addObject("Spreadsheet::Sheet", "material_foo")

        sheet.Label = "KFactor"

        sheet.set("A1", "Radius / Thickness")
        sheet.set("B1", "K-factor (ANSI)")
        sheet.set("A2", "1")
        sheet.set("B2", "0.38")
        sheet.set("A3", "3")
        sheet.set("B3", "0.43")
        sheet.set("A4", "99")
        sheet.set("B4", "0.5")
        sheet.recompute()

        c = KFactorLookupTable(sheet.Label)
        self.assertTrue(c.k_factor_lookup[1] == 0.38)
        self.assertTrue(c.k_factor_lookup[3] == 0.43)
        self.assertTrue(c.k_factor_lookup[99] == 0.5)
        self.assertTrue(c.k_factor_standard == "ansi")


if __name__ == "__main__":
    unittest.main()
