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

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

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

def smMakeReliefFace(edge, dir, gap, reliefW, reliefD, reliefType, op=''):
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
    face = Part.Face(w)
    if hasattr(face, 'mapShapes'):
        face.mapShapes([(edge,face)],[],op)
    return face

def smMakeFace(edge, dir, extLen, gap1 = 0.0,
               gap2 = 0.0, angle1 = 0.0, angle2 = 0.0, op = ''):
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
    face = Part.Face(w)
    if hasattr(face, 'mapShapes'):
        face.mapShapes([(edge,face)],None,op)
    return face

def smRestrict(var, fromVal, toVal):
    if var < fromVal:
      return fromVal
    if var > toVal:
      return toVal
    return var

def smFace(selItem, obj) :
  # find face, if Edge Selected
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

def smGetEdge(Face, obj) :
  # find Edges that overlap
  for edge in obj.Edges :
    face_common = edge.common(Face)
    if face_common.Edges :
      break
  return edge

def LineAngle(edge1, edge2) :
  # find angle between two ines
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

def LineExtend(edge, distance1, distance2):
  # Extend a ine by given distances
  pt1 = edge.valueAt(edge.FirstParameter)
  pt2 = edge.valueAt(edge.LastParameter)
  EdgeVector = pt1 - pt2
  EdgeVector.normalize()
  #print([pt1, pt2, EdgeVector] )
  ExtLine = Part.makeLine(pt1 + EdgeVector * distance1, pt2 + EdgeVector * -distance2)
  #Part.show(ExtLine,"ExtLine")
  return ExtLine

def getParallel(edge1, edge2):
  # Get intersection between two lines
  pt1 = edge1.valueAt(edge1.FirstParameter)
  pt2 = edge1.valueAt(edge1.LastParameter)
  pt3 = edge2.valueAt(edge2.FirstParameter)
  pt4 = edge2.valueAt(edge2.LastParameter)

  e1 = Part.Line(pt1, pt2).toShape()
  #Part.show(e1,'e1')
  e2 = Part.Line(pt3, pt4).toShape()
  #Part.show(e2,'e2')
  section = e1.section(e2)
  if section.Vertexes :
    #Part.show(section,'section')
    return False
  else :
    return True

def getCornerPoint(edge1, edge2):
  # Get intersection between two lines
  #Part.show(edge1,'edge1')
  #Part.show(edge2,'edge21')
  pt1 = edge1.valueAt(edge1.FirstParameter)
  pt2 = edge1.valueAt(edge1.LastParameter)
  pt3 = edge2.valueAt(edge2.FirstParameter)
  pt4 = edge2.valueAt(edge2.LastParameter)

  e1 = Part.Line(pt1, pt2).toShape()
  #Part.show(e1,'e1')
  e2 = Part.Line(pt3, pt4).toShape()
  #Part.show(e2,'e2')
  section = e1.section(e2)
  if section.Vertexes :
    #Part.show(section,'section')
    cornerPoint = section.Vertexes[0].Point
  return cornerPoint

def getGap(edge1, edge2, dist1, dist2, dist3, dist4, mingap) :
  # To find gap between two edges
  gaps = 0.0
  extgap = 0.0
  line1 = LineExtend(edge1, dist1, dist2)
  #Part.show(line1,'line1')
  line2 = LineExtend(edge2, dist3, dist4)
  #Part.show(line2,'line2')
  section =line1.section(line2)
  if section.Vertexes:
    cornerPoint = section.Vertexes[0].Point
    size1 = abs((cornerPoint - line1.Vertexes[0].Point).Length)
    size2 = abs((cornerPoint - line1.Vertexes[1].Point).Length)
    if size1 < size2:
      gaps = size1
    else:
      gaps = size2
    gaps = gaps + mingap
    #print(gaps)
  else :
    cornerPoint = getCornerPoint(edge1, edge2)
#    if cornerPoint != 0 :
    size1 = abs((cornerPoint - line1.Vertexes[0].Point).Length)
    size2 = abs((cornerPoint - line1.Vertexes[1].Point).Length)
    if size1 < size2:
      extgap = size1
    else:
      extgap = size2
    extgap = extgap - mingap
    #print(extgap)
  return gaps, extgap, cornerPoint

