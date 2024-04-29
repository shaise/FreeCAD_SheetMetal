# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalBaseShapeCmd.py
#
#  Copyright 2023 Shai Seger <shaise at gmail dot com>
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

import FreeCAD, os, SheetMetalTools
from PySide import QtCore
from FreeCAD import Gui
from SheetMetalLogger import SMLogger
from SheetMetalBaseShape import SMBaseShape

icons_path = SheetMetalTools.icons_path
panels_path = SheetMetalTools.panels_path
language_path = SheetMetalTools.language_path

mw = Gui.getMainWindow()

base_shape_types = SMBaseShape.getBaseShapeTypes()
origin_location_types = SMBaseShape.getOriginLocationTypes()

##########################################################################################################
# Task
##########################################################################################################

class BaseShapeTaskPanel:
    def __init__(self):
        QtCore.QDir.addSearchPath('Icons', icons_path)
        path = os.path.join(panels_path, 'BaseShapeOptions.ui')
        self.form = Gui.PySideUic.loadUi(path)
        self.formReady = False
        self.ShowAxisCross()
        self.setupUi()


    def _boolToState(self, bool):
        return QtCore.Qt.Checked if bool else QtCore.Qt.Unchecked

    def _stateToBool(self, state):
        return True if state == QtCore.Qt.Checked else False

    def setupUi(self):
        #box = FreeCAD.ActiveDocument.addObject("Part::Box", "Box")
        #bind = Gui.ExpressionBinding(self.form.bHeightSpin).bind(box,"Length")
        #FreeCAD.ActiveDocument.openTransaction("BaseShape")
        self.form.bRadiusSpin.valueChanged.connect(self.spinValChanged)
        self.form.bThicknessSpin.valueChanged.connect(self.spinValChanged)
        self.form.bWidthSpin.valueChanged.connect(self.spinValChanged)
        self.form.bHeightSpin.valueChanged.connect(self.spinValChanged)
        self.form.bFlangeWidthSpin.valueChanged.connect(self.spinValChanged)
        self.form.bLengthSpin.valueChanged.connect(self.spinValChanged)
        self.form.shapeType.currentIndexChanged.connect(self.typeChanged)
        self.form.originLoc.currentIndexChanged.connect(self.spinValChanged)
        self.form.chkFillGaps.stateChanged.connect(self.checkChanged)
        self.form.update()

        #SMLogger.log(str(self.formReady) + " <2 \n")
    def updateEnableState(self):
        type = base_shape_types[self.form.shapeType.currentIndex()]
        self.form.bFlangeWidthSpin.setEnabled(type in ["Hat", "Box"])
        self.form.bRadiusSpin.setEnabled(not type == "Flat")
        self.form.bHeightSpin.setEnabled(not type == "Flat")

    def spinValChanged(self):
        if not self.formReady:
           return
        self.updateObj()
        self.obj.recompute()

    def typeChanged(self):
        self.updateEnableState()
        self.spinValChanged()

    def checkChanged(self):
        self.spinValChanged()

    def ShowAxisCross(self):
        self.hasAxisCross = Gui.ActiveDocument.ActiveView.hasAxisCross()
        Gui.ActiveDocument.ActiveView.setAxisCross(True)

    def RevertAxisCross(self):
        Gui.ActiveDocument.ActiveView.setAxisCross(self.hasAxisCross)

    def updateObj(self):
        #spin = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
        #SMLogger.log(str(self.form.bRadiusSpin.property('rawValue')))
        self.obj.radius = self.form.bRadiusSpin.property('value')
        self.obj.thickness = self.form.bThicknessSpin.property('value')
        self.obj.width = self.form.bWidthSpin.property('value')
        self.obj.height = self.form.bHeightSpin.property('value')
        self.obj.flangeWidth = self.form.bFlangeWidthSpin.property('value')
        self.obj.length = self.form.bLengthSpin.property('value')
        selected_type = self.form.shapeType.currentText()
        if selected_type not in base_shape_types:
            selected_type = base_shape_types[self.form.shapeType.currentIndex()]
        self.obj.shapeType = selected_type
        self.obj.originLoc = origin_location_types[self.form.originLoc.currentIndex()]
        self.obj.fillGaps = self._stateToBool(self.form.chkFillGaps.checkState())

    def accept(self):
        doc = FreeCAD.ActiveDocument
        self.updateObj()
        doc.commitTransaction()
        Gui.Control.closeDialog()
        doc.recompute()
        Gui.ActiveDocument.resetEdit()
        self.RevertAxisCross()


    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        Gui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()
        self.RevertAxisCross()

    def updateSpin(self, spin, property):
        Gui.ExpressionBinding(spin).bind(self.obj, property)
        spin.setProperty('value', getattr(self.obj, property))
        pass

    def update(self):
        self.updateSpin(self.form.bRadiusSpin, 'radius')
        self.updateSpin(self.form.bThicknessSpin, 'thickness')
        self.updateSpin(self.form.bWidthSpin, 'width')
        self.updateSpin(self.form.bHeightSpin, 'height')
        self.updateSpin(self.form.bFlangeWidthSpin, 'flangeWidth')
        self.updateSpin(self.form.bLengthSpin, 'length')
        self.form.shapeType.setCurrentText(self.obj.shapeType)
        self.form.originLoc.setCurrentIndex(origin_location_types.index(self.obj.originLoc))
        self.form.chkFillGaps.setCheckState(self._boolToState(self.obj.fillGaps))
        self.formReady = True


