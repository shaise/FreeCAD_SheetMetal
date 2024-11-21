# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalBend.py
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
##############################################################################

import Part, SheetMetalTools, os

smEpsilon = SheetMetalTools.smEpsilon

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = "sm1."
smAddBendDefaults = {}


def smGetClosestVert(vert, face):
    closestVert = None
    closestDist = 99999999
    for v in face.Vertexes:
        if vert.isSame(v):
            continue
        d = vert.distToShape(v)[0]
        if d < closestDist:
            closestDist = d
            closestVert = v
    return closestVert


# we look for a matching inner edge to the selected outer one
# this function finds a single vertex of that edge
def smFindMatchingVert(shape, edge, vertid):
    facelist = shape.ancestorsOfType(edge, Part.Face)
    edgeVerts = edge.Vertexes
    v = edgeVerts[vertid]
    vfacelist = shape.ancestorsOfType(v, Part.Face)

    # find the face that is not in facelist
    for vface in vfacelist:
        if not vface.isSame(facelist[0]) and not vface.isSame(facelist[1]):
            break

    return smGetClosestVert(v, vface)


def smFindEdgeByVerts(shape, vert1, vert2):
    for edge in shape.Edges:
        if vert1.isSame(edge.Vertexes[0]) and vert2.isSame(edge.Vertexes[1]):
            break
        if vert1.isSame(edge.Vertexes[1]) and vert2.isSame(edge.Vertexes[0]):
            break
    else:
        edge = None
    return edge


def smSolidBend(radius=1.0, selEdgeNames="", MainObject=None):
    InnerEdgesToBend = []
    OuterEdgesToBend = []
    for selEdgeName in selEdgeNames:
        edge = MainObject.getElement(SheetMetalTools.getElementFromTNP(selEdgeName))

        facelist = MainObject.ancestorsOfType(edge, Part.Face)

        # find matching inner edge to selected outer one
        v1 = smFindMatchingVert(MainObject, edge, 0)
        v2 = smFindMatchingVert(MainObject, edge, 1)
        matchingEdge = smFindEdgeByVerts(MainObject, v1, v2)
        if matchingEdge is not None:
            InnerEdgesToBend.append(matchingEdge)
            OuterEdgesToBend.append(edge)

    if len(InnerEdgesToBend) > 0:
        # find thickness of sheet by distance from v1 to one of the edges coming out of edge[0]
        # we assume all corners have same thickness
        for dedge in MainObject.ancestorsOfType(edge.Vertexes[0], Part.Edge):
            if not dedge.isSame(edge):
                break

        thickness = v1.distToShape(dedge)[0]

        resultSolid = MainObject.makeFillet(radius, InnerEdgesToBend)
        resultSolid = resultSolid.makeFillet(radius + thickness, OuterEdgesToBend)

    return resultSolid


class SMSolidBend:
    def __init__(self, obj, selobj, sel_elements):
        """ "Add Bend to Solid" """

        self._addProperties(obj)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Base object")
        obj.addProperty(
            "App::PropertyLinkSub", "baseObject", "Parameters", _tip_
        ).baseObject = (selobj, sel_elements)
        obj.Proxy = self
        SheetMetalTools.taskRestoreDefaults(obj, smAddBendDefaults)

    def _addProperties(self, obj):
        SheetMetalTools.smAddLengthProperty(
            obj, "radius", FreeCAD.Qt.translate("App::Property", "Bend Radius"), 1.0
        )
        # SheetMetalTools.smAddBoolProperty(
        #     obj, "Refine", FreeCAD.Qt.translate("App::Property", "Use Refine"), False
        # )

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver

    def execute(self, fp):
        """ "Print a short message when doing a recomputation, this method is mandatory" """
        self._addProperties(fp)
        Main_Object = fp.baseObject[0].Shape.copy()
        s = smSolidBend(
            radius=fp.radius.Value,
            selEdgeNames=fp.baseObject[1],
            MainObject=Main_Object,
        )
        fp.Shape = s