def getSketchDetails(Sketch, sketchflip, sketchinvert, radius, thk) :
  # Covert Sketch lines to length. Angles between line
  LengthList, bendAList = ([],[])
  sketch_normal = Sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
  e0 = Sketch.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
  WireList = Sketch.Shape.Wires[0]

  # Create filleted wire at centre of thickness
  wire_extr = WireList.extrude(sketch_normal * -50)
  #Part.show(wire_extr,"wire_extr")
  wire_extr_mir = WireList.extrude(sketch_normal * 50)
  #Part.show(wire_extr_mir,"wire_extr_mir")
  wire_extr = wire_extr.makeOffsetShape(thk/2.0, 0.0, fill = False, join = 2)
  #Part.show(wire_extr,"wire_extr")
  wire_extr_mir = wire_extr_mir.makeOffsetShape(-thk/2.0, 0.0, fill = False, join = 2)
  #Part.show(wire_extr_mir,"wire_extr_mir")
  if len(WireList.Edges) > 1 :
    filleted_extr = wire_extr.makeFillet((radius + thk / 2.0), wire_extr.Edges)
    #Part.show(filleted_extr,"filleted_extr")
    filleted_extr_mir = wire_extr_mir.makeFillet((radius + thk / 2.0), wire_extr_mir.Edges)
    #Part.show(filleted_extr_mir,"filleted_extr_mir")
  else :
    filleted_extr = wire_extr
    filleted_extr_mir = wire_extr_mir
  #Part.show(filleted_extr,"filleted_extr")
  sec_wirelist = filleted_extr_mir.section(filleted_extr)
  #Part.show(sec_wirelist,"sec_wirelist")

  for edge in sec_wirelist.Edges :
    if isinstance(edge.Curve, Part.Line) :
      LengthList.append(edge.Length)    

  for i in range(len(WireList.Vertexes)-1) :
    p1 = WireList.Vertexes[i].Point
    p2 = WireList.Vertexes[i+1].Point
    e1 = p2 - p1
 #   LengthList.append(e1.Length)
    normal = e0.cross(e1)
    coeff = sketch_normal.dot(normal)
    if coeff >= 0:
      sign = 1
    else:
      sign = -1
    angle_rad = e0.getAngle(e1)
    if sketchflip :
      angle = sign*math.degrees(angle_rad) * -1
    else :
      angle = sign*math.degrees(angle_rad)
    bendAList.append(angle)
    e0 = e1
  if sketchinvert :
    LengthList.reverse()
    bendAList.reverse()
  #print(LengthList, bendAList)
  return LengthList, bendAList

def sheet_thk(MainObject, selFaceName) :
  selItem = MainObject.getElement(selFaceName)
  selFace = smFace(selItem, MainObject)
  # find the narrow edge
  thk = 999999.0
  for edge in selFace.Edges:
    if abs( edge.Length ) < thk:
      thk = abs(edge.Length)
  return thk

def getBendetail(selFaceNames, MainObject, bendR, bendA, flipped):
  mainlist =[]
  for selFaceName in selFaceNames :
    selItem = MainObject.getElement(selFaceName)
    selFace = smFace(selItem, MainObject)

    # find the narrow edge
    thk = 999999.0
    for edge in selFace.Edges:
      if abs( edge.Length ) < thk:
        thk = abs(edge.Length)
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
        break
      if (p2 - p0).Length < smEpsilon:
        revAxisV = p1 - p2
        break

    # find the large face connected with selected face
    list2 = MainObject.ancestorsOfType(lenEdge, Part.Face)
    for Cface in list2 :
      if not(Cface.isSame(selFace)) :
        break

    # main Length Edge
    revAxisV.normalize()
    thkDir = Cface.normalAt(0,0) * -1
    FaceDir = selFace.normalAt(0,0)

    #make sure the direction verctor is correct in respect to the normal
    if (thkDir.cross(revAxisV).normalize() - FaceDir).Length < smEpsilon:
     revAxisV = revAxisV * -1

    # restrict angle
    if (bendA < 0):
      bendA = -bendA
      flipped = not flipped

    if not(flipped):
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * (bendR + thk)
      revAxisV = revAxisV * -1
    else:
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * -bendR

    #Part.show(lenEdge,'lenEdge')
    mainlist.append([Cface, selFace, thk, lenEdge, revAxisP, revAxisV, thkDir, FaceDir, bendA, flipped])
  #print(mainlist)
  return mainlist

