# ######################################################################
#
#  SheetMetalFromSolid.py
#
#  Copyright 2026 Shai Seger <shaise at gmail dot com>
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
# ######################################################################

import FreeCAD
import Part
import SheetMetalTools
import os
import DraftGeomUtils

translate = FreeCAD.Qt.translate
from SheetMetalTools import SMException

# List of properties to be saved as defaults.
smFromSolidDefaultVars = ["Radius", "Thickness", "KFactor"]


# helper functions:

def smCreateCircularFaceLoft(edge, radius):
    """
    Create a circular face with the given radius at the start of the edge,
    oriented such that the face normal aligns with the edge tangent,
    and then sweep this face along the edge to create a solid.
    """
    try:
        # Get properties at the start of the edge
        u = edge.FirstParameter
        pos = edge.valueAt(u)
        tangent = edge.tangentAt(u)
        
        # Create the circular profile
        # Part.Circle(Center, Normal, Radius)
        circleGeo = Part.Circle(pos, tangent, radius)
        circleEdge = circleGeo.toShape()
        profileWire = Part.Wire([circleEdge])
        # Create the loft (pipe) along the edge using makePipeShell
        pathWire = Part.Wire([edge])
        solidPipe = pathWire.makePipeShell([profileWire], True, True) # isSolid=True, isFrenet=True
        
        # makePipeShell returns a shape, if isSolid=True it should be a solid
        # but let's be safe and wrap it or check
        return solidPipe
    except Exception as e:
        FreeCAD.Console.PrintError(f"smCreateCircularFaceLoft failed: {e}\n")
        return None

    
from OCC.Core import ChFi2d
from OCC import Core

def smAnalizeCorner(edge1, edge2):
    """ Find the corner point and 2 directions of 2 connected edges.
    """
    # extracting vertices
    p1 = edge1.valueAt(edge1.FirstParameter)
    p2 = edge1.valueAt(edge1.LastParameter)
    p3 = edge2.valueAt(edge2.FirstParameter)
    p4 = edge2.valueAt(edge2.LastParameter)

    #find common vertex
    if p1.isEqual(p3, SheetMetalTools.smEpsilon):
        commonPoint = p1
        dir1 = edge1.tangentAt(edge1.FirstParameter)
        dir2 = edge2.tangentAt(edge2.FirstParameter)
    elif p1.isEqual(p4, SheetMetalTools.smEpsilon):
        commonPoint = p1
        dir1 = edge1.tangentAt(edge1.FirstParameter)
        dir2 = -edge2.tangentAt(edge2.LastParameter)
    elif p2.isEqual(p3, SheetMetalTools.smEpsilon):
        commonPoint = p2
        dir1 = -edge1.tangentAt(edge1.LastParameter)
        dir2 = edge2.tangentAt(edge2.FirstParameter)
    elif p2.isEqual(p4, SheetMetalTools.smEpsilon):
        commonPoint = p2
        dir1 = -edge1.tangentAt(edge1.LastParameter)
        dir2 = -edge2.tangentAt(edge2.LastParameter)
    else:
        print("Edges don't share a common vertex")
        return None, None, None
    dir1.normalize()
    dir2.normalize()
    return commonPoint, dir1, dir2
    

def smMakeFilletBetweenEdges(e1, e2, r):
    # asuming edges are in a plane
    commonPoint, dir1, dir2 = smAnalizeCorner(e1, e2)
    if commonPoint is None:
        return None
    normdir = dir1.cross(dir2)
    if normdir.Length < SheetMetalTools.smEpsilon:
        print("Edges are parallel - cannot fillet directly")
        return None
    # normdir.normalize()
    filletApi = ChFi2d.ChFi2d_FilletAPI()
    OccPnt = Core.gp.gp_Pnt(*commonPoint)
    pln = Core.gp.gp_Pln(OccPnt, Core.gp.gp_Dir(*normdir))
    occE1 = Core.TopoDS.topods.Edge(Part.__toPythonOCC__(e1))
    occE2 = Core.TopoDS.topods.Edge(Part.__toPythonOCC__(e2))
    filletApi.Init(occE1, occE2, pln)
    try:
        if filletApi.Perform(r):
            occArc = filletApi.Result(OccPnt, occE1, occE2)
            return ([Part.__fromPythonOCC__(occE1),
                      Part.__fromPythonOCC__(occE2),
                      Part.__fromPythonOCC__(occArc)])
    except Exception as e:
        print("OCC Fillet api failed: " + str(e))
        return None

