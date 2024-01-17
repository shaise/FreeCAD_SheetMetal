# -*- coding: utf-8 -*-
##############################################################################
#
#  SketchOnSheetMetalCmd.py
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
##############################################################################

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, Part, os, math
import SheetMetalBaseCmd

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

# add translations path
LanguagePath = os.path.join( __dir__, 'translations')
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()

import SheetMetalBendSolid
from SheetMetalLogger import SMLogger, UnfoldException, BendException, TreeException

def smWarnDialog(msg):
    diag = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'Error in macro MessageBox', msg)
    diag.setWindowModality(QtCore.Qt.ApplicationModal)
    diag.exec_()

def smBelongToBody(item, body):
    if (body is None):
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False

def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0

def smIsOperationLegal(body, selobj):
    #FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True

def smFace(sel_item, obj) :
  # find face if Edge Selected
  if type(sel_item) == Part.Edge :
    Facelist = obj.ancestorsOfType(sel_item, Part.Face)
    if Facelist[0].Area > Facelist[1].Area :
      selFace = Facelist[0]
    else :
      selFace = Facelist[1]
  elif type(sel_item) == Part.Face :
    selFace = sel_item
  return selFace

def smthk(obj, foldface) :
  normal = foldface.normalAt(0,0)
  theVol = obj.Volume
  if theVol < 0.0001:
      SMLogger.error("Shape is not a real 3D-object or to small for a metal-sheet!")
  else:
      # Make a first estimate of the thickness
      estimated_thk = theVol/(obj.Area / 2.0)
#  p1 = foldface.CenterOfMass
  for v in foldface.Vertexes :
    p1 = v.Point
    p2 = p1 + estimated_thk * -1.5 * normal
    e1 = Part.makeLine(p1, p2)
    thkedge = obj.common(e1)
    thk = thkedge.Length
    if thk > smEpsilon :
      break
  return thk

def smCutFace(Face, obj) :
  # find face Modified During loop
  for face in obj.Faces :
    face_common = face.common(Face)
    if face_common.Faces :
      break
  return face

def smGetEdge(Face, obj) :
  # find face Modified During loop
  for edge in obj.Edges :
    face_common = edge.common(Face)
    if face_common.Edges :
      break
  return edge

def equal_angle(ang1, ang2, p=5):
  # compares two angles
  result = False
  if round(ang1 - ang2, p)==0:
    result = True
  if round((ang1-2.0*math.pi) - ang2, p)==0:
    result = True
  if round(ang1 - (ang2-2.0*math.pi), p)==0:
    result = True
  return result

def bendAngle(theFace, edge_vec) :
  #Start to investigate the angles at self.__Shape.Faces[face_idx].ParameterRange[0]
  #Part.show(theFace,"theFace")
  #valuelist =  theFace.ParameterRange
  #print(valuelist)
  angle_0 = theFace.ParameterRange[0]
  angle_1 = theFace.ParameterRange[1]

  # idea: identify the angle at edge_vec = P_edge.Vertexes[0].copy().Point
  # This will be = angle_start
  # calculate the tan_vec from valueAt
  edgeAngle, edgePar = theFace.Surface.parameter(edge_vec)
  #print('the angles: ', angle_0, ' ', angle_1, ' ', edgeAngle, ' ', edgeAngle - 2*math.pi)

  if equal_angle(angle_0, edgeAngle):
    angle_start = angle_0
    angle_end = angle_1
  else:
    angle_start = angle_1
    angle_end = angle_0

  bend_angle = angle_end - angle_start
#  angle_tan = angle_start + bend_angle/6.0 # need to have the angle_tan before correcting the sign

  if bend_angle < 0.0:
    bend_angle = -bend_angle

  #print(math.degrees(bend_angle))
  return math.degrees(bend_angle)

