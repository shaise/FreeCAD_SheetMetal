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
import DraftGeomUtils

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
    
def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0
        
def smIsOperationLegal(body, selobj):
    #FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True    

def smBase(thk = 2.0, length = 10.0, radius = 1.0, Side = "Inside", MainObject = None):
  WireList = MainObject.Shape.Wires[0]
  #print(sketch_normal)
  if WireList.isClosed() :
    sketch_face = Part.makeFace(MainObject.Shape.Wires,"Part::FaceMakerBullseye" )
    wallSolid = sketch_face.extrude(sketch_face.normalAt(0,0) * thk )
  else : 
    if len(WireList.Edges) > 1 :
      if Side == "Inside" :
        wire = WireList.makeOffset2D(thk/2.0, openResult = True, join = 2 )
      elif Side == "Outside" :
        wire = WireList.makeOffset2D(-thk/2.0, openResult = True, join = 2 )
      else :
        wire = WireList
      #Part.show(wire)
      filletedWire = DraftGeomUtils.filletWire(wire, (radius * 1.5) )
      #Part.show(filletedWire)
      offsetwire = filletedWire.makeOffset2D(thk/2.0, openResult = True )
      #Part.show(offsetwire)
      sketch_face = offsetwire.makeOffset2D(thk, openResult = True, fill = True )
      #Part.show(sketch_face)
      Edge_Dir = sketch_face.normalAt(0,0)
      offsetSolid = offsetwire.extrude(Edge_Dir * length )
      CutList =[]
      for x in offsetSolid.Faces :
        if (str(type(x.Surface))) == "<type 'Part.Plane'>" :
          offsetSolid = x.extrude(x.normalAt(0,0) * -thk )
          CutList.append(offsetSolid)
          #Part.show(offsetSolid)
      wallSolid = sketch_face.extrude(Edge_Dir * length )
      offsetSolids = CutList[0].multiFuse(CutList[1:])
      wallSolid = wallSolid.fuse(offsetSolids)
    else : 
      if MainObject.TypeId == 'Sketcher::SketchObject' :
         mat = MainObject.getGlobalPlacement()
         normal = mat.multVec(FreeCAD.Vector(0,0,1))
         sketch_face = MainObject.Shape.Wires[0].extrude(normal * -length )
         #Part.show(sketch_face)
         wallSolid = sketch_face.extrude(sketch_face.Faces[0].normalAt(0,0) * -thk )

  Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  return wallSolid


###################################################################################
#  Base Bend
###################################################################################

class SMBaseBend:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    
    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyLength","thickness","Parameters","thickness of sheetmetal").thickness = 1.0
    obj.addProperty("App::PropertyEnumeration", "BendSide", "Parameters","Relief Type").BendSide = ["Outside", "Inside", "Middle"]
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 100.0
    obj.addProperty("App::PropertyLink", "BendSketch", "Parameters", "Wall Sketch object").BendSketch = selobj.Object
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    s = smBase(thk = fp.thickness.Value, length = fp.length.Value, radius = fp.radius.Value, Side = fp.BendSide, MainObject = fp.BendSketch)
    fp.Shape = s


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
  """Add Wall command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddBase.svg') , # the name of a svg file available in the resources
            'MenuText': "Make Base Wall" ,
            'ToolTip' : "Create a sheetmetal wall from a sketch"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("Base")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","Base")
      SMBaseBend(a)
      SMBaseViewProvider(a.ViewObject)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) != 1 :
      return False
    selobj = Gui.Selection.getSelection()[0]
    if str(type(selobj)) != "<type 'Sketcher.SketchObject'>":
       return False
    return True

Gui.addCommand('SMBase',AddBaseCommandClass())
