#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  sheet_ufo.py
#
#  Copyright 2014, 2018 Ulrich Brammer <ulrich@Pauline>
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
# CHANGELOG
# sheet_ufo.py git-version

# July 2023
# Significant refactor to remove GUI dependencies.
# UI no folly defined in a .ui file and handle through a separate module.
# main entry function processUnfold() simpler and more readable.

# July 2018
# - added sortEdgesTolerant: more robust generation of Wires for unbend Faces
# - generate fold lines, to be used in drawings of the unfolded part.
# - fixed calculation of Bend Angle, not working in some cases
#
# sheet_ufo20.py
# - removal of dead code

# sheet_ufo19.py
# changes from June 2018
# - found solution for the new unbendFace function.
# - supports now non orthogonals cut in the bends
# - seams do not get a face, just do not call makeSeamFace
#   this avoids internal faces in the unfold under certain cases.

# sheet_ufo18.py
# - Changes done in 2016 and June 2018
# - allow more complex bends: not only straight cut side edges
# - tested some code, not published

# sheet_ufo17.py
# - Refactored version December 2015
# - Clear division of tasks between analysis and folding

# sheet_ufo16.py
# - Die Weiterreichung eines schon geschnittenen Seitenfaces macht Probleme.
# - Die Seitenfaces passen hinterher nicht mehr mit den Hauptflächen zusammen.

# Geänderter Ansatz: lasse die Seitenflächen in der Suchliste und
# schneide jeweils nur den benötigten Teil raus.
# Ich brauche jetzt eine Suchliste und eine Unfoldliste für die
# Face-Indices.

# TODO:
# - handle a selected seam
# - handle not-circle-curves in bends, done
# - detect features like welded screws
# - make a view-provider for bends
# - make the k-factor selectable
# - upfold or unfold single bends
# - change code to handle face indexes in the node instead of faces


# ideas:
# During analysis make a mesh-like structure for the bend-node
# list of edges in the bend-node
# for each face store a list with edge-indices.
# the reason is, each edge has to be recalculated at unfolding
# so the number of calculations could be half, as if for each
# face all edges are calculated.
# Edges perpendicular to the sheet may only be moved to the new location?
# Need to think about it! No only at the end of the bend node.
# Edges in the middle of the bend node will be sheared, because the
# neutral line is not in the middle of the sheet-thickness.
# OK this is more complex, than I thought at the beginning.

# in a bend node all faces and edges are recreated
# all vertices are translated except those from the parent node.
# the code looked already at each of them.
# a good storage structure is needed!

"""

def main():

	return 0

if __name__ == '__main__':
	main()


"""


import Part, FreeCAD, FreeCADGui, os, sys
from FreeCAD import Base
import DraftVecUtils, math, time
import Draft

import traceback

traceback.print_exc()

try:
    from TechDraw import projectEx
except ImportError:
    from Drawing import projectEx

from lookup import get_val_from_range

import tempfile
from math import sqrt

from SheetMetalLogger import SMLogger, UnfoldException, BendException, TreeException


KFACTORSTANDARD = None

# TODO: Error Codes
# - Put error numbers into the text
# - Put user help into more texts
unfold_error = {
    # error codes for the tree-object
    1: ("starting: volume unusable, needs a real 3D-sheet-metal with thickness"),
    2: ("Starting: invalid point for thickness measurement"),
    3: ("Starting: invalid thickness"),
    4: ("Starting: invalid shape"),
    5: (
        "Starting: Shape has unneeded edges. Please use function refine shape from the Part Workbench before unfolding!"
    ),
    # error codes for the bend-analysis
    10: ("Analysis: zero wires in sheet edge analysis"),
    11: ("Analysis: double bends not implemented"),
    12: ("Analysis: more than one bend-child actually not supported"),
    13: ("Analysis: Sheet thickness invalid for this face!"),
    14: ("Analysis: the code can not handle edges without neighbor faces"),
    15: ("Analysis: the code needs a face at all sheet edges"),
    16: (
        "Analysis: did not find startangle of bend, please post failing sample for analysis"
    ),
    17: (
        "Analysis: Type of surface not supported for sheet metal parts"
    ),  # <SurfaceOfExtrusion object> FIXME?
    # error codes for the unfolding
    20: ("Unfold: section wire with less than 4 edges"),
    21: ("Unfold: Unfold: section wire not closed"),
    22: ("Unfold: section failed"),
    23: ("Unfold: CutToolWire not closed"),
    24: ("Unfold: bend-face without child not implemented"),
    25: ("Unfold: "),
    26: ("Unfold: not handled curve type in unbendFace"),
    -1: ("Unknown error"),
}


def equal_vector(vec1, vec2, p=5):
    # compares two vectors
    return (
        round(vec1.x - vec2.x, p) == 0
        and round(vec1.y - vec2.y, p) == 0
        and round(vec1.z - vec2.z, p) == 0
    )


def equal_vertex(vert1, vert2, p=5):
    # compares two vertices
    return (
        round(vert1.X - vert2.X, p) == 0
        and round(vert1.Y - vert2.Y, p) == 0
        and round(vert1.Z - vert2.Z, p) == 0
    )