##########################################################################################################
# View Provider
##########################################################################################################

class SMBaseShapeViewProviderFlat:
    "A View provider that nests children objects under the created one"

    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def updateData(self, fp, prop):
        return

    def getDisplayModes(self,obj):
        modes=[]
        return modes

    def setDisplayMode(self,mode):
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
            self.Object = FreeCAD.ActiveDocument.getObject(state['ObjectName'])

    def claimChildren(self):
        return []

    def getIcon(self):
        return os.path.join( icons_path , 'SheetMetal_AddBaseShape.svg')

    def setEdit(self, vobj, mode):
        SMLogger.log(
            FreeCAD.Qt.translate("Logger", "Base shape edit mode: ") + str(mode)
        )
        if mode != 0:
            return None
            return super.setEdit(vobj, mode)
        taskd = BaseShapeTaskPanel()
        taskd.obj = vobj.Object
        taskd.update()
        #self.Object.ViewObject.Visibility=False
        Gui.Selection.clearSelection()
        FreeCAD.ActiveDocument.openTransaction("BaseShape")
        Gui.Control.showDialog(taskd)
        #Gui.ActiveDocument.resetEdit()
        return False

    def unsetEdit(self,vobj,mode):
        Gui.Control.closeDialog()
        self.Object.ViewObject.Visibility=True
        return False


##########################################################################################################
# Command
##########################################################################################################

class SMBaseshapeCommandClass:
    """Open Base shape task"""

    def GetResources(self):
        # add translations path
        Gui.addLanguagePath(language_path)
        Gui.updateLocale()
        return {
            "Pixmap": os.path.join(
                icons_path, "SheetMetal_AddBaseShape.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Add base shape"),
            "Accel": "H",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Add basic sheet metal object."
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        activeBody = None
        view = Gui.ActiveDocument.ActiveView
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        doc.openTransaction("BaseShape")
        a = doc.addObject("PartDesign::FeaturePython","BaseShape")
        SMBaseShape(a)
        SMBaseShapeViewProviderFlat(a.ViewObject)
        if not activeBody:
            activeBody = FreeCAD.activeDocument().addObject('PartDesign::Body','Body')
            Gui.ActiveDocument.ActiveView.setActiveObject('pdbody', activeBody)
        activeBody.addObject(a)
        doc.recompute()

        dialog = BaseShapeTaskPanel()
        dialog.obj = a
        dialog.update()
        Gui.Control.showDialog(dialog)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

Gui.addCommand("SheetMetal_BaseShape", SMBaseshapeCommandClass())
