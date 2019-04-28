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
# sheet_ufo.py git-version
# July 2018
# added sortEdgesTolerant: more robust generation of Wires for unbend Faces
# generate fold lines, to be used in drawings of the unfolded part.
# fixed calculation of Bend Angle, not working in some cases


# sheet_ufo20.py
# removal of dead code

# sheet_ufo19.py
# changes from June 2018
# - found solution for the new unbendFace function.
# - supports now non orthogonals cut in the bends
# - seams do not get a face, just do not call makeSeamFace
#   this avoids internal faces in the unfold under certain cases.
 

# sheet_ufo18.py
# Changes done in 2016 and June 2018
# allow more complex bends: not only straight cut side edges
# tested some code, not published

# sheet_ufo17.py
# Refactored version December 2015
# Clear division of tasks between analysis and folding

# To do:
# change code to handle face indexes in the node instead of faces


# sheet_ufo16.py
# Die Weiterreichung eines schon geschnittenen Seitenfaces macht Probleme.
# Die Seitenfaces passen hinterher nicht mehr mit den Hauptflächen zusammen.

# Geänderter Ansatz: lasse die Seitenflächen in der Suchliste und 
# schneide jeweils nur den benötigten Teil raus.
# Ich brauche jetzt eine Suchliste und eine Unfoldliste für die 
# Face-Indices.

# To do: 
# - handle a selected seam
# - handle not-circle-curves in bends, done
# - detect features like welded screws
# - make a view-provider for bends
# - make the k-factor selectable
# - upfold or unfold single bends
 

# ideas:
# during analysis make a mesh-like structure for the bend-node
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

'''

def main():
	
	return 0

if __name__ == '__main__':
	main()


'''


import Part, FreeCAD, FreeCADGui, os
from PySide import QtGui, QtCore
from FreeCAD import Base
from FreeCAD import Gui
import DraftVecUtils, DraftGeomUtils, math, time
import Draft
import Drawing
from SheetMetalCmd import iconPath
from lookup import get_val_from_range

genSketchChecked = True
genSketchColor = '#000080'      
bendSketchChecked = False
bendSketchColor = '#c00000'      
intSketchColor = '#ff5733'
genObjTransparency = 70
manKFactor = None
kFactorStandard = None

# to do: 
# - Put error numbers into the text
# - Put user help into more texts
unfold_error = {
  # error codes for the tree-object
  1: ('starting: volume unusable, needs a real 3D-sheet-metal with thickness'), 
  2: ('Starting: invalid point for thickness measurement'), 
  3: ('Starting: invalid thickness'), 
  4: ('Starting: invalid shape'), 
  5: ('Starting: Shape has unneeded edges. Please use function refine shape from the Part Workbench before unfolding!'), 
  # error codes for the bend-analysis 
  10: ('Analysis: zero wires in sheet edge analysis'), 
  11: ('Analysis: double bends not implemented'), 
  12: ('Analysis: more than one bend-child actually not supported'), 
  13: ('Analysis: Sheet thickness invalid for this face!'), 
  14: ('Analysis: the code can not handle edges without neighbor faces'), 
  15: ('Analysis: the code needs a face at all sheet edges'), 
  16: ('Analysis: did not find startangle of bend, please post failing sample for analysis'),
  17: ('Analysis: Type of surface not supported for sheet metal parts'), # <SurfaceOfExtrusion object> fix me?
  # error codes for the unfolding
  20: ('Unfold: section wire with less than 4 edges'),
  21: ('Unfold: Unfold: section wire not closed'),
  22: ('Unfold: section failed'),
  23: ('Unfold: CutToolWire not closed'),
  24: ('Unfold: bend-face without child not implemented'),
  25: ('Unfold: '),
  26: ('Unfold: not handled curve type in unbendFace'),
  -1: ('unknown error')} 


def SMLog(* args):
  message = ""
  for x in args:
    message += str(x)
  FreeCAD.Console.PrintLog(message + "\n")
  #FreeCAD.Console.PrintMessage(message + "\n") #maui

def SMError(* args):
  message = ""
  for x in args:
    message += str(x)
  FreeCAD.Console.PrintError(message + "\n")

def SMMessage(* args):
  message = ""
  for x in args:
    message += str(x)
  FreeCAD.Console.PrintMessage(message + "\n")

def SMWarning(* args):
  message = ""
  for x in args:
    message += str(x)
  FreeCAD.Console.PrintWarning(message + "\n")

def SMErrorBox(* args):  
    message = ""
    for x in args:
        message += str(x)
    SMError(message)
    QtGui.QMessageBox.critical(FreeCADGui.getMainWindow(), "ERROR", message)

def equal_vertex(vert1, vert2, p=5):
  # compares two vertices 
  return (round(vert1.X - vert2.X,p)==0 and round(vert1.Y - vert2.Y,p)==0 and round(vert1.Z - vert2.Z,p)==0)

def equal_vector(vec1, vec2, p=5):
  # compares two vectors 
  return (round(vec1.x - vec2.x,p)==0 and round(vec1.y - vec2.y,p)==0 and round(vec1.z - vec2.z,p)==0)

def radial_vector(point, axis_pnt, axis):
  chord = axis_pnt.sub(point)
  norm = axis.cross(chord)
  perp = axis.cross(norm)
  # FreeCAD.Console.PrintLog( str(chord) + ' ' + str(norm) + ' ' + str(perp)+'\n')
  dist_rv = DraftVecUtils.project(chord,perp)
  #test_line = Part.makeLine(axis_pnt.add(dist_rv),axis_pnt)
  # test_line = Part.makeLine(axis_pnt.add(perp),axis_pnt)
  # test_line = Part.makeLine(point, axis_pnt)
  # Part.show(test_line)
  return perp.normalize()

def equal_angle(ang1, ang2, p=5):
  # compares two angles
  result = False
  if round(ang1 - ang2, p)==0:
    result = True
  if round((ang1-2.0*math.pi) - ang2, p)==0:
    result = True
  if round(ang1 - (ang2-2.0*math.pi), p)==0:
    result = True
  return result

def equal_edge(edg1, edg2, p=5):
  result = True
  if len(edg1.Vertexes) > 1:
    if not (equal_vertex(edg1.Vertexes[0], edg2.Vertexes[0]) or equal_vertex(edg1.Vertexes[0], edg2.Vertexes[1])):
      result = False
    if not (equal_vertex(edg1.Vertexes[1], edg2.Vertexes[0]) or equal_vertex(edg1.Vertexes[1], edg2.Vertexes[1])):
      result = False
  else:
    if not (equal_vertex(edg1.Vertexes[0], edg2.Vertexes[0])):
      result = False
    if len(edg2.Vertexes) > 1:
      result = False
  return result


class Simple_node(object):
  ''' This class defines the nodes of a tree, that is the result of
  the analysis of a sheet-metal-part.
  Each flat or bend part of the metal-sheet gets a node in the tree.
  The indexes are the number of the face in the original part.
  Faces of the edge of the metal-sheet need in cases to be split.
  These new faces are added to the index list.
  '''
  def __init__(self, f_idx=None, Parent_node= None, Parent_edge = None, k_factor_lookup = None):
    self.idx = f_idx  # index of the "top-face"
    self.c_face_idx = None # face index to the opposite face of the sheet (counter-face)
    self.node_type = None  # 'Flat' or 'Bend'
    self.p_node = Parent_node   # Parent node
    self.p_edge = Parent_edge # the connecting edge to the parent node
    self.child_list = [] # List of child-nodes = link to tree structure
    self.child_idx_lists = [] # List of lists with child_idx and child_edge
    # need also a list of indices of child faces
    self.sheet_edges = [] # List of edges without child-face 
    self.axis = None # direction of the axis of the detected cylindrical face
    self.facePosi = None 
    self.bendCenter = None # Vector of the center of the detected cylindrical face
    self.distCenter = None # Value used to detect faces at opposite side of the bend
    self.innerRadius = None # nominal radius of the bend 
    # self.axis for 'Flat'-face: vector pointing from the surface into the metal
    self.bend_dir = None # bend direction values: "up" or "down"
    self.bend_angle = None # angle in radians
    self.tan_vec = None # direction of translation for Bend nodes
    self.oppositePoint = None # Point of a vertex on the opposite site, used to align points to the sheet plane
    self.vertexDict = {} # Vertexes of a bend, original and unbend coordinates, flags p, c, t, o
    self.edgeDict = {} # unbend edges dictionary, key is a combination of indexes to vertexDict.
    self.k_factor_lookup = k_factor_lookup # k-factor lookup dictionary, according to ANSI standard
    self._trans_length = None # length of translation for Bend nodes
    self.analysis_ok = True # indicator if something went wrong with the analysis of the face
    self.error_code = None # index to unfold_error dictionary
    # here the new features of the nodes:
    self.nfIndexes = [] # list of all face-indexes of a node (flat and bend: folded state)
    self.seam_edges = [] # list with edges to seams
    # bend faces are needed for movement simulation at single other bends.
    # otherwise unfolded faces are recreated from self.b_edges
    self.node_flattened_faces = [] # faces of a flattened bend node.
    self.unfoldTopList = None # source of identical side edges
    self.unfoldCounterList = None # source of identical side edges
    self.actual_angle = None # state of angle in refolded sheet metal part
    self.p_wire = None # wire common with parent node, used for bend node
    self.c_wire = None # wire common with child node, used for bend node
    self.b_edges = [] # list of edges in a bend node, that needs to be recalculated, at unfolding

  def get_Face_idx(self):
    # get the face index from the tree-element
    return self.idx
    
  @property
  def k_Factor(self):
    global manKFactor

    k = None
    if manKFactor is not None: 
        k = manKFactor
    else:
        # obtain the K-factor from the lookup table 
        if kFactorStandard is None:
            raise ValueError('K-factor standard declaration is required!')
        k = get_val_from_range(self.k_factor_lookup, self.innerRadius / self.thickness)
    if kFactorStandard == 'din':
        k = k / 2
    elif kFactorStandard == 'ansi':
        pass
    else:
        raise ValueError('Unrecognized K-factor standard: %s' % (str(kFactorStandard)))
    return k 
        
  @k_Factor.setter
  def k_Factor(self, val):
    SMError("k_Factor is a readonly property! Won't set to:", val) 
    

