from PySide.QtGui import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QRadioButton,
    QPushButton,
    QSpinBox,
    QComboBox,
)
from PySide import QtGui, QtCore
import os
import FreeCAD
import FreeCADGui
import re

modPath = os.path.dirname(__file__).replace("\\", "/")


genSketchColor = "#000080"
bendSketchColor = "#c00000"
intSketchColor = "#ff5733"
kfactor = 0.40


mw = FreeCADGui.getMainWindow()


class TaskPanel:
    def __init__(self):
        path = f"{modPath}/UnfoldOptions.ui"
        self.form = FreeCADGui.PySideUic.loadUi(path)
        self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")

        self.setupUi()

    def _find_objects(self, objs, _filter):
        res = []
        queue = list(objs)
        visited = set(objs)
        while queue:
            obj = queue.pop(0)
            r = _filter(obj)
            if r:
                res.append(obj)
                if r > 1:
                    break
            elif r < 0:
                break
            else:
                linked = obj.getLinkedObject()
                if linked not in visited:
                    visited.add(linked)
                    queue.append(linked)
            try:
                names = obj.getSubObjects()
            except Exception:
                names = []
            for name in names:
                sobj = obj.getSubObject(name, retType=1)
                if sobj not in visited:
                    visited.add(sobj)
                    queue.append(sobj)
        return res

    def onColor(self, btn):
        print("onColor")

        # color = QtGui.QColorDialog()
        # col = color.getColor()
        # print(color.currentColor())

        # c = QtGui.QColor(int(color[0]*255),int(color[1]*255),int(color[2]*255))
        # color = QtGui.QColorDialog.getColor()
        #color = QtGui.QColorDialog.getColor(QtGui.QColor(int(c[0]*255),int(c[1]*255),int(c[2]*255)))
        print(btn.getRgbF())

        

        # palette = dialog.palette()
        # palette.setColor(dialog.backgroundRole(), col)
        # dialog.setPalette(palette)

    def findObjectsByTypeRecursive(self, doc, tp):
        return self._find_objects(
            doc.Objects, lambda obj: obj and obj.isDerivedFrom(tp)
        )

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

        DinAnsi = "Din" if self.form.kfactorDin.isChecked() else "Ansi"
        exportType = "dxf" if self.form.dxfExportDxf.isChecked() else "svg"

        results = {
            "manKFactor": self.form.kFactSpin.value(),
            "exportType": exportType,
            "genObjTransparency": self.form.transSpin.value(),
            # "genSketchColor": self.form.genColor.color().name(),
            # "bendSketchColor": self.form.bendColor.color().name(),
            # "intSketchColor": self.form.internalColor.color().name(),
            "DinAnsi": DinAnsi,
        }

        self.pg.SetString("kFactorStandard", str(results["kFactorStandard"]))
        self.pg.SetString("manualKFactor", str(results["manKFactor"]))
        self.pg.SetBool("bendSketch", 0)
        self.pg.SetBool("genSketch", 1)

        # self.pg.SetString("bendColor",bendSketchColor)
        # self.pg.SetString("genColor",genSketchColor)
        # self.pg.SetString("intColor",intSketchColor)

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

        self.form.genColor.onChanged.connect(self.onColor)

        # self.form.genColor.setColor(pg.GetString("genColor", "#000080"))
        # self.form.bendColor.setColor(pg.GetString("bendColor", "#c00000"))
        # self.form.internalColor.setColor(pg.GetString("intColor", "#ff5733"))
        self._setData()
        self.form.update()

    def accept(self):
        print(self._getData())
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()



    # def setMds(self, mds_name):
    #     # in engineering_mode, user should not loose any data, so
    #     # manual k-fa.ctor is also saved upon "unfold" operation.
    #     advanced_mode = engineering_mode_enabled() or not using_manual_kFactor

    #     if mds_name is None or not advanced_mode:
    #         self.root_obj.Label = self.root_label
    #     else:
    #         self.root_obj.Label = "%s_%s" % (self.root_label, mds_name)
    #     self.material_sheet_name = mds_name

    def populateMdsList(self):

        material_sheet_regex_str = "material_([a-zA-Z0-9_\-\[\]\.]+)"
        material_sheet_regex = re.compile(material_sheet_regex_str)

        spreadsheets = self.findObjectsByTypeRecursive(
            FreeCAD.ActiveDocument, "Spreadsheet::Sheet"
        )
        availableMdsObjects = [
            o for o in spreadsheets if material_sheet_regex.match(o.Label)
        ]

        self.form.availableMds.clear()
        self.form.availableMds.addItem("None")
        for mds in availableMdsObjects:
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
