# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalExtendCmd.py
#
#  Copyright 2020 Jaise James <jaisekjames at gmail dot com>
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

import math
import os
import FreeCAD
import Part
from FreeCAD import Base
import SheetMetalTools

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = "sm1."
smEpsilon = SheetMetalTools.smEpsilon

# list of properties to be saved as defaults
smExtrudeDefaultVars = ["Refine"]


def smMakeFace(edge, dir, extLen, gap1=0.0, gap2=0.0, angle1=0.0, angle2=0.0, op=""):
    len1 = extLen * math.tan(math.radians(angle1))
    len2 = extLen * math.tan(math.radians(angle2))

    p1 = edge.valueAt(edge.LastParameter - gap2)
    p2 = edge.valueAt(edge.FirstParameter + gap1)
    p3 = edge.valueAt(edge.FirstParameter + gap1 + len1) + dir.normalize() * extLen
    p4 = edge.valueAt(edge.LastParameter - gap2 - len2) + dir.normalize() * extLen

    e2 = Part.makeLine(p2, p3)
    e4 = Part.makeLine(p4, p1)
    section = e4.section(e2)

    if section.Vertexes:
        p5 = section.Vertexes[0].Point
        w = Part.makePolygon([p1, p2, p5, p1])
    else:
        w = Part.makePolygon([p1, p2, p3, p4, p1])
    face = Part.Face(w)
    if hasattr(face, "mapShapes"):
        face.mapShapes([(edge, face)], None, op)
    return face

def smTouchFace(Face, obj, thk):
    # find face Modified During loop
    # Part.show(Face,'Face')
    facelist = []
    for face in obj.Faces:
        # Part.show(face,'face')
        face_common = face.common(Face)
        if not (face_common.Faces):
            continue
        edge = face.Vertexes[0].extrude(face.normalAt(0, 0) * -thk * 2)
        # Part.show(edge,'edge')
        edge_common = obj.common(edge)
        # Part.show(edge_common,'edge_common')
        if (edge_common.Edges[0].Length - thk) < smEpsilon:
            facelist.append(face)
            break
    return facelist[0]


def smgetSubface(face, obj, edge, thk):
    # Project thickness side edge to get one side rectangle
    normal = face.normalAt(0, 0)
    faceVert = face.Vertexes[0].Point
    pt1 = edge.Vertexes[0].Point.projectToPlane(faceVert, normal)
    pt2 = edge.Vertexes[1].Point.projectToPlane(faceVert, normal)
    vec1 = pt2 - pt1

    # find min & max point of cut shape
    wallsolidlist = []
    for solid in obj.Solids:
        pt_list = []
        for vertex in solid.Vertexes:
            poi = vertex.Point
            pt = poi.projectToPlane(faceVert, normal)
            pt_list.append(pt)
        p1 = Base.Vector(
            min([pts.x for pts in pt_list]),
            min([pts.y for pts in pt_list]),
            min([pts.z for pts in pt_list]),
        )
        p2 = Base.Vector(
            max([pts.x for pts in pt_list]),
            max([pts.y for pts in pt_list]),
            max([pts.z for pts in pt_list]),
        )
        # print([p1, p2])

        # Find angle between diagonal & thickness side edge
        vec2 = p2 - p1
        angle1 = vec2.getAngle(vec1)
        angle = math.degrees(angle1)
        # print(angle)

        # Check & correct orientation of diagonal edge rotation
        e = Part.makeLine(p1, p2)
        e.rotate(p1, normal, -angle)
        vec2 = (e.valueAt(e.LastParameter) - e.valueAt(e.FirstParameter)).normalize()
        coeff = vec2.dot(vec1.normalize())
        # print(coeff)
        if coeff != 1.0:
            angle = 90 - angle

        # Create Cut Rectangle Face from min/max points & angle
        e = Part.Line(p1, p2).toShape()
        e1 = e.copy()
        e1.rotate(p1, normal, -angle)
        e2 = e.copy()
        e2.rotate(p2, normal, 90 - angle)
        section1 = e1.section(e2)
        # Part.show(section1,'section1')
        p3 = section1.Vertexes[0].Point
        e3 = e.copy()
        e3.rotate(p1, normal, 90 - angle)
        e4 = e.copy()
        e4.rotate(p2, normal, -angle)
        section2 = e3.section(e4)
        # Part.show(section2,'section2')
        p4 = section2.Vertexes[0].Point
        w = Part.makePolygon([p1, p3, p2, p4, p1])
        # Part.show(w, "wire")
        face = Part.Face(w)
        wallSolid = face.extrude(normal * -thk)
        wallsolidlist.append(wallSolid)
    return wallsolidlist