class SheetTree(object):
  def __init__(self, TheShape, f_idx, k_factor_lookup):
    self.cFaceTol = 0.002 # tolerance to detect counter-face vertices
    # this high tolerance was needed for more real parts
    self.root = None # make_new_face_node adds the root node if parent_node == None
    self.__Shape = TheShape.copy()
    self.error_code = None
    self.failed_face_idx = None
    self.k_factor_lookup = k_factor_lookup
    
    if not self.__Shape.isValid():
      FreeCAD.Console.PrintLog("The shape is not valid!" + "\n")
      self.error_code = 4  # Starting: invalid shape
      self.failed_face_idx = f_idx
    
    #Part.show(self.__Shape)
    
    # List of indices to the shape.Faces. The list is used a lot for face searches.
    # Some faces will be cut and the new ones added to the list.
    # So a list of faces independent of the shape is needed.
    self.f_list = []  #self.__Shape.Faces.copy() does not work
    self.index_list =[]
    self.index_unfold_list = [] # indexes needed for unfolding
    for i in range(len (self.__Shape.Faces)):
    #for i in range(len (self.f_list)):
      # if i<>(f_idx):
      self.index_list.append(i)
      self.index_unfold_list.append(i)
      self.f_list.append(self.__Shape.Faces[i])
    #print self.index_list
    self.max_f_idx = len(self.f_list) # need this value to make correct indices to new faces
    self.unfoldFaces = len(self.f_list) # need the original number of faces for error detection
    withoutSplitter = self.__Shape.removeSplitter()
    #if self.unfoldFaces > len(withoutSplitter.Faces): # This is not a good idea! Most sheet metal parts have unneeded edges.
      #print 'got case which needs a refine shape from the Part workbench!'
      #self.error_code = 5
      #self.failed_face_idx = f_idx
      

    theVol = self.__Shape.Volume
    if theVol < 0.0001:
      FreeCAD.Console.PrintLog("Shape is not a real 3D-object or to small for a metal-sheet!" + "\n")
      self.error_code = 1
      self.failed_face_idx = f_idx

    else:
      # Make a first estimate of the thickness
      estimated_thickness = theVol/(self.__Shape.Area / 2.0)
      FreeCAD.Console.PrintLog( "approximate Thickness: " + str(estimated_thickness) + "\n")
      # Measure the real thickness of the initial face: Use Orientation and
      # Axis to make an measurement vector
      
    
      if hasattr(self.__Shape.Faces[f_idx],'Surface'):
        # Part.show(self.__Shape.Faces[f_idx])
        # print 'the object is a face! vertices: ', len(self.__Shape.Faces[f_idx].Vertexes)
        F_type = self.__Shape.Faces[f_idx].Surface
        # fixme: through an error, if not Plane Object
        FreeCAD.Console.PrintLog('It is a: ' + str(F_type) + '\n')
        FreeCAD.Console.PrintLog('Orientation: ' + str(self.__Shape.Faces[f_idx].Orientation) + '\n')
        
        # Need a point on the surface to measure the thickness.
        # Sheet edges could be sloping, so there is a danger to measure
        # right at the edge. 
        # Try with Arithmetic mean of plane vertices
        m_vec = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
        for Vvec in self.__Shape.Faces[f_idx].Vertexes:
            #m_vec = m_vec.add(Base.Vector(Vvec.X, Vvec.Y, Vvec.Z))
            m_vec = m_vec.add(Vvec.Point)
        mvec = m_vec.multiply(1.0/len(self.__Shape.Faces[f_idx].Vertexes))
        FreeCAD.Console.PrintLog("mvec: " + str(mvec) + "\n")
        
        #if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
          #s_Posi = self.__Shape.Faces[f_idx].Surface.Position
          #k = 0
          # while k < len(self.__Shape.Faces[f_idx].Vertexes):
          # fixme: what if measurepoint is outside?
          
        if self.__Shape.isInside(mvec, 0.00001, True):
          measure_pos = mvec
          gotValidMeasurePosition = True
        else:
          gotValidMeasurePosition = False
          for pvert in self.__Shape.Faces[f_idx].OuterWire.Vertexes:
            #pvert = self.__Shape.Faces[f_idx].Vertexes[k]
            pvec = Base.Vector(pvert.X, pvert.Y, pvert.Z)
            shiftvec =  mvec.sub(pvec)
            shiftvec = shiftvec.normalize()*2.0*estimated_thickness
            measure_pos = pvec.add(shiftvec)
            if self.__Shape.isInside(measure_pos, 0.00001, True):
              gotValidMeasurePosition = True
              break
          
        # Description: Checks if a point is inside a solid with a certain tolerance.
        # If the 3rd parameter is True a point on a face is considered as inside
        #if not self.__Shape.isInside(measure_pos, 0.00001, True):
        if not gotValidMeasurePosition:
          FreeCAD.Console.PrintLog("Starting measure_pos for thickness measurement is outside!\n")
          self.error_code = 2
          self.failed_face_idx = f_idx

        
        if hasattr(self.__Shape.Faces[f_idx].Surface,'Axis'):
          s_Axis =  self.__Shape.Faces[f_idx].Surface.Axis
          # print 'We have an axis: ', s_Axis
          if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
            s_Posi = self.__Shape.Faces[f_idx].Surface.Position
            # print 'We have a position: ', s_Posi
            s_Ori = self.__Shape.Faces[f_idx].Orientation
            s_Axismp = Base.Vector(s_Axis.x, s_Axis.y, s_Axis.z).multiply(2.0*estimated_thickness)
            if s_Ori == 'Forward':
              Meassure_axis = Part.makeLine(measure_pos,measure_pos.sub(s_Axismp))
              ext_Vec = Base.Vector(-s_Axis.x, -s_Axis.y, -s_Axis.z)
              # Meassure_axis = Part.makeLine(measure_pos,measure_pos.sub(s_Axis.multiply(2.0*estimated_thickness)))
            else:                    
              # Meassure_axis = Part.makeLine(measure_pos,measure_pos.add(s_Axis.multiply(2.0*estimated_thickness)))
              Meassure_axis = Part.makeLine(measure_pos,measure_pos.add(s_Axismp))
              ext_Vec = Base.Vector(s_Axis.x, s_Axis.y, s_Axis.z)
            # Part.show(Meassure_axis)
                
        lostShape = self.__Shape.copy()
        lLine = Meassure_axis.common(lostShape)
        lLine = Meassure_axis.common(self.__Shape)
        FreeCAD.Console.PrintLog("lLine number edges: " + str(len(lLine.Edges)) + "\n")
        measVert = Part.Vertex(measure_pos)
        for mEdge in lLine.Edges:
          if equal_vertex(mEdge.Vertexes[0], measVert) or equal_vertex(mEdge.Vertexes[1], measVert):
            self.__thickness = mEdge.Length
        
        # self.__thickness = lLine.Length
        if (self.__thickness < estimated_thickness) or (self.__thickness > 1.9 * estimated_thickness):
          self.error_code = 3
          self.failed_face_idx = f_idx
          FreeCAD.Console.PrintLog("estimated thickness: " + str(estimated_thickness) + " measured thickness: " + self.__thickness + "\n")
          Part.show(lLine, 'Measurement_Thickness_trial')


  def get_node_faces(self, theNode, wires_e_lists):
    ''' This function searches for all faces making up the node, except
    of the top and bottom face, which are already there.
    wires_e_list is the list of wires lists of the top face without the parent-edge
    theNode: the actual node to be filled with data.
    '''
    
    # How to begin?
    # searching for all faces that have two vertices in common with 
    # an edge from the list should give the sheet edge.
    # But, we also need to look at the sheet edge, in order to not claim
    # faces from the next node!
    # Then we have to treat those faces that belong to more than one
    # node. Those faces needs to be cut and the face list needs to be updated.
    # look also at the number of wires of the top face. More wires will
    # indicate a hole or a feature.
    #print " When will this be called"
    found_indices = []
    # A search strategy for faces based on the wires_e_lists is needed.
    # 

    for theWire in wires_e_lists:
      for theEdge in theWire:
        analyVert = theEdge.Vertexes[0]
        search_list = []
        for x in self.index_list:
          search_list.append(x)
        for i in search_list:
          for lookVert in self.f_list[i].Vertexes:
            if equal_vertex(lookVert, analyVert):
              if len(theEdge.Vertexes) == 1: # Edge is a circle
                if not self.is_sheet_edge_face(theEdge, theNode):
                  found_indices.append(i) # found a node face
                  theNode.child_idx_lists.append([i,theEdge])
                  #self.index_list.remove(i) # remove this face from the index_list
                  #Part.show(self.f_list[i])
              else:
                nextVert = theEdge.Vertexes[1]
                for looknextVert in self.f_list[i].Vertexes:
                  if equal_vertex(looknextVert, nextVert):
                    if not self.is_sheet_edge_face(theEdge, theNode):
                      found_indices.append(i) # found a node face
                      theNode.child_idx_lists.append([i,theEdge])
                      #self.index_list.remove(i) # remove this face from the index_list
                      #Part.show(self.f_list[i])
    FreeCAD.Console.PrintLog("found_indices: " + str(found_indices) + "\n")
                


  def is_sheet_edge_face(self, ise_edge, tree_node): # ise_edge: IsSheetEdge_edge
    # idea: look at properties of neighbor face
    # look at edges with distance of sheet-thickness.
    #    if found and surface == cylinder, check if it could be a bend-node.  
    # look at number of edges:
    # A face with 3 edges is at the sheet edge Cylinder-face or triangle (oh no!)
    # need to look also at surface!
    # A sheet edge face with more as 4 edges, is common to more than 1 node.
    
    # get the face which has a common edge with ise_edge
    the_index = None
    has_sheet_distance_vertex = False
    for i in self.index_list:
      for sf_edge in self.f_list[i].Edges:
        if sf_edge.isSame(ise_edge):
          the_index = i
          #print 'got edge face: Face', str(i+1)
          break
      if the_index is not None:
        break
          
    # Simple strategy applied: look if the connecting face has vertexes
    # with sheet-thickness distance to the top face.
    # fix me: this will fail with sharpened sheet edges with two faces
    # between top and bottom.
    if the_index is not None:
      distVerts = 0
      vertList = []
      F_type = str(self.f_list[tree_node.idx].Surface)
      # now we need to search for vertexes with sheet_thickness_distance
      for F_vert in self.f_list[i].Vertexes:
        #vDist = self.getDistanceToFace(F_vert, tree_node)
        #if vDist > maxDist: maxDist = vDist
        #if vDist < minDist: minDist = vDist
      #maxDist = maxDist- self.__thickness
      #if (minDist > -self.cFaceTol) and (maxDist < self.cFaceTol) and (maxDist > -self.cFaceTol):

        if self.isVertOpposite(F_vert, tree_node):
          has_sheet_distance_vertex = True
          if len(self.f_list[i].Edges)<5:
            tree_node.nfIndexes.append(i)
            self.index_list.remove(i)
            #Part.show(self.f_list[i])
          else:
            # need to cut the face at the ends of ise_edge
            self.divideEdgeFace(i, ise_edge, F_vert, tree_node)
          break

    else:
      tree_node.analysis_ok = False 
      tree_node.error_code = 15  # Analysis: the code needs a face at all sheet edges
      self.error_code = 15
      self.failed_face_idx = tree_node.idx
      Part.show(self.f_list[tree_node.idx])
            
    return has_sheet_distance_vertex


  def isVertOpposite(self, theVert, theNode):
    F_type = str(self.f_list[theNode.idx].Surface)
    vF_vert = Base.Vector(theVert.X, theVert.Y, theVert.Z)
    if F_type == "<Plane object>":
      distFailure = vF_vert.distanceToPlane (theNode.facePosi, theNode.axis) - self.__thickness
    elif F_type == "<Cylinder object>":
      distFailure = vF_vert.distanceToLine (theNode.bendCenter, theNode.axis) - theNode.distCenter
    else: 
      distFailure = 100.0
      theNode.error_code = 17  # Analysis: the code needs a face at all sheet edges
      self.error_code = 17
      self.failed_face_idx = theNode.idx
      #Part.show(self.f_list[theNode.idx], 'SurfaceType_not_supported')
    # print "counter face distance: ", dist_v + self.__thickness
    if (distFailure < self.cFaceTol) and (distFailure > -self.cFaceTol):
      return True
    else:
      return False

  def getDistanceToFace(self, theVert, theNode):
    F_type = str(self.f_list[theNode.idx].Surface)
    vF_vert = Base.Vector(theVert.X, theVert.Y, theVert.Z)
    # a positive distance should go through the sheet metal 
    if F_type == "<Plane object>":
      dist = vF_vert.distanceToPlane (theNode.facePosi, theNode.axis)
    if F_type == "<Cylinder object>":
      dist = vF_vert.distanceToLine(theNode.bendCenter, theNode.axis) - self.f_list[theNode.idx].Surface.Radius
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
    F_type = str(self.f_list[tree_node.idx].Surface)
    needCut0 = True
    firstCutFaceIdx = None
    for sEdge in self.f_list[fIdx].Edges:
      if equal_vertex(ise_edge.Vertexes[0], sEdge.Vertexes[0]) and \
        self.isVertOpposite(sEdge.Vertexes[1], tree_node):
        needCut0 = False
        theEdge = sEdge
      if equal_vertex(ise_edge.Vertexes[0], sEdge.Vertexes[1]) and \
        self.isVertOpposite(sEdge.Vertexes[0], tree_node):
        needCut0 = False
        theEdge = sEdge
    if needCut0:
      #print "need Cut at 0 with fIdx: ", fIdx
      nFace = self.cutEdgeFace(0, fIdx, ise_edge, tree_node)
      
      tree_node.nfIndexes.append(self.max_f_idx)
      self.f_list.append(nFace)
      firstCutFaceIdx = self.max_f_idx
      self.max_f_idx += 1
      #self.f_list.append(rFace)
      #self.index_list.append(self.max_f_idx)
      #self.max_f_idx += 1
      #self.index_list.remove(fIdx)
      #Part.show(nFace)
    #else:
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
      #print "need Cut at 1 with fIdx: ", fIdx
      nFace = self.cutEdgeFace(1, fIdx, ise_edge, tree_node)
      tree_node.nfIndexes.append(self.max_f_idx)
      self.f_list.append(nFace)
      firstCutFaceIdx = self.max_f_idx
      self.max_f_idx += 1
      #self.f_list.append(rFace)
      #self.index_list.append(self.max_f_idx)
      #self.max_f_idx += 1
      #if not needCut0:
      #  self.index_list.remove(fIdx)
      #Part.show(nFace)
    #else:
    #  Part.show(theEdge)


    
  def cutEdgeFace(self, eIdx, fIdx, theEdge, theNode):
    ''' This function cuts a face in two pieces.
    one piece is connected to the node. 
    The residual piece is discarded. 
    The function returns the piece that has a common edge with the top face of theNode.
    '''
    #print "now the face cutter: ", fIdx, ' ', eIdx, ' ', theNode.idx
    #Part.show(theEdge, 'EdgeToCut'+ str(theNode.idx+1)+'_')
    #Part.show(self.f_list[fIdx], 'FaceToCut'+ str(theNode.idx+1)+'_')
    
    if eIdx == 0:
      otherIdx = 1
    else:
      otherIdx = 0
    
    origin = theEdge.Vertexes[eIdx].Point
    
    F_type = str(self.f_list[theNode.idx].Surface)
    if F_type == "<Plane object>":
      tan_vec = theEdge.Vertexes[eIdx].Point - theEdge.Vertexes[otherIdx].Point
      #o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z) 
      tan_vec.normalize()
      #New approach: search for the nearest vertex at the opposite site.
      # The cut is done between the Vertex indicated by eIdx and the nearest
      # opposite vertex. This approach should avoid the generation of 
      # additional short edges in the side faces.
      searchAxis = theNode.axis
      #else:
        #searchAxis = radVector
            
      maxDistance = 1000
      oppoPoint = None
      #print('need to check Face', str(fIdx+1), ' with ', len(self.f_list[fIdx].Vertexes))
      for theVert in self.f_list[fIdx].Vertexes:
        # need to check if theVert has 
        if self.isVertOpposite(theVert, theNode):
          vertDist = theVert.Point.distanceToLine(origin, searchAxis)
          if vertDist < maxDistance:
            maxDistance = vertDist
            oppoPoint = theVert.Point
            
      if oppoPoint is None:
        print(' error need always an opposite point in a side face!')
        # fix me: need a proper error condition.
      
      #vec1 = Base.Vector(theNode.axis.x, theNode.axis.y, theNode.axis.z) # make a copy
      vec1 = (oppoPoint - origin).normalize()

      crossVec = tan_vec.cross(vec1)
      crossVec.multiply(3.0*self.__thickness)

      vec1.multiply(self.__thickness)
      # defining the points of the cutting plane:
      Spnt1 = origin - vec1 - crossVec
      Spnt2 = origin - vec1 + crossVec
      Spnt3 = origin + vec1 +  vec1 + crossVec
      Spnt4 = origin + vec1 +  vec1 - crossVec
  
      
      
    if F_type == "<Cylinder object>":
      ePar = theEdge.parameterAt(theEdge.Vertexes[eIdx])
      FreeCAD.Console.PrintLog("Idx: " + str(eIdx) + " ePar: " + str(ePar) + "\n")
      otherPar = theEdge.parameterAt(theEdge.Vertexes[otherIdx])
      tan_vec = theEdge.tangentAt(ePar)
      if ePar < otherPar:
        tan_vec.multiply(-1.0)
      
      #tan_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(tan_vec), theEdge.Vertexes[eIdx].Point)
      #Part.show(tan_line, 'tan_line'+ str(theNode.idx+1)+'_')
      
      edge_vec = theEdge.Vertexes[eIdx].copy().Point
      radVector = radial_vector(edge_vec, theNode.bendCenter, theNode.axis)
      if theNode.bend_dir == "down":
        radVector.multiply(-1.0)
  
      #rad_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(radVector), theEdge.Vertexes[eIdx].Point)
      #Part.show(rad_line, 'rad_line'+ str(theNode.idx+1)+'_')
      searchAxis = radVector
            
      maxDistance = 1000
      oppoPoint = None
      #print('need to check Face', str(fIdx+1), ' with ', len(self.f_list[fIdx].Vertexes))
      for theVert in self.f_list[fIdx].Vertexes:
        # need to check if theVert has 
        if self.isVertOpposite(theVert, theNode):
          vertDist = theVert.Point.distanceToLine(origin, searchAxis)
          if vertDist < maxDistance:
            maxDistance = vertDist
            oppoPoint = theVert.Point
            
      if oppoPoint is None:
        print(' error need always an opposite point in a side face!')
        # fix me: need a proper error condition.
      #vec1 = Base.Vector(radVector.x, radVector.y, radVector.z) # make a copy
      vec1 = (oppoPoint - origin).normalize()

      crossVec = tan_vec.cross(vec1)
      crossVec.multiply(3.0*self.__thickness)

      vec1.multiply(self.__thickness)
      # defining the points of the cutting plane:
      Spnt1 = origin - vec1 - crossVec
      Spnt2 = origin - vec1 + crossVec
      Spnt3 = origin + vec1 +  vec1 + crossVec
      Spnt4 = origin + vec1 +  vec1 - crossVec
    
    Sedge1 = Part.makeLine(Spnt1,Spnt2)
    Sedge2 = Part.makeLine(Spnt2,Spnt3)
    Sedge3 = Part.makeLine(Spnt3,Spnt4)
    Sedge4 = Part.makeLine(Spnt4,Spnt1)
        
    Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
    # Part.show(Sw1, 'cutWire'+ str(theNode.idx+1)+'_')
    Sf1=Part.Face(Sw1) #
    #Part.show(Sf1, 'cutFace'+ str(theNode.idx+1)+'_')
    #cut_solid = Sf1.extrude(tan_vec.multiply(5.0))
    cut_solid = Sf1.extrude(tan_vec.multiply(self.__thickness))
    #Part.show(cut_solid, 'cut_solid'+ str(theNode.idx+1)+'_')
    #cut_opposite = Sf1.extrude(tan_vec.multiply(-5.0))
    
    cutFaces_node = self.f_list[fIdx].cut(cut_solid)
    for cFace in cutFaces_node.Faces:
      for myVert in cFace.Vertexes:
        if equal_vertex(theEdge.Vertexes[eIdx], myVert):
          nodeFace = cFace
          #print "The nodeFace Idx: ", fIdx, ' eIdx: ', eIdx 
          #Part.show(nodeFace)
          break

    return nodeFace #, residueFace
    

  def getBendAngle(self, newNode, wires_e_lists):
    ''' Get the bend angle for a node connected to a bend face,
    Get the k-Factor
    Get the translation Length
    '''
    # newNode = Simple_node(face_idx, P_node, P_edge)
    P_node = newNode.p_node
    P_edge = newNode.p_edge
    face_idx = newNode.idx
    theFace = self.__Shape.Faces[face_idx]
    
    s_Axis = newNode.axis
    s_Center = newNode.bendCenter
    
    #Start to investigate the angles at self.__Shape.Faces[face_idx].ParameterRange[0]
    angle_0 = theFace.ParameterRange[0]
    angle_1 = theFace.ParameterRange[1]
    
    # idea: identify the angle at edge_vec = P_edge.Vertexes[0].copy().Point
    # This will be = angle_start
    # calculate the tan_vec from valueAt

    edge_vec = P_edge.Vertexes[0].copy().Point
    edgeAngle, edgePar = theFace.Surface.parameter(edge_vec)

    #print 'the angles: ', angle_0, ' ', angle_1, ' ', edgeAngle, ' ', edgeAngle - 2*math.pi
    
    if equal_angle(angle_0, edgeAngle):
      angle_start = angle_0
      angle_end = angle_1
    else:
      angle_start = angle_1
      angle_end = angle_0
    len_start = edgePar
      
    newNode.bend_angle = angle_end - angle_start
    angle_tan = angle_start + newNode.bend_angle/6.0 # need to have the angle_tan before correcting the sign

    if newNode.bend_angle < 0.0:
      newNode.bend_angle = -newNode.bend_angle

    first_vec = radial_vector(edge_vec, s_Center, s_Axis)
    tanPos = self.__Shape.Faces[face_idx].valueAt(angle_tan,len_start)
    sec_vec = radial_vector(tanPos, s_Center, s_Axis)


    cross_vec = first_vec.cross(sec_vec)
    triple_prod = cross_vec.dot(s_Axis)
    if triple_prod < 0:
      newNode.axis = -newNode.axis
      s_Axis = -s_Axis
      
    #tan_vec = radial_vector(tanPos, s_Center, s_Axis)
    tan_vec = s_Axis.cross(first_vec)
    #Part.show(Part.makeLine(tanPos, tanPos + 10 * tan_vec), 'tan_Vec')
    newNode.tan_vec = tan_vec
    #make a better tan_vec based on the parent face normal and the parent edge:
    if P_node.node_type == 'Flat':
      pVec = P_edge.Vertexes[1].Point - P_edge.Vertexes[0].Point
      pVec = pVec.normalize()
      pTanVec = P_node.axis.cross(pVec)
      if (tan_vec - pTanVec).Length > 1.0:
        newNode.tan_vec = -pTanVec
      else:
        newNode.tan_vec = pTanVec
        
    if newNode.bend_dir == 'up':
      innerRadius = theFace.Surface.Radius
    else:
      innerRadius = theFace.Surface.Radius - self.__thickness

    # Will be used to determine the correct K-factor
    newNode.thickness = self.__thickness
    newNode.innerRadius = innerRadius

    FreeCAD.Console.PrintLog(newNode.bend_dir + " Face"+ str(newNode.idx+1)+ " k-factor: "+ str(newNode.k_Factor) + "\n")
    newNode._trans_length = (innerRadius + newNode.k_Factor * self.__thickness) * newNode.bend_angle


    #print 'newNode._trans_length: ', newNode._trans_length
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
      
        
    #print 'node angles: ', newNode.bend_angle, ' ', diffAngle







  def make_new_face_node(self, face_idx, P_node, P_edge, wires_e_lists):
    # e_list: list of edges of the top face of a node without the parent-edge (P_edge)
    # analyze the face and get type of face ("Flat" or "Bend")
    # search the counter face, get axis of Face
    # In case of "Bend" get angle, k_factor and trans_length
    # put the node into the tree
    newNode = Simple_node(face_idx, P_node, P_edge, self.k_factor_lookup)
    F_type = str(self.__Shape.Faces[face_idx].Surface)
    
    # This face should be a node in the tree, and is therefore known!
    # removed from the list of all unknown faces
    self.index_list.remove(face_idx)
    # This means, it could also not be found as neighbor face anymore.
    #newNode.node_faces.append(self.f_list[face_idx].copy())
    newNode.nfIndexes.append(face_idx)
    
    such_list = [] 
    for k in self.index_list:
      such_list.append(k)
    
    if F_type == "<Plane object>":
      newNode.node_type = 'Flat' # fixme
      FreeCAD.Console.PrintLog("Face"+ str(face_idx+1) + " Type: "+ str(newNode.node_type) + "\n")

      s_Posi = self.__Shape.Faces[face_idx].Surface.Position
      newNode.facePosi = s_Posi
      s_Ori = self.__Shape.Faces[face_idx].Orientation
      s_Axis = self.__Shape.Faces[face_idx].Surface.Axis
      if s_Ori == 'Forward':
        ext_Vec = Base.Vector(-s_Axis.x, -s_Axis.y, -s_Axis.z)
      else:                    
        ext_Vec = Base.Vector(s_Axis.x, s_Axis.y, s_Axis.z)

      newNode.axis = ext_Vec
      axis_line = Part.makeLine(s_Posi.add(ext_Vec), s_Posi)
      #Part.show(axis_line, 'axis_line'+str(face_idx+1))
      
      # need a mean point of the face to avoid false counter faces
      faceMiddle = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
      for Vvec in self.__Shape.Faces[face_idx].OuterWire.Vertexes:
          faceMiddle = faceMiddle.add(Vvec.Point)
      faceMiddle = faceMiddle.multiply(1.0/len(self.__Shape.Faces[face_idx].OuterWire.Vertexes))
      faceMiddle = faceMiddle.add(self.__thickness * ext_Vec)
      #Part.show(Part.makeLine(faceMiddle, faceMiddle + 2*ext_Vec), 'faceMiddle'+str(face_idx))
      
      counterFaceList = []
      gotCFace = False
      # search for the counter face
      for i in such_list:
        counter_found = True
        for F_vert in self.f_list[i].Vertexes:
          vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
          dist_v = vF_vert.distanceToPlane (s_Posi, ext_Vec) - self.__thickness
          # print "counter face distance: ", dist_v + self.__thickness
          #print 'checking Face', str(i+1), ' dist_v: ', dist_v
          if (dist_v > self.cFaceTol) or (dist_v < -self.cFaceTol):
              counter_found = False
  
        if counter_found:
          # need a mean point of the face to avoid false counter faces
          counterMiddle = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
          for Vvec in self.__Shape.Faces[i].OuterWire.Vertexes:
              counterMiddle = counterMiddle.add(Vvec.Point)
          counterMiddle = counterMiddle.multiply(1.0/len(self.__Shape.Faces[i].OuterWire.Vertexes))
          
          distVector = counterMiddle.sub(faceMiddle)
          counterDistance = distVector.Length
          
          if counterDistance < 2*self.__thickness: # small stripes are a risk, fix me!
            FreeCAD.Console.PrintLog( "found counter-face"+ str(i + 1) + "\n")
            counterFaceList.append([i, counterDistance])
            gotCFace = True
          else:
            counter_found = False
            FreeCAD.Console.PrintLog("faceMiddle: " + str(faceMiddle) + " counterMiddle: "+ str(counterMiddle) + "\n")
      
      if gotCFace:
        newNode.c_face_idx = counterFaceList[0][0]
        if len(counterFaceList) > 1: # check if more than one counterFace was detected!
          counterDistance = counterFaceList[0][1]
          for i in range(1,len(counterFaceList)):
            if counterDistance > counterFaceList[i][1]:
              counterDistance = counterFaceList[i][1]
              newNode.c_face_idx = counterFaceList[i][0]
        self.index_list.remove(newNode.c_face_idx)
        newNode.nfIndexes.append(newNode.c_face_idx)

            
      #if newNode.c_face_idx == None:
      #  Part.show(axis_line)
      # if the parent is a bend: check the bend angle and correct it.
      if newNode.p_node:
        if newNode.p_node.node_type == 'Bend':
          if newNode.p_node.p_node.node_type == 'Flat':
            # calculate the angle on base of ext_Vec
            ppVec = newNode.p_node.p_node.axis # normal of the flat face
            myVec = newNode.axis # normal of the flat face
            theAxis = newNode.p_node.axis # Bend axis
            angle = math.atan2(ppVec.cross(myVec).dot(theAxis), ppVec.dot(myVec))
            if angle < -math.pi/8:
              angle = angle + 2*math.pi
            #print 'compare angles, bend: ', newNode.p_node.bend_angle, ' ', angle
            newNode.p_node.bend_angle = angle # This seems to be an improvement!
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
          rotatedFace.rotate(self.f_list[newNode.p_node.idx].Surface.Center,newNode.p_node.axis,math.degrees(-newNode.p_node.bend_angle))
          rotatedFace.translate(trans_vec)

          for vKey in newNode.p_node.vertexDict:
            flagStr, origVec, unbendVec = newNode.p_node.vertexDict[vKey]
            #for theVert in myFlatVerts:
            for vertIdx in myFlatVertIndexes:
              theVert = self.__Shape.Faces[face_idx].Vertexes[vertIdx]
              if equal_vector(theVert.Point, origVec):
                flagStr = flagStr + 'c'
                newNode.p_node.vertexDict[vKey] = flagStr, origVec, rotatedFace.Vertexes[vertIdx].Point

          # update the newNode.p_node.vertexDict with the Vertex data
          # from the own vertexes corresponding to the opposite face
          oppVertIndexes = range(len(self.__Shape.Faces[newNode.c_face_idx].Vertexes))
          myFlatVertIndexes = []
          # for theVert in self.__Shape.Faces[face_idx].Vertexes:
          for vertIdx in oppVertIndexes:
            theVert = self.__Shape.Faces[newNode.c_face_idx].Vertexes[vertIdx]
            for cVert in self.__Shape.Faces[newNode.p_node.c_face_idx].Vertexes:
              if equal_vertex(theVert, cVert):
                myFlatVertIndexes.append(vertIdx)
              
          rotatedFace = self.f_list[newNode.c_face_idx].copy()
          trans_vec = newNode.p_node.tan_vec * newNode.p_node._trans_length
          rotatedFace.rotate(self.f_list[newNode.p_node.idx].Surface.Center,newNode.p_node.axis,math.degrees(-newNode.p_node.bend_angle))
          rotatedFace.translate(trans_vec)

          for vKey in newNode.p_node.vertexDict:
            flagStr, origVec, unbendVec = newNode.p_node.vertexDict[vKey]
            #for theVert in myFlatVerts:
            for vertIdx in myFlatVertIndexes:
              theVert = self.__Shape.Faces[newNode.c_face_idx].Vertexes[vertIdx]
              if equal_vector(theVert.Point, origVec):
                flagStr = flagStr + 'c'
                newNode.p_node.vertexDict[vKey] = flagStr, origVec, rotatedFace.Vertexes[vertIdx].Point


    if F_type == "<Cylinder object>":
      newNode.node_type = 'Bend' # fixme
      s_Center = self.__Shape.Faces[face_idx].Surface.Center
      s_Axis = self.__Shape.Faces[face_idx].Surface.Axis
      newNode.axis = s_Axis
      newNode.bendCenter = s_Center
      edge_vec = P_edge.Vertexes[0].copy().Point
      FreeCAD.Console.PrintLog("edge_vec: "+ str(edge_vec) + "\n")
      
      if P_node.node_type == 'Flat':
        dist_c = edge_vec.distanceToPlane (s_Center, P_node.axis) # distance to center
      else:
        P_face = self.__Shape.Faces[P_node.idx]
        radVector = radial_vector(edge_vec, P_face.Surface.Center, P_face.Surface.Axis)
        if P_node.bend_dir == "down":
          dist_c = edge_vec.distanceToPlane (s_Center, radVector.multiply(-1.0))
        else:
          dist_c = edge_vec.distanceToPlane (s_Center, radVector)
          
      if dist_c < 0.0:
        newNode.bend_dir = "down"
        thick_test = self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness
        newNode.innerRadius = thick_test
      else:
        newNode.bend_dir = "up"
        thick_test = self.__Shape.Faces[face_idx].Surface.Radius + self.__thickness
        newNode.innerRadius = self.__Shape.Faces[face_idx].Surface.Radius
      newNode.distCenter = thick_test
      # print "Face idx: ", face_idx, " bend_dir: ", newNode.bend_dir
      FreeCAD.Console.PrintLog("Face" + str(face_idx+1) + " Type: " + str(newNode.node_type)+ " bend_dir: "+ str(newNode.bend_dir) + "\n")


      # calculate mean point of face:
      # fixme implement also for cylindric faces

      # Search the face at the opposite site of the sheet:
      #for i in range(len(such_list)):
      for i in such_list:
        counter_found = True
        for F_vert in self.f_list[i].Vertexes:
          vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
          dist_c = vF_vert.distanceToLine (s_Center, s_Axis) - thick_test
          if (dist_c > self.cFaceTol) or (dist_c < -self.cFaceTol):
            counter_found = False
  
        if counter_found:
          # to do calculate mean point of counter face

          #print "found counter Face", such_list[i]+1
          newNode.c_face_idx = i
          self.index_list.remove(i)
          newNode.nfIndexes.append(i)
          # Part.show(self.__Shape.Faces[newNode.c_face_idx])
          break

      if not counter_found:
        newNode.analysis_ok = False
        newNode.error_code = 13 # Analysis: counter face not found
        self.error_code = 13
        self.failed_face_idx = face_idx
        FreeCAD.Console.PrintLog("No opposite face Debugging Thickness: "+ str(self.__thickness) + "\n")
        Part.show(self.__Shape.Faces[face_idx], 'FailedFace'+ str(face_idx + 1) +'_')
        return newNode

        
      else:
        # Need a Vertex from the parent node on the opposite side of the 
        # sheet metal part. This vertex is used to align other vertexes
        # to the unbended sheet metal plane.
        # The used vertex should be one of the opposite Face of the parent
        # node with the closest distance to a line through edge_vec.
        if P_node.node_type == 'Flat':
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
        #Part.show(Part.makeLine(bestPoint, edge_vec), 'bestPoint'+str(face_idx+1)+'_')
        
        self.getBendAngle(newNode, wires_e_lists)
              
         # As I have learned, that it is necessary to apply corrections to Points / Vertexes,
        # it will be difficult to have all vertexes of the faces of a bend to fit together.
        # Therefore a dictionary is introduced, which holds the original coordinates and
        # the unbend coordinates for the vertexes of the bend. It contains also flags,
        # indicating if a point is part of the parent node (p) or child node (c), top face (t) or
        # opposite face (o). All in newNode.vertexDict
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
        vertDictIdx = 0 # Index as key in newNode.vertexDict
        for theVert in self.__Shape.Faces[face_idx].Vertexes:
          flagStr = 't'
          origVec = theVert.Point
          unbendVec = None
          if equal_vertex(theVert, P_edge.Vertexes[0]):
            flagStr = flagStr + 'p0'
            origVec = P_edge.Vertexes[0].Point
            unbendVec = origVec
          else:
            if equal_vertex(theVert, P_edge.Vertexes[1]):
              flagStr = flagStr + 'p1'
              origVec = P_edge.Vertexes[1].Point
              unbendVec = origVec
          #print('make vertexDict: ', flagStr, ' ', str(face_idx+1))
          newNode.vertexDict[vertDictIdx] = flagStr, origVec, unbendVec
          vertDictIdx += 1
  
        for theVert in self.__Shape.Faces[newNode.c_face_idx].Vertexes:
          flagStr = 'o'
          origVec = theVert.Point
          unbendVec = None
          for pVert in self.__Shape.Faces[P_node.c_face_idx].Vertexes:
            if equal_vertex(theVert, pVert):
              flagStr = flagStr + 'p'
              origVec = pVert.Point
              unbendVec = origVec
          #print('make vertexDict: ', flagStr, ' ', str(face_idx+1))
          newNode.vertexDict[vertDictIdx] = flagStr, origVec, unbendVec
          vertDictIdx += 1
      
    # Part.show(self.__Shape.Faces[newNode.c_face_idx])
    # Part.show(self.__Shape.Faces[newNode.idx])
    if newNode.c_face_idx is None:
      newNode.analysis_ok = False
      newNode.error_code = 13 # Analysis: counter face not found
      self.error_code = 13
      self.failed_face_idx = face_idx
      FreeCAD.Console.PrintLog("No counter-face Debugging Thickness: "+ str(self.__thickness) + "\n")
      Part.show(self.__Shape.Faces[face_idx], 'FailedFace'+ str(face_idx + 1) +'_')




    # now we call the new code
    self.get_node_faces(newNode, wires_e_lists)
    #for nFace in newNode.nfIndexes:
    #  Part.show(nFace)


    if P_node is None:
      self.root = newNode
    else:
      P_node.child_list.append(newNode)
    return newNode



  def Bend_analysis(self, face_idx, parent_node = None, parent_edge = None):
    # This functions traverses the shape in order to build the bend-tree
    # For each relevant face a t_node is created and linked into the tree
    # the linking is done in the call of self.make_new_face_node
    #print "Bend_analysis Face", face_idx +1 ,
    # analysis_ok = True # not used anymore? 
    # edge_list = []
    if self.error_code is None:
      wires_edge_lists = []
      wire_idx = -1
      for n_wire in self.f_list[face_idx].Wires:
        wire_idx += 1
        wires_edge_lists.append([])
        #for n_edge in self.__Shape.Faces[face_idx].Edges:
        for n_edge in n_wire.Edges:
          if parent_edge:
            if not parent_edge.isSame(n_edge):
              #edge_list.append(n_edge)
              wires_edge_lists[wire_idx].append(n_edge)
            #
          else:
            #edge_list.append(n_edge)
            wires_edge_lists[wire_idx].append(n_edge)
      if parent_node:
        FreeCAD.Console.PrintLog(" Parent Face" + str(parent_node.idx + 1) + "\n")
      FreeCAD.Console.PrintLog("The list: "+ str(self.index_list) + "\n")
      t_node = self.make_new_face_node(face_idx, parent_node, parent_edge, wires_edge_lists)
      # Need also the edge_list in the node!
      FreeCAD.Console.PrintLog("The list after make_new_face_node: " + str(self.index_list) + "\n")
      
      # in the new code, only the list of child faces will be analyzed.
      removalList = []
      for child_info in t_node.child_idx_lists:
        if child_info[0] in self.index_list:
          FreeCAD.Console.PrintLog("child in list: "+ str(child_info[0]) + "\n")
          self.Bend_analysis(child_info[0], t_node, child_info[1])
        else:
          FreeCAD.Console.PrintLog("remove child from List: " + str(child_info[0]) + "\n")
          t_node.seam_edges.append(child_info[1]) # give Information to the node, that it has a seam.
          FreeCAD.Console.PrintLog("node faces before: " + str(t_node.nfIndexes) + "\n")
          # do not make Faces at a detected seam!
          # self.makeSeamFace(child_info[1], t_node)
          removalList.append(child_info)
          FreeCAD.Console.PrintLog("node faces with seam: "+ str(t_node.nfIndexes) + "\n")
          otherSeamNode = self.searchNode(child_info[0], self.root)
          FreeCAD.Console.PrintLog("counterface on otherSeamNode: Face" + str(otherSeamNode.c_face_idx+1) + "\n")
          # do not make Faces at a detected seam!
          # self.makeSeamFace(child_info[1], otherSeamNode)
      for seams in removalList:
        t_node.child_idx_lists.remove(seams)
    else:
      FreeCAD.Console.PrintError('got error code: '+ str(self.error_code) + ' at Face'+ str(self.failed_face_idx+1) + "\n")
      

  
  
  def searchNode(self, theIdx, sNode):
    # search for a Node with theIdx in sNode.idx
    FreeCAD.Console.PrintLog("my Idx: "+ str(sNode.idx) + "\n")

    if sNode.idx == theIdx:
      return sNode
    else:
      result = None
      childFaces = []
      for n_node in sNode.child_list:
        childFaces.append(n_node.idx)
      FreeCAD.Console.PrintLog("my children: "+ str(childFaces) + "\n")
      
      for n_node in sNode.child_list:
        nextSearch = self.searchNode(theIdx, n_node)
        if nextSearch is not None:
          result = nextSearch
          break
    if result is not None:
      FreeCAD.Console.PrintLog("This is the result: "+ str(result.idx) + "\n")
    else:
      FreeCAD.Console.PrintLog("This is the result: None\n")
    
    return result
    
    # suche bei mir. wenn ja liefere ab
    # sonst sind Kinder da?
    # Wenn Kinder vorhanden, frag solange Kinder bis gefunden
    # oder kein Kind mehr da.


  def rotateVec(self, vec, phi, rAxis):
    ''' rotate a vector by the angle phi around the axis rAxis'''
    #https://de.wikipedia.org/wiki/Drehmatrix
    rVec = rAxis.cross(vec).cross(rAxis).multiply(math.cos(phi)) + rAxis.cross(vec)*math.sin(phi) + rAxis*rAxis.dot(vec) 
    return rVec


  def unbendFace(self, fIdx, bend_node, nullVec, mode = 'side'):
    '''
    The self.vertexDict requires a further data structure to hold for
    each edge in a list the point indexes to the vertexes of the bend node.
    key: Index to myEdgeList, content: List of indexes to the self.vertexDict.
    '''
    
    axis = bend_node.axis
    cent = bend_node.bendCenter
    bRad = bend_node.innerRadius
    thick = self.__thickness
    
    kFactor = bend_node.k_Factor
    
    transRad = bRad + kFactor * thick
    if kFactorStandard == 'din':
        conv = ', converted from DIN'
    else:
        conv = '' 
    SMMessage("transRad Face: %d, r: %.2f, thickness: %.2f, K-factor: %.2f (ANSI%s)" % (fIdx+1, bRad, thick, kFactor, conv))
    tanVec = bend_node.tan_vec
    aFace = self.f_list[fIdx]
    
    normVec = radial_vector(bend_node.p_edge.Vertexes[0].Point, cent, axis)
    
    if mode == 'top':
      chord = cent.sub(bend_node.p_edge.Vertexes[0].Point)
      norm = axis.cross(chord)
      compRadialVec = axis.cross(norm)


    if mode == 'counter':
      chord = cent.sub(bend_node.oppositePoint)
      norm = axis.cross(chord)
      compRadialVec = axis.cross(norm)


    def unbendPoint(poi):
      radVec = radial_vector(poi, cent, axis)
      angle = math.atan2(nullVec.cross(radVec).dot(axis), nullVec.dot(radVec))
      #print 'point Face', str(fIdx+1), ' ', angle
      if angle < -math.pi/8:
        angle = angle + 2*math.pi
      rotVec = self.rotateVec(poi.sub(cent), -angle, axis)
      #print 'point if Face', str(fIdx+1), ' ', angle, ' ', transRad*angle
      if (mode == 'top') or (mode == 'counter'):
        chord = cent.sub(cent + rotVec)
        norm = axis.cross(chord)
        correctionVec = compRadialVec.sub(axis.cross(norm))
        #correctionVec = axis.cross(norm).sub(compRadialVec)
        #print 'origVec ', axis.cross(norm), ' compRadialVec ', compRadialVec
        bPoint = cent + rotVec + correctionVec + tanVec*transRad*angle
      else:
        bPoint = cent + rotVec + tanVec*transRad*angle
      
      return bPoint
    
    divisions = 12 # fix me! need a dependence on something useful.
    
    
    fWireList = aFace.Wires[:]
    #newWires = []
    edgeLists = []

    for aWire in fWireList:
        uEdge = None
        idxList, closedW = self.sortEdgesTolerant(aWire.Edges)
        #print('Wire', str(fIdx+1), ' has ', len(idxList), ' edges, closed: ', closedW)
        
        eList = []  # is the list of unbend edges
        j=0
        for fEdgeIdx in idxList:
          fEdge = aWire.Edges[fEdgeIdx]
          eType = str(fEdge.Curve)
          vertexCount = len(fEdge.Vertexes)
          #print "the type of curve: ", eType
          vert0 = None
          vert1 = None
          flags0 = None
          flags1 = None
          uVert0 = None
          uVert1 = None
          edgeKey = None
          vert0Idx = None
          vert1Idx = None
          
          #print 'edge vertexes: ', str(fIdx+1), ' ', mode, ' ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point
          for oVertIdx in bend_node.vertexDict:
            flagStr, origVec, unbendVec = bend_node.vertexDict[oVertIdx]
            #print 'origVec: ', origVec
            if equal_vector(fEdge.Vertexes[0].Point, origVec,5):
              vert0Idx = oVertIdx
              flags0 = flagStr
              uVert0 = unbendVec
            if vertexCount > 1:
              if equal_vector(fEdge.Vertexes[1].Point, origVec,5):
                vert1Idx = oVertIdx
                flags1 = flagStr
                uVert1 = unbendVec
            # can we break the for loop at some condition?
          # Handle cases, where a side face has additional vertexes
          if mode == 'side':
            if vert0Idx is None:
              vert0Idx = len(bend_node.vertexDict)
              #print('got additional side vertex0: ', vert0Idx, ' ', fEdge.Vertexes[0].Point)
              flags0 = ''
              origVec = fEdge.Vertexes[0].Point
              uVert0 = unbendPoint(origVec)
              bend_node.vertexDict[vert0Idx] = flags0, origVec, uVert0
            if vertexCount >1:
              if vert1Idx is None:
                vert1Idx = len(bend_node.vertexDict)
                #print('got additional side vertex1: ', vert1Idx, ' ', fEdge.Vertexes[1].Point)
                flags1 = ''
                origVec = fEdge.Vertexes[1].Point
                uVert1 = unbendPoint(origVec)
                bend_node.vertexDict[vert1Idx] = flags1, origVec, uVert1


          # make the key for bend_node.edgeDict, shift vert1 and add both.
          if vert0Idx is None:
            #print 'catastrophy: ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point, ' ', eType
            Part.show(fEdge, 'catastrophyEdge')
            # fix me, need proper failure mode.
          if vert1Idx:
            if vert1Idx < vert0Idx:
              edgeKey = vert0Idx + (vert1Idx << 8)
            else:
              edgeKey = vert1Idx + (vert0Idx << 8)
            # x << n: x shifted left by n bits = Multiplication
          else:
            edgeKey = vert0Idx
            
          #print 'edgeKey: ', edgeKey, ' ', str(fIdx+1), ' ', mode, ' ', uVert0, ' ', uVert1
          
          urollPts = []
          
          if ("<Ellipse object>" in eType):
            minPar, maxPar = fEdge.ParameterRange
            FreeCAD.Console.PrintLog("the Parameterrange: "+ str(minPar)+ " to " + str(maxPar)+ " Type: "+str(eType) + "\n")
            
            # compare minimal 1/curvature with curve-lenght to decide on division
            iMulti = (maxPar-minPar)/24
            maxCurva = 0.0
            for i in range(24):
              posi = fEdge.valueAt(minPar + i*iMulti)
              # print 'testEdge ', i, ' curva: ' , testEdge.Curve.curvature(minPar + i*iMulti)
              curva = fEdge.Curve.curvature(minPar + i*iMulti)
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
            
            iMulti = (maxPar-minPar)/eDivisions
            urollPts.append(uVert0)
            for i in range(1,eDivisions):
              posi = fEdge.valueAt(minPar + i*iMulti)
              bPosi = unbendPoint(posi)
              urollPts.append(bPosi)
            urollPts.append(uVert1)
            
            uCurve = Part.BSplineCurve()
            uCurve.interpolate(urollPts)
            uEdge = uCurve.toShape()
            #Part.show(uEdge, 'Elli'+str(j)+'_')
     
          elif "<Line" in eType:
            #print 'j: ',j , ' eType: ', eType, ' fIdx: ', fIdx, ' verts: ', fEdge.Vertexes[0].Point, ' ', fEdge.Vertexes[1].Point
            #Part.show(fEdge)
            #print 'unbend Line: ', uVert0, ' ', uVert1
            uEdge = Part.makeLine(uVert0, uVert1)
            #Part.show(uEdge, 'Line'+str(j)+'_')
    
          elif "Circle" in eType:  #fix me! need to check if circle ends are at different radii!
            FreeCAD.Console.PrintLog('j: '+ str(j) + ' eType: '+ str(eType) + '\n')
            parList = fEdge.ParameterRange
            #print "the Parameterrange: ", parList[0], " , ", parList[1], " Type: ",eType
            #axis_line = Part.makeLine(cent, cent + axis)
            #Part.show(axis_line, 'axis_line'+ str(bend_node.idx+1)+'_')
            #print 'Face', str(bend_node.idx+1), 'bAxis: ', axis, ' cAxis: ', fEdge.Curve.Axis
            uEdge = Part.makeLine(uVert0, uVert1)
            #Part.show(uEdge, 'CircleLine'+str(j)+'_')
    
          elif ("<BSplineCurve object>" in eType) or ("<BezierCurve object>" in eType):
            minPar, maxPar = fEdge.ParameterRange
            #print "the Parameterrange: ", minPar, " - ", maxPar, " Type: ",eType
            
            # compare minimal 1/curvature with curve-lenght to decide on division
            iMulti = (maxPar-minPar)/24
            maxCurva = 0.0
            testPts = []
            for i in range(24+1):
              posi = fEdge.valueAt(minPar + i*iMulti)
              bPosi = unbendPoint(posi)
              testPts.append(bPosi)
            testCurve = Part.BSplineCurve()
            testCurve.interpolate(testPts)
            testEdge = testCurve.toShape()

            for i in range(24+1):
              posi = testEdge.valueAt(minPar + i*iMulti)
              # print 'testEdge ', i, ' curva: ' , testEdge.Curve.curvature(minPar + i*iMulti)
              curva = testEdge.Curve.curvature(minPar + i*iMulti)
              if curva > maxCurva:
                maxCurva = curva
            
            decisionAngle = testEdge.Length * maxCurva
            #print 'Face', str(fIdx+1), ' decisionAngle: ', decisionAngle
            #Part.show(testEdge, 'deciAng'+str(decisionAngle)+ '_')
            
            if decisionAngle > 1000.0:
              bDivisions = 4
            else:
              bDivisions = 12

            iMulti = (maxPar-minPar)/bDivisions
            if vertexCount > 1:
              urollPts.append(uVert0)
              for i in range(1,bDivisions):
                posi = fEdge.valueAt(minPar + i*iMulti)
                # curvature is 1/radius
                #print 'Face', str(fIdx+1), ' 1/Curvature: ', 1/fEdge.Curve.curvature(minPar + i*iMulti), ' ', fEdge.Length
                bPosi = unbendPoint(posi)
                urollPts.append(bPosi)
              urollPts.append(uVert1)
            else:
              urollPts.append(uVert0)
              for i in range(1,bDivisions):
                posi = fEdge.valueAt(minPar + i*iMulti)
                bPosi = unbendPoint(posi)
                urollPts.append(bPosi)
              urollPts.append(uVert0)
            #testPoly = Part.makePolygon(urollPts)
            #Part.show(testPoly, 'testPoly'+ str(fIdx+1) + '_')
            uCurve = Part.BSplineCurve()
            try:
              uCurve.interpolate(urollPts)
              uEdge = uCurve.toShape()
              #Part.show(theCurve, 'B_spline')
            except:
              #uEdge =  Part.makeLine(urollPts[0], urollPts[-1])
              if bDivisions == 4:
                uCurve.interpolate([urollPts[0], urollPts[2], urollPts[-1]])
              if bDivisions == 12:
                uCurve.interpolate([urollPts[0],urollPts[3],urollPts[6],urollPts[9], urollPts[-1]])
              uEdge = uCurve.toShape()
          else:
            #print 'unbendFace, curve type not handled: ' + str(eType) + ' in Face' + str(fIdx+1)
            FreeCAD.Console.PrintLog('unbendFace, curve type not handled: ' + str(eType) + ' in Face' + str(fIdx+1) + '\n')
            self.error_code = 26
            self.failed_face_idx = fIdx
          
          # in mode 'side' check, if not the top or counter edge can be used instead.
          if mode == 'side':
            if edgeKey in bend_node.edgeDict:
              uEdge = bend_node.edgeDict[edgeKey]
              #print 'found key in node.edgeDict: ', edgeKey, ' in mode: ', mode
          #Part.show(uEdge, 'bendEdge'+str(fIdx+1)+'_')
          eList.append(uEdge)
          if not (edgeKey in bend_node.edgeDict):
            bend_node.edgeDict[edgeKey] = uEdge
            #print 'added key: ', edgeKey, ' to edgeDict in mode: ', mode
          j += 1
        edgeLists.append(eList)
    # end of for what?
    
    # Here we store the unbend top and counter outer edge list in the node data.
    # These are needed later as edges in the new side faces. 
    if mode == 'top':
      bend_node.unfoldTopList = edgeLists[0]
    if mode == 'counter':
      bend_node.unfoldCounterList = edgeLists[0]
    
    
    if len(edgeLists) == 1:
      eList = Part.__sortEdges__(edgeLists[0])
      myWire = Part.Wire(eList)
      FreeCAD.Console.PrintLog('len eList: '+ str(len(eList)) + '\n')
      #Part.show(myWire, 'Wire_Face'+str(fIdx+1)+'_' )
      if (len(myWire.Vertexes) == 2) and (len(myWire.Edges) == 3):
        #print 'got sweep condition!'
        pWire = Part.Wire(myWire.Edges[1])
        fWire = Part.Wire(myWire.Edges[0]) # first sweep profile
        lWire = Part.Wire(myWire.Edges[2]) # last sweep profile
        theFace = pWire.makePipeShell([fWire, lWire], False, True)
        theFace = theFace.Faces[0]
        #Part.show(theFace, 'Loch')
      else:
        try:
            #Part.show(myWire, 'myWire'+ str(bend_node.idx+1)+'_')
            theFace = Part.Face(myWire)
            #theFace = Part.makeFace(myWire, 'Part::FaceMakerSimple')
        except:
            FreeCAD.Console.PrintLog('got exception at Face: '+ str(fIdx+1) +' len eList: '+ str(len(eList)) + '\n')
            #for w in eList:
              #Part.show(w, 'exceptEdge')
              #print 'exception type: ', str(w.Curve)
            #Part.show(myWire, 'exceptionWire'+ str(fIdx+1)+'_')
            secWireList = myWire.Edges[:]
            thirdWireList = Part.__sortEdges__(secWireList)
            theFace = Part.makeFilledFace(thirdWireList)
        #Part.show(theFace, 'theFace'+ str(bend_node.idx+1)+'_')
    else:
      FreeCAD.Console.PrintLog('len edgeLists: '+ str(len(edgeLists))+'\n')
      faces = []
      wires = []
      wireNumber = 0
      for w in edgeLists:
        eList = Part.__sortEdges__(w)
        #print 'eList: ', eList
        if wireNumber < 0:
          #myWire = Part.Wire(eList.reverse())
          reversList = []
          for e in eList:
            reversList.insert(0,e)
          myWire = Part.Wire(reversList)
        else:
          myWire = Part.Wire(eList)
        #Part.show(myWire, 'myWire'+ str(bend_node.idx+1)+'_')
        nextFace = Part.Face(myWire)
        faces.append(nextFace)
        wires.append(myWire)
        wireNumber += 1
        #Part.show(Part.Face(myWire))
      try:
          #theFace = Part.Face(wires)
          #print 'make cutted face\n' 
          theFace = faces[0].copy()
          for f in faces[1:]:
            f.translate(-normVec)
            cutter= f.extrude(2*normVec)
            theFace = theFace.cut(cutter)
            theFace = theFace.Faces[0]
          #Part.show(theFace, 'theFace')
          #theFace = Part.Face(wires[0], wires[1:])
          #theFace = Part.makeFace(myWire, 'Part::FaceMakerSimple')
      except Exception as e:
          #theFace = Part.makeFilledFace(wires)
          theFace = faces[0]
          SMError('got execption: ', str(e))
          #Part.show(theFace, 'exception')
    keyList = []
    for key in bend_node.edgeDict:
      keyList.append(key)
    #print 'edgeDict keys: ', keyList
    #Part.show(theFace, 'unbendFace'+str(fIdx+1))
    return theFace

  def sortEdgesTolerant(self, myEdgeList):
    '''
    sort edges from an existing wire.
    returns:
      a new sorted list of indexes to edges of the original wire
      flag if wire is closed or not (a wire of a cylinder mantle is not closed!)
    '''
    eIndex = 0 
    newEdgeList = []
    idxList = list(range(len(myEdgeList)))
    newIdxList = [eIndex]
    newEdgeList.append(myEdgeList[eIndex])
    idxList.remove(eIndex)
    gotConnection = False
    closedWire = False
    
    startVert  = myEdgeList[eIndex].Vertexes[0]
    if len(myEdgeList[eIndex].Vertexes) > 1:
      vert = myEdgeList[eIndex].Vertexes[1]
    else:
      vert = myEdgeList[eIndex].Vertexes[0]
    #Part.show(myEdgeList[0], 'tolEdge'+str(1)+'_')
    while not gotConnection:
      for eIdx in idxList:
        edge = myEdgeList[eIdx]
        if equal_vertex(vert, edge.Vertexes[0]):
          idxList.remove(eIdx)
          eIndex = eIdx
          #print 'found eIdx: ', eIdx
          newIdxList.append(eIdx)
          if len(edge.Vertexes) > 1:
            vert = edge.Vertexes[1]
          break
        if len(edge.Vertexes) > 1:
          if equal_vertex(vert, edge.Vertexes[1]):
            idxList.remove(eIdx)
            eIndex = eIdx
            #print 'found eIdx: ', eIdx
            newIdxList.append(eIdx)
            vert = edge.Vertexes[0]
            break
      if (len(idxList) == 0):
        gotConnection = True 
      if equal_vertex(vert, startVert):
        #print 'got last connection'
        gotConnection = True
        closedWire = True
      #Part.show(myEdgeList[eIdx], 'tolEdge'+str(eIdx+1)+'_')
    #print 'tolerant wire: ', len(myEdgeList)
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
    bLinePoint0 = theFace.valueAt(halfAngle,length_0)
    #bLinePoint1 = theFace.valueAt(halfAngle,length_1)
    normVec = radial_vector(bLinePoint0, cent, axis)
    sliceVec = normVec.cross(axis)
    origin = Base.Vector(0.0,0.0,0.0)
    distance = origin.distanceToPlane(bLinePoint0, sliceVec)
    testDist = -bLinePoint0.distanceToPlane(sliceVec * distance, sliceVec)
    if math.fabs(testDist) > math.fabs(distance):
      sliceVec = -sliceVec
    
    
    #Part.show(Part.makePolygon([origin,sliceVec * distance]), 'distance') 
    #print 'distance: ', distance, ' testDist: ', testDist
    wires = []
    for i in theFace.slice(sliceVec, distance):
      wires.append(i)
    #print 'got ', len(wires), ' wires'
    #Part.show(Part.Compound(wires), 'slice')
    theComp = Part.Compound(wires)
    # fix me, what if there are no wires?
    wireList =[]
     
    for fEdge in theComp.Edges:
      eType = str(fEdge.Curve)
      #print "the type of curve: ", eType
      urollPts = []

      if "<Line" in eType:
        for lVert in fEdge.Vertexes:
          posi = lVert.Point
          radVec = radial_vector(posi, cent, axis)
          angle = math.atan2(nullVec.cross(radVec).dot(axis), nullVec.dot(radVec))
          if angle < 0:
            angle = angle + 2*math.pi
          rotVec = self.rotateVec(posi.sub(cent), -angle, axis)
          
          bPosi = cent + rotVec + tanVec*transRad*angle
          
          urollPts.append(bPosi)
        edgeL = Part.makeLine(urollPts[0], urollPts[1])
        lWire = Part.Wire([edgeL])
        wireList.append(edgeL)
        #Part.show(lWire, 'foldLine'+str(bend_node.idx +1)+'_')
      else:
        print('fix me! make errorcondition')
        
    return wireList
  
  def unbendVertDict(self, bend_node, cent, axis, nullVec):
    '''
    calculate the unbend points in the vertexDict.
    This is called with the vertexes of the top and the opposite face only.
    '''
    def unbendDictPoint(poi, compRadialVec):
      radVec = radial_vector(poi, cent, axis)
      angle = math.atan2(nullVec.cross(radVec).dot(axis), nullVec.dot(radVec))
      #print 'point Face', str(fIdx+1), ' ', angle
      if angle < -math.pi/8:
        angle = angle + 2*math.pi
      rotVec = self.rotateVec(poi.sub(cent), -angle, axis)
      chord = cent.sub(cent + rotVec)
      norm = axis.cross(chord)
      correctionVec = compRadialVec.sub(axis.cross(norm))
      #print 'origVec ', axis.cross(norm), ' compRadialVec ', compRadialVec
      bPoint = cent + rotVec + correctionVec + tanVec*transRad*angle
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
      if (not ('p' in flagStr)) and (not ('c' in flagStr)):
        if 't' in flagStr:
          unbendVec = unbendDictPoint(origVec, topCompRadialVec)
        else:
          unbendVec = unbendDictPoint(origVec, oppCompRadialVec)
        #print 'unbendDictPoint for ', flagStr
        bend_node.vertexDict[i] = flagStr, origVec, unbendVec
        
    #for i in bend_node.vertexDict:
      #flagStr, origVec, unbendVec = bend_node.vertexDict[i]
      #print 'vDict Face', str(bend_node.idx+1), ' ', i, ' ', flagStr, ' ', origVec, ' ', unbendVec
          
  def generateBendShell2(self, bend_node):
    '''
    This function takes a cylindrical bend part of sheet metal and 
    returns a flat version of that bend part.
    '''
    theCenter = bend_node.bendCenter   # theCyl.Surface.Center
    theAxis = bend_node.axis           # theCyl.Surface.Axis
    # theRadius = theCyl.Surface.Radius # need to include the k-Factor
    
    zeroVert = bend_node.p_edge.Vertexes[0]
    nullVec = radial_vector(zeroVert.Point, theCenter, theAxis)
    #nullVec_line = Part.makeLine(theCenter, theCenter + nullVec*bend_node.innerRadius)
    #Part.show(nullVec_line, 'nullVec_line'+ str(bend_node.idx+1)+'_')
    #tanVec_line = Part.makeLine(zeroVert.Point, zeroVert.Point + bend_node.tan_vec*bend_node.innerRadius)
    #Part.show(tanVec_line, 'tanVec_line'+ str(bend_node.idx+1)+'_')
    
    # calculate the unbend points in the bend_ node.vertexDict
    self.unbendVertDict(bend_node, theCenter, theAxis, nullVec)
    
    
    bendFaceList = bend_node.nfIndexes[:]
    bendFaceList.remove(bend_node.idx)
    bendFaceList.remove(bend_node.c_face_idx)
    
    flat_shell = []
    flat_shell.append(self.unbendFace(bend_node.idx, bend_node, nullVec, 'top'))
    flat_shell.append(self.unbendFace(bend_node.c_face_idx, bend_node, nullVec, 'counter'))
    
    
    for i in bendFaceList:
      bFace = self.unbendFace(i, bend_node, nullVec)
      flat_shell.append(bFace)
      #Part.show(bFace, 'bFace'+str(i +1))
      #for v in bFace.Vertexes:
      #  print 'Face'+str(i+1) + ' ' + str(v.X) + ' ' + str(v.Y) + ' ' + str(v.Z)

    foldwires = self.makeFoldLines(bend_node, nullVec)
    #print 'face idx: ', bend_node.idx +1, ' folds: ', foldwires
    return flat_shell, foldwires


  def makeSeamFace(self, sEdge, theNode):
    ''' This function creates a face at a seam of the sheet metal.
    It works currently only at a flat node.
    '''
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
        if len(theEdge.Vertexes)>1:
          if equal_vertex(theEdge.Vertexes[0], nextVert):
            next_idx = 1
          if equal_vertex(theEdge.Vertexes[1], nextVert):
            next_idx = 0
          if next_idx is not None:
            if self.isVertOpposite(theEdge.Vertexes[next_idx], theNode):
              nextEdge = theEdge.copy()
              search_List.remove(i)
              the_index = i
              #Part.show(nextEdge)
              break
            else:
              next_idx = None
      if the_index is not None:
        break

    #find the lastEdge
    last_idx = None
    FreeCAD.Console.PrintLog("This is the search_List: "+ str(search_List) + "\n")
    for i in search_List:
      #Part.show(self.f_list[i])
      for theEdge in self.f_list[i].Edges:
        FreeCAD.Console.PrintLog("find last Edge in Face: "+ str(i)+ " at Edge: "+ str(theEdge) + "\n")
        if len(theEdge.Vertexes)>1:
          if equal_vertex(theEdge.Vertexes[0], startVert):
            last_idx = 1
          if equal_vertex(theEdge.Vertexes[1], startVert):
            last_idx = 0
          if last_idx is not None:
            FreeCAD.Console.PrintLog("test for the last Edge\n")
            if self.isVertOpposite(theEdge.Vertexes[last_idx], theNode):
              lastEdge = theEdge.copy()
              search_List.remove(i)
              the_index = i
              #Part.show(lastEdge)
              break
            else:
              last_idx = None
      if last_idx is not None:
        break
        
    # find the middleEdge
    mid_idx = None
    midEdge = None
    for theEdge in self.f_list[theNode.c_face_idx].Edges:
      if len(theEdge.Vertexes)>1:
        if equal_vertex(theEdge.Vertexes[0], nextEdge.Vertexes[next_idx]):
          mid_idx = 1
        if equal_vertex(theEdge.Vertexes[1], nextEdge.Vertexes[next_idx]):
          mid_idx = 0
        if mid_idx is not None:
          if equal_vertex(theEdge.Vertexes[mid_idx], lastEdge.Vertexes[last_idx]):
            midEdge = theEdge.copy()
            #Part.show(midEdge)
            break
          else:
            mid_idx = None
      if midEdge:
        break

    seam_wire = Part.Wire([sEdge, nextEdge, midEdge, lastEdge ])
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
    #print "unfold_tree face", node.idx + 1
    theShell = []
    nodeShell = []
    theFoldLines = []
    nodeFoldLines = []
    for n_node in node.child_list:
      if self.error_code is None:
        shell, foldLines = self.unfold_tree2(n_node)
        theShell = theShell + shell
        theFoldLines = theFoldLines + foldLines
    if node.node_type == 'Bend':
      trans_vec = node.tan_vec * node._trans_length
      for bFaces in theShell:
        bFaces.rotate(self.f_list[node.idx].Surface.Center,node.axis,math.degrees(-node.bend_angle))
        bFaces.translate(trans_vec)
      for fold in theFoldLines:
        fold.rotate(self.f_list[node.idx].Surface.Center,node.axis,math.degrees(-node.bend_angle))
        fold.translate(trans_vec)
      if self.error_code is None:
        #nodeShell = self.generateBendShell(node)
        nodeShell, nodeFoldLines = self.generateBendShell2(node)
    else:
      if self.error_code is None:
        # nodeShell = self.generateShell(node)
        for idx in node.nfIndexes:
          nodeShell.append(self.f_list[idx].copy())
        #if len(node.seam_edges)>0:
        #  for seamEdge in node.seam_edges:
        #    self.makeSeamFace(seamEdge, node)
    FreeCAD.Console.PrintLog("ufo finish face" + str(node.idx +1) + "\n")
    return (theShell + nodeShell, theFoldLines + nodeFoldLines)