##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    import FreeCAD
    from FreeCAD import Gui
    from PySide import QtCore, QtGui

    icons_path = SheetMetalTools.icons_path

    class SMBendViewProviderTree:
        "A View provider that nests children objects under the created one (Part WB style)"

        def __init__(self, obj):
            obj.Proxy = self
            self.Object = obj.Object

        def attach(self, obj):
            self.Object = obj.Object
            return

        def setupContextMenu(self, viewObject, menu):
            action = menu.addAction(
                FreeCAD.Qt.translate("QObject", "Edit %1").replace(
                    "%1", viewObject.Object.Label
                )
            )
            action.triggered.connect(lambda: self.startDefaultEditMode(viewObject))
            return False

        def startDefaultEditMode(self, viewObject):
            document = viewObject.Document.Document
            if not document.HasPendingTransaction:
                text = FreeCAD.Qt.translate("QObject", "Edit %1").replace(
                    "%1", viewObject.Object.Label
                )
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
                self.Object = doc.getObject(state["ObjectName"])

        def claimChildren(self):
            objs = []
            if hasattr(self.Object, "baseObject"):
                self.Object.baseObject[0].ViewObject.Visibility=False
                objs.append(self.Object.baseObject[0])
            return objs

        def getIcon(self):
            return os.path.join(icons_path, "SheetMetal_AddBend.svg")

        def setEdit(self, vobj, mode):
            taskd = SMBendTaskPanel(vobj.Object)
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, vobj, mode):
            Gui.Control.closeDialog()
            self.Object.baseObject[0].ViewObject.Visibility = False
            self.Object.ViewObject.Visibility = True
            return False

    class SMBendViewProviderFlat:
        "A View provider that place new objects under the base object (Part design WB style)"

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
                import FreeCAD

                doc = FreeCAD.ActiveDocument  # crap
                self.Object = doc.getObject(state["ObjectName"])

        def claimChildren(self):

            return []

        def getIcon(self):
            return os.path.join(icons_path, "SheetMetal_AddBend.svg")

        def setEdit(self, vobj, mode):
            taskd = SMBendTaskPanel(vobj.Object)
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, vobj, mode):
            Gui.Control.closeDialog()
            self.Object.baseObject[0].ViewObject.Visibility = False
            self.Object.ViewObject.Visibility = True
            return False

    class SMBendTaskPanel:
        """A TaskPanel for the Sheetmetal"""

        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("BendCornerPanel.ui")
            SheetMetalTools.taskPopulateSelectionList(
                self.form.tree, self.obj.baseObject
            )
            SheetMetalTools.taskConnectSelection(
                self.form.AddRemove, self.form.tree, self.obj, ["Edge"]
            )
            SheetMetalTools.taskConnectSpin(self, self.form.Radius, "radius")
            # SheetMetalTools.taskConnectCheck(self, self.form.RefineCheckbox, "Refine")

        def isAllowedAlterSelection(self):
            return True

        def isAllowedAlterView(self):
            return True

        def accept(self):
            SheetMetalTools.taskAccept(self, self.form.AddRemove)
            SheetMetalTools.taskSaveDefaults(self.obj, smAddBendDefaults, ["radius"])
            return True
        
        def reject(self):
            SheetMetalTools.taskReject(self, self.form.AddRemove)

        def retranslateUi(self, SMUnfoldTaskPanel):
            # SMUnfoldTaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "Faces", None))
            self.addButton.setText(
                QtGui.QApplication.translate("draft", "Update", None)
            )

    class AddBendCommandClass:
        """Add Solid Bend command"""

        def GetResources(self):
            return {
                "Pixmap": os.path.join(
                    icons_path, "SheetMetal_AddBend.svg"
                ),  # the name of a svg file available in the resources
                "MenuText": FreeCAD.Qt.translate("SheetMetal", "Make Bend"),
                "Accel": "S, B",
                "ToolTip": FreeCAD.Qt.translate(
                    "SheetMetal",
                    "Create Bend where two walls come together on solids\n"
                    "1. Select edge(s) to create bend on corner edge(s).\n"
                    "2. Use Property editor to modify parameters",
                ),
            }

        def Activated(self):
            doc = FreeCAD.ActiveDocument
            view = Gui.ActiveDocument.ActiveView
            activeBody = None
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            viewConf = SheetMetalTools.GetViewConfig(selobj)
            if hasattr(view, "getActiveObject"):
                activeBody = view.getActiveObject("pdbody")
            if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
                return
            doc.openTransaction("Add Bend")
            if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
                newobj = doc.addObject("Part::FeaturePython", "SolidBend")
                SMSolidBend(newobj, selobj, sel.SubElementNames)
                SMBendViewProviderTree(newobj.ViewObject)
            else:
                # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
                newobj = doc.addObject("PartDesign::FeaturePython", "SolidBend")
                SMSolidBend(newobj, selobj, sel.SubElementNames)
                SMBendViewProviderFlat(newobj.ViewObject)
                activeBody.addObject(newobj)
            SheetMetalTools.SetViewConfig(newobj, viewConf)
            if SheetMetalTools.is_autolink_enabled():
                root = SheetMetalTools.getOriginalBendObject(newobj)
                if root:
                    newobj.setExpression("radius", root.Label + ".radius")
            Gui.Selection.clearSelection()
            newobj.baseObject[0].ViewObject.Visibility = False
            dialog = SMBendTaskPanel(newobj)
            doc.recompute()
            Gui.Control.showDialog(dialog)
            return

        def IsActive(self):
            if (
                len(Gui.Selection.getSelection()) < 1
                or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1
            ):
                return False
            #    selobj = Gui.Selection.getSelection()[0]
            for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
                if type(selFace) != Part.Edge:
                    return False
            return True

    Gui.addCommand("SheetMetal_AddBend", AddBendCommandClass())
