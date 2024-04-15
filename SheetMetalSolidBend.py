import Part, SheetMetalTools

smEpsilon = SheetMetalTools.smEpsilon

# IMPORTANT: please remember to change the element map version in case of any
# changes in modeling logic
smElementMapVersion = 'sm1.'

def smGetClosestVert(vert, face):
  closestVert = None
  closestDist = 99999999
  for v in face.Vertexes:
    if vert.isSame(v):
      continue
    d = vert.distToShape(v)[0]
    if (d < closestDist):
      closestDist = d
      closestVert = v
  return closestVert


# we look for a matching inner edge to the selected outer one
# this function finds a single vertex of that edge
def smFindMatchingVert(shape, edge, vertid):
  facelist = shape.ancestorsOfType(edge, Part.Face)
  edgeVerts = edge.Vertexes
  v = edgeVerts[vertid]
  vfacelist = shape.ancestorsOfType(v, Part.Face)

  # find the face that is not in facelist
  for vface in vfacelist:
    if not vface.isSame(facelist[0]) and not vface.isSame(facelist[1]):
      break

  return smGetClosestVert(v, vface)
  
def smFindEdgeByVerts(shape, vert1, vert2):
  for edge in shape.Edges:
    if vert1.isSame(edge.Vertexes[0]) and vert2.isSame(edge.Vertexes[1]):
      break
    if vert1.isSame(edge.Vertexes[1]) and vert2.isSame(edge.Vertexes[0]):
      break
  else:
    edge = None
  return edge

def smSolidBend(radius = 1.0, selEdgeNames = '', MainObject = None):
  InnerEdgesToBend = []
  OuterEdgesToBend = []
  for selEdgeName in selEdgeNames:
    edge = MainObject.getElement(selEdgeName)


    facelist = MainObject.ancestorsOfType(edge, Part.Face)

    # find matching inner edge to selected outer one    
    v1 = smFindMatchingVert(MainObject, edge, 0)
    v2 = smFindMatchingVert(MainObject, edge, 1)
    matchingEdge = smFindEdgeByVerts(MainObject, v1, v2)
    if matchingEdge is not None:
      InnerEdgesToBend.append(matchingEdge)
      OuterEdgesToBend.append(edge)
  
  if len(InnerEdgesToBend) > 0:
    # find thickness of sheet by distance from v1 to one of the edges comming out of edge[0]
    # we assume all corners have same thickness
    for dedge in MainObject.ancestorsOfType(edge.Vertexes[0], Part.Edge):
      if not dedge.isSame(edge):
        break
    
    thickness = v1.distToShape(dedge)[0]

    resultSolid = MainObject.makeFillet(radius, InnerEdgesToBend)
    resultSolid = resultSolid.makeFillet(radius + thickness, OuterEdgesToBend)

  return resultSolid


class SMSolidBend:
  def __init__(self, obj):
    '''"Add Bend to Solid" '''

    _tip_ = FreeCAD.Qt.translate("App::Property","Bend Radius")
    obj.addProperty("App::PropertyLength","radius","Parameters", _tip_).radius = 1.0

    _tip_ = FreeCAD.Qt.translate("App::Property","Base object")
    obj.addProperty("App::PropertyLinkSub", "baseObject", "Parameters", _tip_)

  def getElementMapVersion(self, _fp, ver, _prop, restored):
      if not restored:
          return smElementMapVersion + ver

  def execute(self, fp):
    '''"Print a short message when doing a recomputation, this method is mandatory" '''
    # pass selected object shape

    Main_Object = fp.baseObject[0].Shape.copy()
    s = smSolidBend(radius = fp.radius.Value, selEdgeNames = fp.baseObject[1],
                MainObject = Main_Object)
    fp.Shape = s