def getUnfold(k_factor_lookup):
    resPart = None
    normalVect = None
    folds = None
    theName = None
    mylist = Gui.Selection.getSelectionEx()
    # print 'Die Selektion: ',mylist
    # print 'Zahl der Selektionen: ', mylist.__len__()
    
    if mylist.__len__() == 0:
      mw=FreeCADGui.getMainWindow()
      QtGui.QMessageBox.information(mw,"Error","""One flat face needs to be selected!""")
    else:
      if mylist.__len__() > 1:
        mw=FreeCADGui.getMainWindow()
        QtGui.QMessageBox.information(mw,"Error","""Only one flat face has to be selected!""")
      else:
        o = Gui.Selection.getSelectionEx()[0]
        theName = o.ObjectName
        if len(o.SubObjects)>1:
          mw=FreeCADGui.getMainWindow()
          QtGui.QMessageBox.information(mw,"SubelementError","""Only one flat face has to be selected!""")
        else:
          subelement = o.SubObjects[0]
          if hasattr(subelement,'Surface'):
            s_type = str(subelement.Surface)
            if s_type == "<Plane object>":
              normalVect = subelement.normalAt(0,0)
              mw=FreeCADGui.getMainWindow()
              #QtGui.QMessageBox.information(mw,"Hurra","""Lets try unfolding!""")
              FreeCAD.Console.PrintLog("name: "+ str(subelement) + "\n")
              f_number = int(o.SubElementNames[0].lstrip('Face'))-1
              #print f_number
              startzeit = time.clock()
              TheTree = SheetTree(o.Object.Shape, f_number, k_factor_lookup) # initializes the tree-structure
              if TheTree.error_code is None:
                TheTree.Bend_analysis(f_number, None) # traverses the shape and builds the tree-structure
                endzeit = time.clock()
                FreeCAD.Console.PrintLog("Analytical time: "+ str(endzeit-startzeit) + "\n")
                
                if TheTree.error_code is None:
                  # TheTree.showFaces()
                  theFaceList, foldLines = TheTree.unfold_tree2(TheTree.root) # traverses the tree-structure
                  if TheTree.error_code is None:
                    unfoldTime = time.clock()
                    FreeCAD.Console.PrintLog("time to run the unfold: "+ str(unfoldTime - endzeit) + "\n")
                    folds = Part.Compound(foldLines)
                    #Part.show(folds, 'Fold_Lines')
                    try:
                        newShell = Part.Shell(theFaceList)
                    except:
                        FreeCAD.Console.PrintLog("couldn't join some faces, show only single faces!\n")
                        resPart = Part.Compound(theFaceList)
                        #for newFace in theFaceList:
                          #Part.show(newFace)
                    else:
                      
                      try:
                          TheSolid = Part.Solid(newShell)
                          solidTime = time.clock()
                          FreeCAD.Console.PrintLog("time to make the solid: "+ str(solidTime - unfoldTime) + "\n")
                      except:
                          FreeCAD.Console.PrintLog("couldn't make a solid, show only a shell, Faces in List: "+ str(len(theFaceList)) +"\n")
                          resPart = newShell
                          #Part.show(newShell)
                          showTime = time.clock()
                          FreeCAD.Console.PrintLog("Show time: "+ str(showTime - unfoldTime) + "\n")
                      else:
                        try:
                          cleanSolid = TheSolid.removeSplitter()
                          #Part.show(cleanSolid)
                          resPart = cleanSolid
                          
                        except:
                          #Part.show(TheSolid)
                          resPart = TheSolid
                        showTime = time.clock()
                        FreeCAD.Console.PrintLog("Show time: "+ str(showTime - solidTime) + " total time: "+ str(showTime - startzeit) + "\n")
              
              if TheTree.error_code is not None:
                FreeCAD.Console.PrintError("Error "+ unfold_error[TheTree.error_code] +
                     " at Face"+ str(TheTree.failed_face_idx+1) + "\n")
                QtGui.QMessageBox.information(mw,"Error",unfold_error[TheTree.error_code])
              else:
                FreeCAD.Console.PrintLog("unfold successful\n")
    
                      
            else:
              mw=FreeCADGui.getMainWindow()
              QtGui.QMessageBox.information(mw,"Selection Error","""Sheet UFO works only with a flat face as starter!\n Select a flat face.""")
          else:
            mw=FreeCADGui.getMainWindow()
            QtGui.QMessageBox.information(mw,"Selection Error","""Sheet UFO works only with a flat face as starter!\n Select a flat face.""")
    return resPart, folds, normalVect, theName


