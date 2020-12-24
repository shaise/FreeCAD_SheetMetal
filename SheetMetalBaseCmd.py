# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalBaseCmd.py
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

def smIsSketchObject(obj):
    return str(obj).find("<Sketcher::") == 0

def smIsOperationLegal(body, selobj):
    #FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsSketchObject(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True

def smBase(thk = 2.0, length = 10.0, radius = 1.0, Side = "Inside", midplane = False, reverse = False, MainObject = None):
  # To Get sketch normal
  WireList = MainObject.Shape.Wires[0]
  mat = MainObject.getGlobalPlacement().Rotation
  normal = (mat.multVec(FreeCAD.Vector(0,0,1))).normalize()
  #print([mat, normal])
  if WireList.isClosed() :
    # If Cosed sketch is there, make a face & extrude it 
    sketch_face = Part.makeFace(MainObject.Shape.Wires,"Part::FaceMakerBullseye")
    wallSolid = sketch_face.extrude(sketch_face.normalAt(0,0) * thk)
  else :
    # If sketch is one type, make a face by extruding & offset it to correct position
    if midplane :
      WireList.translate(normal * length/2.0)
      wire_extr = WireList.extrude(normal * -length)
    elif reverse:
      wire_extr = WireList.extrude(normal * length)
    else :
      wire_extr = WireList.extrude(normal * -length)
    #Part.show(wire_extr,"wire_extr")
    if Side == "Inside" :
      wire_extr = wire_extr.makeOffsetShape(-thk/2.0, 0.0, fill = False, join = 2)
    elif Side == "Outside" :
      wire_extr = wire_extr.makeOffsetShape(thk/2.0, 0.0, fill = False, join = 2)
    #Part.show(wire_extr,"wire_extr")
    if len(WireList.Edges) > 1 :
      filleted_extr = wire_extr.makeFillet((radius + thk / 2.0), wire_extr.Edges)
      #Part.show(filleted_extr,"filleted_extr")
    else :
      filleted_extr = wire_extr
      #Part.show(filleted_extr,"filleted_extr")
    offset_extr = filleted_extr.makeOffsetShape(-thk/2.0, 0.0, fill = False)
    #Part.show(offset_extr,"offset_extr")
    wallSolid = offset_extr.makeOffsetShape(thk, 0.0, fill = True)
    #Part.show(wallSolid,"wallSolid")

  #Part.show(wallSolid,"wallSolid")
  return wallSolid

class SMBaseBend:
  def __init__(self, obj):
    '''"Add wall or Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]

    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyLength","thickness","Parameters","thickness of sheetmetal").thickness = 1.0
    obj.addProperty("App::PropertyEnumeration", "BendSide", "Parameters","Relief Type").BendSide = ["Outside", "Inside", "Middle"]
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 100.0
    obj.addProperty("App::PropertyLink", "BendSketch", "Parameters", "Wall Sketch object").BendSketch = selobj.Object
    obj.addProperty("App::PropertyBool","MidPlane","Parameters","Extrude Symmetric to Plane").MidPlane = False
    obj.addProperty("App::PropertyBool","Reverse","Parameters","Reverse Extrusion Direction").Reverse = False
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    if (not hasattr(fp,"MidPlane")):
      fp.addProperty("App::PropertyBool","MidPlane","Parameters","Extrude Symmetric to Plane").MidPlane = False
      fp.addProperty("App::PropertyBool","Reverse","Parameters","Reverse Extrusion Direction").Reverse = False

    s = smBase(thk = fp.thickness.Value, length = fp.length.Value, radius = fp.radius.Value, Side = fp.BendSide, 
                  midplane = fp.MidPlane, reverse = fp.Reverse, MainObject = fp.BendSketch)
    fp.Shape = s
    Gui.ActiveDocument.getObject(fp.BendSketch.Name).Visibility = False

class SMBaseViewProvider:
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
    if hasattr(self.Object,"BendSketch"):
      objs.append(self.Object.BendSketch)
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'AddBase.svg')

class AddBaseCommandClass():
  """Add Base command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddBase.svg'), # the name of a svg file available in the resources
            'MenuText': QtCore.QT_TRANSLATE_NOOP('SheetMetal','Make Base Wall'),
            'ToolTip' : QtCore.QT_TRANSLATE_NOOP('SheetMetal','Create a sheetmetal wall from a sketch')}

  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
#    if not smIsOperationLegal(activeBody, selobj):
#        return
    doc.openTransaction("BaseBend")
    if activeBody is None :
      a = doc.addObject("Part::FeaturePython","BaseBend")
      SMBaseBend(a)
      SMBaseViewProvider(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","BaseBend")
      SMBaseBend(a)
      SMBaseViewProvider(a.ViewObject)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) != 1 :
      return False
    selobj = Gui.Selection.getSelection()[0]
    if not(selobj.isDerivedFrom("Sketcher::SketchObject")):
       return False
    return True

Gui.addCommand('SMBase',AddBaseCommandClass())
