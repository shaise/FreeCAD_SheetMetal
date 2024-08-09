# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalFoldCmd.py
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

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, Part, os, math

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join(__dir__, "Resources", "icons")
smEpsilon = 0.0000001

# add translations path
LanguagePath = os.path.join(__dir__, "translations")
Gui.addLanguagePath(LanguagePath)
Gui.updateLocale()

import SheetMetalBendSolid
import SheetMetalBaseCmd
from SheetMetalLogger import SMLogger, UnfoldException, BendException, TreeException


def smWarnDialog(msg):
    diag = QtGui.QMessageBox(
        QtGui.QMessageBox.Warning,
        FreeCAD.Qt.translate("QMessageBox", "Error in macro MessageBox"),
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


def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0


def smIsOperationLegal(body, selobj):
    # FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog(
            FreeCAD.Qt.translate(
                "QMessageBox",
                "The selected geometry does not belong to the active Body.\n"
                "Please make the container of this item active by\n"
                "double clicking on it.",
            )
        )
        return False
    return True


def smthk(obj, foldface):
    normal = foldface.normalAt(0, 0)
    theVol = obj.Volume
    if theVol < 0.0001:
        SMLogger.error(
            FreeCAD.Qt.translate(
                "Logger", "Shape is not a real 3D-object or to small for a metal-sheet!"
            )
        )
    else:
        # Make a first estimate of the thickness
        estimated_thk = theVol / (foldface.Area)
    #  p1 = foldface.CenterOfMass
    p1 = foldface.Vertexes[0].Point
    p2 = p1 + estimated_thk * -1.5 * normal
    e1 = Part.makeLine(p1, p2)
    thkedge = obj.common(e1)
    thk = thkedge.Length
    return thk


def smCutFace(Face, obj):
    # find face Modified During loop
    for face in obj.Faces:
        face_common = face.common(Face)
        if face_common.Faces:
            break
    return face


def smFold(
    bendR=0.8,
    bendA=90.0,
    kfactor=1,
    invertbend=False,
    flipped=False,
    unfold=False,
    position="forward",
    bendlinesketch=None,
    selFaceNames="",
    MainObject=None,
):

    import BOPTools.SplitFeatures, BOPTools.JoinFeatures

    FoldShape = MainObject.Shape

    # restrict angle
    if bendA < 0:
        bendA = -bendA
        flipped = not flipped
    if not (unfold):
        if bendlinesketch and bendA > 0.0:
            foldface = FoldShape.getElement(SheetMetalBaseCmd.getElementFromTNP(selFaceNames[0]))
            tool = bendlinesketch.Shape.copy()
            normal = foldface.normalAt(0, 0)
            thk = smthk(FoldShape, foldface)
            #print(thk)

            # if not(flipped) :
            # offset =  thk * kfactor
            # else :
            # offset = thk * (1 - kfactor )
            # adaptive   адаптивний
            if position == "intersection of planes" :
                kfactor = (( bendR ) * math.tan(math.radians(bendA / 2.0)) * 180 / (bendA / 2.0) / math.pi - bendR ) / thk
                print (kfactor)
            unfoldLength = (bendR + kfactor * thk) * bendA * math.pi / 180.0
            neutralRadius = bendR + kfactor * thk
            # neutralLength =  ( bendR + kfactor * thk ) * math.tan(math.radians(bendA / 2.0)) * 2.0
            # offsetdistance = neutralLength - unfoldLength
            # scalefactor = neutralLength / unfoldLength
            # print([neutralRadius, neutralLength, unfoldLength, offsetdistance, scalefactor])

            # To get facedir
            toolFaces = tool.extrude(normal * -thk)
            # Part.show(toolFaces, "toolFaces")
            cutSolid = BOPTools.SplitAPI.slice(
                FoldShape, toolFaces.Faces, "Standard", 0.0
            )
            # Part.show(cutSolid,"cutSolid_check")

            if not (invertbend):
                solid0 = cutSolid.childShapes()[0]
            else:
                solid0 = cutSolid.childShapes()[1]
            cutFaceDir = smCutFace(toolFaces.Faces[0], solid0)
            # Part.show(cutFaceDir,"cutFaceDir")
            facenormal = cutFaceDir.Faces[0].normalAt(0, 0)
            #print(Position)

            if position == "middle" or position == "intersection of planes":
                tool.translate(facenormal * -unfoldLength / 2.0)
                toolFaces = tool.extrude(normal * -thk)
                #print ("middle")
            elif position == "backward":
                tool.translate(facenormal * -unfoldLength)
                toolFaces = tool.extrude(normal * -thk)
                #print ("backward")

            #elif position == "intersection of planes":
                #tool.translate(facenormal * -unfoldLength / 2.0)
                #toolFaces = tool.extrude(normal * -thk)
                #print ("intersection of planes")








            # To get split solid
            solidlist = []
            toolExtr = toolFaces.extrude(facenormal * unfoldLength)
            # Part.show(toolExtr,"toolExtr")
            CutSolids = FoldShape.cut(toolExtr)
            # Part.show(Solids,"Solids")
            solid2list, solid1list = [], []
            for solid in CutSolids.Solids:
                checksolid = toolFaces.common(solid)
                if checksolid.Faces:
                    solid1list.append(solid)
                else:
                    solid2list.append(solid)
            if len(solid1list) > 1:
                solid0 = solid1list[0].multiFuse(solid1list[1:])
            else:
                solid0 = solid1list[0]
            # Part.show(solid0,"solid0")

            if len(solid2list) > 1:
                solid1 = solid2list[0].multiFuse(solid2list[1:])
            else:
                solid1 = solid2list[0]
            # Part.show(solid0,"solid0")
            # Part.show(solid1,"solid1")

            bendEdges = FoldShape.common(tool)
            if tool.Length <= (bendEdges.Edges[0].Length * 1.002):
                FreeCAD.Console.PrintError(
                    "The bend line sketch "
                    + bendlinesketch.Label
                    + " is not overhanging"
                    " the face sufficiently at one end or both, extend to get reliable results for the unfold operation\n"
                )
            # Part.show(bendEdges,"bendEdges")
            bendEdge = bendEdges.Edges[0]