def SMGetGeoSegment(e):
    if 'Line' in str(e.Curve):
        return Part.LineSegment(e.Vertexes[0].Point,e.Vertexes[1].Point)
    elif 'Circle' in str(e.Curve):
        if not e.Closed:
            return Part.ArcOfCircle(e.Curve, e.FirstParameter,
                                    e.LastParameter,e.Curve.Axis.z>0)
        else:
            return Part.Circle(e.Curve.Center,e.Curve.Axis,e.Curve.Radius)
    return None
  
def SMmakeSketchfromEdges (edges, name):
    precision = 0.1 # precision in Bspline to BiArcs
    quasidef = 0.01 #quasi deflection for Ellipses and Parabola
    usk = FreeCAD.activeDocument().addObject('Sketcher::SketchObject',name)
    geo=[]
    for e in edges:
        if isinstance(e.Curve,Part.BSplineCurve):
            arcs = e.Curve.toBiArcs(precision)
            for i in arcs:
                eb = Part.Edge(i)
                seg = SMGetGeoSegment(eb)
                if seg is not None:
                    geo.append(seg)
        elif isinstance(e.Curve,Part.Ellipse) or isinstance(e.Curve,Part.Parabola):
            l=e.copy().discretize(QuasiDeflection=quasidef)
            plines=Part.makePolygon(l)
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


      
#############################################################################
# Gui Part. Widget generated from UnfoldOptions.ui using pyuic
#############################################################################
           
