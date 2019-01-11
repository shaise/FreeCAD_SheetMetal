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
 
def get_thk(obj, face):
  normal, yL = face_direction(face)
  theVol = obj.Shape.Volume
  if theVol < 0.0001:
    smWarnDialog("Shape is not a real 3D-object or to small for a metal-sheet!")
  else:
    # Make a first estimate of the thickness
    estimated_thk = theVol/(obj.Shape.Area / 2.0)
  p1 = yL
  p2 = yL + estimated_thk * 1.3 * normal  
  e1 = Part.makeLine(p1, p2)
#  Part.show(e1)
  thkedge = obj.Shape.common(e1)
#  Part.show(thkedge)
#  print thkedge.Edges[0].Length
  return thkedge.Edges[0].Length

def angleBetween(ve1, ve2):
  angle = ve1.getAngle(ve2)
  return math.degrees(angle)

def face_direction(face):
  yL = face.CenterOfMass
  uv = face.Surface.parameter(yL)
  nv = face.normalAt(uv[0], uv[1])
  direction = yL.sub(nv + yL)
#  print(direction)
  return direction, yL

def transform_tool(tool, base_face, tool_face, point, angle):
  direction1,yL1 = face_direction(base_face)
  direction2,yL2 = face_direction(tool_face)
  rot_angle = angleBetween(direction1, direction2)
#  print(rot_angle)
  rot_axis = direction1.cross(direction2)
#  print(rot_axis)
  if rot_axis == FreeCAD.Vector (0.0, 0.0, 0.0):
      rot_axis = FreeCAD.Vector(0, 1, 0).cross(direction2)
  rot_center = yL2
  tool.rotate(rot_center, rot_axis, -rot_angle)
  tool.translate(-yL2+yL1)
  pl = tool.Placement.multiply(FreeCAD.Placement(point, FreeCAD.Rotation(FreeCAD.Vector(0,0,1), 0)))
  tool.Placement = pl
  rot_center = tool.Placement.Base + yL2
  rot_axis = direction1
  rot_angle = angle
  tool.rotate(rot_center, rot_axis, -rot_angle)
#  Part.show(tool)
  return tool

def makeforming(tool, base, base_face, thk, tool_faces = None, point = FreeCAD.Vector(0, 0, 0), angle = 0.0) :
##  faces = [ face for face in tool.Shape.Faces for tool_face in tool_faces if not(face.isSame(tool_face)) ]
#  faces = [ face for face in tool.Shape.Faces if not face in tool_faces ]
#  tool_shell = Part.makeShell(faces)
#  offsetshell = tool_shell.makeOffsetShape(thk, 0.0, inter = False, self_inter = False, offsetMode = 0, join = 2, fill = True)
  offsetshell = tool.Shape.makeThickness(tool_faces, thk, 0.0001, False, False, 0, 0)
  cutSolid = tool.Shape.fuse(offsetshell)
  offsetshell1 = transform_tool(offsetshell, base_face, tool_faces[0], point, angle)
#  Part.show(offsetshell2)
  cutSolid_trans = transform_tool(cutSolid, base_face, tool_faces[0], point, angle)
  base1 = base.Shape.cut(cutSolid_trans)
  base1 = base1.fuse(offsetshell1)
  base1.removeSplitter()
#  Part.show(base1)
  return base1

class SMBendWall:
  def __init__(self, obj):
    '''"Add Forming Wall" '''
    selobj = Gui.Selection.getSelectionEx()

    obj.addProperty("App::PropertyVectorDistance","offset","Parameters","offset from center")
    obj.addProperty("App::PropertyBool","flip","Parameters","Flip Tool direction").flip = False
    obj.addProperty("App::PropertyBool","SupressFeature","Parameters","Supress Forming Feature").SupressFeature = False    
    obj.addProperty("App::PropertyAngle","angle","Parameters","Tool Position angle").angle = 0.0
    obj.addProperty("App::PropertyDistance","thickness","Parameters","thickness of sheetmetal").thickness = -1.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj[0].Object, selobj[0].SubElementNames)
    obj.addProperty("App::PropertyLinkSub", "toolObject", "Parameters", "Forming Tool object").toolObject = (selobj[1].Object, selobj[1].SubElementNames)
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''

    base = fp.baseObject[0]
    base_face = base.Shape.getElement(fp.baseObject[1][0])
    if fp.thickness.Value == 0.0 :
      thk = get_thk(base, base_face)
    else :
      thk = fp.thickness.Value
    tool = fp.toolObject[0]
    tool_faces = [tool.Shape.getElement(fp.toolObject[1][i]) for i in range(len(fp.toolObject[1]))]

    if not(fp.SupressFeature) :
      a = makeforming(tool, base, base_face, thk, tool_faces, fp.offset, fp.angle.Value)
    else :
      a = base.Shape
    fp.Shape = a
    Gui.ActiveDocument.getObject(fp.baseObject[0].Name).Visibility = False


