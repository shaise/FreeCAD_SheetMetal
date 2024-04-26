# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalCmd.py
#
#  Copyright 2015 Shai Seger <shaise at gmail dot com>
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
from SheetMetalBendWall import SMBendWall
from FreeCAD import Gui
from PySide import QtGui

icons_path = SheetMetalTools.icons_path
panels_path = SheetMetalTools.panels_path
smEpsilon = SheetMetalTools.smEpsilon


class SMViewProviderTree:
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
        if hasattr(self.Object, "Sketch"):
            objs.append(self.Object.Sketch)
        return objs

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_AddWall.svg")

    def setEdit(self, vobj, mode):
        taskd = SMBendWallTaskPanel(vobj.Object)
        Gui.Control.showDialog(taskd)
        return True

    def unsetEdit(self, vobj, mode):
        Gui.Control.closeDialog()
        self.Object.baseObject[0].ViewObject.Visibility = False
        self.Object.ViewObject.Visibility = True
        return False


class SMViewProviderFlat:
    "A View provider that places objects flat under base object"

    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def setupContextMenu(self, viewObject, menu):
        action = menu.addAction(
            FreeCAD.Qt.translate("QObject", "Edit %1").replace(
                "%1", viewObject.Object.Label
            )
        )
        action.triggered.connect(lambda: self.startDefaultEditMode(viewObject))
        return False

    def startDefaultEditMode(self, viewObject):
        document = viewObject.Document.Document
        if not document.HasPendingTransaction:
            text = FreeCAD.Qt.translate("QObject", "Edit %1").replace(
                "%1", viewObject.Object.Label
            )
            document.openTransaction(text)
        viewObject.Document.setEdit(viewObject.Object, 0)

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
        return os.path.join(icons_path, "SheetMetal_AddWall.svg")

    def setEdit(self, vobj, mode):
        taskd = SMBendWallTaskPanel(vobj.Object)
        Gui.Control.showDialog(taskd)
        return True

    def unsetEdit(self, vobj, mode):
        Gui.Control.closeDialog()
        Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)
        self.Object.baseObject[0].ViewObject.Visibility = False
        self.Object.ViewObject.Visibility = True
        return False