try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)
      
# loading presets
pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")
if pg.IsEmpty():
    pg.SetBool("bendSketch",0)
    pg.SetBool("genSketch",1)
    pg.SetString("bendColor","#c00000")
    pg.SetString("genColor","#000080")
    pg.SetString("intColor","#ff5733")
    pg.SetString("manualKFactor", "0.40")

class QColorButton(QtGui.QPushButton):
    '''
    Custom Qt Widget to show a chosen color.
    '''

    def __init__(self, *args, **kwargs):
        super(QColorButton, self).__init__(*args, **kwargs)
        self._color = None
        self.setMaximumWidth(32)
        self.pressed.connect(self.onColorPicker)

    def setColor(self, color):
        if color != self._color:
            self._color = color
            FreeCAD.Console.PrintLog("Set color " + self._color + "\n")
        if self._color is not None:
            self.setStyleSheet("background-color: %s;" % self._color)
        else:
            self.setStyleSheet("")

    def color(self):
        return self._color
        
    def colorF(self):
        return QtGui.QColor(self._color).getRgbF()

    def onColorPicker(self):
        dlg = QtGui.QColorDialog()
        if self._color:
            dlg.setCurrentColor(QtGui.QColor('self._color'))
        if dlg.exec_():
            self.setColor(dlg.currentColor().name())
        
        
