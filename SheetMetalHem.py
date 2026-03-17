# ######################################################################
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
# ######################################################################

import math

from PySide import QtCore, QtGui

import FreeCAD
import Part

import SheetMetalTools
from SheetMetalCmd import smBend, smGetFace, smRestrict, sheet_thk

# List of properties to be saved as defaults.
smAddHemDefaultVars = ["HemType", ("width", "defaultWidth"),
                        ("radius", "defaultRadius"), "AutoMiter", ("kfactor", "defaultKFactor")]

translate = FreeCAD.Qt.translate


# Finds the root of f() in the given interval
def bisection_method(f, min_interval, max_interval, eps):
    a = min_interval
    b = max_interval

    fa = f(a)
    fb = f(b)

    if fa * fb > 0:
        raise ValueError("Teardrop hem has unexpected incorrect geometry")

    c = 0.5 * (a + b)
    prev_c = c + 2 * eps  # ensure the loop starts

    while abs(c - prev_c) >= eps:
        prev_c = c

        fc = f(c)

        if fa * fc < 0:
            b = c
            fb = fc
        else:
            a = c
            fa = fc

        c = 0.5 * (a + b)

    return c


def generateOpenHem(thickness, width, opening):
    if opening < 0:
        raise ValueError("Opening must be positive")
    
    if width > 0.5*opening + thickness:
        bendRadius = 0.5*opening
        legLength = width - bendRadius - thickness
        bendAngle = 180
        return (legLength, bendAngle, bendRadius)
    else:
        raise ValueError("Width must be greater than the bend width (equal to bend radius + thickness)")

def generateRolledHem(thickness, radius, rollAngle=None):
    maxRollAngle = 270.0 + math.degrees(math.asin(radius/(radius+thickness)))
    legLength = 0.0
    bendRadius = radius

    if rollAngle is None:
        bendAngle = maxRollAngle
        return (legLength, bendAngle, bendRadius)
    elif 0.0 < rollAngle <= maxRollAngle:
        bendAngle = rollAngle
        return (legLength, bendAngle, bendRadius)
    elif rollAngle < 0.0:
        raise ValueError("Roll angle must be strictly positive")
    elif rollAngle > maxRollAngle:
        raise ValueError("Roll angle must not exceed physical maximum ({}°)".format(maxRollAngle))

def generateTeardropHem(thickness, radius, width, opening=0.0):
    Lp = width
    R = radius
    t = thickness
    Lbend = R + t
    H = opening

    if H < 0:
        raise ValueError("Opening must be positive")

    if width >= 2*Lbend:
        legLength = 0.0
        bendRadius = R
        bendAngle = 0.0

        if width == 2*Lbend: # Degenerate teardrop hem
            bendAngle = 270.0
            if H < R:
                legLength = R - H
            else:
                raise ValueError("Opening must be smaller than bend radius")
        else: # Regular teadrop hem
            equation = lambda L: L - Lp + Lbend + t*math.sin(2*math.atan(R/L))
            precision = 1.0e-9
            L = bisection_method(equation, Lp-Lbend-t, Lp-Lbend, precision)

            if H == 0.0:
                theta = math.atan(R/L)
                bendAngle = 180.0 + 2*math.degrees(theta)
                legLength = L
            elif H == 2*bendRadius:
                legLength, _, bendRadius = generateOpenHem(t, Lp-Lbend, opening)
            else:
                theta = math.atan((L-math.sqrt(L**2-2.0*R*H+H**2))/H)
                bendAngle = 180.0 + math.degrees(2*theta)
                legLength = H*(math.cos(2*theta)-1)/math.sin(2*theta)+L
        
        return (legLength, bendAngle, bendRadius)
    else:
        raise ValueError("Width must be greater or equal than the bend width (equal to bend radius + thickness)")


