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

import FreeCAD, Part, os, SheetMetalTools
from SheetMetalCmd import smBend

icons_path = SheetMetalTools.icons_path
panels_path = SheetMetalTools.panels_path
language_path = SheetMetalTools.language_path

base_shape_types = ["Flat", "L-Shape", "U-Shape", "Tub", "Hat", "Box"]
origin_location_types = ["-X,-Y", "-X,0", "-X,+Y", "0,-Y", "0,0", "0,+Y", "+X,-Y", "+X,0", "+X,+Y"]
origin_location_buttons = ["BL", "CL", "TL", "BC", "CC", "TC", "BR", "CR", "TR"]

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'


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

def smCreateBaseShape(type, thickness, radius, width, length, height, flangeWidth, fillGaps, origin):
    bendCompensation = thickness + radius
    height -= bendCompensation
    compx = 0
    compy = 0
    if type == "U-Shape":
        numfolds = 2
        width -= 2.0 * bendCompensation
        compy = bendCompensation
    elif type in ["Tub", "Hat", "Box"]:
        numfolds = 4
        width -= 2.0 * bendCompensation
        length -= 2.0 * bendCompensation
        compx = compy = bendCompensation
    elif type == "L-Shape":
        numfolds = 1
        width -= bendCompensation
    else:
        numfolds = 0
    if type in ["Hat", "Box"]:
        height -= bendCompensation
        flangeWidth -= radius
    if width < thickness: width = thickness
    if height < thickness: height = thickness
    if length < thickness: length = thickness
    if flangeWidth < thickness: flangeWidth = thickness
    originX, originY = origin.split(',')
    offsx = GetOriginShift(length, originX, compx)
    offsy = GetOriginShift(width, originY, compy)
    if type == "L-Shape" and originY == "+Y":
        offsy -= bendCompensation
    box = Part.makeBox(length, width, thickness, FreeCAD.Vector(offsx, offsy, 0))
    #box.translate(FreeCAD.Vector(offsx, offsy, 0))
    if numfolds == 0:
        return box
    faces = []
    for i, face in enumerate(box.Faces):
        v = face.normalAt(0,0)
        if (v.y > 0.5 or
            (v.y < -0.5 and numfolds > 1) or
            (v.x > 0.5 and numfolds > 2) or
            (v.x < -0.5 and numfolds > 3)):
            faces.append("Face" + str(i+1))

    shape, _f = smBend(thickness, selFaceNames = faces, extLen = height, bendR = radius,
                      MainObject = box, automiter = fillGaps, maxExtendGap = 999999)
    if type in ["Hat", "Box"]:
        faces = []
        invertBend = False
        if type == "Hat": 
            invertBend = True
        for i, face in enumerate(shape.Faces):
            v = face.normalAt(0,0)
            z = face.CenterOfGravity.z
            if v.z > 0.9999 and z > bendCompensation:
                faces.append("Face" + str(i+1))
        shape, _f = smBend(thickness, selFaceNames = faces, extLen = flangeWidth,
                          bendR = radius, MainObject = shape, flipped = invertBend,
                          automiter = fillGaps)
    #SMLogger.message(str(faces))
    return shape