###########################################################################################################################





            if not (flipped):

                    bendR_flip = bendR
            else:
                    bendR_flip = bendR + thk

            if position == "intersection of planes" :
                bendEdge.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))




##############################################################################################################################
            if not (flipped):
                revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) + normal * bendR

                #print ("not flipped")

            else:
                revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) - normal * (
                    thk + bendR
                )

                #print ("flipped")


            revAxisV = bendEdge.valueAt(bendEdge.LastParameter) - bendEdge.valueAt(
                bendEdge.FirstParameter
            )
            revAxisV.normalize()

            # To check sktech line direction
            if (normal.cross(revAxisV).normalize() - facenormal).Length > smEpsilon:
                revAxisV = revAxisV * -1
                # print(revAxisV)
            if flipped:
                revAxisV = revAxisV * -1
                # print(revAxisV)
            # To get bend surface
            #      revLine = Part.LineSegment(tool.Vertexes[0].Point, tool.Vertexes[-1].Point ).toShape()
            #      bendSurf = revLine.revolve(revAxisP, revAxisV, bendA)
            # Part.show(bendSurf,"bendSurf")

            #      bendSurfTest = bendSurf.makeOffsetShape(bendR/2.0, 0.0, fill = False)
            #      #Part.show(bendSurfTest,"bendSurfTest")
            #      offset =  1
            #      if bendSurfTest.Area < bendSurf.Area and not(flipped) :
            #        offset =  -1
            #      elif bendSurfTest.Area > bendSurf.Area and flipped :
            #        offset =  -1
            #      #print(offset)

            # To get bend solid
            flatsolid = FoldShape.cut(solid0)
            flatsolid = flatsolid.cut(solid1)

            # Part.show(flatsolid,"flatsolid")
            flatfaces = foldface.common(flatsolid)
