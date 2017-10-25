#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  sheet_ufo.py
#  
#  Copyright 2014 Ulrich Brammer <ulrich@Pauline>
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


# Refactored version December 2015
# Clear division of tasks between analysis and folding

# To do:
# change code to handle face indexes in the node instead of faces


# sheet_ufo17.py
# Die Weiterreichung eines schon geschnittenen Seitenfaces macht Probleme.
# Die Seitenfaces passen hinterher nicht mehr mit den Hauptflächen zusammen.

# Geänderter Ansatz: lasse die Seitenflächen in der Suchliste und 
# schneide jeweils nur den benötigten Teil raus.
# Ich brauche jetzt eine Suchliste und eine Unfoldliste für die 
# Face-Indices.

# To do: 
# - handle a selected seam
# - handle not-circle-curves in bends
# - detect features like welded screws
# - make a view-provider for bends
# - make the k-factor selectable
# - upfold or unfold single bends

## https://forum.freecadweb.org/viewtopic.php?t=15421#p122997 

'''

def main():
	
	return 0

if __name__ == '__main__':
	main()


'''


import Part, FreeCAD, FreeCADGui, os
from PySide import QtGui
from FreeCAD import Base
from FreeCAD import Gui
import DraftVecUtils, DraftGeomUtils, math, time

# to do: 
# - Put error numbers into the text
# - Put user help into more texts
unfold_error = {
  # error codes for the tree-object
  1: ('starting: volume unusable, needs a real 3D-sheet-metal with thickness'), 
  2: ('Starting: invalid point for thickness measurement'), 
  3: ('Starting: invalid thickness'), 
  4: ('Starting: invalid shape'), 
  # error codes for the bend-analysis 
  10: ('Analysis: zero wires in sheet edge analysis'), 
  11: ('Analysis: double bends not implemented'), 
  12: ('Analysis: more than one bend-child actually not supported'), 
  13: ('Analysis: counter face not found'), 
  14: ('Analysis: the code can not handle edges without neighbor faces'), 
  15: ('Analysis: the code needs a face at all sheet edges'), 
  16: ('Analysis: did not find startangle of bend, please post failing sample for analysis'), 
  # error codes for the unfolding
  20: ('Unfold: section wire with less than 4 edges'),
  21: ('Unfold: Unfold: section wire not closed'),
  22: ('Unfold: section failed'),
  23: ('Unfold: CutToolWire not closed'),
  24: ('Unfold: bend-face without child not implemented'),
  25: ('Unfold: '),
  -1: ('unknown error')} 


def SMLog(* args):
  message = ""
  for x in args:
    message += str(x)
  FreeCAD.Console.PrintLog(message + "\n")
  FreeCAD.Console.PrintMessage(message + "\n") #maui


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
  # SMLog(chord, norm, perp)
  dist_rv = DraftVecUtils.project(chord,perp)
  #test_line = Part.makeLine(axis_pnt.add(dist_rv),axis_pnt)
  # test_line = Part.makeLine(axis_pnt.add(perp),axis_pnt)
  # test_line = Part.makeLine(point, axis_pnt)
  # Part.show(test_line)
  return perp.normalize()





class Simple_node(object):
  ''' This class defines the nodes of a tree, that is the result of
  the analysis of a sheet-metal-part.
  Each flat or bend part of the metal-sheet gets a node in the tree.
  The indexes are the number of the face in the original part.
  '''
  def __init__(self, f_idx=None, Parent_node= None, Parent_edge = None):
    self.idx = f_idx  # index of the "top-face"
    self.c_face_idx = None # face index to the opposite face of the sheet (counter-face)
    self.node_type = None  # 'Flat' or 'Bend'
    self.p_node = Parent_node   # Parent node
    self.p_edge = Parent_edge # the connecting edge to the parent node
    self.child_list = [] # List of child-nodes = link to tree structure
    self.child_idx_lists = [] # List of lists with child_idx and child_edge
    # need also a list of indices of child faces
    self.sheet_edges = [] # List of edges without child-face 
    self.axis = None
    self.facePosi = None
    self.bendCenter = None
    self.distCenter = None
    # self.axis for 'Flat'-face: vector pointing from the surface into the metal
    self.bend_dir = None # bend direction values: "up" or "down"
    self.bend_angle = None # angle in radians
    self.tan_vec = None # direction of translation for Bend nodes
    self._trans_length = None # length of translation for Bend nodes, k-factor used according to DIN 6935
    self.analysis_ok = True # indicator if something went wrong with the analysis of the face
    self.error_code = None # index to unfold_error dictionary
    # here the new features of the nodes:
    self.nfIndexes = [] # list of all face-indexes of a node (flat and bend: folded state)
    self.seam_edges = [] # list with edges to seams
    # bend faces are needed for movement simulation at single other bends.
    # otherwise unfolded faces are recreated from self.b_edges
    self.node_flattened_faces = [] # faces of a flattened bend node.
    self.actual_angle = None # state of angle in refolded sheet metal part
    self.p_wire = None # wire common with parent node, used for bend node
    self.c_wire = None # wire common with child node, used for bend node
    self.b_edges = [] # list of edges in a bend node, that needs to be recalculated, at unfolding

  def get_Face_idx(self):
    # get the face index from the tree-element
    return self.idx





