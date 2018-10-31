# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalCmd.py
#  
#  Copyright 2015 Shai Seger <shaise at gmail dot com>
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
###################################################################################

from FreeCAD import Gui
from PySide import QtCore, QtGui

import FreeCAD, FreeCADGui, Part, os, math
__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
smEpsilon = 0.0000001

def smWarnDialog(msg):
    diag = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'Error in macro MessageBox', msg)
    diag.setWindowModality(QtCore.Qt.ApplicationModal)
    diag.exec_()
 
def smBelongToBody(item, body):
    if (body is None):
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False
    
def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0
        
def smIsOperationLegal(body, selobj):
    #FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog("The selected geometry does not belong to the active Body.\nPlease make the container of this item active by\ndouble clicking on it.")
        return False
    return True    
 
def smStrEdge(e):
    return "[" + str(e.valueAt(e.FirstParameter)) + " , " + str(e.valueAt(e.LastParameter)) + "]"

def smMakeRelifFace(edge, dir, gap, reliefW, reliefD, reliefType):
    p1 = edge.valueAt(edge.FirstParameter + gap)
    p2 = edge.valueAt(edge.FirstParameter + gap + reliefW )
    if reliefType == "Round" and reliefD > reliefW :
      p3 = edge.valueAt(edge.FirstParameter + gap + reliefW) + dir.normalize() * (reliefD-reliefW/2)
      p34 = edge.valueAt(edge.FirstParameter + gap + reliefW/2) + dir.normalize() * reliefD
      p4 = edge.valueAt(edge.FirstParameter + gap) + dir.normalize() * (reliefD-reliefW/2)
      e1 = Part.makeLine(p1, p2)
      e2 = Part.makeLine(p2, p3)
      e3 = Part.Arc(p3, p34, p4).toShape()
      e4 = Part.makeLine(p4, p1)	
    else :
      p3 = edge.valueAt(edge.FirstParameter + gap + reliefW) + dir.normalize() * reliefD
      p4 = edge.valueAt(edge.FirstParameter + gap) + dir.normalize() * reliefD
      e1 = Part.makeLine(p1, p2)
      e2 = Part.makeLine(p2, p3)
      e3 = Part.makeLine(p3, p4)
      e4 = Part.makeLine(p4, p1)

    w = Part.Wire([e1,e2,e3,e4])
    return Part.Face(w)
 
def smMakeFace(edge, dir, extLen, gap1 = 0.0, gap2 = 0.0, angle1 = 0.0, angle2 = 0.0):
    len1 = extLen * math.tan(math.radians(angle1))
    len2 = extLen * math.tan(math.radians(angle2))

    p1 = edge.valueAt(edge.LastParameter - gap2)
    p2 = edge.valueAt(edge.FirstParameter + gap1)
    p3 = edge.valueAt(edge.FirstParameter + gap1 + len1) + dir.normalize() * extLen
    p4 = edge.valueAt(edge.LastParameter - gap2 - len2) + dir.normalize() * extLen
	
    e2 = Part.makeLine(p2, p3)
    e4 = Part.makeLine(p4, p1)
    section = e4.section(e2)

    if section.Vertexes :
      p5 = section.Vertexes[0].Point
      w = Part.makePolygon([p1,p2,p5,p1])
    else :
      w = Part.makePolygon([p1,p2,p3,p4,p1])
    return Part.Face(w)
    
def smRestrict(var, fromVal, toVal):
    if var < fromVal:
      return fromVal
    if var > toVal:
      return toVal
    return var

def smFace(selItem, obj) :
  # find face if Edge Selected
  if type(selItem) == Part.Edge :
    Facelist = obj.ancestorsOfType(selItem, Part.Face)
    if Facelist[0].Area < Facelist[1].Area :
      selFace = Facelist[0]
    else :
      selFace = Facelist[1]
  elif type(selItem) == Part.Face :
    selFace = selItem
  return selFace

def smModifiedFace(Face, obj) :
  # find face Modified During loop
  for face in obj.Faces :
    face_common = face.common(Face)
    if face_common.Faces :
      if face.Area == face_common.Faces[0].Area :
        break
  return face

def LineAngle(edge1, edge2) :
  import math
  if edge1.Orientation == edge2.Orientation:
    lineDir = edge1.valueAt(edge1.FirstParameter) - edge1.valueAt(edge1.LastParameter)
    edgeDir = edge2.valueAt(edge2.FirstParameter) - edge2.valueAt(edge2.LastParameter)
  else :
    lineDir = edge1.valueAt(edge1.FirstParameter) - edge1.valueAt(edge1.LastParameter)
    edgeDir = edge2.valueAt(edge2.LastParameter) - edge2.valueAt(edge2.FirstParameter)
  angle1 = edgeDir.getAngle(lineDir)
  angle = math.degrees(angle1)
  return angle

def smGetFace(Faces, obj) :
  # find face Name Modified obj
  faceList =[]
  for Face in Faces :
    for i,face in enumerate(obj.Faces) :
      face_common = face.common(Face)
      if face_common.Faces :
        faceList.append('Face'+str(i+1))
  #print(faceList)
  return faceList

