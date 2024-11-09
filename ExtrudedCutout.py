import FreeCAD
import FreeCAD as App
import FreeCADGui as Gui
import Part
import os  # Make sure 'os' is imported for the icon path
import SheetMetalTools

class ExtrudedCutout:
    def __init__(self, obj, sketch, selected_object, selected_face):
        '''Initialize the parametric Sheet Metal Cut object and add properties'''
        obj.addProperty("App::PropertyLink", "Sketch", "ExtrudedCutout", "The sketch for the cut").Sketch = sketch
        obj.addProperty("App::PropertyLink", "SelectedObject", "ExtrudedCutout", "The object to cut").SelectedObject = selected_object
        obj.addProperty("App::PropertyLinkSub", "SelectedFace", "ExtrudedCutout", "The selected face").SelectedFace = selected_face
        obj.addProperty("App::PropertyLength", "ExtrusionLength1", "ExtrudedCutout", "Length of the extrusion direction 1").ExtrusionLength1 = 500.0
        obj.setEditorMode("ExtrusionLength1",2) # Hide by default
        obj.addProperty("App::PropertyLength", "ExtrusionLength2", "ExtrudedCutout", "Length of the extrusion direction 2").ExtrusionLength2 = 500.0
        obj.setEditorMode("ExtrusionLength2",2) # Hide by default
        
        # CutType property
        obj.addProperty("App::PropertyEnumeration", "CutType", "ExtrudedCutout", "Cut type").CutType = ["Two dimensions", "Symmetric", "Through everything both sides", "Through everything side 1", "Through everything side 2"]
        obj.CutType = "Through everything both sides"  # Default value

        # CutSide property
        obj.addProperty("App::PropertyEnumeration", "CutSide", "ExtrudedCutout", "Side of the cut").CutSide = ["Inside", "Outside"]
        obj.CutSide = "Inside"  # Default value

        obj.Proxy = self

    def onChanged(self, fp, prop):
        '''Respond to property changes'''
        if prop in ["Sketch", "SelectedObject", "ExtrusionLength1", "ExtrusionLength2", "CutSide", "CutType"]:
            App.ActiveDocument.recompute()  # Trigger a recompute when these properties change
        
        # Show or hide length properties based in the CutType property:
        if prop == "CutType":
            if fp.CutType == "Through everything both sides":
                fp.setEditorMode("ExtrusionLength1", 2) # Hide
                fp.setEditorMode("ExtrusionLength2", 2) # Hide
            elif fp.CutType == "Through everything side 1":
                fp.setEditorMode("ExtrusionLength1", 2) # Hide
                fp.setEditorMode("ExtrusionLength2", 2) # Hide
            elif fp.CutType == "Through everything side 2":
                fp.setEditorMode("ExtrusionLength1", 2) # Hide
                fp.setEditorMode("ExtrusionLength2", 2) # Hide
            elif fp.CutType == "Symmetric":
                fp.setEditorMode("ExtrusionLength1", 0) # Show
                fp.setEditorMode("ExtrusionLength2", 2) # Hide
            else:
                fp.setEditorMode("ExtrusionLength1", 0) # Show
                fp.setEditorMode("ExtrusionLength2", 0) # Show

    def execute(self, fp):
        '''Perform the cut when the object is recomputed'''
        try:
            # Debug: Print the values of Sketch, SelectedObject, and CutSide
            App.Console.PrintMessage(f"Sketch: {fp.Sketch}\n")
            App.Console.PrintMessage(f"SelectedObject: {fp.SelectedObject}\n")
            App.Console.PrintMessage(f"CutSide: {fp.CutSide}\n")

            # Ensure the Sketch and SelectedObject properties are valid
            if fp.Sketch is None or fp.SelectedObject is None:
                raise Exception("Both the Sketch and SelectedObject properties must be set.")
            
            cutSketch = fp.Sketch
            selected_object = fp.SelectedObject

            if fp.CutType == "Two dimensions":
                ExtLength1 = fp.ExtrusionLength1.Value
                ExtLength2 = fp.ExtrusionLength2.Value

            if fp.CutType == "Symmetric":
                ExtLength1 = fp.ExtrusionLength1.Value/2
                ExtLength2 = fp.ExtrusionLength1.Value/2

            if fp.CutType == "Through everything both sides":
                TotalLength = fp.SelectedObject.Shape.BoundBox.DiagonalLength

                ExtLength1 = TotalLength
                ExtLength2 = TotalLength

            if fp.CutType == "Through everything side 1":
                TotalLength = fp.SelectedObject.Shape.BoundBox.DiagonalLength

                ExtLength1 = TotalLength
                ExtLength2 = -TotalLength

            if fp.CutType == "Through everything side 2":
                TotalLength = fp.SelectedObject.Shape.BoundBox.DiagonalLength

                ExtLength2 = TotalLength
                ExtLength1 = -TotalLength

            # Get the selected face and its normal from the SelectedObject
            faces = fp.SelectedObject.Shape.Faces
            
            # Retrieve the linked object and sub-element from the property
            linked_obj, face_name = fp.SelectedFace
            face_name = face_name[0]
            selected_face = linked_obj.Shape.getElement(face_name)

            normal_vector = selected_face.normalAt(0, 0)

            # Step 1: Determine the sheet metal thickness
            min_distance = float('inf')
            
            for face in faces:
                if face is not selected_face:
                    if normal_vector.isEqual(face.normalAt(0, 0).multiply(-1), 1e-6):
                        distance_info = selected_face.distToShape(face)
                        distance = distance_info[0]
                        if distance < min_distance:
                            min_distance = distance
        
            if min_distance == float('inf'):
                raise Exception("No opposite face found to calculate thickness.")
            
            thickness = min_distance

            # Step 2: Find pairs of parallel faces
            parallel_faces = []
            for i, face1 in enumerate(faces):
                for j, face2 in enumerate(faces):
                    if i >= j:
                        continue
                    if face1.normalAt(0, 0).isEqual(face2.normalAt(0, 0).multiply(-1), 1e-6):
                        distance_info = face1.distToShape(face2)
                        distance = distance_info[0]
                        if abs(distance - thickness) < 1e-6:
                            parallel_faces.extend([face1, face2])
        
            if parallel_faces:
                shell = Part.Shell(parallel_faces)
            else:
                raise Exception("No pairs of parallel faces with the specified thickness distance were found.")

            # Step 3: Extrude the cut sketch
            myFace = Part.Face(cutSketch.Shape)

            if ExtLength1 == 0 and ExtLength2 == 0:
                raise Exception("Cut length cannot be zero for both sides.")
            else:
                if ExtLength1 == 0:
                    ExtLength1 = (-ExtLength2)
                if ExtLength2 == 0:
                    ExtLength2 = (-ExtLength1)

                ExtLength1 = myFace.Faces[0].normalAt(0, 0) * (-ExtLength1)
                ExtLength2 = myFace.Faces[0].normalAt(0, 0) * ExtLength2

                myExtrusion1 = myFace.extrude(ExtLength1)
                myExtrusion2 = myFace.extrude(ExtLength2)
                myUnion = Part.Solid.fuse(myExtrusion1, myExtrusion2).removeSplitter()
                myCommon = myUnion.common(shell)

            # Step 4: Find connected components and offset shapes
            connected_components = self.find_connected_faces(myCommon)
            offset_shapes = []
            for component in connected_components:
                component_shell = Part.Shell(component)
                if component_shell.isValid():
                    offset_shape = component_shell.makeOffsetShape(-thickness, 0, fill=True)
                    if offset_shape.isValid():
                        offset_shapes.append(offset_shape)

            # Step 5: Combine the offsets
            if offset_shapes:
                combined_offset = Part.Solid(offset_shapes[0])
                for shape in offset_shapes[1:]:
                    combined_offset = combined_offset.fuse(shape)

                # Step 6: Cut
                # Check the "CutSide" property to decide how to perform the cut
                if fp.CutSide == "Inside":
                    cut_result = selected_object.Shape.cut(combined_offset).removeSplitter()
                elif fp.CutSide == "Outside":
                    cut_result = selected_object.Shape.common(combined_offset).removeSplitter()
                else:
                    raise Exception("Invalid CutSide value.")

                fp.Shape = cut_result
            else:
                raise Exception("No valid offset shapes were created.")

        except Exception as e:
            App.Console.PrintError(f"Error: {e}\n")

    def find_connected_faces(self, shape):
        '''Find connected faces in a shape'''
        faces = shape.Faces
        visited = set()
        components = []
        
        def is_connected(face1, face2):
            for edge1 in face1.Edges:
                for edge2 in face2.Edges:
                    if edge1.isSame(edge2):
                        return True
            return False

        def dfs(face, component):
            visited.add(face)
            component.append(face)
            for next_face in faces:
                if next_face not in visited and is_connected(face, next_face):
                    dfs(next_face, component)

        for face in faces:
            if face not in visited:
                component = []
                dfs(face, component)
                components.append(component)

        return components