import re


def get_linked_objs_recursive(links):
  Parts_index = 2
  objects = []
  for o in [l.LinkedObject for l in links]:
    if o.TypeId == 'App::Link':
      # recursive
      objects += get_linked_objs_recursive([o])
    elif o.TypeId == 'Part::FeaturePython':
      # this is an assembly container
      objects += o.Group[Parts_index].Group
    else:
      objects.append(o)
  # print "Examined objects: ", ', '.join([o.Label for o in objects])
  return objects


def getObjectsByLabelRecursive(doc, label):
  objects = doc.getObjectsByLabel(label)
  res = None
  if len(objects) == 0:
    # Maybe the document is a link
    try:
      links = doc.findObjects('App::Link')
      objects = get_linked_objs_recursive(links)
      for obj in objects:
        if obj.Label == label:
          res = obj
          break
    except:
      # In FreeCAD Main branch, "App:Link" is not a valid type
      # thus causing FreeCADError. Simply ignore it.
      pass
  else:
    res = objects[0]
  return res

def findObjectsByTypeRecursive(doc, type):
  objects = []
  for obj in doc.findObjects():
    if obj.TypeId == type:
      objects.append(obj)
    elif obj.TypeId == 'App::Link':
      for _o in get_linked_objs_recursive([obj]):
        if _o.TypeId == type:
          objects.append(_o)
  return objects 

