# -*- coding: utf-8 -*-
###################################################################################
#
#  SMBaseBend.py
#
#  Copyright 2015 Shai Seger <shaise at gmail dot com>
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

import FreeCAD, Part

translate = FreeCAD.Qt.translate

def modifiedWire(WireList, radius, thk, length, normal, Side, sign):
    # If sketch is one type, make a face by extruding & offset it to correct position
    wire_extr = WireList.extrude(normal * sign * length)
    # Part.show(wire_extr,"wire_extr")

    if Side == "Inside":
        wire_extr = wire_extr.makeOffsetShape(thk / 2.0 * sign, 0.0, fill=False, join=2)
    elif Side == "Outside":
        wire_extr = wire_extr.makeOffsetShape(
            -thk / 2.0 * sign, 0.0, fill=False, join=2
        )
    # Part.show(wire_extr,"wire_extr")
    try:
        filleted_extr = wire_extr.makeFillet((radius + thk / 2.0), wire_extr.Edges)
    except:
        filleted_extr = wire_extr
    # Part.show(filleted_extr,"filleted_extr")
    filleted_extr = filleted_extr.makeOffsetShape(
        thk / 2.0 * sign, 0.0, fill=False, join=2
    )
    # Part.show(filleted_extr,"filleted_extr")
    return filleted_extr

def smBase(
    thk=2.0,
    length=10.0,
    radius=1.0,
    Side="Inside",
    midplane=False,
    reverse=False,
    MainObject=None,
):
    # To Get sketch normal
    WireList = MainObject.Shape.Wires[0]
    mat = MainObject.getGlobalPlacement().Rotation
    normal = (mat.multVec(FreeCAD.Vector(0, 0, 1))).normalize()
    # print([mat, normal])
    if WireList.isClosed():
        # If Closed sketch is there, make a face & extrude it
        sketch_face = Part.makeFace(MainObject.Shape.Wires, "Part::FaceMakerBullseye")
        thk = -1.0 * thk if reverse else thk
        wallSolid = sketch_face.extrude(sketch_face.normalAt(0, 0) * thk)
        if midplane:
            wallSolid = Part.Solid(
                wallSolid.translated(sketch_face.normalAt(0, 0) * thk * -0.5)
            )
    else:
        filleted_extr = modifiedWire(WireList, radius, thk, length, normal, Side, 1.0)
        # Part.show(filleted_extr,"filleted_extr")
        dist = WireList.Vertexes[0].Point.distanceToPlane(
            FreeCAD.Vector(0, 0, 0), normal
        )
        # print(dist)
        slice_wire = filleted_extr.slice(normal, dist)
        # print(slice_wire)
        # Part.show(slice_wire[0],"slice_wire")
        traj = slice_wire[0]
        # Part.show(traj,"traj")
        if midplane:
            traj.translate(normal * -length / 2.0)
        elif reverse:
            traj.translate(normal * -length)
        traj_extr = traj.extrude(normal * length)
        # Part.show(traj_extr,"traj_extr")
        solidlist = []
        for face in traj_extr.Faces:
            solid = face.makeOffsetShape(thk, 0.0, fill=True)
            solidlist.append(solid)
        if len(solidlist) > 1:
            wallSolid = solidlist[0].multiFuse(solidlist[1:])
        else:
            wallSolid = solidlist[0]
        # Part.show(wallSolid,"wallSolid")
    # Part.show(wallSolid,"wallSolid")
    return wallSolid

class SMBaseBend:
    def __init__(self, obj):
        '''"Add wall or Wall with radius bend"'''
        _tip_ = translate("App::Property", "Bend Radius")
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = 1.0
        _tip_ = translate("App::Property", "Thickness of sheetmetal")
        obj.addProperty(
            "App::PropertyLength", "thickness", "Parameters", _tip_
        ).thickness = 1.0
        _tip_ = translate("App::Property", "Relief Type")
        obj.addProperty(
            "App::PropertyEnumeration", "BendSide", "Parameters", _tip_
        ).BendSide = ["Outside", "Inside", "Middle"]
        _tip_ = translate("App::Property", "Length of wall")
        obj.addProperty(
            "App::PropertyLength", "length", "Parameters", _tip_
        ).length = 100.0
        _tip_ = translate("App::Property", "Wall Sketch object")
        obj.addProperty(
            "App::PropertyLink", "BendSketch", "Parameters", _tip_
        ).BendSketch = None
        _tip_ = translate("App::Property", "Extrude Symmetric to Plane")
        obj.addProperty(
            "App::PropertyBool", "MidPlane", "Parameters", _tip_
        ).MidPlane = False
        _tip_ = translate("App::Property", "Reverse Extrusion Direction")
        obj.addProperty(
            "App::PropertyBool", "Reverse", "Parameters", _tip_
        ).Reverse = False
        obj.Proxy = self

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory"'''
        if not hasattr(fp, "MidPlane"):
            _tip_ = translate("App::Property", "Extrude Symmetric to Plane")
            fp.addProperty(
                "App::PropertyBool", "MidPlane", "Parameters", _tip_
            ).MidPlane = False
            _tip_ = translate("App::Property", "Reverse Extrusion Direction")
            fp.addProperty(
                "App::PropertyBool", "Reverse", "Parameters", _tip_
            ).Reverse = False
        s = smBase(
            thk=fp.thickness.Value,
            length=fp.length.Value,
            radius=fp.radius.Value,
            Side=fp.BendSide,
            midplane=fp.MidPlane,
            reverse=fp.Reverse,
            MainObject=fp.BendSketch,
        )

        fp.Shape = s

