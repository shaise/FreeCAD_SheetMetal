########################################################################
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
########################################################################

import math
import os

import FreeCAD
import Part

import SheetMetalTools

Base = FreeCAD.Base

# IMPORTANT: please remember to change the element map version in case
# of any changes in modeling logic.
smElementMapVersion = "sm1."
smEpsilon = SheetMetalTools.smEpsilon
translate = FreeCAD.Qt.translate

# List of properties to be saved as defaults.
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
    # # Find face Modified During loop.
    # Part.show(Face,'Face')
    facelist = []
    for face in obj.Faces:
        # Part.show(face,'face')
        face_common = face.common(Face)
        if not face_common.Faces:
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
    # Project thickness side edge to get one side rectangle.
    normal = face.normalAt(0, 0)
    faceVert = face.Vertexes[0].Point
    pt1 = edge.Vertexes[0].Point.projectToPlane(faceVert, normal)
    pt2 = edge.Vertexes[1].Point.projectToPlane(faceVert, normal)
    vec1 = pt2 - pt1

    # Find min & max point of cut shape.
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

        # Find angle between diagonal & thickness side edge.
        vec2 = p2 - p1
        angle1 = vec2.getAngle(vec1)
        angle = math.degrees(angle1)
        # print(angle)

        # Check & correct orientation of diagonal edge rotation.
        e = Part.makeLine(p1, p2)
        e.rotate(p1, normal, -angle)
        vec2 = (e.valueAt(e.LastParameter) - e.valueAt(e.FirstParameter)).normalize()
        coeff = vec2.dot(vec1.normalize())
        # print(coeff)
        if coeff != 1.0:
            angle = 90 - angle

        # Create Cut Rectangle Face from min/max points & angle.
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

def smExtendBySketch(sketch, selObject, refine=True, subtraction=False, offset=0.2):
    finalShape = selObject.Shape.copy()
    attachedObj, attachedFaceNames = sketch.AttachmentSupport[0]
    attachedShape = attachedObj.Shape
    attachedFace = attachedShape.getElement(
        SheetMetalTools.getElementFromTNP(attachedFaceNames[0])
    )
    # Find thickess edge by examining all edges attached to an attached face vertex.
    thicknessEdge = None
    for vert in attachedFace.Vertexes:
        edgeList = attachedShape.ancestorsOfType(vert, Part.Edge)
        if (len(edgeList) != 3):
            continue 
        for edge in edgeList:
            edge_common = edge.common(attachedFace)
            if len(edge_common.Edges) == 0:
                thicknessEdge = edge
                break
        if thicknessEdge:
            break
    thickness = thicknessEdge.Length
    extrudeDir = attachedFace.normalAt(0, 0)
    overlap_solidlist = []
    Wall_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
    # if not Wall_face.isCoplanar(Cface, smEpsilon):
    #     thkDir *= -1
    wallSolid = Wall_face.extrude(extrudeDir * thickness * -1)
    if (wallSolid.Volume - smEpsilon) < 0.0:
        raise SheetMetalTools.SMException("Incorrect face selected. Please select a side face.")
    # Part.show(wallSolid, "wallSolid")

    finalShape = finalShape.fuse(wallSolid)

    # Part.show(finalShape, "finalShape")
    if refine:
        finalShape = finalShape.removeSplitter()
    return finalShape