class SMBaseShape:
    def __init__(self, obj):
        '''"Add a base sheetmetal shape" '''
        self._addVerifyProperties(obj)
        obj.Proxy = self

    def _addVerifyProperties(self, obj):
        SheetMetalTools.smAddLengthProperty(
            obj,
            "thickness",
            FreeCAD.Qt.translate("SMBaseShape", "Thickness of sheetmetal", "Property"),
            1.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "radius",
            FreeCAD.Qt.translate("SMBaseShape", "Bend Radius", "Property"),
            1.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "width",
            FreeCAD.Qt.translate("SMBaseShape", "Shape width", "Property"),
            20.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "length",
            FreeCAD.Qt.translate("SMBaseShape", "Shape length", "Property"),
            30.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "height",
            FreeCAD.Qt.translate("SMBaseShape", "Shape height", "Property"),
            10.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "flangeWidth",
            FreeCAD.Qt.translate("SMBaseShape", "Width of top flange", "Property"),
            5.0,
        )
        SheetMetalTools.smAddEnumProperty(
            obj,
            "shapeType",
            FreeCAD.Qt.translate("SMBaseShape", "Base shape type", "Property"),
            base_shape_types,
            defval = "L-Shape"
        )
        SheetMetalTools.smAddEnumProperty(
            obj,
            "originLoc",
            FreeCAD.Qt.translate("SMBaseShape", "Location of part origin", "Property"),
            origin_location_types,
            defval = "0,0"
        )
        SheetMetalTools.smAddBoolProperty(
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

    def onChanged(self, fp, prop):
        if prop == "shapeType":
            flat = fp.shapeType == "Flat"
            hat_box = fp.shapeType in ["Hat", "Box"]
            fp.setEditorMode("radius", flat)
            fp.setEditorMode("height", flat)
            fp.setEditorMode("flangeWidth", not hat_box)

    def execute(self, fp):
        self._addVerifyProperties(fp)
        s = smCreateBaseShape(type = fp.shapeType, thickness = fp.thickness.Value,
                              radius = fp.radius.Value, width = fp.width.Value,
                              length = fp.length.Value, height = fp.height.Value,
                              flangeWidth = fp.flangeWidth.Value, fillGaps = fp.fillGaps,
                              origin = fp.originLoc)

        fp.Shape = s

    def getBaseShapeTypes(self):
        return base_shape_types
    
    def getOriginLocationTypes(self):
        return origin_location_types

##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from PySide import QtCore, QtGui
    from FreeCAD import Gui
    from SheetMetalLogger import SMLogger

    mw = Gui.getMainWindow()

    ##########################################################################################################
    # Task
    ##########################################################################################################

    class BaseShapeTaskPanel:
        ''' Task Panel for Base Shape sheetmetal command '''
        def __init__(self, baseObj):
            self.obj = baseObj
            QtCore.QDir.addSearchPath('Icons', icons_path)
            path = os.path.join(panels_path, 'BaseShapeOptions.ui')
            self.form = Gui.PySideUic.loadUi(path)
            self.formReady = False
            self.firstTime = False
            self.selOrigButton = None
            self.spinPairs = []
            self.ShowAxisCross()
            self.setupUi()


        def _boolToState(self, bool):
            return QtCore.Qt.Checked if bool else QtCore.Qt.Unchecked

        def _stateToBool(self, state):
            return True if state == QtCore.Qt.Checked else False

        def setupUi(self):
            SheetMetalTools.taskConnectSpin(self, self.form.bRadiusSpin, "radius")
            SheetMetalTools.taskConnectSpin(self, self.form.bThicknessSpin, "thickness")
            SheetMetalTools.taskConnectSpin(self, self.form.bWidthSpin, "width")
            SheetMetalTools.taskConnectSpin(self, self.form.bHeightSpin, "height")
            SheetMetalTools.taskConnectSpin(self, self.form.bFlangeWidthSpin, "flangeWidth")
            SheetMetalTools.taskConnectSpin(self, self.form.bLengthSpin, "length")

            self.form.shapeType.currentIndexChanged.connect(self.typeChanged)
            self.form.chkFillGaps.stateChanged.connect(self.checkChanged)
            for origloc in origin_location_buttons:
                buttname = 'push' + origloc
                butt = self.form.findChild(QtGui.QPushButton, buttname)
                butt.pressed.connect(lambda b = butt: self.origButtPressed(b))
            self.form.update()

            #SMLogger.log(str(self.formReady) + " <2 \n")
        def updateEnableState(self):
            shapeType = base_shape_types[self.form.shapeType.currentIndex()]
            self.form.bFlangeWidthSpin.setEnabled(shapeType in ["Hat", "Box"])
            self.form.bRadiusSpin.setEnabled(not shapeType == "Flat")
            self.form.bHeightSpin.setEnabled(not shapeType == "Flat")

        def buttonToOriginType(self, butt):
            if butt is None:
                name = 'pushCC'
            else:
                name = butt.objectName()
            return origin_location_types[origin_location_buttons.index(name[-2:])]
        
        def originTypeToButton(self, type):
            name = "push" + origin_location_buttons[origin_location_types.index(type)]
            return self.form.findChild(QtGui.QPushButton, name)
        
        def setSelectedOrigButton(self, butt):
            if self.selOrigButton is not None:
                self.selOrigButton.setIcon(QtGui.QIcon())
            if butt is not None:
                butt.setIcon(QtGui.QIcon('Icons:BaseShape_Sel.svg'))
            self.selOrigButton = butt

        def spinValChanged(self):
            if not self.formReady:
                return
            self.updateObj()
            self.obj.recompute()

        def typeChanged(self):
            self.updateEnableState()
            self.spinValChanged()

        def origButtPressed(self, butt):
            # print(butt.objectName())
            self.setSelectedOrigButton(butt)
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
            for formvar, objvar in self.spinPairs:
                setattr(self.obj, objvar, formvar.property("value"))
            
            selected_type = self.form.shapeType.currentText()
            if selected_type not in base_shape_types:
                selected_type = base_shape_types[self.form.shapeType.currentIndex()]
            self.obj.shapeType = selected_type
            self.obj.originLoc = self.buttonToOriginType(self.selOrigButton)
            self.obj.fillGaps = self._stateToBool(self.form.chkFillGaps.checkState())

        def accept(self):
            doc = FreeCAD.ActiveDocument
            self.updateObj()
            if self.firstTime  and self._stateToBool(self.form.chkNewBody.checkState()):
                body = FreeCAD.activeDocument().addObject('PartDesign::Body','Body')
                body.Label = 'Body'
                body.addObject(self.obj)
                Gui.ActiveDocument.ActiveView.setActiveObject('pdbody', body)
                self.firstTime = False
            doc.commitTransaction()
            Gui.Control.closeDialog()
            doc.recompute()
            Gui.ActiveDocument.resetEdit()
            self.RevertAxisCross()


        def reject(self):
            FreeCAD.ActiveDocument.abortTransaction()
            Gui.Control.closeDialog()
            FreeCAD.ActiveDocument.recompute()
            Gui.ActiveDocument.resetEdit()
            self.RevertAxisCross()

        def updateSpin(self, spin, property):
            Gui.ExpressionBinding(spin).bind(self.obj, property)
            spin.setProperty('value', getattr(self.obj, property))

        def update(self):
            self.form.shapeType.setCurrentText(self.obj.shapeType)
            self.setSelectedOrigButton(self.originTypeToButton(self.obj.originLoc))
            self.form.chkFillGaps.setCheckState(self._boolToState(self.obj.fillGaps))
            self.form.chkNewBody.setVisible(self.firstTime)
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
            taskd = BaseShapeTaskPanel(vobj.Object)
            taskd.firstTime = False
            taskd.update()
            #self.Object.ViewObject.Visibility=False
            Gui.Selection.clearSelection()
            FreeCAD.ActiveDocument.openTransaction("BaseShape")
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, vobj, mode):
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
            doc.openTransaction("BaseShape")
            a = doc.addObject("PartDesign::FeaturePython","BaseShape")
            SMBaseShape(a)
            SMBaseShapeViewProviderFlat(a.ViewObject)
            doc.recompute()
            dialog = BaseShapeTaskPanel(a)
            dialog.firstTime = True
            dialog.update()
            Gui.Control.showDialog(dialog)

        def IsActive(self):
            return FreeCAD.ActiveDocument is not None

    Gui.addCommand("SheetMetal_BaseShape", SMBaseshapeCommandClass())
