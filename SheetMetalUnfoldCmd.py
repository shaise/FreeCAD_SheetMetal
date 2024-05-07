# -*- coding: utf-8 -*-
###############################################################################
#
#  SheetMetalUnfoldCmd.py
#
#  Copyright 2014, 2018 Ulrich Brammer <ulrich@Pauline>
#  Copyright 2023 Ondsel Inc.
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
###############################################################################

import FreeCAD, Part, os, SheetMetalTools, SheetMetalKfactor
from PySide import QtCore, QtGui
from FreeCAD import Gui
from engineering_mode import engineering_mode_enabled
from SheetMetalUnfolder import SMUnfold, processUnfoldSketches
from SheetMetalLogger import SMLogger

GENSKETCHCOLOR = "#000080"
BENDSKETCHCOLOR = "#c00000"
INTSKETCHCOLOR = "#ff5733"
KFACTOR = 0.40
panels_path = SheetMetalTools.panels_path
icons_path = SheetMetalTools.icons_path
mds_help_url = "https://github.com/shaise/FreeCAD_SheetMetal#material-definition-sheet"

######## ViewProvider ########


class SMUnfoldVP:
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

    def getIcon(self):
        return os.path.join(icons_path, "SheetMetal_Unfold.svg")

    def setEdit(self, vobj, mode):
        vobj.Object.Document.openTransaction("Unfold")
        taskd = SMUnfoldTaskPanel(vobj.Object)
        taskd.form[1].chkSketch.setChecked(False)
        Gui.Control.showDialog(taskd)
        return True

    def unsetEdit(self, vobj, mode):
        Gui.Control.closeDialog()
        self.Object.ViewObject.Visibility = True
        return False


######## TaskPanel ########