def showVect(point, vect, name = "vect"):
    edge = Part.makeLine(point, point + vect)
    Part.show(edge, name)

# non occ version. not working yet
def smMakeFilletBetweenEdges1(edge1, edge2, r):
    commonPoint, dir1, dir2 = smAnalizeCorner(edge1, edge2)
    if commonPoint == None:
        return None
    
    normdir = dir1.cross(dir2)
    if normdir.Length < SheetMetalTools.smEpsilon:
        print("Edges are parallel - cannot fillet directly")
        return None
    
    showVect(commonPoint, dir1, "dir1")
    showVect(commonPoint, dir2, "dir1")
    showVect(commonPoint, normdir, "normal")
    circleGeo = Part.Circle(commonPoint, normdir, r)
    circleEdge = circleGeo.toShape()
    Part.show(circleEdge)
    # normdir.normalize()
    filletApi = Part.ChFi2d.FilletAPI()
    pln = Part.Plane(commonPoint, normdir)
    filletApi.init(Part.Wire([edge1, edge2]), pln)
    return filletApi
    # if filletApi.perform(r):
    #     return filletApi.Result()
    # return None
    # try:
    #     if filletApi.Perform(r):
    #         occArc = filletApi.Result(OccPnt, occE1, occE2)
    #         return ([Part.__fromPythonOCC__(occE1),
    #                   Part.__fromPythonOCC__(occE2),
    #                   Part.__fromPythonOCC__(occArc)])
    # except Exception as e:
    #     print("OCC Fillet api failed: " + str(e))
    #     return None



def smProjectEdgeOnPlane(edge, vertex, normal):
    """Project an edge onto a plane defined by a vertex and a normal."""
    plane = Part.Plane(vertex.Point, normal)
    splnplaneShape = plane.toShape()
    projectedEdges = splnplaneShape.project([edge]).Edges
    projectedEdge = projectedEdges[0] if projectedEdges and len(projectedEdges) > 0 else None
    return projectedEdge

def smFindEdgeAdjacentToedgeOnFace(edge, vertex, face):
    """Find an edge on the face that is adjacent to the given edge."""
    for e in face.Edges:
        if e.isSame(edge):
            continue
        # Check if edges share a vertex
        for v in e.Vertexes:
            if vertex.isSame(v):
                return e
    return None

def smGetVertexBetweenFilletAndEdge(edge, filletEdge):
    """Get the vertex between fillet and FilletEdge, and the relative length cut from original edge."""
    newLength = edge.Length - filletEdge.Length
    if newLength <= 0:
        return None
    relativeLength = newLength / edge.Length
    v1 = filletEdge.Vertexes[0]
    v2 = filletEdge.Vertexes[1]
    if edge.valueAt(edge.FirstParameter).isEqual(v1.Point, SheetMetalTools.smEpsilon) or \
       edge.valueAt(edge.LastParameter).isEqual(v1.Point, SheetMetalTools.smEpsilon):
        return v2, relativeLength
    else:
        return v1, relativeLength
    
def smGenerateEdgeTypeDatabase(shape, selEdgeNames, selFaceNames):
    """Generate a database of edge types for the shape."""
    edgeTypeDB = {}
    for egde in shape.Edges:
        edgeTypeDB[egde.hashCode()] = "bend"
    for edgeName in selEdgeNames:
        hashCode = shape.getElement(edgeName).hashCode()
        edgeTypeDB[hashCode] = "seam"
    for faceName in selFaceNames:
        face = shape.getElement(faceName)
        for edge in face.Edges:
            if edgeTypeDB[edge.hashCode()] == "flange":
                edgeTypeDB[edge.hashCode()] = "ignore"
            else:
                edgeTypeDB[edge.hashCode()] = "flange"
    return edgeTypeDB

def smGetIntersectionPoint(curve, face):
    points, _extra = curve.intersect(face.Surface)
    for pt in points:
        v = FreeCAD.Vector(pt.X, pt.Y, pt.Z)
        if face.isInside(v, SheetMetalTools.smEpsilon, False):
            return v
    return None