def smMiter(bendA = 90.0, miterA1 = 0.0, miterA2 = 0.0, flipped = False, extLen = 10.0, gap1 = 0.0, gap2 = 0.0,
            automiter = True, selFaceNames = '', MainObject = None):

  if not(automiter) :
    miterA1List = [miterA1 for selFaceName in selFaceNames]
    miterA2List = [miterA2 for selFaceName in selFaceNames]
    gap1List = [gap1 for selFaceName in selFaceNames]
    gap2List = [gap2 for selFaceName in selFaceNames]
  else :
    miterA1List = [0.0 for selFaceName in selFaceNames]
    miterA2List = [0.0 for selFaceName in selFaceNames]
    gap1List = [gap1 for selFaceName in selFaceNames]
    gap2List = [gap2 for selFaceName in selFaceNames]
    facelist, edgelist, facefliplist, edgefliplist, transfacelist, transedgelist = ([], [], [], [], [], [])
    for selFaceName in selFaceNames :
      selItem = MainObject.getElement(selFaceName)
      selFace = smFace(selItem, MainObject)

      # find the narrow edge
      thk = 999999.0
      for edge in selFace.Edges:
        if abs( edge.Length ) < thk:
          thk = abs( edge.Length )
          thkEdge = edge

      # find a length edge  =  revolve axis direction
      p0 = thkEdge.valueAt(thkEdge.FirstParameter)
      for lenEdge in selFace.Edges:
        p1 = lenEdge.valueAt(lenEdge.FirstParameter)
        p2 = lenEdge.valueAt(lenEdge.LastParameter)
        if lenEdge.isSame(thkEdge):
          continue
        if (p1 - p0).Length < smEpsilon:
          revAxisV = p2 - p1
          revAxisP = p2
          break
        if (p2 - p0).Length < smEpsilon:
          revAxisV = p1 - p2
          revAxisP = p1
          break

      list2 = MainObject.ancestorsOfType(lenEdge, Part.Face)
      for Cface in list2 :
        if not(Cface.isSame(selFace)) :
          break

      if not(flipped):
        thkDir = Cface.normalAt(0,0)
      else:
        thkDir = Cface.normalAt(0,0) * -1
      FaceDir = selFace.normalAt(0,0)
      revAxisV.normalize()

      #make sure the direction verctor is correct in respect to the normal
      if (thkDir.cross(revAxisV).normalize() - FaceDir).Length < smEpsilon:
       revAxisV = revAxisV * -1

      # restrict angle
      if (bendA < 0):
        bendA = -bendA
        flipped = not flipped

      # to get tranlated face
      transP = FaceDir * (bendR + thk)

      # narrow the wall if we have gaps
      BendFace = smMakeFace(lenEdge, FaceDir, extLen, gap1, gap2)
      if BendFace.normalAt(0,0) != thkDir :
        BendFace.reverse()
      BendFace.rotate(revAxisP, revAxisV, bendA)
      #Part.show(BendFace)
      facelist.append(BendFace)
      BendFace.translate(transP)
      transfacelist.append(BendFace)

      edge_len = lenEdge.copy()
      edge_len.translate(FaceDir * extLen)
      edge_len.rotate(revAxisP, revAxisV, bendA)
      #Part.show(edge_len)
      edgelist.append(edge_len)
      edge_len.translate(transP)
      transedgelist.append(edge_len)

      # narrow the wall if we have gaps
      BendFace = smMakeFace(lenEdge, FaceDir * -1, extLen, gap1, gap2)
      if BendFace.normalAt(0,0) != FaceDir :
        BendFace.reverse()
      BendFace.rotate(revAxisP, revAxisV, bendA)
      #Part.show(BendFace)
      facefliplist.append(BendFace)

      edge_len = lenEdge.copy()
      edge_len.translate(FaceDir * -1 * extLen)
      edge_len.rotate(revAxisP, revAxisV, bendA)
      #Part.show(edge_len)
      edgefliplist.append(edge_len)

    # check faces intersect each other
    for i,face in enumerate(facelist) :
      for j, lenEdge in enumerate(edgelist) :
        if i != j and abs((facelist[i].normalAt(0,0)-facelist[j].normalAt(0,0)).Length) < smEpsilon :
          p1 = lenEdge.valueAt(lenEdge.FirstParameter)
          p2 = lenEdge.valueAt(lenEdge.LastParameter)
          section_vertex = face.section(lenEdge)
          if section_vertex.Vertexes :
            Angle = LineAngle(edgelist[i], edgelist[j])
            #print(Angle)
            dist1 = (p1 - section_vertex.Vertexes[0].Point).Length
            dist2 = (p2 - section_vertex.Vertexes[0].Point).Length
            if abs(dist1) < abs(dist2) :
              miterA1List[j] = Angle / 2.0 
              gap1List[j] = 0.1
            elif abs(dist2) < abs(dist1) :
              miterA2List[j] = Angle / 2.0
              gap2List[j] = 0.1
        elif i != j :
          p1 = lenEdge.valueAt(lenEdge.FirstParameter)
          p2 = lenEdge.valueAt(lenEdge.LastParameter)
          p3 = transedgelist[j].valueAt(transedgelist[j].FirstParameter)
          p4 = transedgelist[j].valueAt(transedgelist[j].LastParameter)
          section_vertex = face.section(lenEdge)
          section_vertex1 = transfacelist[i].section(transedgelist[j])
          if section_vertex.Vertexes :
            section_edge = face.section(facelist[j])
            Angle = LineAngle(section_edge.Edges[0], lenEdge)
            #print(Angle)
            dist1 = (p1 - section_vertex.Vertexes[0].Point).Length
            dist2 = (p2 - section_vertex.Vertexes[0].Point).Length
            dist3 = (p3 - section_vertex1.Vertexes[0].Point).Length
            dist4 = (p4 - section_vertex1.Vertexes[0].Point).Length
            if abs(dist1) < abs(dist2) :
              miterA1List[j] = abs(90-Angle)
              if abs(dist3) > 0.0 :
                gap1List[j] = abs(dist3) + 0.1
            elif abs(dist2) < abs(dist1) :
              miterA2List[j] = abs(90-Angle)
              if abs(dist4) > 0.0 :
                gap2List[j] = abs(dist4) + 0.1

    # check faces intersect each other for fliplist
    for i,face in enumerate(facefliplist) :
      for j, lenEdge in enumerate(edgefliplist) :
        if i != j and abs((facefliplist[i].normalAt(0,0)-facefliplist[j].normalAt(0,0)).Length) < smEpsilon :
          p1 = lenEdge.valueAt(lenEdge.FirstParameter)
          p2 = lenEdge.valueAt(lenEdge.LastParameter)
          section_vertex = face.section(lenEdge)
          if section_vertex.Vertexes :
            Angle = LineAngle(edgefliplist[i], edgefliplist[j])
            #print(Angle)
            dist1 = (p1 - section_vertex.Vertexes[0].Point).Length
            dist2 = (p2 - section_vertex.Vertexes[0].Point).Length
            if abs(dist1) < abs(dist2) :
              miterA1List[j] = -Angle / 2.0 
            elif abs(dist2) < abs(dist1) :
              miterA2List[j] = -Angle / 2.0
        elif i != j :
          p1 = lenEdge.valueAt(lenEdge.FirstParameter)
          p2 = lenEdge.valueAt(lenEdge.LastParameter)
          section_vertex = face.section(lenEdge)
          if section_vertex.Vertexes :
            section_edge = face.section(facefliplist[j])
            Angle = LineAngle(section_edge.Edges[0], lenEdge)
            #print(Angle)
            dist1 = (p1 - section_vertex.Vertexes[0].Point).Length
            dist2 = (p2 - section_vertex.Vertexes[0].Point).Length
            if abs(dist1) < abs(dist2) :
              miterA1List[j] = abs(90-Angle)* -1
            elif abs(dist2) < abs(dist1) :
              miterA2List[j] = abs(90-Angle) *-1

  #print(miterA1List, miterA2List, gap1List, gap2List)
  return miterA1List, miterA2List, gap1List, gap2List