class SMUnfoldTaskPanel:
    def __init__(self, object):
        path = os.path.join(panels_path,"UnfoldOptions.ui")
        path2 = os.path.join(panels_path,"UnfoldSketchOptions.ui")
        self.form = []
        self.form.append(Gui.PySideUic.loadUi(path))
        self.form.append(Gui.PySideUic.loadUi(path2))
        self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
        self.object = object
        self.SelModeActive = False
        self.setupUi()

    def _boolToState(self, bool):
        return QtCore.Qt.Checked if bool else QtCore.Qt.Unchecked

    def _isManualKSelected(self):
        return self.form[0].availableMds.currentIndex() == (
            self.form[0].availableMds.count() - 1
        )

    def _isNoMdsSelected(self):
        return self.form[0].availableMds.currentIndex() == 0

    def _getMdsIndex(self, label):
        for i in range(self.form[0].availableMds.count()):
            if self.form[0].availableMds.itemText(i) == label:
                return i
        return -1

    def setupUi(self):
        self.form[0].availableMds.currentIndexChanged.connect(self.availableMdsChange)
        self.form[0].selectFaceButton.toggled.connect(self.toggleSelectionMode)

        self.form[0].kfactorAnsi.setChecked(self.object.kFactorStandard == "ansi")
        self.form[0].kfactorDin.setChecked(self.object.kFactorStandard == "din")
        self.form[0].kFactSpin.setValue(self.object.kfactor)
        self.form[0].transSpin.setValue(self.object.ViewObject.Transparency)

        self.populateMdsList()
        self.availableMdsChange()

        self.form[0].update()
        self.form[1].chkSketch.stateChanged.connect(self.chkSketchChange)
        self.form[1].chkSeparate.stateChanged.connect(self.chkSketchChange)
        self.form[1].chkSketch.setCheckState(
            self._boolToState(self.pg.GetBool("genSketch"))
        )
        self.form[1].chkSeparate.setCheckState(
            self._boolToState(self.pg.GetBool("separateSketches"))
        )
        self.form[1].genColor.setProperty(
            "color", self.pg.GetString("genColor", GENSKETCHCOLOR)
        )
        self.form[1].bendColor.setProperty(
            "color", self.pg.GetString("bendColor", BENDSKETCHCOLOR)
        )
        self.form[1].internalColor.setProperty(
            "color", self.pg.GetString("internalColor", INTSKETCHCOLOR)
        )


    def accept(self):
        if self.SelModeActive:
            self.toggleSelectionMode()
        self.object.kFactorStandard = "din" if self.form[0].kfactorDin.isChecked() else "ansi"
        self.object.kfactor = self.form[0].kFactSpin.value()
        if self._isManualKSelected():
            self.object.useManualKFactor = True
            self.object.materialSheet = None
        elif self._isNoMdsSelected():
            msg = FreeCAD.Qt.translate(
                "Logger", "Unfold operation needs to know K-factor value(s) to be used."
            )
            SMLogger.warning(msg)
            msg += FreeCAD.Qt.translate(
                "QMessageBox",
                "<ol>\n"
                "<li>Either select 'Manual K-factor'</li>\n"
                "<li>Or use a <a href='{}'>Material Definition Sheet</a></li>\n"
                "</ol>",
            ).format(mds_help_url)
            QtGui.QMessageBox.warning(
                None, FreeCAD.Qt.translate("QMessageBox", "Warning"), msg
            )
            return None
        else:
            self.object.useManualKFactor = False
            self.object.materialSheet = FreeCAD.ActiveDocument.getObjectsByLabel(
                self.form[0].availableMds.currentText()
            )[0]
        self.object.ViewObject.Transparency = self.form[0].transSpin.value()
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()
        if self.form[1].chkSketch.isChecked() and self.object.foldComp:
            FreeCAD.ActiveDocument.openTransaction("Unfold sketch projection")
            shape = self.object.Shape
            foldLines = self.object.foldComp.Edges
            norm = self.object.baseObject[0].getSubObject(self.object.baseObject[1][0]).normalAt(0,0)
            splitSketches = self.form[1].chkSeparate.isChecked()
            genSketchColor = self.form[1].genColor.property("color").name()
            bendSketchColor = self.form[1].bendColor.property("color").name()
            intSketchColor = self.form[1].internalColor.property("color").name()
            processUnfoldSketches(shape, foldLines, norm, splitSketches, genSketchColor, bendSketchColor, intSketchColor)
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()
        Gui.Control.closeDialog()
        Gui.ActiveDocument.resetEdit()

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        Gui.Control.closeDialog()
        Gui.ActiveDocument.resetEdit()
        FreeCAD.ActiveDocument.recompute()

    def populateMdsList(self):
        sheetnames = SheetMetalKfactor.getSpreadSheetNames()
        self.form[0].availableMds.clear()

        self.form[0].availableMds.addItem("Please select")
        for mds in sheetnames:
            if mds.Label.startswith("material_"):
                self.form[0].availableMds.addItem(mds.Label)
        self.form[0].availableMds.addItem("Manual K-Factor")

        selMdsIndex = -1
        if self.object.materialSheet:
            selMdsIndex = self._getMdsIndex(self.object.materialSheet.Label)
        elif self.object.useManualKFactor:
            selMdsIndex = self.form[0].availableMds.count()-1

        if selMdsIndex >= 0:
            self.form[0].availableMds.setCurrentIndex(selMdsIndex)
        elif len(sheetnames) == 1:
            self.form[0].availableMds.setCurrentIndex(1)
        elif engineering_mode_enabled():
            self.form[0].availableMds.setCurrentIndex(0)
        elif len(sheetnames) == 0:
            self.form[0].availableMds.setCurrentIndex(1)
        
    def chkSketchChange(self):
        self.form[1].genColor.setEnabled(self.form[1].chkSketch.isChecked())
        self.form[1].chkSeparate.setEnabled(self.form[1].chkSketch.isChecked())
        enabled = self.form[1].chkSketch.isChecked() and self.form[1].chkSeparate.isChecked()
        self.form[1].bendColor.setEnabled(enabled)
        self.form[1].internalColor.setEnabled(enabled)

    def availableMdsChange(self):
        isManualK = self._isManualKSelected()
        self.form[0].kfactorAnsi.setEnabled(isManualK)
        self.form[0].kfactorDin.setEnabled(isManualK)
        self.form[0].kFactSpin.setEnabled(isManualK)
        self.object.useManualKFactor = isManualK
        if not isManualK:
            self.object.materialSheet = FreeCAD.ActiveDocument.getObjectsByLabel(
                self.form[0].availableMds.currentText()
            )[0]
        self.object.recompute()

    def toggleSelectionMode(self):
        if not self.SelModeActive:
            self.object.Visibility=False
            self.object.baseObject[0].Visibility=True
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(self.object.baseObject[0],self.object.baseObject[1])
            self.SelModeActive=True
            self.form[0].selectFaceButton.setText('Preview')
        else:
            sel = Gui.Selection.getSelectionEx()[0]
            self.object.baseObject = [ sel.Object, sel.SubElementNames[0] ]
            Gui.Selection.clearSelection()
            self.object.Document.recompute()
            self.object.Visibility=True
            self.SelModeActive=False
            self.form[0].selectFaceButton.setText('Select Face')
        