class SMBendWallTaskPanel:
    """A TaskPanel for the Sheetmetal"""

    def __init__(self, obj):
        self.obj = obj
        path = os.path.join(panels_path, "FlangeParameters.ui")
        path2 = os.path.join(panels_path, "FlangeAdvancedParameters.ui")
        self.SelModeActive = False
        self.form = []
        self.form.append(Gui.PySideUic.loadUi(path))
        self.form.append(Gui.PySideUic.loadUi(path2))
        self.update()
        # flange parameters connects
        self.form[0].AddRemove.toggled.connect(self.toggleSelectionMode)
        self.form[0].BendType.currentIndexChanged.connect(self.updateProperties)
        self.form[0].Offset.valueChanged.connect(self.updateProperties)
        self.form[0].Radius.valueChanged.connect(self.updateProperties)
        self.form[0].Angle.valueChanged.connect(self.updateProperties)
        self.form[0].Length.valueChanged.connect(self.updateProperties)
        self.form[0].LengthSpec.currentIndexChanged.connect(self.updateProperties)
        self.form[0].UnfoldCheckbox.toggled.connect(self.updateProperties)
        self.form[0].ReversedCheckbox.toggled.connect(self.updateProperties)
        self.form[0].extend1.valueChanged.connect(self.updateProperties)
        self.form[0].extend2.valueChanged.connect(self.updateProperties)
        # advanced flange parameters connects
        self.form[1].reliefTypeButtonGroup.buttonToggled.connect(self.updateProperties)
        self.form[1].reliefWidth.valueChanged.connect(self.updateProperties)
        self.form[1].reliefDepth.valueChanged.connect(self.updateProperties)
        self.form[1].autoMiterCheckbox.toggled.connect(self.updateProperties)
        self.form[1].minGap.valueChanged.connect(self.updateProperties)
        self.form[1].maxExDist.valueChanged.connect(self.updateProperties)
        self.form[1].miterAngle1.valueChanged.connect(self.updateProperties)
        self.form[1].miterAngle2.valueChanged.connect(self.updateProperties)

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok)

    def updateProperties(self):
        self.obj.BendType = self.form[0].BendType.currentIndex()
        if self.obj.BendType == "Offset":
            self.form[0].Offset.setEnabled(True)
        else:
            self.form[0].Offset.setEnabled(False)
        self.obj.offset = self.form[0].Offset.property("value")
        self.obj.radius = self.form[0].Radius.property("value")
        self.obj.angle = self.form[0].Angle.property("value")
        self.obj.length = self.form[0].Length.property("value")
        self.obj.LengthSpec = self.form[0].LengthSpec.currentIndex()
        self.obj.unfold = self.form[0].UnfoldCheckbox.isChecked()
        self.obj.invert = self.form[0].ReversedCheckbox.isChecked()
        self.obj.extend1 = self.form[0].extend1.property("value")
        self.obj.extend2 = self.form[0].extend2.property("value")
        self.obj.reliefType = (
            "Rectangle" if self.form[1].reliefRectangle.isChecked() else "Round"
        )
        self.obj.reliefw = self.form[1].reliefWidth.property("value")
        self.obj.reliefd = self.form[1].reliefDepth.property("value")
        self.obj.AutoMiter = self.form[1].autoMiterCheckbox.isChecked()
        self.obj.minGap = self.form[1].minGap.property("value")
        self.obj.maxExtendDist = self.form[1].maxExDist.property("value")
        self.obj.miterangle1 = self.form[1].miterAngle1.property("value")
        self.obj.miterangle2 = self.form[1].miterAngle2.property("value")
        self.obj.Document.recompute()

    def update(self):
        # load property values
        typeList = ["Material Outside","Material Inside","Thickness Outside","Offset"]
        lSpecList = ["Leg","Outer Sharp","Inner Sharp","Tangential"]
        self.form[0].BendType.setProperty("currentIndex", typeList.index(self.obj.BendType))
        if self.obj.BendType == "Offset":
            self.form[0].Offset.setEnabled(True)
        else:
            self.form[0].Offset.setEnabled(False)
        self.form[0].Offset.setProperty("value", self.obj.offset)
        self.form[0].Radius.setProperty("value", self.obj.radius)
        self.form[0].Angle.setProperty("value", self.obj.angle)
        self.form[0].Length.setProperty("value", self.obj.length)
        self.form[0].LengthSpec.setProperty("currentIndex", lSpecList.index(self.obj.LengthSpec))
        self.form[0].UnfoldCheckbox.setChecked(self.obj.unfold)
        self.form[0].ReversedCheckbox.setChecked(self.obj.invert)
        self.form[0].extend1.setProperty("value", self.obj.extend1)
        self.form[0].extend2.setProperty("value", self.obj.extend2)
        # fill the treewidget
        self.form[0].tree.clear()
        f = self.obj.baseObject
        if isinstance(f[1], list):
            for subf in f[1]:
                # FreeCAD.Console.PrintLog("item: " + subf + "\n")
                item = QtGui.QTreeWidgetItem(self.form[0].tree)
                item.setText(0, f[0].Name)
                item.setIcon(0, QtGui.QIcon(":/icons/Tree_Part.svg"))
                item.setText(1, subf)
        else:
            item = QtGui.QTreeWidgetItem(self.form[0].tree)
            item.setText(0, f[0].Name)
            item.setIcon(0, QtGui.QIcon(":/icons/Tree_Part.svg"))
            item.setText(1, f[1][0])
        # Advanced parameters update
        if self.obj.reliefType == "Rectangle":
            self.form[1].reliefRectangle.setChecked(True)
        else:
            self.form[1].reliefRound.setChecked(True)
        self.form[1].reliefDepth.setProperty("value", self.obj.reliefd)
        self.form[1].reliefWidth.setProperty("value", self.obj.reliefw)
        self.form[1].autoMiterCheckbox.setChecked(self.obj.AutoMiter)
        self.form[1].minGap.setProperty("value", self.obj.minGap)
        self.form[1].maxExDist.setProperty("value", self.obj.maxExtendDist)
        self.form[1].miterAngle1.setProperty("value", self.obj.miterangle1)
        self.form[1].miterAngle2.setProperty("value", self.obj.miterangle2)

    def toggleSelectionMode(self):
        if not self.SelModeActive:
            self.obj.Visibility=False
            self.obj.baseObject[0].Visibility=True
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(self.obj.baseObject[0],self.obj.baseObject[1])
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.GreedySelection)
            self.SelModeActive=True
            self.form[0].AddRemove.setText('Preview')
        else:
            self.updateElement()
            Gui.Selection.clearSelection()
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)
            self.obj.Document.recompute()
            self.obj.baseObject[0].Visibility=False
            self.obj.Visibility=True
            self.SelModeActive=False
            self.form[0].AddRemove.setText('Select')

    def updateElement(self):
        if not self.obj:
            return

        sel = Gui.Selection.getSelectionEx()[0]
        if not sel.HasSubObjects:
            self.update()
            return

        obj = sel.Object
        for elt in sel.SubElementNames:
            if "Face" in elt or "Edge" in elt:
                face = self.obj.baseObject
                found = False
                if face[0] == obj.Name:
                    if isinstance(face[1], tuple):
                        for subf in face[1]:
                            if subf == elt:
                                found = True
                    else:
                        if face[1][0] == elt:
                            found = True
                if not found:
                    self.obj.baseObject = (sel.Object, sel.SubElementNames)
        self.update()

    def accept(self):
        FreeCAD.ActiveDocument.recompute()
        Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)
        Gui.ActiveDocument.resetEdit()
        # self.obj.ViewObject.Visibility=True
        return True

