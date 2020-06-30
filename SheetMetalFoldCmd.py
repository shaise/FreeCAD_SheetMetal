# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalFoldCmd.py
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
###################################################################################

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, FreeCADGui, Part, os, math
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

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
  p1 = foldface.Vertexes[0].Point
  p2 = p1 + estimated_thk * -1.5 * normal
  e1 = Part.makeLine(p1, p2)
  thkedge = obj.common(e1)
  thk = thkedge.Length
  return thk

def smCutFace(Face, obj) :
  # find face Modified During loop
  for face in obj.Faces :
    face_common = face.common(Face)
    if face_common.Faces :
      break
  return face

def getPointOnCylinder(zeroVert, poi, Radius, circent, axis, zeroVertNormal):
    dist = zeroVert.distanceToPlane(poi, zeroVertNormal)
    poi1 = poi.projectToPlane(zeroVert, zeroVertNormal)
    angle = dist / Radius
    axis = axis * -1
    #print([dist, angle])
    vec = poi1 - circent
    rVec = vec * math.cos(angle) + axis * ( axis.dot(vec)) * (1 - math.cos(angle)) + vec.cross(axis) * math.sin(angle)
    Point = circent + rVec
    #print([rVec,Point])
    return Point

def WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal):
    poles = bspline.getPoles()
    newpoles = []
    for poi in poles:
        bPoint = getPointOnCylinder(zeroVert, poi, Radius, cent, axis, zeroVertNormal)
        newpoles.append(bPoint)
    newbspline = bspline
    newbspline.buildFromPolesMultsKnots(newpoles, bspline.getMultiplicities(),
      bspline.getKnots(), bspline.isPeriodic(), bspline.Degree, bspline.getWeights())
    return newbspline.toShape()

def WrapFace(Face, Radius, axis, normal, zeroVert, cent, zeroVertNormal):
    circent = cent
    Edges = []
    for e in Face.Edges:
        #print(type(e.Curve))
        if isinstance(e.Curve, (Part.Circle, Part.ArcOfCircle)) : 
            #bspline = gg.Curve.toBSpline()
            poles = e.discretize(Number=50)
            bspline=Part.BSplineCurve()
            bspline.interpolate(poles)
            #bs = bspline.toShape()
            #Part.show(bs,"bspline")            
            Edges.append(WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal))

        elif isinstance(e.Curve, Part.BSplineCurve) : 
            Edges.append(WrapBSpline(e.Curve, Radius, zeroVert, cent, axis, zeroVertNormal))

        elif isinstance(e.Curve, Part.Line) :
            sp = e.valueAt(e.FirstParameter)
            ep = e.valueAt(e.LastParameter)
            dist1 = abs(sp.distanceToPlane(cent, normal))
            dist2 = abs(ep.distanceToPlane(cent, normal))
            #print(dist1,dist2)
            linenormal = ep - sp
            mp = sp + linenormal / 2.0
            linenormal.normalize()
            #print(linenormal.dot(axis))
            #print(linenormal.dot(normal))
            if  linenormal.dot(axis) == 0.0 and (dist2 - dist1) == 0.0:
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, mp, Radius, cent, axis, zeroVertNormal)
                Point3 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                arc = Part.Arc(Point1,Point2,Point3)
                Edges.append(arc.toShape())
            elif linenormal.dot(axis) == 1.0  or linenormal.dot(axis) == -1.0 :
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                #print([Point1,Point2])
                Edges.append(Part.makeLine(Point1, Point2))
            elif linenormal.dot(normal) == 1.0  or linenormal.dot(normal) == -1.0 :
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                #print([Point1,Point2])
                Edges.append(Part.makeLine(Point1, Point2))
            else :
                poles = e.discretize(Number=50)
                #print(poles)
                bspline=Part.BSplineCurve()
                bspline.interpolate(poles, PeriodicFlag=False)
                #bs = bspline.toShape()
                #Part.show(bs,"bspline")    
                #bspline = disgg.toBSpline()
                Edges.append(WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal))
    return Edges

def BendSolid(Solid, SelFace, SelEdge, BendR, thk, neturalRadius, Axis, flipped):
    normal = SelFace.normalAt(0,0)
    zeroVert = SelEdge.Vertexes[0].Point
    if not(flipped) :
        cent = zeroVert + normal * BendR
        zeroVertNormal = normal.cross(Axis) * -1
    else:
         cent = zeroVert - normal * (BendR + thk)
         zeroVertNormal = normal.cross(Axis)
    #print([cent,zeroVertNormal])

    Facelist = []
    Wirelist = []
    for face in Solid.Faces:
        w = WrapFace(face, neturalRadius, Axis, normal, zeroVert, cent, zeroVertNormal)
        eList = Part.__sortEdges__(w)
        myWire = Part.Wire(eList)
        #nextFace = Part.Face(myWire)
        Shape = Part.makeCompound(eList)
        Wirelist.append(Shape)
        #Part.show(myWire)
        #Shape.sewShape()
        Face = Part.makeFilledFace(Part.__sortEdges__(Shape.Edges))
        #Face = Part.makeRuledSurface(Part.__sortEdges__(Shape.Edges))
        Facelist.append(Face)
    shell = Part.makeShell(Facelist)
    Shape = Part.makeSolid(shell)   
    #c = Part.makeCompound(Wirelist)
    #Part.show(c)
    return Shape