# Start of spreadsheet functions
cell_regex = re.compile('^([A-Z]+)([0-9]+)$')
def get_cells(sheet):
  return sorted(filter(cell_regex.search, sheet.PropertiesList))

def get_cell_tuple(cell_name):
  m = cell_regex.match(cell_name)
  col_name = m.group(1)
  row_num = int(m.group(2))
  return (col_name, row_num)
# End of spreadsheet functions

class SMUnfoldTaskPanel:
    '''A TaskPanel for the facebinder'''
    def __init__(self):
        global genSketchChecked, genObjTransparency, manKFactor, kFactorStandard
        self.pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")
        
        # Get the material name if possible
        self.material_sheet_name = None
        material_sheet_regex_str = "material_([a-zA-Z0-9_\.]+)"
        material_sheet_regex = re.compile(material_sheet_regex_str)
        material_regex = re.compile(".+_%s" % material_sheet_regex_str)
        self.root_obj = self.get_root_obj()
        self.root_label = self.root_obj.Label
        material_match = material_regex.match(self.root_label)
        virtual_material = False
        if material_match:
            material_name = material_match.group(1)
            SMMessage("Material found: %s" % material_name)
            self.material_sheet_name = "material_%s" % material_name
            mds_postfix = "_" + self.material_sheet_name
            self.root_label = self.root_label[:-len(mds_postfix)]

            # Test if the material is virtual
            # if material name starts with a number, then this is a virtual material
            # (Manual K-Factor)
            virtual_material_regex = re.compile("([0-9\.]+)([a-zA-Z]+)")
            virtual_material_match = virtual_material_regex.match(material_name)
            if virtual_material_match:
                self.material_sheet_name = None
                virtual_material = {
                  "kfactor": float(virtual_material_match.group(1)),
                  "standard": virtual_material_match.group(2)
                }
                SMMessage("This is a Manual K-factor", virtual_material)

        spreadsheets = findObjectsByTypeRecursive(FreeCAD.ActiveDocument, 'Spreadsheet::Sheet')
        self.availableMdsObjects = [o for o in spreadsheets if material_sheet_regex.match(o.Label)]
                        
        self.obj = None
        self.form = SMUnfoldTaskPanel = QtGui.QWidget()
        self.form.setObjectName("SMUnfoldTaskPanel")
        self.form.setWindowTitle("Unfold sheet metal object")
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.form)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.horizontalLayout_1 = QtGui.QHBoxLayout()
        self.checkSketch = QtGui.QCheckBox(self.form)
        self.checkSketch.setObjectName(_fromUtf8("checkSketch"))
        self.checkSketch.stateChanged.connect(self.checkSketchChange)
        self.horizontalLayout_1.addWidget(self.checkSketch)
        self.genColor = QColorButton()
        self.genColor.setMaximumHeight(self.checkSketch.height() * 2 / 3)
        self.genColor.setColor(genSketchColor)
        self.horizontalLayout_1.addWidget(self.genColor)
        self.verticalLayout.addLayout(self.horizontalLayout_1)

        self.checkSeparate = QtGui.QCheckBox(self.form)
        self.checkSeparate.setObjectName(_fromUtf8("checkSeparate"))
        self.checkSeparate.stateChanged.connect(self.checkSketchChange)
        self.verticalLayout.addWidget(self.checkSeparate)
        
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.BendLbl = QtGui.QLabel(self.form)
        self.BendLbl.setObjectName(_fromUtf8("BendLbl"))
        self.horizontalLayout_3.addWidget(self.BendLbl)
        self.bendColor = QColorButton()
        self.bendColor.setMaximumHeight(self.checkSketch.height() * 2 / 3)
        self.bendColor.setColor(bendSketchColor)
        self.horizontalLayout_3.addWidget(self.bendColor)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.InternalLbl = QtGui.QLabel(self.form)
        self.InternalLbl.setObjectName(_fromUtf8("InternalLbl"))
        self.horizontalLayout_4.addWidget(self.InternalLbl)
        self.internalColor = QColorButton()
        self.internalColor.setMaximumHeight(self.checkSketch.height() * 2 / 3)
        self.internalColor.setColor(intSketchColor)
        self.horizontalLayout_4.addWidget(self.internalColor)
        self.verticalLayout.addLayout(self.horizontalLayout_4)
        
        # Material Definition Sheet selection 
        # TODO: This control currently extends the "MDS assignment (the 
        # label renaming hack)". However, in the future (when Propageted Properties 
        # are available) the same control will use a propagated property of the 
        # selected object as the information storage (instead of renaming the label)
        self.materalDefinitionSheetLayout = QtGui.QHBoxLayout()
        self.materalDefinitionSheetLayout.setObjectName(_fromUtf8("materalDefinitionSheetLayout"))
        self.checkUseMds = QtGui.QCheckBox(SMUnfoldTaskPanel)
        self.checkUseMds.setObjectName(_fromUtf8("checkUseMds"))
        self.checkUseMds.stateChanged.connect(self.checkUseMdsChange)
        self.materalDefinitionSheetLayout.addWidget(self.checkUseMds)
        self.availableMds = QtGui.QComboBox(SMUnfoldTaskPanel)
        self.availableMds.setObjectName(_fromUtf8("availableMds"))
        self.availableMds.currentIndexChanged.connect(self.mdsChanged)
        self.materalDefinitionSheetLayout.addWidget(self.availableMds)
        self.mdsApply = QtGui.QPushButton(SMUnfoldTaskPanel)
        self.mdsApply.setMaximumSize(QtCore.QSize(50, 16777215))
        self.mdsApply.setObjectName(_fromUtf8("mdsApply"))
        self.mdsApply.pressed.connect(self.mdsApplyPressed)
        self.materalDefinitionSheetLayout.addWidget(self.mdsApply)

        self.verticalLayout.addLayout(self.materalDefinitionSheetLayout)

        # Manual K-factor selection 
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setSizeConstraint(QtGui.QLayout.SetDefaultConstraint)
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.checkKfact = QtGui.QCheckBox(self.form)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkKfact.sizePolicy().hasHeightForWidth())
        self.checkKfact.setSizePolicy(sizePolicy)
        self.checkKfact.setObjectName(_fromUtf8("checkKfact"))
        # NOTE: use `.clicked.connect` instead of `.stateChanged.connect` if you want to
        # implement a "rollback" feature
        self.checkKfact.stateChanged.connect(self.checkKfactChange)
        # END OF NOTE
        self.horizontalLayout.addWidget(self.checkKfact)
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.kFactSpin = QtGui.QDoubleSpinBox(self.form)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.kFactSpin.sizePolicy().hasHeightForWidth())
        self.kFactSpin.setSizePolicy(sizePolicy)
        self.kFactSpin.setMaximumSize(QtCore.QSize(70, 16777215))
        self.kFactSpin.setDecimals(3)
        self.kFactSpin.setMaximum(2.0)
        self.kFactSpin.setSingleStep(0.1)
        default_k_factor = float(self.pg.GetString('manualKFactor') or 0.40)
        self.kFactSpin.setProperty("value", default_k_factor)
        self.kFactSpin.setObjectName(_fromUtf8("kFactSpin"))
        self.horizontalLayout.addWidget(self.kFactSpin) 
        # ANSI/DIN selection        
        self.kfactorAnsi = QtGui.QRadioButton(SMUnfoldTaskPanel)
        self.kfactorAnsi.setObjectName(_fromUtf8("kfactorAnsi"))
        self.horizontalLayout.addWidget(self.kfactorAnsi)
        self.kfactorDin = QtGui.QRadioButton(SMUnfoldTaskPanel)
        self.kfactorDin.setObjectName(_fromUtf8("kfactorDin"))
        self.horizontalLayout.addWidget(self.kfactorDin)
        #
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.horizontalLayout_2.setContentsMargins(-1, 0, -1, -1)
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.label = QtGui.QLabel(self.form)
        self.label.setObjectName(_fromUtf8("label"))
        self.horizontalLayout_2.addWidget(self.label)        
        self.transSpin = QtGui.QSpinBox(self.form)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.transSpin.sizePolicy().hasHeightForWidth())
        self.transSpin.setSizePolicy(sizePolicy)
        self.transSpin.setMaximumSize(QtCore.QSize(70, 16777215))
        self.transSpin.setMaximum(100)
        self.transSpin.setObjectName(_fromUtf8("transSpin"))
        self.horizontalLayout_2.addWidget(self.transSpin)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        if genSketchChecked:
          self.checkSketch.setCheckState(QtCore.Qt.CheckState.Checked)
        if bendSketchChecked:
          self.checkSeparate.setCheckState(QtCore.Qt.CheckState.Checked)

        self.kFactSpin.setEnabled(False)          
        self.transSpin.setProperty("value", genObjTransparency)

        self.updateKfactorStandard()
        self.checkKfactChange()
        self.checkSketchChange()
        self.populateMdsList()
        self.retranslateUi()

        if isinstance(virtual_material, dict):
            manKFactor = virtual_material["kfactor"]
            self.kFactSpin.setProperty("value", manKFactor)
            self.checkKfact.setChecked(True)
            self.updateKfactorStandard(virtual_material["standard"])

    def get_root_obj(self):
        selobj = Gui.Selection.getSelection()[0]
        selobj_parent = selobj.getParentGeoFeatureGroup()
        if selobj_parent:
            return selobj_parent
        else:
            return selobj

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok)
        
    def mdsApplyPressed(self):
        SMMessage("INFO: Changed material of '%s' from '%s' to '%s'"
                % (self.root_label, self.material_sheet_name, self.new_mds_name))

        self.setMds(self.new_mds_name)
        self.mdsApply.setEnabled(False)

    def setMds(self, mds_name):
        if mds_name is None:
            self.root_obj.Label = self.root_label
        else:
            self.root_obj.Label = "%s_%s" % (self.root_label, mds_name)
        self.material_sheet_name = mds_name

    def mdsChanged(self):
        self.new_mds_name = self.availableMds.currentText()
        if self.availableMds.currentIndex() == 0:
            self.new_mds_name = None
        self.mdsApply.setEnabled(self.material_sheet_name != self.new_mds_name)

    def populateMdsList(self):
        mds_enabled = self.checkUseMds.isChecked()
        self.availableMds.setEnabled(mds_enabled)
        self.mdsApply.setEnabled(False)

        # mark selected state if material is assigned
        if not self.checkKfact.isChecked():
            if self.material_sheet_name is not None:
                self.checkUseMds.setChecked(True)

        if mds_enabled:
            self.checkKfact.setChecked(False)

        self.availableMds.clear()
        self.availableMds.addItem('Not set')
        i = 1
        curr = 0
        for mds in self.availableMdsObjects:
            self.availableMds.addItem(mds.Label)
            if mds.Label == self.material_sheet_name:
                curr = i
            i += 1

        self.availableMds.setCurrentIndex(curr)
        
    def updateKfactorStandard(self, transient_std=None):
        global kFactorStandard
        if transient_std is None:
            # Use any previously saved the K-factor standard if available.
            # (note: this will be ignored while using material definition sheet.)
            kFactorStandard = self.pg.GetString("kFactorStandard")
        else:
            kFactorStandard = transient_std

        self.kfactorAnsi.setChecked(kFactorStandard == 'ansi')
        self.kfactorDin.setChecked(kFactorStandard == 'din')

    def getManualKFactorString(self, k_factor, standard):
        return "material_%.2f%s" % (k_factor, standard)

    def accept(self):
        global genSketchChecked, bendSketchChecked, genObjTransparency, manKFactor
        global genSketchColor, bendSketchColor
        global kFactorStandard
        genSketchChecked = self.checkSketch.isChecked()
        genSketchColor = self.genColor.color()
        bendSketchChecked = self.checkSeparate.isChecked()
        bendSketchColor = self.bendColor.color()
        intSketchColor = self.internalColor.color()
        
        ##print(self.checkSeparate.isChecked())
        pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")
        if bendSketchChecked:
            pg.SetBool("bendSketch",1)
        else:
            pg.SetBool("bendSketch",0)
        if genSketchChecked:
            pg.SetBool("genSketch",1)
        else:
            pg.SetBool("genSketch",0)

        pg.SetString("bendColor",bendSketchColor)
        pg.SetString("genColor",genSketchColor)
        pg.SetString("intColor",intSketchColor)
                
        if self.checkKfact.isChecked():
            if self.kfactorAnsi.isChecked():
                kFactorStandard = 'ansi'
            elif self.kfactorDin.isChecked():
                kFactorStandard = 'din'
            else:
                SMErrorBox("K-factor standard must be explicitly selected")
                return        
            pg.SetString("kFactorStandard", kFactorStandard)
            manKFactor = self.kFactSpin.value()
            self.pg.SetString('manualKFactor', str(manKFactor))
            SMMessage('Manual K-factor is being used: %.2f (%s)', (manKFactor, kFactorStandard))
            self.setMds(self.getManualKFactorString(manKFactor, kFactorStandard))
        else:
            manKFactor = None
            kFactorStandard = None 
            self.updateKfactorStandard()
            if self.new_mds_name != self.material_sheet_name:
                SMErrorBox("Please 'Apply' your new Material Definition Sheet name first.")
                return

        genObjTransparency = self.transSpin.value()

        doc = FreeCAD.ActiveDocument
        # Build the k_factor lookup table
        if self.material_sheet_name and not self.checkKfact.isChecked():
            lookup_sheet = getObjectsByLabelRecursive(doc, self.material_sheet_name)
            if lookup_sheet is None:
                SMErrorBox("No Spreadsheet is found containing material definition: %s" % self.material_sheet_name)
                return
            SMMessage("Using Material Definition Sheet: %s" % self.material_sheet_name)

            key_cell = None
            value_cell = None
            options_cell = None 
            for cell in get_cells(lookup_sheet):
                if lookup_sheet.get(cell) == 'Radius / Thickness':
                    key_cell = cell 
                if lookup_sheet.get(cell) == 'K-factor':
                    value_cell = cell                     
                if lookup_sheet.get(cell) == 'Options':
                    options_cell = cell 
                if key_cell is not None and value_cell is not None and options_cell is not None:
                    break 

            lookup_sheet_err = None
            if key_cell is None:
                lookup_sheet_err = "No cell can be found with name: 'Radius / Thickness'"
            if value_cell is None:
                lookup_sheet_err = "No cell can be found with name: 'K-factor'"
            if options_cell is None:
                lookup_sheet_err = "No cell can be found with name: 'Options'"

            if lookup_sheet_err is not None:
                lookup_sheet_err += '\n\n'
                lookup_sheet_err += "Check your Material Definition Sheet's contents.\n"
                lookup_sheet_err += "Refer to SheetMetal/README if you are unsure what to do."
                SMErrorBox(lookup_sheet_err)
                return

            [key_column_name, key_column_row] = get_cell_tuple(key_cell)
            value_column_name = get_cell_tuple(value_cell)[0]
                
            # Build K-factor lookup table 
            k_factor_lookup = {}
            for i in range(key_column_row + 1, 1000):
                try:
                    key = float(lookup_sheet.get(key_column_name + str(i)))
                except:
                    break            
                value = float(lookup_sheet.get(value_column_name + str(i)))

                #SMMessage("Found key/value: %f : %f" % (key, value))
                k_factor_lookup[key] = value 
            
            # Get the options 
            # ----------------
            
            # Ignore any saved K-factor standard settings when using a M.D.S.
            # because user might be using a third party library that depends 
            # on a different K-factor standard, so project might contain mixed 
            # K-factor standards. 
            kFactorStandard = None  
            
            [opt_col, opt_row] = get_cell_tuple(options_cell)
            i = 1
            while True:
                opt_key_cell = "%s%i" % (opt_col, opt_row + i)
                next_col = chr(ord(opt_col) + 1)
                opt_value_cell = "%s%i" % (next_col, opt_row + i)
                i += 1
                try:
                    option = lookup_sheet.get(opt_key_cell)
                    value = lookup_sheet.get(opt_value_cell)
                except:
                    break
                    
                #print "Found option: ", option, ":", value
                if option == 'K-factor standard':
                    if value in ["ANSI", "DIN"]:
                        kFactorStandard = value.lower()
                    else:
                        SMErrorBox('Invalid K-factor standard: %s \nin %s' % (value, self.material_sheet_name))
                        return                        
                
            if kFactorStandard is None:
                SMErrorBox("'K-factor standard' option is required (ANSI or DIN) in %s" % self.material_sheet_name)
                return
            
            SMMessage("Obtained K-factor lookup table is:", k_factor_lookup)
        elif not self.checkKfact.isChecked():
            msg = "Unfold operation needs to know K-factor value(s) to be used."
            msg += "\n\n"
            msg += "* Either set a manual K-factor in the SheetMetal options menu\n"
            msg += "* Or use a \"Material Definition Sheet\" (see SheetMetal/README)"
            SMErrorBox(msg)
            return
        else:
            k_factor_lookup = {}  # manual value will be used

        """
        # For debugging purposes 
        k_factor_lookup = {
            1: 0.25,
            3: 0.35,
            5: 0.44,
            99: 0.5
        }
        """
        try:
            s, foldComp, norm, thename = getUnfold(k_factor_lookup)
            foldLines = foldComp.Edges
        except Exception as e:
            s = None
            QtGui.QApplication.restoreOverrideCursor()
            SMError(e.args)
            import traceback; traceback.print_exc()
            msg = """Unfold is failing.<br>Please try to select a different face to unfold your object"""
            QtGui.QMessageBox.question(None,"Warning",msg,QtGui.QMessageBox.Ok)
        if (s is not None):
          doc.openTransaction("Unfold")
          a = doc.addObject("Part::Feature","Unfold")
          a.Shape = s
          if genSketchChecked:
            edges = []
            grp1 = Drawing.projectEx(s,norm)
            edges.append(grp1[0])
            if len(foldLines) > 0:
              co = Part.makeCompound(foldLines)
              grp2 = Drawing.projectEx(co, norm)
              if not bendSketchChecked:
                edges.append(grp2[0])
            self.generateSketch(edges, "Unfold_Sketch", self.genColor.colorF())
            sku = doc.ActiveObject
            if bendSketchChecked:
              docG = FreeCADGui.ActiveDocument
              try:
                doc.addObject("Part::Face", "mainFace").Sources = (sku, )
                doc.recompute()
                newface = doc.ActiveObject
                owEdgs = newface.Shape.OuterWire.Edges
                faceEdgs = newface.Shape.Edges
                doc.removeObject(newface.Name)
                #Part.show(newface)
                self.generateSketch(owEdgs, "Unfold_Sketch_Outline", self.genColor.colorF())
                sko = doc.ActiveObject
                intEdgs = []; idx = []
                for i, e in enumerate(faceEdgs):
                  for oe in owEdgs:
                    if oe.hashCode() == e.hashCode():
                      idx.append(i)
                for i, e in enumerate(faceEdgs):
                  if i not in idx:
                    intEdgs.append(e)
                if len (intEdgs) > 0:
                  self.generateSketch(intEdgs, "Unfold_Sketch_Internal", self.internalColor.colorF())
                docG = FreeCADGui.ActiveDocument
                docG.getObject(sku.Name).Visibility = False
                #doc.recompute()
              except:
                doc.removeObject(newface.Name)
                SMError('Exception: Outline Sketch not created')
            if len(foldLines) > 0 and bendSketchChecked:
              foldEdges = []
              foldEdges.append(grp2[0])
              self.generateSketch(foldEdges, "Unfold_Sketch_bends", self.bendColor.colorF())
          doc.commitTransaction()
          docG = FreeCADGui.ActiveDocument
          docG.getObject(a.Name).Transparency = genObjTransparency
        doc.recompute()
        FreeCAD.ActiveDocument.recompute()
        return True
        
    def generateSketch(self, edges, name, color):
        docG = FreeCADGui.ActiveDocument
        p = Part.makeCompound(edges)
        try:
            sk = Draft.makeSketch(p.Edges, autoconstraints = True)
            sk.Label = name
        except:
            doc = FreeCAD.ActiveDocument
            skb = doc.ActiveObject
            doc.removeObject(skb.Name)
            SMWarning("discretizing Sketch")
            sk = SMmakeSketchfromEdges(p.Edges,name)
        docG.getObject(sk.Name).LineColor = color
        docG.getObject(sk.Name).PointColor = color

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok) + int(QtGui.QDialogButtonBox.Cancel)
        
    def checkKfactChange(self):
        checked = self.checkKfact.isChecked()
        if not checked and not self.checkUseMds.isChecked():
            # not allowed to uncheck unless "Use MDS" box is checked
            # (radio-button behavior)
            # FIXME: NOT WORKING! Why? >>See .clicked.connect note<< -> self.checkKfact.setChecked(True)
            # return 
            pass
        self.kFactSpin.setEnabled(checked)
        self.kfactorAnsi.setEnabled(checked)
        self.kfactorDin.setEnabled(checked)
        if checked:
            self.checkUseMds.setChecked(False)
        
    def checkUseMdsChange(self):
        self.populateMdsList()

    def checkSketchChange(self):
        self.checkSeparate.setEnabled(self.checkSketch.isChecked())
        #self.genColor.setEnabled(self.checkSketch.isChecked())
        #self.bendColor.setEnabled(self.checkSketch.isChecked() and self.checkSeparate.isChecked())
        
    def retranslateUi(self):
        self.form.setWindowTitle(_translate("SheetMetal", "Unfold sheet metal object", None))
        self.checkSketch.setText(_translate("SheetMetal", "Generate projection sketch", None))
        self.checkSeparate.setText(_translate("SheetMetal", "Separate projection layers", None))
        self.checkKfact.setText(_translate("SheetMetal", "Manual K-factor", None))
        self.label.setText(_translate("SheetMetal", "Unfold object transparency", None))
        self.transSpin.setSuffix(_translate("SheetMetal", "%", None))
        self.BendLbl.setText(_translate("SheetMetal", "    Bend lines color", None))
        self.InternalLbl.setText(_translate("SheetMetal", "    Internal lines color", None))
        self.kfactorAnsi.setText(_translate("SheetMetal", "ANSI", None))
        self.kfactorDin.setText(_translate("SheetMetal", "DIN", None))
        self.checkUseMds.setText(_translate("SMUnfoldTaskPanel", "Use Material Definition Sheet", None))
        self.mdsApply.setText(_translate("SMUnfoldTaskPanel", "Apply", None))


