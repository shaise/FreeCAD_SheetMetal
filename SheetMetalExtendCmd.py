# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalJunction.py
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
from FreeCAD import Base

import FreeCAD, FreeCADGui, Part, os, math
import SheetMetalBaseCmd
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001
import BOPTools.SplitFeatures

# add translations path
LanguagePath = os.path.join( __dir__, 'translations')
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

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

def smMakeFace(edge, dir, extLen, gap1 = 0.0,
               gap2 = 0.0, angle1 = 0.0, angle2 = 0.0, op = ''):
    len1 = extLen * math.tan(math.radians(angle1))
    len2 = extLen * math.tan(math.radians(angle2))

    p1 = edge.valueAt(edge.LastParameter - gap2)
    p2 = edge.valueAt(edge.FirstParameter + gap1)
    p3 = edge.valueAt(edge.FirstParameter + gap1 + len1) + dir.normalize() * extLen
    p4 = edge.valueAt(edge.LastParameter - gap2 - len2) + dir.normalize() * extLen

    e2 = Part.makeLine(p2, p3)
    e4 = Part.makeLine(p4, p1)
    section = e4.section(e2)

    if section.Vertexes :
      p5 = section.Vertexes[0].Point
      w = Part.makePolygon([p1,p2,p5,p1])
    else :
      w = Part.makePolygon([p1,p2,p3,p4,p1])
    face = Part.Face(w)
    if hasattr(face, 'mapShapes'):
        face.mapShapes([(edge,face)],None,op)
    return face

def smFace(selItem, obj) :
  # find face if Edge Selected
  if type(selItem) == Part.Edge :
    Facelist = obj.ancestorsOfType(selItem, Part.Face)
    if Facelist[0].Area < Facelist[1].Area :
      selFace = Facelist[0]
    else :
      selFace = Facelist[1]
  elif type(selItem) == Part.Face :
    selFace = selItem
  return selFace

def smTouchFace(Face, obj, thk) :
  # find face Modified During loop
  #Part.show(Face,'Face')
  facelist =[]
  for face in obj.Faces :
    #Part.show(face,'face')
    face_common = face.common(Face)
    if not(face_common.Faces) :
      continue
    edge = face.Vertexes[0].extrude(face.normalAt(0,0) * -thk * 2)
    #Part.show(edge,'edge')
    edge_common = obj.common(edge)
    #Part.show(edge_common,'edge_common')
    if (edge_common.Edges[0].Length - thk) < smEpsilon :
      facelist.append( face)
      break
  return facelist[0]

def smgetSubface(face, obj, edge, thk):
  # Project thickness side edge to get one side rectangle
  normal = face.normalAt(0,0)
  faceVert = face.Vertexes[0].Point
  pt1 = edge.Vertexes[0].Point.projectToPlane(faceVert, normal)
  pt2 = edge.Vertexes[1].Point.projectToPlane(faceVert, normal)
  vec1 = (pt2-pt1)

  # find min & max point of cut shape
  wallsolidlist =[]
  for solid in obj.Solids:
    pt_list =[]
    for vertex in solid.Vertexes :
      poi = vertex.Point
      pt = poi.projectToPlane(faceVert, normal)
      pt_list.append(pt)
    p1 = Base.Vector(min([pts.x for pts in pt_list]), min([pts.y for pts in pt_list]), min([pts.z for pts in pt_list]))
    p2 = Base.Vector(max([pts.x for pts in pt_list]), max([pts.y for pts in pt_list]), max([pts.z for pts in pt_list]))
    #print([p1, p2])

    # Find angle between diagonal & thickness side edge
    vec2 = (p2 - p1)
    angle1 = vec2.getAngle(vec1)
    angle = math.degrees(angle1)
    #print(angle)

    # Check & correct orientation of diagonal edge rotation
    e = Part.makeLine(p1, p2)
    e.rotate(p1, normal, -angle)
    vec2 = (e.valueAt(e.LastParameter) - e.valueAt(e.FirstParameter)).normalize()
    coeff = vec2.dot(vec1.normalize())
    #print(coeff)
    if coeff != 1.0 :
      angle = 90 - angle

    # Create Cut Rectangle Face from min/max points & angle
    e = Part.Line(p1, p2).toShape()
    e1 = e.copy()
    e1.rotate(p1, normal, -angle)
    e2 = e.copy()
    e2.rotate(p2, normal, 90-angle)
    section1 = e1.section(e2)
    #Part.show(section1,'section1')
    p3 = section1.Vertexes[0].Point
    e3 = e.copy()
    e3.rotate(p1, normal, 90-angle)
    e4 = e.copy()
    e4.rotate(p2, normal, -angle)
    section2 = e3.section(e4)
    #Part.show(section2,'section2')
    p4 = section2.Vertexes[0].Point
    w = Part.makePolygon([p1,p3,p2,p4,p1])
    #Part.show(w, "wire")
    face = Part.Face(w)
    wallSolid = face.extrude(normal * -thk)
    wallsolidlist.append(wallSolid)
  return wallsolidlist