def smExtrude(
    extLength=10.0,
    gap1=0.0,
    gap2=0.0,
    subtraction=False,
    offset=0.02,
    refine=True,
    sketch="",
    selFaceNames="",
    selObject="",
):

    import BOPTools.SplitFeatures

    finalShape = selObject
    for selFaceName in selFaceNames:
        selItem = selObject.getElement(SheetMetalTools.getElementFromTNP(selFaceName))
        selFace = SheetMetalTools.smGetFaceByEdge(selItem, selObject)

        # find the narrow edge
        thk = 999999.
        thkEdge = None
        for edge in selFace.Edges:
            if abs(edge.Length) < thk:
                thk = abs(edge.Length)
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
        for Cface in list2:
            if not (Cface.isSame(selFace)):
                break
        # Part.show(Cface, "Cface")

        # Main Length Edge, Extrusion direction
        #    MlenEdge = lenEdge
        #    leng = MlenEdge.Length
        pThkDir1 = selFace.CenterOfMass
        pThkDir2 = lenEdge.Curve.value(lenEdge.Curve.parameter(pThkDir1))
        thkDir = pThkDir1.sub(pThkDir2).normalize()
        FaceDir = selFace.normalAt(0, 0)

        # if sketch is as wall
        sketches = False
        if sketch:
            if sketch.Shape.Wires[0].isClosed():
                sketches = True
            else:
                pass

        # Split solid Based on Top Face into two solid
        Topface_Solid = Cface.Wires[0].extrude(Cface.normalAt(0, 0) * -thk)
        # Part.show(Topface_Solid,"Topface_Solid")
        SplitSolids = BOPTools.SplitAPI.slice(
            finalShape, Topface_Solid.Faces, "Standard", 0.0
        )
        # Part.show(SplitSolids,"SplitSolids")
        for SplitSolid in SplitSolids.Solids:
            check_face = SplitSolid.common(Cface)
            if check_face.Faces:
                SplitSolid1 = SplitSolid
                break
        # Part.show(SplitSolid1,"SplitSolid1")
        for SplitSolid in SplitSolids.Solids:
            if not (SplitSolid.isSame(SplitSolid1)):
                SplitSolid2 = SplitSolid
                break
        # Part.show(SplitSolid2, "SplitSolid2")

        # Make solid from sketch, if sketch is present
        solidlist = []
        if sketches:
            Wall_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
            check_face = Wall_face.common(Cface)
            if not (check_face.Faces):
                thkDir = thkDir * -1
            wallSolid = Wall_face.extrude(thkDir * thk)
            # Part.show(wallSolid, "wallSolid")
            solidlist.append(wallSolid)

            # To find Overlapping Solid, non thickness side Face that touch Overlapping Solid
            overlap_solid = wallSolid.common(SplitSolid2)
            # Part.show(overlap_solid, "overlap_solid")

            overlap_solidlist = []
            if overlap_solid.Faces:
                substract_face = smTouchFace(wallSolid, SplitSolid2, thk)
                # Part.show(substract_face, "substract_face")
                # To get solids that aligned/normal to touching face
                overlap_solidlist = smgetSubface(
                    substract_face, overlap_solid, lenEdge, thk
                )

            # Substract solid from Initial Solid
            if subtraction:
                for solid in overlap_solidlist:
                    CutSolid = solid.makeOffsetShape(offset, 0.0, fill=False, join=2)
                    # Part.show(CutSolid, "CutSolid")
                    finalShape = finalShape.cut(CutSolid)
                    # Part.show(finalShape,"finalShape")

        elif extLength > 0.0:
            # create wall, if edge or face selected
            Wall_face = smMakeFace(lenEdge, FaceDir, extLength, gap1, gap2, op="SMW")
            wallSolid = Wall_face.extrude(thkDir * thk)
            # Part.show(wallSolid,"wallSolid")
            solidlist.append(wallSolid)

        # Fuse All solid created to Split solid
        if len(solidlist) > 0:
            resultSolid = SplitSolid1.fuse(solidlist[0])
            # Part.show(resultSolid,"resultSolid")

            # Merge final list
            finalShape = finalShape.cut(resultSolid)
            # Part.show(finalShape,"finalShape")
            finalShape = finalShape.fuse(resultSolid)

    # Part.show(finalShape,"finalShape")
    if refine:
        finalShape = finalShape.removeSplitter()
    return finalShape


