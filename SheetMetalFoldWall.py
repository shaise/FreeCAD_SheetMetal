import FreeCAD, Part, math, SheetMetalTools
import SheetMetalBendSolid
from SheetMetalLogger import SMLogger

smEpsilon = SheetMetalTools.smEpsilon

def smthk(obj, foldface):
    normal = foldface.normalAt(0, 0)
    theVol = obj.Volume
    if theVol < 0.0001:
        SMLogger.error(
            FreeCAD.Qt.translate(
                "Logger", "Shape is not a real 3D-object or to small for a metal-sheet!"
            )
        )
    else:
        # Make a first estimate of the thickness
        estimated_thk = theVol / (foldface.Area)
    #  p1 = foldface.CenterOfMass
    p1 = foldface.Vertexes[0].Point
    p2 = p1 + estimated_thk * -1.5 * normal
    e1 = Part.makeLine(p1, p2)
    thkedge = obj.common(e1)
    thk = thkedge.Length
    return thk


def smCutFace(Face, obj):
    # find face Modified During loop
    for face in obj.Faces:
        face_common = face.common(Face)
        if face_common.Faces:
            break
    return face


def smFold(
    bendR=0.8,
    bendA=90.0,
    kfactor=1,
    invertbend=False,
    flipped=False,
    unfold=False,
    position="forward",
    bendlinesketch=None,
    selFaceNames="",
    MainObject=None,
):

    import BOPTools.SplitFeatures, BOPTools.JoinFeatures

    FoldShape = MainObject.Shape

    # restrict angle
    if bendA < 0:
        bendA = -bendA
        flipped = not flipped
    if not (unfold):
        if bendlinesketch and bendA > 0.0:
            foldface = FoldShape.getElement(selFaceNames[0])
            tool = bendlinesketch.Shape.copy()
            normal = foldface.normalAt(0, 0)
            thk = smthk(FoldShape, foldface)
            #print(thk)

            # if not(flipped) :
            # offset =  thk * kfactor
            # else :
            # offset = thk * (1 - kfactor )
            # adaptive   адаптивний
            if position == "intersection of planes" :
                kfactor = (( bendR ) * math.tan(math.radians(bendA / 2.0)) * 180 / (bendA / 2.0) / math.pi - bendR ) / thk
                print (kfactor)

            unfoldLength = (bendR + kfactor * thk) * bendA * math.pi / 180.0
            neutralRadius = bendR + kfactor * thk
            # neutralLength =  ( bendR + kfactor * thk ) * math.tan(math.radians(bendA / 2.0)) * 2.0
            # offsetdistance = neutralLength - unfoldLength
            # scalefactor = neutralLength / unfoldLength
            # print([neutralRadius, neutralLength, unfoldLength, offsetdistance, scalefactor])

            # To get facedir
            toolFaces = tool.extrude(normal * -thk)
            # Part.show(toolFaces, "toolFaces")
            cutSolid = BOPTools.SplitAPI.slice(
                FoldShape, toolFaces.Faces, "Standard", 0.0
            )
            # Part.show(cutSolid,"cutSolid_check")

            if not (invertbend):
                solid0 = cutSolid.childShapes()[0]
            else:
                solid0 = cutSolid.childShapes()[1]
            cutFaceDir = smCutFace(toolFaces.Faces[0], solid0)
            # Part.show(cutFaceDir,"cutFaceDir")
            facenormal = cutFaceDir.Faces[0].normalAt(0, 0)
            # print(facenormal)

            if position == "middle":
                tool.translate(facenormal * -unfoldLength / 2.0)
                toolFaces = tool.extrude(normal * -thk)
            elif position == "backward":
                tool.translate(facenormal * -unfoldLength)
                toolFaces = tool.extrude(normal * -thk)
            # To get split solid
            solidlist = []
            toolExtr = toolFaces.extrude(facenormal * unfoldLength)
            # Part.show(toolExtr,"toolExtr")
            CutSolids = FoldShape.cut(toolExtr)
            # Part.show(Solids,"Solids")
            solid2list, solid1list = [], []
            for solid in CutSolids.Solids:
                checksolid = toolFaces.common(solid)
                if checksolid.Faces:
                    solid1list.append(solid)
                else:
                    solid2list.append(solid)
            if len(solid1list) > 1:
                solid0 = solid1list[0].multiFuse(solid1list[1:])
            else:
                solid0 = solid1list[0]
            # Part.show(solid0,"solid0")

            if len(solid2list) > 1:
                solid1 = solid2list[0].multiFuse(solid2list[1:])
            else:
                solid1 = solid2list[0]
            # Part.show(solid0,"solid0")
            # Part.show(solid1,"solid1")

            bendEdges = FoldShape.common(tool)
            if tool.Length <= (bendEdges.Edges[0].Length * 1.002):
                FreeCAD.Console.PrintError(
                    "The bend line sketch "
                    + bendlinesketch.Label
                    + " is not overhanging"
                    " the face sufficiently at one end or both, extend to get reliable results for the unfold operation\n"
                )
            # Part.show(bendEdges,"bendEdges")
            bendEdge = bendEdges.Edges[0]


###########################################################################################################################

            if not (flipped):

                    bendR_flip = bendR
            else:
                    bendR_flip = bendR + thk

            if position == "intersection of planes" :
                bendEdge.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))