def smExtrude(extLength=10.0, gap1=0.0, gap2=0.0, reversed=False, subtraction=False, offset=0.2,
              refine=True, sketch="", selFaceNames="", selObject="", ):
    import BOPTools.SplitFeatures

    if sketch:
        return smExtendBySketch(sketch, selObject, refine)

    baseSolid = selObject.Shape.copy()
    finalShape = baseSolid
    for selFaceName in selFaceNames:
        selItem = baseSolid.getElement(SheetMetalTools.getElementFromTNP(selFaceName))
        selFace = SheetMetalTools.smGetFaceByEdge(selItem, baseSolid)

        # Find the narrow edge.
        thk = 999999.
        thkEdge = None
        for edge in selFace.Edges:
            if abs(edge.Length) < thk:
                thk = abs(edge.Length)
                thkEdge = edge

        # Find a length edge.
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

        # Find the large face connected with selected face.
        list2 = baseSolid.ancestorsOfType(lenEdge, Part.Face)
        for Cface in list2:
            if not (Cface.isSame(selFace)):
                break
        Part.show(Cface, "Cface")

        # Main Length Edge, Extrusion direction
        #    MlenEdge = lenEdge
        #    leng = MlenEdge.Length
        pThkDir1 = selFace.CenterOfMass
        pThkDir2 = lenEdge.Curve.value(lenEdge.Curve.parameter(pThkDir1))
        thkDir = pThkDir1.sub(pThkDir2).normalize()
        FaceDir = selFace.normalAt(0, 0)

        # If sketch is as wall.
        useSketch = False
        if sketch:
            if sketch.Shape.Wires[0].isClosed():
                useSketch = True
            else:
                pass

        # Split solid Based on Top Face into two solid.
        Topface_Solid = Cface.Wires[0].extrude(Cface.normalAt(0, 0) * -thk)
        # Part.show(Topface_Solid, "Topface_Solid")
        SplitSolids = BOPTools.SplitAPI.slice(finalShape, Topface_Solid.Faces, "Standard", 0.0)
        # Part.show(SplitSolids, "SplitSolids")
        for SplitSolid in SplitSolids.Solids:
            check_face = SplitSolid.common(Cface)
            if check_face.Faces:
                SplitSolid1 = SplitSolid
                break
        # Part.show(SplitSolid1, "SplitSolid1")

        SplitSolid2 = None
        for SplitSolid in SplitSolids.Solids:
            if not (SplitSolid.isSame(SplitSolid1)):
                SplitSolid2 = SplitSolid
                break
        # Part.show(SplitSolid2, "SplitSolid2")

        # Make solid from sketch, if sketch is present.
        extendsolid = None
        if useSketch:
            attachedObj, attachedFaceNames = sketch.AttachmentSupport[0]
            attachedShape = attachedObj.Shape
            attachedFace = attachedShape.getElement(
                SheetMetalTools.getElementFromTNP(attachedFaceNames[0])
            )
            # Find thickess edge by examining all edges attached to an attached face vertex.
            thicknessEdge = None
            for vert in attachedFace.Vertexes:
                edgeList = attachedShape.ancestorsOfType(vert, Part.Edge)
                if (len(edgeList) != 3):
                    continue 
                for edge in edgeList:
                    edge_common = edge.common(attachedFace)
                    if len(edge_common.Edges) == 0:
                        thicknessEdge = edge
                        break
                if thicknessEdge:
                    break
            thickness = thicknessEdge.Length
            extrudeDir = attachedFace.normalAt(0, 0)
            overlap_solidlist = []
            Wall_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
            # if not Wall_face.isCoplanar(Cface, smEpsilon):
            #     thkDir *= -1
            wallSolid = Wall_face.extrude(extrudeDir * thickness * -1)
            if (wallSolid.Volume - smEpsilon) < 0.0:
                raise SheetMetalTools.SMException("Incorrect face selected. Please select a side face.")
            # Part.show(wallSolid, "wallSolid")
            extendsolid = wallSolid
            # To find Overlapping Solid, non thickness side Face that
            # touch Overlapping Solid.
            if SplitSolid2:
                overlap_solid = wallSolid.common(SplitSolid2)
                # Part.show(overlap_solid, "overlap_solid")
                if overlap_solid.Faces:
                    substract_face = smTouchFace(wallSolid, SplitSolid2, thk)
                    # Part.show(substract_face, "substract_face")
                    # # To get solids that aligned/normal to touching face.
                    overlap_solidlist = smgetSubface(substract_face, overlap_solid, lenEdge, thk)
                # Substract solid from Initial Solid.
                if subtraction:
                    for solid in overlap_solidlist:
                        CutSolid = solid.makeOffsetShape(offset, 0.0, fill=False, join=2)
                        # Part.show(CutSolid, "CutSolid")
                        finalShape = finalShape.cut(CutSolid)
                        # Part.show(finalShape, "finalShape")
        elif extLength > 0.0:
            # Create wall, if edge or face selected.
            if reversed:
                FaceDir *= -1
            Wall_face = smMakeFace(lenEdge, FaceDir, extLength, gap1, gap2, op="SMW")
            # Part.show(Wall_face, "Wall_face")
            extendsolid = Wall_face.extrude(thkDir * thk)
            # Part.show(extendsolid, "extendsolid")

        # Fuse All solid created to Split solid.
        if extendsolid:
            if reversed and not useSketch:
                finalShape = finalShape.cut(SplitSolid1)
                resultSolid = SplitSolid1.cut(extendsolid)
            else:
                resultSolid = SplitSolid1.fuse(extendsolid)
                # Part.show(resultSolid, "resultSolid")
                # # Merge final list.
                finalShape = finalShape.cut(resultSolid)
            # Part.show(finalShape, "finalShape")
            finalShape = finalShape.fuse(resultSolid)

    # Part.show(finalShape, "finalShape")
    if refine:
        finalShape = finalShape.removeSplitter()
    return finalShape


