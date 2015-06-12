#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  sheet_ufo.py
#  
#  Copyright 2014 Ulrich Brammer <ulrich1a[at]users.sourceforge.net>
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
import DraftVecUtils, DraftGeomUtils, math


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
  16: ('Analysis: '), 
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

def radial_vector(point, axis_pnt, axis):
  chord = axis_pnt.sub(point)
  norm = axis.cross(chord)
  perp = axis.cross(norm)
  # SMLog (chord, norm, perp)
  dist_rv = DraftVecUtils.project(chord,perp)
  #test_line = Part.makeLine(axis_pnt.add(dist_rv),axis_pnt)
  # test_line = Part.makeLine(axis_pnt.add(perp),axis_pnt)
  # test_line = Part.makeLine(point, axis_pnt)
  # Part.show(test_line)
  return perp.normalize()





class Simple_node(object):
  def __init__(self, f_idx=None, Parent_node= None, Parent_edge = None):
    self.idx = f_idx  # index of the "top-face"
    self.c_face_idx = None # face index to the opposite face of the sheet
    self.node_type = None  # 'Flat' or 'Bend'
    self.p_node = Parent_node   # Parent node
    self.p_edge = Parent_edge # the connecting edge to the parent node
    self.child_list = [] # List of child-nodes
    self.sheet_edges = [] # List of edges without child-face 
    self.axis = None 
    # self.axis for 'Flat'-face: vector pointing from the surface into the metal
    self.bend_dir = None # bend direction values: "up" or "down"
    self.bend_angle = None # angle in radians
    self.tan_vec = None # direction of translation for Bend nodes
    self._trans_length = None # length of translation for Bend nodes, k-factor used according to DIN 6935
    self.analysis_ok = True # indicator if something went wrong with the analysis of the face
    self.error_code = None # index to unfold_error dictionary

  def get_Face_idx(self):
    # get the face index from the tree-element
    return self.idx





