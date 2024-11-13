import FreeCAD
import FreeCAD as App
import FreeCADGui as Gui
import Part
import os  # Make sure 'os' is imported for the icon path
import SheetMetalTools

class ExtrudedCutout:
    def __init__(self, obj, sketch, selected_face):
        '''Initialize the parametric Sheet Metal Cut object and add properties'''
        obj.addProperty("App::PropertyLink", "Sketch", "ExtrudedCutout", "The sketch for the cut").Sketch = sketch
        obj.addProperty("App::PropertyLinkSub", "SelectedFace", "ExtrudedCutout", "The selecteds object and face").SelectedFace = selected_face
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
        if prop in ["Sketch", "SelectedFace", "ExtrusionLength1", "ExtrusionLength2", "CutSide", "CutType"]:
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
            # Debug: Print the values of Sketch, SelectedFace, and CutSide
            App.Console.PrintMessage(f"Sketch: {fp.Sketch}\n")
            App.Console.PrintMessage(f"SelectedFace: {fp.SelectedFace}\n")
            App.Console.PrintMessage(f"CutSide: {fp.CutSide}\n")

            # Ensure the Sketch and SelectedFace properties are valid
            if fp.Sketch is None or fp.SelectedFace is None:
                raise Exception("Both the Sketch and SelectedFace properties must be set.")
            
            # Get the sketch from the properties
            cutSketch = fp.Sketch
            
            # Get selected object and selected face from the properties
            selected_object, face_name = fp.SelectedFace
            face_name = face_name[0]
            selected_face = selected_object.Shape.getElement(face_name)

            normal_vector = selected_face.normalAt(0, 0)

            # Lengths
            if fp.CutType == "Two dimensions":
                ExtLength1 = fp.ExtrusionLength1.Value
                ExtLength2 = fp.ExtrusionLength2.Value

            if fp.CutType == "Symmetric":
                ExtLength1 = fp.ExtrusionLength1.Value/2
                ExtLength2 = fp.ExtrusionLength1.Value/2

            if fp.CutType == "Through everything both sides":
                TotalLength = selected_object.Shape.BoundBox.DiagonalLength

                ExtLength1 = TotalLength
                ExtLength2 = TotalLength

            if fp.CutType == "Through everything side 1":
                TotalLength = selected_object.Shape.BoundBox.DiagonalLength

                ExtLength1 = TotalLength
                ExtLength2 = -TotalLength

            if fp.CutType == "Through everything side 2":
                TotalLength = selected_object.Shape.BoundBox.DiagonalLength

                ExtLength2 = TotalLength
                ExtLength1 = -TotalLength

            # Step 1: Determine the sheet metal thickness
            min_distance = float('inf')
            
            faces = selected_object.Shape.Faces
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
            modes = []
            return modes

        def setDisplayMode(self, mode):
            return mode

        def onChanged(self, vp, prop):
            '''Triggered when the object or its properties change'''
            return

        def __getstate__(self):
            '''Return the state of the object for serialization'''
            return None

        def __setstate__(self, state):
            '''Restore the object from its state'''
            self.loads(state)

        def claimChildren(self):
            '''Define the children of the object'''
            objs = []
            if hasattr(self.Object, "SelectedFace") and self.Object.SelectedFace is not None:
                # If SelectedFace is a PropertyLink, you need to access it correctly
                selected_object = self.Object.SelectedFace[0]
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
            modes = []
            return modes

        def setDisplayMode(self, mode):
            return mode

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
                "ToolTip": "Extruded cutout from sketch extrusion\n"
                    "1. Select a face of the sheet metal part (must not be the thickness face) and\n"
                    "2. Select a sketch for the extruded cut (the sketch must be closed).\n"
                    "3. Use Property editor to modify other parameters"
            }

        def Activated(self):
            '''Create a Extruded Cutout object from user selections'''

            doc = App.ActiveDocument

            # Get the selecteds object and face
            selection = Gui.Selection.getSelectionEx()[0]
            if selection.Object.isDerivedFrom("Sketcher::SketchObject"): # When user select first the sketch
                # Get selected sketch
                cutSketch = Gui.Selection.Filter("SELECT Sketcher::SketchObject")
                cutSketch.match()
                cutSketch = cutSketch.result()[0][0].Object if cutSketch.result() else None

                # Check if we have any sub-objects (faces) selected
                selection = Gui.Selection.getSelectionEx()[1]
                if len(selection.SubObjects) == 0:
                    raise Exception("No face selected. Please select a face.")

                #Get selected object
                selected_object = selection.Object

                # Get the selected face
                selected_face = [selected_object, selection.SubElementNames[0]]
            else:  # When user select first the object face
                if len(selection.SubObjects) == 0: # Check if we have any sub-objects (faces) selected
                    raise Exception("No face selected. Please select a face.")
                
                # Get selected object
                selected_object = selection.Object

                # Get the selected face
                selected_face = [selected_object, selection.SubElementNames[0]]

                # Get selected sketch
                cutSketch = Gui.Selection.Filter("SELECT Sketcher::SketchObject")
                cutSketch.match()
                cutSketch = cutSketch.result()[0][0].Object if cutSketch.result() else None

            if cutSketch is None or not selected_object.Shape:
                raise Exception("Both a valid sketch and an object with a shape must be selected.")
            
            # Create and assign the ExtrudedCutout object
            doc.openTransaction("ExtrudedCutout") # Feature that makes undoing and redoing easier - START
            if selected_object.isDerivedFrom("PartDesign::Feature"):
                SMBody = SheetMetalTools.smGetBodyOfItem(selected_object)

                obj = App.ActiveDocument.addObject("PartDesign::FeaturePython", "ExtrudedCutout")
                ExtrudedCutout(obj, cutSketch, selected_face)

                SMExtrudedCutoutPDVP(obj.ViewObject)

                SMBody.addObject(obj)
            else:
                obj = App.ActiveDocument.addObject("Part::FeaturePython", "ExtrudedCutout")
                ExtrudedCutout(obj, cutSketch, selected_face)
                
                SMExtrudedCutoutVP(obj.ViewObject)
            cutSketch.ViewObject.hide()
            selected_object.ViewObject.hide()
            App.ActiveDocument.recompute()
            doc.commitTransaction() # Feature that makes undoing and redoing easier - END
 
        def IsActive(self):
            if len(Gui.Selection.getSelection()) < 2:
                return False
            if len(Gui.Selection.getSelection()) > 2:
                return False
            return True
         
    Gui.addCommand("SheetMetal_AddCutout", AddExtrudedCutoutCommandClass())