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
    if (body == None):
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
 
def smStrEdge(e):
    return "[" + str(e.valueAt(e.FirstParameter)) + " , " + str(e.valueAt(e.LastParameter)) + "]"

def smMakeRelifFace(edge, dir, gap, reliefW, reliefD, reliefType):
    p1 = edge.valueAt(edge.FirstParameter + gap)
    p2 = edge.valueAt(edge.FirstParameter + gap + reliefW )
    if reliefType == "Round" and reliefD > reliefW :
      p3 = edge.valueAt(edge.FirstParameter + gap + reliefW) + dir.normalize() * (reliefD-reliefW/2)
      p34 = edge.valueAt(edge.FirstParameter + gap + reliefW/2) + dir.normalize() * reliefD
      p4 = edge.valueAt(edge.FirstParameter + gap) + dir.normalize() * (reliefD-reliefW/2)
      e1 = Part.makeLine(p1, p2)
      e2 = Part.makeLine(p2, p3)
      e3 = Part.Arc(p3, p34, p4).toShape()
      e4 = Part.makeLine(p4, p1)	
    else :
      p3 = edge.valueAt(edge.FirstParameter + gap + reliefW) + dir.normalize() * reliefD
      p4 = edge.valueAt(edge.FirstParameter + gap) + dir.normalize() * reliefD
      e1 = Part.makeLine(p1, p2)
      e2 = Part.makeLine(p2, p3)
      e3 = Part.makeLine(p3, p4)
      e4 = Part.makeLine(p4, p1)

    w = Part.Wire([e1,e2,e3,e4])
    return Part.Face(w)
 
def smMakeFace(edge, dir, gap1, gap2, extLen, angle1=0.0, angle2=0.0):
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
    return Part.Face(w)
    
def smRestrict(var, fromVal, toVal):
    if var < fromVal:
      return fromVal
    if var > toVal:
      return toVal
    return var

def smBend(bendR = 1.0, bendA = 90.0, miterA1 =0.0,miterA2 =0.0, flipped = False, extLen = 10.0, gap1 = 0.0, gap2 = 0.0, reliefType = "Rectangle", 
            reliefW = 0.5, reliefD = 1.0, extend1 = 0.0, extend2 = 0.0, selFaceNames = '', MainObject = None):
            
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
      #FreeCAD.Console.PrintLog("=>" + str(lastp)+", "+ str(lenEdge.valueAt(firstp)) +", "+ str(lenEdge.valueAt(lastp)) + ", " + str(p0) + "\n")
      if (lenEdge.valueAt(firstp) - p0).Length < smEpsilon:
        revAxisV = lenEdge.valueAt(lastp) - lenEdge.valueAt(firstp)
        break
      if (lenEdge.valueAt(lastp) - p0).Length < smEpsilon:
        revAxisV = lenEdge.valueAt(firstp) - lenEdge.valueAt(lastp)
        break
     
    # narrow the wall if we have gaps
    revDir = revAxisV.normalize()
    if gap1 == 0 and gap2 == 0:
      revFace = selFace
    else:
      revFace = smMakeFace(lenEdge, thkDir, gap1, gap2, thk)
      if (revFace.normalAt(0,0) != selFace.normalAt(0,0)):
        revFace.reverse()
    
    #make sure the direction verctor is correct in respect to the normal
    if (thkDir.cross(revAxisV).normalize() - selFace.normalAt(0,0)).Length < smEpsilon:
      revAxisV = revAxisV * -1
    
    # remove relief if needed
    if reliefW > 0 and reliefD > 0 and (gap1 > 0 or gap2 > 0) :
      reliefFace = smMakeRelifFace(lenEdge, selFace.normalAt(0,0)* -1, gap1-reliefW, reliefW, reliefD, reliefType)
      reliefFace = reliefFace.fuse(smMakeRelifFace(lenEdge, selFace.normalAt(0,0)* -1, len-gap2, reliefW, reliefD, reliefType))
      reliefSolid = reliefFace.extrude(thkDir.normalize() * thk)
      #Part.show(reliefSolid)
      resultSolid = resultSolid.cut(reliefSolid)

    # restrict angle
    if (bendA < 0):
        bendA = -bendA
        flipped = not flipped
            
    #find revolve point
    if not(flipped):
      revAxisP = thkEdge.valueAt(thkEdge.LastParameter + bendR)
      revAxisV = revAxisV * -1
    else:
      revAxisP = thkEdge.valueAt(thkEdge.FirstParameter - bendR)  
    
    if bendA > 0.0 :
    # create bend	
      bendSolid = revFace.revolve(revAxisP, revAxisV, bendA)
      #Part.show(bendSolid)
      resultSolid = resultSolid.fuse(bendSolid)

    if extLen > 0 :
	# create wall
      Wall_face = smMakeFace(lenEdge, revFace.normalAt(0,0), gap1-extend1, gap2-extend2, extLen, miterA1, miterA2)
      wallSolid = Wall_face.extrude(thkDir.normalize() * thk)
      #Part.show(wallSolid)	  
      wallSolid.rotate(revAxisP, revAxisV, bendA)
      resultSolid = resultSolid.fuse(wallSolid)
      
  Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  return resultSolid
  
class SMBendWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    
    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 10.0
    obj.addProperty("App::PropertyDistance","gap1","Parameters","Gap from left side").gap1 = 0.0
    obj.addProperty("App::PropertyDistance","gap2","Parameters","Gap from right side").gap2 = 0.0
    obj.addProperty("App::PropertyDistance","extend1","Parameters","Gap from left side").extend1 = 0.0
    obj.addProperty("App::PropertyDistance","extend2","Parameters","Gap from right side").extend2 = 0.0	
    obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
    obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
    obj.addProperty("App::PropertyAngle","miterangle1","Parameters","Bend miter angle").miterangle1 = 0.0
    obj.addProperty("App::PropertyAngle","miterangle2","Parameters","Bend miter angle").miterangle2 = 0.0
    obj.addProperty("App::PropertyEnumeration", "reliefType", "Parameters","Relief Type").reliefType = ["Rectangle", "Round"]
    obj.addProperty("App::PropertyLength","reliefw","Parameters","Relief width").reliefw = 0.5
    obj.addProperty("App::PropertyLength","reliefd","Parameters","Relief depth").reliefd = 1.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self
 
  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    if (not hasattr(fp,"miterangle1")):
      fp.addProperty("App::PropertyAngle","miterangle1","Parameters","Bend miter angle").miterangle1 = 0.0
      fp.addProperty("App::PropertyAngle","miterangle2","Parameters","Bend miter angle").miterangle2 = 0.0

    if (not hasattr(fp,"reliefType")):
      fp.addProperty("App::PropertyEnumeration", "reliefType", "Parameters","Relief Type").reliefType = ["Rectangle", "Round"]

    if (not hasattr(fp,"extend1")):
      fp.addProperty("App::PropertyDistance","extend1","Parameters","Gap from left side").extend1 = 0.0
      fp.addProperty("App::PropertyDistance","extend2","Parameters","Gap from right side").extend2 = 0.0	
   
    # restrict some params
    fp.miterangle1.Value = smRestrict(fp.miterangle1.Value, -80.0, 80.0)
    fp.miterangle2.Value = smRestrict(fp.miterangle2.Value, -80.0, 80.0)
    
    s = smBend(bendR = fp.radius.Value, bendA = fp.angle.Value, miterA1 = fp.miterangle1.Value, miterA2 = fp.miterangle2.Value, flipped = fp.invert, extLen = fp.length.Value, 
                gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefType = fp.reliefType, reliefW = fp.reliefw.Value, reliefD = fp.reliefd.Value, 
                extend1 = fp.extend1.Value, extend2 = fp.extend2.Value, selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s


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
    if isinstance(self.Object.Proxy,SMBendWall):
      return os.path.join( iconPath , 'AddWall.svg')
    elif isinstance(self.Object.Proxy,SMExtrudeWall):
      return os.path.join( iconPath , 'SMExtrude.svg')
      
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

  def __setstate__(self,state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    objs = []
    return objs
 
  def getIcon(self):
    if isinstance(self.Object.Proxy,SMBendWall):
      return os.path.join( iconPath , 'AddWall.svg')
    elif isinstance(self.Object.Proxy,SMExtrudeWall):
      return os.path.join( iconPath , 'SMExtrude.svg')

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
    '''A TaskPanel for the facebinder'''
    def __init__(self):
        
        self.obj = None
        self.form = QtGui.QWidget()
        self.form.setObjectName("SMBendWallTaskPanel")
        self.form.setWindowTitle("Binded faces list")
        self.grid = QtGui.QGridLayout(self.form)
        self.grid.setObjectName("grid")
        self.title = QtGui.QLabel(self.form)
        self.grid.addWidget(self.title, 0, 0, 1, 2)
        self.title.setText("Select new face(s) and press Update")

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
      SMViewProviderTree(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","Bend")
      SMBendWall(a)
      SMViewProviderFlat(a.ViewObject)
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
    s = smBend(bendA = 0.0, extLen = fp.length.Value, gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefW = 0.0,
                selFaceNames = fp.baseObject[1], MainObject = fp.baseObject[0])
    fp.Shape = s
    

class SMExtrudeCommandClass():
  """Extrude face"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SMExtrude.svg') , # the name of a svg file available in the resources
            'MenuText': "Extend Face" ,
            'ToolTip' : "Extend a face along normal"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return      
    doc.openTransaction("Extend")
    if (activeBody == None):
      a = doc.addObject("Part::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderTree(a.ViewObject)
    else:
      a = doc.addObject("PartDesign::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderFlat(a.ViewObject)
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
