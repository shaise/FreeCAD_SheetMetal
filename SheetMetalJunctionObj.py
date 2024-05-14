# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalJunctionObj.py
#
#  Copyright 2024 Shai Seger <shaise at gmail dot com>
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

import FreeCAD, Part

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

def smJunction(gap = 2.0, selEdgeNames = '', MainObject = None):
  import BOPTools.SplitFeatures, BOPTools.JoinFeatures

  resultSolid = MainObject
  for selEdgeName in selEdgeNames:
    edge = MainObject.getElement(selEdgeName)

    facelist = MainObject.ancestorsOfType(edge, Part.Face)
    #for face in facelist :
    #  Part.show(face,'face')

    joinface = facelist[0].fuse(facelist[1])
    #Part.show(joinface,'joinface')
    filletedface = joinface.makeFillet(gap, joinface.Edges)
    #Part.show(filletedface,'filletedface')

    cutface1= facelist[0].cut(filletedface)
    #Part.show(cutface1,'cutface1')
    offsetsolid1 = cutface1.makeOffsetShape(-gap, 0.0, fill = True)
    #Part.show(offsetsolid1,'offsetsolid1')

    cutface2 = facelist[1].cut(filletedface)
    #Part.show(cutface2,'cutface2')
    offsetsolid2 = cutface2.makeOffsetShape(-gap, 0.0, fill = True)
    #Part.show(offsetsolid2,'offsetsolid2')
    cutsolid = offsetsolid1.fuse(offsetsolid2)
    #Part.show(cutsolid,'cutsolid')
    resultSolid = resultSolid.cut(cutsolid)
    #Part.show(resultsolid,'resultsolid')

  return resultSolid

class SMJunction:
  def __init__(self, obj):
    '''"Add Gap to Solid" '''

    _tip_ = FreeCAD.Qt.translate("App::Property","Junction Gap")
    obj.addProperty("App::PropertyLength","gap","Parameters",_tip_).gap = 2.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Base Object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",_tip_)
    obj.Proxy = self

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    # pass selected object shape
    Main_Object = fp.baseObject[0].Shape.copy()
    s = smJunction(gap = fp.gap.Value, selEdgeNames = fp.baseObject[1], MainObject = Main_Object)
    fp.Shape = s