##########################################################################################################
# Gui code
##########################################################################################################

if SheetMetalTools.isGuiLoaded():
    from FreeCAD import Gui

    icons_path = SheetMetalTools.icons_path

    class SMExtrudedCutoutVP:
        "A View provider for Sheet Metal Cut"

        def __init__(self, obj):
            self.Object = obj.Object
            obj.Proxy = self

        def attach(self, obj):
            '''Called when the ViewProvider is attached to an object'''
            self.Object = obj.Object
            return

        def updateData(self, fp, prop):
            '''Handle updates to properties'''
            return

        def getDisplayModes(self, obj):
            '''Define display modes for the object'''
            return ["Flat", "Shaded"]

        def setDisplayMode(self, mode):
            '''Set a specific display mode'''
            if mode == "Flat":
                return "Flat"
            elif mode == "Shaded":
                return "Shaded"
            return "Flat"

        def onChanged(self, vp, prop):
            '''Triggered when the object or its properties change'''
            if prop == "Shape":
                vp.ViewObject.Document.recompute()

        def __getstate__(self):
            '''Return the state of the object for serialization'''
            return None

        def __setstate__(self, state):
            '''Restore the object from its state'''
            self.loads(state)

        def claimChildren(self):
            '''Define the children of the object'''
            objs = []
            if hasattr(self.Object, "SelectedObject") and self.Object.SelectedObject is not None:
                # If SelectedObject is a PropertyLink, you need to access it correctly
                selected_object = self.Object.SelectedObject
                if hasattr(selected_object, "Shape"):
                    objs.append(selected_object)
            if hasattr(self.Object, "Sketch") and self.Object.Sketch is not None:
                objs.append(self.Object.Sketch)
            return objs

        def getIcon(self):
            '''Return the icon for the object'''
            icons_path = SheetMetalTools.icons_path
            return os.path.join(icons_path, "SheetMetal_AddCutout.svg")

    class SMExtrudedCutoutPDVP:
        "A View provider for Sheet Metal Cut"

        def __init__(self, obj):
            self.Object = obj.Object
            obj.Proxy = self

        def attach(self, obj):
            '''Called when the ViewProvider is attached to an object'''
            self.Object = obj.Object
            return

        def updateData(self, fp, prop):
            '''Handle updates to properties'''
            return

        def getDisplayModes(self, obj):
            '''Define display modes for the object'''
            return ["Flat", "Shaded"]

        def setDisplayMode(self, mode):
            '''Set a specific display mode'''
            if mode == "Flat":
                return "Flat"
            elif mode == "Shaded":
                return "Shaded"
            return "Flat"

        def onChanged(self, vp, prop):
            '''Triggered when the object or its properties change'''
            if prop == "Shape":
                vp.ViewObject.Document.recompute()

        def __getstate__(self):
            '''Return the state of the object for serialization'''
            return None

        def __setstate__(self, state):
            '''Restore the object from its state'''
            self.loads(state)

        def claimChildren(self):
            '''Define the children of the object (if any)'''
            objs = []
            if hasattr(self.Object, "Sketch") and self.Object.Sketch is not None:
                objs.append(self.Object.Sketch)
            return objs

        def getIcon(self):
            '''Return the icon for the object'''
            icons_path = SheetMetalTools.icons_path
            return os.path.join(icons_path, "SheetMetal_AddCutout.svg")

    class AddExtrudedCutoutCommandClass:
        """Add Extruded Cutout command"""

        def GetResources(self):
            return {
                "Pixmap": os.path.join(
                    icons_path, "SheetMetal_AddCutout.svg"
                ),  # the name of a svg file available in the resources
                "MenuText": "Extruded Cutout",
                "Accel": "E, C",
                "ToolTip": "SheetMetal Extruded Cutout"
            }

        def Activated(self):
            '''Create a Extruded Cutout object from user selections'''

            doc = App.ActiveDocument

            # Get the selected face
            selection = Gui.Selection.getSelectionEx()[0]
            obj = selection.Object

            # Check if we have any sub-objects (faces) selected
            if len(selection.SubObjects) == 0:
                raise Exception("No face selected. Please select a face.")

            # Get the selected face directly from SubObjects
            selected_face = [obj, selection.SubElementNames[0]]

            # Identify selected sketch and object
            cutSketch = Gui.Selection.Filter("SELECT Sketcher::SketchObject")
            cutSketch.match()
            cutSketch = cutSketch.result()[0][0].Object if cutSketch.result() else None

            selection = Gui.Selection.getSelection()
            selected_object = selection[0]
            if cutSketch is None or not selected_object.Shape:
                raise Exception("Both a valid sketch and an object with a shape must be selected.")
            
            # Create and assign the ExtrudedCutout object
            doc.openTransaction("ExtrudedCutout") # Feature that makes undoing and redoing easier - START
            if selected_object.isDerivedFrom("PartDesign::Feature"):
                SMBody = selected_object.getParent()

                obj = App.ActiveDocument.addObject("PartDesign::FeaturePython", "ExtrudedCutout")
                ExtrudedCutout(obj, cutSketch, selected_object, selected_face)

                SMExtrudedCutoutPDVP(obj.ViewObject)

                SMBody.addObject(obj)
            else:
                obj = App.ActiveDocument.addObject("Part::FeaturePython", "ExtrudedCutout")
                ExtrudedCutout(obj, cutSketch, selected_object, selected_face)
                
                SMExtrudedCutoutVP(obj.ViewObject)
            cutSketch.ViewObject.hide()
            selected_object.ViewObject.hide()
            App.ActiveDocument.recompute()
            doc.commitTransaction() # Feature that makes undoing and redoing easier - END
 

        def IsActive(self):
            if len(Gui.Selection.getSelection()) < 2:
                return False
            return True
         
    Gui.addCommand("SheetMetal_AddCutout", AddExtrudedCutoutCommandClass())