class SMViewProviderTree:
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
    return objs
 
  def getIcon(self):
    return os.path.join( iconPath , 'SMForming.svg')
      
  def setEdit(self,vobj,mode):
    taskd = SMFormingWallTaskPanel()
    taskd.obj = vobj.Object
    taskd.update()
    self.Object.ViewObject.Visibility=False
    self.Object.baseObject[0].ViewObject.Visibility=True
    FreeCADGui.Control.showDialog(taskd)
    return True

  def unsetEdit(self,vobj,mode):
    FreeCADGui.Control.closeDialog()
    self.Object.baseObject[0].ViewObject.Visibility=False
    self.Object.ViewObject.Visibility=True
    return False


class SMFormingWallTaskPanel:
    '''A TaskPanel for the Sheetmetal'''
    def __init__(self):
      
      self.obj = None
      self.form = QtGui.QWidget()
      self.form.setObjectName("SMBendWallTaskPanel")
      self.form.setWindowTitle("Binded faces/edges list")
      self.grid = QtGui.QGridLayout(self.form)
      self.grid.setObjectName("grid")
      self.title = QtGui.QLabel(self.form)
      self.grid.addWidget(self.title, 0, 0, 1, 2)
      self.title.setText("Select new face(s)/Edge(s) and press Update")

      # tree
      self.tree = QtGui.QTreeWidget(self.form)
      self.grid.addWidget(self.tree, 1, 0, 1, 2)
      self.tree.setColumnCount(2)
      self.tree.setHeaderLabels(["Name","Subelement"])

      # buttons
      self.addButton = QtGui.QPushButton(self.form)
      self.addButton.setObjectName("addButton")
      self.addButton.setIcon(QtGui.QIcon(os.path.join( iconPath , 'SMUpdate.svg')))
      self.grid.addWidget(self.addButton, 3, 0, 1, 2)

      QtCore.QObject.connect(self.addButton, QtCore.SIGNAL("clicked()"), self.updateElement)
      self.update()

    def isAllowedAlterSelection(self):
      return True

    def isAllowedAlterView(self):
      return True

    def getStandardButtons(self):
      return int(QtGui.QDialogButtonBox.Ok)

    def update(self):
      'fills the treewidget'
      self.tree.clear()
      if self.obj:
        f = self.obj.baseObject
        if isinstance(f[1],list):
          for subf in f[1]:
            #FreeCAD.Console.PrintLog("item: " + subf + "\n")
            item = QtGui.QTreeWidgetItem(self.tree)
            item.setText(0,f[0].Name)
            item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
            item.setText(1,subf)  
        else:
          item = QtGui.QTreeWidgetItem(self.tree)
          item.setText(0,f[0].Name)
          item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
          item.setText(1,f[1][0])
      self.retranslateUi(self.form)

    def updateElement(self):
      if self.obj:
        sel = FreeCADGui.Selection.getSelectionEx()[0]
        if sel.HasSubObjects:
          obj = sel.Object
          for elt in sel.SubElementNames:
            if "Face" in elt:
              face = self.obj.baseObject
              found = False
              if (face[0] == obj.Name):
                if isinstance(face[1],tuple):
                  for subf in face[1]:
                    if subf == elt:
                      found = True
                else:
                  if (face[1][0] == elt):
                    found = True
              if not found:
                self.obj.baseObject = (sel.Object, sel.SubElementNames)
        self.update()

    def accept(self):
      FreeCAD.ActiveDocument.recompute()
      FreeCADGui.ActiveDocument.resetEdit()
      #self.obj.ViewObject.Visibility=True
      return True

    def retranslateUi(self, TaskPanel):
      #TaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "Faces", None))
      self.addButton.setText(QtGui.QApplication.translate("draft", "Update", None))


class AddFormingWallCommand():
  """Add Forming Wall command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SMForming.svg') , # the name of a svg file available in the resources
            'MenuText': "Make Forming in Wall" ,
            'ToolTip' : "Make a forming using tool in metal sheet"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("WallForming")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","WallForming")
      SMBendWall(a)
      SMViewProviderTree(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","WallForming")
      SMBendWall(a)
      SMViewProviderTree(a.ViewObject)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 2 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    if str(type(selobj)) == "<type 'Sketcher.SketchObject'>":
      return False
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) != Part.Face :
        return False
    return True

Gui.addCommand('SMFormingWall',AddFormingWallCommand())

