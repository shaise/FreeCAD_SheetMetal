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

import os
import Part
import FreeCAD
import importDXF
import importSVG
import SheetMetalKfactor
import SheetMetalTools
import SheetMetalUnfolder

from SheetMetalTools import SMLogger, UnfoldException
from engineering_mode import engineering_mode_enabled

translate = FreeCAD.Qt.translate

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = "sm1."


# self.pg.SetString("kFactorStandard", str(results["kFactorStandard"]))
# self.pg.SetFloat("manualKFactor", float(self.form.kFactSpin.value()))
# self.pg.SetBool("genSketch", results["genSketch"])

# self.pg.SetString("genColor", results["genSketchColor"])
# self.pg.SetString("bendColor", results["bendSketchColor"])
# self.pg.SetString("internalColor", results["intSketchColor"])
# self.pg.SetBool("separateSketches", results["separateSketches"])
# self.pg.SetBool("exportEn", self.form.chkExport.isChecked())
# self.pg.SetString("exportType", self._getExportType(True))


# list of properties to be saved as defaults
smUnfoldDefaultVars = [
    "KFactorStandard", 
    "UseManualKFactor",
    "UnfoldTransparency"
]
smUnfoldNonSavedDefaultVars = [
    "GenerateSketch",
    "SketchColor",
    "InternalColor",
    "BendLineColor"
]


GENSKETCHCOLOR = "#000080"
OUTLINESKETCHCOLOR = "#c00000"
BENDLINESKETCHCOLOR = "#ff5733"
KFACTOR = 0.40


##########################################################################################################
# Object class
##########################################################################################################

class SMUnfold:
    ''' Class object for the unfold command '''
    def __init__(self, obj, selobj, sel_elements):
        '''"Add wall or Wall with radius bend"'''
        SheetMetalTools.smAddProperty(
            obj,
            "App::PropertyLinkSub",
            "baseObject",
            translate( "App::Property", "Base Object" ),
            (selobj, sel_elements),
        )
        self._addProperties(obj)
        SheetMetalTools.taskRestoreDefaults(obj, smUnfoldDefaultVars)
        obj.Proxy = self

    def _addProperties(self, obj):
        SheetMetalTools.smAddProperty(
            obj,
            "App::PropertyFloatConstraint",
            "KFactor",
            translate( "App::Property", "Manual K-Factor value" ),
            (0.4, 0.0, 2.0, 0.01),
        )
        SheetMetalTools.smAddEnumProperty(
            obj,
            "KFactorStandard",
            translate( "App::Property", "K-Factor standard" ),
            ["ansi","din"],
            "ansi",
        )
        SheetMetalTools.smAddProperty(
            obj,
            "App::PropertyLink",
            "MaterialSheet",
            translate( "App::Property", "Material definition sheet" ),
            None,
        )
        SheetMetalTools.smAddBoolProperty(
            obj,
            "UseManualKFactor",
            translate("App::Property", 
                      "Enable manually defining K-Factor value, otherwise the lookup table is used"),
            False,
        )
        SheetMetalTools.smAddBoolProperty(
            obj,
            "GenerateSketch",
            translate("App::Property", 
                      "Generate unfold sketch"),
            False,
        )
        SheetMetalTools.smAddBoolProperty(
            obj,
            "SeparateSketchLayers",
            translate("App::Property", 
                      "Generate seperate unfold sketches for outline, innerlines and bend lines"),
            False,
        )
        SheetMetalTools.smAddIntProperty(
            obj,
            "UnfoldTransparency",
            translate("App::Property", "Unfold object transparency"),
            50
        )
        SheetMetalTools.smAddProperty(
            obj,
            "App::PropertyStringList",
            "UnfoldSketchs",
            translate("App::Property", "Generated sketchs"),
            None,
            "Hidden",
        )
        # setup non-saved properties
        self.GenerateSketch = False
        self.SketchColor = GENSKETCHCOLOR
        self.InternalColor = OUTLINESKETCHCOLOR
        self.BendLineColor = BENDLINESKETCHCOLOR
        SheetMetalTools.taskRestoreDefaults(self, smUnfoldNonSavedDefaultVars)

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver
        
    def onChanged(self, obj, prop):
        print("====>", obj, "/", prop)

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory"'''
        kFactorTable = {1: fp.KFactor}
        if fp.MaterialSheet and fp.UseManualKFactor:
            lookupTable = SheetMetalKfactor.KFactorLookupTable(fp.MaterialSheet)
            kFactorTable = lookupTable.k_factor_lookup
        # shape, foldComp, _norm, _name, _err_cd, _fSel, _obN = SheetMetalUnfolder.getUnfold(
        #     k_factor_lookup=kf_lookup,
        #     solid=fp.baseObject[0],
        #     facename=fp.baseObject[1][0],
        #     kFactorStandard=fp.KFactorStandard)
        for prop in fp.UnfoldSketchs:
            item = fp.Document.getObject(prop)
            if item is not None:
                print ("===>",item.FullName)
                fp.Document.removeObject(item.Name)

        unfoldResult = SheetMetalUnfolder.processUnfold(
            kFactorTable,
            obj=fp.baseObject[0],
            faceName=fp.baseObject[1][0],
            genSketch=fp.GenerateSketch,
            splitSketches=fp.SeparateSketchLayers,
            sketchColor=fp.Proxy.SketchColor,
            bendSketchColor=fp.Proxy.InternalColor,
            internalSketchColor=fp.Proxy.BendLineColor,
            transparency=fp.UnfoldTransparency,
            kFactorStandard=fp.KFactorStandard,
        )
     
        fp.Shape = unfoldResult[0]
        sketchList = []
        for sketch in unfoldResult[1:]:
            if sketch is not None:
                sketchList.append(sketch.Name)
        fp.UnfoldSketchs = sketchList



