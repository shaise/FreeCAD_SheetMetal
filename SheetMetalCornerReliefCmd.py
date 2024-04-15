# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalCornerReliefCmd.py
#
#  Copyright 2020 Jaise James <jaisekjames at gmail dot com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
###################################################################################

import FreeCAD, Part, os, SheetMetalTools
from FreeCAD import Gui
from SheetMetalCornerRelief import SMCornerRelief

icons_path = SheetMetalTools.icons_path

# add translations path
Gui.addLanguagePath(SheetMetalTools.language_path)
Gui.updateLocale()


class SMCornerReliefVP:
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
            objs.append(self.Object.Sketch)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddCornerRelief.svg")


class SMCornerReliefPDVP:
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
        if hasattr(self.Object, "Sketch"):
            objs.append(self.Object.Sketch)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddCornerRelief.svg")


class AddCornerReliefCommandClass:
    """Add Corner Relief command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_AddCornerRelief.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Add Corner Relief"),
            "Accel": "C, R",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Corner Relief to metal sheet corner.\n"
                "1. Select 2 Edges (on flat face that shared with bend faces) to create Relief on sheetmetal.\n"
                "2. Use Property editor to modify default parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        sel = Gui.Selection.getSelectionEx()[0]
        selobj = Gui.Selection.getSelectionEx()[0].Object
        viewConf = SheetMetalTools.GetViewConfig(selobj)
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
            return
        doc.openTransaction("Corner Relief")
        if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
            a = doc.addObject("Part::FeaturePython", "CornerRelief")
            SMCornerRelief(a)
            a.baseObject = (selobj, sel.SubElementNames)
            SMCornerReliefVP(a.ViewObject)
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "CornerRelief")
            SMCornerRelief(a)
            SMCornerReliefPDVP(a.ViewObject)
            activeBody.addObject(a)
        SheetMetalTools.SetViewConfig(a, viewConf)
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if (
            len(Gui.Selection.getSelection()) < 1
            or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 2
        ):
            return False
        #    selobj = Gui.Selection.getSelection()[0]
        for selVertex in Gui.Selection.getSelectionEx()[0].SubObjects:
            if type(selVertex) != Part.Edge:
                return False
        return True


Gui.addCommand("SheetMetal_AddCornerRelief", AddCornerReliefCommandClass())
