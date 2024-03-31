# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalBaseCmd.py
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
###################################################################################

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, Part, os

translate = FreeCAD.Qt.translate

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join(__dir__, "Resources", "icons")

# add translations path
LanguagePath = os.path.join(__dir__, "translations")
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()


def smWarnDialog(msg):
    diag = QtGui.QMessageBox(
        QtGui.QMessageBox.Warning,
        translate("QMessageBox", "Error in macro MessageBox"),
        msg,
    )
    diag.setWindowModality(QtCore.Qt.ApplicationModal)
    diag.exec_()


def smBelongToBody(item, body):
    if body is None:
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False


def smIsSketchObject(obj):
    return str(obj).find("<Sketcher::") == 0


def smIsOperationLegal(body, selobj):
    # FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsSketchObject(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog(
            translate(
                "QMessageBox",
                "The selected geometry does not belong to the active Body.\n"
                "Please make the container of this item active by\n"
                "double clicking on it.",
            )
        )
        return False
    return True


def GetViewConfig(obj):
    return obj.ViewObject.dumpContent()
    viewconf = {}
    viewconf["objShapeCol"] = obj.ViewObject.ShapeColor
    viewconf["objShapeTsp"] = obj.ViewObject.Transparency
    viewconf["objDiffuseCol"] = obj.ViewObject.DiffuseColor
    # TODO: Make the individual face colors be retained
    # needDiffuseColorExtension = ( len(selobj.ViewObject.DiffuseColor) < len(selobj.Shape.Faces) )
    return viewconf


def SetViewConfig(obj, viewconf):
    obj.ViewObject.restoreContent(viewconf)
    #obj.ViewObject.ShapeColor = viewconf["objShapeCol"]
    #obj.ViewObject.Transparency = viewconf["objShapeTsp"]
    #obj.ViewObject.DiffuseColor = viewconf["objDiffuseCol"]


def getOriginalBendObject(obj):
    from SheetMetalCmd import SMBendWall
    from SheetMetalBend import SMSolidBend
    from SheetMetalFoldCmd import SMFoldWall

    for item in obj.OutListRecursive:
        if hasattr(item, "Proxy") and (
            isinstance(item.Proxy, SMBaseBend)
            or isinstance(item.Proxy, SMBendWall)
            or isinstance(item.Proxy, SMSolidBend)
            or isinstance(item.Proxy, SMFoldWall)
        ):
            if not getOriginalBendObject(item):
                return item
    return None


def autolink_enabled():
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
    return FSParam.GetInt("AutoLinkBendRadius", 0)


def modifiedWire(WireList, radius, thk, length, normal, Side, sign):
    # If sketch is one type, make a face by extruding & offset it to correct position
    wire_extr = WireList.extrude(normal * sign * length)
    # Part.show(wire_extr,"wire_extr")

    if Side == "Inside":
        wire_extr = wire_extr.makeOffsetShape(thk / 2.0 * sign, 0.0, fill=False, join=2)
    elif Side == "Outside":
        wire_extr = wire_extr.makeOffsetShape(
            -thk / 2.0 * sign, 0.0, fill=False, join=2
        )
    # Part.show(wire_extr,"wire_extr")
    try:
        filleted_extr = wire_extr.makeFillet((radius + thk / 2.0), wire_extr.Edges)
    except:
        filleted_extr = wire_extr
    # Part.show(filleted_extr,"filleted_extr")
    filleted_extr = filleted_extr.makeOffsetShape(
        thk / 2.0 * sign, 0.0, fill=False, join=2
    )
    # Part.show(filleted_extr,"filleted_extr")
    return filleted_extr


def smBase(
    thk=2.0,
    length=10.0,
    radius=1.0,
    Side="Inside",
    midplane=False,
    reverse=False,
    MainObject=None,
):
    # To Get sketch normal
    WireList = MainObject.Shape.Wires[0]
    mat = MainObject.getGlobalPlacement().Rotation
    normal = (mat.multVec(FreeCAD.Vector(0, 0, 1))).normalize()
    # print([mat, normal])
    if WireList.isClosed():
        # If Closed sketch is there, make a face & extrude it
        sketch_face = Part.makeFace(MainObject.Shape.Wires, "Part::FaceMakerBullseye")
        thk = -1.0 * thk if reverse else thk
        wallSolid = sketch_face.extrude(sketch_face.normalAt(0, 0) * thk)
        if midplane:
            wallSolid = Part.Solid(
                wallSolid.translated(sketch_face.normalAt(0, 0) * thk * -0.5)
            )
    else:
        filleted_extr = modifiedWire(WireList, radius, thk, length, normal, Side, 1.0)
        # Part.show(filleted_extr,"filleted_extr")
        dist = WireList.Vertexes[0].Point.distanceToPlane(
            FreeCAD.Vector(0, 0, 0), normal
        )
        # print(dist)
        slice_wire = filleted_extr.slice(normal, dist)
        # print(slice_wire)
        # Part.show(slice_wire[0],"slice_wire")
        traj = slice_wire[0]
        # Part.show(traj,"traj")
        if midplane:
            traj.translate(normal * -length / 2.0)
        elif reverse:
            traj.translate(normal * -length)
        traj_extr = traj.extrude(normal * length)
        # Part.show(traj_extr,"traj_extr")
        solidlist = []
        for face in traj_extr.Faces:
            solid = face.makeOffsetShape(thk, 0.0, fill=True)
            solidlist.append(solid)
        if len(solidlist) > 1:
            wallSolid = solidlist[0].multiFuse(solidlist[1:])
        else:
            wallSolid = solidlist[0]
        # Part.show(wallSolid,"wallSolid")
    # Part.show(wallSolid,"wallSolid")
    return wallSolid