def sk_distance(p0, p1):
    return sqrt((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2)


def sanitizeSkBsp(s_name, knot_tolerance):
    # s_name = 'Sketch001'
    s = FreeCAD.ActiveDocument.getObject(s_name)
    FreeCAD.Console.PrintWarning("check to sanitize\n")
    if "Sketcher" in s.TypeId:
        FreeCAD.ActiveDocument.openTransaction("Sanitizing")
        idx_to_del = []
        geo_to_del = []
        # check for duplicates in splines
        if len(s.Geometry) > 2:  # cleaning algo approx valid for more than 2 splines
            for i, g in enumerate(s.Geometry):
                if "BSplineCurve object" in str(g):
                    j = i + 1
                    for bg in s.Geometry[(i + 1) :]:
                        if "BSplineCurve object" in str(bg):
                            if j not in idx_to_del:
                                if len(g.KnotSequence) == len(bg.KnotSequence):
                                    # print('equal knot nbrs')
                                    eqp = True
                                    if (
                                        sk_distance(g.StartPoint, bg.StartPoint)
                                        > knot_tolerance
                                    ):
                                        if (
                                            sk_distance(g.StartPoint, bg.EndPoint)
                                            > knot_tolerance
                                        ):
                                            eqp = False
                                    if (
                                        sk_distance(g.EndPoint, bg.EndPoint)
                                        > knot_tolerance
                                    ):
                                        if (
                                            sk_distance(g.EndPoint, bg.StartPoint)
                                            > knot_tolerance
                                        ):
                                            eqp = False
                                    # print(simu_dist(g.StartPoint,bg.StartPoint))
                                    # print(simu_dist(g.StartPoint,bg.EndPoint))
                                    # print(simu_dist(g.EndPoint,bg.StartPoint))
                                    # #if simu_dist(g.StartPoint,bg.StartPoint) > knot_tolerance:
                                    # #        eqp = False
                                    # print(simu_dist(g.EndPoint,bg.EndPoint))
                                    # if simu_dist(g.EndPoint,bg.EndPoint) > knot_tolerance:
                                    #        eqp = False
                                    # for k,kn in enumerate (bg.KnotSequence):
                                    # if abs(kn-g.KnotSequence[k]) > knot_tolerance:
                                    #    print (kn,g.KnotSequence[k])
                                    #    if abs(kn-g.KnotSequence[k]) > knot_tolerance:
                                    # if (kn == g.KnotSequence[k]):
                                    #        eqp = False
                                    if eqp:
                                        print("identical splines found")  # ,g,bg)
                                        if j not in idx_to_del:
                                            idx_to_del.append(j)
                        j += 1
        j = 0
        # print(idx_to_del)
        if len(idx_to_del) > 0:
            FreeCAD.Console.PrintMessage("sanitizing " + s.Label)
            FreeCAD.Console.PrintMessage("\n")
            idx_to_del.sort()
            # print(idx_to_del)
            idx_to_del.reverse()
            # print(idx_to_del)
            # stop
            for i, e in enumerate(idx_to_del):
                # print('to delete ',s.Geometry[(e)],e)
                print("deleting identical geo")
                # print(s.Geometry)
                s.delGeometry(e)
                # print(s.Geometry)
        FreeCAD.ActiveDocument.commitTransaction()
        return s.Geometry
    else:
        return None


##


def radial_vector(point, axis_pnt, axis):
    chord = axis_pnt.sub(point)
    norm = axis.cross(chord)
    perp = axis.cross(norm)
    # FreeCAD.Console.PrintLog( str(chord) + ' ' + str(norm) + ' ' + str(perp)+'\n')
    # test_line = Part.makeLine(axis_pnt.add(dist_rv),axis_pnt)
    # test_line = Part.makeLine(axis_pnt.add(perp),axis_pnt)
    # test_line = Part.makeLine(point, axis_pnt)
    # Part.show(test_line)
    return perp.normalize()


def equal_angle(ang1, ang2, p=5):
    # compares two angles
    result = False
    if round(ang1 - ang2, p) == 0:
        result = True
    if round((ang1 - 2.0 * math.pi) - ang2, p) == 0:
        result = True
    if round(ang1 - (ang2 - 2.0 * math.pi), p) == 0:
        result = True
    return result


def equal_edge(edg1, edg2, p=5):
    result = True
    if len(edg1.Vertexes) > 1:
        if not (
            equal_vertex(edg1.Vertexes[0], edg2.Vertexes[0])
            or equal_vertex(edg1.Vertexes[0], edg2.Vertexes[1])
        ):
            result = False
        if not (
            equal_vertex(edg1.Vertexes[1], edg2.Vertexes[0])
            or equal_vertex(edg1.Vertexes[1], edg2.Vertexes[1])
        ):
            result = False
    else:
        if not (equal_vertex(edg1.Vertexes[0], edg2.Vertexes[0])):
            result = False
        if len(edg2.Vertexes) > 1:
            result = False
    return result


class Simple_node(object):
    """This class defines the nodes of a tree, that is the result of
    the analysis of a sheet-metal-part.
    Each flat or bend part of the metal-sheet gets a node in the tree.
    The indexes are the number of the face in the original part.
    Faces of the edge of the metal-sheet need in cases to be split.
    These new faces are added to the index list.
    """

    global KFACTORSTANDARD

    def __init__(
        self,
        f_idx=None,
        Parent_node=None,
        Parent_edge=None,
        k_factor_lookup=None,
    ):
        self.idx = f_idx  # Index of the "top-face"
        self.c_face_idx = (
            None  # Face index to the opposite face of the sheet (counter-face)
        )
        self.node_type = None  # 'Flat' or 'Bend'
        self.p_node = Parent_node  # Parent node
        self.p_edge = Parent_edge  # The connecting edge to the parent node
        self.child_list = []  # List of child-nodes = link to tree structure
        self.child_idx_lists = []  # List of lists with child_idx and child_edge
        # need a list of indices of child faces
        self.sheet_edges = []  # List of edges without child-face
        self.axis = None  # Direction of the axis of the detected cylindrical face
        self.facePosi = None
        self.bendCenter = None  # Vector of the center of the detected cylindrical face
        self.distCenter = (
            None  # Value used to detect faces at opposite side of the bend
        )
        self.innerRadius = None  # nominal radius of the bend
        # self.axis for 'Flat'-face: vector pointing from the surface into the metal
        self.bend_dir = None  # Bend direction values: "up" or "down"
        self.bend_angle = None  # Angle in radians
        self.tan_vec = None  # Direction of translation for Bend nodes
        self.oppositePoint = None  # Point of a vertex on the opposite site, used to align points to the sheet plane
        self.vertexDict = (
            {}
        )  # Vertexes of a bend, original and unbend coordinates, flags p, c, t, o
        self.edgeDict = (
            {}
        )  # Unbend edges dictionary, key is a combination of indexes to vertexDict.
        self._trans_length = None  # Length of translation for Bend nodes
        self.analysis_ok = (
            True  # Indicator if something went wrong with the analysis of the face
        )
        self.error_code = None  # Index to unfold_error dictionary
        self.k_factor_lookup = (
            k_factor_lookup  # K-factor lookup dictionary, according to ANSI standard
        )
        # new node features:
        self.nfIndexes = (
            []
        )  # List of all face-indexes of a node (flat and bend: folded state)
        self.seam_edges = []  # List with edges to seams
        # bend faces are needed for movement simulation at single other bends.
        # otherwise unfolded faces are recreated from self.b_edges
        self.node_flattened_faces = []  # Faces of a flattened bend node
        self.unfoldTopList = None  # Source of identical side edges
        self.unfoldCounterList = None  # Source of identical side edges
        self.actual_angle = None  # State of angle in refolded sheet metal part
        self.p_wire = None  # Wire common with parent node, used for bend node
        self.c_wire = None  # Wire common with child node, used for bend node
        self.b_edges = (
            []
        )  # List of edges in a bend node, that needs to be recalculated, at unfolding

    def dump(self):
        print("Node: %s" % (str(self.idx)))
        print("  Type: %s" % (str(self.node_type)))
        print("  Parent: %s" % (str(self.p_node)))
        print("  Parent edge: %s" % (str(self.p_edge)))
        print("  Children: %s" % (str(self.child_list)))
        print("  Child idx lists: %s" % (str(self.child_idx_lists)))
        print("  Sheet edges: %s" % (str(self.sheet_edges)))
        print("  Axis: %s" % (str(self.axis)))
        print("  Face position: %s" % (str(self.facePosi)))
        print("  Bend center: %s" % (str(self.bendCenter)))
        print("  Distance to center: %s" % (str(self.distCenter)))
        print("  Inner radius: %s" % (str(self.innerRadius)))
        print("  Bend direction: %s" % (str(self.bend_dir)))
        print("  Bend angle: %s" % (str(self.bend_angle)))
        print("  Tangent vector: %s" % (str(self.tan_vec)))
        print("  Opposite point: %s" % (str(self.oppositePoint)))
        print("  Vertex dictionary: %s" % (str(self.vertexDict)))
        print("  Edge dictionary: %s" % (str(self.edgeDict)))
        print("  translation length %s" % (str(self._trans_length)))
        print("  Analysis ok: %s" % (str(self.analysis_ok)))
        print("  Error code: %s" % (str(self.error_code)))
        print("  K-factor lookup: %s" % (str(self.k_factor_lookup)))
        print("  nfIndexes: %s" % (str(self.nfIndexes)))
        print("  seam edges: %s" % (str(self.seam_edges)))
        print("  node flattened faces: %s" % (str(self.node_flattened_faces)))
        print("  unfoldTopList: %s" % (str(self.unfoldTopList)))
        print("  unfoldCounterList: %s" % (str(self.unfoldCounterList)))
        print("  actual angle: %s" % (str(self.actual_angle)))
        print("  p_wire: %s" % (str(self.p_wire)))
        print("  c_wire: %s" % (str(self.c_wire)))
        print("  b_edges: %s" % (str(self.b_edges)))

    def get_Face_idx(self):
        # get the face index from the tree-element
        return self.idx

    @property
    def k_Factor(self):

        k = get_val_from_range(self.k_factor_lookup, self.innerRadius / self.thickness)

        return k if KFACTORSTANDARD == "ansi" else k / 2

    @k_Factor.setter
    def k_Factor(self, val):
        SMLogger.error("k_Factor is a readonly property! Won't set to:", val)


def get_surface(face):
    # 'searchSubShape' is used to distinguish upstream FreeCAD with LinkStage3
    # branch, which has a different implementation of findPlane()
    if hasattr(face, "searchSubShape"):
        try:
            surface = face.findPlane()
            if surface:
                return surface
        except Exception:
            pass
    surface = face.Surface
    if face.Orientation == "Reversed" and isinstance(surface, Part.Plane):
        return Part.Plane(surface.Position, -surface.Axis)
    return surface


class SheetTree(object):

    # Class representing a wire to replace in the unfolded shape. During tree creation, some features are detected
    # (e.g. countersink and counterbore holes) and are replaced later when the unfolded shape is created.
    class WireReplacement:
        def __init__(self, face_idx, wire_idx, new_wire):
            self.face_idx = face_idx
            self.wire_idx = wire_idx
            self.new_wire = new_wire

    def dump(self):
        FreeCAD.Console.PrintLog("Dumping tree:" + "\n")
        print("Root node:")
        print(self.root)
        print("f_list:")
        print(self.f_list)
        print("index_list:")
        print(self.index_list)
        print("index Unfold list:")
        print(self.index_unfold_list)

    def __init__(self, TheShape, f_idx, k_factor_lookup):
        self.cFaceTol = 0.002  # tolerance to detect counter-face vertices
        # this high tolerance was needed for more real parts
        self.root = None  # make_new_face_node adds the root node if parent_node == None
        self.__Shape = TheShape.copy()
        self.error_code = None
        self.failed_face_idx = None
        self.k_factor_lookup = k_factor_lookup
        self.wire_replacements = (
            []
        )  # list of wires to be replaced during unfold shape creation

        if not self.__Shape.isValid():
            FreeCAD.Console.PrintLog("The shape is not valid!" + "\n")
            self.error_code = 4  # Starting: invalid shape
            self.failed_face_idx = f_idx

        # Part.show(self.__Shape)

        # List of indices to the shape.Faces. The list is used a lot for face searches.
        # Some faces will be cut and the new ones added to the list.
        # So a list of faces independent of the shape is needed.
        self.f_list = []  # self.__Shape.Faces.copy() does not work
        self.index_list = []
        self.index_unfold_list = []  # indexes needed for unfolding
        for i in range(len(self.__Shape.Faces)):
            # for i in range(len (self.f_list)):
            # if i<>(f_idx):
            self.index_list.append(i)
            self.index_unfold_list.append(i)
            self.f_list.append(self.__Shape.Faces[i])
        # print self.index_list
        self.max_f_idx = len(
            self.f_list
        )  # need this value to make correct indices to new faces
        self.unfoldFaces = len(
            self.f_list
        )  # need the original number of faces for error detection

        # withoutSplitter = self.__Shape.removeSplitter()
        # if self.unfoldFaces > len(withoutSplitter.Faces): # This is not a good idea! Most sheet metal parts have unneeded edges.
        # print 'got case which needs a refine shape from the Part workbench!'
        # self.error_code = 5
        # self.failed_face_idx = f_idx

        theVol = self.__Shape.Volume
        if theVol < 0.0001:
            FreeCAD.Console.PrintLog(
                "Shape is not a real 3D-object or to small for a metal-sheet!" + "\n"
            )
            self.error_code = 1
            self.failed_face_idx = f_idx
            return

        # Make a first estimate of the thickness
        estimated_thickness = theVol / (self.__Shape.Area / 2.0)
        FreeCAD.Console.PrintLog(
            "approximate Thickness: " + str(estimated_thickness) + "\n"
        )
        # Measure the real thickness of the initial face:
        # Use Orientation and Axis to make a measurement vector

        if not hasattr(self.__Shape.Faces[f_idx], "Surface"):
            return

        # Part.show(self.__Shape.Faces[f_idx])
        # print 'the object is a face! vertices: ', len(self.__Shape.Faces[f_idx].Vertexes)
        F_type = self.__Shape.Faces[f_idx].Surface
        # FIXME: through an error, if not Plane Object
        FreeCAD.Console.PrintLog("It is a: " + str(F_type) + "\n")
        FreeCAD.Console.PrintLog(
            "Orientation: " + str(self.__Shape.Faces[f_idx].Orientation) + "\n"
        )

        # Need a point on the surface to measure the thickness.
        # Sheet edges could be sloping, so there is a danger to measure
        # right at the edge.
        # Try with Arithmetic mean of plane vertices
        m_vec = Base.Vector(0.0, 0.0, 0.0)  # calculating a mean vector
        for Vvec in self.__Shape.Faces[f_idx].Vertexes:
            # m_vec = m_vec.add(Base.Vector(Vvec.X, Vvec.Y, Vvec.Z))
            m_vec = m_vec.add(Vvec.Point)
        mvec = m_vec.multiply(1.0 / len(self.__Shape.Faces[f_idx].Vertexes))
        FreeCAD.Console.PrintLog("mvec: " + str(mvec) + "\n")

        # if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
        # s_Posi = self.__Shape.Faces[f_idx].Surface.Position
        # k = 0
        # while k < len(self.__Shape.Faces[f_idx].Vertexes):
        # FIXME: what if measurepoint is outside?

        if self.__Shape.isInside(mvec, 0.00001, True):
            measure_pos = mvec
            gotValidMeasurePosition = True
        else:
            gotValidMeasurePosition = False
            for pvert in self.__Shape.Faces[f_idx].OuterWire.Vertexes:
                # pvert = self.__Shape.Faces[f_idx].Vertexes[k]
                pvec = Base.Vector(pvert.X, pvert.Y, pvert.Z)
                shiftvec = mvec.sub(pvec)
                shiftvec = shiftvec.normalize() * 2.0 * estimated_thickness
                measure_pos = pvec.add(shiftvec)
                if self.__Shape.isInside(measure_pos, 0.00001, True):
                    gotValidMeasurePosition = True
                    break

        # Description: Checks if a point is inside a solid with a certain tolerance.
        # If the 3rd parameter is True a point on a face is considered as inside
        # if not self.__Shape.isInside(measure_pos, 0.00001, True):
        if not gotValidMeasurePosition:
            FreeCAD.Console.PrintLog(
                "Starting measure_pos for thickness measurement is outside!\n"
            )
            self.error_code = 2
            self.failed_face_idx = f_idx

        surface = get_surface(self.__Shape.Faces[f_idx])
        s_Axis = surface.Axis
        s_Posi = surface.Position
        # print 'We have a position: ', s_Posi
        s_Axismp = Base.Vector(s_Axis.x, s_Axis.y, s_Axis.z).multiply(
            2.0 * estimated_thickness
        )
        # Part.show(Meassure_axis)
        Meassure_axis = Part.makeLine(measure_pos, measure_pos.sub(s_Axismp))
        ext_Vec = Base.Vector(-s_Axis.x, -s_Axis.y, -s_Axis.z)

        lostShape = self.__Shape.copy()
        lLine = Meassure_axis.common(lostShape)
        lLine = Meassure_axis.common(self.__Shape)
        FreeCAD.Console.PrintLog("lLine number edges: " + str(len(lLine.Edges)) + "\n")
        measVert = Part.Vertex(measure_pos)
        for mEdge in lLine.Edges:
            if equal_vertex(mEdge.Vertexes[0], measVert) or equal_vertex(
                mEdge.Vertexes[1], measVert
            ):
                self.__thickness = mEdge.Length

        # self.__thickness = lLine.Length
        if (self.__thickness < estimated_thickness) or (
            self.__thickness > 1.9 * estimated_thickness
        ):
            self.error_code = 3
            self.failed_face_idx = f_idx
            FreeCAD.Console.PrintLog(
                "estimated thickness: "
                + str(estimated_thickness)
                + " measured thickness: "
                + str(self.__thickness)
                + "\n"
            )
            Part.show(lLine, "Measurement_Thickness_trial")

    def get_node_faces(self, theNode, wires_e_lists):
        """This function searches for all faces making up the node, except
        of the top and bottom face, which are already there.
        wires_e_list is the list of wires lists of the top face without the parent-edge
        theNode: the actual node to be filled with data.
        """

        # Where to start?
        # Searching for all faces that have two vertices in common with
        # an edge from the list should give the sheet edge.
        # But, we also need to look at the sheet edge, in order to not claim
        # faces from the next node!
        # Then we have to treat those faces that belong to more than one node.
        # Those faces needs to be cut and the face list needs to be updated.
        # Look also at the number of wires of the top face. More wires will
        # indicate a hole or a feature.

        found_indices = []
        # A search strategy for faces based on the wires_e_lists is needed.

        for theWire in wires_e_lists:
            for theEdge in theWire:
                analyVert = theEdge.Vertexes[0]
                for i in self.index_list:
                    for lookVert in self.f_list[i].Vertexes:
                        if equal_vertex(lookVert, analyVert):
                            if len(theEdge.Vertexes) == 1:  # Edge is a circle
                                if not self.is_sheet_edge_face(theEdge, theNode):
                                    found_indices.append(i)  # found a node face
                                    theNode.child_idx_lists.append([i, theEdge])
                                    # self.index_list.remove(i) # remove this face from the index_list
                                    # Part.show(self.f_list[i])
                            else:
                                nextVert = theEdge.Vertexes[1]
                                for looknextVert in self.f_list[i].Vertexes:
                                    if equal_vertex(looknextVert, nextVert):
                                        # Special case to handle : sometimes, holes are defined as two semicircles, thus there are 2 edges and 2 interior faces for the hole.
                                        # Since both edges have the exact same vertices, this algorithm would bind each interior face with each edge, so we'd get something
                                        # like that : [[face1, edge1], [face2, edge2], [face1, edge2], [face2, edge1]]. Here the last two pairs are not valid, thus we remove
                                        # them by checking that the edge is part of the face before adding the pair to the list.
                                        edge_faces = self.__Shape.ancestorsOfType(
                                            theEdge, Part.Face
                                        )
                                        found = False

                                        for edge_face in edge_faces:
                                            if edge_face.isSame(self.f_list[i]):
                                                found = True
                                                break

                                        if found:
                                            if not self.is_sheet_edge_face(
                                                theEdge, theNode
                                            ):
                                                found_indices.append(
                                                    i
                                                )  # found a node face
                                                theNode.child_idx_lists.append(
                                                    [i, theEdge]
                                                )
                                                # self.index_list.remove(i) # remove this face from the index_list
                                                # Part.show(self.f_list[i])
        FreeCAD.Console.PrintLog("found_indices: " + str(found_indices) + "\n")

    def is_sheet_edge_face(self, ise_edge, tree_node):  # ise_edge: IsSheetEdge_edge
        # Idea: look at properties of neighbor face
        # Look at edges with distance of sheet-thickness.
        #    if found and surface == cylinder, check if it could be a bend-node.
        # Look at number of edges:
        # A face with 3 edges is at the sheet edge Cylinder-face or triangle (oh no!)
        # need to look also at surface!
        # A sheet edge face with more as 4 edges, is common to more than 1 node.

        # get the face which has a common edge with ise_edge
        the_index = None
        has_sheet_distance_vertex = False
        for i in self.index_list:
            for sf_edge in self.f_list[i].Edges:
                if self.same_edges(sf_edge, ise_edge):
                    the_index = i
                    # print 'got edge face: Face', str(i+1)
                    break
            if the_index is not None:
                break

        # Simple strategy applied: look if the connecting face has vertexes
        # with sheet-thickness distance to the top face.
        # FIXME: this will fail with sharpened sheet edges with two faces
        # between top and bottom.
        if the_index is not None:
            # now we need to search for vertexes with sheet_thickness_distance
            for F_vert in self.f_list[i].Vertexes:
                # vDist = self.getDistanceToFace(F_vert, tree_node)
                # if vDist > maxDist: maxDist = vDist
                # if vDist < minDist: minDist = vDist
                # maxDist = maxDist- self.__thickness
                # if (minDist > -self.cFaceTol) and (maxDist < self.cFaceTol) and (maxDist > -self.cFaceTol):

                if self.isVertOpposite(F_vert, tree_node):
                    has_sheet_distance_vertex = True
                    if len(self.f_list[i].Edges) < 5:
                        tree_node.nfIndexes.append(i)
                        self.index_list.remove(i)
                        # Part.show(self.f_list[i])
                    else:
                        # need to cut the face at the ends of ise_edge
                        self.divideEdgeFace(i, ise_edge, F_vert, tree_node)
                    break

        else:
            tree_node.analysis_ok = False
            tree_node.error_code = (
                15  # Analysis: the code needs a face at all sheet edges
            )
            self.error_code = 15
            self.failed_face_idx = tree_node.idx
            Part.show(self.f_list[tree_node.idx])

        return has_sheet_distance_vertex

    # Method to check if two edges are the same, i.e. they have the same vertices.
    # This is needed because sometimes an edge may be defined twice but with vertices in a different order, thus edge1.isSame(edge2) may fail even though it is the same edge
    # Right now this works only if the edge has two vertices, to be improved later if needed.
    def same_edges(self, edge1, edge2):
        return edge1.isSame(edge2) or (
            len(edge1.Vertexes) == 2
            and len(edge2.Vertexes) == 2
            and edge1.firstVertex().isSame(edge2.lastVertex())
            and edge2.firstVertex().isSame(edge1.lastVertex())
        )

    def isVertOpposite(self, theVert, theNode):
        F_type = str(get_surface(self.f_list[theNode.idx]))
        vF_vert = Base.Vector(theVert.X, theVert.Y, theVert.Z)
        if F_type == "<Plane object>":
            distFailure = (
                vF_vert.distanceToPlane(theNode.facePosi, theNode.axis)
                - self.__thickness
            )
        elif F_type == "<Cylinder object>":
            distFailure = (
                vF_vert.distanceToLine(theNode.bendCenter, theNode.axis)
                - theNode.distCenter
            )
        else:
            distFailure = 100.0
            theNode.error_code = (
                17  # Analysis: the code needs a face at all sheet edges
            )
            self.error_code = 17
            self.failed_face_idx = theNode.idx
            # Part.show(self.f_list[theNode.idx], 'SurfaceType_not_supported')
        # print "counter face distance: ", dist_v + self.__thickness
        if (distFailure < self.cFaceTol) and (distFailure > -self.cFaceTol):
            return True
        else:
            return False

    def getDistanceToFace(self, theVert, theNode):
        F_type = str(get_surface(self.f_list[theNode.idx]))
        vF_vert = Base.Vector(theVert.X, theVert.Y, theVert.Z)
        # a positive distance should go through the sheet metal
        if F_type == "<Plane object>":
            dist = vF_vert.distanceToPlane(theNode.facePosi, theNode.axis)
        if F_type == "<Cylinder object>":
            dist = (
                vF_vert.distanceToLine(theNode.bendCenter, theNode.axis)
                - self.f_list[theNode.idx].Surface.Radius
            )
            if theNode.bend_dir == "down":
                dist = -dist
        return dist

    def divideEdgeFace(self, fIdx, ise_edge, F_vert, tree_node):
        FreeCAD.Console.PrintLog("Sheet edge face has more than 4 edges!\n")
        # first find out where the Sheet edge face has no edge to the opposite side of the sheet
        # There is a need to cut the face.
        # make a cut-tool perpendicular to the ise_edge
        # cut the face and select the good one to add to the node
        # make another cut, in order to add the residual face(s) to the face list.

        # Search edges in the face with a vertex common with ise_edge
        F_type = str(get_surface(self.f_list[tree_node.idx]))
        needCut0 = True
        firstCutFaceIdx = None
        for sEdge in self.f_list[fIdx].Edges:
            if equal_vertex(
                ise_edge.Vertexes[0], sEdge.Vertexes[0]
            ) and self.isVertOpposite(sEdge.Vertexes[1], tree_node):
                needCut0 = False
                theEdge = sEdge
            if equal_vertex(
                ise_edge.Vertexes[0], sEdge.Vertexes[1]
            ) and self.isVertOpposite(sEdge.Vertexes[0], tree_node):
                needCut0 = False
                theEdge = sEdge
        if needCut0:
            # print "need Cut at 0 with fIdx: ", fIdx
            nFace = self.cutEdgeFace(0, fIdx, ise_edge, tree_node)

            tree_node.nfIndexes.append(self.max_f_idx)
            self.f_list.append(nFace)
            firstCutFaceIdx = self.max_f_idx
            self.max_f_idx += 1
            # self.f_list.append(rFace)
            # self.index_list.append(self.max_f_idx)
            # self.max_f_idx += 1
            # self.index_list.remove(fIdx)
            # Part.show(nFace)
        # else:
        #  Part.show(theEdge)

        needCut1 = True
        for sEdge in self.f_list[fIdx].Edges:
            if equal_vertex(ise_edge.Vertexes[1], sEdge.Vertexes[0]):
                if self.isVertOpposite(sEdge.Vertexes[1], tree_node):
                    needCut1 = False
                    theEdge = sEdge
            if equal_vertex(ise_edge.Vertexes[1], sEdge.Vertexes[1]):
                if self.isVertOpposite(sEdge.Vertexes[0], tree_node):
                    needCut1 = False
                    theEdge = sEdge
        if needCut1:
            if needCut0:
                fIdx = firstCutFaceIdx
                tree_node.nfIndexes.remove(fIdx)
            # print "need Cut at 1 with fIdx: ", fIdx
            nFace = self.cutEdgeFace(1, fIdx, ise_edge, tree_node)
            tree_node.nfIndexes.append(self.max_f_idx)
            self.f_list.append(nFace)
            firstCutFaceIdx = self.max_f_idx
            self.max_f_idx += 1
            # self.f_list.append(rFace)
            # self.index_list.append(self.max_f_idx)
            # self.max_f_idx += 1
            # if not needCut0:
            #  self.index_list.remove(fIdx)
            # Part.show(nFace)
        # else:
        #  Part.show(theEdge)

    def cutEdgeFace(self, eIdx, fIdx, theEdge, theNode):
        """This function cuts a face in two pieces.
        one piece is connected to the node.
        The residual piece is discarded.
        The function returns the piece that has a common edge with the top face of theNode.
        """
        # print "now the face cutter: ", fIdx, ' ', eIdx, ' ', theNode.idx
        # Part.show(theEdge, 'EdgeToCut'+ str(theNode.idx+1)+'_')
        # Part.show(self.f_list[fIdx], 'FaceToCut'+ str(theNode.idx+1)+'_')

        if eIdx == 0:
            otherIdx = 1
        else:
            otherIdx = 0

        origin = theEdge.Vertexes[eIdx].Point

        F_type = str(get_surface(self.f_list[theNode.idx]))
        if F_type == "<Plane object>":
            tan_vec = theEdge.Vertexes[eIdx].Point - theEdge.Vertexes[otherIdx].Point
            # o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z)
            tan_vec.normalize()
            # New approach: search for the nearest vertex at the opposite site.
            # The cut is done between the Vertex indicated by eIdx and the nearest
            # opposite vertex. This approach should avoid the generation of
            # additional short edges in the side faces.
            searchAxis = theNode.axis
            # else:
            # searchAxis = radVector

            maxDistance = 1000
            oppoPoint = None
            # print('need to check Face', str(fIdx+1), ' with ', len(self.f_list[fIdx].Vertexes))
            for theVert in self.f_list[fIdx].Vertexes:
                # need to check if theVert has
                if self.isVertOpposite(theVert, theNode):
                    vertDist = theVert.Point.distanceToLine(origin, searchAxis)
                    if vertDist < maxDistance:
                        maxDistance = vertDist
                        oppoPoint = theVert.Point

            if oppoPoint is None:
                print(" error need always an opposite point in a side face!")
                # FIXME: need a proper error condition.

            # vec1 = Base.Vector(theNode.axis.x, theNode.axis.y, theNode.axis.z) # make a copy
            vec1 = (oppoPoint - origin).normalize()

            crossVec = tan_vec.cross(vec1)
            crossVec.multiply(3.0 * self.__thickness)

            vec1.multiply(self.__thickness)
            # defining the points of the cutting plane:
            Spnt1 = origin - vec1 - crossVec
            Spnt2 = origin - vec1 + crossVec
            Spnt3 = origin + vec1 + vec1 + crossVec
            Spnt4 = origin + vec1 + vec1 - crossVec

        if F_type == "<Cylinder object>":
            ePar = theEdge.parameterAt(theEdge.Vertexes[eIdx])
            FreeCAD.Console.PrintLog("Idx: " + str(eIdx) + " ePar: " + str(ePar) + "\n")
            otherPar = theEdge.parameterAt(theEdge.Vertexes[otherIdx])
            tan_vec = theEdge.tangentAt(ePar)
            if ePar < otherPar:
                tan_vec.multiply(-1.0)

            # tan_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(tan_vec), theEdge.Vertexes[eIdx].Point)
            # Part.show(tan_line, 'tan_line'+ str(theNode.idx+1)+'_')

            edge_vec = theEdge.Vertexes[eIdx].copy().Point
            radVector = radial_vector(edge_vec, theNode.bendCenter, theNode.axis)
            if theNode.bend_dir == "down":
                radVector.multiply(-1.0)

            # rad_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(radVector), theEdge.Vertexes[eIdx].Point)
            # Part.show(rad_line, 'rad_line'+ str(theNode.idx+1)+'_')
            searchAxis = radVector

            maxDistance = 1000
            oppoPoint = None
            # print('need to check Face', str(fIdx+1), ' with ', len(self.f_list[fIdx].Vertexes))
            for theVert in self.f_list[fIdx].Vertexes:
                # need to check if theVert has
                if self.isVertOpposite(theVert, theNode):
                    vertDist = theVert.Point.distanceToLine(origin, searchAxis)
                    if vertDist < maxDistance:
                        maxDistance = vertDist
                        oppoPoint = theVert.Point

            if oppoPoint is None:
                print(" error need always an opposite point in a side face!")
                # FIXME: need a proper error condition.
            # vec1 = Base.Vector(radVector.x, radVector.y, radVector.z) # make a copy
            vec1 = (oppoPoint - origin).normalize()

            crossVec = tan_vec.cross(vec1)
            crossVec.multiply(3.0 * self.__thickness)

            vec1.multiply(self.__thickness)
            # defining the points of the cutting plane:
            Spnt1 = origin - vec1 - crossVec
            Spnt2 = origin - vec1 + crossVec
            Spnt3 = origin + vec1 + vec1 + crossVec
            Spnt4 = origin + vec1 + vec1 - crossVec

        Sedge1 = Part.makeLine(Spnt1, Spnt2)
        Sedge2 = Part.makeLine(Spnt2, Spnt3)
        Sedge3 = Part.makeLine(Spnt3, Spnt4)
        Sedge4 = Part.makeLine(Spnt4, Spnt1)

        Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
        # Part.show(Sw1, 'cutWire'+ str(theNode.idx+1)+'_')
        Sf1 = Part.Face(Sw1)  #
        # Part.show(Sf1, 'cutFace'+ str(theNode.idx+1)+'_')
        # cut_solid = Sf1.extrude(tan_vec.multiply(5.0))
        cut_solid = Sf1.extrude(tan_vec.multiply(self.__thickness))
        # Part.show(cut_solid, 'cut_solid'+ str(theNode.idx+1)+'_')
        # cut_opposite = Sf1.extrude(tan_vec.multiply(-5.0))

        cutFaces_node = self.f_list[fIdx].cut(cut_solid)
        for cFace in cutFaces_node.Faces:
            for myVert in cFace.Vertexes:
                if equal_vertex(theEdge.Vertexes[eIdx], myVert):
                    nodeFace = cFace
                    # print "The nodeFace Idx: ", fIdx, ' eIdx: ', eIdx
                    # Part.show(nodeFace)
                    break

        return nodeFace  # , residueFace

    def getBendAngle(self, newNode, wires_e_lists):
        """Get the bend angle for a node connected to a bend face,
        Get the k-Factor
        Get the translation Length
        """
        # newNode = Simple_node(face_idx, P_node, P_edge)
        P_node = newNode.p_node
        P_edge = newNode.p_edge
        face_idx = newNode.idx
        theFace = self.__Shape.Faces[face_idx]

        s_Axis = newNode.axis
        s_Center = newNode.bendCenter

        # Start to investigate the angles at self.__Shape.Faces[face_idx].ParameterRange[0]
        angle_0 = theFace.ParameterRange[0]
        angle_1 = theFace.ParameterRange[1]

        # idea: identify the angle at edge_vec = P_edge.Vertexes[0].copy().Point
        # This will be = angle_start
        # calculate the tan_vec from valueAt

        edge_vec = P_edge.Vertexes[0].copy().Point
        edgeAngle, edgePar = theFace.Surface.parameter(edge_vec)

        # print 'the angles: ', angle_0, ' ', angle_1, ' ', edgeAngle, ' ', edgeAngle - 2*math.pi

        if equal_angle(angle_0, edgeAngle):
            angle_start = angle_0
            angle_end = angle_1
        else:
            angle_start = angle_1
            angle_end = angle_0
        len_start = edgePar

        newNode.bend_angle = angle_end - angle_start
        angle_tan = (
            angle_start + newNode.bend_angle / 6.0
        )  # need to have the angle_tan before correcting the sign

        if newNode.bend_angle < 0.0:
            newNode.bend_angle = -newNode.bend_angle

        first_vec = radial_vector(edge_vec, s_Center, s_Axis)
        tanPos = self.__Shape.Faces[face_idx].valueAt(angle_tan, len_start)
        sec_vec = radial_vector(tanPos, s_Center, s_Axis)

        cross_vec = first_vec.cross(sec_vec)
        triple_prod = cross_vec.dot(s_Axis)
        if triple_prod < 0:
            newNode.axis = -newNode.axis
            s_Axis = -s_Axis

        # tan_vec = radial_vector(tanPos, s_Center, s_Axis)
        tan_vec = s_Axis.cross(first_vec)
        # Part.show(Part.makeLine(tanPos, tanPos + 10 * tan_vec), 'tan_Vec')
        newNode.tan_vec = tan_vec
        # make a better tan_vec based on the parent face normal and the parent edge:
        if P_node.node_type == "Flat":
            pVec = P_edge.Vertexes[1].Point - P_edge.Vertexes[0].Point
            pVec = pVec.normalize()
            pTanVec = P_node.axis.cross(pVec)
            if (tan_vec - pTanVec).Length > 1.0:
                newNode.tan_vec = -pTanVec
            else:
                newNode.tan_vec = pTanVec

        if newNode.bend_dir == "up":
            innerRadius = theFace.Surface.Radius
        else:
            innerRadius = theFace.Surface.Radius - self.__thickness

        # Will be used to determine the correct K-factor
        newNode.thickness = self.__thickness
        newNode.innerRadius = innerRadius

        FreeCAD.Console.PrintLog(
            newNode.bend_dir
            + " Face"
            + str(newNode.idx + 1)
            + " k-factor: "
            + str(newNode.k_Factor)
            + "\n"
        )
        newNode._trans_length = (
            innerRadius + newNode.k_Factor * self.__thickness
        ) * newNode.bend_angle

        # print 'newNode._trans_length: ', newNode._trans_length
        cAngle_0 = self.__Shape.Faces[newNode.c_face_idx].ParameterRange[0]
        cAngle_1 = self.__Shape.Faces[newNode.c_face_idx].ParameterRange[1]

        cFaceAngle = cAngle_1 - cAngle_0

        if newNode.bend_angle > 0:
            if cFaceAngle > 0:
                diffAngle = newNode.bend_angle - cFaceAngle
            else:
                diffAngle = newNode.bend_angle + cFaceAngle
        else:
            if cFaceAngle > 0:
                diffAngle = cFaceAngle + newNode.bend_angle
            else:
                diffAngle = newNode.bend_angle - cFaceAngle

        # print 'node angles: ', newNode.bend_angle, ' ', diffAngle

    def make_new_face_node(self, face_idx, P_node, P_edge, wires_e_lists):
        # e_list: list of edges of the top face of a node without the parent-edge (P_edge)
        # analyze the face and get type of face ("Flat" or "Bend")
        # search the counter face, get axis of Face
        # In case of "Bend" get angle, k_factor and trans_length
        # put the node into the tree
        newNode = Simple_node(face_idx, P_node, P_edge, self.k_factor_lookup)

        # This face should be a node in the tree, and is therefore known!
        # removed from the list of all unknown faces
        self.index_list.remove(face_idx)
        # This means, it could also not be found as neighbor face anymore.
        # newNode.node_faces.append(self.f_list[face_idx].copy())
        newNode.nfIndexes.append(face_idx)

        such_list = []
        for k in self.index_list:
            such_list.append(k)

        surface = get_surface(self.__Shape.Faces[face_idx])
        F_type = str(surface)

        if F_type == "<Plane object>":
            newNode.node_type = "Flat"  # FIXME

            s_Posi = surface.Position
            newNode.facePosi = s_Posi
            s_Axis = surface.Axis
            ext_Vec = Base.Vector(-s_Axis.x, -s_Axis.y, -s_Axis.z)

            newNode.axis = ext_Vec
            axis_line = Part.makeLine(s_Posi.add(ext_Vec), s_Posi)
            # Part.show(axis_line, 'axis_line'+str(face_idx+1))

            # need a mean point of the face to avoid false counter faces
            faceMiddle = Base.Vector(0.0, 0.0, 0.0)  # calculating a mean vector
            for Vvec in self.__Shape.Faces[face_idx].OuterWire.Vertexes:
                faceMiddle = faceMiddle.add(Vvec.Point)
            faceMiddle = faceMiddle.multiply(
                1.0 / len(self.__Shape.Faces[face_idx].OuterWire.Vertexes)
            )
            faceMiddle = faceMiddle.add(self.__thickness * ext_Vec)
            # Part.show(Part.makeLine(faceMiddle, faceMiddle + 2*ext_Vec), 'faceMiddle'+str(face_idx))

            counterFaceList = []
            gotCFace = False
            # search for the counter face
            for i in such_list:
                counter_found = True
                for F_vert in self.f_list[i].Vertexes:
                    vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
                    dist_v = vF_vert.distanceToPlane(s_Posi, ext_Vec) - self.__thickness
                    # print "counter face distance: ", dist_v + self.__thickness
                    # print 'checking Face', str(i+1), ' dist_v: ', dist_v
                    if (dist_v > self.cFaceTol) or (dist_v < -self.cFaceTol):
                        counter_found = False

                if counter_found:
                    if hasattr(FreeCADGui.Selection.getSelection()[0], "Refine"):
                        if FreeCADGui.Selection.getSelection()[0].Refine is True:
                            distance = self.__Shape.Faces[i].distToShape(
                                self.__Shape.Faces[face_idx]
                            )[0]
                            if math.isclose(distance, self.__thickness):
                                FreeCAD.Console.PrintLog(
                                    "found counter-face" + str(i + 1) + "\n"
                                )
                                counterFaceList.append([i, distance])
                                gotCFace = True
                            else:
                                counter_found = False
                        else:
                            # need a mean point of the face to avoid false counter faces
                            counterMiddle = Base.Vector(
                                0.0, 0.0, 0.0
                            )  # calculating a mean vector
                            for Vvec in self.__Shape.Faces[i].OuterWire.Vertexes:
                                counterMiddle = counterMiddle.add(Vvec.Point)
                            counterMiddle = counterMiddle.multiply(
                                1.0 / len(self.__Shape.Faces[i].OuterWire.Vertexes)
                            )

                            distVector = counterMiddle.sub(faceMiddle)
                            counterDistance = distVector.Length

                            if (
                                counterDistance < 2 * self.__thickness
                            ):  # FIXME: small stripes are a risk!
                                FreeCAD.Console.PrintLog(
                                    "found counter-face" + str(i + 1) + "\n"
                                )
                                counterFaceList.append([i, counterDistance])
                                gotCFace = True
                            else:
                                counter_found = False
                                FreeCAD.Console.PrintLog(
                                    "faceMiddle: "
                                    + str(faceMiddle)
                                    + " counterMiddle: "
                                    + str(counterMiddle)
                                    + "\n"
                                )
                    else:
                        # need a mean point of the face to avoid false counter faces
                        counterMiddle = Base.Vector(
                            0.0, 0.0, 0.0
                        )  # calculating a mean vector
                        for Vvec in self.__Shape.Faces[i].OuterWire.Vertexes:
                            counterMiddle = counterMiddle.add(Vvec.Point)
                        counterMiddle = counterMiddle.multiply(
                            1.0 / len(self.__Shape.Faces[i].OuterWire.Vertexes)
                        )

                        distVector = counterMiddle.sub(faceMiddle)
                        counterDistance = distVector.Length

                        if (
                            counterDistance < 2 * self.__thickness
                        ):  # FIXME: small stripes are a risk!
                            FreeCAD.Console.PrintLog(
                                "found counter-face" + str(i + 1) + "\n"
                            )
                            counterFaceList.append([i, counterDistance])
                            gotCFace = True
                        else:
                            counter_found = False
                            FreeCAD.Console.PrintLog(
                                "faceMiddle: "
                                + str(faceMiddle)
                                + " counterMiddle: "
                                + str(counterMiddle)
                                + "\n"
                            )

            if gotCFace:
                newNode.c_face_idx = counterFaceList[0][0]
                if (
                    len(counterFaceList) > 1
                ):  # check if more than one counterFace was detected!
                    counterDistance = counterFaceList[0][1]
                    for i in range(1, len(counterFaceList)):
                        if counterDistance > counterFaceList[i][1]:
                            counterDistance = counterFaceList[i][1]
                            newNode.c_face_idx = counterFaceList[i][0]
                self.index_list.remove(newNode.c_face_idx)
                newNode.nfIndexes.append(newNode.c_face_idx)

            # if newNode.c_face_idx == None:
            #  Part.show(axis_line)
            # if the parent is a bend: check the bend angle and correct it.
            if newNode.p_node:
                if newNode.p_node.node_type == "Bend":
                    if newNode.p_node.p_node.node_type == "Flat":
                        # calculate the angle on base of ext_Vec
                        ppVec = newNode.p_node.p_node.axis  # normal of the flat face
                        myVec = newNode.axis  # normal of the flat face
                        theAxis = newNode.p_node.axis  # Bend axis
                        angle = math.atan2(
                            ppVec.cross(myVec).dot(theAxis), ppVec.dot(myVec)
                        )
                        if angle < -math.pi / 8:
                            angle = angle + 2 * math.pi
                        # print 'compare angles, bend: ', newNode.p_node.bend_angle, ' ', angle
                        newNode.p_node.bend_angle = (
                            angle  # This seems to be an improvement!
                        )
                        # newNode.p_node.bend_angle = (angle + newNode.p_node.bend_angle) / 2.0 # this is a bad approach

                    # update the newNode.p_node.vertexDict with the Vertex data
                    # from the own vertexes corresponding to the parent edge: P_edge
                    topVertIndexes = range(len(self.__Shape.Faces[face_idx].Vertexes))
                    myFlatVertIndexes = []
                    # for theVert in self.__Shape.Faces[face_idx].Vertexes:
                    for vertIdx in topVertIndexes:
                        theVert = self.__Shape.Faces[face_idx].Vertexes[vertIdx]
                        if equal_vertex(theVert, P_edge.Vertexes[0]):
                            myFlatVertIndexes.append(vertIdx)
                        if equal_vertex(theVert, P_edge.Vertexes[1]):
                            myFlatVertIndexes.append(vertIdx)

                    rotatedFace = self.f_list[face_idx].copy()
                    trans_vec = newNode.p_node.tan_vec * newNode.p_node._trans_length
                    rotatedFace.rotate(
                        self.f_list[newNode.p_node.idx].Surface.Center,
                        newNode.p_node.axis,
                        math.degrees(-newNode.p_node.bend_angle),
                    )
                    rotatedFace.translate(trans_vec)

                    for vKey in newNode.p_node.vertexDict:
                        flagStr, origVec, unbendVec = newNode.p_node.vertexDict[vKey]
                        # for theVert in myFlatVerts:
                        for vertIdx in myFlatVertIndexes:
                            theVert = self.__Shape.Faces[face_idx].Vertexes[vertIdx]
                            if equal_vector(theVert.Point, origVec):
                                flagStr = flagStr + "c"
                                newNode.p_node.vertexDict[vKey] = (
                                    flagStr,
                                    origVec,
                                    rotatedFace.Vertexes[vertIdx].Point,
                                )

                    # update the newNode.p_node.vertexDict with the Vertex data
                    # from the own vertexes corresponding to the opposite face
                    oppVertIndexes = range(
                        len(self.__Shape.Faces[newNode.c_face_idx].Vertexes)
                    )
                    myFlatVertIndexes = []
                    # for theVert in self.__Shape.Faces[face_idx].Vertexes:
                    for vertIdx in oppVertIndexes:
                        theVert = self.__Shape.Faces[newNode.c_face_idx].Vertexes[
                            vertIdx
                        ]
                        for cVert in self.__Shape.Faces[
                            newNode.p_node.c_face_idx
                        ].Vertexes:
                            if equal_vertex(theVert, cVert):
                                myFlatVertIndexes.append(vertIdx)

                    rotatedFace = self.f_list[newNode.c_face_idx].copy()
                    trans_vec = newNode.p_node.tan_vec * newNode.p_node._trans_length
                    rotatedFace.rotate(
                        self.f_list[newNode.p_node.idx].Surface.Center,
                        newNode.p_node.axis,
                        math.degrees(-newNode.p_node.bend_angle),
                    )
                    rotatedFace.translate(trans_vec)

                    for vKey in newNode.p_node.vertexDict:
                        flagStr, origVec, unbendVec = newNode.p_node.vertexDict[vKey]
                        # for theVert in myFlatVerts:
                        for vertIdx in myFlatVertIndexes:
                            theVert = self.__Shape.Faces[newNode.c_face_idx].Vertexes[
                                vertIdx
                            ]
                            if equal_vector(theVert.Point, origVec):
                                flagStr = flagStr + "c"
                                newNode.p_node.vertexDict[vKey] = (
                                    flagStr,
                                    origVec,
                                    rotatedFace.Vertexes[vertIdx].Point,
                                )

        if F_type == "<Cylinder object>":
            newNode.node_type = "Bend"  # FIXME
            s_Center = self.__Shape.Faces[face_idx].Surface.Center
            s_Axis = self.__Shape.Faces[face_idx].Surface.Axis
            newNode.axis = s_Axis
            newNode.bendCenter = s_Center
            edge_vec = P_edge.Vertexes[0].copy().Point
            FreeCAD.Console.PrintLog("edge_vec: " + str(edge_vec) + "\n")

            if P_node.node_type == "Flat":
                dist_c = edge_vec.distanceToPlane(
                    s_Center, P_node.axis
                )  # distance to center
            else:
                P_face = self.__Shape.Faces[P_node.idx]
                radVector = radial_vector(
                    edge_vec, P_face.Surface.Center, P_face.Surface.Axis
                )
                if P_node.bend_dir == "down":
                    dist_c = edge_vec.distanceToPlane(
                        s_Center, radVector.multiply(-1.0)
                    )
                else:
                    dist_c = edge_vec.distanceToPlane(s_Center, radVector)

            if dist_c < 0.0:
                newNode.bend_dir = "down"
                thick_test = (
                    self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness
                )
                newNode.innerRadius = thick_test
            else:
                newNode.bend_dir = "up"
                thick_test = (
                    self.__Shape.Faces[face_idx].Surface.Radius + self.__thickness
                )
                newNode.innerRadius = self.__Shape.Faces[face_idx].Surface.Radius
            newNode.distCenter = thick_test
            # print "Face idx: ", face_idx, " bend_dir: ", newNode.bend_dir
            FreeCAD.Console.PrintLog(
                "Face"
                + str(face_idx + 1)
                + " Type: "
                + str(newNode.node_type)
                + " bend_dir: "
                + str(newNode.bend_dir)
                + "\n"
            )

            # calculate mean point of face:
            # FIXME implement also for cylindric faces

            # Search the face at the opposite site of the sheet:
            # for i in range(len(such_list)):
            for i in such_list:
                counter_found = True
                for F_vert in self.f_list[i].Vertexes:
                    vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
                    dist_c = vF_vert.distanceToLine(s_Center, s_Axis) - thick_test
                    if (dist_c > self.cFaceTol) or (dist_c < -self.cFaceTol):
                        counter_found = False

                if counter_found:
                    # to do calculate mean point of counter face

                    # print "found counter Face", such_list[i]+1
                    newNode.c_face_idx = i
                    self.index_list.remove(i)
                    newNode.nfIndexes.append(i)
                    # Part.show(self.__Shape.Faces[newNode.c_face_idx])
                    break

            if not counter_found:
                newNode.analysis_ok = False
                newNode.error_code = 13  # Analysis: counter face not found
                self.error_code = 13
                self.failed_face_idx = face_idx
                FreeCAD.Console.PrintLog(
                    "No opposite face Debugging Thickness: "
                    + str(self.__thickness)
                    + "\n"
                )
                Part.show(
                    self.__Shape.Faces[face_idx], "FailedFace" + str(face_idx + 1) + "_"
                )
                return newNode

            else:
                # Need a Vertex from the parent node on the opposite side of the
                # sheet metal part. This vertex is used to align other vertexes
                # to the unbended sheet metal plane.
                # The used vertex should be one of the opposite Face of the parent
                # node with the closest distance to a line through edge_vec.
                if P_node.node_type == "Flat":
                    searchAxis = P_node.axis
                else:
                    searchAxis = radVector

                maxDistance = 1000
                bestPoint = None
                for theVert in self.__Shape.Faces[P_node.c_face_idx].Vertexes:
                    vertDist = theVert.Point.distanceToLine(edge_vec, searchAxis)
                    if vertDist < maxDistance:
                        maxDistance = vertDist
                        bestPoint = theVert.Point

                newNode.oppositePoint = bestPoint
                # Part.show(Part.makeLine(bestPoint, edge_vec), 'bestPoint'+str(face_idx+1)+'_')

                self.getBendAngle(newNode, wires_e_lists)

                # As I have learned, that it is necessary to apply corrections to Points / Vertexes,
                # it will be difficult to have all vertexes of the faces of a bend to fit together.
                # Therefore a dictionary is introduced, which holds the original coordinates and
                # the unbend coordinates for the vertexes of the bend. It contains also flags,
                # indicating if a point is part of the parent node (p) or child node (c),
                # top face (t) or opposite face (o). All in newNode.vertexDict
                # Structure: key: Flagstring, Base.Vector(original), Base.Vector(unbend)
                # The unbend coordinates should be added before processing the top face and the
                # opposite face in the generateBendShell2 procedure.
                # Next is to identify for each vertex in the edges the corresponding vertex in
                # newNode.vertexDict.
                # Create a dictionary for the unbend edges. The key is a combination of the
                # vertex indexes. The higher index is shifted 16 bits. simple_node.edgeDict
                # Next is to unbend the edges, using the points in newNode.vertexDict as
                # starting and ending vertex.
                # Store the edge in self.edgeDict and process it to make a wire and a face.
                #
                # The side faces uses only the unbend vertexes from newNode.vertexDict,
                # the edges from self.edgeDict are recycled.
                # Only new to generate edges may need other vertexes too.
                vertDictIdx = 0  # Index as key in newNode.vertexDict
                for theVert in self.__Shape.Faces[face_idx].Vertexes:
                    flagStr = "t"
                    origVec = theVert.Point
                    unbendVec = None
                    if equal_vertex(theVert, P_edge.Vertexes[0]):
                        flagStr = flagStr + "p0"
                        origVec = P_edge.Vertexes[0].Point
                        unbendVec = origVec
                    else:
                        if equal_vertex(theVert, P_edge.Vertexes[1]):
                            flagStr = flagStr + "p1"
                            origVec = P_edge.Vertexes[1].Point
                            unbendVec = origVec
                    # print('make vertexDict: ', flagStr, ' ', str(face_idx+1))
                    newNode.vertexDict[vertDictIdx] = flagStr, origVec, unbendVec
                    vertDictIdx += 1

                for theVert in self.__Shape.Faces[newNode.c_face_idx].Vertexes:
                    flagStr = "o"
                    origVec = theVert.Point
                    unbendVec = None
                    for pVert in self.__Shape.Faces[P_node.c_face_idx].Vertexes:
                        if equal_vertex(theVert, pVert):
                            flagStr = flagStr + "p"
                            origVec = pVert.Point
                            unbendVec = origVec
                    # print('make vertexDict: ', flagStr, ' ', str(face_idx+1))
                    newNode.vertexDict[vertDictIdx] = flagStr, origVec, unbendVec
                    vertDictIdx += 1

        # Part.show(self.__Shape.Faces[newNode.c_face_idx])
        # Part.show(self.__Shape.Faces[newNode.idx])
        if newNode.c_face_idx is None:
            newNode.analysis_ok = False
            newNode.error_code = 13  # Analysis: counter face not found
            self.error_code = 13
            self.failed_face_idx = face_idx
            FreeCAD.Console.PrintLog(
                "No counter-face Debugging Thickness: " + str(self.__thickness) + "\n"
            )
            Part.show(
                self.__Shape.Faces[face_idx], "FailedFace" + str(face_idx + 1) + "_"
            )

        # now we call the new code
        self.get_node_faces(newNode, wires_e_lists)
        # for nFace in newNode.nfIndexes:
        #  Part.show(nFace)

        if P_node is None:
            self.root = newNode
        else:
            P_node.child_list.append(newNode)
        return newNode

    def Bend_analysis(self, face_idx, parent_node=None, parent_edge=None):
        # This functions traverses the shape in order to build the bend-tree
        # For each relevant face a t_node is created and linked into the tree
        # the linking is done in the call of self.make_new_face_node
        # print "Bend_analysis Face", face_idx +1 ,
        # analysis_ok = True # not used anymore?
        # edge_list = []
        if self.error_code is None:
            wires_edge_lists = []
            wire_idx = -1
            for n_wire in self.f_list[face_idx].Wires:
                wire_idx += 1
                wires_edge_lists.append([])
                # for n_edge in self.__Shape.Faces[face_idx].Edges:
                for n_edge in n_wire.Edges:
                    if parent_edge:
                        if not self.same_edges(parent_edge, n_edge):
                            # edge_list.append(n_edge)
                            wires_edge_lists[wire_idx].append(n_edge)
                        #
                    else:
                        # edge_list.append(n_edge)
                        wires_edge_lists[wire_idx].append(n_edge)
            if parent_node:
                FreeCAD.Console.PrintLog(
                    " Parent Face" + str(parent_node.idx + 1) + "\n"
                )
            FreeCAD.Console.PrintLog("The list: " + str(self.index_list) + "\n")
            parent_node = self.make_new_face_node(
                face_idx, parent_node, parent_edge, wires_edge_lists
            )
            # Need also the edge_list in the node!
            FreeCAD.Console.PrintLog(
                "The list after make_new_face_node: " + str(self.index_list) + "\n"
            )

            # in the new code, only the list of child faces will be analyzed.
            removalList = []

            for child_index, child_info in enumerate(parent_node.child_idx_lists):
                if child_info[0] in self.index_list:
                    child_face_idx = child_info[0]
                    child_face = self.__Shape.Faces[child_face_idx]
                    edge = child_info[1]

                    if not self.handle_hole(
                        parent_node, face_idx, edge, child_face, child_index
                    ):
                        if hasattr(FreeCADGui.Selection.getSelection()[0], "Refine"):
                            if FreeCADGui.Selection.getSelection()[0].Refine is True:
                                if not self.handle_chamfer(
                                    face_idx, edge, child_face, child_face_idx
                                ):
                                    self.Bend_analysis(
                                        child_face_idx, parent_node, edge
                                    )
                            else:
                                self.Bend_analysis(child_face_idx, parent_node, edge)
                        else:
                            self.Bend_analysis(child_face_idx, parent_node, edge)
                else:
                    FreeCAD.Console.PrintLog(
                        "remove child from List: " + str(child_info[0]) + "\n"
                    )
                    parent_node.seam_edges.append(
                        child_info[1]
                    )  # give Information to the node, that it has a seam.
                    FreeCAD.Console.PrintLog(
                        "node faces before: " + str(parent_node.nfIndexes) + "\n"
                    )
                    # do not make Faces at a detected seam!
                    # self.makeSeamFace(child_info[1], t_node)
                    removalList.append(child_info)
                    FreeCAD.Console.PrintLog(
                        "node faces with seam: " + str(parent_node.nfIndexes) + "\n"
                    )
                    otherSeamNode = self.searchNode(child_info[0], self.root)
                    FreeCAD.Console.PrintLog(
                        "counterface on otherSeamNode: Face"
                        + str(otherSeamNode.c_face_idx + 1)
                        + "\n"
                    )
                    # do not make Faces at a detected seam!
                    # self.makeSeamFace(child_info[1], otherSeamNode)
            for seams in removalList:
                parent_node.child_idx_lists.remove(seams)
        else:
            FreeCAD.Console.PrintError(
                "got error code: "
                + str(self.error_code)
                + " at Face"
                + str(self.failed_face_idx + 1)
                + "\n"
            )

    # Check if a face is a chamfer, and handle it as a special case.
    # parent_face_idx: The index of the top face
    # edge: the edge shared by parent and child faces
    # child_face: the supposedly face of the chamfer
    def handle_chamfer(self, parent_face_idx, edge, child_face, child_face_idx):
        # if edge doesn't have 2 vertices, it can't be a chamfer
        if len(edge.Vertexes) != 2:
            return False

        # get the child edge the furthest away from parent face
        next_edge = None
        max_distance = 0.0

        for child_edge in child_face.Edges:
            min_distance = sys.float_info.max

            for vertex in child_edge.Vertexes:
                distance = vertex.distToShape(edge)[0]

                if distance < min_distance:
                    min_distance = distance

            if min_distance > max_distance:
                next_edge = child_edge
                max_distance = min_distance

        parent_face = self.__Shape.Faces[parent_face_idx]
        distance = abs(
            next_edge.Vertexes[0].Point.distanceToPlane(
                parent_face.CenterOfGravity, self.face_normal(parent_face)
            )
        )

        # if next_edge distance to parent_face plane is greater than thickness, it can't be a chamfer
        if distance >= self.__thickness:
            return False

        # if there is a counter face, it can't be a chamfer
        if self.find_counter_face(child_face, child_face_idx) is not None:
            return False

        # if next_edge doesn't have 2 vertices, it can't be a chamfer
        if len(next_edge.Vertexes) != 2:
            return False

        ignore_list = self.find_neighbor_faces(parent_face, [])
        ignore_list.append(parent_face)
        next_faces = self.find_neighbor_faces(child_face, ignore_list)

        # there should be at least one next face, otherwise it can't be a chamfer
        if len(next_faces) < 1:
            return False

        if len(next_faces) == 1:
            next_face = next_faces[0]
        else:
            next_face = self.find_edge_face(next_edge, next_faces)

            # if no next face is found, it can't be a chamfer
            if next_face is None:
                return False

        # we use dot product with face normals to check if they are perpendicular
        dot = self.face_normal(child_face).dot(self.face_normal(parent_face))

        # if child face is perpendicular and it is a chamfer, there is nothing to do since it is not the sloped side of the chamfer
        if math.isclose(dot, 0):
            return True

        next_face_idx = None

        for idx, face in enumerate(self.__Shape.Faces):
            if face.isSame(next_face):
                next_face_idx = idx
                break

        if next_face_idx is not None:
            self.compute_chamfer_replacement_edges(
                parent_face, parent_face_idx, child_face, edge
            )

        return True

    # Check if a face is a hole, and handle countersink and counterbore cases.
    # parent_node: The node of the top face of the hole
    # parent_face_idx: The index of the top face of the hole
    # edge: the edge shared by parent and child faces
    # child_face: the supposedly lateral face of the hole
    # child_index: the index of the child in the parent_node
    def handle_hole(self, parent_node, parent_face_idx, edge, child_face, child_index):
        # if child face is not cylindrical it can't be a hole
        if not self.is_cylindrical_face(child_face):
            return False

        # if edge has more than 2 vertices it can't be a hole
        if len(edge.Vertexes) > 2:
            return False

        parent_face = self.__Shape.Faces[parent_face_idx]
        ignore_list = [parent_face, child_face]
        other_child_face = None

        if len(edge.Vertexes) == 2:
            # two vertices means semicircle
            # if we already processed the other semicircle before, there is no need to handle this one
            for i in range(0, child_index):
                if self.same_edges(parent_node.child_idx_lists[i][1], edge):
                    return True

            # if not yet processed, let's find the other semicircle
            for i in range(child_index + 1, len(parent_node.child_idx_lists)):
                if self.same_edges(parent_node.child_idx_lists[i][1], edge):
                    other_child_face = self.__Shape.Faces[
                        parent_node.child_idx_lists[i][0]
                    ]
                    break

            if other_child_face is not None:
                ignore_list.append(other_child_face)
            else:
                return False

        next_faces = self.find_neighbor_faces(child_face, ignore_list)

        # if no more faces, it was not a countersink or a counterbore
        if len(next_faces) == 0:
            return False

        # we use dot product with face normals to check if they are parallel
        dot = self.face_normal(next_faces[0]).dot(self.face_normal(parent_face))

        if math.isclose(dot, 1) or math.isclose(dot, -1):
            # since there is an intermediate face parallel to the parent face, this is a counterbore, let's skip this face
            ignore_list.extend(next_faces)
            next_faces = self.find_neighbor_faces(next_faces[0], ignore_list)

            # if no more faces, it was not a countersink or a counterbore
            if len(next_faces) == 0:
                return False
        else:
            if other_child_face is not None:
                # if there was another child face (semicircle case) there may be another face to ignore next
                other_child_next_faces = self.find_neighbor_faces(
                    other_child_face, ignore_list
                )
                ignore_list.extend(other_child_next_faces)

        ignore_list.extend(next_faces)
        bottom_faces = self.find_neighbor_faces(next_faces[0], ignore_list)

        # there should be only one bottom face
        if len(bottom_faces) != 1:
            return False

        return self.compute_replacement_circle(
            parent_face, parent_face_idx, edge, bottom_faces[0], next_faces[0].Edges
        )

    # Find all neighbors of a face that are not in an ignore list
    def find_neighbor_faces(self, face, ignore_list):
        neighbors = []

        for edge in face.Edges:
            faces = self.__Shape.ancestorsOfType(edge, Part.Face)

            for f in faces:
                found = False

                for face_to_ignore in ignore_list:
                    if face_to_ignore.isSame(f):
                        found = True
                        break

                if not found:
                    neighbors.append(f)

        return neighbors

    # Finds the counter (opposite) face of a given face, and return its index. Returns None if not found.
    def find_counter_face(self, face, face_idx):
        counter_idx = None
        min_distance = 0.0
        normal = self.face_normal(face)

        # iterate on all faces to try to find the opposite face
        for i, other_face in enumerate(self.__Shape.Faces):
            if i != face_idx:
                # the counter face normal must be parallel to the face normal, and pointing in the opposite direction
                # thus the dot product of the normals must be -1
                other_normal = self.face_normal(other_face)
                dot = normal.dot(other_normal)

                if math.isclose(
                    dot, -1.0
                ):  # we use isclose to avoid numerical precision problems
                    # the counter face must be in the opposite direction of the normal
                    # again we use the dot product to check this, using the normal and the vector from the face to the counter face
                    point = face.Vertexes[0].Point
                    other_point = other_face.Vertexes[0].Point
                    dot = normal.dot(other_point - point)

                    if dot < 0.0:
                        # we found a counter face, we can compute the distance and compare it with sheet thickness
                        distance = self.__Shape.Faces[i].distToShape(
                            self.__Shape.Faces[face_idx]
                        )[0]

                        if math.isclose(distance, self.__thickness) and (
                            min_distance == 0.0 or distance < min_distance
                        ):  # we use isclose to avoid numerical precision problems
                            min_distance = distance
                            counter_idx = i

        return counter_idx

    # Add new replacement edges for a chamfer to the list of wires to replace.
    # top_face: the face from which the chamfer starts
    # top_face_idx: the index of top_face
    # sloped_face: the sloped face of the chamfer
    # edge: the edge between top_face and sloped_face
    def compute_chamfer_replacement_edges(
        self, top_face, top_face_idx, sloped_face, edge
    ):
        v1 = self.compute_chamfer_reconstructed_vertex(
            top_face, sloped_face, edge, edge.Vertexes[0]
        )
        v2 = self.compute_chamfer_reconstructed_vertex(
            top_face, sloped_face, edge, edge.Vertexes[1]
        )
        self.add_edge_wire_replacement(top_face, top_face_idx, edge, v1, v2)

    # Given a face and an edge, create a new wire replacement with two new vertices added to replace the edge in the face.
    def add_edge_wire_replacement(self, face, face_idx, edge, v1, v2):
        wire_index = self.find_wire_index(face, edge)
        edges = []

        for wire_edge in face.Wires[wire_index].Edges:
            if self.is_line_edge(wire_edge) and len(wire_edge.Vertexes) == 2:
                vertices = []
                normal = (
                    self.face_normal(face)
                    .cross(edge.Vertexes[1].Point - edge.Vertexes[0].Point)
                    .normalize()
                )

                for index, vertex in enumerate(wire_edge.Vertexes):
                    new_vertex = None

                    if vertex.isSame(edge.Vertexes[0]):
                        new_vertex = v1
                    elif vertex.isSame(edge.Vertexes[1]):
                        new_vertex = v2

                    if new_vertex is not None:
                        if self.same_edges(wire_edge, edge):
                            vertices.append((new_vertex.x, new_vertex.y, new_vertex.z))
                        else:
                            if index == 0:
                                vertices.append(
                                    (new_vertex.x, new_vertex.y, new_vertex.z)
                                )

                            vector = Base.Vector(
                                vertex.X - new_vertex.x,
                                vertex.Y - new_vertex.y,
                                vertex.Z - new_vertex.z,
                            ).normalize()
                            dot = vector.dot(normal)

                            if not math.isclose(dot, 1) and not math.isclose(dot, -1):
                                vertices.append((vertex.X, vertex.Y, vertex.Z))

                            if index == 1:
                                vertices.append(
                                    (new_vertex.x, new_vertex.y, new_vertex.z)
                                )
                    else:
                        vertices.append((vertex.X, vertex.Y, vertex.Z))

                for i in range(0, len(vertices) - 1):
                    edges.append(Part.makeLine(vertices[i], vertices[i + 1]))
            else:
                edges.append(wire_edge)

        self.wire_replacements.append(
            SheetTree.WireReplacement(face_idx, wire_index, Part.Wire(edges))
        )

    # Add a new replacement circle to the list of wires to replace.
    # top_face: The top face where the wire will be replaced
    # top_face_idx : The index of the top face
    # top_edge : An edge of the top face that will be replaced
    # bottom_face : The bottom face used to compute the radius of the new circle
    # bottom_edges : The edges of the hole face just above the bottom face
    def compute_replacement_circle(
        self, top_face, top_face_idx, top_edge, bottom_face, bottom_edges
    ):
        top_radius = self.arc_edge_radius(top_edge)
        top_center = self.arc_edge_center(top_edge)

        for bottom_edge in bottom_face.Edges:
            if not self.is_arc_edge(bottom_edge):
                return False

            for edge in bottom_edges:
                if not self.same_edges(edge, bottom_edge):
                    return False

                bottom_radius = self.arc_edge_radius(bottom_edge)

                if bottom_radius is None or bottom_radius == top_radius:
                    return True
                bottom_center = self.arc_edge_center(bottom_edge)

                if bottom_center is None:
                    return False

                distance = (top_center - bottom_center).Length

                if math.isclose(
                    distance, self.__thickness
                ):  # check that we are indeed at the bottom of the hole
                    return False

                if bottom_radius < top_radius:
                    wire_index = self.find_wire_index(top_face, top_edge)
                    circle = Part.makeCircle(
                        bottom_radius,
                        top_center,
                        (bottom_center - top_center).normalize(),
                    )
                    self.wire_replacements.append(
                        SheetTree.WireReplacement(
                            top_face_idx,
                            wire_index,
                            Part.Wire(circle),
                        )
                    )
                    return True
                else:
                    bottom_face_idx = None

                    for idx, face in enumerate(self.__Shape.Faces):
                        if face.isSame(bottom_face):
                            bottom_face_idx = idx
                            break

                    if bottom_face_idx is not None:
                        wire_index = self.find_wire_index(bottom_face, bottom_edge)
                        circle = Part.makeCircle(
                            top_radius,
                            bottom_center,
                            (top_center - bottom_center).normalize(),
                        )
                        self.wire_replacements.append(
                            SheetTree.WireReplacement(
                                bottom_face_idx,
                                wire_index,
                                Part.Wire(circle),
                            )
                        )
                        return True

    # Check if a face is cylindrical or not.
    def is_cylindrical_face(self, face):
        return (
            str(get_surface(face)) == "<Cylinder object>"
            or str(get_surface(face)) == "<Cone object>"
        )

    # Check if an edge is an arc or not. Sometimes B-spline is used instead of circle.
    def is_arc_edge(self, edge):
        return isinstance(edge.Curve, Part.Circle) or isinstance(
            edge.Curve, Part.BSplineCurve
        )

    # Check if an edge is a line or not
    def is_line_edge(self, edge):
        return isinstance(edge.Curve, Part.Line)

    # Compute the radius of an arc edge
    def arc_edge_radius(self, edge):
        if isinstance(edge.Curve, Part.Circle):
            # Circle has radius
            return edge.Curve.Radius
        elif len(edge.Vertexes) == 2:
            # B-spline with 2 vertices, we can assume it's a semicircle
            return (edge.Vertexes[0].Point - edge.Vertexes[1].Point).Length / 2.0
        else:
            # B-spline but not with 2 vertices, this should not happen
            return None

    # Compute the center of an arc edge
    def arc_edge_center(self, edge):
        if isinstance(edge.Curve, Part.Circle):
            # Circle has location
            return edge.Curve.Location
        elif len(edge.Vertexes) == 2:
            # B-spline with 2 vertices, we can assume it's a semicircle
            return (edge.Vertexes[0].Point + edge.Vertexes[1].Point) / 2.0
        else:
            # B-spline but not with 2 vertices, this should not happen
            return None

    # Find the wire index inside a face that contains an edge
    def find_wire_index(self, face, edge):
        for i, wire in enumerate(face.Wires):
            for wire_edge in wire.Edges:
                if self.same_edges(wire_edge, edge):
                    return i

        return None

    # Find an edge's face among a list of faces
    def find_edge_face(self, edge, faces):
        edge_faces = self.__Shape.ancestorsOfType(edge, Part.Face)

        for face in faces:
            for edge_face in edge_faces:
                if edge_face.isSame(face):
                    return face

        return None

    # Compute the normal of a face
    def face_normal(self, face):
        uv = face.Surface.parameter(face.CenterOfGravity)

        return face.normalAt(uv[0], uv[1])

    # Compute the vertex needed to reconstruct a chamfered face to its original shape
    # top_face: the face from which the chamfer starts
    # sloped_face: the sloped face of the chamfer
    # edge: the edge between top_face and sloped_face
    # vertex: the vertex of edge edge used to compute the intersection (this method must be called twice, for each vertex)
    def compute_chamfer_reconstructed_vertex(self, top_face, sloped_face, edge, vertex):
        vert = self.find_face_vertex(sloped_face, vertex, edge)
        normal = self.face_normal(top_face)
        distance = abs(vert.Point.distanceToPlane(vertex.Point, normal))

        return vert.Point + (normal * distance)

    # Given a face and a vertex, find the other vertex that shares an edge with the vertex but is different from the given edge
    def find_face_vertex(self, face, vertex, edge):
        for face_edge in face.Edges:
            if not self.same_edges(face_edge, edge) and len(face_edge.Vertexes) == 2:
                if face_edge.Vertexes[0].isSame(vertex):
                    return face_edge.Vertexes[1]
                elif face_edge.Vertexes[1].isSame(vertex):
                    return face_edge.Vertexes[0]

        return None

    def searchNode(self, theIdx, sNode):
        # search for a Node with theIdx in sNode.idx
        FreeCAD.Console.PrintLog("my Idx: " + str(sNode.idx) + "\n")

        if sNode.idx == theIdx:
            return sNode
        else:
            result = None
            childFaces = []
            for n_node in sNode.child_list:
                childFaces.append(n_node.idx)
            FreeCAD.Console.PrintLog("my children: " + str(childFaces) + "\n")

            for n_node in sNode.child_list:
                nextSearch = self.searchNode(theIdx, n_node)
                if nextSearch is not None:
                    result = nextSearch
                    break
        if result is not None:
            FreeCAD.Console.PrintLog("This is the result: " + str(result.idx) + "\n")
        else:
            FreeCAD.Console.PrintLog("This is the result: None\n")

        return result

        # suche bei mir. wenn ja liefere ab
        # sonst sind Kinder da?
        # Wenn Kinder vorhanden, frag solange Kinder bis gefunden
        # oder kein Kind mehr da.

    def rotateVec(self, vec, phi, rAxis):
        """rotate a vector by the angle phi around the axis rAxis"""
        # https://de.wikipedia.org/wiki/Drehmatrix
        rVec = (
            rAxis.cross(vec).cross(rAxis).multiply(math.cos(phi))
            + rAxis.cross(vec) * math.sin(phi)
            + rAxis * rAxis.dot(vec)
        )
        return rVec

    def unbendFace(self, fIdx, bend_node, nullVec, mode="side"):
        """
        The self.vertexDict requires a further data structure to hold for
        each edge in a list the point indexes to the vertexes of the bend node.
        key: Index to myEdgeList, content: List of indexes to the self.vertexDict.
        """

        axis = bend_node.axis
        cent = bend_node.bendCenter
        bRad = bend_node.innerRadius
        thick = self.__thickness

        kFactor = bend_node.k_Factor

        transRad = bRad + kFactor * thick
        if KFACTORSTANDARD == "din":
            conv = ", converted from DIN"
        else:
            conv = ""
        # Should only be enabled for debugging purposes:
        # SMMessage("transRad Face: %d, r: %.2f, thickness: %.2f, K-factor: %.2f (ANSI%s)" % (fIdx+1, bRad, thick, kFactor, conv))
        tanVec = bend_node.tan_vec
        aFace = self.f_list[fIdx]

        normVec = radial_vector(bend_node.p_edge.Vertexes[0].Point, cent, axis)

        if mode == "top":
            chord = cent.sub(bend_node.p_edge.Vertexes[0].Point)
            norm = axis.cross(chord)
            compRadialVec = axis.cross(norm)

        if mode == "counter":
            chord = cent.sub(bend_node.oppositePoint)
            norm = axis.cross(chord)
            compRadialVec = axis.cross(norm)

        def unbendPoint(poi):
            radVec = radial_vector(poi, cent, axis)
            angle = math.atan2(nullVec.cross(radVec).dot(axis), nullVec.dot(radVec))
            # print 'point Face', str(fIdx+1), ' ', angle
            if angle < -math.pi / 8:
                angle = angle + 2 * math.pi
            rotVec = self.rotateVec(poi.sub(cent), -angle, axis)
            # print 'point if Face', str(fIdx+1), ' ', angle, ' ', transRad*angle
            if (mode == "top") or (mode == "counter"):
                chord = cent.sub(cent + rotVec)
                norm = axis.cross(chord)
                correctionVec = compRadialVec.sub(axis.cross(norm))
                # correctionVec = axis.cross(norm).sub(compRadialVec)
                # print 'origVec ', axis.cross(norm), ' compRadialVec ', compRadialVec
                bPoint = cent + rotVec + correctionVec + tanVec * transRad * angle
            else:
                bPoint = cent + rotVec + tanVec * transRad * angle

            return bPoint

        divisions = 12  # FIXME need a dependence on something useful.

        fWireList = aFace.Wires[:]
        # newWires = []
        edgeLists = []

        for aWire in fWireList:
            uEdge = None
            idxList, closedW = self.sortEdgesTolerant(aWire.Edges)
            # print('Wire', str(fIdx+1), ' has ', len(idxList), ' edges, closed: ', closedW)

            eList = []  # is the list of unbend edges
            j = 0
            for fEdgeIdx in idxList:
                fEdge = aWire.Edges[fEdgeIdx]
                eType = str(fEdge.Curve)
                vertexCount = len(fEdge.Vertexes)
                # print "the type of curve: ", eType
                vert0 = None
                vert1 = None
                flags0 = None
                flags1 = None
                uVert0 = None
                uVert1 = None
                edgeKey = None
                vert0Idx = None
                vert1Idx = None

                # print 'edge vertexes: ', str(fIdx+1), ' ', mode, ' ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point
                for oVertIdx in bend_node.vertexDict:
                    flagStr, origVec, unbendVec = bend_node.vertexDict[oVertIdx]
                    # print 'origVec: ', origVec
                    if equal_vector(fEdge.Vertexes[0].Point, origVec, 5):
                        vert0Idx = oVertIdx
                        flags0 = flagStr
                        uVert0 = unbendVec
                    if vertexCount > 1:
                        if equal_vector(fEdge.Vertexes[1].Point, origVec, 5):
                            vert1Idx = oVertIdx
                            flags1 = flagStr
                            uVert1 = unbendVec
                    # can we break the for loop at some condition?
                # Handle cases, where a side face has additional vertexes
                if mode == "side":
                    if vert0Idx is None:
                        vert0Idx = len(bend_node.vertexDict)
                        # print('got additional side vertex0: ', vert0Idx, ' ', fEdge.Vertexes[0].Point)
                        flags0 = ""
                        origVec = fEdge.Vertexes[0].Point
                        uVert0 = unbendPoint(origVec)
                        bend_node.vertexDict[vert0Idx] = flags0, origVec, uVert0
                    if vertexCount > 1:
                        if vert1Idx is None:
                            vert1Idx = len(bend_node.vertexDict)
                            # print('got additional side vertex1: ', vert1Idx, ' ', fEdge.Vertexes[1].Point)
                            flags1 = ""
                            origVec = fEdge.Vertexes[1].Point
                            uVert1 = unbendPoint(origVec)
                            bend_node.vertexDict[vert1Idx] = flags1, origVec, uVert1

                # make the key for bend_node.edgeDict, shift vert1 and add both.
                if vert0Idx is None:
                    # print 'catastrophy: ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point, ' ', eType
                    Part.show(fEdge, "catastrophyEdge")
                    # FIXME, need proper failure mode.
                if vert1Idx:
                    if vert1Idx < vert0Idx:
                        edgeKey = vert0Idx + (vert1Idx << 8)
                    else:
                        edgeKey = vert1Idx + (vert0Idx << 8)
                    # x << n: x shifted left by n bits = Multiplication
                else:
                    edgeKey = vert0Idx

                # print 'edgeKey: ', edgeKey, ' ', str(fIdx+1), ' ', mode, ' ', uVert0, ' ', uVert1

                urollPts = []

                if "<Ellipse object>" in eType:
                    minPar, maxPar = fEdge.ParameterRange
                    FreeCAD.Console.PrintLog(
                        "the Parameterrange: "
                        + str(minPar)
                        + " to "
                        + str(maxPar)
                        + " Type: "
                        + str(eType)
                        + "\n"
                    )

                    # compare minimal 1/curvature with curve-lenght to decide on division
                    iMulti = (maxPar - minPar) / 24
                    maxCurva = 0.0
                    for i in range(24):
                        posi = fEdge.valueAt(minPar + i * iMulti)
                        # print 'testEdge ', i, ' curva: ' , testEdge.Curve.curvature(minPar + i*iMulti)
                        curva = fEdge.Curve.curvature(minPar + i * iMulti)
                        if curva > maxCurva:
                            maxCurva = curva

                    decisionAngle = fEdge.Length * maxCurva
                    # print 'Face', str(fIdx+1), ' EllidecisionAngle: ', decisionAngle
                    # Part.show(fEdge, 'EllideciAng'+str(decisionAngle)+ '_')

                    if decisionAngle < 0.1:
                        eDivisions = 4
                    elif decisionAngle < 0.5:
                        eDivisions = 6
                    else:
                        eDivisions = 12

                    iMulti = (maxPar - minPar) / eDivisions
                    urollPts.append(uVert0)
                    for i in range(1, eDivisions):
                        posi = fEdge.valueAt(minPar + i * iMulti)
                        bPosi = unbendPoint(posi)
                        urollPts.append(bPosi)
                    urollPts.append(uVert1)

                    uCurve = Part.BSplineCurve()
                    uCurve.interpolate(urollPts)
                    uEdge = uCurve.toShape()
                    # Part.show(uEdge, 'Elli'+str(j)+'_')

                elif "<Line" in eType:
                    # print 'j: ',j , ' eType: ', eType, ' fIdx: ', fIdx, ' verts: ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point
                    # Part.show(fEdge)
                    # print 'unbend Line: ', uVert0, ' ', uVert1
                    uEdge = Part.makeLine(uVert0, uVert1)
                    # Part.show(uEdge, 'Line'+str(j)+'_')

                elif (
                    "Circle" in eType
                ):  # FIXME need to check if circle ends are at different radii!
                    FreeCAD.Console.PrintLog(
                        "j: " + str(j) + " eType: " + str(eType) + "\n"
                    )
                    parList = fEdge.ParameterRange
                    # print "the Parameterrange: ", parList[0], " , ", parList[1], " Type: ",eType
                    # axis_line = Part.makeLine(cent, cent + axis)
                    # Part.show(axis_line, 'axis_line'+ str(bend_node.idx+1)+'_')
                    # print 'Face', str(bend_node.idx+1), 'bAxis: ', axis, ' cAxis: ', fEdge.Curve.Axis
                    uEdge = Part.makeLine(uVert0, uVert1)
                    # Part.show(uEdge, 'CircleLine'+str(j)+'_')

                elif ("<BSplineCurve object>" in eType) or (
                    "<BezierCurve object>" in eType
                ):
                    minPar, maxPar = fEdge.ParameterRange
                    # print "the Parameterrange: ", minPar, " - ", maxPar, " Type: ",eType

                    # compare minimal 1/curvature with curve-lenght to decide on division
                    iMulti = (maxPar - minPar) / 24
                    maxCurva = 0.0
                    testPts = []
                    for i in range(24 + 1):
                        posi = fEdge.valueAt(minPar + i * iMulti)
                        bPosi = unbendPoint(posi)
                        testPts.append(bPosi)
                    testCurve = Part.BSplineCurve()
                    testCurve.interpolate(testPts)
                    testEdge = testCurve.toShape()

                    for i in range(24 + 1):
                        posi = testEdge.valueAt(minPar + i * iMulti)
                        # print 'testEdge ', i, ' curva: ' , testEdge.Curve.curvature(minPar + i*iMulti)
                        curva = testEdge.Curve.curvature(minPar + i * iMulti)
                        if curva > maxCurva:
                            maxCurva = curva

                    decisionAngle = testEdge.Length * maxCurva
                    # print 'Face', str(fIdx+1), ' decisionAngle: ', decisionAngle
                    # Part.show(testEdge, 'deciAng'+str(decisionAngle)+ '_')

                    if decisionAngle > 1000.0:
                        bDivisions = 4
                    else:
                        bDivisions = 12

                    iMulti = (maxPar - minPar) / bDivisions
                    if vertexCount > 1:
                        urollPts.append(uVert0)
                        for i in range(1, bDivisions):
                            posi = fEdge.valueAt(minPar + i * iMulti)
                            # curvature is 1/radius
                            # print 'Face', str(fIdx+1), ' 1/Curvature: ', 1/fEdge.Curve.curvature(minPar + i*iMulti), ' ', fEdge.Length
                            bPosi = unbendPoint(posi)
                            urollPts.append(bPosi)
                        urollPts.append(uVert1)
                    else:
                        urollPts.append(uVert0)
                        for i in range(1, bDivisions):
                            posi = fEdge.valueAt(minPar + i * iMulti)
                            bPosi = unbendPoint(posi)
                            urollPts.append(bPosi)
                        urollPts.append(uVert0)
                    # testPoly = Part.makePolygon(urollPts)
                    # Part.show(testPoly, 'testPoly'+ str(fIdx+1) + '_')
                    uCurve = Part.BSplineCurve()
                    try:
                        uCurve.interpolate(urollPts)
                        uEdge = uCurve.toShape()
                        # Part.show(theCurve, 'B_spline')
                    except:
                        # uEdge =  Part.makeLine(urollPts[0], urollPts[-1])
                        if bDivisions == 4:
                            uCurve.interpolate([urollPts[0], urollPts[2], urollPts[-1]])
                        if bDivisions == 12:
                            uCurve.interpolate(
                                [
                                    urollPts[0],
                                    urollPts[3],
                                    urollPts[6],
                                    urollPts[9],
                                    urollPts[-1],
                                ]
                            )
                        uEdge = uCurve.toShape()
                else:
                    # print 'unbendFace, curve type not handled: ' + str(eType) + ' in Face' + str(fIdx+1)
                    FreeCAD.Console.PrintLog(
                        "unbendFace, curve type not handled: "
                        + str(eType)
                        + " in Face"
                        + str(fIdx + 1)
                        + "\n"
                    )
                    self.error_code = 26
                    self.failed_face_idx = fIdx

                # in mode 'side' check, if not the top or counter edge can be used instead.
                if mode == "side":
                    if edgeKey in bend_node.edgeDict:
                        uEdge = bend_node.edgeDict[edgeKey]
                        # print 'found key in node.edgeDict: ', edgeKey, ' in mode: ', mode
                # Part.show(uEdge, 'bendEdge'+str(fIdx+1)+'_')
                eList.append(uEdge)
                if not (edgeKey in bend_node.edgeDict):
                    bend_node.edgeDict[edgeKey] = uEdge
                    # print 'added key: ', edgeKey, ' to edgeDict in mode: ', mode
                j += 1
            edgeLists.append(eList)
        # end of for what?

        # Here we store the unbend top and counter outer edge list in the node data.
        # These are needed later as edges in the new side faces.
        if mode == "top":
            bend_node.unfoldTopList = edgeLists[0]
        if mode == "counter":
            bend_node.unfoldCounterList = edgeLists[0]

        if len(edgeLists) == 1:
            eList = Part.__sortEdges__(edgeLists[0])
            myWire = Part.Wire(eList)
            FreeCAD.Console.PrintLog("len eList: " + str(len(eList)) + "\n")
            # Part.show(myWire, 'Wire_Face'+str(fIdx+1)+'_' )
            if (len(myWire.Vertexes) == 2) and (len(myWire.Edges) == 3):
                # print 'got sweep condition!'
                pWire = Part.Wire(myWire.Edges[1])
                fWire = Part.Wire(myWire.Edges[0])  # first sweep profile
                lWire = Part.Wire(myWire.Edges[2])  # last sweep profile
                theFace = pWire.makePipeShell([fWire, lWire], False, True)
                theFace = theFace.Faces[0]
                # Part.show(theFace, 'Loch')
            else:
                try:
                    # Part.show(myWire, 'myWire'+ str(bend_node.idx+1)+'_')
                    theFace = Part.Face(myWire)
                    # theFace = Part.makeFace(myWire, 'Part::FaceMakerSimple')
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    FreeCAD.Console.PrintLog(
                        "got exception at Face: "
                        + str(fIdx + 1)
                        + " len eList: "
                        + str(len(eList))
                        + " at line "
                        + str(exc_tb.tb_lineno)
                        + "\n"
                    )
                    # for w in eList:
                    # Part.show(w, 'exceptEdge')
                    # print 'exception type: ', str(w.Curve)
                    # Part.show(myWire, 'exceptionWire'+ str(fIdx+1)+'_')
                    secWireList = myWire.Edges[:]
                    thirdWireList = Part.__sortEdges__(secWireList)
                    theFace = Part.makeFilledFace(thirdWireList)
                # Part.show(theFace, 'theFace'+ str(bend_node.idx+1)+'_')
        else:
            FreeCAD.Console.PrintLog("len edgeLists: " + str(len(edgeLists)) + "\n")
            faces = []
            wires = []
            wireNumber = 0
            for w in edgeLists:
                eList = Part.__sortEdges__(w)
                # print 'eList: ', eList
                if wireNumber < 0:
                    # myWire = Part.Wire(eList.reverse())
                    reversList = []
                    for e in eList:
                        reversList.insert(0, e)
                    myWire = Part.Wire(reversList)
                else:
                    myWire = Part.Wire(eList)
                # Part.show(myWire, 'myWire'+ str(bend_node.idx+1)+'_')
                nextFace = Part.Face(myWire)
                faces.append(nextFace)
                wires.append(myWire)
                wireNumber += 1
                # Part.show(Part.Face(myWire))
            try:
                # theFace = Part.Face(wires)
                # print 'make cut face\n'
                theFace = faces[0].copy()
                for f in faces[1:]:
                    f.translate(-normVec)
                    cutter = f.extrude(2 * normVec)
                    theFace = theFace.cut(cutter)
                    theFace = theFace.Faces[0]
                # Part.show(theFace, 'theFace')
                # theFace = Part.Face(wires[0], wires[1:])
                # theFace = Part.makeFace(myWire, 'Part::FaceMakerSimple')
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                # theFace = Part.makeFilledFace(wires)
                theFace = faces[0]
                SMLogger.error(
                    "at line " + str(exc_tb.tb_lineno) + " got exception: ", str(e)
                )
                # Part.show(theFace, 'exception')
        keyList = []
        for key in bend_node.edgeDict:
            keyList.append(key)
        # print 'edgeDict keys: ', keyList
        # Part.show(theFace, 'unbendFace'+str(fIdx+1))
        return theFace

    def sortEdgesTolerant(self, myEdgeList):
        """
        sort edges from an existing wire.
        returns:
          a new sorted list of indexes to edges of the original wire
          flag if wire is closed or not (a wire of a cylinder mantle is not closed!)
        """
        eIndex = 0
        newEdgeList = []
        idxList = list(range(len(myEdgeList)))
        newIdxList = [eIndex]
        newEdgeList.append(myEdgeList[eIndex])
        idxList.remove(eIndex)
        gotConnection = False
        closedWire = False

        startVert = myEdgeList[eIndex].Vertexes[0]
        if len(myEdgeList[eIndex].Vertexes) > 1:
            vert = myEdgeList[eIndex].Vertexes[1]
        else:
            vert = myEdgeList[eIndex].Vertexes[0]
        # Part.show(myEdgeList[0], 'tolEdge'+str(1)+'_')
        while not gotConnection:
            for eIdx in idxList:
                edge = myEdgeList[eIdx]
                if equal_vertex(vert, edge.Vertexes[0]):
                    idxList.remove(eIdx)
                    eIndex = eIdx
                    # print 'found eIdx: ', eIdx
                    newIdxList.append(eIdx)
                    if len(edge.Vertexes) > 1:
                        vert = edge.Vertexes[1]
                    break
                if len(edge.Vertexes) > 1:
                    if equal_vertex(vert, edge.Vertexes[1]):
                        idxList.remove(eIdx)
                        eIndex = eIdx
                        # print 'found eIdx: ', eIdx
                        newIdxList.append(eIdx)
                        vert = edge.Vertexes[0]
                        break
            if len(idxList) == 0:
                gotConnection = True
            if equal_vertex(vert, startVert):
                # print 'got last connection'
                gotConnection = True
                closedWire = True
            # Part.show(myEdgeList[eIdx], 'tolEdge'+str(eIdx+1)+'_')
        # print 'tolerant wire: ', len(myEdgeList)
        return newIdxList, closedWire

    def makeFoldLines(self, bend_node, nullVec):
        axis = bend_node.axis
        cent = bend_node.bendCenter
        bRad = bend_node.innerRadius
        kFactor = bend_node.k_Factor
        thick = self.__thickness
        transRad = bRad + kFactor * thick
        tanVec = bend_node.tan_vec
        theFace = self.f_list[bend_node.idx]

        angle_0 = theFace.ParameterRange[0]
        angle_1 = theFace.ParameterRange[1]
        length_0 = theFace.ParameterRange[2]

        halfAngle = (angle_0 + angle_1) / 2
        bLinePoint0 = theFace.valueAt(halfAngle, length_0)
        # bLinePoint1 = theFace.valueAt(halfAngle,length_1)
        normVec = radial_vector(bLinePoint0, cent, axis)
        sliceVec = normVec.cross(axis)
        origin = Base.Vector(0.0, 0.0, 0.0)
        distance = origin.distanceToPlane(bLinePoint0, sliceVec)
        testDist = -bLinePoint0.distanceToPlane(sliceVec * distance, sliceVec)
        if math.fabs(testDist) > math.fabs(distance):
            sliceVec = -sliceVec

        # Part.show(Part.makePolygon([origin,sliceVec * distance]), 'distance')
        # print 'distance: ', distance, ' testDist: ', testDist
        wires = []
        for i in theFace.slice(sliceVec, distance):
            wires.append(i)
        # print 'got ', len(wires), ' wires'
        # Part.show(Part.Compound(wires), 'slice')
        theComp = Part.Compound(wires)
        # FIXME, what if there are no wires?
        wireList = []

        for fEdge in theComp.Edges:
            eType = str(fEdge.Curve)
            # print "the type of curve: ", eType
            urollPts = []

            if "<Line" in eType:
                for lVert in fEdge.Vertexes:
                    posi = lVert.Point
                    radVec = radial_vector(posi, cent, axis)
                    angle = math.atan2(
                        nullVec.cross(radVec).dot(axis), nullVec.dot(radVec)
                    )
                    if angle < 0:
                        angle = angle + 2 * math.pi
                    rotVec = self.rotateVec(posi.sub(cent), -angle, axis)

                    bPosi = cent + rotVec + tanVec * transRad * angle

                    urollPts.append(bPosi)
                edgeL = Part.makeLine(urollPts[0], urollPts[1])
                lWire = Part.Wire([edgeL])
                wireList.append(edgeL)
                # Part.show(lWire, 'foldLine'+str(bend_node.idx +1)+'_')
            else:
                print("FIXME! make errorcondition")

        return wireList

    def unbendVertDict(self, bend_node, cent, axis, nullVec):
        """
        calculate the unbend points in the vertexDict.
        This is called with the vertices of the top and the opposite face only.
        """

        def unbendDictPoint(poi, compRadialVec):
            radVec = radial_vector(poi, cent, axis)
            angle = math.atan2(nullVec.cross(radVec).dot(axis), nullVec.dot(radVec))
            # print 'point Face', str(fIdx+1), ' ', angle
            if angle < -math.pi / 8:
                angle = angle + 2 * math.pi
            rotVec = self.rotateVec(poi.sub(cent), -angle, axis)
            chord = cent.sub(cent + rotVec)
            norm = axis.cross(chord)
            correctionVec = compRadialVec.sub(axis.cross(norm))
            # print 'origVec ', axis.cross(norm), ' compRadialVec ', compRadialVec
            bPoint = cent + rotVec + correctionVec + tanVec * transRad * angle
            return bPoint

        thick = self.__thickness
        transRad = bend_node.innerRadius + bend_node.k_Factor * thick
        tanVec = bend_node.tan_vec

        chord = cent.sub(bend_node.p_edge.Vertexes[0].Point)
        norm = axis.cross(chord)
        topCompRadialVec = axis.cross(norm)

        chord = cent.sub(bend_node.oppositePoint)
        norm = axis.cross(chord)
        oppCompRadialVec = axis.cross(norm)

        for i in bend_node.vertexDict:
            flagStr, origVec, unbendVec = bend_node.vertexDict[i]
            if (not ("p" in flagStr)) and (not ("c" in flagStr)):
                if "t" in flagStr:
                    unbendVec = unbendDictPoint(origVec, topCompRadialVec)
                else:
                    unbendVec = unbendDictPoint(origVec, oppCompRadialVec)
                # print 'unbendDictPoint for ', flagStr
                bend_node.vertexDict[i] = flagStr, origVec, unbendVec

        # for i in bend_node.vertexDict:
        # flagStr, origVec, unbendVec = bend_node.vertexDict[i]
        # print 'vDict Face', str(bend_node.idx+1), ' ', i, ' ', flagStr, ' ', origVec, ' ', unbendVec

    def generateBendShell2(self, bend_node):
        """
        This function takes a cylindrical bend part of sheet metal and
        returns a flat version of that bend part.
        """
        theCenter = bend_node.bendCenter  # theCyl.Surface.Center
        theAxis = bend_node.axis  # theCyl.Surface.Axis
        # theRadius = theCyl.Surface.Radius # need to include the k-Factor

        zeroVert = bend_node.p_edge.Vertexes[0]
        nullVec = radial_vector(zeroVert.Point, theCenter, theAxis)
        # nullVec_line = Part.makeLine(theCenter, theCenter + nullVec*bend_node.innerRadius)
        # Part.show(nullVec_line, 'nullVec_line'+ str(bend_node.idx+1)+'_')
        # tanVec_line = Part.makeLine(zeroVert.Point, zeroVert.Point + bend_node.tan_vec*bend_node.innerRadius)
        # Part.show(tanVec_line, 'tanVec_line'+ str(bend_node.idx+1)+'_')

        # calculate the unbend points in the bend_ node.vertexDict
        self.unbendVertDict(bend_node, theCenter, theAxis, nullVec)

        bendFaceList = bend_node.nfIndexes[:]
        bendFaceList.remove(bend_node.idx)
        bendFaceList.remove(bend_node.c_face_idx)

        flat_shell = []
        flat_shell.append(self.unbendFace(bend_node.idx, bend_node, nullVec, "top"))
        flat_shell.append(
            self.unbendFace(bend_node.c_face_idx, bend_node, nullVec, "counter")
        )

        for i in bendFaceList:
            bFace = self.unbendFace(i, bend_node, nullVec)
            flat_shell.append(bFace)
            # Part.show(bFace, 'bFace'+str(i +1))
            # for v in bFace.Vertexes:
            #  print 'Face'+str(i+1) + ' ' + str(v.X) + ' ' + str(v.Y) + ' ' + str(v.Z)

        foldwires = self.makeFoldLines(bend_node, nullVec)
        # print 'face idx: ', bend_node.idx +1, ' folds: ', foldwires
        return flat_shell, foldwires

    def makeSeamFace(self, sEdge, theNode):
        """This function creates a face at a seam of the sheet metal.
        It works currently only at a flat node.
        """
        FreeCAD.Console.PrintLog("now make a seam Face\n")
        nextVert = sEdge.Vertexes[1]
        startVert = sEdge.Vertexes[0]
        start_idx = 0
        end_idx = 1

        search_List = theNode.nfIndexes[:]
        FreeCAD.Console.PrintLog("This is the search_List: " + str(search_List) + "\n")
        search_List.remove(theNode.idx)
        the_index = None
        next_idx = None
        for i in search_List:
            for theEdge in self.f_list[i].Edges:
                if len(theEdge.Vertexes) > 1:
                    if equal_vertex(theEdge.Vertexes[0], nextVert):
                        next_idx = 1
                    if equal_vertex(theEdge.Vertexes[1], nextVert):
                        next_idx = 0
                    if next_idx is not None:
                        if self.isVertOpposite(theEdge.Vertexes[next_idx], theNode):
                            nextEdge = theEdge.copy()
                            search_List.remove(i)
                            the_index = i
                            # Part.show(nextEdge)
                            break
                        else:
                            next_idx = None
            if the_index is not None:
                break

        # find the lastEdge
        last_idx = None
        FreeCAD.Console.PrintLog("This is the search_List: " + str(search_List) + "\n")
        for i in search_List:
            # Part.show(self.f_list[i])
            for theEdge in self.f_list[i].Edges:
                FreeCAD.Console.PrintLog(
                    "Find last Edge in Face: "
                    + str(i)
                    + " at Edge: "
                    + str(theEdge)
                    + "\n"
                )
                if len(theEdge.Vertexes) > 1:
                    if equal_vertex(theEdge.Vertexes[0], startVert):
                        last_idx = 1
                    if equal_vertex(theEdge.Vertexes[1], startVert):
                        last_idx = 0
                    if last_idx is not None:
                        FreeCAD.Console.PrintLog("Test for the last Edge\n")
                        if self.isVertOpposite(theEdge.Vertexes[last_idx], theNode):
                            lastEdge = theEdge.copy()
                            search_List.remove(i)
                            the_index = i
                            # Part.show(lastEdge)
                            break
                        else:
                            last_idx = None
            if last_idx is not None:
                break

        # find the middleEdge
        mid_idx = None
        midEdge = None
        for theEdge in self.f_list[theNode.c_face_idx].Edges:
            if len(theEdge.Vertexes) > 1:
                if equal_vertex(theEdge.Vertexes[0], nextEdge.Vertexes[next_idx]):
                    mid_idx = 1
                if equal_vertex(theEdge.Vertexes[1], nextEdge.Vertexes[next_idx]):
                    mid_idx = 0
                if mid_idx is not None:
                    if equal_vertex(
                        theEdge.Vertexes[mid_idx], lastEdge.Vertexes[last_idx]
                    ):
                        midEdge = theEdge.copy()
                        # Part.show(midEdge)
                        break
                    else:
                        mid_idx = None
            if midEdge:
                break

        seam_wire = Part.Wire([sEdge, nextEdge, midEdge, lastEdge])
        seamFace = Part.Face(seam_wire)
        self.f_list.append(seamFace)
        theNode.nfIndexes.append(self.max_f_idx)
        self.max_f_idx += 1

    def showFaces(self):
        for i in self.index_list:
            Part.show(self.f_list[i])

    def unfold_tree2(self, node):
        # This function traverses the tree and unfolds the faces
        # beginning at the outermost nodes.
        # print "unfold_tree face", node.idx + 1
        theShell = []
        nodeShell = []
        theFoldLines = []
        nodeFoldLines = []
        for n_node in node.child_list:
            if self.error_code is None:
                shell, foldLines = self.unfold_tree2(n_node)
                theShell = theShell + shell
                theFoldLines = theFoldLines + foldLines
        if node.node_type == "Bend":
            trans_vec = node.tan_vec * node._trans_length
            for bFaces in theShell:
                bFaces.rotate(
                    self.f_list[node.idx].Surface.Center,
                    node.axis,
                    math.degrees(-node.bend_angle),
                )
                bFaces.translate(trans_vec)
            for fold in theFoldLines:
                fold.rotate(
                    self.f_list[node.idx].Surface.Center,
                    node.axis,
                    math.degrees(-node.bend_angle),
                )
                fold.translate(trans_vec)
            if self.error_code is None:
                # nodeShell = self.generateBendShell(node)
                nodeShell, nodeFoldLines = self.generateBendShell2(node)
        else:
            if self.error_code is None:
                # nodeShell = self.generateShell(node)
                for idx in node.nfIndexes:
                    new_face = self.build_new_face(idx)
                    nodeShell.append(new_face)

                # if len(node.seam_edges)>0:
                #  for seamEdge in node.seam_edges:
                #    self.makeSeamFace(seamEdge, node)
        FreeCAD.Console.PrintLog("ufo finish face" + str(node.idx + 1) + "\n")
        return (theShell + nodeShell, theFoldLines + nodeFoldLines)

    # Build a copy of the face, replacing any wire that must be replaced
    def build_new_face(self, face_index):
        new_wires = []
        face = self.f_list[face_index]
        face_replaced = False

        for wire_idx, wire in enumerate(face.Wires):
            new_wire, replaced = self.build_new_wire(wire, face_index, wire_idx)
            new_wires.append(new_wire)

            if replaced:
                face_replaced = True

        if face_replaced:
            return Part.Face(new_wires)
        else:
            return face.copy()

    # Given a wire, check if there is a replacement wire and return it, otherwise return a copy of the wire.
    def build_new_wire(self, wire, face_idx, wire_idx):
        for wire_replacement in self.wire_replacements:
            if (
                wire_replacement.face_idx == face_idx
                and wire_replacement.wire_idx == wire_idx
            ):
                return wire_replacement.new_wire, True

        return wire.copy(), False


#  from Defeaturing WB: Export to Step
def sew_Shape():
    """checking Shape"""

    doc = FreeCAD.ActiveDocument
    docG = FreeCADGui.ActiveDocument

    sel = FreeCADGui.Selection.getSelection()
    if len(sel) == 1:
        o = sel[0]
        if hasattr(o, "Shape"):
            sh = o.Shape.copy()
            sh.sewShape()
            sl = Part.Solid(sh)
            docG.getObject(o.Name).Visibility = False
            Part.show(sl)
            ao = FreeCAD.ActiveDocument.ActiveObject
            ao.Label = "Solid"
            docG.ActiveObject.ShapeColor = docG.getObject(o.Name).ShapeColor
            docG.ActiveObject.LineColor = docG.getObject(o.Name).LineColor
            docG.ActiveObject.PointColor = docG.getObject(o.Name).PointColor
            docG.ActiveObject.DiffuseColor = docG.getObject(o.Name).DiffuseColor
            docG.ActiveObject.Transparency = docG.getObject(o.Name).Transparency
    else:
        FreeCAD.Console.PrintError("select only one object")


def makeSolidExpSTEP():

    doc = FreeCAD.ActiveDocument
    docG = FreeCADGui.ActiveDocument
    if doc is not None:
        fname = doc.FileName
        if len(fname) == 0:
            fileNm = "untitled"
        else:
            fileNm = os.path.basename(fname)
            fileNm = os.path.splitext(fileNm)[0]
        tempdir = tempfile.gettempdir()  # get the current temporary directory
        # print(tempdir)
        # fileNm = os.path.basename(fname)
        # tempfilepath = os.path.join(tempdir,fname.rstrip(".fcstd").rstrip(".FCStd") + u'_cp.stp')
        tempfilepath = os.path.join(tempdir, fileNm + "_cp.stp")
        print(tempfilepath)
        sel = FreeCADGui.Selection.getSelection()
        if len(sel) == 1:
            __objs__ = []
            __objs__.append(sel[0])
            import ImportGui

            stop
            ImportGui.export(__objs__, tempfilepath)
            del __objs__
            # docG.getObject(sel[0].Name).Visibility = False
            ImportGui.insert(tempfilepath, doc.Name)
            FreeCADGui.SendMsgToActiveView("ViewFit")
        else:
            FreeCAD.Console.PrintError("Select only one object")
    else:
        FreeCAD.Console.PrintError("Select only one object")


##


def getUnfold(k_factor_lookup, solid, subelement, facename):
    resPart = None
    normalVect = None
    folds = None
    theName = None
    faceSel = ""
    ob_Name = solid.Name
    err_code = 0

    normalVect = subelement.normalAt(0, 0)
    FreeCAD.Console.PrintLog(f"name: {facename}\n ")
    f_number = int(facename.lstrip("Face")) - 1

    startzeit = time.process_time()

    TheTree = SheetTree(
        solid.Shape, f_number, k_factor_lookup
    )  # initializes the tree-structure
    if TheTree.error_code is None:
        TheTree.Bend_analysis(
            f_number, None
        )  # traverses the shape and builds the tree-structure
        endzeit = time.process_time()
        FreeCAD.Console.PrintLog("Analytical time: " + str(endzeit - startzeit) + "\n")

        if TheTree.error_code is None:
            # TheTree.showFaces()
            theFaceList, foldLines = TheTree.unfold_tree2(
                TheTree.root
            )  # traverses the tree-structure
            if TheTree.error_code is None:
                unfoldTime = time.process_time()
                FreeCAD.Console.PrintLog(
                    "time to run the unfold: " + str(unfoldTime - endzeit) + "\n"
                )
                folds = Part.Compound(foldLines)
                # Part.show(folds, 'Fold_Lines')
                try:
                    newShell = Part.Shell(theFaceList)
                except:
                    FreeCAD.Console.PrintLog(
                        "couldn't join some faces, show only single faces!\n"
                    )
                    resPart = Part.Compound(theFaceList)
                    # for newFace in theFaceList:
                    # Part.show(newFace)
                else:

                    try:
                        TheSolid = Part.Solid(newShell)
                        solidTime = time.process_time()
                        FreeCAD.Console.PrintLog(
                            "Time to make the solid: "
                            + str(solidTime - unfoldTime)
                            + "\n"
                        )
                    except:
                        FreeCAD.Console.PrintLog(
                            "Couldn't make a solid, show only a shell, Faces in List: "
                            + str(len(theFaceList))
                            + "\n"
                        )
                        resPart = newShell
                        # Part.show(newShell)
                        showTime = time.process_time()
                        FreeCAD.Console.PrintLog(
                            "Show time: " + str(showTime - unfoldTime) + "\n"
                        )
                    else:
                        try:
                            cleanSolid = TheSolid.removeSplitter()
                            # Part.show(cleanSolid)
                            resPart = cleanSolid

                        except:
                            # Part.show(TheSolid)
                            resPart = TheSolid
                        showTime = time.process_time()
                        FreeCAD.Console.PrintLog(
                            "Show time: "
                            + str(showTime - solidTime)
                            + " total time: "
                            + str(showTime - startzeit)
                            + "\n"
                        )

    if TheTree.error_code is not None:
        if TheTree.error_code == 1:
            FreeCAD.Console.PrintError(
                "Error at Face" + str(TheTree.failed_face_idx + 1) + "\n"
            )
            FreeCAD.Console.PrintError(
                "Trying to repeat the unfold process again with the Sewed copied Shape\n"
            )
            FreeCAD.ActiveDocument.openTransaction("sanitize")
            sew_Shape()
            FreeCAD.ActiveDocument.commitTransaction()
            ob = FreeCAD.ActiveDocument.ActiveObject
            ob_Name = ob.Name
            ob.Label = solid.Label + "_copy"
            faceSel = facename
            err_code = TheTree.error_code
        else:
            FreeCAD.Console.PrintError(
                "Error "
                + unfold_error[TheTree.error_code]
                + " at Face"
                + str(TheTree.failed_face_idx + 1)
                + "\n"
            )
    else:
        FreeCAD.Console.PrintLog("Unfold successful\n")

    endzeit = time.process_time()
    # FreeCAD.Console.PrintMessage("Analytical time: " + str(endzeit - startzeit) + "\n")
    return resPart, folds, normalVect, theName, err_code, faceSel, ob_Name


def SMGetGeoSegment(e):
    if "Line" in str(e.Curve):
        return Part.LineSegment(e.Vertexes[0].Point, e.Vertexes[1].Point)
    elif "Circle" in str(e.Curve):
        if not e.Closed:
            return Part.ArcOfCircle(
                e.Curve, e.FirstParameter, e.LastParameter, e.Curve.Axis.z > 0
            )
        else:
            return Part.Circle(e.Curve.Center, e.Curve.Axis, e.Curve.Radius)
    return None


def SMmakeSketchfromEdges(edges, name):
    precision = 0.1  # precision in Bspline to BiArcs
    quasidef = 0.01  # quasi deflection for Ellipses and Parabola
    usk = FreeCAD.activeDocument().addObject("Sketcher::SketchObject", name)
    geo = []
    for e in edges:
        if isinstance(e.Curve, Part.BSplineCurve):
            arcs = e.Curve.toBiArcs(precision)
            for i in arcs:
                eb = Part.Edge(i)
                seg = SMGetGeoSegment(eb)
                if seg is not None:
                    geo.append(seg)
        elif isinstance(e.Curve, Part.Ellipse) or isinstance(e.Curve, Part.Parabola):
            l = e.copy().discretize(QuasiDeflection=quasidef)
            plines = Part.makePolygon(l)
            for edg in plines.Edges:
                seg = SMGetGeoSegment(edg)
                if seg is not None:
                    geo.append(seg)
        else:
            seg = SMGetGeoSegment(e)
            if seg is not None:
                geo.append(seg)
    usk.addGeometry(geo)
    return usk


def processUnfold(
    k_factor_lookup,
    object,
    referenceFace,
    faceName,
    genSketch=True,
    splitSketches=False,
    sketchColor="#000080",
    bendSketchColor="#c00000",
    internalSketchColor="#ff5733",
    transparency=0.7,
    kFactorStandard="ansi",
):

    global KFACTORSTANDARD
    KFACTORSTANDARD = kFactorStandard

    unfoldShape = None
    unfold_sketch = None
    unfold_sketch_outline = None
    unfold_sketch_bend = None
    unfold_sketch_internal = None

    try:
        shape, foldComp, norm, thename, err_cd, fSel, obN = getUnfold(
            k_factor_lookup, object, referenceFace, faceName
        )
        foldLines = foldComp.Edges
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        SMLogger.error("exception at line " + str(exc_tb.tb_lineno), e.args)
        SMLogger.error(e.args)
        raise UnfoldException()

    if shape is None:
        raise UnfoldException()

    unfoldShape = FreeCAD.ActiveDocument.addObject("Part::Feature", "Unfold")
    unfoldShape.Shape = shape

    if genSketch:
        #locate the projection face
        unfoldobj = shape
        for face in shape.Faces:
            fnorm = face.normalAt(0,0)
            isSameDir = abs(fnorm.dot(norm) - 1.0) < 0.00001
            if isSameDir:
                unfoldobj = face
                break
        edges = []
        perimEdges = projectEx(unfoldobj, norm)[0]
        edges.append(perimEdges)
        if len(foldLines) > 0:
            co = Part.makeCompound(foldLines)
            foldEdges = projectEx(co, norm)[0]

            if not splitSketches:
                edges.append(foldEdges)
        unfold_sketch = generateSketch(edges, "Unfold_Sketch", sketchColor)
        FreeCAD.ActiveDocument.recompute()

        if splitSketches:
            tidy = False
            try:
                newface = Part.makeFace(unfold_sketch.Shape, "Part::FaceMakerBullseye")

                try:
                    owEdgs = newface.OuterWire.Edges
                    faceEdgs = newface.Edges
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    SMLogger.error(
                        "Exception at line "
                        + str(exc_tb.tb_lineno)
                        + ": Outline Sketch failed, re-trying after tidying up"
                    )
                    tidy = True
                    owEdgs = unfold_sketch.Shape.Edges
                    faceEdgs = unfold_sketch.Shape.Edges
                    FreeCAD.ActiveDocument.recompute()

                unfold_sketch_outline = generateSketch(
                    owEdgs, "Unfold_Sketch_Outline", sketchColor
                )

                if tidy:
                    SMLogger.error("tidying up Unfold_Sketch_Outline")
                intEdgs = []
                idx = []
                for i, e in enumerate(faceEdgs):
                    for oe in owEdgs:
                        if oe.hashCode() == e.hashCode():
                            idx.append(i)
                for i, e in enumerate(faceEdgs):
                    if i not in idx:
                        intEdgs.append(e)
                if len(intEdgs) > 0:
                    unfold_sketch_internal = generateSketch(
                        intEdgs, "Unfold_Sketch_Internal", internalSketchColor
                    )

            except Exception as e:
                print(e)
                exc_type, exc_obj, exc_tb = sys.exc_info()
                SMLogger.error(
                    "Exception at line "
                    + str(exc_tb.tb_lineno)
                    + ": Outline Sketch not created"
                )

        if len(foldLines) > 0 and splitSketches:
            unfold_sketch_bend = generateSketch(
                foldEdges, "Unfold_Sketch_bends", bendSketchColor
            )

    if FreeCAD.GuiUp:
        unfoldShape.ViewObject.Transparency = transparency

    return (
        unfoldShape,
        unfold_sketch,
        unfold_sketch_outline,
        unfold_sketch_bend,
        unfold_sketch_internal,
    )


def generateSketch(edges, name, color):

    p = Part.makeCompound(edges)
    try:
        sk = Draft.makeSketch(
            p.Edges, autoconstraints=True, addTo=None, delete=False, name=name
        )
        sk.Label = name
    except:
        doc = FreeCAD.ActiveDocument
        skb = doc.ActiveObject
        doc.removeObject(skb.Name)
        SMLogger.warning("discretizing Sketch")
        sk = SMmakeSketchfromEdges(p.Edges, name)

    if FreeCAD.GuiUp:
        rgb_color = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
        sk.ViewObject.LineColor = rgb_color
        sk.ViewObject.PointColor = rgb_color

    return sk
