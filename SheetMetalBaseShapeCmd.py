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

import Part, FreeCAD, FreeCADGui, os
from PySide import QtGui, QtCore
from FreeCAD import Gui
from SheetMetalCmd import smBend, smAddLengthProperty, smAddBoolProperty, smAddEnumProperty
from SheetMetalLogger import SMLogger

modPath = os.path.dirname(__file__)
iconPath = os.path.join(modPath, "Resources", "icons")

mw = FreeCADGui.getMainWindow()

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

origin_location_types = ["-X,-Y", "-X,0", "-X,+Y", "0,-Y", "0,0", "0,+Y", "+X,-Y", "+X,0", "+X,+Y"]
base_shape_types = [
    FreeCAD.Qt.translate("SMBaseShape", "Flat", "Base shape"),
    FreeCAD.Qt.translate("SMBaseShape", "L-Shape", "Base shape"),
    FreeCAD.Qt.translate("SMBaseShape", "U-Shape", "Base shape"),
    FreeCAD.Qt.translate("SMBaseShape", "Tub", "Base shape"),
    FreeCAD.Qt.translate("SMBaseShape", "Hat", "Base shape"),
    FreeCAD.Qt.translate("SMBaseShape", "Box", "Base shape"),
]

##########################################################################################################
# Task
##########################################################################################################


class BaseShapeTaskPanel:
    def __init__(self):
        QtCore.QDir.addSearchPath('Icons', iconPath)
        path = f"{modPath}/BaseShapeOptions.ui"
        self.form = FreeCADGui.PySideUic.loadUi(path)
        self.formReady = False
        self.firstTime = True
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
        self.form.bFlangeWidthSpin.setEnabled(type in base_shape_types[4:6]) # Hat, Box
        self.form.bRadiusSpin.setEnabled(not type == base_shape_types[0]) # ! Flat
        self.form.bHeightSpin.setEnabled(not type == base_shape_types[0]) # ! Flat

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
        self.hasAxisCross = FreeCADGui.ActiveDocument.ActiveView.hasAxisCross()
        FreeCADGui.ActiveDocument.ActiveView.setAxisCross(True)

    def RevertAxisCross(self):
        FreeCADGui.ActiveDocument.ActiveView.setAxisCross(self.hasAxisCross)

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
        if self.firstTime  and self._stateToBool(self.form.chkNewBody.checkState()):
            body = FreeCAD.activeDocument().addObject('PartDesign::Body','Body')
            body.Label = 'Body'
            body.addObject(self.obj)
            FreeCADGui.ActiveDocument.ActiveView.setActiveObject('pdbody', body)
        doc.commitTransaction()
        FreeCADGui.Control.closeDialog()
        doc.recompute()
        self.RevertAxisCross()

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Control.closeDialog()
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
        self.form.chkNewBody.setVisible(self.firstTime)
        self.formReady = True


##########################################################################################################
# Object class and creation function
##########################################################################################################

def GetOriginShift(dimension, type, bendCompensation):
    type = type[0]
    if type == '+':
        return -dimension - bendCompensation
    if type == '0':
        return -dimension / 2.0
    return bendCompensation

def smCreateBaseShape(
    type: int,
    thickness: float,
    radius: float,
    width: float,
    length: float,
    height: float,
    flangeWidth: float,
    fillGaps: bool,
    origin: str,
):
    bendCompensation = thickness + radius
    height -= bendCompensation
    compx = 0
    compy = 0
    if type == 2:  # U-Shape
        numfolds = 2
        width -= 2.0 * bendCompensation
        compy = bendCompensation
    elif type in [3, 4, 5]:  # Tub, Hat, Box
        numfolds = 4
        width -= 2.0 * bendCompensation
        length -= 2.0 * bendCompensation
        compx = compy = bendCompensation
    elif type == 1:  # L-Shape
        numfolds = 1
        width -= bendCompensation
    else:
        numfolds = 0
    if type in [4, 5]:  # Hat, Box
        height -= bendCompensation
        flangeWidth -= radius
    if width < thickness: width = thickness
    if height < thickness: height = thickness
    if length < thickness: length = thickness
    if flangeWidth < thickness: flangeWidth = thickness
    originX, originY = origin.split(',')
    offsx = GetOriginShift(length, originX, compx)
    offsy = GetOriginShift(width, originY, compy)
    if type == 1 and originY == "+Y":
        offsy -= bendCompensation
    box = Part.makeBox(length, width, thickness, FreeCAD.Vector(offsx, offsy, 0))
    #box.translate(FreeCAD.Vector(offsx, offsy, 0))
    if numfolds == 0:
        return box
    faces = []
    for i in range(len(box.Faces)):
        v = box.Faces[i].normalAt(0,0)
        if (v.y > 0.5 or
            (v.y < -0.5 and numfolds > 1) or
            (v.x > 0.5 and numfolds > 2) or
            (v.x < -0.5 and numfolds > 3)):
            faces.append("Face" + str(i+1))

    shape, f = smBend(thickness, selFaceNames = faces, extLen = height, bendR = radius,
                      MainObject = box, automiter = fillGaps)
    if type in [4, 5]:  # Hat, Box
        faces = []
        invertBend = False
        if type == 4:  # Hat
            invertBend = True
        for i in range(len(shape.Faces)):
            v = shape.Faces[i].normalAt(0,0)
            z = shape.Faces[i].CenterOfGravity.z
            if v.z > 0.9999 and z > bendCompensation:
                faces.append("Face" + str(i+1))
        shape, f = smBend(thickness, selFaceNames = faces, extLen = flangeWidth,
                          bendR = radius, MainObject = shape, flipped = invertBend,
                          automiter = fillGaps)
    #SMLogger.message(str(faces))
    return shape

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
        return os.path.join( iconPath , 'SheetMetal_AddBaseShape.svg')

    def setEdit(self, vobj, mode):
        SMLogger.log(
            FreeCAD.Qt.translate("Logger", "Base shape edit mode: ") + str(mode)
        )
        if mode != 0:
            return None
            return super.setEdit(vobj, mode)
        taskd = BaseShapeTaskPanel()
        taskd.obj = vobj.Object
        taskd.firstTime = False
        taskd.update()
        #self.Object.ViewObject.Visibility=False
        Gui.Selection.clearSelection()
        FreeCAD.ActiveDocument.openTransaction("BaseShape")
        FreeCADGui.Control.showDialog(taskd)
        #Gui.ActiveDocument.resetEdit()
        return False

    def unsetEdit(self,vobj,mode):
        FreeCADGui.Control.closeDialog()
        self.Object.ViewObject.Visibility=True
        return False