def smMiter(mainlist, bendR = 1.0, miterA1 = 0.0, miterA2 = 0.0, extLen = 10.0, gap1 = 0.0, gap2 = 0.0,offset = 0.0, 
              reliefD = 1.0, automiter = True, extend1 = 0.0, extend2 = 0.0, mingap = 0.1, maxExtendGap = 5.0):

  if not(automiter) :
    miterA1List = [miterA1 for n in range(len(mainlist))]
    miterA2List = [miterA2 for n in range(len(mainlist))]
    gap1List = [gap1 for n in range(len(mainlist))]
    gap2List = [gap2 for n in range(len(mainlist))]
    extgap1List = [extend1 for n in range(len(mainlist))]
    extgap2List = [extend2 for n in range(len(mainlist))]
    reliefDList = [reliefD for n in range(len(mainlist))]
  else :
    miterA1List = [0.0 for n in range(len(mainlist))]
    miterA2List = [0.0 for n in range(len(mainlist))]
    gap1List = [gap1 for n in range(len(mainlist))]
    gap2List = [gap2 for n in range(len(mainlist))]
    extgap1List = [extend1 for n in range(len(mainlist))]
    extgap2List = [extend2 for n in range(len(mainlist))]
    reliefDList = [reliefD for n in range(len(mainlist))]

    facelist, tranfacelist = ([], [])
    extfacelist, exttranfacelist = ([], [])
    lenedgelist, tranedgelist = ([], [])
    for i, sublist in enumerate(mainlist):
      # find the narrow edge
      Cface, selFace, thk, lenEdge, revAxisP, revAxisV, thkDir, FaceDir, bendA, flipped = sublist

      # Produce Offset Edge
      if offset > 0.0 :
        lenEdge.translate(FaceDir * offset)

      # narrow the wall, if we have gaps
      BendFace = smMakeFace(lenEdge, FaceDir, extLen, 
              gap1-extend1, gap2-extend2, op='SMB')
      if BendFace.normalAt(0,0) != thkDir :
        BendFace.reverse()
      transBendFace = BendFace.copy()
      BendFace.rotate(revAxisP, revAxisV, bendA)
      #Part.show(BendFace,'BendFace')
      facelist.append(BendFace)
      transBendFace.translate(thkDir * thk)
      transBendFace.rotate(revAxisP, revAxisV, bendA)
      tranfacelist.append(transBendFace)

      # narrow the wall, if we have gaps
      BendFace = smMakeFace(lenEdge, FaceDir, extLen, 
              gap1-extend1-maxExtendGap, gap2-extend2-maxExtendGap, op='SMB')
      if BendFace.normalAt(0,0) != thkDir :
        BendFace.reverse()
      transBendFace = BendFace.copy()
      BendFace.rotate(revAxisP, revAxisV, bendA)
      #Part.show(BendFace,'BendFace')
      extfacelist.append(BendFace)
      transBendFace.translate(thkDir * thk)
      transBendFace.rotate(revAxisP, revAxisV, bendA)
      exttranfacelist.append(transBendFace)

      edge_len = lenEdge.copy()
      edge_len.rotate(revAxisP, revAxisV, bendA)
      lenedgelist.append(edge_len)
      #Part.show(edge_len,'edge_len')
      edge_len = lenEdge.copy()
      edge_len.translate(thkDir * thk)
      edge_len.rotate(revAxisP, revAxisV, bendA)
      tranedgelist.append(edge_len)
      #Part.show(edge_len,'edge_len')

    # check faces intersect each other
    for i in range(len(facelist)) :
      for j in range(len(lenedgelist)) :
        if i != j and facelist[i].isCoplanar(facelist[j]) and not(getParallel(lenedgelist[i], lenedgelist[j])) :
          #Part.show(lenedgelist[i],'edge_len1')
          #Part.show(lenedgelist[j],'edge_len2')
          gaps1, extgap1, cornerPoint1 = getGap(lenedgelist[i], lenedgelist[j], extend1, extend2, extend1, extend2, mingap)
          gaps2, extgap2, cornerPoint2 = getGap(tranedgelist[i], tranedgelist[j], extend1, extend2, extend1, extend2, mingap)
          #print([gaps1,gaps2, extgap1, extgap2])
          gaps = max(gaps1, gaps2)
          extgap = min(extgap1, extgap2)
          p1 = lenedgelist[j].valueAt(lenedgelist[j].FirstParameter)
          p2 = lenedgelist[j].valueAt(lenedgelist[j].LastParameter)
          Angle = LineAngle(lenedgelist[i], lenedgelist[j])
          #print(Angle)
          if gaps >=  extgap :
            wallface_common = facelist[j].section(facelist[i])
            vp1 = wallface_common.Vertexes[0].Point
            dist1 = (p1-vp1).Length
            dist2 = (p2-vp1).Length
            if abs(dist1) < abs(dist2) :
              miterA1List[j] = Angle / 2.0 
              if gaps > 0.0 :
                gap1List[j] = gaps
              else:
                gap1List[j] = 0.0
            elif abs(dist2) < abs(dist1) :
              miterA2List[j] = Angle / 2.0
              if gaps > 0.0 :
                gap2List[j] = gaps
              else:
                gap2List[j] = 0.0
            reliefDList[j] = 0.0
          elif gaps <  extgap :
            wallface_common = facelist[j].common(facelist[i])
            dist1 = (p1-cornerPoint1).Length
            dist2 = (p2-cornerPoint1).Length
            if abs(dist1) < abs(dist2) and extgap <= maxExtendGap:
              if wallface_common.Faces :
                miterA1List[j] = Angle / 2.0 
              else:
                miterA1List[j] = -Angle / 2.0 
              if extgap > 0.0  :
                extgap1List[j] = extgap
              else:
                extgap1List[j] = 0.0
            elif abs(dist2) < abs(dist1)  and extgap <= maxExtendGap:
              if wallface_common.Faces :
                miterA2List[j] = Angle / 2.0
              else :
                miterA2List[j] = -Angle / 2.0
              if extgap > 0.0 :
                extgap2List[j] = extgap
              else:
                extgap2List[j] = 0.0
            reliefDList[j] = 0.0
        elif i != j and not(getParallel(lenedgelist[i], lenedgelist[j])) :
          #Part.show(lenedgelist[i],'edge_len1')
          #Part.show(lenedgelist[j],'edge_len2')
          gaps1, extgap1, cornerPoint1 = getGap(lenedgelist[i], lenedgelist[j], extend1, extend2, extend1, extend2, mingap)
          gaps2, extgap2, cornerPoint2 = getGap(tranedgelist[i], tranedgelist[j], extend1, extend2, extend1, extend2, mingap)
          #print([gaps1,gaps2, extgap1, extgap2])
          gaps = max(gaps1, gaps2)
          extgap = min(extgap1, extgap2)
          p1 = lenedgelist[j].valueAt(lenedgelist[j].FirstParameter)
          p2 = lenedgelist[j].valueAt(lenedgelist[j].LastParameter)
          if gaps >=  extgap :
            wallface_common = facelist[j].section(facelist[i])
            wallface_common1 = tranfacelist[j].section(tranfacelist[i])
            #Part.show(wallface_common,'wallface_common')
            if wallface_common.Edges :
              vp1 = wallface_common.Vertexes[0].Point
              vp2 = wallface_common.Vertexes[1].Point
            elif wallface_common1.Edges :
              vp1 = wallface_common1.Vertexes[0].Point
              vp2 = wallface_common1.Vertexes[1].Point
            dist1 = (p1 - vp1).Length
            dist2 = (p2 - vp1).Length
            if abs(dist1) < abs(dist2) :
              edgedir = (p1 - p2).normalize()
              dist3 = (p1 - vp1).Length
              dist4 = (p1 - vp2).Length
              if dist4 < dist3 :
                lineDir = (vp2 - vp1).normalize()
              else :
                lineDir = (vp1 - vp2).normalize()
              angle1 = edgedir.getAngle(lineDir)
              Angle2 = math.degrees(angle1)
              Angle = 90 - Angle2
              #print([Angle, Angle2, 'ext'])
              miterA1List[j] = Angle
              if gaps > 0.0 :
                gap1List[j] = gaps
              else:
                gap1List[j] = 0.0
            elif abs(dist2) < abs(dist1) :
              edgedir = (p2 - p1).normalize()
              dist3 = (p2 - vp1).Length
              dist4 = (p2 - vp2).Length
              if dist4 < dist3 :
                lineDir = (vp2 - vp1).normalize()
              else :
                lineDir = (vp1 - vp2).normalize()
              angle1 = edgedir.getAngle(lineDir)
              Angle2 = math.degrees(angle1)
              Angle = 90 - Angle2
              #print([Angle, Angle2, 'ext'])
              miterA2List[j] = Angle
              if gaps > 0.0 :
                gap2List[j] = gaps
              else:
                gap2List[j] = 0.0
            reliefDList[j] = 0.0
          elif gaps <  extgap :
            wallface_common = extfacelist[j].section(extfacelist[i])
            wallface_common1 = exttranfacelist[j].section(exttranfacelist[i])
            #Part.show(wallface_common,'wallface_common')
            if wallface_common.Edges :
              vp1 = wallface_common.Vertexes[0].Point
              vp2 = wallface_common.Vertexes[1].Point
            elif wallface_common1.Edges :
              vp1 = wallface_common1.Vertexes[0].Point
              vp2 = wallface_common1.Vertexes[1].Point
            dist1 = (p1 - vp1).Length
            dist2 = (p2 - vp1).Length
            if abs(dist1) < abs(dist2) :
              edgedir = (p1 - p2).normalize()
              dist3 = (p1 - vp1).Length
              dist4 = (p1 - vp2).Length
              if dist4 < dist3 :
                lineDir = (vp2 - vp1).normalize()
              else :
                lineDir = (vp1 - vp2).normalize()
              angle1 = edgedir.getAngle(lineDir)
              Angle2 = math.degrees(angle1)
              Angle = 90 - Angle2
              #print([Angle, Angle2, 'ext'])
              miterA1List[j] = Angle
              if extgap > 0.0 and extgap <= maxExtendGap:
                extgap1List[j] = extgap
              else:
                extgap1List[j] = 0.0
            elif abs(dist2) < abs(dist1) :
              edgedir = (p2 - p1).normalize()
              dist3 = (p2 - vp1).Length
              dist4 = (p2 - vp2).Length
              if dist4 < dist3 :
                lineDir = (vp2 - vp1).normalize()
              else :
                lineDir = (vp1 - vp2).normalize()
              angle1 = edgedir.getAngle(lineDir)
              Angle2 = math.degrees(angle1)
              Angle = 90 - Angle2
              #print([Angle, Angle2, 'ext'])
              miterA2List[j] = Angle
              if extgap > 0.0  and extgap <= maxExtendGap:
                extgap2List[j] = extgap
              else:
                extgap2List[j] = 0.0
            reliefDList[j] = 0.0

  #print(miterA1List, miterA2List, gap1List, gap2List, extgap1List, extgap2List, reliefDList)
  return miterA1List, miterA2List, gap1List, gap2List, extgap1List, extgap2List, reliefDList