def smGetEdgeConcavityType(solid, edge):
    """Get the concavity type of the bend between two faces.
       We do it by taking 2 points on the faces near the edge, find the
       average point between them and check if it is inside or outside the solid.
       If it is inside, the bend is convex. Otherwise, it is concave.
    """
    connected_faces = solid.ancestorsOfType(edge, Part.Face)
    face1, face2 = connected_faces[:2]  # Take the first two connected faces
    try:
        # Get properties at the start of the edge
        u = (edge.FirstParameter + edge.LastParameter) / 2.0
        pos = edge.valueAt(u)
        tangent = edge.tangentAt(u)
        
        # Create the circular profile
        # Part.Circle(Center, Normal, Radius)
        circleGeo = Part.Circle(pos, tangent, 0.01)
        pt1 = smGetIntersectionPoint(circleGeo, face1)
        pt2 = smGetIntersectionPoint(circleGeo, face2)
        avgPt = (pt1 + pt2) / 2
        if solid.isInside(avgPt, SheetMetalTools.smEpsilon, False):
            return "convex"
        return "concave"
        
    except Exception as e:
        FreeCAD.Console.PrintError(f"smCreateCircularFaceLoft failed: {e}\n")
        return None


def smGetVertexConcavityType(face, vertex):
    """Get the concavity type of a corner on a face.
       We do it by taking 2 points on the edges connected to the vertex, find the
       average point between them and check if it is inside or outside the face.
       If it is inside, the corner is convex. Otherwise, it is concave.
    """
    edges = face.ancestorsOfType(vertex, Part.Edge)
    edge1, edge2 = edges[:2]  # Take the first two connected edges
    commonPoint, dir1, dir2 = smAnalizeCorner(edge1, edge2)
    pt1 = commonPoint.add(dir1 * 0.01)
    pt2 = commonPoint.add(dir2 * 0.01)
    avgPt = (pt1 + pt2) / 2
    if face.isInside(avgPt, SheetMetalTools.smEpsilon, False):
        return "convex"
    return "concave"


def smCalculateBendEdgeInfo(edgeInfo, radius, thickness, invertDir):
    """
    Calculate the fillet between two faces connected by the given edge.
    :return: fillet arc
    """
    # Find 2 edges on each face that are adjacent to the given edge
    edge = edgeInfo.edge

    vertex0 = edge.Vertexes[0]
    vertex1 = edge.Vertexes[1]
    edgeFace1 = smFindEdgeAdjacentToedgeOnFace(edge, vertex0, edgeInfo.face1)
    edgeFace2 = smFindEdgeAdjacentToedgeOnFace(edge, vertex0, edgeInfo.face2)
    # project the edges onto the plane defined by the edge and its direction
    edgeDir = vertex0.Point.sub(vertex1.Point).normalize()
    projectedEdge1 = smProjectEdgeOnPlane(edgeFace1, vertex0, edgeDir)
    projectedEdge2 = smProjectEdgeOnPlane(edgeFace2, vertex0, edgeDir)

    concavityType = smGetEdgeConcavityType(edgeInfo.solid, edge)
    edgeInfo.concavityType = concavityType
    # print("Concavity type: ", concavityType)
    if concavityType == "concave":
        invertDir = not invertDir
    if invertDir:
        radius = radius + thickness

    # create fillet between the two projected edges
    filletEdges = smMakeFilletBetweenEdges(projectedEdge1, projectedEdge2, radius)
    if filletEdges is None:
        return None
    # we need find the edge part from the vertex to the fillet start point
    _rightFilletEdge, _leftFilletEdge, filletArc = filletEdges
    # Part.show(filletArc, "filletArc")
    return filletArc

def smCompareDirections(dir1, dir2, epsilon = SheetMetalTools.smEpsilon):
    if dir1.isEqual(dir2, epsilon):
        return "same"
    if dir1.isEqual(-dir2, epsilon):
        return "opposite"
    return "other"

def smExtendEdgeBothSides(edge, distance):
    pt1 = edge.Vertexes[0].Point
    pt2 = edge.Vertexes[1].Point
    dir = (pt2 - pt1).normalize()
    pt1 = pt1 - dir * distance
    pt2 = pt2 + dir * distance
    return Part.makeLine(pt1, pt2)

