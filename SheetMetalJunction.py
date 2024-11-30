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

import FreeCAD
import Part
import os
import SheetMetalTools

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'
smJunctionDefaults = {}


def smJunction(gap=2.0, selEdgeNames='', MainObject=None):
    import BOPTools.SplitFeatures
    import BOPTools.JoinFeatures

    resultSolid = MainObject
    for selEdgeName in selEdgeNames:
        edge = MainObject.getElement(
            SheetMetalTools.getElementFromTNP(selEdgeName))

        facelist = MainObject.ancestorsOfType(edge, Part.Face)
        # for face in facelist :
        #  Part.show(face,'face')

        joinface = facelist[0].fuse(facelist[1])
        # Part.show(joinface,'joinface')
        filletedface = joinface.makeFillet(gap, joinface.Edges)
        # Part.show(filletedface,'filletedface')

        cutface1 = facelist[0].cut(filletedface)
        # Part.show(cutface1,'cutface1')
        offsetsolid1 = cutface1.makeOffsetShape(-gap, 0.0, fill=True)
        # Part.show(offsetsolid1,'offsetsolid1')

        cutface2 = facelist[1].cut(filletedface)
        # Part.show(cutface2,'cutface2')
        offsetsolid2 = cutface2.makeOffsetShape(-gap, 0.0, fill=True)
        # Part.show(offsetsolid2,'offsetsolid2')
        cutsolid = offsetsolid1.fuse(offsetsolid2)
        # Part.show(cutsolid,'cutsolid')
        resultSolid = resultSolid.cut(cutsolid)
        # Part.show(resultsolid,'resultsolid')

    return resultSolid


class SMJunction:
    def __init__(self, obj, selobj, sel_items):
        '''"Add Gap to Solid" '''

        _tip_ = FreeCAD.Qt.translate("App::Property", "Junction Gap")
        obj.addProperty("App::PropertyLength", "gap",
                        "Parameters", _tip_).gap = 2.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Base Object")
        obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",
                        _tip_).baseObject = (selobj, sel_items)
        obj.Proxy = self
        SheetMetalTools.taskRestoreDefaults(obj, smJunctionDefaults)

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory" '''
        # pass selected object shape
        Main_Object = fp.baseObject[0].Shape.copy()
        s = smJunction(gap=fp.gap.Value,
                       selEdgeNames=fp.baseObject[1], MainObject=Main_Object)
        fp.Shape = s
        SheetMetalTools.smHideObjects(fp.baseObject[0])


