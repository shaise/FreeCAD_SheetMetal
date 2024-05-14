# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalBaseCmd.py
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
###################################################################################

import FreeCAD, os
from FreeCAD import Gui
import SheetMetalTools, SheetMetalBaseBend

# kept around for compatibility with old files
SMBaseBend = SheetMetalBaseBend.SMBaseBend

translate = FreeCAD.Qt.translate
icons_path = SheetMetalTools.icons_path
panels_path = SheetMetalTools.panels_path

class SMBaseViewProvider:
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
        #    return {'ObjectName' : self.Object.Name}
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
        if hasattr(self, "Object") and hasattr(self.Object, "BendSketch"):
            objs.append(self.Object.BendSketch)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddBase.svg")


class AddBaseCommandClass:
    """Add Base Wall command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_AddBase.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": translate("SheetMetal", "Make Base Wall"),
            "Accel": "C, B",
            "ToolTip": translate(
                "SheetMetal",
                "Create a sheetmetal wall from a sketch\n"
                "1. Select a Skech to create bends with walls.\n"
                "2. Use Property editor to modify other parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        selobj = Gui.Selection.getSelectionEx()[0].Object
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        #    if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
        #        return
        doc.openTransaction("BaseBend")
        if activeBody is None:
            a = doc.addObject("Part::FeaturePython", "BaseBend")
            SMBaseBend(a)
            SMBaseViewProvider(a.ViewObject)
            a.BendSketch = selobj
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "BaseBend")
            SMBaseBend(a)
            SMBaseViewProvider(a.ViewObject)
            a.BendSketch = selobj
            activeBody.addObject(a)
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if len(Gui.Selection.getSelection()) != 1:
            return False
        selobj = Gui.Selection.getSelection()[0]
        if not (
            selobj.isDerivedFrom("Sketcher::SketchObject")
            or selobj.isDerivedFrom("PartDesign::ShapeBinder")
            or selobj.isDerivedFrom("PartDesign::SubShapeBinder")
        ):
            return False
        return True


Gui.addCommand("SheetMetal_AddBase", AddBaseCommandClass())