def smDisplayNormals(solid):
    for face in solid.Faces:
        u,v = face.Surface.parameter(face.Vertexes[0].Point)
        p = face.valueAt(u, v)
        n = face.normalAt(u,v)
        Part.show(Part.makeLine(p, p + n * 5), "normal")

def smDisplayEdgeDirection(edge):
    p = edge.valueAt(edge.LastParameter)
    dir = -edge.tangentAt(edge.LastParameter)
    Part.show(Part.makeLine(p, p + dir * 5), "tangentDir")

class smfsEdgeInfo:
    """Represent edge information in solid to sheet map."""

    def __init__(self, edge, solid, type):
        """Initialize the edge info with a values."""
        self.edge = edge
        self.bendEdge = edge
        self.solid = solid
        self.type = type
        connected_faces = solid.ancestorsOfType(edge, Part.Face)
        self.edgeDir = (edge.Vertexes[0].Point - edge.Vertexes[1].Point).normalize()

        if len(connected_faces) < 2:
            print("Could not find two faces connected by the given edge")
        else:
            self.face1, self.face2 = connected_faces[:2]  # Take the first two connected faces
        if type == "bend":
            self.extendedEdge = smExtendEdgeBothSides(edge, edge.Length * 10)

    def analizeBend(self, radius, thickness, invertDir):
        self.filletArc = smCalculateBendEdgeInfo(self, radius, thickness, invertDir)
        if self.filletArc is None:
            self.type = "ignore"

    def getJunctionAtVertex(self, vertex):
        """Get the junction at the given vertex."""
        for junction in self.juctionList:
            if junction.vertex.isSame(vertex):
                return junction
        return None

    def adjustBendEdge(self, newEdge):
        self.bendEdge = self.bendEdge.common(newEdge)

class smfsFaceInfo:
    """Represent face information in solid to sheet map."""
    def __init__(self, face, solid, isRemoved = False):
        """Initialize the face info with a values."""
        self.face = face
        self.modifiedFace = face.copy()
        self.solid = solid
        self.isRemoved = isRemoved

    def cutEdge(self, edgePipe):
        if self.isRemoved:
            print("Face is removed")
            return
        cutFace = self.modifiedFace.cut(edgePipe)
        self.modifiedFace = cutFace.Faces[0]
        # Part.show(self.modifiedFace, "modifiedFace")

    def detectBendEdge(self, edgeInfo, cutRadius):
        cornerEdge = edgeInfo.edge
        cornerEdgeDir = edgeInfo.edgeDir
        for edge in self.modifiedFace.Edges:
            edgeDir = (edge.Vertexes[0].Point - edge.Vertexes[1].Point).normalize()
            dirTest = smCompareDirections(edgeDir, cornerEdgeDir)
            if dirTest == "other":
                continue
            dist, points, _extra = edge.Vertexes[0].distToShape(cornerEdge)
            if abs(dist - cutRadius) > SheetMetalTools.smEpsilon:
                continue
            projPoint1 = points[0][1]
            dist, points, _extra = edge.Vertexes[1].distToShape(cornerEdge)
            projPoint2 = points[0][1]
            bendEdge = Part.makeLine(projPoint1, projPoint2)
            edgeInfo.adjustBendEdge(bendEdge)