class SheetTree(object):
  def __init__(self, TheShape, f_idx):
    self.cFaceTol = 0.002 # tolerance to detect counter-face vertices
    # this high tolerance was needed for more real parts
    self.root = None
    self.__Shape = TheShape.copy()
    self.error_code = None
    self.failed_face_idx = None
    
    if not self.__Shape.isValid():
      SMError ("The shape is not valid!")
      self.error_code = 4  # Starting: invalid shape
      self.failed_face_idx = f_idx
    
    #Part.show(self.__Shape)
    
    # List of indices to the shape.Faces. The list is used a lot for face searches.
    self.index_list =[] 
    for i in range(len (self.__Shape.Faces)):
      # if i<>(f_idx):
      self.index_list.append(i)
    #SMLog (self.index_list)

    theVol = self.__Shape.Volume
    if theVol < 0.0001:
      SMError ("Shape is not a real 3D-object or to small for a metal-sheet!")
      self.error_code = 1
      self.failed_face_idx = f_idx

    else:
      # Make a first estimate of the thickness
      estimated_thickness = theVol/(self.__Shape.Area / 2.0)
      SMLog ("approximate Thickness: ", estimated_thickness)
      # Measure the real thickness of the initial face: Use Orientation and
      # Axis to make an measurement vector
      
    
      if hasattr(self.__Shape.Faces[f_idx],'Surface'):
        # Part.show(self.__Shape.Faces[f_idx])
        # SMLog ('the object is a face! vertices: ', len(self.__Shape.Faces[f_idx].Vertexes))
        F_type = self.__Shape.Faces[f_idx].Surface
        # fixme: through an error, if not Plane Object
        SMLog ('It is a: ' , str(F_type))
        SMLog ('Orientation: ' , str(self.__Shape.Faces[f_idx].Orientation))
        
        # Need a point on the surface to measure the thickness.
        # Sheet edges could be sloping, so there is a danger to measure
        # right at the edge. 
        # Try with Arithmetic mean of plane vertices
        m_vec = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
        for Vvec in self.__Shape.Faces[f_idx].Vertexes:
            #m_vec = m_vec.add(Base.Vector(Vvec.X, Vvec.Y, Vvec.Z))
            m_vec = m_vec.add(Vvec.Point)
        mvec = m_vec.multiply(1.0/len(self.__Shape.Faces[f_idx].Vertexes))
        SMLog ("mvec: " , mvec)
        
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
            SMError ("Starting measure_pos for thickness measurement is outside!")
            self.error_code = 2
            self.failed_face_idx = f_idx

        
        if hasattr(self.__Shape.Faces[f_idx].Surface,'Axis'):
          s_Axis =  self.__Shape.Faces[f_idx].Surface.Axis
          # SMLog ('We have an axis: ' , s_Axis)
          if hasattr(self.__Shape.Faces[f_idx].Surface,'Position'):
            s_Posi = self.__Shape.Faces[f_idx].Surface.Position
            # SMLog ('We have a position: ' , s_Posi)
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
        SMLog ("lLine number edges: " , len(lLine.Edges))
        measVert = Part.Vertex(measure_pos)
        for mEdge in lLine.Edges:
          if equal_vertex(mEdge.Vertexes[0], measVert) or equal_vertex(mEdge.Vertexes[1], measVert):
            self.__thickness = mEdge.Length
        
        # self.__thickness = lLine.Length
        if (self.__thickness < estimated_thickness) or (self.__thickness > 1.9 * estimated_thickness):
          self.error_code = 3
          self.failed_face_idx = f_idx
          SMLog ("estimated thickness: " , estimated_thickness , " measured thickness: " , self.__thickness)
          Part.show(lLine)





  def make_new_face_node(self, face_idx, P_node, P_edge ):
    # analyze the face and get type of face
    # put the node into the tree
    newNode = Simple_node(face_idx, P_node, P_edge)
    F_type = str(self.__Shape.Faces[face_idx].Surface)
    
    # This face should be a node in the tree, and is therefore known!
    # removed from the list of all unknown faces
    self.index_list.remove(face_idx)
    # This means, it could also not be found as neighbor face anymore.

    such_list = [] 
    for k in range(len(self.index_list)):
      such_list.append(self.index_list[k])
    
    if F_type == "<Plane object>":
      newNode.node_type = 'Flat' # fixme
      SMLog ("Face" , face_idx+1 ,  " Type: ", newNode.node_type)

      s_Posi = self.__Shape.Faces[face_idx].Surface.Position
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
      for i in range(len(such_list)):
        counter_found = True
        for F_vert in self.__Shape.Faces[such_list[i]].Vertexes:
          vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
          dist_v = vF_vert.distanceToPlane (s_Posi, ext_Vec) - self.__thickness
          # SMLog ("counter face distance: ", dist_v + self.__thickness)
          if (dist_v > self.cFaceTol) or (dist_v < -self.cFaceTol):
              counter_found = False
  
        if counter_found:
          # nead a mean point of the face to avoid false counter faces
          counterMiddle = Base.Vector(0.0,0.0,0.0) # calculating a mean vector
          for Vvec in self.__Shape.Faces[such_list[i]].OuterWire.Vertexes:
              counterMiddle = counterMiddle.add(Vvec.Point)
          counterMiddle = counterMiddle.multiply(1.0/len(self.__Shape.Faces[such_list[i]].OuterWire.Vertexes))
          
          distVector = counterMiddle.sub(faceMiddle)
          counterDistance = distVector.Length
          
          if counterDistance < 3*self.__thickness:
            SMLog ("found counter-face", such_list[i]+1)
            newNode.c_face_idx = such_list[i]
            self.index_list.remove(such_list[i])
            # Part.show(self.__Shape.Faces[newNode.c_face_idx])
          else:
            counter_found = False
            SMLog ("faceMiddle: ", str(faceMiddle), "counterMiddle: ", str(counterMiddle))
      #if newNode.c_face_idx == None:
      #  Part.show(axis_line)
          
        

            
    if F_type == "<Cylinder object>":
      newNode.node_type = 'Bend' # fixme
      s_Center = self.__Shape.Faces[face_idx].Surface.Center
      s_Axis = self.__Shape.Faces[face_idx].Surface.Axis
      newNode.axis = s_Axis
      edge_vec = P_edge.Vertexes[0].copy().Point
      
      if P_node.node_type == 'Flat':
        dist_c = edge_vec.distanceToPlane (s_Center, P_node.axis) 
      else:
        P_face = self.__Shape.Faces[P_node.idx]
        radVector = radial_vector(edge_vec, P_face.Surface.Center, P_face.Surface.Axis)
        if P_node.bend_dir == "down":
          dist_c = edge_vec.distanceToPlane (s_Center, radVector.multiply(-1.0))
        else:
          dist_c = edge_vec.distanceToPlane (s_Center, radVector)
        '''  
        newNode.analysis_ok = False 
        newNode.error_code = 11  #Analysis: double bends not implemented
        self.error_code = 11
        self.failed_face_idx = face_idx
        SMError ("Error: Bend directly following a bend not implemented!")
        '''
      if dist_c < 0.0:
        newNode.bend_dir = "down"
        thick_test = self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness
      else:
        newNode.bend_dir = "up"
        thick_test = self.__Shape.Faces[face_idx].Surface.Radius + self.__thickness
      # SMLog ("Face idx: ", face_idx, " bend_dir: ", newNode.bend_dir)
      SMLog ("Face", face_idx+1, " Type: ", newNode.node_type, " bend_dir: ", newNode.bend_dir)
      
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
          # SMLog ("found circle in c_edge search")
        else:
          # SMLog ("found line in c_edge search")
          for E_vert in s_edge.Vertexes:
            if equal_vertex(E_vert, P_edge.Vertexes[0]):
              c_edg_found = False
        if c_edg_found:
          c_edge = s_edge
          number_c_edges = number_c_edges + 1
          # SMLog (" found the second Line edge of the bend face")
          # Part.show(c_edge)
      if number_c_edges > 1:
        newNode.analysis_ok = False # the code can not handle bend faces with more than one child!
        newNode.error_code = 12 # ('more than one bend-childs')
        self.error_code = 12
        self.failed_face_idx = face_idx

      # Calculate the signed rotation angle
      vec1 = radial_vector(edge_vec, s_Center, s_Axis)
      vec2 = radial_vector(c_edge.Vertexes[0].Point, s_Center, s_Axis)
      #newNode.bend_angle = DraftVecUtils.angle(vec2, vec1, s_Axis)
      draftAngle = DraftVecUtils.angle(vec2, vec1, s_Axis)
      
      
      newNode.bend_angle = self.__Shape.Faces[face_idx].ParameterRange[1] \
        -self.__Shape.Faces[face_idx].ParameterRange[0]
      if (newNode.bend_angle < math.pi) and (newNode.bend_angle > -math.pi):
        if draftAngle * newNode.bend_angle < 0.0:
          newNode.bend_angle = -newNode.bend_angle
      else:
        if draftAngle * newNode.bend_angle > 0.0:
          newNode.bend_angle = -newNode.bend_angle
      
      SMLog ("Face_idx ", face_idx, " bend_angle ", math.degrees(newNode.bend_angle))
      tan_vec = vec1.cross(s_Axis)
      
      # Compare sign of the angle between vector vec3 and vec1 with the sign of the bend_angle
      vec3 = radial_vector(edge_vec + tan_vec, s_Center, s_Axis)
      test_angle = DraftVecUtils.angle(vec3, vec1, s_Axis)

      #vecTest = (edge_vec + tan_vec)
      #vec1_test = Part.makeLine(edge_vec, edge_vec.add(vec1))
      #Part.show(vec1_test)
      #angle_test = Part.makeLine(vecTest, vecTest.add(vec3))
      #Part.show(angle_test)
      
      if (test_angle * newNode.bend_angle) < 0.0:
        newNode.tan_vec = tan_vec.multiply(-1.0)
      else:
        newNode.tan_vec = tan_vec
        


      if newNode.bend_dir == 'up':
        k_Factor = 0.65 + 0.5*math.log10(self.__Shape.Faces[face_idx].Surface.Radius/self.__thickness)
        SMLog ("Face", newNode.idx+1, " k-factor: ", k_Factor)
        newNode._trans_length = (self.__Shape.Faces[face_idx].Surface.Radius + k_Factor * self.__thickness/2.0) * newNode.bend_angle
      else:
        k_Factor = 0.65 + 0.5*math.log10((self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness)/self.__thickness)
        newNode._trans_length = (self.__Shape.Faces[face_idx].Surface.Radius - self.__thickness \
                                  + k_Factor * self.__thickness/2.0) * newNode.bend_angle
      if newNode._trans_length < 0.0:
        newNode._trans_length = -newNode._trans_length
      tan_test = Part.makeLine(s_Center, s_Center.add(newNode.tan_vec + newNode.tan_vec + newNode.tan_vec))
      # Part.show(tan_test)
      
      SMLog ("angle: ", math.degrees(newNode.bend_angle)," test_angle: ", math.degrees(test_angle), " trans: ", newNode._trans_length)


      # calculate mean point of face:
      # fixme implement also for cylindric faces

      # Search the face at the opposite site of the sheet:
      for i in range(len(such_list)):
        counter_found = True
        for F_vert in self.__Shape.Faces[such_list[i]].Vertexes:
          vF_vert = Base.Vector(F_vert.X, F_vert.Y, F_vert.Z)
          dist_c = vF_vert.distanceToLine (s_Center, s_Axis) - thick_test
          if (dist_c > self.cFaceTol) or (dist_c < -self.cFaceTol):
            counter_found = False
  
        if counter_found:
          # calculate mean point of counter face
          
          
          
          
          SMLog ("found counter Face", such_list[i]+1)
          newNode.c_face_idx = such_list[i]
          self.index_list.remove(such_list[i])
          # Part.show(self.__Shape.Faces[newNode.c_face_idx])
          break

    # Part.show(self.__Shape.Faces[newNode.c_face_idx])
    # Part.show(self.__Shape.Faces[newNode.idx])
    if newNode.c_face_idx == None:
      newNode.analysis_ok = False
      newNode.error_code = 13 # Analysis: counter face not found
      self.error_code = 13
      self.failed_face_idx = face_idx
      SMLog ("No counter-face Debugging Thickness: ", self.__thickness)

    if P_node == None:
      self.root = newNode
    else:
      P_node.child_list.append(newNode)
    return newNode


  def analyzeSectionEdges(self, edList, startPnt):
    # search for a wire in edList starting at startPnt
    startVert = Part.Vertex(startPnt)
    wireList = []
    startEdge = None
    # searching the startEdge
    lastCon = None
    for edge in edList:
      if equal_vertex(edge.Vertexes[0], startVert, 3):
        lastCon = 1
        firstCon = 0
        startEdge = edge
      if len(edge.Vertexes) > 1:
        if equal_vertex(edge.Vertexes[1], startVert, 3):
          lastCon = 0
          firstCon = 1
          startEdge = edge
      # fixme remove edges with only one Vertex from edList
      if lastCon <> None:
        break
    if startEdge <> None:    
      wireList.append(startEdge)
      edList.remove(startEdge)
      # append connecting edges to wireList at point lastCon
      compVert = startEdge.Vertexes[lastCon]
      for i in range(len(edList)):
        for nextEdge in edList:
          if equal_vertex(nextEdge.Vertexes[0], compVert):
            wireList.append(nextEdge)
            edList.remove(nextEdge)
            compVert = nextEdge.Vertexes[1]
            break
          if equal_vertex(nextEdge.Vertexes[1], compVert):
            wireList.append(nextEdge)
            edList.remove(nextEdge)
            compVert = nextEdge.Vertexes[0]
            break
      # now look at the other side of startEdge
      compVert = startEdge.Vertexes[firstCon]
      for i in range(len(edList)):
        for nextEdge in edList:
          if equal_vertex(nextEdge.Vertexes[0], compVert):
            wireList.insert(0,nextEdge)
            edList.remove(nextEdge)
            compVert = nextEdge.Vertexes[1]
            break
          if equal_vertex(nextEdge.Vertexes[1], compVert):
            wireList.insert(0,nextEdge)
            edList.remove(nextEdge)
            compVert = nextEdge.Vertexes[0]
            break
          
    sectWire = Part.Wire(wireList)
    return sectWire



  def is_sheet_edge(self, ise_edge, tree_node):
    # analyzes ise_edge is at the edge of the metal sheet
    result = True
    # fixme test only for one common edge
    factor = self.__thickness/2.0
    sc = 1.4 # multiplicator for sec_circle
    # fixme: Axis for Bend face is parallel to face, works only with normal Axis of Flat face. 
    lookAt = (ise_edge.FirstParameter + ise_edge.LastParameter)/2.0
    ise_Posi = ise_edge.valueAt(lookAt)
    s_axis = ise_edge.tangentAt(lookAt)
    #if tree_node.idx == 151:
    #  Part.show(Part.Vertex(ise_Posi))
    #  SMLog ("ise_Posi: ", str(ise_Posi))
    
    
      
    F_type = str(self.__Shape.Faces[tree_node.idx].Surface)
    if F_type == "<Plane object>":
      halfThick = Base.Vector(tree_node.axis.x*factor,tree_node.axis.y*factor,tree_node.axis.z*factor)
      sec_circle = Part.makeCircle(self.__thickness*sc, ise_Posi+halfThick, s_axis)
      testAxis = Base.Vector(tree_node.axis.x, tree_node.axis.y, tree_node.axis.z)

    if F_type == "<Cylinder object>":
      a_pnt = self.__Shape.Faces[tree_node.idx].Surface.Center
      axi = self.__Shape.Faces[tree_node.idx].Surface.Axis
      r_vec = radial_vector(ise_Posi, a_pnt, axi)
      testAxis = Base.Vector(r_vec.x, r_vec.y, r_vec.z)
      r_vec.multiply(self.__thickness/2.0)
      # sec_circle = Part.makeCircle(self.__thickness*2.0, ise_Posi, s_axis) # fixme: make center of sec_circle at half the thickness of the sheet

      if tree_node.bend_dir == "down":
        thick_test = self.__Shape.Faces[tree_node.idx].Surface.Radius - self.__thickness
        sec_circle = Part.makeCircle(self.__thickness*sc, ise_Posi-r_vec, s_axis) # fixme: make center of sec_circle at half the thickness of the sheet
      else:
        thick_test = self.__Shape.Faces[tree_node.idx].Surface.Radius + self.__thickness
        sec_circle = Part.makeCircle(self.__thickness*sc, ise_Posi+r_vec, s_axis) # fixme: make center of sec_circle at half the thickness of the sheet


    s_wire = Part.Wire(sec_circle)
    sec_face = Part.Face(s_wire)
    #if tree_node.idx == 151:
    #  Part.show(sec_face)
    #lostShape = self.__Shape.copy()
    # Part.show(lostShape)
    #sect = sec_face.section(lostShape)
    
    sect = sec_face.section(self.__Shape)
    #if tree_node.idx == 151:
    #  Part.show(sect)

    foundWire = self.analyzeSectionEdges(sect.Edges, ise_Posi)
    if len(foundWire.Edges) == 0:
      Part.show(sec_face)
      tree_node.analysis_ok = False 
      tree_node.error_code = 10 # Analysis: zero wires in sheet edge analysis
      self.error_code = 10
      self.failed_face_idx = tree_node.idx

    if F_type == "<Cylinder object>":
      # Part.show(sec_face)
      SMLog ("cylinder radius: ", self.__Shape.Faces[tree_node.idx].Surface.Radius, "length/2: ", lookAt  / math.pi*4.0)
      SMLog ("Orientation: ", ise_edge.Orientation)

    
    if (len(sect.Edges) - len(foundWire.Edges)) <> 0:
      
      if F_type == "<Plane object>":
        if len(foundWire.Edges)> 2:
          # need to test, if there are 2 vertices in thickness distance
          vertCount = 0

          for verts in foundWire.Vertexes:
            v_verts = verts.Point
            dist_v = v_verts.distanceToPlane (ise_Posi, tree_node.axis) - self.__thickness
            if (dist_v < self.cFaceTol) and (dist_v > -self.cFaceTol):
              vertCount = vertCount + 1
              #SMLog ("got result ", dist_v, " ", ise_Posi, " ", verts.Point)
              #result = True
              
          if vertCount > 1:
            result = True
          else:
            result = False
          
        else:
          result = False

      if F_type == "<Cylinder object>":
        SMLog ("testing isSheetEdge edges in wire: ", len(foundWire.Edges))
        if len(foundWire.Edges)> 2:
          s_Center = self.__Shape.Faces[tree_node.idx].Surface.Center
          vertCount = 0
  
          for verts in foundWire.Vertexes:
            v_verts = verts.Point
            dist_c = v_verts.distanceToLine (s_Center, tree_node.axis) - thick_test
            if (dist_c < self.cFaceTol) and (dist_c > -self.cFaceTol):
              SMLog ("got cyl result ", dist_c, " ", ise_Posi, " ", verts.Point)
              vertCount = vertCount + 1
          if vertCount > 1:
            result = True
          else:
            result = False
          
        else:
          result = False
        
        
        
    else:
      result = True
      SMError ("only one wire in section!")
      # testAxis 

      neighborIdx = self.search_face(ise_edge, tree_node)
      nextF_type = str(self.__Shape.Faces[neighborIdx].Surface)
      
      if nextF_type == "<Plane object>":
        dotProd = testAxis.dot(self.__Shape.Faces[neighborIdx].Surface.Axis)
        if dotProd < 0.0:
          SMLog (" dotProd: ", dotProd)
          dotProd = -dotProd
        if (dotProd <1.001) and (dotProd > 0.999):
          result = False

    return result

  '''
  Blechkante in der Mitte mit Sektion Radius ca. 2 x Blechdicke quer schneiden: 
  nur eine geschlossene Kurve ist eine Blechkante.
  Tangenten mit TangentAt ermitteln.
  
  '''

  def is_sheet_edge2(self, ise_edge, tree_node):
    # another strategy to identify the sheet edge:
    # get the face which has a common edge with ise_edge
    # look if this face has a common edge with the counter-face of tree_node
    # does not work in case of overlapping up- and down-faces.
    the_index = None
    connection_to_counter_face = False
    for i in self.index_list:
      for sf_edge in self.__Shape.Faces[i].Edges:
        if sf_edge.isSame(ise_edge):
          the_index = i
          break
      if the_index <> None:
        break
          
    if the_index == None:
      tree_node.analysis_ok = False 
      tree_node.error_code = 15  # Analysis: the code needs a face at all sheet edges
      self.error_code = 15
      self.failed_face_idx = tree_node.idx
      Part.show(self.__Shape.Faces[tree_node.idx])
      
    else:
      for c_edge in self.__Shape.Faces[tree_node.c_face_idx].Edges:
        for side_edge in self.__Shape.Faces[the_index].Edges:
          if c_edge.isSame(side_edge):
            connection_to_counter_face = True
            break
            
    return connection_to_counter_face



  def search_face(self, sf_edge, the_node):
    # search for the connecting face to sf_edges in the faces
    the_index = None
    for i in self.index_list:
      for n_edge in self.__Shape.Faces[i].Edges:
        if sf_edge.isSame(n_edge):
          the_index = i
          
    if the_index == None:
      the_node.analysis_ok = False # the code can not handle? edges without neighbor faces
      the_node.error_code = 14 # Analysis: the code can not handle? edges without neighbor faces
      self.error_code = 14
      self.failed_face_idx = the_node.idx
      
    return the_index


  def Bend_analysis(self, face_idx, parent_node = None, parent_edge = None):
    # This functions traverses the shape in order to build the bend-tree
    # For each relevant face a t_node is created and linked into the tree
    # the linking is done in the call of self.make_new_face_node
    SMLog ("Bend_analysis Face", face_idx +1)
    # analysis_ok = True # not used anymore? 
    edge_list = []
    for n_edge in self.__Shape.Faces[face_idx].Edges:
      if parent_edge:
        if not parent_edge.isSame(n_edge):
          edge_list.append(n_edge)
        #
      else:
        edge_list.append(n_edge)

    if parent_node:
      SMLog (" Parent Face", parent_node.idx + 1)

    t_node = self.make_new_face_node(face_idx, parent_node, parent_edge)

    for n_edge in edge_list:
      if self.is_sheet_edge(n_edge, t_node):
      #if self.is_sheet_edge2(n_edge, t_node):
        t_node.sheet_edges.append(n_edge)
      else:
        next_face = self.search_face(n_edge, t_node)

        if (next_face <> None) and (self.error_code == None):
          self.Bend_analysis(next_face, t_node, n_edge)
      if self.error_code <> None: 
        break



    
    


  def makeSectionWire(self, theEdge, W_node, Dir = 'up'):
    SMLog ("mSW Face", W_node.idx +1)
    # makes a Section wire through the shape
    # The section wire is used to generate a new flat shell
    # for the bend faces. 
    origin = theEdge.Vertexes[0].Point
    o_vec = theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point
    o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z) 
    o_thick.normalize().multiply(2.0 * self.__thickness)

    s_Center = self.__Shape.Faces[W_node.idx].Surface.Center
    s_Axis = self.__Shape.Faces[W_node.idx].Surface.Axis
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

    
    for i in self.index_list:
      singleEdge = Sf1.section(self.__Shape.Faces[i])
      # Part.show(singleEdge)
      SMLog ("section edges: ", len(singleEdge.Edges))
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
      
    SMLog ("finisch mSW Face", W_node.idx +1)
    return Swire1
    
    
    


  def generateBendShell(self, bend_node):
    SMLog ("genBendShell Face", bend_node.idx +1)
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
      for s_edge in self.__Shape.Faces[bend_node.idx].Edges:
        c_edg_found = True
        type_str = str(s_edge.Curve)
        if type_str.find('Line') == -1:
          c_edg_found = False
          # SMLog ("found circle in c_edge search")
        else:
          # SMLog ("found line in c_edge search")
          for E_vert in s_edge.Vertexes:
            if equal_vertex(E_vert, bend_node.p_edge.Vertexes[0]):
              c_edg_found = False
        if c_edg_found:
          bend_edge = s_edge
          number_c_edges = number_c_edges + 1
          SMLog (" found the second Line edge of the bend face")
          #Part.show(bend_edge)

      t_idx = self.search_face(bend_edge, bend_node)
      #Part.show(self.__Shape.Faces[t_idx])
      if t_idx <> None:
        if t_idx in self.index_list:
          self.index_list.remove(t_idx)
          topFace = self.__Shape.Faces[t_idx].copy()
          topFace.rotate(self.__Shape.Faces[bend_node.idx].Surface.Center,bend_node.axis,math.degrees(bend_node.bend_angle))
          topFace.translate(trans_vec)
          flat_shell.append(topFace)
          

          s_Center = self.__Shape.Faces[bend_node.idx].Surface.Center
          s_Axis = self.__Shape.Faces[bend_node.idx].Surface.Axis

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
      
          b_wireList = self.__Shape.Faces[t_idx].Edges[:]
          #for remEdge in b_wireList:
          #  SMLog ("in b_wireList")
          #  Part.show(remEdge)

          for remEdge in b_wireList:
            # Part.show(remEdge)
            if remEdge.isSame(bend_edge):
              b_wireList.remove(remEdge)
              break
          
          for singleEdge in b_wireList:
            #Part.show(singleEdge)
            # SMLog ("section edges: ", len(singleEdge.Edges))
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


    b_wire.rotate(self.__Shape.Faces[bend_node.idx].Surface.Center,bend_node.axis,math.degrees(bend_node.bend_angle))
    b_wire.translate(trans_vec)
    
    #Part.show(b_wire)
    #for vert in b_wire.Vertexes:
    #  SMLog ("b_wire1 tol: ", vert.Tolerance)
    
    #for ed in b_wire.Edges:
    #  SMLog ("b_wire1 tol: ", ed.Vertexes[0].Tolerance, " ", ed.Vertexes[1].Tolerance)
      
    sweep_path = Part.makeLine(o_wire.Vertexes[0].Point, b_wire.Vertexes[0].Point)
    #Part.show(sweep_path)

    Bend_shell = Part.makeRuledSurface (o_wire, b_wire)
    # Part.show(Bend_shell)
    for shell_face in Bend_shell.Faces:
      flat_shell.append(shell_face )


    #Part.show(self.__Shape.copy())
    SMLog ("finish genBendShell Face", bend_node.idx +1)

    return flat_shell



  def makeCutTool(self, theEdge, W_node):
    SMLog ("mCT Face", W_node.idx +1)
    # makes a Section wire through the shape
    # and generates a cutTool to be used to cut faces at the sheet edges
    origin = theEdge.Vertexes[0].Point
    o_vec = theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point
    o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z) 
    o_thick.normalize().multiply(2.0 * self.__thickness)

    vec1 = Base.Vector(W_node.axis.x, W_node.axis.y, W_node.axis.z)
    vec1.multiply(self.__thickness)
    
    # defining the points of the section plane:
    Spnt1 = origin - vec1 - o_thick
    Spnt2 = origin - vec1 + o_vec + o_thick
    Spnt3 = origin +  vec1 +  vec1 + o_vec + o_thick
    Spnt4 = origin +  vec1 +  vec1 - o_thick

    Sedge1 = Part.makeLine(Spnt1,Spnt2)
    Sedge2 = Part.makeLine(Spnt2,Spnt3)
    Sedge3 = Part.makeLine(Spnt3,Spnt4)
    Sedge4 = Part.makeLine(Spnt4,Spnt1)
        
    Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
    Sf1=Part.Face(Sw1) # 
    
    #Part.show(Sf1)
    lostShape = self.__Shape.copy()
    Sedges = Sf1.section(lostShape)
    #Part.show(Sedges)
    # find edge in Sedges equal to theEdge
    other_edges = []
    for lu_edge in Sedges.Edges:
      if not ((equal_vertex(lu_edge.Vertexes[0], theEdge.Vertexes[0]) and 
          equal_vertex(lu_edge.Vertexes[1], theEdge.Vertexes[1])) or 
          (equal_vertex(lu_edge.Vertexes[1], theEdge.Vertexes[0]) and 
          equal_vertex(lu_edge.Vertexes[0], theEdge.Vertexes[1]))):
        other_edges.append(lu_edge)
        
    next_pnt = theEdge.Vertexes[0]
    start_pnt = theEdge.Vertexes[1]
      
    S_edge_list = [theEdge]
    e_counter = len(other_edges)
    # SMLog ("e_counter: ", e_counter)
    startFound = False 
    while (e_counter > 0) and (not startFound):
      found_next = False
      for lu_edge in other_edges:
        if equal_vertex(lu_edge.Vertexes[0], next_pnt):
          found_next = True
          next_next_pnt = lu_edge.Vertexes[1]
        if equal_vertex(lu_edge.Vertexes[1], next_pnt):
          found_next = True
          next_next_pnt = lu_edge.Vertexes[0]
        if found_next:
          S_edge_list.append(lu_edge)
          other_edges.remove(lu_edge)
          next_pnt = next_next_pnt
          if equal_vertex(start_pnt, next_pnt):
            startFound = True
          break
      e_counter = e_counter -1

    if not startFound:
      W_node.analysis_ok = False # 
      W_node.error_code = 23 # Unfold: Unfold: CutToolWire not closed
      self.error_code = 23
      self.failed_face_idx = W_node.idx

          
    Swire1 = Part.Wire(S_edge_list)
    
    # fixme: look if we have more than one wire
    # Part.show(Swire1)
    
    SectionNormal = o_vec.cross(W_node.axis)
    SectionNormal.normalize()
    
    lookAt = theEdge.LastParameter/2.0
    mCT_Posi = theEdge.valueAt(lookAt) + SectionNormal
    
    # T_pnt = vertex_verwaltung[i][0] + Base.Vector(kante.x/2.0, kante.y/2.0, kante.z/2.0) + SectionNormal
    
    Sf1=Part.Face(Swire1) 
    # Part.show(Sf1)

    s_face_body = lostShape.Faces[W_node.idx].extrude(vec1)
    # Part.show(s_face_body)


    if s_face_body.isInside(mCT_Posi, 0.00001, True):
        SMLog (" T_pnt is inside!")
        SectionNormal.multiply(-1.0)
    else:
        SMLog ("T_pnt is outside!")
    cut_solid = Sf1.extrude(SectionNormal)
    # Part.show(cut_solid)
    SMLog ("finish mCT Face", W_node.idx +1)
    
    return cut_solid





  def makeCutTool2(self, theEdge, W_node, cutType = None):
    SMLog ("mCT2 Face", W_node.idx +1)
    # makes a Section wire through the face defining the sheet edge at theEdge
    # This version did not cut the faces. Why???

    o_vec = theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point
    o_thick = Base.Vector(o_vec.x, o_vec.y, o_vec.z) 
    o_thick.normalize().multiply(2.0 * self.__thickness)
    vec1 = Base.Vector(W_node.axis.x, W_node.axis.y, W_node.axis.z)
    vec1.multiply(self.__thickness)

    if (cutType == None) or (cutType == 3):
      origin = theEdge.Vertexes[0].Point
      o_vec = theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point
      # defining the points of the section plane:
      Spnt1 = origin - vec1 - o_thick
      Spnt2 = origin - vec1 + o_vec + o_thick
      Spnt3 = origin +  vec1 +  vec1 + o_vec + o_thick
      Spnt4 = origin +  vec1 +  vec1 - o_thick
    elif cutType == 1:
      origin = theEdge.Vertexes[0].Point
      o_vec = (theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point)/2.0
      Spnt1 = origin - vec1 - o_thick
      Spnt2 = origin - vec1 + o_vec 
      Spnt3 = origin +  vec1 +  vec1 + o_vec
      Spnt4 = origin +  vec1 +  vec1 - o_thick
    elif cutType == 2:
      origin = theEdge.Vertexes[1].Point
      o_vec = (theEdge.Vertexes[0].Point - theEdge.Vertexes[1].Point)/2.0
      # defining the points of the section plane:
      Spnt1 = origin - vec1 + o_thick
      Spnt2 = origin - vec1 + o_vec
      Spnt3 = origin +  vec1 +  vec1 + o_vec
      Spnt4 = origin +  vec1 +  vec1 + o_thick
  
    

    Sedge1 = Part.makeLine(Spnt1,Spnt2)
    Sedge2 = Part.makeLine(Spnt2,Spnt3)
    Sedge3 = Part.makeLine(Spnt3,Spnt4)
    Sedge4 = Part.makeLine(Spnt4,Spnt1)
        
    Sw1 = Part.Wire([Sedge1, Sedge2, Sedge3, Sedge4])
    Sf1=Part.Face(Sw1) # 
    # Part.show(Sf1)

    next_pnt = theEdge.Vertexes[1].Point
    start_pnt = theEdge.Vertexes[0].Point
    start_idx = 0
    end_idx = 1

    
    for i in self.index_list:
      singleEdge = Sf1.section(self.__Shape.Faces[i])
      #Part.show(singleEdge)
      # SMLog ("section edges: ", len(singleEdge.Edges))
      if len(singleEdge.Edges) == 1:
        if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[0].Point, start_pnt)):
          lastEdge = singleEdge.Edges[0]
          lastConnect = 1
        if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[1].Point, start_pnt)):
          lastEdge = singleEdge.Edges[0]
          lastConnect = 0
      
        if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[0].Point, next_pnt)):
          nextEdge = singleEdge.Edges[0]
          nextConnect = 1
        if (DraftVecUtils.equals(singleEdge.Edges[0].Vertexes[1].Point, next_pnt)):
          nextEdge = singleEdge.Edges[0]
          nextConnect = 0
    

    if (cutType == None) or (cutType == 3):
      origin = theEdge.Vertexes[0].Point
      startEdge = Part.makeLine(start_pnt, next_pnt)
      middleEdge = Part.makeLine(nextEdge.Vertexes[nextConnect].Point, lastEdge.Vertexes[lastConnect].Point)
    elif cutType == 1:
      origin = theEdge.Vertexes[0].Point
      o_vec = (theEdge.Vertexes[1].Point - theEdge.Vertexes[0].Point)/2.0
      startEdge = Part.makeLine(start_pnt, start_pnt + o_vec)
      nextEdge = Part.makeLine(start_pnt + o_vec, start_pnt + o_vec + vec1)
      middleEdge = Part.makeLine(start_pnt + o_vec + vec1, lastEdge.Vertexes[lastConnect].Point)
      
    elif cutType == 2:
      origin = theEdge.Vertexes[1].Point
      o_vec = (theEdge.Vertexes[0].Point - theEdge.Vertexes[1].Point)/2.0
      startEdge = Part.makeLine(next_pnt + o_vec, next_pnt)
      middleEdge = Part.makeLine(nextEdge.Vertexes[nextConnect].Point, next_pnt + o_vec + vec1)
      lastEdge = Part.makeLine(next_pnt + o_vec + vec1, next_pnt + o_vec)


    Swire1 = Part.Wire([startEdge, nextEdge, middleEdge, lastEdge ])

    # Part.show(Swire1)
    
    SectionNormal = o_vec.cross(W_node.axis)
    SectionNormal.normalize()
    
    lookAt = theEdge.LastParameter/2.0
    testPnt = theEdge.valueAt(lookAt) + SectionNormal
    
    Sf1=Part.Face(Swire1) 
    # Part.show(Sf1)

    s_face_body = self.__Shape.Faces[W_node.idx].extrude(vec1)
    # Part.show(s_face_body)
    if s_face_body.isInside(testPnt, 0.00001, True):
        SMLog (" testPnt is inside!")
        SectionNormal.multiply(-1.0)
    else:
        SMError ("testPnt is outside!")

    cut_solid = Sf1.extrude(SectionNormal)
    # Part.show(cut_solid)
    SMLog ("finish mCT2 Face", W_node.idx +1)
    return cut_solid
    



  def genVertEdgeList(self, theVert):
    SMLog ("theVert tolerance: ", theVert.Tolerance)
    cornerEdges = []
    for foEd in self.__Shape.Edges:
      #SMLog ("foEd0 tolerance: ", foEd.Vertexes[0].Tolerance)
      if equal_vertex(foEd.Vertexes[0], theVert):
        cornerEdges.append(foEd)
        #Part.show(foEd)
      if len(foEd.Vertexes) > 1:
        #SMLog ("foEd1 tolerance: ", foEd.Vertexes[1].Tolerance)
        if equal_vertex(foEd.Vertexes[1], theVert):
          cornerEdges.append(foEd)
    SMLog ("genVertEdgeList: ", len(cornerEdges))
    return cornerEdges




  def generateShell(self, flat_node):
    SMLog ("genShell Face", flat_node.idx +1)
    # collect faces from the flat_node and return them
    flat_shell = []
    flat_shell.append(self.__Shape.Faces[flat_node.idx].copy())
    flat_shell.append(self.__Shape.Faces[flat_node.c_face_idx].copy())
    
    # Needed are all edges
    edge_wires = DraftGeomUtils.findWires(flat_node.sheet_edges)
    SMLog ("Face", flat_node.idx +1, " Wires found: ", len(edge_wires))
        
    # the edges to the parent-node  and the child-nodes are used to
    # generate cut tools for the faces at the sheet edge
    neighborCuts = [] # make list of cutTools
    if flat_node.p_edge:
      typeOfCut = 0
      #if len(self.genPntEdgeList(flat_node.p_edge.Vertexes[0].Point)) == 3:
      if len(self.genVertEdgeList(flat_node.p_edge.Vertexes[0])) == 3:
        SMLog ("mCT typeOfCut 1")
        typeOfCut = typeOfCut + 1
      #if len(self.genPntEdgeList(flat_node.p_edge.Vertexes[1].Point)) == 3:
      if len(self.genVertEdgeList(flat_node.p_edge.Vertexes[1])) == 3:
        SMLog ("mCT typeOfCut 2")
        typeOfCut = typeOfCut + 2
        
      if typeOfCut <> 0:
        SMLog ("should call mCT")
        #neighborCuts.append(self.makeCutTool2(flat_node.p_edge, flat_node, typeOfCut))
        neighborCuts.append(self.makeCutTool(flat_node.p_edge, flat_node))
    
    for child in flat_node.child_list:
      typeOfCut = 0
      #if len(self.genPntEdgeList(child.p_edge.Vertexes[0].Point)) == 3:
      if len(self.genVertEdgeList(child.p_edge.Vertexes[0])) == 3:
        SMLog ("mCT child typeOfCut 1")
        typeOfCut = typeOfCut + 1
      #if len(self.genPntEdgeList(child.p_edge.Vertexes[1].Point)) == 3:
      if len(self.genVertEdgeList(child.p_edge.Vertexes[1])) == 3:
        SMLog ("mCT child typeOfCut 2")
        typeOfCut = typeOfCut + 2
        
      if typeOfCut <> 0:
        SMLog ("should call mCT child")
        #neighborCuts.append(self.makeCutTool2(child.p_edge, flat_node, typeOfCut))
        neighborCuts.append(self.makeCutTool(child.p_edge, flat_node))
    
    

    faces_list = []
    cut_faces =[]
    for i in self.index_list:
      faces_list.append(self.__Shape.Faces[i])

    # cut all residual faces which should define the edges of the sheet with the cutters where needed
    
    if len(neighborCuts) > 0:
      SMLog ("CutTools: ", len(neighborCuts), " for sheet_edges: ", len(flat_node.sheet_edges))
      for cutter in neighborCuts:
        SMLog ("next cutter in action")
        if self.error_code <> None:
          break
        for c_face in faces_list:
          cutted = c_face.cut(cutter)
          # SMLog ("Anzahl Schnittteile: ", len(cutted.Faces))
          # if len(cutted.Faces) == 2:
          #   Part.show(cutted.Faces[0])
          #   Part.show(cutted.Faces[1])
          for cut_face in cutted.Faces:
            cut_faces.append(cut_face)
        faces_list = cut_faces[:]
        cut_faces = []
        
    if self.error_code <> None:
      return flat_shell
    # select those faces, that have a common edge to the flat_node
    for s_edge in flat_node.sheet_edges:
      SMLog ("search faces for next edge")
      for c_face in faces_list:
        for c_edge in c_face.Edges:
          if s_edge.isSame(c_edge):
            if not c_face in flat_shell:
              flat_shell.append(c_face.copy())
              # Part.show(c_face)
      
    SMLog ("finisch genShell Face", flat_node.idx +1)
    return flat_shell
    
  '''
  Den Baum rekursiv abwandern. Nur jeweils im höchsten Level unbend
  ausführen.
  '''
  def unfold_tree(self, node):
    # This function traverses the tree and unfolds the faces 
    # beginning at the outermost nodes.
    SMLog ("unfold_tree face", node.idx + 1)
    theShell = []
    for n_node in node.child_list:
      if self.error_code == None:
        theShell = theShell + self.unfold_tree(n_node)
    if node.node_type == 'Bend':
      trans_vec = node.tan_vec * node._trans_length
      for bFaces in theShell:
        bFaces.rotate(self.__Shape.Faces[node.idx].Surface.Center,node.axis,math.degrees(node.bend_angle))
        bFaces.translate(trans_vec)
      if self.error_code == None:
        nodeShell = self.generateBendShell(node) 
      else:
        nodeShell = []
    else:
      if self.error_code == None:
        nodeShell = self.generateShell(node)
      else:
        nodeShell = []
    SMLog ("ufo finish face",node.idx +1)
    return (theShell + nodeShell)
    

  def showFaces(self):
    for i in self.index_list:
      Part.show(self.__Shape.Faces[i])