##############################################################################################################################
            if not (flipped):
                revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) + normal * bendR
            else:
                revAxisP = bendEdge.valueAt(bendEdge.FirstParameter) - normal * (
                    thk + bendR
                )
            revAxisV = bendEdge.valueAt(bendEdge.LastParameter) - bendEdge.valueAt(
                bendEdge.FirstParameter
            )
            revAxisV.normalize()

            # To check sktech line direction
            if (normal.cross(revAxisV).normalize() - facenormal).Length > smEpsilon:
                revAxisV = revAxisV * -1
                # print(revAxisV)
            if flipped:
                revAxisV = revAxisV * -1
                # print(revAxisV)
            # To get bend surface
            #      revLine = Part.LineSegment(tool.Vertexes[0].Point, tool.Vertexes[-1].Point ).toShape()
            #      bendSurf = revLine.revolve(revAxisP, revAxisV, bendA)
            # Part.show(bendSurf,"bendSurf")

            #      bendSurfTest = bendSurf.makeOffsetShape(bendR/2.0, 0.0, fill = False)
            #      #Part.show(bendSurfTest,"bendSurfTest")
            #      offset =  1
            #      if bendSurfTest.Area < bendSurf.Area and not(flipped) :
            #        offset =  -1
            #      elif bendSurfTest.Area > bendSurf.Area and flipped :
            #        offset =  -1
            #      #print(offset)

            # To get bend solid
            flatsolid = FoldShape.cut(solid0)
            flatsolid = flatsolid.cut(solid1)
            # Part.show(flatsolid,"flatsolid")
            flatfaces = foldface.common(flatsolid)
############################################################################################################################################
            if position == "intersection of planes" :
                flatfaces.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
            #Part.show(flatfaces,"flatface")
                solid0.translate(facenormal * ((unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
                solid1.translate(facenormal * ((-unfoldLength/2) -( bendR_flip ) * math.tan(math.radians(bendA / 2.0))))
#############################################################################################################################################
            else :
                solid1.translate(facenormal * (-unfoldLength))
            # Part.show(flatfaces,"flatface")
            #solid1.translate(facenormal * (-unfoldLength))
            # Part.show(solid1,"solid1")
            solid1.rotate(revAxisP, revAxisV, bendA)
            # Part.show(solid1,"rotatedsolid1")
            #      bendSolidlist =[]
            for flatface in flatfaces.Faces:
                bendsolid = SheetMetalBendSolid.bend_solid(
                    flatface, bendEdge, bendR, thk, neutralRadius, revAxisV, flipped
                )
                # Part.show(bendsolid,"bendsolid")
                solidlist.append(bendsolid)
            solidlist.append(solid0)
            solidlist.append(solid1)
            # resultsolid = Part.makeCompound(solidlist)
            # resultsolid = BOPTools.JoinAPI.connect(solidlist)
            resultsolid = solidlist[0].multiFuse(solidlist[1:])
    else:
        if bendlinesketch and bendA > 0.0:
            resultsolid = FoldShape
    return resultsolid


class SMFoldWall:
    def __init__(self, obj):
        '''"Fold / Bend a Sheetmetal with given Bend Radius"'''

        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Radius")
        obj.addProperty(
            "App::PropertyLength", "radius", "Parameters", _tip_
        ).radius = 1.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Angle")
        obj.addProperty("App::PropertyAngle", "angle", "Parameters", _tip_).angle = 90.0
        _tip_ = FreeCAD.Qt.translate("App::Property", "Base Object")
        obj.addProperty(
            "App::PropertyLinkSub", "baseObject", "Parameters", _tip_
        )
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Reference Line List")
        obj.addProperty(
            "App::PropertyLink", "BendLine", "Parameters", _tip_
        )
        _tip_ = FreeCAD.Qt.translate("App::Property", "Invert Solid Bend Direction")
        obj.addProperty(
            "App::PropertyBool", "invertbend", "Parameters", _tip_
        ).invertbend = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Neutral Axis Position")
        obj.addProperty(
            "App::PropertyFloatConstraint", "kfactor", "Parameters", _tip_
        ).kfactor = (0.5, 0.0, 1.0, 0.01)
        _tip_ = FreeCAD.Qt.translate("App::Property", "Invert Bend Direction")
        obj.addProperty(
            "App::PropertyBool", "invert", "Parameters", _tip_
        ).invert = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Unfold Bend")
        obj.addProperty(
            "App::PropertyBool", "unfold", "Parameters", _tip_
        ).unfold = False
        _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Line Position")
        obj.addProperty(
            "App::PropertyEnumeration", "Position", "Parameters", _tip_
        ).Position = ["intersection of planes", "middle", "backward", "forward"]
        obj.Proxy = self

    def execute(self, fp):
        '''"Print a short message when doing a recomputation, this method is mandatory"'''

        if not hasattr(fp, "Position"):
            _tip_ = FreeCAD.Qt.translate("App::Property", "Bend Line Position")
            fp.addProperty(
                "App::PropertyEnumeration", "Position", "Parameters", _tip_
            ).Position = ["intersection of planes", "middle", "backward", "forward"]
        s = smFold(
            bendR=fp.radius.Value,
            bendA=fp.angle.Value,
            flipped=fp.invert,
            unfold=fp.unfold,
            kfactor=fp.kfactor,
            bendlinesketch=fp.BendLine,
            position=fp.Position,
            invertbend=fp.invertbend,
            selFaceNames=fp.baseObject[1],
            MainObject=fp.baseObject[0],
        )
        fp.Shape = s

