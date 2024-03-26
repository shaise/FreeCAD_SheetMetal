# -*- coding: utf-8 -*-
##############################################################################
#
#  UnfoldGUI.py
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
##############################################################################

from PySide import QtCore, QtGui
from SheetMetalLogger import SMLogger, UnfoldException
from engineering_mode import engineering_mode_enabled
import FreeCAD
import FreeCADGui
import SheetMetalKfactor
import importDXF
import importSVG
import os
import SheetMetalUnfolder as smu

modPath = os.path.dirname(__file__).replace("\\", "/")

GENSKETCHCOLOR = "#000080"
BENDSKETCHCOLOR = "#c00000"
INTSKETCHCOLOR = "#ff5733"
KFACTOR = 0.40

last_selected_mds = "none"
mds_help_url = "https://github.com/shaise/FreeCAD_SheetMetal#material-definition-sheet"

mw = FreeCADGui.getMainWindow()


class SMUnfoldTaskPanel:
    def __init__(self):
        path = f"{modPath}/UnfoldOptions.ui"
        self.form = FreeCADGui.PySideUic.loadUi(path)
        self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")

        # Technical Debt.
        # The command that gets us here is defined in SheetMetalUnfoldCmd.py.
        # It limits the selection to planar faces.
        # However, once the dialog is open, the user can change the selection
        # and select any kind of geometry.  This is wrong.

        # if it is desirable to allow user to change the selection with the
        # dialog open, then a selectiongate should be written to limit
        # what the user can select.
        # If we want to prevent changing selection, then something else has to
        # happen.
        # For now, we are setting the reference plane when the user activates
        # the command. Any change by the user is ignored.

        self.referenceFace = FreeCADGui.Selection.getSelectionEx()[0].SubObjects[0]
        self.facename = FreeCADGui.Selection.getSelectionEx()[0].SubElementNames[0]
        self.object = FreeCADGui.Selection.getSelectionEx()[0].Object

        # End Technical debt

        self.setupUi()

    def _boolToState(self, bool):
        return QtCore.Qt.Checked if bool else QtCore.Qt.Unchecked

    def _getExportType(self, typeonly=False):
        if not typeonly and not self.form.chkExport.isChecked():
            return None
        if self.form.svgExport.isChecked():
            return "svg"
        else:
            return "dxf"

    def _isManualKSelected(self):
        return self.form.availableMds.currentIndex() == (
            self.form.availableMds.count() - 1
        )

    def _isNoMdsSelected(self):
        return self.form.availableMds.currentIndex() == 0

    def _updateSelectedMds(self):
        global last_selected_mds
        last_selected_mds = self.form.availableMds.currentText()

    def _getLastSelectedMdsIndex(self):
        global last_selected_mds
        for i in range(self.form.availableMds.count()):
            if self.form.availableMds.itemText(i) == last_selected_mds:
                return i
        return -1

    def _getData(self):
        kFactorStandard = "din" if self.form.kfactorDin.isChecked() else "ansi"

        results = {
            "exportType": self._getExportType(),
            "genObjTransparency": self.form.transSpin.value(),
            "genSketchColor": self.form.genColor.property("color").name(),
            "bendSketchColor": self.form.bendColor.property("color").name(),
            "intSketchColor": self.form.internalColor.property("color").name(),
            "separateSketches": self.form.chkSeparate.isChecked(),
            "genSketch": self.form.chkSketch.isChecked(),
            "kFactorStandard": kFactorStandard,
        }

        if self._isManualKSelected():
            results["lookupTable"] = {1: self.form.kFactSpin.value()}
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
            lookupTable = SheetMetalKfactor.KFactorLookupTable(
                self.form.availableMds.currentText()
            )
            results["lookupTable"] = lookupTable.k_factor_lookup

        self.pg.SetString("kFactorStandard", str(results["kFactorStandard"]))
        self.pg.SetFloat("manualKFactor", float(self.form.kFactSpin.value()))
        self.pg.SetBool("genSketch", results["genSketch"])

        self.pg.SetString("genColor", results["genSketchColor"])
        self.pg.SetString("bendColor", results["bendSketchColor"])
        self.pg.SetString("internalColor", results["intSketchColor"])
        self.pg.SetBool("separateSketches", results["separateSketches"])
        self.pg.SetBool("exportEn", self.form.chkExport.isChecked())
        self.pg.SetString("exportType", self._getExportType(True))

        return results

    def setupUi(self):
        kFactorStandard = self.pg.GetString("kFactorStandard", "ansi")
        if kFactorStandard == "ansi":
            self.form.kfactorAnsi.setChecked(True)
        else:
            self.form.kfactorDin.setChecked(True)

        self.form.chkSketch.stateChanged.connect(self.chkSketchChange)
        self.form.chkSeparate.stateChanged.connect(self.chkSketchChange)
        self.form.availableMds.currentIndexChanged.connect(self.availableMdsChacnge)

        self.form.chkSeparate.setCheckState(
            self._boolToState(self.pg.GetBool("separateSketches"))
        )
        self.form.chkSketch.setCheckState(
            self._boolToState(self.pg.GetBool("genSketch"))
        )

        self.form.genColor.setProperty(
            "color", self.pg.GetString("genColor", GENSKETCHCOLOR)
        )
        self.form.bendColor.setProperty(
            "color", self.pg.GetString("bendColor", BENDSKETCHCOLOR)
        )
        self.form.internalColor.setProperty(
            "color", self.pg.GetString("internalColor", INTSKETCHCOLOR)
        )

        self.form.transSpin.setValue(self.pg.GetInt("genObjTransparency", 50))
        self.form.kFactSpin.setValue(self.pg.GetFloat("manualKFactor", KFACTOR))

        self.form.chkSeparate.setEnabled(self.pg.GetBool("separateSketches", False))

        self.form.chkExport.setCheckState(
            self._boolToState(self.pg.GetBool("exportEn", False))
        )
        if self.pg.GetString("exportType", "dxf") == "dxf":
            self.form.dxfExport.setChecked(True)
        else:
            self.form.svgExport.setChecked(True)

        self.chkSketchChange()
        self.populateMdsList()
        self.availableMdsChacnge()

        self.form.update()
        FreeCAD.ActiveDocument.openTransaction("Unfold")

    def accept(self):
        self._updateSelectedMds()
        params = self._getData()
        if params is None:
            return

        try:
            result = smu.processUnfold(
                params["lookupTable"],
                self.object,
                self.referenceFace,
                self.facename,
                genSketch=self.form.chkSketch.isChecked(),
                splitSketches=self.form.chkSeparate.isChecked(),
                sketchColor=params["genSketchColor"],
                bendSketchColor=params["bendSketchColor"],
                internalSketchColor=params["intSketchColor"],
                transparency=params["genObjTransparency"],
                kFactorStandard=params["kFactorStandard"],
            )
            if result:
                self.doExport(result[1])

                FreeCAD.ActiveDocument.commitTransaction()
                FreeCADGui.ActiveDocument.resetEdit()
                FreeCADGui.Control.closeDialog()
                FreeCAD.ActiveDocument.recompute()
            else:
                FreeCAD.ActiveDocument.abortTransaction()
                FreeCADGui.Control.closeDialog()
                FreeCAD.ActiveDocument.recompute()

        except UnfoldException:
            msg = (
                FreeCAD.Qt.translate(
                    "QMessageBox",
                    "Unfold is failing.\n"
                    "Please try to select a different face to unfold your object\n\n"
                    "If the opposite face also fails then switch Refine to false on feature ",
                )
                + FreeCADGui.Selection.getSelection()[0].Name
            )
            QtGui.QMessageBox.question(
                None,
                FreeCAD.Qt.translate("QMessageBox", "Warning"),
                msg,
                QtGui.QMessageBox.Ok,
            )

        except Exception as e:
            raise e

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def doExport(self, obj):
        # Not sure we should be doing export in this dialog but if we want to,
        # it should be handled here and not in the unfold function.

        # This implementation of export is limited because it doesn't export
        # split sketches.  More reason to potentially remove it entirely and
        # let the user use the standard export functions

        if obj is None:
            return

        if self._getExportType() is None:
            return

        __objs__ = []
        __objs__.append(obj)
        filename = f"{FreeCAD.ActiveDocument.FileName[0:-6]}-{obj.Name}.{self._getExportType()}"
        print("Exporting to " + filename)

        if self._getExportType() == "dxf":
            importDXF.export(__objs__, filename)
        else:
            importSVG.export(__objs__, filename)
        del __objs__

    def populateMdsList(self):
        sheetnames = SheetMetalKfactor.getSpreadSheetNames()
        self.form.availableMds.clear()

        self.form.availableMds.addItem("Please select")
        for mds in sheetnames:
            if mds.Label.startswith("material_"):
                self.form.availableMds.addItem(mds.Label)
        self.form.availableMds.addItem("Manual K-Factor")

        selMdsIndex = self._getLastSelectedMdsIndex()

        if selMdsIndex >= 0:
            self.form.availableMds.setCurrentIndex(selMdsIndex)
        elif len(sheetnames) == 1:
            self.form.availableMds.setCurrentIndex(1)
        elif engineering_mode_enabled():
            self.form.availableMds.setCurrentIndex(0)
        elif len(sheetnames) == 0:
            self.form.availableMds.setCurrentIndex(1)

    def chkSketchChange(self):
        self.form.chkSeparate.setEnabled(self.form.chkSketch.isChecked())
        if self.form.chkSketch.isChecked():
            self.form.dxfExport.show()
            self.form.svgExport.show()
            self.form.genColor.setEnabled(True)
        else:
            self.form.dxfExport.hide()
            self.form.svgExport.hide()
            self.form.genColor.setEnabled(False)

        enabled = self.form.chkSketch.isChecked() and self.form.chkSeparate.isChecked()
        self.form.bendColor.setEnabled(enabled)
        self.form.internalColor.setEnabled(enabled)

    def availableMdsChacnge(self):
        isManualK = self._isManualKSelected()
        self.form.kfactorAnsi.setEnabled(isManualK)
        self.form.kfactorDin.setEnabled(isManualK)
        self.form.kFactSpin.setEnabled(isManualK)