class SMBaseBend:
    def __init__(self, obj):
        '''"Add wall or Wall with radius bend"'''
        selobj = Gui.Selection.getSelectionEx()[0]

        _tip_ = translate("App::Property", "Bend Radius")
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = 1.0
        _tip_ = translate("App::Property", "Thickness of sheetmetal")
        obj.addProperty(
            "App::PropertyLength", "thickness", "Parameters", _tip_
        ).thickness = 1.0
        _tip_ = translate("App::Property", "Relief Type")
        obj.addProperty(
            "App::PropertyEnumeration", "BendSide", "Parameters", _tip_
        ).BendSide = ["Outside", "Inside", "Middle"]
        _tip_ = translate("App::Property", "Length of wall")
        obj.addProperty(
            "App::PropertyLength", "length", "Parameters", _tip_
        ).length = 100.0
        _tip_ = translate("App::Property", "Wall Sketch object")
        obj.addProperty(
            "App::PropertyLink", "BendSketch", "Parameters", _tip_
        ).BendSketch = selobj.Object
        _tip_ = translate("App::Property", "Extrude Symmetric to Plane")
        obj.addProperty(
            "App::PropertyBool", "MidPlane", "Parameters", _tip_
        ).MidPlane = False
        _tip_ = translate("App::Property", "Reverse Extrusion Direction")
        obj.addProperty(
            "App::PropertyBool", "Reverse", "Parameters", _tip_
        ).Reverse = False
        obj.Proxy = self

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory"'''
        if not hasattr(fp, "MidPlane"):
            _tip_ = translate("App::Property", "Extrude Symmetric to Plane")
            fp.addProperty(
                "App::PropertyBool", "MidPlane", "Parameters", _tip_
            ).MidPlane = False
            _tip_ = translate("App::Property", "Reverse Extrusion Direction")
            fp.addProperty(
                "App::PropertyBool", "Reverse", "Parameters", _tip_
            ).Reverse = False
        s = smBase(
            thk=fp.thickness.Value,
            length=fp.length.Value,
            radius=fp.radius.Value,
            Side=fp.BendSide,
            midplane=fp.MidPlane,
            reverse=fp.Reverse,
            MainObject=fp.BendSketch,
        )

        fp.Shape = s
        obj = Gui.ActiveDocument.getObject(fp.BendSketch.Name)
        if obj:
            obj.Visibility = False


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

    def getDisplayModes(self, obj):
        modes = []
        return modes

    def setDisplayMode(self, mode):
        return mode

    def onChanged(self, vp, prop):
        return

    def __getstate__(self):
        #    return {'ObjectName' : self.Object.Name}
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
        if hasattr(self.Object, "BendSketch"):
            objs.append(self.Object.BendSketch)
        return objs

    def getIcon(self):
        return os.path.join(iconPath, "SheetMetal_AddBase.svg")


class AddBaseCommandClass:
    """Add Base Wall command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                iconPath, "SheetMetal_AddBase.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": translate("SheetMetal", "Make Base Wall"),
            "Accel": "C, B",
            "ToolTip": translate(
                "SheetMetal",
                "Create a sheetmetal wall from a sketch\n"
                "1. Select a Skech to create bends with walls.\n"
                "2. Use Property editor to modify other parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        #    selobj = Gui.Selection.getSelectionEx()[0].Object
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        #    if not smIsOperationLegal(activeBody, selobj):
        #        return
        doc.openTransaction("BaseBend")
        if activeBody is None:
            a = doc.addObject("Part::FeaturePython", "BaseBend")
            SMBaseBend(a)
            SMBaseViewProvider(a.ViewObject)
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "BaseBend")
            SMBaseBend(a)
            SMBaseViewProvider(a.ViewObject)
            activeBody.addObject(a)
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if len(Gui.Selection.getSelection()) != 1:
            return False
        selobj = Gui.Selection.getSelection()[0]
        if not (
            selobj.isDerivedFrom("Sketcher::SketchObject")
            or selobj.isDerivedFrom("PartDesign::ShapeBinder")
            or selobj.isDerivedFrom("PartDesign::SubShapeBinder")
        ):
            return False
        return True


Gui.addCommand("SheetMetal_AddBase", AddBaseCommandClass())