######## Commands ########


class SMUnfoldUnattendedCommandClass:
    """Unfold object"""

    def GetResources(self):
        icons_path = SheetMetalTools.icons_path
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_UnfoldUnattended.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Unattended Unfold"),
            "Accel": "U",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Flatten folded sheet metal object with default options\n"
                "1. Select flat face on sheetmetal shape.\n"
                "2. Change parameters from task Panel to create unfold Shape & Flatten drawing.",
            ),
        }

    def Activated(self):
        SMLogger.message(FreeCAD.Qt.translate("Logger", "Running unattended unfold..."))
        doc = FreeCAD.ActiveDocument
        sel = Gui.Selection.getSelectionEx()[0]
        doc.openTransaction("Unattended Unfold")
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Unfold")
        SMUnfold(obj)
        SMUnfoldVP(obj.ViewObject)
        obj.baseObject = [ sel.Object, sel.SubElementNames[0] ]
        pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
        obj.kFactorStandard = pg.GetString("kFactorStandard", "ansi")
        obj.ViewObject.Transparency = pg.GetInt("genObjTransparency", 50)
        obj.kfactor = pg.GetFloat("manualKFactor", KFACTOR)
        Gui.Selection.clearSelection()
        doc.recompute()
        dialog = SMUnfoldTaskPanel(obj)
        dialog.accept()
        return

    def IsActive(self):
        if (
            len(Gui.Selection.getSelection()) != 1
            or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
        ):
            return False
        selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]

        return isinstance(selFace.Surface, Part.Plane)


Gui.addCommand("SheetMetal_UnattendedUnfold", SMUnfoldUnattendedCommandClass())


class SMUnfoldCommandClass:
    """Unfold object"""

    def GetResources(self):
        icons_path = SheetMetalTools.icons_path
        # add translations path
        Gui.addLanguagePath(SheetMetalTools.language_path)
        Gui.updateLocale()
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_Unfold.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Unfold"),
            "Accel": "U",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Flatten folded sheet metal object.\n"
                "1. Select flat face on sheetmetal shape.\n"
                "2. Change parameters from task Panel to create unfold Shape & Flatten drawing.",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        sel = Gui.Selection.getSelectionEx()[0]
        doc.openTransaction("Unfold")
        obj = doc.addObject("Part::FeaturePython", "Unfold")
        SMUnfold(obj)
        SMUnfoldVP(obj.ViewObject)
        obj.baseObject = [ sel.Object, sel.SubElementNames[0] ]
        pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
        obj.kFactorStandard = pg.GetString("kFactorStandard", "ansi")
        obj.ViewObject.Transparency = pg.GetInt("genObjTransparency", 50)
        obj.kfactor = pg.GetFloat("manualKFactor", KFACTOR)
        Gui.Selection.clearSelection()
        doc.recompute()
        dialog = SMUnfoldTaskPanel(obj)
        Gui.Control.showDialog(dialog)

    def IsActive(self):
        if (
            len(Gui.Selection.getSelection()) != 1
            or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
        ):
            return False
        selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
        return isinstance(selFace.Surface, Part.Plane)

Gui.addCommand("SheetMetal_Unfold", SMUnfoldCommandClass())