def smSketchOnSheetMetal(kfactor = 0.5, sketch = '', flipped = False, selFaceNames = '', MainObject = None):
  resultSolid = MainObject.Shape.copy()
  selElement = resultSolid.getElement(selFaceNames[0])
  LargeFace = smFace(selElement, resultSolid)
  sketch_face = Part.makeFace(sketch.Shape.Wires,"Part::FaceMakerBullseye")

  #To get thk of sheet, top face normal
  thk = smthk(resultSolid, LargeFace)
  #print(thk)

  #To get top face normal, flatsolid
  solidlist = []
  normal = LargeFace.normalAt(0,0)
  #To check face direction
  coeff = normal.dot(sketch_face.Faces[0].normalAt(0,0))
  if coeff < 0 :
    sketch_face.reverse()
  Flatface = sketch_face.common(LargeFace)
  BalanceFaces = sketch_face.cut(Flatface)
  #Part.show(BalanceFace,"BalanceFace")
  Flatsolid = Flatface.extrude(normal * -thk)
  #Part.show(Flatsolid,"Flatsolid")
  solidlist.append(Flatsolid)

  if BalanceFaces.Faces :
    for BalanceFace in BalanceFaces.Faces :
      #Part.show(BalanceFace,"BalanceFace")
      TopFace = LargeFace
      #Part.show(TopFace,"TopFace")
      #flipped = False
      while BalanceFace.Faces :
        BendEdge = smGetEdge(BalanceFace, TopFace)
        #Part.show(BendEdge,"BendEdge")
        facelist = resultSolid.ancestorsOfType(BendEdge, Part.Face)

        #To get bend radius, bend angle
        for cylface in facelist :
          if issubclass(type(cylface.Surface),Part.Cylinder) :
            break
        if not(issubclass(type(cylface.Surface),Part.Cylinder)) :
          break
        #Part.show(cylface,"cylface")
        for planeface in facelist :
          if issubclass(type(planeface.Surface),Part.Plane) :
            break
        #Part.show(planeface,"planeface")
        normal = planeface.normalAt(0,0)
        revAxisV = cylface.Surface.Axis
        revAxisP = cylface.Surface.Center
        bendA = bendAngle(cylface, revAxisP)
        #print([bendA, revAxisV, revAxisP, cylface.Orientation])

        #To check bend direction
        offsetface = cylface.makeOffsetShape(-thk, 0.0, fill = False)
        #Part.show(offsetface,"offsetface")
        if offsetface.Area < cylface.Area :
          bendR = cylface.Surface.Radius - thk
          flipped = True
        else :
          bendR = cylface.Surface.Radius
          flipped = False

        #To arrive unfold Length, neutralRadius
        unfoldLength = ( bendR + kfactor * thk ) * abs(bendA) * math.pi / 180.0
        neutralRadius =  ( bendR + kfactor * thk )
        #print([unfoldLength,neutralRadius])

        #To get faceNormal, bend face
        faceNormal = normal.cross(revAxisV).normalize()
        #print(faceNormal)
        if bendR < cylface.Surface.Radius :
          offsetSolid = cylface.makeOffsetShape(bendR/2.0, 0.0, fill = True)
        else:
          offsetSolid = cylface.makeOffsetShape(-bendR/2.0, 0.0, fill = True)
        #Part.show(offsetSolid,"offsetSolid")
        tool = BendEdge.copy()
        FaceArea = tool.extrude(faceNormal * -unfoldLength )
        #Part.show(FaceArea,"FaceArea")
        #Part.show(BalanceFace,"BalanceFace")
        SolidFace = offsetSolid.common(FaceArea)
        #Part.show(BendSolidFace,"BendSolidFace")
        if not(SolidFace.Faces):
          faceNormal = faceNormal * -1
          FaceArea = tool.extrude(faceNormal * -unfoldLength )
        BendSolidFace = BalanceFace.common(FaceArea)
        #Part.show(FaceArea,"FaceArea")
        #Part.show(BendSolidFace,"BendSolidFace")
        #print([bendR, bendA, revAxisV, revAxisP, normal, flipped, BendSolidFace.Faces[0].normalAt(0,0)])

        bendsolid = SheetMetalBendSolid.BendSolid(BendSolidFace.Faces[0], BendEdge, bendR, thk, neutralRadius, revAxisV, flipped)
        #Part.show(bendsolid,"bendsolid")
        solidlist.append(bendsolid)

        if flipped == True:
          bendA = -bendA
        if not(SolidFace.Faces):
          revAxisV = revAxisV * -1
        sketch_face = BalanceFace.cut(BendSolidFace)
        sketch_face.translate(faceNormal * unfoldLength)
        #Part.show(sketch_face,"sketch_face")
        sketch_face.rotate(revAxisP, -revAxisV, bendA)
        #Part.show(sketch_face,"Rsketch_face")
        TopFace = smCutFace(sketch_face, resultSolid)
        #Part.show(TopFace,"TopFace")

        #To get top face normal, flatsolid
        normal = TopFace.normalAt(0,0)
        Flatface = sketch_face.common(TopFace)
        BalanceFace = sketch_face.cut(Flatface)
        #Part.show(BalanceFace,"BalanceFace")
        Flatsolid = Flatface.extrude(normal * -thk)
        #Part.show(Flatsolid,"Flatsolid")
        solidlist.append(Flatsolid)

  #To get relief Solid fused
  if len(solidlist) > 1 :
    SMSolid = solidlist[0].multiFuse(solidlist[1:])
    #Part.show(SMSolid,"SMSolid")
    SMSolid = SMSolid.removeSplitter()
  else :
   SMSolid = solidlist[0]
  #Part.show(SMSolid,"SMSolid")
  resultSolid = resultSolid.cut(SMSolid)

  Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  Gui.ActiveDocument.getObject(sketch.Name).Visibility = False
  return resultSolid