def smBend(bendR = 1.0, bendA = 90.0, miterA1 = 0.0,miterA2 = 0.0, BendType = "Material Outside", flipped = False, unfold = False, 
            offset = 0.0, extLen = 10.0, gap1 = 0.0, gap2 = 0.0,  reliefType = "Rectangle", reliefW = 0.8, reliefD = 1.0, extend1 = 0.0, 
            extend2 = 0.0, kfactor = 0.45, RelifFactor = 0.7, UseRelifFactor = False, selFaceNames = '', MainObject = None, 
            automiter = True, sketch = None ):

  # if sketch is as wall 
  sketches = False
  if sketch :
    if sketch.Shape.Wires[0].isClosed() :
      sketches = True
    else :
      pass

  if not(sketches) :
    miterA1List, miterA2List, gap1List, gap2List = smMiter(bendA = bendA, miterA1 = miterA1, miterA2 = miterA2, flipped = flipped, extLen = extLen, gap1 = gap1, 
                                      gap2 = gap2, selFaceNames = selFaceNames, automiter = automiter, MainObject = MainObject)
  else :
    miterA1List, miterA2List, gap1List, gap2List = ( [0.0],[0.0],[gap1],[gap2])

  thk_faceList = []
  resultSolid = MainObject
  for i, selFaceName in enumerate(selFaceNames):
    selItem = MainObject.getElement(selFaceName)
    selFace = smFace(selItem, MainObject)
    selFace = smModifiedFace(selFace, resultSolid)
    gap1, gap2 = (gap1List[i], gap2List[i])

    # find the narrow edge
    thk = 999999.0
    for edge in selFace.Edges:
      if abs( edge.Length ) < thk:
        thk = abs( edge.Length )
        thkEdge = edge

    # Add as offset to  set any distance
    if UseRelifFactor :
      reliefW = thk * RelifFactor
      reliefD = thk * RelifFactor

    # Add Relief factor
    if BendType == "Material Outside" :
      offset = 0.0
      inside = False
    elif BendType == "Material Inside" :
      offset = -(thk + bendR)
      inside = True
    elif BendType == "Thickness Outside" :
      offset = -bendR
      inside = True
    elif BendType == "Offset" :
      if offset < 0.0 :
        inside = True
      else :
        inside = False

    # find a length edge  =  revolve axis direction
    p0 = thkEdge.valueAt(thkEdge.FirstParameter)
    for lenEdge in selFace.Edges:
      p1 = lenEdge.valueAt(lenEdge.FirstParameter)
      p2 = lenEdge.valueAt(lenEdge.LastParameter)
      if lenEdge.isSame(thkEdge):
        continue
      if (p1 - p0).Length < smEpsilon:
        revAxisV = p2 - p1
        break
      if (p2 - p0).Length < smEpsilon:
        revAxisV = p1 - p2
        break

    # find the large face connected with selected face
    list2 = resultSolid.ancestorsOfType(lenEdge, Part.Face)
    for Cface in list2 :
      if not(Cface.isSame(selFace)) :
        break

    # main Length Edge
    MlenEdge = lenEdge
    leng = MlenEdge.Length
    revAxisV.normalize()
    thkDir = Cface.normalAt(0,0) * -1
    FaceDir = selFace.normalAt(0,0)

    # Get correct size inside face
    if inside :
      e1 = MlenEdge.copy()
      e1.translate(FaceDir * offset)
      EdgeShape = e1.common(Cface)
      lenEdge = EdgeShape.Edges[0]
      Noffset1 = abs((MlenEdge.valueAt(MlenEdge.FirstParameter)-lenEdge.valueAt(lenEdge.FirstParameter)).Length)
      Noffset2 = abs((MlenEdge.valueAt(MlenEdge.LastParameter)-lenEdge.valueAt(lenEdge.LastParameter)).Length)

    # if sketch is as wall 
    sketches = False
    if sketch :
      if sketch.Shape.Wires[0].isClosed() :
        sketches = True
      else :
        pass

    if sketches :
      sketch_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
      sketch_face.translate(thkDir * -thk )
      if inside :
        sketch_face.translate(FaceDir * offset )
      sketch_Shape = lenEdge.common(sketch_face)
      sketch_Edge = sketch_Shape.Edges[0]
      gap1 = (lenEdge.valueAt(lenEdge.FirstParameter) - sketch_Edge.valueAt(sketch_Edge.FirstParameter)).Length
      gap2 = (lenEdge.valueAt(lenEdge.LastParameter) - sketch_Edge.valueAt(sketch_Edge.LastParameter)).Length

    # Get angles of adjcent face
    Agap1 = 0.0
    Agap2 = 0.0
    if inside :
      AngleList =[]
      if MlenEdge.Vertexes[0].Orientation == "Reversed" :
        vertex1 = MlenEdge.Vertexes[0]
        vertex0 = MlenEdge.Vertexes[1]
      else : 
        vertex0 = MlenEdge.Vertexes[0]
        vertex1 = MlenEdge.Vertexes[1]
      Edgelist = Cface.ancestorsOfType(vertex0, Part.Edge)
      for ed in Edgelist :
        if not(MlenEdge.isSame(ed)):
          #Part.show(ed)
          if abs((MlenEdge.valueAt(MlenEdge.FirstParameter)- ed.valueAt(ed.LastParameter)).Length)  < smEpsilon:
            lineDir = ed.valueAt(ed.LastParameter)- ed.valueAt(ed.FirstParameter)
            edgeDir = MlenEdge.valueAt(MlenEdge.FirstParameter) - MlenEdge.valueAt(MlenEdge.LastParameter)
            angle1 = edgeDir.getAngle(lineDir)
            angle = math.degrees(angle1)
            #print("1",angle)
            AngleList.append(angle)
          elif abs((MlenEdge.valueAt(MlenEdge.FirstParameter) - ed.valueAt(ed.FirstParameter)).Length) < smEpsilon:
            lineDir = ed.valueAt(ed.FirstParameter)- ed.valueAt(ed.LastParameter)
            edgeDir = MlenEdge.valueAt(MlenEdge.FirstParameter) - MlenEdge.valueAt(MlenEdge.LastParameter)
            angle1 = edgeDir.getAngle(lineDir)
            angle = math.degrees(angle1)
            #print("2",angle)
            AngleList.append(angle)

      Edgelist = Cface.ancestorsOfType(vertex1, Part.Edge)
      for ed in Edgelist :
        if not(MlenEdge.isSame(ed)):
          if abs((MlenEdge.valueAt(MlenEdge.LastParameter)- ed.valueAt(ed.FirstParameter)).Length)  < smEpsilon:
            lineDir = ed.valueAt(ed.FirstParameter)- ed.valueAt(ed.LastParameter)
            edgeDir = MlenEdge.valueAt(MlenEdge.LastParameter) - MlenEdge.valueAt(MlenEdge.FirstParameter)
            angle1 = edgeDir.getAngle(lineDir)
            angle = math.degrees(angle1)
            #print("1",angle)
            AngleList.append(angle)
          elif abs((MlenEdge.valueAt(MlenEdge.LastParameter) - ed.valueAt(ed.LastParameter)).Length) < smEpsilon:
            lineDir = ed.valueAt(ed.LastParameter)- ed.valueAt(ed.FirstParameter)
            edgeDir = MlenEdge.valueAt(MlenEdge.LastParameter) - MlenEdge.valueAt(MlenEdge.FirstParameter)
            angle1 = edgeDir.getAngle(lineDir)
            angle = math.degrees(angle1)
            #print("2",angle)
            AngleList.append(angle)
      if AngleList : 
        if AngleList[0] > 90.01 and gap1 == 0.0 :
          Agap1 = reliefW
        if AngleList[1] > 90.01 and gap2 == 0.0 :
          Agap2 = reliefW
    
    #make sure the direction verctor is correct in respect to the normal
    if (thkDir.cross(revAxisV).normalize() - FaceDir).Length < smEpsilon:
     revAxisV = revAxisV * -1

    reliefDn = reliefD
    if inside :
      reliefDn = reliefD + abs(offset)

    # CutSolids list for collecting Solids
    CutSolids = []

    # remove relief if needed
    if reliefD > 0.0 :
      if reliefW > 0.0 and ( gap1 > 0.0 or Agap1 > 0.0 ):
        reliefFace1 = smMakeRelifFace(MlenEdge, FaceDir* -1, gap1-reliefW, reliefW, reliefDn, reliefType)
        reliefSolid1 = reliefFace1.extrude(thkDir * thk)
        #Part.show(reliefSolid1)
        CutSolids.append(reliefSolid1)
      if reliefW > 0.0 and ( gap2 > 0.0 or Agap2 > 0.0 ):
        reliefFace2 = smMakeRelifFace(MlenEdge, FaceDir* -1, leng-gap2, reliefW, reliefDn, reliefType)
        reliefSolid2 = reliefFace2.extrude(thkDir * thk)
        #Part.show(reliefSolid2)
        CutSolids.append(reliefSolid2)

    # restrict angle
    if (bendA < 0):
        bendA = -bendA
        flipped = not flipped

    if not(flipped):
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * (bendR + thk)
      revAxisV = revAxisV * -1
    else:
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * -bendR

    # remove bend face if present
    if inside :
      if gap1 == 0.0 :
        Edgelist = selFace.ancestorsOfType(vertex0, Part.Edge)
        for ed in Edgelist :
          if not(MlenEdge.isSame(ed)):
            list1 = resultSolid.ancestorsOfType(ed, Part.Face)
            for Rface in list1 :
              if Rface.Area != selFace.Area and str(Rface.Surface) == "<Plane object>" :
                for edge in Rface.Edges:
                  if str(type(edge.Curve)) == "<type 'Part.Circle'>":
                    RfaceE = Rface.extrude(Rface.normalAt(0,0) * -Noffset1 )
                    CutSolids.append(RfaceE)
                    break

      if gap2 == 0.0 :
        Edgelist = selFace.ancestorsOfType(vertex1, Part.Edge)
        for ed in Edgelist :
          if not(MlenEdge.isSame(ed)):
            list1 = resultSolid.ancestorsOfType(ed, Part.Face)
            for Rface in list1 :
              if Rface.Area != selFace.Area and str(Rface.Surface) == "<Plane object>" :
                for edge in Rface.Edges:
                  if str(type(edge.Curve)) == "<type 'Part.Circle'>":
                    RfaceE = Rface.extrude(Rface.normalAt(0,0) * -Noffset2 )
                    CutSolids.append(RfaceE)
                    break

      CutFace = smMakeFace(MlenEdge, thkDir, thk, gap1, gap2)
      CutSolid = CutFace.extrude(FaceDir * offset )
      CfaceSolid = Cface.extrude(thkDir * thk)
      CutSolid = CutSolid.common(CfaceSolid)
      CutSolids.append(CutSolid)

    # Produce Main Solid for Inside Bends
    if CutSolids :
      if len(CutSolids) == 1 :
        resultSolid = resultSolid.cut(CutSolids[0])
      else :
        Solid = CutSolids[0].multiFuse(CutSolids[1:])
        Solid.removeSplitter()
        #Part.show(Solid)
        resultSolid = resultSolid.cut(Solid)

    # Produce Offset Solid
    if offset > 0.0 :
      # create wall
      offset_face = smMakeFace(lenEdge, FaceDir, -offset)
      OffsetSolid = offset_face.extrude(thkDir * thk)
      resultSolid = resultSolid.fuse(OffsetSolid)

    #wallSolid = None
    if sketches :
      Wall_face = Part.makeFace(sketch.Shape.Wires, "Part::FaceMakerBullseye")
      if inside :
        Wall_face.translate(FaceDir * offset )
      FaceAxisP = sketch_Edge.valueAt(sketch_Edge.FirstParameter) + thkDir * thk
      FaceAxisV = sketch_Edge.valueAt(sketch_Edge.FirstParameter) - sketch_Edge.valueAt(sketch_Edge.LastParameter)
      Wall_face.rotate(FaceAxisP, FaceAxisV, -90.0)
      wallSolid = Wall_face.extrude(thkDir * -thk)
      #Part.show(wallSolid)
      wallSolid.rotate(revAxisP, revAxisV, bendA)

    elif extLen > 0.0 :
      # create wall
      Wall_face = smMakeFace(lenEdge, FaceDir, extLen, gap1-extend1, gap2-extend2, miterA1List[i], miterA2List[i])
      wallSolid = Wall_face.extrude(thkDir * thk)
      #Part.show(wallSolid)
      wallSolid.rotate(revAxisP, revAxisV, bendA)
      #Part.show(wallSolid.Faces[2])
      thk_faceList.append(wallSolid.Faces[2])

    # Produce bend Solid
    if not(unfold) :
      if bendA > 0.0 :
        # create bend
        # narrow the wall if we have gaps
        revFace = smMakeFace(lenEdge, thkDir, thk, gap1, gap2)
        if revFace.normalAt(0,0) != FaceDir :
          revFace.reverse()
        bendSolid = revFace.revolve(revAxisP, revAxisV, bendA)
        #Part.show(bendSolid)
        resultSolid = resultSolid.fuse(bendSolid)
      if wallSolid :
        resultSolid = resultSolid.fuse(wallSolid)

    # Produce unfold Solid
    else :
      if bendA > 0.0 :
        # create bend
        unfoldLength = ( bendR + kfactor * thk / 2.0 ) * bendA * math.pi / 180
        # narrow the wall if we have gaps
        unfoldFace = smMakeFace(lenEdge, thkDir, thk, gap1, gap2)
        if unfoldFace.normalAt(0,0) != FaceDir :
          unfoldFace.reverse()
        unfoldSolid = unfoldFace.extrude(FaceDir * unfoldLength)
        #Part.show(unfoldSolid)
        resultSolid = resultSolid.fuse(unfoldSolid)

      if extLen > 0.0 :
        wallSolid.rotate(revAxisP, revAxisV, -bendA)
        #Part.show(wallSolid)
        wallSolid.translate(FaceDir * unfoldLength)
        resultSolid = resultSolid.fuse(wallSolid)

  #Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
  #if sketch :
    #Gui.ActiveDocument.getObject(sketch.Name).Visibility = False
  return resultSolid, thk_faceList

class SMBendWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]

    obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 10.0
    obj.addProperty("App::PropertyDistance","gap1","Parameters","Gap from left side").gap1 = 0.0
    obj.addProperty("App::PropertyDistance","gap2","Parameters","Gap from right side").gap2 = 0.0
    obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
    obj.addProperty("App::PropertyEnumeration", "BendType", "Parameters","Relief Type").BendType = ["Material Outside", "Material Inside", "Thickness Outside", "Offset"]
    obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
    obj.addProperty("App::PropertyEnumeration", "reliefType", "ParametersRelief","Relief Type").reliefType = ["Rectangle", "Round"]
    obj.addProperty("App::PropertyBool","UseRelifFactor","ParametersRelief","Use Relif Factor").UseRelifFactor = False
    obj.addProperty("App::PropertyFloat","RelifFactor","ParametersRelief","Relif Factor").RelifFactor = 0.7
    obj.addProperty("App::PropertyLength","reliefw","ParametersRelief","Relief width").reliefw = 0.8
    obj.addProperty("App::PropertyLength","reliefd","ParametersRelief","Relief depth").reliefd = 1.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.addProperty("App::PropertyDistance","extend1","ParametersEx","extend from left side").extend1 = 0.0
    obj.addProperty("App::PropertyDistance","extend2","ParametersEx","extend from right side").extend2 = 0.0
    obj.addProperty("App::PropertyBool","AutoMiter","ParametersEx","Auto Miter").AutoMiter = True
    obj.addProperty("App::PropertyAngle","miterangle1","ParametersEx","Bend miter angle").miterangle1 = 0.0
    obj.addProperty("App::PropertyAngle","miterangle2","ParametersEx","Bend miter angle").miterangle2 = 0.0
    obj.addProperty("App::PropertyDistance","offset","ParametersEx","offset Bend").offset = 0.0
    obj.addProperty("App::PropertyBool","unfold","ParametersEx","Invert bend direction").unfold = False
    obj.addProperty("App::PropertyFloatConstraint","kfactor","ParametersEx","Gap from left side").kfactor = (0.5,0.0,1.0,0.01)
    obj.addProperty("App::PropertyLink", "Sketch", "ParametersEx2", "Sketch object")
    obj.addProperty("App::PropertyBool","sketchflip","ParametersEx2","flip sketch direction").sketchflip = False
    obj.addProperty("App::PropertyBool","sketchinvert","ParametersEx2","invert sketch start").sketchinvert = False
    obj.addProperty("App::PropertyFloatList", "LengthList", "ParametersEx3", "Length of Wall List")
    obj.addProperty("App::PropertyFloatList", "bendAList", "ParametersEx3", "Bend angle List")
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    if (not hasattr(fp,"miterangle1")):
      fp.addProperty("App::PropertyAngle","miterangle1","ParametersMiterangle","Bend miter angle").miterangle1 = 0.0
      fp.addProperty("App::PropertyAngle","miterangle2","ParametersMiterangle","Bend miter angle").miterangle2 = 0.0

    if (not hasattr(fp,"AutoMiter")):
      fp.addProperty("App::PropertyBool","AutoMiter","ParametersEx","Auto Miter").AutoMiter = True

    if (not hasattr(fp,"reliefType")):
      fp.addProperty("App::PropertyEnumeration", "reliefType", "Parameters","Relief Type").reliefType = ["Rectangle", "Round"]

    if (not hasattr(fp,"extend1")):
      fp.addProperty("App::PropertyDistance","extend1","Parameters","extend from left side").extend1 = 0.0
      fp.addProperty("App::PropertyDistance","extend2","Parameters","extend from right side").extend2 = 0.0

    if (not hasattr(fp,"unfold")):
      fp.addProperty("App::PropertyBool","unfold","ParametersEx","Invert bend direction").unfold = False

    if (not hasattr(fp,"kfactor")):
      fp.addProperty("App::PropertyFloatConstraint","kfactor","ParametersEx","Gap from left side").kfactor = (0.5,0.0,1.0,0.01)

    if (not hasattr(fp,"BendType")):
      fp.addProperty("App::PropertyEnumeration", "BendType", "Parameters","Bend Type").BendType = ["Material Outside", "Material Inside", "Thickness Outside", "Offset"]

    if (not hasattr(fp,"RelifFactor")):
      fp.addProperty("App::PropertyBool","UseRelifFactor","ReliefParameters","Use Relif Factor").UseRelifFactor = False
      fp.addProperty("App::PropertyFloat","RelifFactor","ReliefParameters","Relif Factor").RelifFactor = 0.7

    if (not hasattr(fp,"Sketch")):
      fp.addProperty("App::PropertyLink", "Sketch", "ParametersEx2", "Sketch object")
      fp.addProperty("App::PropertyBool","sketchflip","ParametersEx2","flip sketch direction").sketchflip = False
      fp.addProperty("App::PropertyBool","sketchinvert","ParametersEx2","invert sketch start").sketchinvert = False
      fp.addProperty("App::PropertyFloatList", "LengthList", "ParametersEx3", "Length of Wall List")
      fp.addProperty("App::PropertyFloatList", "bendAList", "ParametersEx3", "Bend angle List")

    # restrict some params
    fp.miterangle1.Value = smRestrict(fp.miterangle1.Value, -80.0, 80.0)
    fp.miterangle2.Value = smRestrict(fp.miterangle2.Value, -80.0, 80.0)

    # get LengthList, bendAList
    bendAList = [fp.angle.Value]
    LengthList = [fp.length.Value]
    #print face

    if fp.Sketch :
      WireList = fp.Sketch.Shape.Wires[0]
      LengthList = []
      i = 0
      if not(WireList.isClosed()) :
        for v in range(len(WireList.Vertexes)-1) :
          p1 = WireList.Vertexes[i].Point
          p2 = WireList.Vertexes[i+1].Point
          e1 = p2 - p1
          LengthList.append(e1.Length)
          if i != (len(WireList.Vertexes)-2) :
            p3 = WireList.Vertexes[i+2].Point
            e2 = p3 - p2
            normal = e1.cross(e2)
            sketch_normal = fp.Sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
            coeff = sketch_normal.dot(normal)
            if coeff >= 0:
              sign = 1
            else:
              sign = -1
            angle_rad = e1.getAngle(e2)
            if fp.sketchflip :
              angle = sign*math.degrees(angle_rad) * -1
            else :
              angle = sign*math.degrees(angle_rad)
            bendAList.append(angle)
          i += 1
      else :
        if fp.Sketch.Support :
          fp.baseObject = (fp.Sketch.Support[0][0], fp.Sketch.Support[0][1] )
        LengthList = [10.0]
      if fp.sketchinvert :
        LengthList.reverse()
        bendAList.reverse()
    fp.LengthList = LengthList
    fp.bendAList = bendAList
    #print(LengthList, bendAList)

    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    face = fp.baseObject[1]

    for i in range(len(LengthList)) :
      s, f = smBend(bendR = fp.radius.Value, bendA = bendAList[i], miterA1 = fp.miterangle1.Value, miterA2 = fp.miterangle2.Value, BendType = fp.BendType,  
                    flipped = fp.invert, unfold = fp.unfold, extLen = LengthList[i], gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefType = fp.reliefType,  
                    reliefW = fp.reliefw.Value, reliefD = fp.reliefd.Value, extend1 = fp.extend1.Value, extend2 = fp.extend2.Value, kfactor = fp.kfactor,
                    offset = fp.offset.Value, RelifFactor = fp.RelifFactor, UseRelifFactor = fp.UseRelifFactor, automiter = fp.AutoMiter, 
                    selFaceNames = face, MainObject = Main_Object, sketch = fp.Sketch)
      faces = smGetFace(f, s)
      face = faces
      Main_Object = s

    fp.Shape = s
    Gui.ActiveDocument.getObject(fp.baseObject[0].Name).Visibility = False
    if fp.Sketch :
      Gui.ActiveDocument.getObject(fp.Sketch.Name).Visibility = False


