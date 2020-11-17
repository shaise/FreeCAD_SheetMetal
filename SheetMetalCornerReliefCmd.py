# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalCornerReliefCmd.py
#  
#  Copyright 2020 Jaise James <jaisekjames at gmail dot com>
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

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, FreeCADGui, Part, os, math
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

import SheetMetalBendSolid

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
 
def smthk(obj, foldface) :
  normal = foldface.normalAt(0,0)
  theVol = obj.Volume
  if theVol < 0.0001:
      SMError("Shape is not a real 3D-object or to small for a metal-sheet!")
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

def makeSketch(relieftype, size, ratio, cent, normal, addvector):
  # create wire for face creation
  if relieftype == "Circle" :
    circle = Part.makeCircle(size, cent, normal)
    sketch = Part.Wire(circle)
  else :
    diagonal_length = math.sqrt(size**2 + (ratio * size)**2)
    opposite_vector = normal.cross(addvector).normalize()
    pt1 = cent + addvector * diagonal_length / 2.0
    pt2 = cent + opposite_vector * diagonal_length / 2.0
    pt3 = cent + addvector * -diagonal_length / 2.0
    pt4 = cent + opposite_vector * -diagonal_length / 2.0
    rect = Part.makePolygon([pt1,pt2,pt3,pt4,pt1])
    sketch = Part.Wire(rect)
  #Part.show(sketch,'sketch')
  return sketch

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
  angle_tan = angle_start + bend_angle/6.0 # need to have the angle_tan before correcting the sign

  if bend_angle < 0.0:
    bend_angle = -bend_angle

  #print(math.degrees(bend_angle))
  return math.degrees(bend_angle)

def smCornerR(relieftype = "Circle", size = 3.0, ratio = 1.0, xoffset = 1.0, yoffset = 1.0, kfactor = 0.5, sketch = '', 
                            selVertexNames = '', MainObject = None):

  import BOPTools.SplitFeatures, BOPTools.JoinFeatures
  resultSolid = MainObject.Shape
  for selVertexName in selVertexNames:
    #vertex = selVertexName
    vertex = MainObject.Shape.getElement(selVertexName)
    facelist = MainObject.Shape.ancestorsOfType(vertex, Part.Face)
  
    #To get top face
    eList = []
    for face in facelist :
      eList.append((face.Area, face))
    largeface = max(eList)[1]
    #Part.show(largeface,"largeface")
  
    #To get top face edges
    Edgelist = largeface.ancestorsOfType(vertex, Part.Edge)
    Edgewire = Part.Wire(Edgelist)
    #Part.show(Edgewire,"Edgewire")
  
    #To get bend radius
    for cylface in facelist :
      if issubclass(type(cylface.Surface),Part.Cylinder) :
        bendR = cylface.Surface.Radius
        break

    #To get thk of sheet, top face normal, bend angle
    normal = largeface.normalAt(0,0)
    thk = smthk(resultSolid, largeface)
    #print(thk)
    bendA = bendAngle(cylface, vertex.Point)
    #print(bendA)
  
    #To arrive unfold Length
    unfoldLength = ( bendR + kfactor * thk ) * bendA * math.pi / 180.0
    neturalRadius =  ( bendR + kfactor * thk )
  
    #To get centre of sketch
    neturalEdges = Edgewire.makeOffset2D(unfoldLength/2.0, openResult = True, join = 2)
    #Part.show(neturalEdges,"neturalEdges")
    for offsetvertex in neturalEdges.Vertexes :
      Edgelist = neturalEdges.ancestorsOfType(offsetvertex, Part.Edge)
      #print(len(Edgelist))
  
      if len(Edgelist) > 1 :
        e1 = Edgelist[0].valueAt(Edgelist[0].LastParameter) - Edgelist[0].valueAt(Edgelist[0].FirstParameter)
        e2 = Edgelist[1].valueAt(Edgelist[1].LastParameter) - Edgelist[1].valueAt(Edgelist[1].FirstParameter)
        angle_rad = e1.getAngle(e2)
        if angle_rad > smEpsilon :
          break
   
    cent = offsetvertex.Point
    corner = vertex.Point
    addvector = cent - corner
    addvector.normalize()
    #print([cent, corner, addvector] )
    sLine = Part.makeLine(cent+ addvector * (unfoldLength+size), corner+ addvector * -(unfoldLength+size))
    #Part.show(sLine,"sLine")
  
    if relieftype != "Sketch" :
      sketch = makeSketch(relieftype, size, ratio, cent, normal, addvector)
      reliefFace = Part.Face(sketch)
    else :
      reliefFace = Part.Face(sketch.Shape.Wires[0])
    #Part.show(reliefFace,'reliefFace')
 
    # to get top face cut
    LcutFace = largeface.common(reliefFace) 
    #Part.show(LcutFace,'LcutFace')
    BcutFace = reliefFace.cut(LcutFace) 
    #Part.show(BcutFace,'BcutFace')   

    #To get bend solid face
    Bcutfaces = BOPTools.SplitAPI.slice(BcutFace, sLine.Edges, "Standard", 0.0)
    #Part.show(Bcutfaces,"Bcutfaces")
    neturalFaces = Edgewire.makeOffset2D(unfoldLength, fill = True, openResult = False, join = 2)
    #Part.show(neturalFaces,"neturalFaces")

    solidlist = []
    LcutSolid = LcutFace.extrude(normal * -thk)
    #Part.show(LcutSolid,'LcutSolid')
    solidlist.append(LcutSolid)
    flipped = False
    for Bdcutface in Bcutfaces.Faces :  
      BdcutFace = neturalFaces.common(Bdcutface)       
      #Part.show(BdcutFace,"BdcutFace")
      #bendFacelist.append(BdcutFace)

      #To get bend edge
      bendedge = Edgewire.common(Bdcutface).Edges[0]
      #Part.show(bendedge,"bendedge")

      #To get facedir
      toolFaces = bendedge.extrude(normal * -thk)
      #Part.show(toolFaces, "toolFaces")
      FaceDir = smCutFace(toolFaces.Faces[0], LcutSolid)
      #Part.show(cutFaceDir,"cutFaceDir")
      faceNormal = FaceDir.Faces[0].normalAt(0,0)
      #print(facenormal)

      pt1 = bendedge.Edges[0].valueAt(bendedge.Edges[0].FirstParameter)
      pt2 = bendedge.Edges[0].valueAt(bendedge.Edges[0].LastParameter) 
      revAxisV = pt2 - pt1
      revAxisV.normalize()
      #print(addvector)
      bendline = Part.makeLine(pt1 + revAxisV * size, pt2 + revAxisV * -size)
      #Part.show(bendline,"bendline")

      #To get revoling Axis & Point
      if not(flipped) :
        revAxisP = bendedge.valueAt(bendedge.FirstParameter) + normal * bendR
      else :
        revAxisP = bendedge.valueAt(bendedge.FirstParameter) - normal * (thk +  bendR)

      # To check bend line direction
      if (normal.cross(revAxisV).normalize() - faceNormal).Length > smEpsilon:
        revAxisV = revAxisV * -1
        #print(revAxisV)

      # To reverse bend line direction
      if flipped :
        revAxisV = revAxisV * -1
        #print(revAxisV)

      #To get bend solid
      bendsolid = SheetMetalBendSolid.BendSolid(BdcutFace.Faces[0], bendline, bendR, thk, neturalRadius, revAxisV, flipped)
      #Part.show(bendsolid,"bendsolid")
      solidlist.append(bendsolid)
      FlatFace = Bdcutface.cut(BdcutFace) 
      #Part.show(FlatFace,'FlatFace')
      FlatSolid = FlatFace.extrude(normal * -thk)
      #Part.show(FlatSolid,'FlatSolid')
      FlatSolid.translate(faceNormal * -unfoldLength)
      #Part.show(FlatSolid,"FlatSolid")
      FlatSolid.rotate(revAxisP, revAxisV, bendA)
      #Part.show(FlatSolid,"RFlatSolid")
      solidlist.append(FlatSolid)

    #To get relief Solid fused
    reliefSolid = solidlist[0].multiFuse(solidlist[1:])
    #Part.show(reliefSolid,"reliefSolid")    
    reliefSolid = reliefSolid.removeSplitter()    
    #Part.show(reliefSolid,"reliefSolid")
    resultSolid = resultSolid.cut(reliefSolid)
  return resultSolid