class SMSketchOnSheet:
  def __init__(self, obj):
    '''"Add Sketch based cut On Sheet metal" '''
    selobj = Gui.Selection.getSelectionEx()

    _tip_ = FreeCAD.Qt.translate("App::Property","Base Object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",_tip_).baseObject = (selobj[0].Object, selobj[0].SubElementNames)
    _tip_ = FreeCAD.Qt.translate("App::Property","Sketch on Sheetmetal")
    obj.addProperty("App::PropertyLink","Sketch","Parameters",_tip_).Sketch = selobj[1].Object
    _tip_ = FreeCAD.Qt.translate("App::Property","Gap from Left Side")
    obj.addProperty("App::PropertyFloatConstraint","kfactor","Parameters",_tip_).kfactor = (0.5,0.0,1.0,0.01)
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''

    s = smSketchOnSheetMetal(kfactor = fp.kfactor, sketch = fp.Sketch, selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s

class SMSketchOnSheetVP:
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
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
  def dumps(self):
    return None

  def loads(self, state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"baseObject"):
      objs.append(self.Object.baseObject[0])
      objs.append(self.Object.Sketch)
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_SketchOnSheet.svg')

class SMSketchOnSheetPDVP:
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
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
  def dumps(self):
    return None

  def loads(self, state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"Sketch"):
      objs.append(self.Object.Sketch)
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_SketchOnSheet.svg')

class AddSketchOnSheetCommandClass():
  """Add Sketch On Sheet metal command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SheetMetal_SketchOnSheet.svg'), # the name of a svg file available in the resources
            'MenuText': FreeCAD.Qt.translate('SheetMetal','Sketch On Sheet metal'),
            'Accel': "M, S",
            'ToolTip' : FreeCAD.Qt.translate('SheetMetal',' Extruded cut from Sketch On Sheet metal faces\n'
            '1. Select a flat face on sheet metal and\n'
            '2. Select a sketch on same face to create sheetmetal extruded cut.\n'
            '3. Use Property editor to modify other parameters')}

  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    viewConf = SheetMetalBaseCmd.GetViewConfig(selobj)
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("SketchOnSheet")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","SketchOnSheet")
      SMSketchOnSheet(a)
      SMSketchOnSheetVP(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","SketchOnSheet")
      SMSketchOnSheet(a)
      SMSketchOnSheetPDVP(a.ViewObject)
      activeBody.addObject(a)
    SheetMetalBaseCmd.SetViewConfig(a, viewConf)
    doc.recompute()
    doc.commitTransaction()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 2 :
      return False
#    selobj = Gui.Selection.getSelection()[1]
#    if str(type(selobj)) != "<type 'Sketcher.SketchObject'>" :
#      return False
    return True

Gui.addCommand('SMSketchOnSheet',AddSketchOnSheetCommandClass())