class SMExtrudeWall:
    def __init__(self, obj, selobj, sel_items):
        """ "Add Sheetmetal Wall by Extending" """

        _tip_ = FreeCAD.Qt.translate("App::Property", "Length of Wall")
        obj.addProperty("App::PropertyLength", "length", "Parameters", _tip_).length = (
            10.0
        )
        _tip_ = FreeCAD.Qt.translate("App::Property", "Gap from left side")
        obj.addProperty("App::PropertyDistance", "gap1", "Parameters", _tip_).gap1 = 0.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Gap from right side")
        obj.addProperty("App::PropertyDistance", "gap2", "Parameters", _tip_).gap2 = 0.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Base object")
        obj.addProperty(
            "App::PropertyLinkSub", "baseObject", "Parameters", _tip_
        ).baseObject = (selobj, sel_items)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Wall Sketch")
        obj.addProperty("App::PropertyLink", "Sketch", "ParametersExt", _tip_)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Use Subtraction")
        obj.addProperty(
            "App::PropertyBool", "UseSubtraction", "ParametersExt", _tip_
        ).UseSubtraction = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Offset for subtraction")
        obj.addProperty(
            "App::PropertyDistance", "Offset", "ParametersExt", _tip_
        ).Offset = 0.02
        _tip_ = FreeCAD.Qt.translate("App::Property", "Use Refine")
        obj.addProperty(
            "App::PropertyBool", "Refine", "ParametersExt", _tip_
        ).Refine = True
        obj.Proxy = self
        SheetMetalTools.taskRestoreDefaults(obj, smExtrudeDefaultVars)
    
    def addVerifyProperties(self, obj):
        pass

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver

    def execute(self, fp):
        if not hasattr(fp, "Sketch"):
            _tip_ = FreeCAD.Qt.translate("App::Property", "Wall Sketch")
            fp.addProperty("App::PropertyLink", "Sketch", "ParametersExt", _tip_)
            _tip_ = FreeCAD.Qt.translate("App::Property", "Use Subtraction")
            fp.addProperty(
                "App::PropertyDistance", "Offset", "ParametersExt", _tip_
            ).Offset = 0.02
            _tip_ = FreeCAD.Qt.translate("App::Property", "Use Refine")
            fp.addProperty(
                "App::PropertyBool", "Refine", "ParametersExt", _tip_
            ).Refine = False
        if not hasattr(fp, "UseSubtraction"):
            useSub = False
            if hasattr(fp, "UseSubstraction"):
                useSub = fp.UseSubstraction  # compatibility with old files
            _tip_ = FreeCAD.Qt.translate("App::Property", "Use Subtraction")
            fp.addProperty(
                "App::PropertyBool", "UseSubtraction", "ParametersExt", _tip_
            ).UseSubtraction = fp.UseSubstraction
        # pass selected object shape
        Main_Object = fp.baseObject[0].Shape.copy()
        face = fp.baseObject[1]

        s = smExtrude(
            extLength=fp.length.Value,
            gap1=fp.gap1.Value,
            gap2=fp.gap2.Value,
            subtraction=fp.UseSubtraction,
            offset=fp.Offset.Value,
            refine=fp.Refine,
            sketch=fp.Sketch,
            selFaceNames=face,
            selObject=Main_Object,
        )
        fp.Shape = s


##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from FreeCAD import Gui
    from PySide import QtCore, QtGui

    icons_path = SheetMetalTools.icons_path

    class SMViewProviderTree(SheetMetalTools.SMViewProvider):
        ''' Part WB style ViewProvider '''        
        def getIcon(self):
            return os.path.join(icons_path, "SheetMetal_Extrude.svg")
        
        def getTaskPanel(self, obj):
            return SMExtendWallTaskPanel(obj)
        
    class SMViewProviderFlat(SMViewProviderTree):
        ''' Part Design WB style ViewProvider - backward compatibility only''' 


    class SMExtendWallTaskPanel:
        """A TaskPanel for the Sheetmetal"""

        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("ExtendTaskPanel.ui")
            obj.Proxy.addVerifyProperties(obj) # Make sure all properties are added
            SheetMetalTools.taskConnectSelection(
                self.form.AddRemove, self.form.tree, self.obj, ["Face"], self.form.pushClearSel
            )
            SheetMetalTools.taskConnectSpin(self, self.form.OffsetA, "gap1")
            SheetMetalTools.taskConnectSpin(self, self.form.OffsetB, "gap2")
            SheetMetalTools.taskConnectSpin(self, self.form.Length, "length")
            SheetMetalTools.taskConnectCheck(self, self.form.RefineCheckbox, "Refine")

        def isAllowedAlterSelection(self):
            return True

        def isAllowedAlterView(self):
            return True

        def accept(self):
            SheetMetalTools.taskAccept(self, self.form.AddRemove)
            SheetMetalTools.taskSaveDefaults(self.obj, smExtrudeDefaultVars)
            return True

        def reject(self):
            SheetMetalTools.taskReject(self, self.form.AddRemove)

    class SMExtrudeCommandClass:
        """Extrude face"""

        def GetResources(self):
            return {
                "Pixmap": os.path.join(
                    icons_path, "SheetMetal_Extrude.svg"
                ),  # the name of a svg file available in the resources
                "MenuText": FreeCAD.Qt.translate("SheetMetal", "Extend Face"),
                "Accel": "E",
                "ToolTip": FreeCAD.Qt.translate(
                    "SheetMetal",
                    "Extends one or more face, on existing sheet metal.\n"
                    "1. Select edges or thickness side faces to create walls.\n"
                    "2. Select a sketch in property editor to create tabs. \n"
                    "3. Use Property editor to modify other parameters",
                ),
            }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, "Extend")
            if newObj is None:
                return
            SMExtrudeWall(newObj, selobj, sel.SubElementNames)
            SMViewProviderTree(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, newObj, activeBody, SMExtendWallTaskPanel)
            return

        def IsActive(self):
            if (
                len(Gui.Selection.getSelection()) < 1
                or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1
            ):
                return False
            for selobj in Gui.Selection.getSelection():
                if selobj.isDerivedFrom("Sketcher::SketchObject"):
                    return False
            for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
                if isinstance(selFace, Part.Vertex):
                    return False
            return True

    Gui.addCommand("SheetMetal_Extrude", SMExtrudeCommandClass())