def smBend(bendR = 1.0, bendA = 90.0, miterA1 = 0.0,miterA2 = 0.0, BendType = "Material Outside", flipped = False, unfold = False, 
            offset = 0.0, extLen = 10.0, gap1 = 0.0, gap2 = 0.0, reliefType = "Rectangle", reliefW = 0.8, reliefD = 1.0, extend1 = 0.0, 
            extend2 = 0.0, kfactor = 0.45, ReliefFactor = 0.7, UseReliefFactor = False, selFaceNames = '', MainObject = None, 
            maxExtendGap = 5.0, mingap = 0.1, automiter = True, sketch = None, extendType ="Simple"):

  # if sketch is as wall 
  sketches = False
  if sketch :
    if sketch.Shape.Wires[0].isClosed() :
      sketches = True
    else :
      pass

  if not(sketches) :
    mainlist = getBendetail(selFaceNames, MainObject, bendR, bendA, flipped)
    miterA1List, miterA2List, gap1List, gap2List, extend1List, extend2List, reliefDList = smMiter(mainlist, 
                  bendR = bendR, miterA1 = miterA1, miterA2 = miterA2, extLen = extLen, gap1 = gap1,  gap2 = gap2,
                  offset = offset, reliefD = reliefD, automiter = automiter, extend1 = extend1, extend2 = extend2, 
                  mingap = mingap, maxExtendGap = maxExtendGap)

    #print(miterA1List, miterA2List, gap1List, gap2List, extend1List, extend2List,reliefDList,)
  else :
    miterA1List, miterA2List, gap1List, gap2List, extend1List, extend2List, reliefDList = ( [0.0], [0.0], [gap1], [gap2], [extend1], [extend2],[reliefD])

  mainlist = getBendetail(selFaceNames, MainObject, bendR, bendA, flipped)
  thk_faceList = []
  resultSolid = MainObject
  for i, sublist in enumerate(mainlist):
    # find the narrow edge
    Cface, selFace, thk, lenEdge, revAxisP, revAxisV, thkDir, FaceDir, bendA, flipped = sublist
    gap1, gap2 = (gap1List[i], gap2List[i])
    reliefD = reliefDList[i]
    extend1, extend2 = (extend1List[i], extend2List[i])
    #Part.show(lenEdge,'lenEdge1')
    selFace = smModifiedFace(selFace, resultSolid)
    Cface = smModifiedFace(Cface, resultSolid)
    lenEdge = smGetEdge(lenEdge, resultSolid)
    #Part.show(lenEdge,'lenEdge')

    # Add as offset to set any distance
    if UseReliefFactor :
      reliefW = thk * ReliefFactor
      reliefD = thk * ReliefFactor

    # Add Bend Type details
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

    # Produce Offset Edge
    if offset > 0.0 :
      lenEdge.translate(selFace.normalAt(0,0) * offset)

    # main Length Edge
    MlenEdge = lenEdge
    leng = MlenEdge.Length
    #Part.show(MlenEdge,'MlenEdge')

    # Get correct size inside face
    if inside :
      e1 = MlenEdge.copy()
      e1.translate(FaceDir * offset)
      EdgeShape = e1.common(Cface)
      lenEdge = EdgeShape.Edges[0]
      Noffset1 = abs((MlenEdge.valueAt(MlenEdge.FirstParameter)-lenEdge.valueAt(lenEdge.FirstParameter)).Length)