class SMCornerRelief:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()

    obj.addProperty("App::PropertyEnumeration", "ReliefType", "Parameters","Corner Relief Type").ReliefType = ["Circle", "Square", "Sketch"]    
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj[0].Object, selobj[0].SubElementNames)
    obj.addProperty("App::PropertyFloat","Size","Parameters","Size of Shape").Size = 3.0
    obj.addProperty("App::PropertyFloat","SizeRatio","Parameters","Size Ratio of Shape").SizeRatio = 1.0
    obj.addProperty("App::PropertyFloatConstraint","kfactor","Parameters","Netural Axis Position").kfactor = (0.5,0.0,1.0,0.01)      
    obj.addProperty("App::PropertyLink","Sketch","Parameters1","Corner Relief Sketch")
    obj.addProperty("App::PropertyFloat","XOffset","Parameters1","Gap from side one").XOffset = 1.0
    obj.addProperty("App::PropertyFloat","YOffset","Parameters1","Gap from side two").YOffset = 1.0
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''

    s = smCornerR(relieftype = fp.ReliefType, ratio = fp.SizeRatio, size = fp.Size, kfactor = fp.kfactor, xoffset = fp.XOffset, 
                    yoffset = fp.YOffset, sketch = fp.Sketch, selVertexNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s

    Gui.ActiveDocument.getObject(fp.baseObject[0].Name).Visibility = False
    if fp.Sketch :
      Gui.ActiveDocument.getObject(fp.Sketch.Name).Visibility = False

class SMCornerReliefVP:
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

  def __setstate__(self,state):
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
    return os.path.join( iconPath , 'AddCornerRelief.svg')

class SMCornerReliefPDVP:
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

  def __setstate__(self,state):
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
    return os.path.join( iconPath , 'AddCornerRelief.svg')

class AddCornerReliefCommandClass():
  """Add Corner Relief command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddCornerRelief.svg'), # the name of a svg file available in the resources
            'MenuText': QtCore.QT_TRANSLATE_NOOP('SheetMetal','Add Corner Relief'),
            'ToolTip' : QtCore.QT_TRANSLATE_NOOP('SheetMetal','2 Bend Corner Relief to metal sheet corner')}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("Corner Relief")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","CornerRelief")
      SMCornerRelief(a)
      SMCornerReliefVP(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","CornerRelief")
      SMCornerRelief(a)
      SMCornerReliefPDVP(a.ViewObject)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    for selVertex in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selVertex) != Part.Vertex :
        return False
    return True

Gui.addCommand('SMCornerRelief',AddCornerReliefCommandClass())

