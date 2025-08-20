# -*- coding: utf-8 -*-
##############################################################################
#
#  InitGui.py
#
#  Copyright 2015 Shai Seger <shaise at gmail dot com>
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
#
##############################################################################

import os
import FreeCAD
from FreeCAD import Gui
import SheetMetalTools
from engineering_mode import engineering_mode_enabled

# add translations path
SMWBPath = SheetMetalTools.mod_path
SMIconPath = SheetMetalTools.icons_path

LanguagePath = os.path.join(SMWBPath, "Resources", "translations")
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()


class SMWorkbench(Workbench):
    global SMIconPath
    global SMWBPath
    global SHEETMETALWB_VERSION
    global engineering_mode_enabled

    MenuText = FreeCAD.Qt.translate("SheetMetal", "Sheet Metal")
    ToolTip = FreeCAD.Qt.translate(
        "SheetMetal",
        "Sheet Metal workbench allows for designing and unfolding sheet metal parts",
    )
    Icon = os.path.join(SMIconPath, "SMLogo.svg")

    def Initialize(self):
        "This function is executed when FreeCAD starts"
        import SheetMetalCmd  # import here all the needed files that create your FreeCAD commands
        import SheetMetalExtendCmd
        import SheetMetalUnfolder
        import SheetMetalBaseCmd
        import SheetMetalFoldCmd
        import SheetMetalRelief
        import SheetMetalJunction
        import SheetMetalBend
        import SketchOnSheetMetalCmd
        import ExtrudedCutout
        import SheetMetalCornerReliefCmd
        import SheetMetalFormingCmd
        import SheetMetalUnfoldCmd
        import SheetMetalBaseShapeCmd
        import os.path
        import SheetMetalExtraToolbar

        self.list = [
            "SheetMetal_AddBase",
            "SheetMetal_AddWall",
            "SheetMetal_Extrude",
            "SheetMetal_AddFoldWall",
            "SheetMetal_Unfold",
            "SheetMetal_UnfoldUpdate",
            "SheetMetal_AddCornerRelief",
            "SheetMetal_AddRelief",
            "SheetMetal_AddJunction",
            "SheetMetal_AddBend",
            "SheetMetal_SketchOnSheet",
            "SheetMetal_AddCutout",
            "SheetMetal_Forming",
            "SheetMetal_BaseShape",
        ]  # A list of command names created in the line above
        if engineering_mode_enabled():
            self.list.insert(
                self.list.index("SheetMetal_Unfold") + 1, "SheetMetal_UnattendedUnfold"
            )
        self.appendToolbar(
            FreeCAD.Qt.translate("SheetMetal", "Sheet Metal"), self.list
        )  # creates a new toolbar with your commands
        self.appendMenu(
            FreeCAD.Qt.translate("SheetMetal", "&Sheet Metal"), self.list
        )  # creates a new menu
        # self.appendMenu(["An existing Menu","My submenu"],self.list) # appends a submenu to an existing menu
        Gui.addPreferencePage(os.path.join(SMWBPath, "Resources/panels/SMprefs.ui"), "SheetMetal")
        Gui.addIconPath(SMIconPath)
        SheetMetalExtraToolbar.check_setup()

    def Activated(self):
        "This function is executed when the workbench is activated"
        return

    def Deactivated(self):
        "This function is executed when the workbench is deactivated"
        return

    def ContextMenu(self, recipient):
        "This is executed whenever the user right-clicks on screen"
        # "recipient" will be either "view" or "tree"
        self.appendContextMenu(
            FreeCAD.Qt.translate("SheetMetal", "Sheet Metal"), self.list
        )  # add commands to the context menu

    def GetClassName(self):
        # this function is mandatory if this is a full python workbench
        return "Gui::PythonWorkbench"


Gui.addWorkbench(SMWorkbench())