#      Noffset2 = abs((MlenEdge.valueAt(MlenEdge.LastParameter)-lenEdge.valueAt(lenEdge.LastParameter)).Length)
    #Part.show(lenEdge,'lenEdge')

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

    # Get angles of adjacent face
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
          if abs((MlenEdge.valueAt(MlenEdge.FirstParameter)- ed.valueAt(ed.LastParameter)).Length) < smEpsilon:
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
          if abs((MlenEdge.valueAt(MlenEdge.LastParameter)- ed.valueAt(ed.FirstParameter)).Length) < smEpsilon:
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

    reliefDn = reliefD
    if inside :
      reliefDn = reliefD + abs(offset)

    # CutSolids list for collecting Solids
    CutSolids = []

    # remove relief if needed
    if reliefD > 0.0 :
      if reliefW > 0.0 and ( gap1 > 0.0 or Agap1 > 0.0 ):
        reliefFace1 = smMakeReliefFace(MlenEdge, FaceDir* -1, gap1-reliefW,
                reliefW, reliefDn, reliefType, op='SMF')
        reliefSolid1 = reliefFace1.extrude(thkDir * thk)
        #Part.show(reliefSolid1)
        CutSolids.append(reliefSolid1)
      if reliefW > 0.0 and ( gap2 > 0.0 or Agap2 > 0.0 ):
        reliefFace2 = smMakeReliefFace(MlenEdge, FaceDir* -1, leng-gap2,
                reliefW, reliefDn, reliefType, op='SMFF')
        reliefSolid2 = reliefFace2.extrude(thkDir * thk)
        #Part.show(reliefSolid2)
        CutSolids.append(reliefSolid2)

    # remove bend face if present
    if inside :
      if gap1 == 0.0 or (reliefD == 0.0 and gap1 == 0.1) :
        Edgelist = selFace.ancestorsOfType(vertex0, Part.Edge)
        for ed in Edgelist :
          if not(MlenEdge.isSame(ed)):
            list1 = resultSolid.ancestorsOfType(ed, Part.Face)
            for Rface in list1 :
              #print(type(Rface.Surface))
              if not(selFace.isSame(Rface)):
                for edge in Rface.Edges:
                  #print(type(edge.Curve))
                  if issubclass(type(edge.Curve),(Part.Circle or Part.BSplineSurface)):
                    RfaceE = Rface.makeOffsetShape(-Noffset1, 0.0, fill = True)
                    #Part.show(RfaceE,"RfaceSolid1")
                    CutSolids.append(RfaceE)
                    break

      if gap2 == 0.0 or (reliefD == 0.0 and gap2 == 0.1) :
        Edgelist = selFace.ancestorsOfType(vertex1, Part.Edge)
        for ed in Edgelist :
          if not(MlenEdge.isSame(ed)):
            list1 = resultSolid.ancestorsOfType(ed, Part.Face)
            for Rface in list1 :
              #print(type(Rface.Surface))
              if not(selFace.isSame(Rface)):
                for edge in Rface.Edges:
                  #print(type(edge.Curve))
                  if issubclass(type(edge.Curve),(Part.Circle or Part.BSplineSurface)):
                    RfaceE = Rface.makeOffsetShape(-Noffset1, 0.0, fill = True)
                    #Part.show(RfaceE,"RfaceSolid2")
                    CutSolids.append(RfaceE)
                    break

      if reliefD == 0.0 and ( gap1 == 0.1 or gap2 == 0.1 ) :
        CutFace = smMakeFace(MlenEdge, thkDir, thk, 0, 0, op='SMC')
      else :
        CutFace = smMakeFace(MlenEdge, thkDir, thk, gap1, gap2, op='SMC')
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
      offset_face = smMakeFace(lenEdge, FaceDir, -offset, op='SMO')
      OffsetSolid = offset_face.extrude(thkDir * thk)
      resultSolid = resultSolid.fuse(OffsetSolid)

    # Adjust revolving center to new point
    if not(flipped):
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * (bendR + thk)
    else:
      revAxisP = lenEdge.valueAt(lenEdge.FirstParameter) + thkDir * -bendR

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
      Wall_face = smMakeFace(lenEdge, FaceDir, extLen, gap1-extend1,
              gap2-extend2, miterA1List[i], miterA2List[i], op='SMW')
      wallSolid = Wall_face.extrude(thkDir * thk)
      #Part.show(wallSolid,"wallSolid")
      wallSolid.rotate(revAxisP, revAxisV, bendA)
      #Part.show(wallSolid.Faces[2])
      thk_faceList.append(wallSolid.Faces[2])

    # Produce bend Solid
    if not(unfold) :
      if bendA > 0.0 :
        # create bend
        # narrow the wall if we have gaps
        revFace = smMakeFace(lenEdge, thkDir, thk, gap1, gap2, op='SMR')
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
        unfoldLength = ( bendR + kfactor * thk ) * bendA * math.pi / 180.0
        # narrow the wall if we have gaps
        unfoldFace = smMakeFace(lenEdge, thkDir, thk, gap1, gap2, op='SMR')
        if unfoldFace.normalAt(0,0) != FaceDir :
          unfoldFace.reverse()
        unfoldSolid = unfoldFace.extrude(FaceDir * unfoldLength)
        #Part.show(unfoldSolid)
        resultSolid = resultSolid.fuse(unfoldSolid)

      if extLen > 0.0 :
        wallSolid.rotate(revAxisP, revAxisV, -bendA)
        #Part.show(wallSolid, "wallSolid")
        wallSolid.translate(FaceDir * unfoldLength)
        resultSolid = resultSolid.fuse(wallSolid)
  #Part.show(resultSolid, "resultSolid")
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
    obj.addProperty("App::PropertyBool","UseReliefFactor","ParametersRelief","Use Relief Factor").UseReliefFactor = False
    obj.addProperty("App::PropertyFloat","ReliefFactor","ParametersRelief","Relief Factor").ReliefFactor = 0.7
    obj.addProperty("App::PropertyLength","reliefw","ParametersRelief","Relief width").reliefw = 0.8
    obj.addProperty("App::PropertyLength","reliefd","ParametersRelief","Relief depth").reliefd = 1.0
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", "Base object").baseObject = (selobj.Object, selobj.SubElementNames)
    obj.addProperty("App::PropertyDistance","extend1","ParametersEx","extend from left side").extend1 = 0.0
    obj.addProperty("App::PropertyDistance","extend2","ParametersEx","extend from right side").extend2 = 0.0
    obj.addProperty("App::PropertyBool","AutoMiter","ParametersEx","Auto Miter").AutoMiter = True
    obj.addProperty("App::PropertyLength","minGap","ParametersEx","Auto Miter minimum Gap").minGap = 0.1
    obj.addProperty("App::PropertyLength","maxExtendDist","ParametersEx","Auto Miter maximum Extend Distance").maxExtendDist = 5.0
    obj.addProperty("App::PropertyAngle","miterangle1","ParametersEx","Bend miter angle").miterangle1 = 0.0
    obj.addProperty("App::PropertyAngle","miterangle2","ParametersEx","Bend miter angle").miterangle2 = 0.0
    obj.addProperty("App::PropertyDistance","offset","ParametersEx","offset Bend").offset = 0.0
    obj.addProperty("App::PropertyBool","unfold","ParametersEx","Invert bend direction").unfold = False
    obj.addProperty("App::PropertyFloatConstraint","kfactor","ParametersEx","Location of neutral line. Caution: Using ANSI standards, not DIN.").kfactor = (0.5,0.0,1.0,0.01)
    obj.addProperty("App::PropertyLink", "Sketch", "ParametersEx2", "Sketch object")
    obj.addProperty("App::PropertyBool","sketchflip","ParametersEx2","flip sketch direction").sketchflip = False
    obj.addProperty("App::PropertyBool","sketchinvert","ParametersEx2","invert sketch start").sketchinvert = False
    obj.addProperty("App::PropertyFloatList", "LengthList", "ParametersEx3", "Length of Wall List")
    obj.addProperty("App::PropertyFloatList", "bendAList", "ParametersEx3", "Bend angle List")
    obj.Proxy = self

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    if (not hasattr(fp,"miterangle1")):
      fp.addProperty("App::PropertyAngle","miterangle1","ParametersMiterangle","Bend miter angle").miterangle1 = 0.0
      fp.addProperty("App::PropertyAngle","miterangle2","ParametersMiterangle","Bend miter angle").miterangle2 = 0.0

    if (not hasattr(fp,"AutoMiter")):
      fp.addProperty("App::PropertyBool","AutoMiter","ParametersEx","Auto Miter").AutoMiter = True

    if (not hasattr(fp,"reliefType")):
      fp.addProperty("App::PropertyEnumeration", "reliefType", "ParametersRelief","Relief Type").reliefType = ["Rectangle", "Round"]

    if (not hasattr(fp,"extend1")):
      fp.addProperty("App::PropertyDistance","extend1","Parameters","extend from left side").extend1 = 0.0
      fp.addProperty("App::PropertyDistance","extend2","Parameters","extend from right side").extend2 = 0.0

    if (not hasattr(fp,"unfold")):
      fp.addProperty("App::PropertyBool","unfold","ParametersEx","Invert bend direction").unfold = False

    if (not hasattr(fp,"kfactor")):
      fp.addProperty("App::PropertyFloatConstraint","kfactor","ParametersEx","Location of neutral line. Caution: Using ANSI standards, not DIN.").kfactor = (0.5,0.0,1.0,0.01)

    if (not hasattr(fp,"BendType")):
      fp.addProperty("App::PropertyEnumeration", "BendType", "Parameters","Bend Type").BendType = ["Material Outside", "Material Inside", "Thickness Outside", "Offset"]
      fp.addProperty("App::PropertyDistance","offset","ParametersEx","offset Bend").offset = 0.0

    if (not hasattr(fp,"ReliefFactor")):
      fp.addProperty("App::PropertyBool","UseReliefFactor","ParametersRelief","Use Relief Factor").UseReliefFactor = False
      fp.addProperty("App::PropertyFloat","ReliefFactor","ParametersRelief","Relief Factor").ReliefFactor = 0.7

    if (not hasattr(fp,"Sketch")):
      fp.addProperty("App::PropertyLink", "Sketch", "ParametersEx2", "Sketch object")
      fp.addProperty("App::PropertyBool","sketchflip","ParametersEx2","flip sketch direction").sketchflip = False
      fp.addProperty("App::PropertyBool","sketchinvert","ParametersEx2","invert sketch start").sketchinvert = False
      fp.addProperty("App::PropertyFloatList", "LengthList", "ParametersEx3", "Length of Wall List")
      fp.addProperty("App::PropertyFloatList", "bendAList", "ParametersEx3", "Bend angle List")

    if (not hasattr(fp,"minGap")):
      fp.addProperty("App::PropertyLength","minGap","ParametersEx","Auto Miter minimum Gap").minGap = 0.1
      fp.addProperty("App::PropertyLength","maxExtendDist","ParametersEx","Auto Miter maximum Extend Distance").maxExtendDist = 5.0
    # restrict some params
    fp.miterangle1.Value = smRestrict(fp.miterangle1.Value, -80.0, 80.0)
    fp.miterangle2.Value = smRestrict(fp.miterangle2.Value, -80.0, 80.0)

    # get LengthList, bendAList
    bendAList = [fp.angle.Value]
    LengthList = [fp.length.Value]
    #print face

    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    face = fp.baseObject[1]
    thk = sheet_thk(Main_Object, face[0])

    if fp.Sketch :
      WireList = fp.Sketch.Shape.Wires[0]
      if not(WireList.isClosed()) :
        LengthList, bendAList = getSketchDetails(fp.Sketch, fp.sketchflip, fp.sketchinvert, fp.radius.Value, thk)
      else :
        if fp.Sketch.Support :
          fp.baseObject = (fp.Sketch.Support[0][0], fp.Sketch.Support[0][1] )
        LengthList = [10.0]
    fp.LengthList = LengthList
    fp.bendAList = bendAList
    #print(LengthList, bendAList)

    # extend value needed for first bend set only
    extend1_list =[0.0 for n in range(len(LengthList))]
    extend2_list =[0.0 for n in range(len(LengthList))]
    extend1_list[0] = fp.extend1.Value
    extend2_list[0] = fp.extend2.Value
    #print(extend1_list, extend2_list)

    # gap value needed for first bend set only
    gap1_list =[0.0 for n in range(len(LengthList))]
    gap2_list =[0.0 for n in range(len(LengthList))]
    gap1_list[0] = fp.gap1.Value
    gap2_list[0] = fp.gap2.Value
    #print(gap1_list, gap2_list)

    for i in range(len(LengthList)) :
      s, f = smBend(bendR = fp.radius.Value, bendA = bendAList[i], miterA1 = fp.miterangle1.Value, miterA2 = fp.miterangle2.Value,  
                    BendType = fp.BendType, flipped = fp.invert, unfold = fp.unfold, extLen = LengthList[i], 
                    reliefType = fp.reliefType, gap1 = gap1_list[i], gap2 = gap2_list[i], reliefW = fp.reliefw.Value, 
                    reliefD = fp.reliefd.Value, extend1 = extend1_list[i], extend2 = extend2_list[i], kfactor = fp.kfactor,
                    offset = fp.offset.Value, ReliefFactor = fp.ReliefFactor, UseReliefFactor = fp.UseReliefFactor, 
                    automiter = fp.AutoMiter, selFaceNames = face, MainObject = Main_Object, sketch = fp.Sketch, 
                    mingap = fp.minGap.Value, maxExtendGap = fp.maxExtendDist.Value)
      faces = smGetFace(f, s)
      face = faces
      Main_Object = s

    fp.Shape = s
    fp.baseObject[0].ViewObject.Visibility = False
    if fp.Sketch :
      fp.Sketch.ViewObject.Visibility = False


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
    return os.path.join( iconPath , 'SheetMetal_AddWall.svg')

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
    if hasattr(self.Object,"Sketch"):
      objs.append(self.Object.Sketch)
    return objs
 
  def getIcon(self):
    return os.path.join( iconPath , 'SheetMetal_AddWall.svg')

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
      self.addButton.setIcon(QtGui.QIcon(os.path.join( iconPath , 'SheetMetal_Update.svg')))
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
    return {'Pixmap'  : os.path.join( iconPath , 'SheetMetal_AddWall.svg'), # the name of a svg file available in the resources
            'MenuText': QtCore.QT_TRANSLATE_NOOP('SheetMetal','Make Wall'),
            'ToolTip' : QtCore.QT_TRANSLATE_NOOP('SheetMetal','Extends a wall from a side face of metal sheet')}

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
    FreeCADGui.Selection.clearSelection()
    doc.recompute()
    doc.commitTransaction()
    return

  def IsActive(self):
    if len(Gui.Selection.getSelection()) < 1 or len(Gui.Selection.getSelectionEx()[0].SubElementNames) < 1:
      return False
    selobj = Gui.Selection.getSelection()[0]
    if selobj.isDerivedFrom("Sketcher::SketchObject"):
      return False
    for selFace in Gui.Selection.getSelectionEx()[0].SubObjects:
      if type(selFace) == Part.Vertex :
        return False
    return True

Gui.addCommand('SMMakeWall',AddWallCommandClass())

