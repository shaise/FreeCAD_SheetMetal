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

import FreeCAD, Part, os, SheetMetalTools
from FreeCAD import Gui
from PySide import QtCore, QtGui
from SheetMetalJunction import SMJunction

icons_path = SheetMetalTools.icons_path

# add translations path
Gui.addLanguagePath(SheetMetalTools.language_path)
Gui.updateLocale()


class SMJViewProviderTree:
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
    return os.path.join( icons_path , 'SheetMetal_AddJunction.svg')

  def setEdit(self,vobj,mode):
    taskd = SMJunctionTaskPanel()
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

class SMJViewProviderFlat:
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
    return os.path.join( icons_path , 'SheetMetal_AddJunction.svg')

  def setEdit(self,vobj,mode):
    taskd = SMJunctionTaskPanel()
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

class SMJunctionTaskPanel:
    '''A TaskPanel for the Sheetmetal'''
    def __init__(self):

      self.obj = None
      self.form = QtGui.QWidget()
      self.form.setObjectName("SMJunctionTaskPanel")
      self.form.setWindowTitle("Binded edges list")
      self.grid = QtGui.QGridLayout(self.form)
      self.grid.setObjectName("grid")
      self.title = QtGui.QLabel(self.form)
      self.grid.addWidget(self.title, 0, 0, 1, 2)
      self.title.setText("Select new Edge(s) and press Update")

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
        sel = Gui.Selection.getSelectionEx()[0]
        if sel.HasSubObjects:
          obj = sel.Object
          for elt in sel.SubElementNames:
            if "Edge" in elt:
              edge = self.obj.baseObject
              found = False
              if (edge[0] == obj.Name):
                if isinstance(edge[1],tuple):
                  for subf in edge[1]:
                    if subf == elt:
                      found = True
                else:
                  if (edge[1][0] == elt):
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
        #TaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "edges", None))
        self.addButton.setText(QtGui.QApplication.translate("draft", "Update", None))


class AddJunctionCommandClass():
  """Add Junction command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( icons_path , 'SheetMetal_AddJunction.svg'), # the name of a svg file available in the resources
            'MenuText': FreeCAD.Qt.translate('SheetMetal','Make Junction'),
            'Accel': "S, J",
            'ToolTip' : FreeCAD.Qt.translate('SheetMetal','Create a rip where two walls come together on solids.\n'
            '1. Select edge(s) to create rip on corner edge(s).\n'
            '2. Use Property editor to modify parameters')}

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
    doc.openTransaction("Add Junction")
    if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","Junction")
      SMJunction(a)
      a.baseObject = (selobj, sel.SubElementNames)
      SMJViewProviderTree(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","Junction")
      SMJunction(a)
      a.baseObject = (selobj, sel.SubElementNames)
      SMJViewProviderFlat(a.ViewObject)
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
    for selEdge in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selEdge) != Part.Edge :
        return False
    return True

Gui.addCommand("SheetMetal_AddJunction", AddJunctionCommandClass())