class SMViewProviderTree:
  "A View provider that nests children objects under the created one"
      
  def __init__(self, obj):
    obj.Proxy = self
    self.Object = obj.Object
      
  def attach(self, obj):
    self.Object = obj.Object
    return

  def updateData(self, fp, prop):
    return

  def getDisplayModes(self,obj):
    modes=[]
    return modes

  def setDisplayMode(self,mode):
    return mode

  def onChanged(self, vp, prop):
    return

  def __getstate__(self):
    #        return {'ObjectName' : self.Object.Name}
    return None

  def __setstate__(self,state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    if hasattr(self.Object,"baseObject"):
      objs.append(self.Object.baseObject[0])
    if hasattr(self.Object,"Sketch"):
      objs.append(self.Object.Sketch)
    return objs
 
  def getIcon(self):
    if isinstance(self.Object.Proxy,SMBendWall):
      return os.path.join( iconPath , 'AddWall.svg')
    elif isinstance(self.Object.Proxy,SMExtrudeWall):
      return os.path.join( iconPath , 'SMExtrude.svg')
      
  def setEdit(self,vobj,mode):
    taskd = SMBendWallTaskPanel()
    taskd.obj = vobj.Object
    taskd.update()
    self.Object.ViewObject.Visibility=False
    self.Object.baseObject[0].ViewObject.Visibility=True
    FreeCADGui.Control.showDialog(taskd)
    return True

  def unsetEdit(self,vobj,mode):
    FreeCADGui.Control.closeDialog()
    self.Object.baseObject[0].ViewObject.Visibility=False
    self.Object.ViewObject.Visibility=True
    return False
	  

class SMViewProviderFlat:
  "A View provider that places objects flat under base object"
      
  def __init__(self, obj):
    obj.Proxy = self
    self.Object = obj.Object
      
  def attach(self, obj):
    self.Object = obj.Object
    return

  def updateData(self, fp, prop):
    return

  def getDisplayModes(self,obj):
    modes=[]
    return modes

  def setDisplayMode(self,mode):
    return mode

  def onChanged(self, vp, prop):
    return

  def __getstate__(self):
    #        return {'ObjectName' : self.Object.Name}
    return None

  def __setstate__(self,state):
    if state is not None:
      import FreeCAD
      doc = FreeCAD.ActiveDocument #crap
      self.Object = doc.getObject(state['ObjectName'])

  def claimChildren(self):
    objs = []
    objs = []
    return objs
 
  def getIcon(self):
    if isinstance(self.Object.Proxy,SMBendWall):
      return os.path.join( iconPath , 'AddWall.svg')
    elif isinstance(self.Object.Proxy,SMExtrudeWall):
      return os.path.join( iconPath , 'SMExtrude.svg')

  def setEdit(self,vobj,mode):
    taskd = SMBendWallTaskPanel()
    taskd.obj = vobj.Object
    taskd.update()
    self.Object.ViewObject.Visibility=False
    self.Object.baseObject[0].ViewObject.Visibility=True
    FreeCADGui.Control.showDialog(taskd)
    return True

  def unsetEdit(self,vobj,mode):
    FreeCADGui.Control.closeDialog()
    self.Object.baseObject[0].ViewObject.Visibility=False
    self.Object.ViewObject.Visibility=True
    return False


class SMBendWallTaskPanel:
    '''A TaskPanel for the Sheetmetal'''
    def __init__(self):
      
      self.obj = None
      self.form = QtGui.QWidget()
      self.form.setObjectName("SMBendWallTaskPanel")
      self.form.setWindowTitle("Binded faces/edges list")
      self.grid = QtGui.QGridLayout(self.form)
      self.grid.setObjectName("grid")
      self.title = QtGui.QLabel(self.form)
      self.grid.addWidget(self.title, 0, 0, 1, 2)
      self.title.setText("Select new face(s)/Edge(s) and press Update")

      # tree
      self.tree = QtGui.QTreeWidget(self.form)
      self.grid.addWidget(self.tree, 1, 0, 1, 2)
      self.tree.setColumnCount(2)
      self.tree.setHeaderLabels(["Name","Subelement"])

      # buttons
      self.addButton = QtGui.QPushButton(self.form)
      self.addButton.setObjectName("addButton")
      self.addButton.setIcon(QtGui.QIcon(os.path.join( iconPath , 'SMUpdate.svg')))
      self.grid.addWidget(self.addButton, 3, 0, 1, 2)

      QtCore.QObject.connect(self.addButton, QtCore.SIGNAL("clicked()"), self.updateElement)
      self.update()

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok)

    def update(self):
      'fills the treewidget'
      self.tree.clear()
      if self.obj:
        f = self.obj.baseObject
        if isinstance(f[1],list):
          for subf in f[1]:
            #FreeCAD.Console.PrintLog("item: " + subf + "\n")
            item = QtGui.QTreeWidgetItem(self.tree)
            item.setText(0,f[0].Name)
            item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
            item.setText(1,subf)  
        else:
          item = QtGui.QTreeWidgetItem(self.tree)
          item.setText(0,f[0].Name)
          item.setIcon(0,QtGui.QIcon(":/icons/Tree_Part.svg"))
          item.setText(1,f[1][0])
      self.retranslateUi(self.form)

    def updateElement(self):
      if self.obj:
        sel = FreeCADGui.Selection.getSelectionEx()[0]
        if sel.HasSubObjects:
          obj = sel.Object
          for elt in sel.SubElementNames:
            if "Face" in elt or "Edge" in elt:
              face = self.obj.baseObject
              found = False
              if (face[0] == obj.Name):
                if isinstance(face[1],tuple):
                  for subf in face[1]:
                    if subf == elt:
                      found = True
                else:
                  if (face[1][0] == elt):
                    found = True
              if not found:
                self.obj.baseObject = (sel.Object, sel.SubElementNames)
        self.update()

    def accept(self):
        FreeCAD.ActiveDocument.recompute()
        FreeCADGui.ActiveDocument.resetEdit()
        #self.obj.ViewObject.Visibility=True
        return True

    def retranslateUi(self, TaskPanel):
        #TaskPanel.setWindowTitle(QtGui.QApplication.translate("draft", "Faces", None))
        self.addButton.setText(QtGui.QApplication.translate("draft", "Update", None))