def smFold(bendR = 1.0, bendA = 90.0, kfactor = 0.5, invertbend = False, flipped = False, unfold = False,
            position = "forward", bendlinesketch = None, selFaceNames = '', MainObject = None):

  import BOPTools.SplitFeatures, BOPTools.JoinFeatures
  FoldShape = MainObject.Shape
  
  # restrict angle
  if (bendA < 0):
    bendA = -bendA
    flipped = not flipped

  if not(unfold) :
    if bendlinesketch and bendA > 0.0 :
      foldface = FoldShape.getElement(selFaceNames[0])
      tool = bendlinesketch.Shape.copy()
      normal = foldface.normalAt(0,0)
      thk = smthk(FoldShape, foldface)
      #print(thk)

     # if not(flipped) :
        #offset =  thk * kfactor 
      #else :
        #offset = thk * (1 - kfactor )

      unfoldLength = ( bendR + kfactor * thk ) * bendA * math.pi / 180.0
      neturalRadius =  ( bendR + kfactor * thk )
      #neturalLength =  ( bendR + kfactor * thk ) * math.tan(math.radians(bendA / 2.0)) * 2.0
      #offsetdistance = neturalLength - unfoldLength
      #scalefactor = neturalLength / unfoldLength
      #print([neturalRadius, neturalLength, unfoldLength, offsetdistance, scalefactor])

      #To get facedir
      tool_faces = tool.extrude(normal * -thk)
      #Part.show(tool_faces, "tool_faces")
      cutSolid = BOPTools.SplitAPI.slice(FoldShape, tool_faces.Faces, "Standard", 0.0)
      #Part.show(cutSolid,"cutSolid_check")

      if not(invertbend) :
        solid0 = cutSolid.childShapes()[0]
      else :
        solid0 = cutSolid.childShapes()[1]

      cutFaceDir = smCutFace(tool_faces.Faces[0], solid0)
      #Part.show(cutFaceDir,"cutFaceDir")
      facenormal = cutFaceDir.Faces[0].normalAt(0,0)
      #print(facenormal)

      if position == "middle" :
        tool.translate(facenormal * -unfoldLength / 2.0 )
        tool_faces = tool.extrude(normal * -thk)
        cutSolid = BOPTools.SplitAPI.slice(FoldShape, tool_faces.Faces, "Standard", 0.0)
        if not(invertbend) :
          solid0 = cutSolid.childShapes()[0]
        else :
          solid0 = cutSolid.childShapes()[1]
      elif position == "backward" :
        tool.translate(facenormal * -unfoldLength )
        tool_faces = tool.extrude(normal * -thk)
        cutSolid = BOPTools.SplitAPI.slice(FoldShape, tool_faces.Faces, "Standard", 0.0)
        if not(invertbend) :
          solid0 = cutSolid.childShapes()[0]
        else :
          solid0 = cutSolid.childShapes()[1]
      #Part.show(solid0,"solid0")

      bendEdges = FoldShape.common(tool)
      #Part.show(bendEdges,"bendEdges")
      bendEdge = bendEdges.Edges[0]
      if not(flipped) :
        revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) + normal * bendR
      else :
        revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) - normal * (thk +  bendR)
      revAxisV = bendEdge.valueAt(bendEdge.LastParameter) - bendEdge.valueAt(bendEdge.FirstParameter)
      revAxisV.normalize()

      # To check sktech line direction
      if (normal.cross(revAxisV).normalize() - facenormal).Length > smEpsilon:
        revAxisV = revAxisV * -1
        #print(revAxisV)

      if flipped :
        revAxisV = revAxisV * -1
        #print(revAxisV)

      # To get bend surface 
      bendSurf = tool.revolve(revAxisP, revAxisV, bendA)
      #Part.show(bendSurf,"bendSurf")
     
      tool.translate(facenormal * unfoldLength)
      tool_faces = tool.extrude(normal * -thk)
      #Part.show(tool_faces,"tool_faces")
      cutSolid2 = BOPTools.SplitAPI.slice(FoldShape, tool_faces.Faces, "Standard", 0.0)
      #Part.show(cutSolid2,"cutSolid2")

      if not(invertbend) :
        solid1 = cutSolid2.childShapes()[1]        
      else :
        solid1 = cutSolid2.childShapes()[0]    

      # To get bend solid
      flatsolid = FoldShape.cut(solid0)
      flatsolid = flatsolid.cut( solid1)
      #Part.show(flatsolid,"flatsolid")
      flatface = foldface.cut(flatsolid)
      solid1.translate(facenormal * (-unfoldLength))
      #Part.show(solid1,"solid1")
      solid1.rotate(revAxisP, revAxisV, bendA)
      #Part.show(solid1,"rotatedsolid1")
      bendSolidlist =[]
      for solid in flatsolid.Solids :
        bendsolid = BendSolid(solid, flatface.Faces[0], bendEdge, bendR, thk, neturalRadius, revAxisV, flipped)
        #Part.show(bendsolid,"bendsolid")
        bendSolidlist.append(bendsolid)

      if not(invertbend) :
        offset1 = thk / 2.0
        offset2 = thk
      else :
        offset1 =thk / 2.0 * -1
        offset2 =thk  * -1

      bendSurf1 = bendSurf.makeOffsetShape(offset1, 0.0, fill = False)
      #Part.show(bendSurf1,"bendSurf1")
      solidlist = []
      for solid in bendSolidlist :
        #cutbendSurf = bendSurf1.cut(solid)
        #bendFace = bendSurf1.cut(cutbendSurf)
        bendFace = BOPTools.SplitAPI.slice(bendSurf1, [bendSurf1, solid], "Standard", 0.0)
        #Part.show(bendFace,"bendFace")
        bendFace1 = bendFace.childShapes()[1].makeOffsetShape(-offset1, 0.0, fill = False)
        #bendFace1 = bendFace.makeOffsetShape(-offset1, 0.0, fill = False)
        #Part.show(bendFace1,"bendFace1")
        offsetsolid = bendFace1.makeOffsetShape(offset2, 0.0, fill = True)
        #Part.show(offsetsolid, "offsetsolid")
        solidlist.append(offsetsolid)

      solidlist.append(solid0)
      solidlist.append(solid1)
      #resultsolid = Part.makeCompound(solidlist)
      #resultsolid = BOPTools.JoinAPI.connect(solidlist)
      resultsolid = solidlist[0].multiFuse(solidlist[1:])

  else :
    if bendlinesketch and bendA > 0.0 :
      resultsolid = FoldShape

  Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  Gui.ActiveDocument.getObject(bendlinesketch.Name).Visibility = False
  return resultsolid

class SMFoldWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()
    
    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj[0].Object, selobj[0].SubElementNames)
    obj.addProperty("App::PropertyLink","BendLine","Parameters","Bend Reference Line List").BendLine = selobj[1].Object
    obj.addProperty("App::PropertyBool","invertbend","Parameters","Invert bend direction").invertbend = False
    obj.addProperty("App::PropertyFloatConstraint","kfactor","Parameters","Gap from left side").kfactor = (0.5,0.0,1.0,0.01)
    obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
    obj.addProperty("App::PropertyBool","unfold","Parameters","Invert bend direction").unfold = False
    obj.addProperty("App::PropertyEnumeration", "Position", "Parameters","Bend Line Position").Position = ["forward", "middle", "backward"]
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''

    if (not hasattr(fp,"Position")):
      fp.addProperty("App::PropertyEnumeration", "Position", "Parameters","Bend Line Position").Position = ["forward", "middle", "backward"]

    s = smFold(bendR = fp.radius.Value, bendA = fp.angle.Value, flipped = fp.invert, unfold = fp.unfold, kfactor = fp.kfactor, bendlinesketch = fp.BendLine,
                position = fp.Position, invertbend = fp.invertbend, selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s

class SMFoldViewProvider:
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
      objs.append(self.Object.BendLine)
    return objs
 
  def getIcon(self):
    return os.path.join( iconPath , 'AddFoldWall.svg')

class SMFoldPDViewProvider:
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
    if hasattr(self.Object,"BendLine"):
      objs.append(self.Object.BendLine)
    return objs
 
  def getIcon(self):
    return os.path.join( iconPath , 'AddFoldWall.svg')

class AddFoldWallCommandClass():
  """Add Wall command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddFoldWall.svg'), # the name of a svg file available in the resources
            'MenuText': QtCore.QT_TRANSLATE_NOOP('SheetMetal','Fold a Wall'),
            'ToolTip' : QtCore.QT_TRANSLATE_NOOP('SheetMetal','Fold a wall of metal sheet')}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("Bend")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","Fold")
      SMFoldWall(a)
      SMFoldViewProvider(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","Fold")
      SMFoldWall(a)
      SMFoldPDViewProvider(a.ViewObject)
      activeBody.addObject(a)
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

Gui.addCommand('SMFoldWall',AddFoldWallCommandClass())
