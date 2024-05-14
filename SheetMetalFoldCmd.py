# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalFoldCmd.py
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

import FreeCAD, Part, os, SheetMetalTools, SheetMetalFoldWall
from FreeCAD import Gui

# kept around for compatibility with old files
SMFoldWall = SheetMetalFoldWall.SMFoldWall

icons_path = SheetMetalTools.icons_path


class SMFoldViewProvider:
    "A View provider that nests children objects under the created one"

    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def updateData(self, fp, prop):
        return

    def getDisplayModes(self, obj):
        modes = []
        return modes

    def setDisplayMode(self, mode):
        return mode

    def onChanged(self, vp, prop):
        return

    def __getstate__(self):
        #        return {'ObjectName' : self.Object.Name}
        return None

    def __setstate__(self, state):
        self.loads(state)

    # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
    def dumps(self):
        return None

    def loads(self, state):
        if state is not None:
            import FreeCAD

            doc = FreeCAD.ActiveDocument  # crap
            self.Object = doc.getObject(state["ObjectName"])

    def claimChildren(self):
        objs = []
        if hasattr(self.Object, "baseObject"):
            objs.append(self.Object.baseObject[0])
            objs.append(self.Object.BendLine)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddFoldWall.svg")


class SMFoldPDViewProvider:
    "A View provider that nests children objects under the created one"

    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def updateData(self, fp, prop):
        return

    def getDisplayModes(self, obj):
        modes = []
        return modes

    def setDisplayMode(self, mode):
        return mode

    def onChanged(self, vp, prop):
        return

    def __getstate__(self):
        #        return {'ObjectName' : self.Object.Name}
        return None

    def __setstate__(self, state):
        self.loads(state)

    # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
    def dumps(self):
        return None

    def loads(self, state):
        if state is not None:
            import FreeCAD

            doc = FreeCAD.ActiveDocument  # crap
            self.Object = doc.getObject(state["ObjectName"])

    def claimChildren(self):
        objs = []
        if hasattr(self.Object, "BendLine"):
            objs.append(self.Object.BendLine)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddFoldWall.svg")


class AddFoldWallCommandClass:
    """Add Fold Wall command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_AddFoldWall.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Fold a Wall"),
            "Accel": "C, F",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Fold a wall of metal sheet\n"
                "1. Select a flat face on sheet metal and\n"
                "2. Select a bend line (sketch) on same face (ends of sketch bend lines must"
                " extend beyond edges of face) to create sheetmetal fold.\n"
                "3. Use Property editor to modify other parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        sel = Gui.Selection.getSelectionEx()
        selobj = Gui.Selection.getSelectionEx()[0].Object
        viewConf = SheetMetalTools.GetViewConfig(selobj)
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
            return
        doc.openTransaction("Bend")
        if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
            a = doc.addObject("Part::FeaturePython", "Fold")
            SMFoldWall(a)
            a.baseObject = (selobj, sel[0].SubElementNames)
            a.BendLine = sel[1].Object
            SMFoldViewProvider(a.ViewObject)
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "Fold")
            SMFoldWall(a)
            a.baseObject = (selobj, sel[0].SubElementNames)
            a.BendLine = sel[1].Object
            SMFoldPDViewProvider(a.ViewObject)
            activeBody.addObject(a)
        SheetMetalTools.SetViewConfig(a, viewConf)
        if SheetMetalTools.is_autolink_enabled():
            root = SheetMetalTools.getOriginalBendObject(a)
            if root:
                a.setExpression("radius", root.Label + ".radius")
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if len(Gui.Selection.getSelection()) < 2:
            return False
        selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
        if type(selFace) != Part.Face:
            return False
        selobj = Gui.Selection.getSelection()[1]
        if not (selobj.isDerivedFrom("Sketcher::SketchObject")):
            return False
        return True


Gui.addCommand("SheetMetal_AddFoldWall", AddFoldWallCommandClass())