class AddWallCommandClass:
    """Add Wall command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_AddWall.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Make Wall"),
            "Accel": "W",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Extends one or more face, connected by a bend on existing sheet metal.\n"
                "1. Select edges or thickness side faces to create bends with walls.\n"
                "2. Use Property editor to modify other parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        sel = Gui.Selection.getSelectionEx()[0]
        selobj = sel.Object
        viewConf = SheetMetalTools.GetViewConfig(selobj)
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
            return
        doc.openTransaction("Bend")
        if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
            a = doc.addObject("Part::FeaturePython", "Bend")
            SMBendWall(a)
            a.baseObject = (selobj, sel.SubElementNames)
            SMViewProviderTree(a.ViewObject)
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "Bend")
            SMBendWall(a)
            a.baseObject = (selobj, sel.SubElementNames)
            SMViewProviderFlat(a.ViewObject)
            activeBody.addObject(a)
        SheetMetalTools.SetViewConfig(a, viewConf)
        Gui.Selection.clearSelection()
        if SheetMetalTools.is_autolink_enabled():
            root = SheetMetalTools.getOriginalBendObject(a)
            if root:
                a.setExpression("radius", root.Label + ".radius")
        dialog = SMBendWallTaskPanel(a)
        doc.recompute()
        Gui.Control.showDialog(dialog)
        doc.commitTransaction()
        return

    def IsActive(self):
        if (
            len(Gui.Selection.getSelection()) < 1
            or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1
        ):
            return False
        selobj = Gui.Selection.getSelection()[0]
        if selobj.isDerivedFrom("Sketcher::SketchObject"):
            return False
        for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
            if type(selFace) == Part.Vertex:
                return False
        return True


Gui.addCommand("SheetMetal_AddWall", AddWallCommandClass())
