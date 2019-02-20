from FreeCAD import Gui

import FreeCAD
import Part
import os
import math

from SheetMetalCmd import smIsOperationLegal, smIsPartDesign
from SheetMetalUnfolder import SMError
import BOPTools.SplitFeatures

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )


def smFold(bendR=1.0, bendA=90.0, flipped=False, unfold=False, kfactor=0.45, bendlinelist=None, invertbend=False,
                         MainObject=None):

        FoldShape = MainObject.Shape
        # restrict angle
        if (bendA < 0):
                bendA = -bendA
                flipped = not flipped

        if not unfold:
            if bendlinelist and bendA > 0.0 :
                cutFaceList = []
                for sketch in bendlinelist:
                    sketchsupport = sketch.Support
                    sketchface = sketchsupport[0][0].Shape.getElement(sketchsupport[0][1][0])
                    mat = sketch.getGlobalPlacement()
                    normal = mat.Rotation.multVec(FreeCAD.Vector(0,0,1))
                    theVol = FoldShape.Volume
                    if theVol < 0.0001:
                        SMError("Shape is not a real 3D-object or to small for a metal-sheet!")
                    else:
                        # Make a first estimate of the thickness
                        estimated_thk = theVol/(FoldShape.Area / 2.0)
                    p1 = sketchface.CenterOfMass
                    p2 = sketchface.CenterOfMass + estimated_thk * -1.3 * normal
                    e1 = Part.makeLine(p1, p2)
                    thkedge = FoldShape.common(e1)
                    thk = thkedge.Length
                    unfoldLength = math.pi * (bendR + kfactor * thk) * (bendA / 180)

                    for faceEdge in sketchface.Edges :
                        shape1 = sketch.Shape.section(faceEdge)
                        if shape1.Vertexes :
                            ExtrDir = faceEdge.valueAt(faceEdge.LastParameter) - faceEdge.valueAt(faceEdge.FirstParameter)
                            ExtrDir.normalize()
                            e1 = sketch.Shape.Edges[0]
                            e2 = faceEdge
                            d1 = e1.Vertexes[0].Point.sub(e1.Vertexes[1].Point)
                            d2 = e2.Vertexes[0].Point.sub(e2.Vertexes[1].Point)
                            angle1 = d2.getAngle(d1)
                            actualLength = unfoldLength/math.cos(math.pi/2-angle1)
                            break
                    for sketchedge in sketch.Shape.Edges:
                        if isinstance(sketchedge.Curve, Part.Line):
                            cutFace = sketchedge.extrude(normal * -thk)
                            cutFaceList.append(cutFace)
                            start = sketchedge.FirstParameter
                            end = sketchedge.LastParameter
                            revAxisV = sketchedge.valueAt(start) - sketchedge.valueAt(end)
                            revAxisV.normalize()
                #print(revAxisV)

                slice = BOPTools.SplitAPI.slice(FoldShape, cutFaceList, "Standard", 0.0)
                Extcut = cutFaceList[0].extrude(ExtrDir * actualLength)
                SolidPart = slice.Solids[1].common(Extcut)
                if SolidPart.Volume :
                    soild1 = slice.Solids[1]
                    solid2 = slice.Solids[0]
                else :
                    soild1 = slice.Solids[0]
                    solid2 = slice.Solids[1]

                if not(invertbend):
                    wallSolid = soild1
                    resultSolid = solid2
                else :
                    wallSolid = solid2
                    resultSolid = soild1
                    bendA = -bendA
                    ExtrDir = -ExtrDir

                # make sure the direction verctor is correct in respect to the normal
                #print((normal.cross(revAxisV) - ExtrDir).Length)
                if (normal.cross(revAxisV) - ExtrDir).Length < 1.0 :
                    revAxisV = revAxisV * -1

                if (len(cutFaceList)) > 1:
                    cutFace = cutFaceList[0].multiFuse(cutFaceList[1:])

                if not(flipped):
                    revAxisP = sketchedge.valueAt(end) + normal * bendR
                    revAxisV = revAxisV * -1
                else :
                    revAxisP = sketchedge.valueAt(end) + normal * -(bendR+thk)
                print(revAxisP)

                cutFace = cutFace.common(wallSolid)
                cutLineList = []
                for sketchEdge in sketch.Shape.Edges:
                    if isinstance(sketchEdge.Curve, Part.Line):
                        cutLine = sketchEdge.extrude(ExtrDir * actualLength)
                        cutLineList.append(cutLine)
                if (len(cutLineList)) > 1 :
                    cutLine = cutLineList[0].multiFuse(cutLineList[1:])
                else :
                    cutLine = cutLineList[0]
                BFace = cutLine.common(wallSolid)
                for cutFaces in cutFaceList :
                    cutExt = cutFaces.extrude(ExtrDir.normalize() * actualLength)
                    wallSolid = wallSolid.cut(cutExt)
                wallSolid.translate(ExtrDir * -actualLength)
                wallSolid.rotate(revAxisP, revAxisV, bendA)
                resultSolid = resultSolid.fuse(wallSolid)
                bendSolid = cutFace.revolve(revAxisP, revAxisV, bendA)
                #bendSolid = makeBend(BFace, bendR, bendA)
                #Part.show(bendSolid)
                resultSolid = resultSolid.fuse(bendSolid)
        else :
            if bendA > 0.0 :
                # create bend
                # FIXME undefined revFace!
                bendSolid = revFace.extrude(revFace.normalAt(0,0) * unfoldLength)
                #Part.show(bendSolid)
                resultSolid = resultSolid.fuse(bendSolid)

        Gui.ActiveDocument.getObject(MainObject.Name).Visibility = False
        return resultSolid