##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from FreeCAD import Gui
    from PySide import QtCore, QtGui

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
            action = menu.addAction(FreeCAD.Qt.translate(
                "QObject", "Edit %1").replace("%1", viewObject.Object.Label))
            action.triggered.connect(
                lambda: self.startDefaultEditMode(viewObject))
            return False

        def startDefaultEditMode(self, viewObject):
            document = viewObject.Document.Document
            if not document.HasPendingTransaction:
                text = FreeCAD.Qt.translate("QObject", "Edit %1").replace(
                    "%1", viewObject.Object.Label)
                document.openTransaction(text)
            viewObject.Document.setEdit(viewObject.Object, 0)

        def updateData(self, fp, prop):
            return

        def getDisplayModes(self, obj):
            modes = []
            return modes

        def setDisplayMode(self, mode):
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
                doc = FreeCAD.ActiveDocument  # crap
                self.Object = doc.getObject(state['ObjectName'])

        def claimChildren(self):
            objs = []
            if hasattr(self.Object, "baseObject"):
                objs.append(self.Object.baseObject[0])
            return objs

        def getIcon(self):
            return os.path.join(icons_path, 'SheetMetal_AddJunction.svg')

        def setEdit(self, vobj, mode):
            taskd = SMJunctionTaskPanel(vobj.Object)
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, vobj, mode):
            Gui.Control.closeDialog()
            self.Object.baseObject[0].ViewObject.Visibility = False
            self.Object.ViewObject.Visibility = True
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

        def getDisplayModes(self, obj):
            modes = []
            return modes

        def setDisplayMode(self, mode):
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
                doc = FreeCAD.ActiveDocument
                self.Object = doc.getObject(state['ObjectName'])

        def claimChildren(self):
            return []

        def getIcon(self):
            return os.path.join(icons_path, 'SheetMetal_AddJunction.svg')

        def setEdit(self, vobj, mode):
            taskd = SMJunctionTaskPanel(vobj.Object)
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, vobj, mode):
            Gui.Control.closeDialog()
            self.Object.baseObject[0].ViewObject.Visibility = False
            self.Object.ViewObject.Visibility = True
            return False

    class SMJunctionTaskPanel:
        '''A TaskPanel for the Sheetmetal addJunction command'''

        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("AddJunctionPanel.ui")
            SheetMetalTools.taskPopulateSelectionList(
                self.form.tree, self.obj.baseObject
            )
            SheetMetalTools.taskConnectSelection(
                self.form.AddRemove, self.form.tree, self.obj, ["Edge"]
            )
            SheetMetalTools.taskConnectSpin(self, self.form.JunctionWidth, "gap")
            # SheetMetalTools.taskConnectCheck(self, self.form.RefineCheckbox, "Refine")

        def isAllowedAlterSelection(self):
            return True

        def isAllowedAlterView(self):
            return True

        def accept(self):
            SheetMetalTools.taskAccept(self, self.form.AddRemove)
            SheetMetalTools.taskSaveDefaults(self.obj, smJunctionDefaults, ["gap"])
            return True
        
        def reject(self):
            SheetMetalTools.taskReject(self, self.form.AddRemove)

        def retranslateUi(self, TaskPanel):
            self.addButton.setText(
                QtGui.QApplication.translate("draft", "Update", None))

    class AddJunctionCommandClass():
        """Add Junction command"""

        def GetResources(self):
            return {'Pixmap': os.path.join(icons_path, 'SheetMetal_AddJunction.svg'),  # the name of a svg file available in the resources
                    'MenuText': FreeCAD.Qt.translate('SheetMetal', 'Make Junction'),
                    'Accel': "S, J",
                    'ToolTip': FreeCAD.Qt.translate('SheetMetal', 'Create a rip where two walls come together on solids.\n'
                                                    '1. Select edge(s) to create rip on corner edge(s).\n'
                                                    '2. Use Property editor to modify parameters')}

        def Activated(self):
            doc = FreeCAD.ActiveDocument
            view = Gui.ActiveDocument.ActiveView
            activeBody = None
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = Gui.Selection.getSelectionEx()[0].Object
            viewConf = SheetMetalTools.GetViewConfig(selobj)
            if hasattr(view, 'getActiveObject'):
                activeBody = view.getActiveObject('pdbody')
            if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
                return
            doc.openTransaction("Add Junction")
            if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
                newObj = doc.addObject("Part::FeaturePython", "Junction")
                SMJunction(newObj, selobj, sel.SubElementNames)
                SMJViewProviderTree(newObj.ViewObject)
            else:
                # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
                newObj = doc.addObject("PartDesign::FeaturePython", "Junction")
                SMJunction(newObj, selobj, sel.SubElementNames)
                SMJViewProviderFlat(newObj.ViewObject)
                activeBody.addObject(newObj)
            SheetMetalTools.SetViewConfig(newObj, viewConf)
            Gui.Selection.clearSelection()
            newObj.baseObject[0].ViewObject.Visibility = False
            dialog = SMJunctionTaskPanel(newObj)
            doc.recompute()
            Gui.Control.showDialog(dialog)
            return

        def IsActive(self):
            if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
                return False
    #    selobj = Gui.Selection.getSelection()[0]
            for selEdge in Gui.Selection.getSelectionEx()[0].SubObjects:
                if type(selEdge) != Part.Edge:
                    return False
            return True

    Gui.addCommand("SheetMetal_AddJunction", AddJunctionCommandClass())