class SMExtrudeWall:
    def __init__(self, obj, selobj, sel_items, selSketch=None):
        """Add SheetMetal Wall by Extending."""
        _tip_ = translate("App::Property", "Length of Wall")
        obj.addProperty("App::PropertyLength", "length", "Parameters", _tip_).length = 10.0
        _tip_ = translate("App::Property", "Gap from left side")
        obj.addProperty("App::PropertyDistance", "gap1", "Parameters", _tip_).gap1 = 0.0
        _tip_ = translate("App::Property", "Gap from right side")
        obj.addProperty("App::PropertyDistance", "gap2", "Parameters", _tip_).gap2 = 0.0
        _tip_ = translate("App::Property", "Base object")
        obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",
                        _tip_).baseObject = (selobj, sel_items)
        self.addVerifyProperties(obj, selSketch)
        obj.Proxy = self
        SheetMetalTools.taskRestoreDefaults(obj, smExtrudeDefaultVars)

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver
        return None

    def addVerifyProperties(self, obj, selSketch=None):
        SheetMetalTools.smAddBoolProperty(obj, "reversed",
                translate("App::Property", "Reverse extend direction (cut)"), False, "Parameters")
        SheetMetalTools.smAddProperty(obj, "App::PropertyLink", "Sketch", 
                translate("App::Property", "Wall Sketch"), selSketch, "ParametersExt")
        SheetMetalTools.smAddBoolProperty(obj, "UseSubtraction",
                translate("App::Property", "Use Subtraction"), False, "ParametersExt")
        SheetMetalTools.smAddDistanceProperty(obj, "Offset",
                translate("App::Property", "Offset for subtraction"), 0.2, "ParametersExt")
        SheetMetalTools.smAddBoolProperty(obj, "Refine",
                translate("App::Property", "Use Refine"), True, "ParametersExt")
        if hasattr(obj, "UseSubstraction"):
                obj.UseSubtraction = obj.UseSubstraction  # Compatibility with old files.
        

    def execute(self, fp):
        """Execute SheetMetal Wall by Extruding."""
        self.addVerifyProperties(fp)

        # Pass selected object shape.
        Main_Object = fp.baseObject[0]
        face = fp.baseObject[1]
        fp.Shape = smExtrude(extLength=fp.length.Value,
                             gap1=fp.gap1.Value,
                             gap2=fp.gap2.Value,
                             reversed=fp.reversed,
                             subtraction=fp.UseSubtraction,
                             offset=fp.Offset.Value,
                             refine=fp.Refine,
                             sketch=fp.Sketch,
                             selFaceNames=face,
                             selObject=Main_Object)
        if fp.Sketch :
            fp.Sketch.ViewObject.Visibility = False



###################################################################################################
# Gui code
###################################################################################################