############################################################################################################################################
            if position == "intersection of planes" :
                flatfaces.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
            #Part.show(flatfaces,"flatface")
                solid0.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
                solid1.translate(facenormal * ((-unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
















#############################################################################################################################################
            else :
                solid1.translate(facenormal * (-unfoldLength))

            # Part.show(flatfaces,"flatface")
   #solid1.translate(facenormal * (-unfoldLength))
            # Part.show(solid1,"solid1")
            solid1.rotate(revAxisP, revAxisV, bendA)
            # Part.show(solid1,"rotatedsolid1")
            #      bendSolidlist =[]
            for flatface in flatfaces.Faces:
                bendsolid = SheetMetalBendSolid.bend_solid(
                    flatface, bendEdge, bendR, thk, neutralRadius, revAxisV, flipped
                )
                # Part.show(bendsolid,"bendsolid")
                solidlist.append(bendsolid)
            solidlist.append(solid0)
            solidlist.append(solid1)
            # resultsolid = Part.makeCompound(solidlist)
            # resultsolid = BOPTools.JoinAPI.connect(solidlist)
            resultsolid = solidlist[0].multiFuse(solidlist[1:])
    else:
        if bendlinesketch and bendA > 0.0:
            resultsolid = FoldShape
    Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
    Gui.ActiveDocument.getObject(bendlinesketch.Name).Visibility = False
    return resultsolid


class SMFoldWall:
    def __init__(self, obj):
        '''"Fold / Bend a Sheetmetal with given Bend Radius"'''
        selobj = Gui.Selection.getSelectionEx()

        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Radius")
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = 1.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Angle")
        obj.addProperty("App::PropertyAngle", "angle", "Parameters", _tip_).angle = 90.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Base Object")
        obj.addProperty(
            "App::PropertyLinkSub", "baseObject", "Parameters", _tip_
        ).baseObject = (selobj[0].Object, selobj[0].SubElementNames)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Reference Line List")
        obj.addProperty(
            "App::PropertyLink", "BendLine", "Parameters", _tip_
        ).BendLine = selobj[1].Object
        _tip_ = FreeCAD.Qt.translate("App::Property", "Invert Solid Bend Direction")
        obj.addProperty(
            "App::PropertyBool", "invertbend", "Parameters", _tip_
        ).invertbend = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Neutral Axis Position")
        obj.addProperty(
            "App::PropertyFloatConstraint", "kfactor", "Parameters", _tip_
        ).kfactor = (0.5, 0.0, 1.0, 0.01)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Invert Bend Direction")
        obj.addProperty(
            "App::PropertyBool", "invert", "Parameters", _tip_
        ).invert = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Unfold Bend")
        obj.addProperty(
            "App::PropertyBool", "unfold", "Parameters", _tip_
        ).unfold = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Line Position")
        obj.addProperty(
            "App::PropertyEnumeration", "Position", "Parameters", _tip_
        ).Position = ["intersection of planes", "middle", "backward", "forward"]
        obj.Proxy = self

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory"'''

        if not hasattr(fp, "Position"):
            _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Line Position")
            fp.addProperty(
                "App::PropertyEnumeration", "Position", "Parameters", _tip_
            ).Position = ["intersection of planes", "middle", "backward", "forward"]
        s = smFold(
            bendR=fp.radius.Value,
            bendA=fp.angle.Value,
            flipped=fp.invert,
            unfold=fp.unfold,
            kfactor=fp.kfactor,
            bendlinesketch=fp.BendLine,
            position=fp.Position,
            invertbend=fp.invertbend,
            selFaceNames=fp.baseObject[1],
            MainObject=fp.baseObject[0],
        )
        fp.Shape = s


class SMFoldViewProvider:
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
            import FreeCAD

            doc = FreeCAD.ActiveDocument  # crap
            self.Object = doc.getObject(state["ObjectName"])

    def claimChildren(self):
        objs = []
        if hasattr(self.Object, "baseObject"):
            objs.append(self.Object.baseObject[0])
            objs.append(self.Object.BendLine)
        return objs

    def getIcon(self):
        return os.path.join(iconPath, "SheetMetal_AddFoldWall.svg")


class SMFoldPDViewProvider:
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
            import FreeCAD

            doc = FreeCAD.ActiveDocument  # crap
            self.Object = doc.getObject(state["ObjectName"])

    def claimChildren(self):
        objs = []
        if hasattr(self.Object, "BendLine"):
            objs.append(self.Object.BendLine)
        return objs

    def getIcon(self):
        return os.path.join(iconPath, "SheetMetal_AddFoldWall.svg")


class AddFoldWallCommandClass:
    """Add Fold Wall command"""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(
                iconPath, "SheetMetal_AddFoldWall.svg"
            ),  # the name of a svg file available in the resources
            "MenuText": FreeCAD.Qt.translate("SheetMetal", "Fold a Wall"),
            "Accel": "C, F",
            "ToolTip": FreeCAD.Qt.translate(
                "SheetMetal",
                "Fold a wall of metal sheet\n"
                "1. Select a flat face on sheet metal and\n"
                "2. Select a bend line (sketch) on same face (ends of sketch bend lines must"
                " extend beyond edges of face) to create sheetmetal fold.\n"
                "3. Use Property editor to modify other parameters",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        selobj = Gui.Selection.getSelectionEx()[0].Object
        viewConf = SheetMetalBaseCmd.GetViewConfig(selobj)
        if hasattr(view, "getActiveObject"):
            activeBody = view.getActiveObject("pdbody")
        if not smIsOperationLegal(activeBody, selobj):
            return
        doc.openTransaction("Bend")
        if activeBody is None or not smIsPartDesign(selobj):
            a = doc.addObject("Part::FeaturePython", "Fold")
            SMFoldWall(a)
            SMFoldViewProvider(a.ViewObject)
        else:
            # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython", "Fold")
            SMFoldWall(a)
            SMFoldPDViewProvider(a.ViewObject)
            activeBody.addObject(a)
        SheetMetalBaseCmd.SetViewConfig(a, viewConf)
        if SheetMetalBaseCmd.autolink_enabled():
            root = SheetMetalBaseCmd.getOriginalBendObject(a)
            if root:
                a.setExpression("radius", root.Label + ".radius")
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if len(Gui.Selection.getSelection()) < 2:
            return False
        selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
        if type(selFace) != Part.Face:
            return False
        selobj = Gui.Selection.getSelection()[1]
        if selobj.isDerivedFrom("App::Link"):
            selobj = selobj.LinkedObject
        elif selobj.isDerivedFrom("Part::Part2DObject"):
            selobj = selobj.Objects[0]
        if not (selobj.isDerivedFrom("Sketcher::SketchObject")):
            return False
        return True


Gui.addCommand("SheetMetal_AddFoldWall", AddFoldWallCommandClass())
