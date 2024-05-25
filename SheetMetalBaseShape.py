import Part, FreeCAD, SheetMetalTools
from SheetMetalBendWall import smBend

base_shape_types = ["Flat", "L-Shape", "U-Shape", "Tub", "Hat", "Box"]
origin_location_types = ["-X,-Y", "-X,0", "-X,+Y", "0,-Y", "0,0", "0,+Y", "+X,-Y", "+X,0", "+X,+Y"]

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

##########################################################################################################
# Object class and creation function
##########################################################################################################

def GetOriginShift(dimension, type, bendCompensation):
    type = type[0]
    if type == '+':
        return -dimension - bendCompensation
    if type == '0':
        return -dimension / 2.0
    return bendCompensation

def smCreateBaseShape(type, thickness, radius, width, length, height, flangeWidth, fillGaps, origin):
    bendCompensation = thickness + radius
    height -= bendCompensation
    compx = 0
    compy = 0
    if type == "U-Shape":
        numfolds = 2
        width -= 2.0 * bendCompensation
        compy = bendCompensation
    elif type in ["Tub", "Hat", "Box"]:
        numfolds = 4
        width -= 2.0 * bendCompensation
        length -= 2.0 * bendCompensation
        compx = compy = bendCompensation
    elif type == "L-Shape":
        numfolds = 1
        width -= bendCompensation
    else:
        numfolds = 0
    if type in ["Hat", "Box"]:
        height -= bendCompensation
        flangeWidth -= radius
    if width < thickness: width = thickness
    if height < thickness: height = thickness
    if length < thickness: length = thickness
    if flangeWidth < thickness: flangeWidth = thickness
    originX, originY = origin.split(',')
    offsx = GetOriginShift(length, originX, compx)
    offsy = GetOriginShift(width, originY, compy)
    if type == "L-Shape" and originY == "+Y":
        offsy -= bendCompensation
    box = Part.makeBox(length, width, thickness, FreeCAD.Vector(offsx, offsy, 0))
    #box.translate(FreeCAD.Vector(offsx, offsy, 0))
    if numfolds == 0:
        return box
    faces = []
    for i in range(len(box.Faces)):
        v = box.Faces[i].normalAt(0,0)
        if (v.y > 0.5 or
            (v.y < -0.5 and numfolds > 1) or
            (v.x > 0.5 and numfolds > 2) or
            (v.x < -0.5 and numfolds > 3)):
            faces.append("Face" + str(i+1))

    shape, f = smBend(thickness, selFaceNames = faces, extLen = height, bendR = radius,
                      MainObject = box, automiter = fillGaps)
    if type in ["Hat", "Box"]:
        faces = []
        invertBend = False
        if type == "Hat": invertBend = True
        for i in range(len(shape.Faces)):
            v = shape.Faces[i].normalAt(0,0)
            z = shape.Faces[i].CenterOfGravity.z
            if v.z > 0.9999 and z > bendCompensation:
                faces.append("Face" + str(i+1))
        shape, f = smBend(thickness, selFaceNames = faces, extLen = flangeWidth,
                          bendR = radius, MainObject = shape, flipped = invertBend,
                          automiter = fillGaps)
    #SMLogger.message(str(faces))
    return shape


class SMBaseShape:
    def __init__(self, obj):
        '''"Add a base sheetmetal shape" '''
        self._addVerifyProperties(obj)
        obj.Proxy = self

    def _addVerifyProperties(self, obj):
        SheetMetalTools.smAddLengthProperty(
            obj,
            "thickness",
            FreeCAD.Qt.translate("SMBaseShape", "Thickness of sheetmetal", "Property"),
            1.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "radius",
            FreeCAD.Qt.translate("SMBaseShape", "Bend Radius", "Property"),
            1.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "width",
            FreeCAD.Qt.translate("SMBaseShape", "Shape width", "Property"),
            20.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "length",
            FreeCAD.Qt.translate("SMBaseShape", "Shape length", "Property"),
            30.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "height",
            FreeCAD.Qt.translate("SMBaseShape", "Shape height", "Property"),
            10.0,
        )
        SheetMetalTools.smAddLengthProperty(
            obj,
            "flangeWidth",
            FreeCAD.Qt.translate("SMBaseShape", "Width of top flange", "Property"),
            5.0,
        )
        SheetMetalTools.smAddEnumProperty(
            obj,
            "shapeType",
            FreeCAD.Qt.translate("SMBaseShape", "Base shape type", "Property"),
            base_shape_types,
            defval = "L-Shape"
        )
        SheetMetalTools.smAddEnumProperty(
            obj,
            "originLoc",
            FreeCAD.Qt.translate("SMBaseShape", "Location of part origin", "Property"),
            origin_location_types,
            defval = "0,0"
        )
        SheetMetalTools.smAddBoolProperty(
            obj,
            "fillGaps",
            FreeCAD.Qt.translate(
                "SMBaseShape", "Extend sides and flange to close all gaps", "Property"
            ),
            True,
        )

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver

    def onChanged(self, fp, prop):
        if prop == "shapeType":
            flat = fp.shapeType == "Flat"
            hat_box = fp.shapeType in ["Hat", "Box"]
            fp.setEditorMode("radius", flat)
            fp.setEditorMode("height", flat)
            fp.setEditorMode("flangeWidth", not hat_box)

    def execute(self, fp):
        self._addVerifyProperties(fp)
        s = smCreateBaseShape(type = fp.shapeType, thickness = fp.thickness.Value,
                              radius = fp.radius.Value, width = fp.width.Value,
                              length = fp.length.Value, height = fp.height.Value,
                              flangeWidth = fp.flangeWidth.Value, fillGaps = fp.fillGaps,
                              origin = fp.originLoc)

        fp.Shape = s

    def getBaseShapeTypes():
        return base_shape_types
    
    def getOriginLocationTypes():
        return origin_location_types