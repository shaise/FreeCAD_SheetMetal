from PySide import QtCore
import os
import FreeCAD
import FreeCADGui
import SheetMetalKfactor
from engineering_mode import engineering_mode_enabled

modPath = os.path.dirname(__file__).replace("\\", "/")

GENSKETCHCOLOR = "#000080"
BENDSKETCHCOLOR = "#c00000"
INTSKETCHCOLOR = "#ff5733"
KFACTOR = 0.40

mw = FreeCADGui.getMainWindow()


class TaskPanel:
    def __init__(self):
        path = f"{modPath}/UnfoldOptions.ui"
        self.form = FreeCADGui.PySideUic.loadUi(path)
        self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")

        self.setupUi()

    def updateData(self):
        pass

    def _boolToState(self, bool):
        if bool:
            return QtCore.Qt.Checked
        else:
            return QtCore.Qt.Unchecked

    def _setData(self):
        self.updateKfactorStandard()
        self.chkSketchChange()
        self.populateMdsList()

    def _getData(self):

        kFactorStandard = "Din" if self.form.kfactorDin.isChecked() else "Ansi"

        if self.form.dxfExport.isChecked():
            exportType = "dxf"

        elif self.form.svgExport.isChecked():
            exportType = "svg"
        else:
            exportType = None

        results = {
            "manKFactor": self.form.kFactSpin.value(),
            "exportType": exportType,
            "genObjTransparency": self.form.transSpin.value(),
            "genSketchColor": self.form.genColor.property("color").name(),
            "bendSketchColor": self.form.bendColor.property("color").name(),
            "intSketchColor": self.form.internalColor.property("color").name(),
            "kFactorStandard": kFactorStandard,
        }

        self.pg.SetString("kFactorStandard", str(results["kFactorStandard"]))
        self.pg.SetString("manualKFactor", str(results["manKFactor"]))
        self.pg.SetBool("bendSketch", 0)
        self.pg.SetBool("genSketch", 1)

        self.pg.SetString("genColor", results["genSketchColor"])
        self.pg.SetString("bendColor", results["bendSketchColor"])
        self.pg.SetString("internalColor", results["intSketchColor"])
        self.pg.SetBool("separateSketches", self.form.chkSeparate.isChecked())

        print(results)

        return results

    def setupUi(self):

        self.form.kfactorAnsi.setChecked(True)
        self.form.dxfExport.setChecked(True)

        self.form.chkSketch.stateChanged.connect(self.chkSketchChange)
        self.form.chkSeparate.stateChanged.connect(self.chkSketchChange)
        # self.form.availableMds.currentIndexChanged.connect(self.mdsChanged)

        self.form.chkSeparate.setCheckState(
            self._boolToState(self.pg.GetBool("bendSketch"))
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

        self._setData()
        self.form.update()

    def accept(self):
        self._getData()

        FreeCAD.ActiveDocument.commitTransaction()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def populateMdsList(self):

        sheetnames = SheetMetalKfactor.getSpreadSheetNames()

        self.form.availableMds.clear()

        if engineering_mode_enabled():
            self.form.availableMds.addItem("None")
        else:
            self.form.availableMds.addItem("Manual K-Factor")

        for mds in sheetnames:
            self.form.availableMds.addItem(mds.Label)

        self.form.availableMds.setCurrentIndex(0)

    def updateKfactorStandard(self, transient_std=None):
        global kFactor
        if transient_std is None:
            # Use any previously saved the K-factor standard if available.
            # (note: this will be ignored while using material definition sheet.)
            kFactorStandard = self.pg.GetString("kFactorStandard")
        else:
            kFactorStandard = transient_std

        self.form.kfactorAnsi.setChecked(kFactorStandard == "ansi")
        self.form.kfactorDin.setChecked(kFactorStandard == "din")

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
