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
        # how to add QtCore.QT_TRANSLATE_NOOP() to this ?
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True    
 
def smthk(obj, foldface) :
  normal = foldface.normalAt(0,0)
  theVol = obj.Volume
  if theVol < 0.0001:
      # translate
      SMError("Shape is not a real 3D-object or to small for a metal-sheet!")
  else:
      # Make a first estimate of the thickness
      estimated_thk = theVol/(obj.Area / 2.0)
  p1 = foldface.CenterOfMass
  p2 = foldface.CenterOfMass + estimated_thk * -1.3 * normal
  e1 = Part.makeLine(p1, p2)
  thkedge = obj.common(e1)
  thk = thkedge.Length
  return thk

def smFold(bendR = 1.0, bendA = 90.0, kfactor = 0.45, invertbend = False, flipped = False, unfold = False,
            bendlinesketch = None, selFaceNames = '', MainObject = None):

  import BOPTools.SplitFeatures, BOPTools.JoinFeatures
  FoldShape = MainObject.Shape
  
  # restrict angle
  if (bendA < 0):
    bendA = -bendA
    flipped = not flipped

  if not(unfold) :
    if bendlinesketch and bendA > 0.0 :
      foldface = FoldShape.getElement(selFaceNames[0])
      normal = foldface.normalAt(0,0)
      thk = smthk(FoldShape, foldface)

      if not(flipped) :
        offset = thk * kfactor
      else :
        offset = thk - ( thk * kfactor )

      tool = bendlinesketch.Shape
      tool_faces = tool.extrude(normal * -thk)
      #Part.show(tool_faces)
      cutSolid = BOPTools.SplitAPI.slice(FoldShape, tool_faces.Faces, "Standard", 0.0)
      cutface = BOPTools.SplitAPI.slice(foldface, tool.Edges, "Standard", 0.0)
      sketch = tool.copy()
      sketch.translate(normal * -offset)
      cutface.translate(normal * -offset)
      Axis = FoldShape.common(sketch)
      #Part.show(Axis)
      edge = Axis.Edges[0]
      revAxisP = edge.valueAt(edge.FirstParameter)
      revAxisV = edge.valueAt(edge.LastParameter) - edge.valueAt(edge.FirstParameter)
      revAxisV.normalize()

      if not(invertbend) :
        face0 = cutface.childShapes()[0]
        face1 = cutface.childShapes()[1]
        solid0 = cutSolid.childShapes()[0]
        solid1 = cutSolid.childShapes()[1]
      else :
        bendA = -bendA
        face0 = cutface.childShapes()[1]
        face1 = cutface.childShapes()[0]
        solid0 = cutSolid.childShapes()[1]
        solid1 = cutSolid.childShapes()[0]
      #Part.show(solid0)
      #Part.show(solid1)

      # To check sktech line direction
      tool_copy = tool.copy()
      if flipped :
        tool_copy.translate(normal * -thk)
      solid1_copy = solid1.copy()
      solid1_copy.rotate(revAxisP, revAxisV, bendA)
      common_edge = solid1_copy.common(tool_copy)
      #Part.show(common_edge)

      if not(common_edge.Edges) :
        revAxisV = revAxisV * -1

      solid1.rotate(revAxisP, revAxisV, bendA)
      #Part.show(solid1)
      face1.rotate(revAxisP, revAxisV, bendA)
      #Part.show(face1)

      facelist = [face0, face1]
      joinface = BOPTools.JoinAPI.connect(facelist)
      #Part.show(joinface)
      filletedface = joinface.makeFillet(bendR + offset, joinface.Edges)
      #Part.show(filletedface)
      offsetfacelist = []
      offsetsolidlist = []
      for face in filletedface.Faces :
        if not(issubclass(type(face.Surface),Part.Plane)):
          offsetface = face.makeOffsetShape(offset-thk, 0.0)
          #Part.show(offsetface)
          offsetfacelist.append(offsetface)
      for face in offsetfacelist :
        offsetsolid = face.makeOffsetShape(thk, 0.0, fill = True)
        #Part.show(offsetsolid)
        offsetsolidlist.append(offsetsolid)
      if len(offsetsolidlist) > 1 :
        offsetsolid = offsetsolidlist[0].multiFuse(offsetsolidlist[1:])
      else :
        offsetsolid = offsetsolidlist[0]
      cutsolid1 = BOPTools.JoinAPI.cutout_legacy(solid0, offsetsolid, 0.0)
      cutsolid2 = BOPTools.JoinAPI.cutout_legacy(solid1, offsetsolid, 0.0)
      # To Check cut solid in correct direction 
      solid0_c = cutsolid1.common(solid1)
      #Part.show(solid0_c,"solid1")
      solid1_c = cutsolid2.common(solid0)
      #Part.show(solid1_c,"solid2")
      if solid0_c.Edges :
        solid0 = solid0.cut(cutsolid1)
        cutsolid1 = BOPTools.JoinAPI.cutout_legacy(solid0, offsetsolid, 0.0)
      if solid1_c.Edges :
        solid1 = solid1.cut(cutsolid2)
        cutsolid2 = BOPTools.JoinAPI.cutout_legacy(solid1, offsetsolid, 0.0)
      solidlist = [cutsolid1, cutsolid2, offsetsolid]
      resultsolid = BOPTools.JoinAPI.connect(solidlist)
  
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

    #translate
    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj[0].Object, selobj[0].SubElementNames)
    obj.addProperty("App::PropertyLink","BendLine","Parameters","Bend Reference Line List").BendLine = selobj[1].Object
    obj.addProperty("App::PropertyBool","invertbend","Parameters","Invert bend direction").invertbend = False
    obj.addProperty("App::PropertyFloatConstraint","kfactor","Parameters","Gap from left side").kfactor = (0.5,0.0,1.0,0.01)
    obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
    obj.addProperty("App::PropertyBool","unfold","Parameters","Invert bend direction").unfold = False
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    
    s = smFold(bendR = fp.radius.Value, bendA = fp.angle.Value, flipped = fp.invert, unfold = fp.unfold, kfactor = fp.kfactor, bendlinesketch = fp.BendLine,
                invertbend = fp.invertbend, selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
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
    if activeBody == None or not smIsPartDesign(selobj):
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