class smfsSolidInfo:
    """Build mapped solid information."""
    def __init__(self, solid, selEdgeNames, selFaceNames):
        """Initialize the solid info with a values."""
        self.debugCount = 0
        self.solid = solid
        self.faceInfoDict = {}
        self.edgeInfoDict = {}
        self.edgeTypeDB = smGenerateEdgeTypeDatabase(solid, selEdgeNames, selFaceNames)
        for face in solid.Faces:
            isRemoved = False
            for removedName in selFaceNames:
                removed_face = solid.getElement(removedName)
                if face.isSame(removed_face):
                    isRemoved = True
                    break
            self.faceInfoDict[face.hashCode()] = smfsFaceInfo(face, solid, isRemoved)
        for edge in solid.Edges:
            edgeType = self.edgeTypeDB[edge.hashCode()]
            edgeInfo = smfsEdgeInfo(edge, solid, edgeType)
            edgeInfo.faceInf1 = self.faceInfoDict[edgeInfo.face1.hashCode()]
            edgeInfo.faceInf2 = self.faceInfoDict[edgeInfo.face2.hashCode()]
            self.edgeInfoDict[edge.hashCode()] = edgeInfo

    def analizeBends(self, radius, thickness, invertDir):
        for edgeInfo in self.edgeInfoDict.values():
            if edgeInfo.type == "bend":
                edgeInfo.analizeBend(radius, thickness, invertDir)

    def ripSeams(self, radius):
        for edgeInfo in self.edgeInfoDict.values():
            if edgeInfo.type == "bend":
                continue
            edgePipe = smCreateCircularFaceLoft(edgeInfo.edge, radius)
            if edgePipe is None:
                continue
            edgeInfo.faceInf1.cutEdge(edgePipe)
            edgeInfo.faceInf2.cutEdge(edgePipe)

    def cutBend(self, edgeInfo, faceInfo):
        arc = edgeInfo.filletArc
        if arc.Vertexes[0].isCoplanar(faceInfo.face):
            vert = arc.Vertexes[0]
        else:
            vert = arc.Vertexes[1]

        cutRadius = (vert.Point - edgeInfo.edge.Vertexes[0].Point).Length
        edgePipe = smCreateCircularFaceLoft(edgeInfo.extendedEdge, cutRadius)
        if edgePipe is None:
            return 0
        faceInfo.cutEdge(edgePipe)
        self.debugCount += 1
        return cutRadius

    def cutBends(self):
        for edgeInfo in self.edgeInfoDict.values():
            if edgeInfo.type != "bend":
                continue
            edgeInfo.cutRadius1 = self.cutBend(edgeInfo, edgeInfo.faceInf1)
            edgeInfo.cutRadius2 = self.cutBend(edgeInfo, edgeInfo.faceInf2)

        for edgeInfo in self.edgeInfoDict.values():
            if edgeInfo.type != "bend":
                continue
            edgeInfo.faceInf1.detectBendEdge(edgeInfo, edgeInfo.cutRadius1)
            edgeInfo.faceInf2.detectBendEdge(edgeInfo, edgeInfo.cutRadius2)

    def generateBends(self):
        self.bendFaces = []
        for edgeInfo in self.edgeInfoDict.values():
            if edgeInfo.type != "bend":
                continue
            startPoint = edgeInfo.bendEdge.Vertexes[0].Point
            endPoint = edgeInfo.bendEdge.Vertexes[1].Point
            arc = edgeInfo.filletArc
            arc.translate(startPoint - edgeInfo.edge.Vertexes[0].Point)
            bendFace = arc.extrude(endPoint - startPoint)
            self.bendFaces.append(bendFace)

    def makeShell(self):
        shellFaces = []
        for faceInfo in self.faceInfoDict.values():
            if not faceInfo.isRemoved:
                shellFaces.append(faceInfo.modifiedFace)
        shellFaces.extend(self.bendFaces)
        return Part.makeShell(shellFaces)

def smMakeSheetMetalFromSolid(shape, removeFaces, ripEdges, radius, thickness, tolerance, invert):
    solidInfo = smfsSolidInfo(shape, ripEdges, removeFaces)
    solidInfo.analizeBends(radius, thickness, invert)
    ripRadius = tolerance
    if invert:
        ripRadius += thickness
    solidInfo.ripSeams(ripRadius)
    solidInfo.cutBends()
    solidInfo.generateBends()
    shell = solidInfo.makeShell()
    solid = None
    try:
        for shellPart in shell.Shells:
            s = shellPart.makeOffsetShape(thickness, 0.001, fill=True)
            solid = s if solid is None else solid.fuse(s)
    except:
        #smDisplayNormals(shell)
        print("shell.makeOffsetShape failed, trying face by face")
        Part.show(shell, "shell")
        for face in shell.Faces:
            s = face.makeOffsetShape(thickness, 0.001, fill=True)
            solid = s if solid is None else solid.fuse(s)
    return solid