def smExtrude(extLength = 10.0, gap1 = 0.0, gap2 = 0.0, subtraction = False, offset = 0.02, refine = True,
                            sketch = '', selFaceNames = '', selObject = ''):

  finalShape = selObject
  for selFaceName in selFaceNames:
    selItem = selObject.getElement(selFaceName)
    selFace = smFace(selItem, selObject)

    # find the narrow edge
    thk = 999999.0
    for edge in selFace.Edges:
      if abs( edge.Length ) < thk:
        thk = abs( edge.Length )
        thkEdge = edge

    # find a length edge
    p0 = thkEdge.valueAt(thkEdge.FirstParameter)
    for lenEdge in selFace.Edges:
      p1 = lenEdge.valueAt(lenEdge.FirstParameter)
      p2 = lenEdge.valueAt(lenEdge.LastParameter)
      if lenEdge.isSame(thkEdge):
        continue
      if (p1 - p0).Length < smEpsilon:
        break
      if (p2 - p0).Length < smEpsilon:
        break

    # find the large face connected with selected face
    list2 = selObject.ancestorsOfType(lenEdge, Part.Face)
    for Cface in list2 :
      if not(Cface.isSame(selFace)) :
        break
    #Part.show(Cface, "Cface")

    # Main Length Edge, Extrusion direction