class SMHem:
    def __init__(self, obj, selobj, sel_items, refAngOffset=None, checkRefFace=False):
        """Add Hem on an edge."""
        self.addVerifyProperties(obj, refAngOffset, checkRefFace)

        _tip_ = translate("App::Property", "Base Object")
        obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", _tip_
        ).baseObject = (selobj, sel_items)
        obj.Proxy = self
        SheetMetalTools.taskRestoreDefaults(obj, smAddHemDefaultVars)

    def addVerifyProperties(self, obj, refAngOffset=None, checkRefFace=False):
        SheetMetalTools.smAddEnumProperty(obj,
                "HemType",
                translate("App::Property", "Hem Type"),
                ["Flat", "Open", "Teardrop", "Rolled"])
        SheetMetalTools.smAddLengthProperty(obj,
                "radius",
                translate("App::Property", "Bend Radius"),
                1.0)
        SheetMetalTools.smAddLengthProperty(obj,
                "width",
                translate("App::Property", "Width of Hem"),
                10.0)
        SheetMetalTools.smAddAngleProperty(obj,
                "rollangle",
                translate("App::Property", "Roll angle"),
                225.0)
        SheetMetalTools.smAddBoolProperty(obj,
                "opened",
                translate("App::Property", "Opened hem"),
                False)
        SheetMetalTools.smAddLengthProperty(obj,
                "opening",
                translate("App::Property", "Opening of Hem"),
                1.0)
        SheetMetalTools.smAddDistanceProperty(obj,
                "gap1",
                translate("App::Property", "Gap from Left Side"),
                0.0)
        SheetMetalTools.smAddDistanceProperty(obj,
                "gap2",
                translate("App::Property", "Gap from Right Side"),
                0.0)
        SheetMetalTools.smAddBoolProperty(obj,
                "invert",
                translate("App::Property", "Invert Bend Direction"),
                False)
        SheetMetalTools.smAddDistanceProperty(obj,
                "extend1",
                translate("App::Property", "Extend from Left Side"),
                0.0)
        SheetMetalTools.smAddDistanceProperty(obj,
                "extend2",
                translate("App::Property", "Extend from Right Side"),
                0.0)
        SheetMetalTools.smAddEnumProperty(obj,
                "BendType",
                translate("App::Property", "Bend Type"),
                ["Material Outside", "Material Inside", "Thickness Outside", "Offset"])
        SheetMetalTools.smAddLengthProperty(obj,
                "reliefw",
                translate("App::Property", "Relief Width"),
                0.8,
                "ParametersRelief")
        SheetMetalTools.smAddLengthProperty(obj,
                "reliefd",
                translate("App::Property", "Relief Depth"),
                1.0,
                "ParametersRelief")
        SheetMetalTools.smAddBoolProperty(obj,
                "UseReliefFactor",
                translate("App::Property", "Use Relief Factor"),
                False,
                "ParametersRelief")
        SheetMetalTools.smAddEnumProperty(obj,
                "reliefType",
                translate("App::Property", "Relief Type"),
                ["Rectangle", "Round"],
                None,
                "ParametersRelief")
        SheetMetalTools.smAddFloatProperty(obj,
                "ReliefFactor",
                translate("App::Property", "Relief Factor"),
                0.7,
                "ParametersRelief")
        SheetMetalTools.smAddAngleProperty(obj,
                "miterangle1",
                translate("App::Property", "Bend Miter Angle from Left Side"),
                0.0,
                "ParametersMiterangle")
        SheetMetalTools.smAddAngleProperty(obj,
                "miterangle2",
                translate("App::Property", "Bend Miter Angle from Right Side"),
                0.0,
                "ParametersMiterangle")
        SheetMetalTools.smAddLengthProperty(obj,
                "minGap",
                translate("App::Property", "Auto Miter Minimum Gap"),
                0.2,
                "ParametersEx")
        SheetMetalTools.smAddLengthProperty(obj,
                "maxExtendDist",
                translate("App::Property", "Auto Miter maximum Extend Distance"),
                5.0,
                "ParametersEx")
        SheetMetalTools.smAddLengthProperty(obj,
                "minReliefGap",
                translate("App::Property", "Minimum Gap to Relief Cut"),
                1.0,
                "ParametersEx")
        SheetMetalTools.smAddBoolProperty(obj,
                "AutoMiter",
                translate("App::Property", "Enable Auto Miter"),
                True,
                "ParametersEx")
        SheetMetalTools.smAddBoolProperty(obj,
                "unfold",
                translate("App::Property", "Shows Unfold View of Current Bend"),
                False,
                "ParametersEx")
        SheetMetalTools.smAddProperty(obj,
                "App::PropertyFloatConstraint",
                "kfactor",
                translate("App::Property",
                          "Location of Neutral Line. Caution: Using ANSI standards, not DIN."),
                (0.5, 0.0, 1.0, 0.01),
                "ParametersEx")
        SheetMetalTools.smAddBoolProperty(obj,
                "sketchflip",
                translate("App::Property", "Flip Sketch Direction"),
                False,
                "ParametersEx2")
        SheetMetalTools.smAddBoolProperty(obj,
                "sketchinvert",
                translate("App::Property", "Invert Sketch Start"),
                False,
                "ParametersEx2")
        SheetMetalTools.smAddProperty(obj,
                "App::PropertyFloatList",
                "LegLengthList",
                translate("App::Property", "Leg Lenghts List"),
                None,
                "ParametersEx3")
        SheetMetalTools.smAddBoolProperty(obj,
                "Perforate",
                FreeCAD.Qt.translate("App::Property", "Enable Perforation"),
                False,
                "ParametersPerforation")
        SheetMetalTools.smAddAngleProperty(obj,
                "PerforationAngle",
                FreeCAD.Qt.translate("App::Property", "Perforation Angle"),
                0.0,
                "ParametersPerforation")
        SheetMetalTools.smAddLengthProperty(obj,
                "PerforationInitialLength",
                FreeCAD.Qt.translate("App::Property", "Initial Perforation Length"),
                5.0,
                "ParametersPerforation")
        SheetMetalTools.smAddLengthProperty(obj,
                "PerforationMaxLength",
                FreeCAD.Qt.translate("App::Property", "Perforation Max Length"),
                5.0,
                "ParametersPerforation")
        SheetMetalTools.smAddLengthProperty(obj,
                "NonperforationMaxLength",
                FreeCAD.Qt.translate("App::Property", "Non-Perforation Max Length"),
                5.0,
                "ParametersPerforation")
        SheetMetalTools.smAddProperty(obj,
                "App::PropertyLinkSub",
                "OffsetFaceReference",
                "Face reference for offset",
                refAngOffset,
                "ParametersEx")
        SheetMetalTools.smAddEnumProperty(obj,
                "OffsetType",
                "Offset Type",
                ["Material Outside", "Material Inside", "Thickness Outside", "Offset"],
                "Material Inside",
                "ParametersEx")
        SheetMetalTools.smAddDistanceProperty(obj,
                "OffsetTypeOffset",
                "Works when offset face reference is on. It offsets by "
                "a normal distance from the offsets reference face.",
                0.0,
                "ParametersEx")
        SheetMetalTools.smAddBoolProperty(obj,
                "SupplAngleRef",
                "Supplementary angle reference",
                False,
                "ParametersEx")

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver
        return None

    def execute(self, fp):
        """Print a short message when doing a recomputation.

        Note:
            This method is mandatory.

        """
        self.addVerifyProperties(fp)

        bendAList = [fp.width.Value]
        LegLengthList = [fp.width.Value]
        bendR = fp.radius.Value
        allowedAutoMiter = fp.AutoMiter

        # Restrict some params.
        fp.miterangle1.Value = smRestrict(fp.miterangle1.Value, -80.0, 80.0)
        fp.miterangle2.Value = smRestrict(fp.miterangle2.Value, -80.0, 80.0)

        # Pass selected object shape.
        Main_Object = fp.baseObject[0].Shape.copy()
        face = fp.baseObject[1]
        thk, thkDir = sheet_thk(Main_Object, face[0])

        fp.LegLengthList = LegLengthList
        # print(LegLengthList)

        # Extend value needed for first bend set only.
        extend1_list = [0.0 for n in LegLengthList]
        extend2_list = [0.0 for n in LegLengthList]
        extend1_list[0] = fp.extend1.Value
        extend2_list[0] = fp.extend2.Value
        # print(extend1_list, extend2_list)

        # Gap value needed for first bend set only.
        gap1_list = [0.0 for n in LegLengthList]
        gap2_list = [0.0 for n in LegLengthList]
        gap1_list[0] = fp.gap1.Value
        gap2_list[0] = fp.gap2.Value
        # print(gap1_list, gap2_list)

        # Compute geometrical parameters for selected hem type
        for i, _ in enumerate(LegLengthList):
            values = ()
            if fp.HemType == "Flat":
                values = generateOpenHem(thk, fp.width.Value, 0.0)
            elif fp.HemType == "Open":
                values = generateOpenHem(thk, fp.width.Value, fp.opening.Value)
            elif fp.HemType == "Teardrop":
                if fp.opened:
                    values = generateTeardropHem(thk, bendR,fp.width.Value)
                else:
                    values = generateTeardropHem(thk, bendR,fp.width.Value, fp.opening.Value)
            elif fp.HemType == "Rolled":
                allowedAutoMiter = False
                if fp.opened:
                    values = generateRolledHem(thk, bendR, fp.rollangle.Value)
                else:
                    values = generateRolledHem(thk, bendR)

            LegLengthList[i], bendAList[i], bendR = values

        for i, LegLength in enumerate(LegLengthList):
            s, f = smBend(
                thk,
                bendR=bendR,
                bendA=bendAList[i],
                miterA1=fp.miterangle1.Value,
                miterA2=fp.miterangle2.Value,
                BendType=fp.BendType,
                flipped=fp.invert,
                unfold=fp.unfold,
                extLen=LegLength,
                reliefType=fp.reliefType,
                gap1=gap1_list[i],
                gap2=gap2_list[i],
                reliefW=fp.reliefw.Value,
                reliefD=fp.reliefd.Value,
                minReliefgap=fp.minReliefGap.Value,
                extend1=extend1_list[i],
                extend2=extend2_list[i],
                kfactor=fp.kfactor,
                #offset=offsetValue,
                ReliefFactor=fp.ReliefFactor,
                UseReliefFactor=fp.UseReliefFactor,
                automiter=allowedAutoMiter,
                selFaceNames=face,
                MainObject=Main_Object,
                #sketch=fp.Sketch,
                mingap=fp.minGap.Value,
                maxExtendGap=fp.maxExtendDist.Value,
                #LengthSpec=fp.LengthSpec,
                Perforate=fp.Perforate,
                PerforationAngle=fp.PerforationAngle.Value,
                PerforationInitialLength=fp.PerforationInitialLength.Value,
                PerforationMaxLength=fp.PerforationMaxLength.Value,
                NonperforationMaxLength=fp.NonperforationMaxLength.Value)
            faces = smGetFace(f, s)
            face = faces
            Main_Object = s

        fp.Shape = s