class SMFoldWall:
    def __init__(self, obj):
        """Add Wall with radius bend"""
        selobj = Gui.Selection.getSelection()

        obj.addProperty("App::PropertyLength","radius","Parameters","Bend Radius").radius = 1.0
        obj.addProperty("App::PropertyBool","invert","Parameters","Invert bend direction").invert = False
        obj.addProperty("App::PropertyAngle","angle","Parameters","Bend angle").angle = 90.0
        obj.addProperty("App::PropertyBool","unfold","Parameters","Invert bend direction").unfold = False
        obj.addProperty("App::PropertyFloatConstraint","kfactor","Parameters","Gap from left side").kfactor = (0.45,0.0,1.0,0.01)
        obj.addProperty("App::PropertyLink", "baseObject", "Parameters", "Base object").baseObject = selobj[0]
        obj.addProperty("App::PropertyLinkList","BendLineList","Parameters","Bend Reference Line List").BendLineList = selobj[1:]
        obj.addProperty("App::PropertyBool","invertbend","Parameters","Invert bend direction").invertbend = False
        obj.Proxy = self

    def execute(self, fp):
        """Print a short message when doing a recomputation, this method is mandatory"""

        s = smFold(bendR=fp.radius.Value,
                   bendA=fp.angle.Value,
                   flipped=fp.invert,
                   unfold=fp.unfold,
                   kfactor=fp.kfactor,
                   bendlinelist=fp.BendLineList,
                   invertbend=fp.invertbend,
                   MainObject=fp.baseObject,
                 )
        fp.Shape = s


class SMFoldViewProviderTree:
    """A View provider that nests children objects under the created one"""

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
        return None

    def __setstate__(self,state):
        if state is not None:
            import FreeCAD
            doc = FreeCAD.ActiveDocument #crap
            self.Object = doc.getObject(state['ObjectName'])

    def claimChildren(self):
        objs = []
        if hasattr(self.Object,"baseObject"):
            objs.append(self.Object.baseObject)
            objs.append(self.Object.BendLineList)
        return objs

    def getIcon(self):
        return os.path.join( iconPath , 'SMFoldWall.svg')


class AddFoldWallCommandClass():
    """Add Wall command"""

    def GetResources(self):
        return {'Pixmap'    : os.path.join( iconPath , 'SMFoldWall.svg') , # the name of a svg file available in the resources
                        'MenuText': "Make Wall" ,
                        'ToolTip' : "Extends a wall from a side face of metal sheet"}

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        view = Gui.ActiveDocument.ActiveView
        activeBody = None
        selobj = Gui.Selection.getSelection()
        if hasattr(view,'getActiveObject'):
            activeBody = view.getActiveObject('pdbody')
        if not smIsOperationLegal(activeBody, selobj):
            return

        doc.openTransaction("Bend")
        if activeBody == None or not smIsPartDesign(selobj):
            a = doc.addObject("Part::FeaturePython","Fold")
            SMFoldWall(a)
            SMFoldViewProviderTree(a.ViewObject)
        else:
            #FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
            a = doc.addObject("PartDesign::FeaturePython","Fold")
            SMFoldWall(a)
            SMFoldViewProviderTree(a.ViewObject)
            activeBody.addObject(a)
        doc.recompute()
        doc.commitTransaction()
        return

    def IsActive(self):
        if len(Gui.Selection.getSelection()) > 1 :
            selobjs = Gui.Selection.getSelection()
            for obj in selobjs:
                if str(type(obj)) == "<type 'Sketcher.SketchObject'>":
                    return True

Gui.addCommand('SMFoldWall',AddFoldWallCommandClass())
