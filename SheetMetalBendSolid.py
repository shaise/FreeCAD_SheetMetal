# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalBendSolid.py
#
#  Copyright 2020 Jaise James <jaisejames at gmail dot com>
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

import Part, math

def getPointOnCylinder(zeroVert, poi, Radius, circent, axis, zeroVertNormal):
    dist = zeroVert.distanceToPlane(poi, zeroVertNormal)
    poi1 = poi.projectToPlane(zeroVert, zeroVertNormal)
    angle = dist / Radius
    axis = axis * -1
    #print([dist, angle])
    vec = poi1 - circent
    rVec = vec * math.cos(angle) + axis * ( axis.dot(vec)) * (1 - math.cos(angle)) + vec.cross(axis) * math.sin(angle)
    Point = circent + rVec
    #print([rVec,Point])
    return Point

def WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal):
    poles = bspline.getPoles()
    newpoles = []
    for poi in poles:
        bPoint = getPointOnCylinder(zeroVert, poi, Radius, cent, axis, zeroVertNormal)
        newpoles.append(bPoint)
    newbspline = bspline
    newbspline.buildFromPolesMultsKnots(newpoles, bspline.getMultiplicities(),
      bspline.getKnots(), bspline.isPeriodic(), bspline.Degree, bspline.getWeights())
    return newbspline.toShape()

def WrapFace(Face, Radius, axis, normal, zeroVert, cent, zeroVertNormal):
#    circent = cent
    Edges = []
    for e in Face.Edges:
        #print(type(e.Curve))
        if isinstance(e.Curve, (Part.Circle, Part.ArcOfCircle)) :
            #bspline = gg.Curve.toBSpline()
            poles = e.discretize(Number=50)
            bspline=Part.BSplineCurve()
            bspline.interpolate(poles)
            #bs = bspline.toShape()
            #Part.show(bs,"bspline")
            Edges.append(WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal))

        elif isinstance(e.Curve, Part.BSplineCurve) :
            Edges.append(WrapBSpline(e.Curve, Radius, zeroVert, cent, axis, zeroVertNormal))

        elif isinstance(e.Curve, Part.Line) :
            sp = e.valueAt(e.FirstParameter)
            ep = e.valueAt(e.LastParameter)
            dist1 = abs(sp.distanceToPlane(cent, normal))
            dist2 = abs(ep.distanceToPlane(cent, normal))
            #print(dist1,dist2)
            linenormal = ep - sp
            mp = sp + linenormal / 2.0
            linenormal.normalize()
            #print(linenormal.dot(axis))
            #print(linenormal.dot(normal))
            if  linenormal.dot(axis) == 0.0 and (dist2 - dist1) == 0.0:
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, mp, Radius, cent, axis, zeroVertNormal)
                Point3 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                arc = Part.Arc(Point1,Point2,Point3)
                Edges.append(arc.toShape())
            elif linenormal.dot(axis) == 1.0  or linenormal.dot(axis) == -1.0 :
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                #print([Point1,Point2])
                Edges.append(Part.makeLine(Point1, Point2))
            elif linenormal.dot(normal) == 1.0  or linenormal.dot(normal) == -1.0 :
                Point1 = getPointOnCylinder(zeroVert, sp, Radius, cent, axis, zeroVertNormal)
                Point2 = getPointOnCylinder(zeroVert, ep, Radius, cent, axis, zeroVertNormal)
                #print([Point1,Point2])
                Edges.append(Part.makeLine(Point1, Point2))
            else :
                poles = e.discretize(Number=50)
                #print(poles)
                bspline=Part.BSplineCurve()
                bspline.interpolate(poles, PeriodicFlag=False)
                #bs = bspline.toShape()
                #Part.show(bs,"bspline")
                #bspline = disgg.toBSpline()
                Edges.append(WrapBSpline(bspline, Radius, zeroVert, cent, axis, zeroVertNormal))
    return Edges

def BendSolid(SelFace, SelEdge, BendR, thk, neutralRadius, Axis, flipped):
    normal = SelFace.normalAt(0,0)
    zeroVert = SelEdge.Vertexes[0].Point
    if not(flipped) :
        cent = zeroVert + normal * BendR
        zeroVertNormal = normal.cross(Axis) * -1
        shp = Part.makeCylinder(BendR, 100, cent, Axis, 360)
    else:
         cent = zeroVert - normal * (BendR + thk)
         zeroVertNormal = normal.cross(Axis)
         shp = Part.makeCylinder(BendR+thk, 100, cent, Axis, 360)
    elt = shp.Face1
    #Part.show(elt)
    #Part.show(SelFace)
    #print([cent,zeroVertNormal])

#    Wirelist = []
    w = WrapFace(SelFace, neutralRadius, Axis, normal, zeroVert, cent, zeroVertNormal)
    eList = Part.__sortEdges__(w)
    myWire = Part.Wire(eList)
    #Part.show(myWire, "myWire")
    nextFace = Part.Face(elt.Surface, myWire)
    #f.check(True)
    nextFace.validate()
    #Part.show(nextFace, "nextFace")
    nextFace.check(True) # No output = good
    #Part.show(nextFace, "nextFace")
    if not(flipped) :
        bendsolid = nextFace.makeOffsetShape(thk, 0.0, fill = True)
    else:
        bendsolid = nextFace.makeOffsetShape(-thk, 0.0, fill = True)
    #Part.show(bendsolid, "bendsolid")
    return bendsolid