#    MlenEdge = lenEdge
#    leng = MlenEdge.Length
    pThkDir1 = selFace.CenterOfMass
    pThkDir2 = lenEdge.Curve.value(lenEdge.Curve.parameter(pThkDir1))
    thkDir = pThkDir1.sub(pThkDir2).normalize()
    FaceDir = selFace.normalAt(0,0)

    # if sketch is as wall
    sketches = False
    if sketch :
      if sketch.Shape.Wires[0].isClosed() :
        sketches = True
      else :
        pass

    # Split solid Based on Top Face into two solid
    Topface_Solid = Cface.Wires[0].extrude(Cface.normalAt(0,0) * -thk)
    #Part.show(Topface_Solid,"Topface_Solid")
    SplitSolids = BOPTools.SplitAPI.slice(finalShape, Topface_Solid.Faces, "Standard", 0.0)
    #Part.show(SplitSolids,"SplitSolids")
    for SplitSolid in SplitSolids.Solids:
      check_face = SplitSolid.common(Cface)
      if check_face.Faces:
          SplitSolid1 = SplitSolid
          break
    #Part.show(SplitSolid1,"SplitSolid1")
    for SplitSolid in SplitSolids.Solids:
      if not(SplitSolid.isSame(SplitSolid1)) :
        SplitSolid2 = SplitSolid
        break
    #Part.show(SplitSolid2, "SplitSolid2")

    # Make solid from sketch, if sketch is present
    solidlist =[]
    if sketches :
      Wall_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
      check_face =Wall_face.common(Cface)
      if not(check_face.Faces) :
        thkDir = thkDir * -1
      wallSolid = Wall_face.extrude(thkDir * thk)
      #Part.show(wallSolid, "wallSolid")
      solidlist.append(wallSolid)

      # To find Overlapping Solid, non thickness side Face that touch Overlapping Solid
      overlap_solid = wallSolid.common(SplitSolid2)
      #Part.show(overlap_solid, "overlap_solid")

      if overlap_solid.Faces :
        substract_face = smTouchFace(wallSolid, SplitSolid2, thk)
        #Part.show(substract_face, "substract_face")
        # To get solids that aligned/normal to touching face
        overlap_solidlist = smgetSubface(substract_face, overlap_solid, lenEdge, thk)

      # Substract solid from Initial Solid
      if subtraction :
        for solid in overlap_solidlist:
          CutSolid = solid.makeOffsetShape(offset, 0.0, fill = False, join = 2)
          #Part.show(CutSolid, "CutSolid")
          finalShape = finalShape.cut(CutSolid)
          #Part.show(finalShape,"finalShape")

    elif extLength > 0.0 :
      # create wall, if edge or face selected
      Wall_face = smMakeFace(lenEdge, FaceDir, extLength, gap1, gap2, op='SMW')
      wallSolid = Wall_face.extrude(thkDir * thk)
      #Part.show(wallSolid,"wallSolid")
      solidlist.append(wallSolid)

    # Fuse All solid created to Split solid
    if len(solidlist) > 0 :
      resultSolid = SplitSolid1.fuse(solidlist[0])
      #Part.show(resultSolid,"resultSolid")

      # Merge final list
      finalShape = finalShape.cut(resultSolid)
      #Part.show(finalShape,"finalShape")
      finalShape = finalShape.fuse(resultSolid)

  #Part.show(finalShape,"finalShape")
  if refine :
    finalShape = finalShape.removeSplitter()
  return finalShape

class SMExtrudeWall:
  def __init__(self, obj):
    '''"Add Sheetmetal Wall by Extending" '''
    selobj = Gui.Selection.getSelectionEx()[0]

    _tip_ = FreeCAD.Qt.translate("App::Property","Length of Wall")
    obj.addProperty("App::PropertyLength","length","Parameters",_tip_).length = 10.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Gap from left side")
    obj.addProperty("App::PropertyDistance","gap1","Parameters",_tip_).gap1 = 0.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Gap from right side")
    obj.addProperty("App::PropertyDistance","gap2","Parameters",_tip_).gap2 = 0.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Base object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",_tip_).baseObject = (selobj.Object, selobj.SubElementNames)
    _tip_ = FreeCAD.Qt.translate("App::Property","Wall Sketch")
    obj.addProperty("App::PropertyLink","Sketch","ParametersExt",_tip_)
    _tip_ = FreeCAD.Qt.translate("App::Property","Use Subtraction")
    obj.addProperty("App::PropertyBool","UseSubtraction","ParametersExt",_tip_).UseSubtraction = False
    _tip_ = FreeCAD.Qt.translate("App::Property","Offset for subtraction")
    obj.addProperty("App::PropertyDistance","Offset","ParametersExt",_tip_).Offset = 0.02
    _tip_ = FreeCAD.Qt.translate("App::Property","Use Refine")
    obj.addProperty("App::PropertyBool","Refine","ParametersExt",_tip_).Refine = True
    obj.Proxy = self

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    if (not hasattr(fp,"Sketch")):
      _tip_ = FreeCAD.Qt.translate("App::Property","Wall Sketch")
      fp.addProperty("App::PropertyLink","Sketch","ParametersExt",_tip_)
      _tip_ = FreeCAD.Qt.translate("App::Property","Use Subtraction")
      fp.addProperty("App::PropertyDistance","Offset","ParametersExt",_tip_).Offset = 0.02
      _tip_ = FreeCAD.Qt.translate("App::Property","Use Refine")
      fp.addProperty("App::PropertyBool","Refine","ParametersExt",_tip_).Refine = False
    if (not hasattr(fp, "UseSubtraction")):
      useSub = False
      if (hasattr(fp,"UseSubstraction")):
        useSub = fp.UseSubstraction # compatibility with old files
      _tip_ = FreeCAD.Qt.translate("App::Property","Use Subtraction")
      fp.addProperty("App::PropertyBool","UseSubtraction","ParametersExt",_tip_).UseSubtraction = fp.UseSubstraction
    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    face = fp.baseObject[1]

    s = smExtrude(extLength = fp.length.Value,  gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, subtraction = fp.UseSubtraction,
                    offset = fp.Offset.Value, refine = fp.Refine, sketch = fp.Sketch, selFaceNames = face, selObject = Main_Object)
    fp.baseObject[0].ViewObject.Visibility = False
    if fp.Sketch :
      fp.Sketch.ViewObject.Visibility = False
    fp.Shape = s

