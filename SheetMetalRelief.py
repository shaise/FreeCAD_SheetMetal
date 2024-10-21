# -*- coding: utf-8 -*- 
############################################################################### 
# 
#  SheetMetalRelief.py 
# 
#  Copyright 2015 Shai Seger <shaise at gmail dot com> 
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU Lesser General Public 
#  License as published by the Free Software Foundation; either 
#  version 2 of the License, or (at your option) any later version. 
# 
#  This program is distributed in the hope that it will be useful, 
#  but WITHOUT ANY WARRANTY; without even the implied warranty of 
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
#  GNU General Public License for more details. 
# 
#  You should have received a copy of the GNU Lesser General Public 
#  License along with this program; if not, write to the Free Software 
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, 
#  MA 02110-1301, USA. 
# 
# 
###############################################################################

import FreeCAD, Part, os, SheetMetalTools

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'
smEpsilon = SheetMetalTools.smEpsilon

def smMakeFace(vertex, face, edges, relief):

  if  edges[0].Vertexes[0].isSame(vertex) :
    Edgedir1 = edges[0].Vertexes[1].Point - edges[0].Vertexes[0].Point
  else :
    Edgedir1 = edges[0].Vertexes[0].Point - edges[0].Vertexes[1].Point
  Edgedir1.normalize()

  if  edges[1].Vertexes[0].isSame(vertex) :
    Edgedir2 = edges[1].Vertexes[1].Point - edges[1].Vertexes[0].Point
  else :
    Edgedir2 = edges[1].Vertexes[0].Point - edges[1].Vertexes[1].Point
  Edgedir2.normalize()
  normal = face.normalAt(0,0)
  Edgedir3 = normal.cross(Edgedir1)
  Edgedir4 = normal.cross(Edgedir2)

  p1 = vertex.Point
  p2 = p1 + relief * Edgedir1
  p3 = p2 + relief * Edgedir3
  if not(face.isInside(p3,0.0,True)) :
    p3 = p2 + relief * Edgedir3 * -1
  p6 = p1 + relief * Edgedir2
  p5 = p6 + relief * Edgedir4
  if not(face.isInside(p5, 0.0,True)) :
    p5 = p6 + relief * Edgedir4 * -1
  #print([p1,p2,p3,p5,p6,p1])

  e1 = Part.makeLine(p2, p3)
  #Part.show(e1,'e1')
  e2 = Part.makeLine(p5, p6)
  #Part.show(e2,'e2')
  section = e1.section(e2)
  #Part.show(section1,'section1')

  if section.Vertexes :
    wire = Part.makePolygon([p1,p2,p3,p6,p1])
  else :
    p41 = p3 + relief * Edgedir1 * -1
    p42 = p5 + relief * Edgedir2 * -1
    e1 = Part.Line(p3, p41).toShape()
    #Part.show(e1,'e1')
    e2 = Part.Line(p42, p5).toShape()
    #Part.show(e2,'e2')
    section = e1.section(e2)
    #Part.show(section1,'section1')
    p4 = section.Vertexes[0].Point
    wire = Part.makePolygon([p1,p2,p3,p4,p5,p6,p1])

  extface = Part.Face(wire)
  return extface

def smRelief(relief = 2.0, selVertexNames = ' ', MainObject = None):

  resultSolid = MainObject
  for selVertexName in selVertexNames:
    vertex = MainObject.getElement(SheetMetalTools.getElementFromTNP(selVertexName))
    facelist = MainObject.ancestorsOfType(vertex, Part.Face)

    extsolidlist = []
    for face in facelist :
      #Part.show(face,'face')
      edgelist =face.ancestorsOfType(vertex, Part.Edge)
      #for edge in edgelist :
        #Part.show(edge,'edge')
      extface = smMakeFace(vertex, face, edgelist, relief)
      #Part.show(extface,'extface')
      extsolid = extface.extrude(relief * face.normalAt(0,0)*-1)
      extsolidlist.append(extsolid)

    cutsolid = extsolidlist[0].multiFuse(extsolidlist[1:])
    #Part.show(cutsolid,'cutsolid')
    cutsolid = cutsolid.removeSplitter()
    resultSolid = resultSolid.cut(cutsolid)
    #Part.show(resultsolid,'resultsolid')

  return resultSolid