class AddWallCommandClass():
  """Add Wall command"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'AddWall.svg') , # the name of a svg file available in the resources
            'MenuText': "Make Wall" ,
            'ToolTip' : "Extends a wall from a side face of metal sheet"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return
    doc.openTransaction("Bend")
    if activeBody is None or not smIsPartDesign(selobj):
      a = doc.addObject("Part::FeaturePython","Bend")
      SMBendWall(a)
      SMViewProviderTree(a.ViewObject)
    else:
      #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
      a = doc.addObject("PartDesign::FeaturePython","Bend")
      SMBendWall(a)
      SMViewProviderFlat(a.ViewObject)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) == Part.Vertex :
        return False
    return True

Gui.addCommand('SMMakeWall',AddWallCommandClass())

###########################################################################################
# Extrude
###########################################################################################

def smExtrude(extLength = 10.0, selFaceNames = '', selObjectName = ''):
  
#  selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
#  selObjectName = Gui.Selection.getSelection()[0].Name
  AAD = FreeCAD.ActiveDocument
  MainObject = AAD.getObject( selObjectName )
  finalShape = MainObject.Shape
  for selFaceName in selFaceNames:
    selFace = AAD.getObject(selObjectName).Shape.getElement(selFaceName)

    # extrusion direction
    V_extDir = selFace.normalAt( 0,0 )

    # extrusion
    wallFace = selFace.extrude( V_extDir*extLength )
    finalShape = finalShape.fuse( wallFace )
  
  #finalShape = finalShape.removeSplitter()
  #finalShape = Part.Solid(finalShape.childShapes()[0])  
  Gui.ActiveDocument.getObject( selObjectName ).Visibility = False
  return finalShape


  
class SMExtrudeWall:
  def __init__(self, obj):
    '''"Add Wall with radius bend" '''
    selobj = Gui.Selection.getSelectionEx()[0]
    
    obj.addProperty("App::PropertyLength","length","Parameters","Length of wall").length = 10.0
    obj.addProperty("App::PropertyDistance","gap1","Parameters","Gap from left side").gap1 = 0.0
    obj.addProperty("App::PropertyDistance","gap2","Parameters","Gap from right side").gap2 = 0.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.Proxy = self

  def execute(self, fp):

    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    face = fp.baseObject[1]

    #s = smExtrude(extLength = fp.length.Value, selFaceNames = self.selFaceNames, selObjectName = self.selObjectName)
    s,f = smBend(bendA = 0.0, extLen = fp.length.Value, gap1 = fp.gap1.Value, gap2 = fp.gap2.Value, reliefW = 0.0,
                selFaceNames = face, MainObject = Main_Object)
    fp.Shape = s
    

class SMExtrudeCommandClass():
  """Extrude face"""

  def GetResources(self):
    return {'Pixmap'  : os.path.join( iconPath , 'SMExtrude.svg') , # the name of a svg file available in the resources
            'MenuText': "Extend Face" ,
            'ToolTip' : "Extend a face along normal"}
 
  def Activated(self):
    doc = FreeCAD.ActiveDocument
    view = Gui.ActiveDocument.ActiveView
    activeBody = None
    selobj = Gui.Selection.getSelectionEx()[0].Object
    if hasattr(view,'getActiveObject'):
      activeBody = view.getActiveObject('pdbody')
    if not smIsOperationLegal(activeBody, selobj):
        return      
    doc.openTransaction("Extend")
    if (activeBody is None):
      a = doc.addObject("Part::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderTree(a.ViewObject)
    else:
      a = doc.addObject("PartDesign::FeaturePython","Extend")
      SMExtrudeWall(a)
      SMViewProviderFlat(a.ViewObject)
      activeBody.addObject(a)
    doc.recompute()
    doc.commitTransaction()
    return
   
  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) == Part.Vertex :
        return False
    return True

Gui.addCommand('SMExtrudeFace',SMExtrudeCommandClass())