class SMUnfoldCommandClass():
  """Unfold object"""

  def GetResources(self):
    __dir__ = os.path.dirname(__file__)
    iconPath = os.path.join( __dir__, 'Resources', 'icons' )
    return {'Pixmap'  : os.path.join( iconPath , 'SMUnfold.svg') , # the name of a svg file available in the resources
            'MenuText': "Unfold" ,
            'ToolTip' : "Flatten folded sheet metal object"}
 
  def Activated(self):
    try:
        taskd = SMUnfoldTaskPanel()
    except ValueError as e:
        SMErrorBox(e.args[0])
        return 

    pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")
    if pg.GetBool("bendSketch"):
        taskd.checkSeparate.setCheckState(QtCore.Qt.CheckState.Checked)
    else:
        taskd.checkSeparate.setCheckState(QtCore.Qt.CheckState.Unchecked)
    if pg.GetBool("genSketch"):
        taskd.checkSketch.setCheckState(QtCore.Qt.CheckState.Checked)
    else:
        taskd.checkSketch.setCheckState(QtCore.Qt.CheckState.Unchecked)
    taskd.bendColor.setColor(pg.GetString("bendColor"))
    taskd.genColor.setColor(pg.GetString("genColor"))
    taskd.internalColor.setColor(pg.GetString("intColor"))
    FreeCADGui.Control.showDialog(taskd)
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) != 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
    if type(selFace) != Part.Face:
      return False
    return True

Gui.addCommand('SMUnfold',SMUnfoldCommandClass())

class SMUnfoldUnattendedCommandClass():
  """Unfold object"""

  def GetResources(self):
    __dir__ = os.path.dirname(__file__)
    iconPath = os.path.join( __dir__, 'Resources', 'icons' )
    return {'Pixmap'  : os.path.join( iconPath , 'SMUnfoldUnattended.svg') , # the name of a svg file available in the resources
            'MenuText': "Unattended Unfold" ,
            'ToolTip' : "Flatten folded sheet metal object with default options."}

  def Activated(self):
    SMMessage("Running unattended unfold...")
    try:
        taskd = SMUnfoldTaskPanel()
    except ValueError as e:
        SMErrorBox(e.args[0])
        return 

    pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/sheetmetal")
    if pg.GetBool("bendSketch"):
        taskd.checkSeparate.setCheckState(QtCore.Qt.CheckState.Checked)
    else:
        taskd.checkSeparate.setCheckState(QtCore.Qt.CheckState.Unchecked)
    if pg.GetBool("genSketch"):
        taskd.checkSketch.setCheckState(QtCore.Qt.CheckState.Checked)
    else:
        taskd.checkSketch.setCheckState(QtCore.Qt.CheckState.Unchecked)
    taskd.bendColor.setColor(pg.GetString("bendColor"))
    taskd.genColor.setColor(pg.GetString("genColor"))
    taskd.internalColor.setColor(pg.GetString("intColor"))
    taskd.new_mds_name = taskd.material_sheet_name
    taskd.accept()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) != 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
    if type(selFace) != Part.Face:
      return False
    return True

Gui.addCommand("SMUnfoldUnattended",SMUnfoldUnattendedCommandClass())
