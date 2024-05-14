import FreeCAD, Part, math, SheetMetalTools
from SheetMetalLogger import SMLogger

smEpsilon = SheetMetalTools.smEpsilon

def smthk(obj, foldface) :
  normal = foldface.normalAt(0,0)
  theVol = obj.Volume
  if theVol < 0.0001:
      SMLogger.error(
            FreeCAD.Qt.translate(
                "Logger",
                "Shape is not a real 3D-object or to small for a metal-sheet!"
            )
        )
  else:
      # Make a first estimate of the thickness
      estimated_thk = theVol/(obj.Area / 2.0)
  #p1 = foldface.CenterOfMass
  for v in foldface.Vertexes :
    p1 = v.Point
    p2 = p1 + estimated_thk * -1.5 * normal
    e1 = Part.makeLine(p1, p2)
    thkedge = obj.common(e1)
    thk = thkedge.Length
    if thk > smEpsilon :
      break
  return thk

def angleBetween(ve1, ve2):
  # Find angle between two vectors in degrees
  return math.degrees(ve1.getAngle(ve2))

def face_direction(face):
  yL = face.CenterOfMass
  uv = face.Surface.parameter(yL)
  nv = face.normalAt(uv[0], uv[1])
  direction = yL.sub(nv + yL)
  #print([direction, yL])
  return direction, yL

def transform_tool(tool, base_face, tool_face, point = FreeCAD.Vector(0, 0, 0), angle = 0.0):
  # Find normal of faces & center to align faces
  direction1,yL1 = face_direction(base_face)
  direction2,yL2 = face_direction(tool_face)

  # Find angle between faces, axis of rotation & center of axis
  rot_angle = angleBetween(direction1, direction2)
  rot_axis = direction1.cross(direction2)
  if rot_axis == FreeCAD.Vector (0.0, 0.0, 0.0):
      rot_axis = FreeCAD.Vector(0, 1, 0).cross(direction2)
  rot_center = yL2
  #print([rot_center, rot_axis, rot_angle])
  tool.rotate(rot_center, rot_axis, -rot_angle)
  tool.translate(-yL2 + yL1)
  #Part.show(tool, "tool")

  tool.rotate(yL1, direction1, angle)
  tool.translate(point)
  #Part.show(tool,"tool")
  return tool

def makeforming(tool, base, base_face, thk, tool_faces = None, point = FreeCAD.Vector(0, 0, 0), angle = 0.0) :
##  faces = [ face for face in tool.Shape.Faces for tool_face in tool_faces if not(face.isSame(tool_face)) ]
#  faces = [ face for face in tool.Shape.Faces if not face in tool_faces ]
#  tool_shell = Part.makeShell(faces)
#  offsetshell = tool_shell.makeOffsetShape(thk, 0.0, inter = False, self_inter = False, offsetMode = 0, join = 2, fill = True)
  offsetshell = tool.makeThickness(tool_faces, thk, 0.0001, False, False, 0, 0)
  cutSolid = tool.fuse(offsetshell)
  offsetshell_tran = transform_tool(offsetshell, base_face, tool_faces[0], point, angle)
  #Part.show(offsetshell1, "offsetshell1")
  cutSolid_trans = transform_tool(cutSolid, base_face, tool_faces[0], point, angle)
  base = base.cut(cutSolid_trans)
  base = base.fuse(offsetshell_tran)
  #base.removeSplitter()
  #Part.show(base, "base")
  return base

class SMFormingWall:
  def __init__(self, obj):
    '''"Add Forming Wall" '''

    _tip_ = FreeCAD.Qt.translate("App::Property","Offset from Center of Face")
    obj.addProperty("App::PropertyVectorDistance","offset","Parameters",_tip_)
    _tip_ = FreeCAD.Qt.translate("App::Property","Suppress Forming Feature")
    obj.addProperty("App::PropertyBool","SuppressFeature","Parameters",_tip_).SuppressFeature = False
    _tip_ = FreeCAD.Qt.translate("App::Property","Tool Position Angle")
    obj.addProperty("App::PropertyAngle","angle","Parameters",_tip_).angle = 0.0
    _tip_ = FreeCAD.Qt.translate("App::Property","Thickness of Sheetmetal")
    obj.addProperty("App::PropertyDistance","thickness","Parameters",_tip_)
    _tip_ = FreeCAD.Qt.translate("App::Property","Base Object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters",_tip_)
    _tip_ = FreeCAD.Qt.translate("App::Property","Forming Tool Object")
    obj.addProperty("App::PropertyLinkSub", "toolObject", "Parameters",_tip_)
    _tip_ = FreeCAD.Qt.translate("App::Property","Point Sketch on Sheetmetal")
    obj.addProperty("App::PropertyLink","Sketch","Parameters1",_tip_)
    obj.Proxy = self

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''

    base = fp.baseObject[0].Shape
    base_face = base.getElement(fp.baseObject[1][0])
    thk = smthk(base, base_face)
    fp.thickness = thk
    tool = fp.toolObject[0].Shape
    tool_faces = [tool.getElement(fp.toolObject[1][i]) for i in range(len(fp.toolObject[1]))]

    offsetlist = []
    if fp.Sketch:
      sketch = fp.Sketch.Shape
      for e in sketch.Edges:
          #print(type(e.Curve))
          if isinstance(e.Curve, (Part.Circle, Part.ArcOfCircle)):
            pt1 = base_face.CenterOfMass
            pt2 = e.Curve.Center
            offsetPoint = pt2 - pt1
            #print(offsetPoint)
            offsetlist.append(offsetPoint)
    else:
      offsetlist.append(fp.offset)

    if not(fp.SuppressFeature) :
      for i in range(len(offsetlist)):
        a = makeforming(tool, base, base_face, thk, tool_faces, offsetlist[i], fp.angle.Value)
        base = a
    else :
      a = base
    fp.Shape = a


# kept around for compatibility with files from ondsel-es 2024.2.0
SMBendWall = SMFormingWall