class SheetTree(object):
  def __init__(self, TheShape, f_idx):
    self.cFaceTol = 0.002 # tolerance to detect counter-face vertices
    # this high tolerance was needed for more real parts
    self.root = None # make_new_face_node adds the root node if parent_node == None
    self.__Shape = TheShape.copy()
    self.error_code = None
    self.failed_face_idx = None
    
    if not self.__Shape.isValid():
      SMError("The shape is not valid!")
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
    #SMLog(self.index_list)
    self.max_f_idx = len(self.f_list) # need this value to make correct indices to new faces

    theVol = self.__Shape.Volume
    if theVol < 0.0001:
      SMError("Shape is not a real 3D-object or to small for a metal-sheet!")
      self.error_code = 1
      self.failed_face_idx = f_idx

    else:
      # Make a first estimate of the thickness
      estimated_thickness = theVol/(self.__Shape.Area / 2.0)
      SMLog("approximate Thickness: ", estimated_thickness)
      # Measure the real thickness of the initial face: Use Orientation and
      # Axis to make an measurement vector
      
    
      if hasattr(self.__Shape.Faces[f_idx],'Surface'):
        # Part.show(self.__Shape.Faces[f_idx])
        # SMLog('the object is a face! vertices: ', len(self.__Shape.Faces[f_idx].Vertexes))
        F_type = self.__Shape.Faces[f_idx].Surface
        # fixme: through an error, if not Plane Object
        SMLog('It is a: ', str(F_type))
        SMLog('Orientation: ', str(self.__Shape.Faces[f_idx].Orientation))
        
        # Need a point on the surface to measure the thickness.
        # Sheet edges could be sloping, so there is a danger to measure
        # right at the edge. 
        # Try with Arithmetic mean of plane vertices
        m_vec = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
        for Vvec in self.__Shape.Faces[f_idx].Vertexes:
            #m_vec = m_vec.add(Base.Vector(Vvec.X, Vvec.Y, Vvec.Z))
            m_vec = m_vec.add(Vvec.Point)
        mvec = m_vec.multiply(1.0/len(self.__Shape.Faces[f_idx].Vertexes))
        SMLog("mvec: ", mvec)
        
        if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
          s_Posi = self.__Shape.Faces[f_idx].Surface.Position
          k = 0
          # while k < len(self.__Shape.Faces[f_idx].Vertexes):
          # fixme: what if measurepoint is outside?
          pvert = self.__Shape.Faces[f_idx].Vertexes[k]
          pvec = Base.Vector(pvert.X, pvert.Y, pvert.Z)
          shiftvec =  mvec.sub(pvec)
          shiftvec = shiftvec.normalize()*2.0*estimated_thickness
          measure_pos = pvec.add(shiftvec)
          # Description: Checks if a point is inside a solid with a certain tolerance.
          # If the 3rd parameter is True a point on a face is considered as inside

          if not self.__Shape.isInside(measure_pos, 0.00001, True):
            SMError("Starting measure_pos for thickness measurement is outside!")
            self.error_code = 2
            self.failed_face_idx = f_idx

        
        if hasattr(self.__Shape.Faces[f_idx].Surface,'Axis'):
          s_Axis =  self.__Shape.Faces[f_idx].Surface.Axis
          # SMLog('We have an axis: ', s_Axis)
          if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
            s_Posi = self.__Shape.Faces[f_idx].Surface.Position
            # SMLog('We have a position: ', s_Posi)
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
        SMLog("lLine number edges: ", len(lLine.Edges))
        measVert = Part.Vertex(measure_pos)
        for mEdge in lLine.Edges:
          if equal_vertex(mEdge.Vertexes[0], measVert) or equal_vertex(mEdge.Vertexes[1], measVert):
            self.__thickness = mEdge.Length
        
        # self.__thickness = lLine.Length
        if (self.__thickness < estimated_thickness) or (self.__thickness > 1.9 * estimated_thickness): #maui
          self.error_code = 3
          self.failed_face_idx = f_idx
          SMError("estimated thickness: ", estimated_thickness, " measured thickness: ", self.__thickness)
          Part.show(lLine)


  def get_node_faces(self, theNode, wires_e_lists):
    ''' This function searches for all faces making up the node, except
    of the top and bottom face, which are already there.
    wires_e_list is the list of wires lists of the top face without the parent-edge
    theNode: the actual node to be filled with data.
    '''
    
    # How to begin?
    # searching for all faces, that have two vertices in common with 
    # an edge from the list should give the sheet edge.
    # But we also need to look at the sheet edge, in order to not claim
    # faces from the next node!
    # Then we have to treat thoses faces, that belongs to more than one
    # node. Those faces needs to be cut and the face list needs to be updated.
    # look also at the number of wires of the top face. More wires will
    # indicate a hole or a feature.
    SMLog(" When will this be called")
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
    SMLog("found_indices: ", found_indices)
                


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
          break
      if the_index <> None:
        break
          
    # Simple strategy applied: look if the connecting face has vertexes
    # with sheet-thickness distance to the top face.
    # fix me: this will fail with sharpened sheet edges with two faces
    # between top and bottom.
    if the_index <> None:
      distVerts = 0
      vertList = []
      F_type = str(self.f_list[tree_node.idx].Surface)
      # now we need to search for vertexes with sheet_thickness_distance
      #if F_type == "<Plane object>":
      for F_vert in self.f_list[i].Vertexes:
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
    distFailure = 0
    if F_type == "<Plane object>":
      distFailure = vF_vert.distanceToPlane (theNode.facePosi, theNode.axis) - self.__thickness
    if F_type == "<Cylinder object>":
      distFailure = vF_vert.distanceToLine (theNode.bendCenter, theNode.axis) - theNode.distCenter
    # SMLog("counter face distance: ", dist_v + self.__thickness)
    if (distFailure < self.cFaceTol) and (distFailure > -self.cFaceTol):
      return True
    else:
      return False





  def divideEdgeFace(self, fIdx, ise_edge, F_vert, tree_node):
    SMLog("Sheet edge face has more than 4 edges!")
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
      #SMLog("need Cut at 0 with fIdx: ", fIdx)
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
      #SMLog("need Cut at 1 with fIdx: ", fIdx)
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
    one piece is connected to the node. The residual pieces is given
    for assignment to other nodes.
    The function returns both pieces of the original face.
    '''
    # SMLog("now the face cutter")
    
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
      vec1 = Base.Vector(theNode.axis.x, theNode.axis.y, theNode.axis.z) # make a copy

      crossVec = tan_vec.cross(vec1)
      crossVec.multiply(3.0*self.__thickness)

      vec1.multiply(self.__thickness)
      # defining the points of the cutting plane:
      Spnt1 = origin - theNode.axis - crossVec
      Spnt2 = origin - theNode.axis + crossVec
      Spnt3 = origin + theNode.axis +  vec1 + crossVec
      Spnt4 = origin + theNode.axis +  vec1 - crossVec
  
      
      
    if F_type == "<Cylinder object>":
      ePar = theEdge.parameterAt(theEdge.Vertexes[eIdx])
      SMLog("Idx: ", eIdx, " ePar: ", ePar)
      otherPar = theEdge.parameterAt(theEdge.Vertexes[otherIdx])
      tan_vec = theEdge.tangentAt(ePar)
      if ePar < otherPar:
        tan_vec.multiply(-1.0)
      
      #tan_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(tan_vec), theEdge.Vertexes[eIdx].Point)
      #Part.show(tan_line)
      
      edge_vec = theEdge.Vertexes[eIdx].copy().Point
      radVector = radial_vector(edge_vec, theNode.bendCenter, theNode.axis)
      if theNode.bend_dir == "down":
        radVector.multiply(-1.0)
  
      #rad_line = Part.makeLine(theEdge.Vertexes[eIdx].Point.add(radVector), theEdge.Vertexes[eIdx].Point)
      #Part.show(rad_line)

      crossVec = tan_vec.cross(radVector)
      crossVec.multiply(3.0*self.__thickness)
      vec1 = Base.Vector(radVector.x, radVector.y, radVector.z) # make a copy

      vec1.multiply(self.__thickness)
      # defining the points of the cutting plane:
      Spnt1 = origin - radVector - crossVec
      Spnt2 = origin - radVector + crossVec
      Spnt3 = origin + radVector +  vec1 + crossVec
      Spnt4 = origin + radVector +  vec1 - crossVec
    
    Sedge1 = Part.makeLine(Spnt1,Spnt2)
    Sedge2 = Part.makeLine(Spnt2,Spnt3)
    Sedge3 = Part.makeLine(Spnt3,Spnt4)
    Sedge4 = Part.makeLine(Spnt4,Spnt1)
        
    Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
    Sf1=Part.Face(Sw1) #
    cut_solid = Sf1.extrude(tan_vec.multiply(5.0))
    #Part.show(cut_solid)
    #cut_opposite = Sf1.extrude(tan_vec.multiply(-5.0))
    
    cutFaces_node = self.f_list[fIdx].cut(cut_solid)
    for cFace in cutFaces_node.Faces:
      for myVert in cFace.Vertexes:
        if equal_vertex(theEdge.Vertexes[eIdx], myVert):
          nodeFace = cFace
          #SMLog("The nodeFace")
          #Part.show(nodeFace)
          break

    '''
    cutFaces_residue = self.f_list[fIdx].cut(cut_opposite)
    for cFace in cutFaces_residue.Faces:
      for myVert in cFace.Vertexes:
        if equal_vertex(theEdge.Vertexes[eIdx], myVert):
          residueFace = cFace
          #SMLog("the residueFace")
          #Part.show(residueFace)
          break
    '''

    return nodeFace #, residueFace
    


  def is_sheet_edge3(self, ise_edge, tree_node): # ise_edge: IsSheetEdge_edge
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
          break
      if the_index <> None:
        break
          
    if the_index <> None:
      distVerts = 0
      vertList = []
      F_type = str(self.f_list[tree_node.idx].Surface)
      # now we need to search for vertexes with sheet_thickness_distance
      #if F_type == "<Plane object>":
      for F_vert in self.f_list[i].Vertexes:
        vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
        if F_type == "<Plane object>":
          distFailure = vF_vert.distanceToPlane (tree_node.facePosi, tree_node.axis) - self.__thickness
        if F_type == "<Cylinder object>":
          distFailure = vF_vert.distanceToLine (tree_node.bendCenter, tree_node.axis) - tree_node.distCenter
        # SMLog("counter face distance: ", dist_v + self.__thickness)
        if (distFailure < self.cFaceTol) and (distFailure > -self.cFaceTol):
          has_sheet_distance_vertex = True
          break

    else:
      tree_node.analysis_ok = False 
      tree_node.error_code = 15  # Analysis: the code needs a face at all sheet edges
      self.error_code = 15
      self.failed_face_idx = tree_node.idx
      Part.show(self.f_list[tree_node.idx])
            
    return has_sheet_distance_vertex
    



  def make_new_face_node(self, face_idx, P_node, P_edge, wires_e_lists):
    # e_list: list of edges of the top face of a node without the parent-edge (P_edge)
    # analyze the face and get type of face ("Flat" or "Bend")
    # search the counter face, get axis of Face
    # In case of "Bend" get angle, k_factor and trans_length
    # put the node into the tree
    newNode = Simple_node(face_idx, P_node, P_edge)
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
      SMLog("Face", face_idx+1, " Type: ", newNode.node_type)

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
      # Part.show(axis_line)
      
      # nead a mean point of the face to avoid false counter faces
      faceMiddle = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
      for Vvec in self.__Shape.Faces[face_idx].OuterWire.Vertexes:
          faceMiddle = faceMiddle.add(Vvec.Point)
      faceMiddle = faceMiddle.multiply(1.0/len(self.__Shape.Faces[face_idx].OuterWire.Vertexes))
      
      # search for the counter face
      for i in such_list:
        counter_found = True
        for F_vert in self.f_list[i].Vertexes:
          vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
          dist_v = vF_vert.distanceToPlane (s_Posi, ext_Vec) - self.__thickness
          # SMLog("counter face distance: ", dist_v + self.__thickness)
          if (dist_v > self.cFaceTol) or (dist_v < -self.cFaceTol):
              counter_found = False
  
        if counter_found:
          # nead a mean point of the face to avoid false counter faces
          counterMiddle = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
          for Vvec in self.__Shape.Faces[i].OuterWire.Vertexes:
              counterMiddle = counterMiddle.add(Vvec.Point)
          counterMiddle = counterMiddle.multiply(1.0/len(self.__Shape.Faces[i].OuterWire.Vertexes))
          
          distVector = counterMiddle.sub(faceMiddle)
          counterDistance = distVector.Length
          
          if counterDistance < 3*self.__thickness:
            SMLog("found counter-face", i + 1)
            newNode.c_face_idx = i
            self.index_list.remove(i)
            newNode.nfIndexes.append(i)
            
            # Part.show(self.__Shape.Faces[newNode.c_face_idx])
          else:
            counter_found = False
            SMLog("faceMiddle: ", str(faceMiddle), "counterMiddle: ", str(counterMiddle))
      #if newNode.c_face_idx == None:
      #  Part.show(axis_line)
          
        

            
    if F_type == "<Cylinder object>":
      newNode.node_type = 'Bend' # fixme
      s_Center = self.__Shape.Faces[face_idx].Surface.Center
      s_Axis = self.__Shape.Faces[face_idx].Surface.Axis
      newNode.axis = s_Axis
      newNode.bendCenter = s_Center
      edge_vec = P_edge.Vertexes[0].copy().Point
      SMLog("edge_vec: ", str(edge_vec))
      
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
      else:
        newNode.bend_dir = "up"
        thick_test = self.__Shape.Faces[face_idx].Surface.Radius + self.__thickness
      newNode.distCenter = thick_test
      # SMLog("Face idx: ", face_idx, " bend_dir: ", newNode.bend_dir)
      SMLog("Face", face_idx+1, " Type: ", newNode.node_type, " bend_dir: ", newNode.bend_dir)
      
      # need to define the bending angle relative to the Center and the
      # Axis of the bend surface:
      # search for line-edges with no common point with edge_vec and fixme: not in the same line
      # fixme: there could be more than one edge meeting the criteria!
      number_c_edges = 0
      for s_edge in self.__Shape.Faces[face_idx].Edges:
        c_edg_found = True
        type_str = str(s_edge.Curve)
        if type_str.find('Line') == -1:
          c_edg_found = False
          # SMLog("found circle in c_edge search")
        else:
          # SMLog("found line in c_edge search")
          for E_vert in s_edge.Vertexes:
            if equal_vertex(E_vert, P_edge.Vertexes[0]):
              c_edg_found = False
        if c_edg_found:
          c_edge = s_edge
          number_c_edges = number_c_edges + 1
          # SMLog(" found the second Line edge of the bend face")
          # Part.show(c_edge)
      if number_c_edges > 1:
        newNode.analysis_ok = False # the code can not handle bend faces with more than one child!
        newNode.error_code = 12 # ('more than one bend-childs')
        self.error_code = 12
        self.failed_face_idx = face_idx

      #Start to investigate the angles at self.__Shape.Faces[face_idx].ParameterRange[0]
      angle_0 = self.__Shape.Faces[face_idx].ParameterRange[0]
      angle_1 = self.__Shape.Faces[face_idx].ParameterRange[1]
      length_0 = self.__Shape.Faces[face_idx].ParameterRange[2]
      length_1 = self.__Shape.Faces[face_idx].ParameterRange[3]
      
      # idea: identify the angle at edge_vec = P_edge.Vertexes[0].copy().Point
      # This will be = angle_start
      # identify rotSign from angle_end minus angle_start
      # The tangentvector will be in direction of position at angle_sta + rotSign*90°
      # calculate the tan_vec from valueAt
      parPos00 = self.__Shape.Faces[face_idx].valueAt(angle_0,length_0)
      parPos01 = self.__Shape.Faces[face_idx].valueAt(angle_0,length_1)
      parPos10 = self.__Shape.Faces[face_idx].valueAt(angle_1,length_0)
      parPos11 = self.__Shape.Faces[face_idx].valueAt(angle_1,length_1)
      
      if equal_vector(edge_vec, parPos00):
        SMLog("got case 00")
        angle_start = angle_0
        angle_end = angle_1
        len_start = length_0
      else:
        if equal_vector(edge_vec, parPos01):
          SMLog("got case 01")
          angle_start = angle_0
          angle_end = angle_1
          len_start = length_1
        else:
          if equal_vector(edge_vec, parPos10):
            SMLog("got case 10")
            angle_start = angle_1
            angle_end = angle_0
            len_start = length_0
          else:
            if equal_vector(edge_vec, parPos11):
              SMLog("got case 11")
              angle_start = angle_1
              angle_end = angle_0
              len_start = length_1
            else:
              newNode.analysis_ok = False
              newNode.error_code = 16 # Analysis: did not find startangle of bend
              self.error_code = 16
              self.failed_face_idx = face_idx
              SMError("did not found start angle, to do to fix")
        
      newNode.bend_angle = angle_end - angle_start
      if newNode.bend_angle < 0.0:
        angle_tan = angle_start - math.pi/2.0
        # newNode.bend_angle = -newNode.bend_angle
      else:
        angle_tan = angle_start + math.pi/2.0
      tanPos = self.__Shape.Faces[face_idx].valueAt(angle_tan,len_start)
      tan_vec = radial_vector(tanPos, s_Center, s_Axis)
      newNode.tan_vec = tan_vec
        
      first_vec = radial_vector(edge_vec, s_Center, s_Axis)
      cross_vec = first_vec.cross(tan_vec)
      triple_prod = cross_vec.dot(s_Axis)
      SMLog(" the new bend_angle: ", math.degrees(newNode.bend_angle), "triple_prod: ", triple_prod)
      # testing showed, that the bend_angle has to be changed in sign
      # at the following conditions.
      if ((triple_prod > 0.0) and (newNode.bend_angle > 0.0)) or \
        ((triple_prod < 0.0) and (newNode.bend_angle < 0.0)):
        newNode.bend_angle = -newNode.bend_angle
        SMLog("minus bend_angle")



      if newNode.bend_dir == 'up':
        k_Factor = 0.65 + 0.5*math.log10(self.__Shape.Faces[face_idx].Surface.Radius/self.__thickness)
        SMLog("Face", newNode.idx+1, " k-factor up: ", k_Factor)
        newNode._trans_length = (self.__Shape.Faces[face_idx].Surface.Radius + k_Factor * self.__thickness/2.0) * newNode.bend_angle
      else:
        k_Factor = 0.65 + 0.5*math.log10((self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness)/self.__thickness)
        SMLog("Face", newNode.idx+1, " k-factor: ", k_Factor)
        newNode._trans_length = (self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness \
                                  + k_Factor * self.__thickness/2.0) * newNode.bend_angle
      if newNode._trans_length < 0.0:
        newNode._trans_length = -newNode._trans_length
        # the _trans_length is always positive, due to correct tan_vec


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

          #SMLog("found counter Face", such_list[i]+1)
          newNode.c_face_idx = i
          self.index_list.remove(i)
          
          newNode.nfIndexes.append(i)
          # Part.show(self.__Shape.Faces[newNode.c_face_idx])
          break

    # Part.show(self.__Shape.Faces[newNode.c_face_idx])
    # Part.show(self.__Shape.Faces[newNode.idx])
    if newNode.c_face_idx == None:
      newNode.analysis_ok = False
      newNode.error_code = 13 # Analysis: counter face not found
      self.error_code = 13
      self.failed_face_idx = face_idx
      SMError("No counter-face Debugging Thickness: ", self.__thickness)
      Part.show(self.__Shape.Faces[face_idx])

    # now we call the new code
    self.get_node_faces(newNode, wires_e_lists)
    #for nFace in newNode.nfIndexes:
    #  Part.show(nFace)


    if P_node == None:
      self.root = newNode
    else:
      P_node.child_list.append(newNode)
    return newNode




  def search_face(self, sf_edge, the_node):
    # search for the connecting face to sf_edge in the faces of a node
    search_List = the_node.nfIndexes[:]
    search_List.remove(the_node.idx)
    the_index = None
    for i in search_List:     #self.index_list:
      for n_edge in self.f_list[i].Edges:
        if sf_edge.isSame(n_edge):
          the_index = i
          
    #if the_index == None:
    #  the_node.analysis_ok = False # the code can not handle? edges without neighbor faces
    #  the_node.error_code = 14 # Analysis: the code can not handle? edges without neighbor faces
    #  self.error_code = 14
    #  self.failed_face_idx = the_node.idx
      
    return the_index


  def Bend_analysis(self, face_idx, parent_node = None, parent_edge = None):
    # This functions traverses the shape in order to build the bend-tree
    # For each relevant face a t_node is created and linked into the tree
    # the linking is done in the call of self.make_new_face_node
    #SMLog("Bend_analysis Face", face_idx +1 )
    # analysis_ok = True # not used anymore? 
    # edge_list = []
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
      SMLog(" Parent Face", parent_node.idx + 1)
    SMLog("Die Liste: ", self.index_list)
    t_node = self.make_new_face_node(face_idx, parent_node, parent_edge, wires_edge_lists)
    # Need also the edge_list in the node!
    SMLog("Die Liste nach make_new_face_node: ", self.index_list)
    
    # in the new code, only the list of child faces will be analyzed.
    removalList = []
    for child_info in t_node.child_idx_lists:
      if child_info[0] in self.index_list:
        SMLog("child in List: ", child_info[0])
        self.Bend_analysis(child_info[0], t_node, child_info[1])
      else:
        SMLog("remove child from List: ", child_info[0])
        t_node.seam_edges.append(child_info[1]) # give Information to the node, that it has a seam.
        SMLog("node faces before: ", t_node.nfIndexes)
        self.makeSeamFace(child_info[1], t_node)
        removalList.append(child_info)
        SMLog("node faces with seam: ", t_node.nfIndexes)
        otherSeamNode = self.searchNode(child_info[0], self.root)
        SMLog("counterface on otherSeamNode: Face", otherSeamNode.c_face_idx+1)
        self.makeSeamFace(child_info[1], otherSeamNode)
        #t_node.analysis_ok = False # the code can not handle? edges without neighbor faces
        #t_node.error_code = 14 # Analysis: the code can not handle? edges without neighbor faces
        #self.error_code = 14
        #self.failed_face_idx = t_node.idx
        #break
    for seams in removalList:
      t_node.child_idx_lists.remove(seams)
      
  
  
  def searchNode(self, theIdx, sNode):
    # search for a Node with theIdx in sNode.idx
    SMLog("my Idx: ", sNode.idx)

    if sNode.idx == theIdx:
      return sNode
    else:
      result = None
      childFaces = []
      for n_node in sNode.child_list:
        childFaces.append(n_node.idx)
      SMLog("my children: ", childFaces)
      
      for n_node in sNode.child_list:
        nextSearch = self.searchNode(theIdx, n_node)
        if nextSearch <> None:
          result = nextSearch
          break
    if result<>None:
      SMLog("this is the result: ", result.idx)
    else:
      SMLog("this is the result: ", None)
    
    return result
    
    # suche bei mir. wenn ja liefere ab
    # sonst sind Kinder da?
    # Wenn Kinder vorhanden, frag solange Kinder bis gefunden
    # oder kein Kind mehr da.


    
    


  def makeSectionWire(self, theEdge, W_node, Dir = 'up'):
    #SMLog("mSW Face", W_node.idx +1)
    # makes a Section wire through the shape
    # The section wire is used to generate a new flat shell
    # for the bend faces. 
    origin = theEdge.Vertexes[0].Point
    o_vec = theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point
    o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z) 
    o_thick.normalize().multiply(2.0 * self.__thickness)

    s_Center = self.f_list[W_node.idx].Surface.Center
    s_Axis = self.f_list[W_node.idx].Surface.Axis
    vec1 = radial_vector(origin, s_Center, s_Axis)
    vec1.multiply(self.__thickness)
    
    # defining the points of the section plane:
    if W_node.bend_dir == 'up':
      Spnt1 = origin - vec1 - o_thick
      Spnt2 = origin - vec1 + o_vec + o_thick
      Spnt3 = origin +  vec1 +  vec1 + o_vec + o_thick
      Spnt4 = origin +  vec1 +  vec1 - o_thick
    else:
      Spnt4 = origin - vec1 - vec1 - o_thick
      Spnt3 = origin - vec1 - vec1 + o_vec + o_thick
      Spnt2 = origin +  vec1  + o_vec + o_thick
      Spnt1 = origin +  vec1 - o_thick

    Sedge1 = Part.makeLine(Spnt1,Spnt2)
    Sedge2 = Part.makeLine(Spnt2,Spnt3)
    Sedge3 = Part.makeLine(Spnt3,Spnt4)
    Sedge4 = Part.makeLine(Spnt4,Spnt1)
        
    Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
    Sf1=Part.Face(Sw1) # 
    # Part.show(Sf1)
    
    # find the nearest vertex of theEdge to a plane through s_Center
    # The section-wire should start at this vertex
    if (theEdge.Vertexes[0].Point.distanceToPlane(s_Center, s_Axis) <
        theEdge.Vertexes[1].Point.distanceToPlane(s_Center, s_Axis)):
      next_pnt = theEdge.Vertexes[1]
      start_pnt = theEdge.Vertexes[0]
      start_idx = 0
      end_idx = 1
    else:
      next_pnt = theEdge.Vertexes[0]
      start_pnt = theEdge.Vertexes[1]
      start_idx = 1
      end_idx = 0

    # for i in self.index_list:    
    for i in W_node.nfIndexes:
      singleEdge = Sf1.section(self.f_list[i])
      # Part.show(singleEdge)
      #SMLog("section edges: ", len(singleEdge.Edges))
      for j in range(len(singleEdge.Edges)):
        if (equal_vertex(singleEdge.Edges[j].Vertexes[0], start_pnt)):
          lastEdge = singleEdge.Edges[j].copy()
          lastConnect = 1
        if (equal_vertex(singleEdge.Edges[j].Vertexes[1], start_pnt)):
          lastEdge = singleEdge.Edges[j].copy()
          lastConnect = 0
      
        if (equal_vertex(singleEdge.Edges[j].Vertexes[0], next_pnt)):
          nextEdge = singleEdge.Edges[j].copy()
          nextConnect = 1
        if (equal_vertex(singleEdge.Edges[j].Vertexes[1], next_pnt)):
          nextEdge = singleEdge.Edges[j].copy()
          nextConnect = 0
    
    startEdge = Part.makeLine(start_pnt.Point, next_pnt.Point)
    middleEdge = Part.makeLine(nextEdge.Vertexes[nextConnect].Point, lastEdge.Vertexes[lastConnect].Point)
    
    Swire1 = Part.Wire([startEdge, nextEdge, middleEdge, lastEdge ])
    # Part.show(Swire1)
      
    SMLog("finisch mSW Face", W_node.idx +1)
    return Swire1
    
    
    


  def generateBendShell(self, bend_node):
    #SMLog("genBendShell Face", bend_node.idx +1)
    # make new flat faces for the bend_node and return them
    # the k-Factor is already included in bend_node._trans_length
    
    # Part.show(self.__Shape.copy())
    flat_shell = []
      
    trans_vec = bend_node.tan_vec * bend_node._trans_length

    # o_edge: originating edge of the bend = parent edge
    o_edge = bend_node.p_edge.copy()
    # We want a section wire at the start of the bend_node, in order
    # to regenerate a flat body with this section wire.
    # 3 vectors are needed to generate a section plane: vec1 and 
    # a vector from o_edge and a vector with same direction of o_edge,
    # but with a length of two times the thickness
    o_wire = self.makeSectionWire(o_edge, bend_node, bend_node.bend_dir)
    #Part.show(o_wire)

    
    # The same vectors are needed for the other side of the bend face
    if len(bend_node.child_list)>=1:
      child_node = bend_node.child_list[0] # fixme: there could be more than one child node for a bend face.
      # bend_edge = bend_node.edge_pool[child_node.idx][0] 
      bend_edge = child_node.p_edge.copy()

      b_wire = self.makeSectionWire(bend_edge, bend_node, bend_node.bend_dir).copy()
      
    else:
      number_c_edges = 0
      for s_edge in self.f_list[bend_node.idx].Edges:
        c_edg_found = True
        type_str = str(s_edge.Curve)
        if type_str.find('Line') == -1:
          c_edg_found = False
          SMLog("found circle in c_edge search in bend Face", bend_node.idx+1)
        else:
          SMLog("found line in c_edge search in bend Face", bend_node.idx+1)
          for E_vert in s_edge.Vertexes:
            if equal_vertex(E_vert, bend_node.p_edge.Vertexes[0]):
              c_edg_found = False
        if c_edg_found:
          bend_edge = s_edge
          number_c_edges = number_c_edges + 1
          SMLog(" found the second Line edge of the bend Face", bend_node.idx+1)
          #Part.show(bend_edge)
      
      
      
      
      
      
      t_idx = self.search_face(bend_edge, bend_node)
      # Part.show(self.f_list[t_idx])
      if t_idx <> None:
        topFace = self.f_list[t_idx].copy()
        topFace.rotate(self.f_list[bend_node.idx].Surface.Center,bend_node.axis,math.degrees(bend_node.bend_angle))
        topFace.translate(trans_vec)
        flat_shell.append(topFace)
        

        s_Center = self.f_list[bend_node.idx].Surface.Center
        s_Axis = self.f_list[bend_node.idx].Surface.Axis

        # find the nearest vertex of bend_edge to a plane through s_Center
        # The section-wire should start at this vertex
        if (bend_edge.Vertexes[0].Point.distanceToPlane(s_Center, s_Axis) <
            bend_edge.Vertexes[1].Point.distanceToPlane(s_Center, s_Axis)):
          next_pnt = bend_edge.Vertexes[1].Point
          start_pnt = bend_edge.Vertexes[0].Point
          start_idx = 0
          end_idx = 1
        else:
          next_pnt = bend_edge.Vertexes[0].Point
          start_pnt = bend_edge.Vertexes[1].Point
          start_idx = 1
          end_idx = 0
    
        b_wireList = self.f_list[t_idx].Edges[:]
        #for remEdge in b_wireList:
        #  SMLog("in b_wireList")
        #  Part.show(remEdge)

        for remEdge in b_wireList:
          # Part.show(remEdge)
          if remEdge.isSame(bend_edge):
            b_wireList.remove(remEdge)
            break
        
        for singleEdge in b_wireList:
          #Part.show(singleEdge)
          # SMLog("section edges: ", len(singleEdge.Edges))
          if len(singleEdge.Edges) == 1:
            if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[0].Point, start_pnt)):
              lastEdge = singleEdge.Edges[0].copy()
              lastConnect = 1
            if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[1].Point, start_pnt)):
              lastEdge = singleEdge.Edges[0].copy()
              lastConnect = 0
          
            if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[0].Point, next_pnt)):
              nextEdge = singleEdge.Edges[0].copy()
              nextConnect = 1
            if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[1].Point, next_pnt)):
              nextEdge = singleEdge.Edges[0].copy()
              nextConnect = 0
        
        startEdge = Part.makeLine(start_pnt, next_pnt)
        middleEdge = Part.makeLine(nextEdge.Vertexes[nextConnect].Point, lastEdge.Vertexes[lastConnect].Point)
        
        b_wire = Part.Wire([startEdge, nextEdge, middleEdge, lastEdge ])
        # Part.show(Swire1)
        
      else:
        SMLog("Found no Face?!")
        # there is a seam in the metal sheet. 
        # Generate a new face for the seam.
        '''
        b_wire = self.makeSectionWire(bend_edge, bend_node, bend_node.bend_dir).copy()
        topFace = Part.Face(b_wire)
        #self.f_list.append(topFace)
        topFace.rotate(self.f_list[bend_node.idx].Surface.Center,bend_node.axis,math.degrees(bend_node.bend_angle))
        topFace.translate(trans_vec)
        flat_shell.append(topFace)
        '''
        
        '''
        # find the nearest vertex of bend_edge to a plane through s_Center
        # The section-wire should start at this vertex
        if (bend_edge.Vertexes[0].Point.distanceToPlane(s_Center, s_Axis) <
            bend_edge.Vertexes[1].Point.distanceToPlane(s_Center, s_Axis)):
          next_pnt = bend_edge.Vertexes[1].Point
          start_pnt = bend_edge.Vertexes[0].Point
          start_idx = 0
          end_idx = 1
        else:
          next_pnt = bend_edge.Vertexes[0].Point
          start_pnt = bend_edge.Vertexes[1].Point
          start_idx = 1
          end_idx = 0
        # find the nextEdge in the node faces
        
        search_List = bend_node.nfIndexes[:]
        search_List.remove(bend_node.idx)
        the_index = None
        next_idx = None
        for i in search_List:
          for theEdge in self.f_list[i].Edges:
            if len(theEdge.Vertexes)>1:
              if equal_vector(theEdge.Vertexes[0].Point, next_pnt):
                next_idx = 1
              if equal_vector(theEdge.Vertexes[1].Point, next_pnt):
                next_idx = 0
              if next_idx <> None:
                if self.isVertOpposite(theEdge.Vertexes[next_idx], bend_node):
                  nextEdge = theEdge.copy()
                  search_List.remove(i)
                  the_index = i
                  break
                else:
                  next_idx = None
          if the_index <> None:
            break

        #find the lastEdge
        last_idx = None
        for i in search_List:
          for theEdge in self.f_list[i].Edges:
            if len(theEdge.Vertexes)>1:
              if equal_vector(theEdge.Vertexes[0].Point, start_pnt):
                last_idx = 1
              if equal_vector(theEdge.Vertexes[1].Point, start_pnt):
                last_idx = 0
              if last_idx <> None:
                if self.isVertOpposite(theEdge.Vertexes[last_idx], bend_node):
                  lastEdge = theEdge.copy()
                  search_List.remove(i)
                  the_index = i
                  break
                else:
                  last_idx = None
          if the_index <> None:
            break
            
        # find the middleEdge
        for theEdge in self.f_list[bend_node.c_face_idx].Edges:
          if len(theEdge.Vertexes)>1:
            if equal_vector(theEdge.Vertexes[0].Point, start_pnt):
              last_idx = 1
            if equal_vector(theEdge.Vertexes[1].Point, start_pnt):
              last_idx = 0
            if last_idx <> None:
              if self.isVertOpposite(theEdge.Vertexes[last_idx], bend_node):
                lastEdge = theEdge.copy()
                search_List.remove(i)
                the_index = i
                break
              else:
                last_idx = None
        '''


    b_wire.rotate(self.f_list[bend_node.idx].Surface.Center,bend_node.axis,math.degrees(bend_node.bend_angle))
    b_wire.translate(trans_vec)
    
    #Part.show(b_wire)
    #for vert in b_wire.Vertexes:
    #  SMLog("b_wire1 tol: ", vert.Tolerance)
    
    #for ed in b_wire.Edges:
    #  SMLog("b_wire1 tol: ", ed.Vertexes[0].Tolerance, " ", ed.Vertexes[1].Tolerance)
      
    #sweep_path = Part.makeLine(o_wire.Vertexes[0].Point, b_wire.Vertexes[0].Point)
    #Part.show(sweep_path)

    Bend_shell = Part.makeRuledSurface (o_wire, b_wire)  #changed
    # Part.show(Bend_shell)
        
    for shell_face in Bend_shell.Faces:  #changed
      flat_shell.append(shell_face )     #changed

    #for i in range(len(o_wire.Edges)) :
    #  flat_shell.append(self.MakeFace(o_wire.Edges[i], b_wire.Edges[i]))

    #Part.show(self.__Shape.copy())
    #SMLog("finish genBendShell Face", bend_node.idx +1)

    return flat_shell

  def MakeFace(self, e1, e2):
    e3 = Part.makeLine(e1.valueAt(e1.FirstParameter), e2.valueAt(e2.FirstParameter))
    e4 = Part.makeLine(e1.valueAt(e1.LastParameter), e2.valueAt(e2.LastParameter))
    w = Part.Wire([e1,e3,e2,e4])
    return Part.Face(w)


  def makeSeamFace(self, sEdge, theNode):
    ''' This function creates a face at a seam of the sheet metal.
    It works currently only at a flat node.
    '''
    SMLog("now make a seam Face")
    nextVert = sEdge.Vertexes[1]
    startVert = sEdge.Vertexes[0]
    start_idx = 0
    end_idx = 1
    
    search_List = theNode.nfIndexes[:]
    SMLog("This is the search_List: ", search_List)
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
          if next_idx <> None:
            if self.isVertOpposite(theEdge.Vertexes[next_idx], theNode):
              nextEdge = theEdge.copy()
              search_List.remove(i)
              the_index = i
              #Part.show(nextEdge)
              break
            else:
              next_idx = None
      if the_index <> None:
        break

    #find the lastEdge
    last_idx = None
    SMLog("This is the search_List: ", search_List)
    for i in search_List:
      #Part.show(self.f_list[i])
      for theEdge in self.f_list[i].Edges:
        SMLog("find last Edge in Face: ", i, " at Edge: ", theEdge)
        if len(theEdge.Vertexes)>1:
          if equal_vertex(theEdge.Vertexes[0], startVert):
            last_idx = 1
          if equal_vertex(theEdge.Vertexes[1], startVert):
            last_idx = 0
          if last_idx <> None:
            SMLog("test for the last Edge")
            if self.isVertOpposite(theEdge.Vertexes[last_idx], theNode):
              lastEdge = theEdge.copy()
              search_List.remove(i)
              the_index = i
              #Part.show(lastEdge)
              break
            else:
              last_idx = None
      if last_idx <> None:
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
        if mid_idx <> None:
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
    #SMLog("unfold_tree face", node.idx + 1)
    theShell = []
    nodeShell = []
    for n_node in node.child_list:
      if self.error_code == None:
        theShell = theShell + self.unfold_tree2(n_node)
    if node.node_type == 'Bend':
      trans_vec = node.tan_vec * node._trans_length
      for bFaces in theShell:
        bFaces.rotate(self.f_list[node.idx].Surface.Center,node.axis,math.degrees(node.bend_angle))
        bFaces.translate(trans_vec)
      if self.error_code == None:
        nodeShell = self.generateBendShell(node)
    else:
      if self.error_code == None:
        # nodeShell = self.generateShell(node)
        for idx in node.nfIndexes:
          nodeShell.append(self.f_list[idx].copy())
        #if len(node.seam_edges)>0:
        #  for seamEdge in node.seam_edges:
        #    self.makeSeamFace(seamEdge, node)
    SMLog("ufo finish face",node.idx +1)
    return (theShell + nodeShell)





def PerformUnfold():
  mylist = Gui.Selection.getSelectionEx()
  resPart = None
  # SMLog('Die Selektion: ',mylist)
  # SMLog('Zahl der Selektionen: ', mylist.__len__())

  if mylist.__len__() == 0:
    mw=FreeCADGui.getMainWindow()
    QtGui.QMessageBox.information(mw,"Error","""One flat face needs to be selected!""")
  else:
    if mylist.__len__() > 1:
      mw=FreeCADGui.getMainWindow()
      QtGui.QMessageBox.information(mw,"Error","""Only one flat face has to be selected!""")
    else:
      o = Gui.Selection.getSelectionEx()[0]
      SMLog(o.ObjectName)
      if len(o.SubObjects)>1:
        mw=FreeCADGui.getMainWindow()
        QtGui.QMessageBox.information(mw,"SubelementError","""Only one flat face has to be selected!""")
      else:
        subelement = o.SubObjects[0]
        if hasattr(subelement,'Surface'):
          s_type = str(subelement.Surface)
          if s_type == "<Plane object>":
            mw=FreeCADGui.getMainWindow()
            #QtGui.QMessageBox.information(mw,"Hurra","""Lets try unfolding!""")
            SMLog("name: ",subelement)
            f_number = int(o.SubElementNames[0].lstrip('Face'))-1
            #SMLog(f_number)
            startzeit = time.clock()
            TheTree = SheetTree(o.Object.Shape, f_number) # initializes the tree-structure
            if TheTree.error_code == None:
              TheTree.Bend_analysis(f_number, None) # traverses the shape builds the tree-structure
              endzeit = time.clock()
              SMLog("Analytical time: ",endzeit-startzeit)
              
              if TheTree.error_code == None:
                # TheTree.showFaces()
                theFaceList = TheTree.unfold_tree2(TheTree.root) # traverses the tree-structure
                if TheTree.error_code == None:
                  unfoldTime = time.clock()
                  SMLog("time to run the unfold: ", unfoldTime - endzeit)

                  try:
                      newShell = Part.Shell(theFaceList)
                  except:
                      SMError("couldn't join some faces, show only single faces")
                      for newFace in theFaceList:
                        if (resPart == None):
                          resPart = newFace
                        else:
                          resPart = resPart.fuse(newFace)
                  else:
                    
                    try:
                        TheSolid = Part.Solid(newShell)
                        solidTime = time.clock()
                        SMLog("time to make the solid: ", solidTime - unfoldTime)
                    except:
                        SMError("couldn't make a solid, show only a shell, Faces in List: ", len(theFaceList)) 
                        resPart = newShell
                        showTime = time.clock()
                        SMLog("Show time: ", showTime - unfoldTime)
                    else:
                        resPart = TheSolid
                        showTime = time.clock()
                        SMLog("Show time: ", showTime - solidTime, " total time: ", showTime - startzeit)
            
            if TheTree.error_code <> None:
              SMError("Error ", unfold_error[TheTree.error_code], " at Face", TheTree.failed_face_idx+1)
              QtGui.QMessageBox.information(mw,"Error",unfold_error[TheTree.error_code])
            else:
              SMMessage("unfold successful")

                    
          else:
            mw=FreeCADGui.getMainWindow()
            QtGui.QMessageBox.information(mw,"Selection Error","""Sheet UFO works only with a flat face as starter!\n Select a flat face.""")
        else:
          mw=FreeCADGui.getMainWindow()
          QtGui.QMessageBox.information(mw,"Selection Error","""Sheet UFO works only with a flat face as starter!\n Select a flat face.""")
  return resPart


class SMUnfoldObject:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    obj.Proxy = None
    self.isOk = True

  def execute(self, fp):
    s = PerformUnfold()
    if (s != None):
      fp.Shape = s
      self.isOk = True
    else:
      self.isOk = False
    


class SMUnfoldCommandClass():
  """Unfold object"""

  def GetResources(self):
    __dir__ = os.path.dirname(__file__)
    iconPath = os.path.join( __dir__, 'Resources', 'icons' )
    return {'Pixmap'  : os.path.join( iconPath , 'SMUnfold.svg') , # the name of a svg file available in the resources
            'MenuText': "Unfold" ,
            'ToolTip' : "Flatten folded sheet metal object"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    s = PerformUnfold()
    if (s != None):
      doc.openTransaction("Unfold")
      a = doc.addObject("Part::Feature","Unfold")
      a.Shape = s
      doc.commitTransaction()
    doc.recompute()
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