class SMFromSolid:
    def __init__(self, obj, selobj, sel_items):
        obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", 
                        "Base object").baseObject = (selobj, [])
        faces = []
        edges = []
        for sub in sel_items:
            if sub.startswith("Face"):
                faces.append(sub)
            elif sub.startswith("Edge"):
                edges.append(sub)
        
        obj.addProperty("App::PropertyLinkSub", "removeFaces", "Parameters", "Faces to remove").removeFaces = (selobj, faces)
        obj.addProperty("App::PropertyLinkSub", "ripEdges", "Parameters", "Edges to rip (seams)").ripEdges = (selobj, edges)
        
        SheetMetalTools.smAddLengthProperty(obj, "Radius", "Bend Radius", 1.0)
        SheetMetalTools.smAddLengthProperty(obj, "Thickness", "Wall Thickness", 1.0)
        obj.addProperty("App::PropertyFloatConstraint", "KFactor", "Parameters", "K Factor").KFactor = (0.5, 0.0, 1.0, 0.01)
        SheetMetalTools.taskRestoreDefaults(obj, smFromSolidDefaultVars)
        obj.Proxy = self

    def execute(self, fp):
        if not fp.baseObject:
            return

        base_shape = fp.baseObject[0].Shape
        if not base_shape.Faces:
            return

        fp.Shape = smMakeSheetMetalFromSolid(base_shape, fp.removeFaces[1], fp.ripEdges[1], fp.Radius.Value, fp.Thickness.Value, 0.1, False)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


# View Provider
if SheetMetalTools.isGuiLoaded():
    Gui = FreeCAD.Gui

    class SMFromSolidViewProvider(SheetMetalTools.SMViewProvider):
        def getIcon(self):
            return os.path.join(SheetMetalTools.icons_path, "SheetMetal_FromSolid.svg")

        def getTaskPanel(self, obj):
            return SMFromSolidTaskPanel(obj)
            
    class SMFromSolidTaskPanel:
        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("CreateFromSolid.ui") # We need to create this UI file!
            # Or we can build it programmatically if we don't want to create a .ui file, 
            # but SheetMetalTools relies on .ui.
            # Wait, `CreateBaseShape.ui` exists. Maybe I can reuse/modify a similar one or create a new one.
            # I will create a new UI file `CreateFromSolid.ui` as well.
            
            SheetMetalTools.taskConnectSpin(obj, self.form.spinRadius, "Radius")
            SheetMetalTools.taskConnectSpin(obj, self.form.spinThickness, "Thickness")
            SheetMetalTools.taskConnectSpin(obj, self.form.spinKFactor, "KFactor")
            
            # Selection for Remove Faces
            self.selFaces = SheetMetalTools.taskConnectSelection(
                self.form.btnRemoveFaces, self.form.listRemoveFaces,
                obj, ["Face"], self.form.btnClearFaces, "removeFaces", hideObject=False
            )
            # Constrain selection to the base object
            self.selFaces.ConstrainToObject = obj.baseObject[0]

            # Selection for Rip Edges
            self.selEdges = SheetMetalTools.taskConnectSelection(
                self.form.btnRipEdges, self.form.listRipEdges,
                obj, ["Edge"], self.form.btnClearEdges, "ripEdges", hideObject=False
            )
            self.selEdges.ConstrainToObject = obj.baseObject[0]

        def accept(self):
            SheetMetalTools.taskAccept(self)
            SheetMetalTools.taskSaveDefaults(self.obj, smFromSolidDefaultVars)
            return True

        def reject(self):
            SheetMetalTools.taskReject(self)
            return True


    class FromSolidCommandClass:
        """Convert a solid to a sheet metal object."""

        def GetResources(self):
            return {
                "Pixmap": os.path.join(SheetMetalTools.icons_path, "SheetMetal_FromSolid.svg"),
                "MenuText": translate("SheetMetal", "Convert to Sheet Metal"),
                "Accel": "C, S",
                "ToolTip": translate("SheetMetal", "Convert a solid to a sheet metal object"),
            }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()
            if not sel:
                SheetMetalTools.smWarnDialog("Please select a solid object first.")
                return
            selobj = sel[0].Object           
            # Ensure it has Shape
            if not hasattr(selobj, "Shape"):
                 SheetMetalTools.smWarnDialog("Selection is not a geometric object.")
                 return

            new_obj, active_body = SheetMetalTools.smCreateNewObject(selobj, "SolidToSheet")
            if new_obj is None:
                return

            SMFromSolid(new_obj, selobj, sel[0].SubElementNames)
            SMFromSolidViewProvider(new_obj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, new_obj, active_body, SMFromSolidTaskPanel)

        def IsActive(self):
            return len(Gui.Selection.getSelection()) == 1

    Gui.addCommand("SheetMetal_FromSolid", FromSolidCommandClass())