def PerformUnfold():
  mylist = Gui.Selection.getSelectionEx()
  resPart = None
  # SMLog ('Die Selektion: ',mylist)
  # SMLog ('Zahl der Selektionen: ', mylist.__len__())

  if mylist.__len__() == 0:
    mw=FreeCADGui.getMainWindow()
    QtGui.QMessageBox.information(mw,"Error","""One flat face needs to be selected!""")
  else:
    if mylist.__len__() > 1:
      mw=FreeCADGui.getMainWindow()
      QtGui.QMessageBox.information(mw,"Error","""Only one flat face has to be selected!""")
    else:
      o = Gui.Selection.getSelectionEx()[0]
      SMLog (o.ObjectName)
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
            SMLog ("name: ",subelement)
            f_number = int(o.SubElementNames[0].lstrip('Face'))-1
            SMLog (f_number)
            TheTree = SheetTree(o.Object.Shape, f_number) # initializes the tree-structure
            if TheTree.error_code == None:
              TheTree.Bend_analysis(f_number, None) # traverses the shape builds the tree-structure
              
              if TheTree.error_code == None:
                # TheTree.showFaces()
                theFaceList = TheTree.unfold_tree(TheTree.root) # traverses the tree-structure
                if TheTree.error_code == None:

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
                    except:
                        SMError("couldn't make a solid, show only a shell")
                        resPart = newShell
                    else:
                        resPart = TheSolid
            
            if TheTree.error_code <> None:
              SMError ("Error " + unfold_error[TheTree.error_code])
              SMError (" at Face" + TheTree.failed_face_idx+1)
              QtGui.QMessageBox.information(mw,"Error",unfold_error[TheTree.error_code])
            else:
              SMMessage ("unfold successful")
                   
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
    obj.Proxy = self

  def execute(self, fp):
    s = PerformUnfold()
    fp.Shape = s
    


class SMUnfoldCommandClass():
  """Unfold object"""

  def GetResources(self):
    __dir__ = os.path.dirname(__file__)
    iconPath = os.path.join( __dir__, 'Resources', 'icons' )
    return {'Pixmap'  : os.path.join( iconPath , 'SMUnfold.svg') , # the name of a svg file available in the resources
            'MenuText': "Unfold" ,
            'ToolTip' : "Flatten folded sheet metal object"}
 
  def Activated(self):
    a=FreeCAD.ActiveDocument.addObject("Part::FeaturePython","Unfold")
    SMUnfoldObject(a)
    a.ViewObject.Proxy = 0
    FreeCAD.ActiveDocument.recompute()
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