if SheetMetalTools.isGuiLoaded():
    from PySide import QtCore, QtGui

    Gui = FreeCAD.Gui
    icons_path = SheetMetalTools.icons_path


    class SMViewProviderTree(SheetMetalTools.SMViewProvider):
        """Part WB style ViewProvider."""

        def getIcon(self):
            if self.Object.Sketch:
                return os.path.join(icons_path, "SheetMetal_ExtendBySketch.svg")
            else:
                return os.path.join(icons_path, "SheetMetal_Extrude.svg")

        def getTaskPanel(self, obj):
            return SMExtendWallTaskPanel(obj)


    class SMViewProviderFlat(SMViewProviderTree):
        """Part Design WB style ViewProvider.

        Note:
            Backward compatibility only.

        """


    class SMExtendWallTaskPanel:
        """A TaskPanel for the SheetMetal."""

        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("ExtendTaskPanel.ui")

            # Make sure all properties are added.
            obj.Proxy.addVerifyProperties(obj)

            self.selParams = SheetMetalTools.taskConnectSelection(self.form.AddRemove,
                                                                  self.form.tree, self.obj,
                                                                  ["Face"], self.form.pushClearSel)
            SheetMetalTools.taskConnectSelectionSingle(self.form.buttSelSketch,
                                                       self.form.txtSelSketch, obj, "Sketch",
                                                       ("Sketcher::SketchObject", []))
            SheetMetalTools.taskConnectSpin(obj, self.form.OffsetA, "gap1")
            SheetMetalTools.taskConnectSpin(obj, self.form.OffsetB, "gap2")
            SheetMetalTools.taskConnectSpin(obj, self.form.Length, "length")
            SheetMetalTools.taskConnectSpin(obj, self.form.Offset, "Offset")
            SheetMetalTools.taskConnectCheck(obj, self.form.RefineCheckbox, "Refine")
            SheetMetalTools.taskConnectCheck(obj, self.form.checkIntersectClear, "UseSubtraction")
            SheetMetalTools.taskConnectCheck(obj, self.form.checkReversed, "reversed")
            isStandardExtend = self.obj.Sketch is None
            self.form.groupExtend.setVisible(isStandardExtend)
            self.form.groupExtendBySketch.setVisible(not isStandardExtend)

            # for now disable clear sketch button since we have a seperate command for that
            self.form.buttClearSketch.setVisible(False)
            self.form.buttClearSketch.clicked.connect(self.clearPressed)

        def isAllowedAlterSelection(self):
            return True

        def isAllowedAlterView(self):
            return True
        
        def clearPressed(self):
            if self.obj.Sketch is None:
                return
            self.obj.Sketch.ViewObject.Visibility = True
            self.obj.Sketch = None
            self.form.txtSelSketch.setText("")
            self.obj.recompute()

        def accept(self):
            SheetMetalTools.taskAccept(self)
            SheetMetalTools.taskSaveDefaults(self.obj, smExtrudeDefaultVars)
            return True

        def reject(self):
            SheetMetalTools.taskReject(self)


    class SMExtrudeCommandClass:
        """Extrude face."""

        def GetResources(self):
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(icons_path, "SheetMetal_Extrude.svg"),
                    "MenuText": translate("SheetMetal", "Extend Face"),
                    "Accel": "E",
                    "ToolTip": translate(
                        "SheetMetal",
                        "Extends one or more face, on existing sheet metal.\n"
                        "1. Select edges or thickness side faces to extend walls.\n"
                        "2. Use Property-editor / Task-panel to modify other parameters",
                        ),
                    }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, "Extend")
            if newObj is None:
                return
            SMExtrudeWall(newObj, selobj, sel.SubElementNames, None)
            SMViewProviderTree(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, newObj, activeBody, SMExtendWallTaskPanel)
            return

        def IsActive(self):
            if (
                len(Gui.Selection.getSelection()) != 1
                or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1
            ):
                return False
            selobj = Gui.Selection.getSelection()[0]
            if selobj.isDerivedFrom("Sketcher::SketchObject"):
                return False
            for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
                if isinstance(selFace, Part.Vertex):
                    return False
            return True

    class SMExtendBySketchCommandClass:
        """Extrude by sketch."""

        def GetResources(self):
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(icons_path, "SheetMetal_ExtendBySketch.svg"),
                    "MenuText": translate("SheetMetal", "Extend by Sketch"),
                    "Accel": "T",
                    "ToolTip": translate(
                        "SheetMetal",
                        "Extends a side face using a sketch.\n"
                        "1. Select a thickness side face to extend.\n"
                        "2. Select a sketch to shape the extension (Good for creating tabs).\n"
                        "3. Use Property-editor / Task-panel to modify other parameters",
                        ),
                    }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, "Extend")
            if newObj is None:
                return
            selSketch = None
            if (len(Gui.Selection.getSelection()) > 1):
                selSketch = Gui.Selection.getSelection()[1]
            SMExtrudeWall(newObj, selobj, sel.SubElementNames, selSketch)
            SMViewProviderTree(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, newObj, activeBody, SMExtendWallTaskPanel)
            return

        def IsActive(self):
            if (
                len(Gui.Selection.getSelection()) != 2
                or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
            ):
                return False
            selobj = Gui.Selection.getSelection()[0]
            if selobj.isDerivedFrom("Sketcher::SketchObject"):
                return False
            if not Gui.Selection.getSelection()[1].isDerivedFrom("Sketcher::SketchObject"):
                return False 
            for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
                if isinstance(selFace, Part.Vertex):
                    return False
            return True


    Gui.addCommand("SheetMetal_Extrude", SMExtrudeCommandClass())
    Gui.addCommand("SheetMetal_ExtendBySketch", SMExtendBySketchCommandClass())