##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from FreeCAD import Gui
    from PySide import QtGui, QtCore

    mds_help_url = "https://github.com/shaise/FreeCAD_SheetMetal#material-definition-sheet"
    last_selected_mds = "none"


    ##########################################################################################################
    # View Provider
    ##########################################################################################################

    class SMUnfoldViewProvider(SheetMetalTools.SMViewProvider):
        ''' Part / Part WB style ViewProvider '''        
        def getIcon(self):
            return os.path.join(SheetMetalTools.icons_path, 'SheetMetal_AddBase.svg')
        
        def claimChildren(self):
            objs = []
            o = self.Object
            # for item in [o.UnfoldSketch, o.UnfoldSketchOutline, o.UnfoldSketchInternal, o.UnfoldSketchBends]:
            #     if item is not None:
            #         objs.append(item)
            return objs

        def getTaskPanel(self, obj):
            return SMUnfoldTaskPanel(obj)

    ##########################################################################################################
    # Task Panel
    ##########################################################################################################

    class SMUnfoldTaskPanel:
        ''' Task Panel for the unfold function '''
        def __init__(self, obj):
            QtCore.QDir.addSearchPath('Icons', SheetMetalTools.icons_path)
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("UnfoldOptions.ui")
            self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")

            SheetMetalTools.taskConnectSelectionSingle(
                self, self.form.pushFace, self.form.txtFace, obj, "baseObject", ["Face"])

            # self.referenceFace = FreeCADGui.Selection.getSelectionEx()[0].SubObjects[0]
            # self.facename = FreeCADGui.Selection.getSelectionEx()[0].SubElementNames[0]
            # self.object = FreeCADGui.Selection.getSelectionEx()[0].Object

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

        def getKFactorTable(self):
            result = None
            if self._isManualKSelected():
                result = {1: self.form.kFactSpin.value()}
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
                SheetMetalTools.smWarnDialog(msg)
            else:
                lookupTable = SheetMetalKfactor.KFactorLookupTable(
                    self.form.availableMds.currentText()
                )
                result = lookupTable.k_factor_lookup
            return result

        def setupUi(self):
            self.form.kfactorAnsi.setChecked(self.obj.KFactorStandard == "ansi")
            self.form.kfactorDin.setChecked(self.obj.KFactorStandard == "din")
            self.SketchColor = GENSKETCHCOLOR
            self.InternalColor = OUTLINESKETCHCOLOR
            self.BendLineColor = BENDLINESKETCHCOLOR
            SheetMetalTools.taskConnectColor(self, self.form.genColor, "SketchColor", customObj = self.obj.Proxy)
            SheetMetalTools.taskConnectColor(self, self.form.bendColor, "BendLineColor", customObj = self.obj.Proxy)
            SheetMetalTools.taskConnectColor(self, self.form.internalColor, "InternalColor", customObj = self.obj.Proxy)
            SheetMetalTools.taskConnectCheck(self, self.form.chkSketch, "GenerateSketch", self.chkSketchChange)
            SheetMetalTools.taskConnectCheck(self, self.form.chkSeparate, "SeparateSketchLayers", self.chkSketchChange)

            self.form.availableMds.currentIndexChanged.connect(self.availableMdsChacnge)

            self.form.transSpin.setValue(self.pg.GetInt("genObjTransparency", 50))
            self.form.kFactSpin.setValue(self.pg.GetFloat("manualKFactor", KFACTOR))

            self.form.chkSeparate.setEnabled(self.pg.GetBool("separateSketches", False))

            self.form.chkExport.setChecked(self.pg.GetBool("exportEn", False))
            if self.pg.GetString("exportType", "dxf") == "dxf":
                self.form.dxfExport.setChecked(True)
            else:
                self.form.svgExport.setChecked(True)

            self.populateMdsList()
            self.availableMdsChacnge()

            self.form.update()
            FreeCAD.ActiveDocument.openTransaction("Unfold")

        def accept(self):
            SheetMetalTools.taskAccept(self)
            SheetMetalTools.taskSaveDefaults(self.obj, smUnfoldDefaultVars)
            SheetMetalTools.taskSaveDefaults(self.obj.Proxy, smUnfoldNonSavedDefaultVars)
            # self._updateSelectedMds()
            # kFactorTable = self.getKFactorTable()
            # if kFactorTable is None:
            #     return
            # try:
            #     solid, faces = self.obj.baseObject
            #     proxy = self.obj.Proxy
            #     print(self.obj.UnfoldTransparency)
            #     result = SheetMetalUnfolder.processUnfold(
            #         kFactorTable,
            #         solid,
            #         faces[0],
            #         genSketch=self.form.chkSketch.isChecked(),
            #         splitSketches=self.form.chkSeparate.isChecked(),
            #         sketchColor=proxy.SketchColor,
            #         bendSketchColor=proxy.InternalColor,
            #         internalSketchColor=proxy.BendLineColor,
            #         transparency=self.obj.UnfoldTransparency,
            #         kFactorStandard=self.obj.KFactorStandard,
            #     )
            #     if result:
            #         self.doExport(result[1])

            #         FreeCAD.ActiveDocument.commitTransaction()
            #         Gui.ActiveDocument.resetEdit()
            #         Gui.Control.closeDialog()
            #         FreeCAD.ActiveDocument.recompute()
            #     else:
            #         FreeCAD.ActiveDocument.abortTransaction()
            #         Gui.Control.closeDialog()
            #         FreeCAD.ActiveDocument.recompute()

            # except UnfoldException:
            #     msg = (
            #         FreeCAD.Qt.translate(
            #             "QMessageBox",
            #             "Unfold is failing.\n"
            #             "Please try to select a different face to unfold your object\n\n"
            #             "If the opposite face also fails then switch Refine to false on feature ",
            #         )
            #         + Gui.Selection.getSelection()[0].Name
            #     )
            #     QtGui.QMessageBox.question(
            #         None,
            #         FreeCAD.Qt.translate("QMessageBox", "Warning"),
            #         msg,
            #         QtGui.QMessageBox.Ok,
            #     )

            # except Exception as e:
            #     raise e

        def reject(self):
            FreeCAD.ActiveDocument.abortTransaction()
            Gui.Control.closeDialog()
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

        def chkSketchChange(self, _value):
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

    ##########################################################################################################
    # Command
    ##########################################################################################################

    class SMUnfoldCommandClass:
        """Unfold object"""

        def GetResources(self):
            __dir__ = os.path.dirname(__file__)
            iconPath = os.path.join(__dir__, "Resources", "icons")
            # add translations path
            LanguagePath = os.path.join(__dir__, "translations")
            Gui.addLanguagePath(LanguagePath)
            Gui.updateLocale()
            return {
                "Pixmap": os.path.join(
                    iconPath, "SheetMetal_Unfold.svg"
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
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, "BaseBend", False)
            if newObj is None:
                return
            SMUnfold(newObj, selobj, sel.SubElementNames)
            SMUnfoldViewProvider(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(
                selobj, newObj, activeBody, SMUnfoldTaskPanel)
            return

            # try:
            #     taskd = SMUnfoldTaskPanel()
            # except ValueError as e:
            #     SMErrorBox(e.args[0])
            #     return

            # FreeCADGui.Control.showDialog(taskd)
            # return

        def IsActive(self):
            if (
                len(Gui.Selection.getSelection()) != 1
                or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
            ):
                return False
            selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
            return isinstance(selFace.Surface, Part.Plane)

    Gui.addCommand("SheetMetal_Unfold", SMUnfoldCommandClass())
