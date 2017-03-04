# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalCmd.py
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

import FreeCAD, FreeCADGui, Part, os
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

def smWarnDialog(msg):
    diag = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'Error in macro MessageBox', msg)
    diag.setWindowModality(QtCore.Qt.ApplicationModal)
    diag.exec_()
 
def smBelongToBody(item, body):
    if (body == None):
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False
    
def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0
    
def smIsOperationLegal(body, selobj):
    FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True    
 
def smStrEdge(e):
    return "[" + str(e.valueAt(e.FirstParameter)) + " , " + str(e.valueAt(e.LastParameter)) + "]"
 
def smMakeFace(edge, dir, from_p, to_p):
    e1 = edge.copy()
    e1.translate(dir * from_p)
    e2 = edge.copy()
    e2.translate(dir * to_p)
    FreeCAD.Console.PrintLog("=> fromp:" + str(from_p) + "\n   top:" + str(to_p) + "\n   fp:" + str(e1.FirstParameter) + "\n   lp:" + str(e1.LastParameter) + "\n")
    e3 = Part.LineSegment(e1.valueAt(e1.FirstParameter), e2.valueAt(e2.FirstParameter)).toShape()
    e4 = Part.LineSegment(e1.valueAt(e1.LastParameter), e2.valueAt(e2.LastParameter)).toShape()
    FreeCAD.Console.PrintLog("=>" + smStrEdge(e1) + "\n  " + smStrEdge(e3) + "\n  " + smStrEdge(e2) + "\n  " + smStrEdge(e4) + "\n")
    w = Part.Wire([e1,e3,e2,e4])
    return Part.Face(w)


def smBend(bendR = 1.0, bendA = 90.0, flipped = False, extLen = 10.0, gap1 = 0.0, gap2 = 0.0, reliefW = 0.5, 
            reliefD = 1.0, selFaceNames = '', MainObject = None):
            
  #AAD = FreeCAD.ActiveDocument
  #MainObject = AAD.getObject( selObjectName )
  
  resultSolid = MainObject.Shape
  for selFaceName in selFaceNames:
    selFace = MainObject.Shape.getElement(selFaceName)
  
    # find the narrow edge
    thk = 999999.0
    for edge in selFace.Edges:
      if abs( edge.Length ) < thk:
        thk = abs( edge.Length )
        thkEdge = edge

    # main corner
    p0 = thkEdge.valueAt(thkEdge.FirstParameter)
    thkDir = thkEdge.valueAt(thkEdge.LastParameter) - thkEdge.valueAt(thkEdge.FirstParameter)
    
    # find a length edge  =  revolve axis direction
    for lenEdge in selFace.Edges:
      lastp = lenEdge.LastParameter
      firstp = lenEdge.FirstParameter
      len = lenEdge.Length
      if lenEdge.isSame(thkEdge):
        continue
      FreeCAD.Console.PrintLog("=>" + str(lastp)+", "+ str(lenEdge.valueAt(firstp)) +", "+ str(lenEdge.valueAt(lastp)) + ", " + str(p0) + "\n")
      if (lenEdge.valueAt(firstp) - p0).Length < smEpsilon:
        revAxisV = lenEdge.valueAt(lastp) - lenEdge.valueAt(firstp)
        break
      if (lenEdge.valueAt(lastp) - p0).Length < smEpsilon:
        revAxisV = lenEdge.valueAt(firstp) - lenEdge.valueAt(lastp)
        break
     
    # narrow the wall if we have gaps
    revDir = revAxisV.normalize()
    lgap2 = len - gap2
    if gap1 == 0 and gap2 == 0:
      revFace = selFace
    else:
      revFace = smMakeFace(thkEdge, revDir, gap1, lgap2)
      if (revFace.normalAt(0,0) != selFace.normalAt(0,0)):
        revFace.reverse()
    
    #make sure the direction verctor is correct in respect to the normal
    if (thkDir.cross(revAxisV).normalize() - selFace.normalAt(0,0)).Length < smEpsilon:
      revAxisV = revAxisV * -1
    
    # remove relief if needed
    if reliefW > 0 and reliefD > 0 and (gap1 > 0 or gap2 > 0) :
      thkEdgeW = Part.LineSegment(thkEdge.valueAt(thkEdge.FirstParameter-0.1), thkEdge.valueAt(thkEdge.LastParameter+0.1)).toShape()
      reliefFace = smMakeFace(thkEdgeW, revDir, gap1 - reliefW, gap1)
      reliefFace = reliefFace.fuse(smMakeFace(thkEdgeW, revDir, lgap2, lgap2 + reliefW))
      reliefSolid = reliefFace.extrude(selFace.normalAt(0,0) * reliefD * -1)
      #Part.show(reliefSolid)
      resultSolid = resultSolid.cut(reliefSolid)
   
    #find revolve point
    if not(flipped):
      revAxisP = thkEdge.valueAt(thkEdge.LastParameter + bendR)
      revAxisV = revAxisV * -1
    else:
      revAxisP = thkEdge.valueAt(thkEdge.FirstParameter - bendR)  
    
    # create bend
    wallFace = revFace
    if bendA > 0 :
      bendSolid = revFace.revolve(revAxisP, revAxisV, bendA)
      #Part.show(bendSolid)
      resultSolid = resultSolid.fuse(bendSolid)
      wallFace = revFace.copy()
      wallFace.rotate(revAxisP, revAxisV, bendA)
    
    # create wall
    if extLen > 0 :
      wallSolid = wallFace.extrude(wallFace.normalAt(0,0) * extLen)
      resultSolid = resultSolid.fuse(wallSolid)
      
  Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  return resultSolid
  



class SMBendWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    
    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 10.0
    obj.addProperty("App::PropertyLength","gap1","Parameters","Gap from left side").gap1 = 0.0
    obj.addProperty("App::PropertyLength","gap2","Parameters","Gap from right side").gap2 = 0.0
    obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
    obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
    obj.addProperty("App::PropertyLength","reliefw","Parameters","Relief width").reliefw = 0.5
    obj.addProperty("App::PropertyLength","reliefd","Parameters","Relief depth").reliefd = 1.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self
 
  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    s = smBend(bendR = fp.radius.Value, bendA = fp.angle.Value,  flipped = fp.invert, extLen = fp.length.Value, 
                gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefW = fp.reliefw.Value, reliefD = fp.reliefd.Value,
                selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s


class SMViewProviderTree:
  "A View provider that nests children objects under the created one"
      
  def __init__(self, obj, isPartDesign):
    obj.Proxy = self
    self.Object = obj.Object
    self.isPartDesign = isPartDesign
    FreeCAD.Console.PrintLog("isPartDesign = " + str(self.isPartDesign) + '\n')
      
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
    if hasattr(self, "isPartDesign") and not self.isPartDesign and hasattr(self.Object,"baseObject"):
      objs.append(self.Object.baseObject[0])
    return objs
 
  def getIcon(self):
    if isinstance(self.Object.Proxy,SMBendWall):
      return os.path.join( iconPath , 'AddWall.svg')
    elif isinstance(self.Object.Proxy,SMExtrudeWall):
      return os.path.join( iconPath , 'SMExtrude.svg')




class AddWallCommandClass():
  """Add Wall command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddWall.svg') , # the name of a svg file available in the resources
            'MenuText': "Make Wall" ,
            'ToolTip' : "Extends a wall from a side face of metal sheet"}
 
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
    if activeBody == None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","Bend")
      SMBendWall(a)
      SMViewProviderTree(a.ViewObject, False)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","Bend")
      SMBendWall(a)
      SMViewProviderTree(a.ViewObject, True)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) != Part.Face:
        return False
    return True

Gui.addCommand('SMMakeWall',AddWallCommandClass())

###########################################################################################
# Extrude
###########################################################################################

def smExtrude(extLength = 10.0, selFaceNames = '', selObjectName = ''):
  
#  selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
#  selObjectName = Gui.Selection.getSelection()[0].Name
  AAD = FreeCAD.ActiveDocument
  MainObject = AAD.getObject( selObjectName )
  finalShape = MainObject.Shape
  for selFaceName in selFaceNames:
    selFace = AAD.getObject(selObjectName).Shape.getElement(selFaceName)

    # extrusion direction
    V_extDir = selFace.normalAt( 0,0 )

    # extrusion
    wallFace = selFace.extrude( V_extDir*extLength )
    finalShape = finalShape.fuse( wallFace )
  
  #finalShape = finalShape.removeSplitter()
  #finalShape = Part.Solid(finalShape.childShapes()[0])  
  Gui.ActiveDocument.getObject( selObjectName ).Visibility = False
  return finalShape


  
class SMExtrudeWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 10.0
    obj.addProperty("App::PropertyDistance","gap1","Parameters","Gap from left side").gap1 = 0.0
    obj.addProperty("App::PropertyDistance","gap2","Parameters","Gap from right side").gap2 = 0.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self

  def execute(self, fp):
    #s = smExtrude(extLength = fp.length.Value, selFaceNames = self.selFaceNames, selObjectName = self.selObjectName)
    s = smBend(bendA = 0.0,  extLen = fp.length.Value, gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefW = 0.0,
                selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s
    

class SMExtrudeCommandClass():
  """Extrude face"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SMExtrude.svg') , # the name of a svg file available in the resources
            'MenuText': "Extrude Face" ,
            'ToolTip' : "Extrude a face along normal"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
      #FreeCAD.Console.PrintLog("ver 0.17 detected") 
    doc.openTransaction("Extrude")
    if (activeBody == None):
      a = doc.addObject("Part::FeaturePython","Extrude")
      SMExtrudeWall(a)
      SMViewProviderTree(a.ViewObject, False)
    else:
      a = doc.addObject("PartDesign::FeaturePython","Extrude")
      SMExtrudeWall(a)
      SMViewProviderTree(a.ViewObject, True)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) != Part.Face:
        return False
    return True

Gui.addCommand('SMExtrudeFace',SMExtrudeCommandClass())