if SheetMetalTools.isGuiLoaded():
    import os

    Gui = FreeCAD.Gui
    icons_path = SheetMetalTools.icons_path
    smEpsilon = SheetMetalTools.smEpsilon


    class SMViewProviderTree(SheetMetalTools.SMViewProvider):
        """Part WB style ViewProvider."""

        def getIcon(self):
            return os.path.join(icons_path, "SheetMetal_AddHem.svg")

        #def getTaskPanel(self, obj):
        #    return SMBendWallTaskPanel(obj)


    class SMViewProviderFlat(SMViewProviderTree):
        """Part Design WB style ViewProvider.

        Note:
            Backward compatibility only.

        """


    class AddHemCommandClass:
        """Add Hem command."""

        def GetResources(self):
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(icons_path, "SheetMetal_AddHem.svg"),
                    "MenuText": FreeCAD.Qt.translate("SheetMetal", "Make Hem"),
                    "Accel": "Z",
                    "ToolTip": FreeCAD.Qt.translate(
                        "SheetMetal",
                        "Creat hems on edges.\n"
                        "1. Select edges to create bends with walls.\n"
                        "2. Use Property editor to modify other parameters",
                        ),
                    }

        def Activated(self):
            doc = FreeCAD.ActiveDocument
            view = Gui.ActiveDocument.ActiveView
            activeBody = None

            # Get the sheet metal object.
            try:
                for obj in Gui.Selection.getSelectionEx():
                    if not "Plane" in obj.Object.TypeId:
                        for subElem in obj.SubElementNames:
                            if type(obj.Object.Shape.getElement(subElem)) == Part.Edge:
                                sel = obj
                                break
                selobj = sel.Object
            except:
                raise Exception("At least one edge must be selected to create a hem.")

            selSubNames = list(sel.SubElementNames)
            selSubObjs = sel.SubObjects

            # Remove faces for wall creation reference because only
            # edges should be used as reference to create hems.
            for subObjName in selSubNames:
                if type(selobj.Shape.getElement(subObjName)) == Part.Face:
                    selSubNames.remove(subObjName)
                    if len(selSubNames) < 1:
                        raise Exception("At least one edge must be selected to create a hem.")

            # Get only one selected face to use for reference to angle
            # and offset.
            faceCount = 0
            refAngOffset = None
            checkRefFace = False
            for obj in Gui.Selection.getSelectionEx():
                for subObj in obj.SubObjects:
                    if type(subObj) == Part.Face and not "Plane" in obj.Object.TypeId:
                        faceCount += 1
                        if faceCount == 1:
                            for subObjName in obj.SubElementNames:
                                if obj.Object.Shape.getElement(subObjName).isEqual(subObj):
                                    refAngOffset = [obj.Object, subObjName]
                                    checkRefFace = True
                        else:
                            print("If more than one face is selected, "
                                  "only the first is used for "
                                  "reference to angle and offset.")
                if "Plane" in obj.Object.TypeId and faceCount == 0:
                    if obj.Object.TypeId == "App::Plane":
                        refAngOffset = [obj.Object, ""]
                    else:
                        refAngOffset = [obj.Object, obj.SubElementNames[0]]
                    checkRefFace = True

            viewConf = SheetMetalTools.GetViewConfig(selobj)
            if hasattr(view, "getActiveObject"):
                activeBody = view.getActiveObject("pdbody")
            if not SheetMetalTools.smIsOperationLegal(activeBody, selobj):
                return
            doc.openTransaction("Hem")
            if activeBody is None or not SheetMetalTools.smIsPartDesign(selobj):
                newObj = doc.addObject("Part::FeaturePython", "Hem")
                SMHem(newObj, selobj, selSubNames, refAngOffset, checkRefFace)
                SMViewProviderTree(newObj.ViewObject)
            else:
                # FreeCAD.Console.PrintLog("found active body: " + activeBody.Name)
                newObj = doc.addObject("PartDesign::FeaturePython", "Hem")
                SMHem(newObj, selobj, selSubNames, refAngOffset, checkRefFace)
                SMViewProviderFlat(newObj.ViewObject)
                activeBody.addObject(newObj)
            SheetMetalTools.SetViewConfig(newObj, viewConf)
            Gui.Selection.clearSelection()
            if SheetMetalTools.is_autolink_enabled():
                root = SheetMetalTools.getOriginalBendObject(newObj)
                if root:
                    if hasattr(root, "Radius"):
                        newObj.setExpression("radius", root.Label + ".Radius")
                    elif hasattr(root, "radius"):
                        newObj.setExpression("radius", root.Label + ".radius")
            newObj.baseObject[0].ViewObject.Visibility = False
            doc.recompute()
            # 'checkRefFace' turn bendtype to 'Offset' when face
            # reference is before the command.
            #dialog = SMHemTaskPanel(newObj, checkRefFace)
            #SheetMetalTools.updateTaskTitleIcon(dialog)
            #Gui.Control.showDialog(dialog)
            return

        def IsActive(self):
            selobj = Gui.Selection.getSelectionEx()
            objSM = None
            # In this iteration, we will find which selected object is
            # the sheet metal part, 'cause the user can select a face
            # for reference (this object will not be the sheet metal
            # part).
            for obj in selobj:
                for subObj in obj.SubObjects:
                    if type(subObj) == Part.Edge:
                        objSM = obj

            # Test if any selected subObject in the sheet metal
            # isn't edge.
            geomTest = []
            for subObj in objSM.SubObjects:
                if type(subObj) == Part.Edge:
                    geomTest.append(True)
                else:
                    geomTest.append(False)

            if not False in geomTest and geomTest is not None:
                return True
            return None


    Gui.addCommand("SheetMetal_AddHem", AddHemCommandClass())