class SMViewProviderTree:
  "A View provider that nests children objects under the created one"

  def __init__(self, obj):
    obj.Proxy = self
    self.Object = obj.Object

  def attach(self, obj):
    self.Object = obj.Object
    return

  def setupContextMenu(self, viewObject, menu):
    action = menu.addAction(FreeCAD.Qt.translate("QObject", "Edit %1").replace("%1", viewObject.Object.Label))
    action.triggered.connect(lambda: self.startDefaultEditMode(viewObject))
    return False

  def startDefaultEditMode(self, viewObject):
    document = viewObject.Document.Document
    if not document.HasPendingTransaction:
      text = FreeCAD.Qt.translate("QObject", "Edit %1").replace("%1", viewObject.Object.Label)
      document.openTransaction(text)
    viewObject.Document.setEdit(viewObject.Object, 0)

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
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"baseObject"):
      objs.append(self.Object.baseObject[0])
    if hasattr(self.Object,"Sketch"):
      objs.append(self.Object.Sketch)
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_Extrude.svg')

  def setEdit(self,vobj,mode):
    taskd = SMBendWallTaskPanel()
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

class SMViewProviderFlat:
  "A View provider that places objects flat under base object"

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
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"Sketch"):
      objs.append(self.Object.Sketch)
    return objs

  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_Extrude.svg')

  def setEdit(self,vobj,mode):
    taskd = SMBendWallTaskPanel()
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

class SMBendWallTaskPanel:
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
      self.addButton.setIcon(QtGui.QIcon(os.path.join( iconPath , 'SheetMetal_Update.svg')))
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
            if "Face" in elt or "Edge" in elt:
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

class SMExtrudeCommandClass():
  """Extrude face"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SheetMetal_Extrude.svg'), # the name of a svg file available in the resources
            'MenuText': FreeCAD.Qt.translate('SheetMetal','Extend Face'),
            'Accel': "E",
            'ToolTip' : FreeCAD.Qt.translate('SheetMetal','Extends one or more face, on existing sheet metal.\n'
            '1. Select edges or thickness side faces to create walls.\n'
            '2. Select a sketch in property editor to create tabs. \n'
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
    doc.openTransaction("Extend")
    if (activeBody is None):
      a = doc.addObject("Part::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderTree(a.ViewObject)
    else:
      a = doc.addObject("PartDesign::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderFlat(a.ViewObject)
      activeBody.addObject(a)
    SheetMetalBaseCmd.SetViewConfig(a, viewConf)    
    FreeCADGui.Selection.clearSelection()
    doc.recompute()
    doc.commitTransaction()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    if selobj.isDerivedFrom("Sketcher::SketchObject"):
      return False
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) == Part.Vertex :
        return False
    return True

Gui.addCommand('SMExtrudeFace',SMExtrudeCommandClass())