class SMRelief:
  def __init__(self, obj):
    '''"Add Relief to Solid" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    _tip_ = FreeCAD.Qt.translate("App::Property","Relief Size")
    obj.addProperty("App::PropertyLength","relief","Parameters",_tip_).relief = 2.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Base Object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",_tip_).baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    s = smRelief(relief = fp.relief.Value, selVertexNames = fp.baseObject[1], MainObject = Main_Object)
    fp.Shape = s
    SheetMetalTools.HideObjects(fp.baseObject[0])


##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from PySide import QtCore, QtGui
    from FreeCAD import Gui
    
    icons_path = SheetMetalTools.icons_path
    
    # add translations path
    Gui.addLanguagePath(SheetMetalTools.language_path)
    Gui.updateLocale()
    
    
    class SMReliefViewProviderTree:
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
        return objs
    
      def getIcon(self):
        return os.path.join( icons_path , 'SheetMetal_AddRelief.svg')
    
      def setEdit(self,vobj,mode):
        taskd = SMReliefTaskPanel()
        taskd.obj = vobj.Object
        taskd.update()
        self.Object.ViewObject.Visibility=False
        self.Object.baseObject[0].ViewObject.Visibility=True
        Gui.Control.showDialog(taskd)
        return True
    
      def unsetEdit(self,vobj,mode):
        Gui.Control.closeDialog()
        self.Object.baseObject[0].ViewObject.Visibility=False
        self.Object.ViewObject.Visibility=True
        return False
    
    class SMReliefViewProviderFlat:
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
    
        return []
    
      def getIcon(self):
        return os.path.join( icons_path , 'SheetMetal_AddRelief.svg')
    
      def setEdit(self,vobj,mode):
        taskd = SMReliefTaskPanel()
        taskd.obj = vobj.Object
        taskd.update()
        self.Object.ViewObject.Visibility=False
        self.Object.baseObject[0].ViewObject.Visibility=True
        Gui.Control.showDialog(taskd)
        return True
    
      def unsetEdit(self,vobj,mode):
        Gui.Control.closeDialog()
        self.Object.baseObject[0].ViewObject.Visibility=False
        self.Object.ViewObject.Visibility=True
        return False
    
    class SMReliefTaskPanel:
        '''A TaskPanel for the Sheetmetal'''
        def __init__(self):
        
          self.obj = None
          self.form = QtGui.QWidget()
          self.form.setObjectName("SMReliefTaskPanel")
          self.form.setWindowTitle("Binded vertexes list")
          self.grid = QtGui.QGridLayout(self.form)
          self.grid.setObjectName("grid")
          self.title = QtGui.QLabel(self.form)
          self.grid.addWidget(self.title, 0, 0, 1, 2)
          self.title.setText("Select new vertex(es) and press Update")
    
          # tree
          self.tree = QtGui.QTreeWidget(self.form)
          self.grid.addWidget(self.tree, 1, 0, 1, 2)
          self.tree.setColumnCount(2)
          self.tree.setHeaderLabels(["Name","Subelement"])
    
          # buttons
          self.addButton = QtGui.QPushButton(self.form)
          self.addButton.setObjectName("addButton")
          self.addButton.setIcon(QtGui.QIcon(os.path.join( icons_path , 'SheetMetal_Update.svg')))
          self.grid.addWidget(self.addButton, 3, 0, 1, 2)
    
          QtCore.QObject.connect(self.addButton, QtCore.SIGNAL("clicked()"), self.updateElement)
          self.update()
    
        def isAllowedAlterSelection(self):
            return True
    
        def isAllowedAlterView(self):
            return True
    
        def getStandardButtons(self):
            return QtGui.QDialogButtonBox.Ok
    
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
            sel = Gui.Selection.getSelectionEx()[0]
            if sel.HasSubObjects:
              obj = sel.Object
              for elt in sel.SubElementNames:
                if "Vertex" in elt:
                  vertex = self.obj.baseObject
                  found = False
                  if (vertex[0] == obj.Name):
                    if isinstance(vertex[1],tuple):
                      for subf in vertex[1]:
                        if subf == elt:
                          found = True
                    else:
                      if (vertex[1][0] == elt):
                        found = True
                  if not found:
                    self.obj.baseObject = (sel.Object, sel.SubElementNames)
            self.update()
    
        def accept(self):
            FreeCAD.ActiveDocument.recompute()
            Gui.ActiveDocument.resetEdit()
            #self.obj.ViewObject.Visibility=True
            return True

        def retranslateUi(self, TaskPanel):
            #TaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "vertexs", None))
            self.addButton.setText(QtGui.QApplication.translate("draft", "Update", None))


    class AddReliefCommandClass():
      """Add Relief command"""

      def GetResources(self):
        return {'Pixmap'  : os.path.join( icons_path , 'SheetMetal_AddRelief.svg'), # the name of a svg file available in the resources
                'MenuText': FreeCAD.Qt.translate('SheetMetal','Make Relief'),
                'Accel': "S, R",
                'ToolTip' : FreeCAD.Qt.translate('SheetMetal','Modify an Individual solid corner to create Relief.\n'
                '1. Select Vertex(es) to create Relief on Solid corner Vertex(es).\n'
                '2. Use Property editor to modify default parameters')}

      def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        sel = Gui.Selection.getSelectionEx()[0]
        selobj = Gui.Selection.getSelectionEx()[0].Object
        viewConf = SheetMetalTools.GetViewConfig(selobj)
        if hasattr(view,'getActiveObject'):
          activeBody = view.getActiveObject('pdbody')
        if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
            return
        doc.openTransaction("Add Relief")
        if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
          a = doc.addObject("Part::FeaturePython","Relief")
          SMRelief(a)
          a.baseObject = (selobj, sel.SubElementNames)
          SMReliefViewProviderTree(a.ViewObject)
        else:
          #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
          a = doc.addObject("PartDesign::FeaturePython","Relief")
          SMRelief(a)
          a.baseObject = (selobj, sel.SubElementNames)
          SMReliefViewProviderFlat(a.ViewObject)
          activeBody.addObject(a)
        SheetMetalTools.SetViewConfig(a, viewConf)
        Gui.Selection.clearSelection()
        doc.recompute()
        doc.commitTransaction()
        return

      def IsActive(self):
        if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
          return False
    #    selobj = Gui.Selection.getSelection()[0]
        for selVertex in Gui.Selection.getSelectionEx()[0].SubObjects:
          if type(selVertex) != Part.Vertex :
            return False
        return True

    Gui.addCommand("SheetMetal_AddRelief", AddReliefCommandClass())