class SMBaseShape:
    def __init__(self, obj):
        '''"Add a base sheetmetal shape" '''
        self._addVerifyProperties(obj)
        obj.Proxy = self

    def _addVerifyProperties(self, obj):
        smAddLengthProperty(
            obj,
            "thickness",
            FreeCAD.Qt.translate("SMBaseShape", "Thickness of sheetmetal", "Property"),
            1.0,
        )
        smAddLengthProperty(
            obj,
            "radius",
            FreeCAD.Qt.translate("SMBaseShape", "Bend Radius", "Property"),
            1.0,
        )
        smAddLengthProperty(
            obj,
            "width",
            FreeCAD.Qt.translate("SMBaseShape", "Shape width", "Property"),
            20.0,
        )
        smAddLengthProperty(
            obj,
            "length",
            FreeCAD.Qt.translate("SMBaseShape", "Shape length", "Property"),
            30.0,
        )
        smAddLengthProperty(
            obj,
            "height",
            FreeCAD.Qt.translate("SMBaseShape", "Shape height", "Property"),
            10.0,
        )
        smAddLengthProperty(
            obj,
            "flangeWidth",
            FreeCAD.Qt.translate("SMBaseShape", "Width of top flange", "Property"),
            5.0,
        )
        smAddEnumProperty(
            obj,
            "shapeType",
            FreeCAD.Qt.translate("SMBaseShape", "Base shape type", "Property"),
            base_shape_types,
            defval = base_shape_types[1],
        )
        smAddEnumProperty(
            obj,
            "originLoc",
            FreeCAD.Qt.translate("SMBaseShape", "Location of part origin", "Property"),
            origin_location_types,
            defval = "0,0"
        )
        smAddBoolProperty(
            obj,
            "fillGaps",
            FreeCAD.Qt.translate(
                "SMBaseShape", "Extend sides and flange to close all gaps", "Property"
            ),
            True,
        )

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver

    def execute(self, fp):
        self._addVerifyProperties(fp)
        s = smCreateBaseShape(
            type=base_shape_types.index(fp.shapeType),
            thickness=fp.thickness.Value,
            radius=fp.radius.Value,
            width=fp.width.Value,
            length=fp.length.Value,
            height=fp.height.Value,
            flangeWidth=fp.flangeWidth.Value,
            fillGaps=fp.fillGaps,
            origin=fp.originLoc,
        )

        fp.Shape = s


##########################################################################################################
# Command
##########################################################################################################


class SMBaseshapeCommandClass:
    """Open Base shape task"""

    def GetResources(self):
        # add translations path
        LanguagePath = os.path.join(modPath, "translations")
        Gui.addLanguagePath(LanguagePath)
        Gui.updateLocale()
        return {
            "Pixmap": os.path.join(
                iconPath, "SheetMetal_AddBaseShape.svg"
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
        doc.openTransaction("BaseShape")
        a = doc.addObject("PartDesign::FeaturePython","BaseShape")
        SMBaseShape(a)
        SMBaseShapeViewProviderFlat(a.ViewObject)
        doc.recompute()

        dialog = BaseShapeTaskPanel()
        dialog.obj = a
        dialog.firstTime = True
        dialog.update()
        FreeCADGui.Control.showDialog(dialog)

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


Gui.addCommand("SheetMetal_BaseShape", SMBaseshapeCommandClass())
