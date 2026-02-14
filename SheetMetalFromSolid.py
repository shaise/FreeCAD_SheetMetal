# ######################################################################
#
#  SheetMetalFromSolid.py
#
#  Copyright 2026 Shai Seger <shaise at gmail dot com>
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
# ######################################################################

import FreeCAD
import Part
import SheetMetalTools
import os

translate = FreeCAD.Qt.translate

# List of properties to be saved as defaults.
smFromSolidDefaultVars = ["Radius", "Thickness", "KFactor"]

class SMFromSolid:
    def __init__(self, obj):
        obj.addProperty("App::PropertyLink", "baseObject", "Parameters", "Base object")
        obj.addProperty("App::PropertyLinkSubList", "removeFaces", "Parameters", "Faces to remove")
        obj.addProperty("App::PropertyLinkSubList", "ripEdges", "Parameters", "Edges to rip (seams)")
        
        SheetMetalTools.smAddLengthProperty(obj, "Radius", "Bend Radius", 1.0)
        SheetMetalTools.smAddLengthProperty(obj, "Thickness", "Wall Thickness", 1.0)
        SheetMetalTools.smAddFloatProperty(obj, "KFactor", "K Factor", 0.5)
        
        SheetMetalTools.taskRestoreDefaults(obj, smFromSolidDefaultVars)
        obj.Proxy = self

    def execute(self, fp):
        if not fp.baseObject:
            return

        base_shape = fp.baseObject.Shape
        if not base_shape.Faces:
            return

        # Get faces to keep (all faces minus removed faces)
        faces_to_remove_names = []
        if fp.removeFaces:
            # Handle LinkSubList format which might vary slightly
            # It usually returns a list of tuples or strings depending on version/context, 
            # but standard property access gives us the object and subelement names.
            # Here we assume removeFaces contains the subelement names if linked to the same object.
            # Actually, LinkSubList is [ (obj, [name1, name2]) ] or similar.
            
            # Let's rely on the property value structure:
            # It is a list of tuples: [(object, [list of subelement names])]
            for link_ref in fp.removeFaces:
                obj = link_ref[0]
                if obj == fp.baseObject: # Ensure we are talking about the base object
                    faces_to_remove_names.extend(link_ref[1])

        faces_to_keep = []
        for face in base_shape.Faces:
            # We need to find the name of this face in the base object
            # This is tricky without the element map, but we can check geometric strict inclusion/equality?
            # Or rely on getElement/getElementName if available.
            # A safer way for topological stability is relying on the standard ExpFace names if the geometry hasn't changed,
            # but mapped names are better.
            
            # For now, let's use the standard "FaceN" matching if possible, or geometry check.
            # NOTE: FreeCAD's internal naming can be fragile.
            
            # Let's try to identify if this face is in the remove list.
            # We will use the 'getElement' from the shape if possible to check against selected subelements.
            
            is_removed = False
            for removed_name in faces_to_remove_names:
                removed_face = base_shape.getElement(removed_name)
                if face.isSame(removed_face):
                    is_removed = True
                    break
            
            if not is_removed:
                faces_to_keep.append(face)

        if not faces_to_keep:
             # If all faces removed, nothing to do
            return

        shell = Part.makeShell(faces_to_keep)
        
        # Now identify edges to fillet (bend) vs edges to keep sharp (rip/seam).
        # We need to find shared edges between the remaining faces.
        # Edges that are shared by 2 faces in the shell are candidates for bends.
        # If an edge is in "ripEdges", we skip filleting it.
        
        rip_edges_names = []
        if fp.ripEdges:
            for link_ref in fp.ripEdges:
                obj = link_ref[0]
                if obj == fp.baseObject:
                    rip_edges_names.extend(link_ref[1])
        
        # We need to collect edges that we WANT to fillet.
        # Part.makeFillet requires a shell (or solid) and a list of edges.
        
        edges_to_fillet = []
        
        # Iterate over all edges in the shell
        # We only care about edges that connect two faces. 
        # Shell.Edges includes boundary edges too (connected to only 1 face).
        # We should NOT fillet boundary edges.
        
        # Build an edge map to count face usage? 
        # Or just use the native `Part.Shape.getEdges()` logic?
        # Actually, `makeFillet` on a shell might fillet the boundaries if we ask it to.
        # We only want to fillet the "ridges".
        
        # Helper to check if edge is in rip list
        def is_rip_edge(e):
            for rip_name in rip_edges_names:
                rip_edge = base_shape.getElement(rip_name)
                # Note: The edge in the shell might have different orientation or be a copy.
                # `isSame` checks for geometric/topological identity.
                if e.isSame(rip_edge):
                    return True
            return False

        # Find edges shared by at least 2 faces in the NEW shell.
        # Since we made a shell from faces, `shell.Edges` contains all edges.
        # We need to know which ones are "inner" seams.
        
        # A robust way: 
        # go through each edge in the shell.
        # Check if it IsSame as any edge in the rip list.
        # If NOT in rip list, AND it is shared by 2 faces of the shell, add to fillet list.
        
        # How to check if shared by 2 faces efficiently?
        # `shell.removeSplitter()` might help to sew? `makeShell` usually creates a sewn shape if faces share edges.
        # If `makeShell` just groups them, we might need `Part.Compound` converted to `Shell` and then fixed?
        # `Part.makeShell` usually creates a valid shell.
        
        # Lets check edge connections
        # We can iterate unique edges.
        
        import collections
        
        # This is a generic approach to find shared edges
        # But `makeFillet` needs edges from the shell itself.
        
        shell_edges = shell.Edges
        for e in shell_edges:
            # Check if this edge is a seam/rip
            if is_rip_edge(e):
                continue
                
            # Check topology: Is this edge shared by 2 faces in the *shell*?
            # We can use `shell.getConnectedFaces(e)`? No, that method doesn't exist on Shape.
            # We can count how many faces in `faces_to_keep` contain this edge.
            
            count = 0
            for f in faces_to_keep:
                for fe in f.Edges:
                    if fe.isSame(e):
                        count += 1
            
            if count >= 2:
                # It is a bend!
                edges_to_fillet.append(e)

        if edges_to_fillet and fp.Radius > 0:
            try:
                # 0 create a fillet
                # We need to pass the shell and the edges
                # makeFillet(radius, edgeList) -> returns a new Shape
                shell = shell.makeFillet(fp.Radius, edges_to_fillet)
            except Exception as e:
                FreeCAD.Console.PrintError(f"SheetMetalFromSolid: Fillet failed: {e}\n")

        # Now thicken the shell
        # makeOffsetShape(offset, tolerance, inter=False, self_inter=False, offsetMode=0, join=0, fill=True)
        # join=0 (Arc), 1 (Tangent), 2 (Intersection)
        # fill=True to make a solid
        
        # Thickness direction:
        # Usually positive is "outwards" relative to face normals.
        # If we selected a solid, faces point outwards.
        # If we want to maintain the INNER dimensions (the solid was the mold), we thicken OUTWARDS (+Thickness).
        # If the solid represented the bounding box, maybe we want INWARDS (-Thickness).
        
        # Standard sheet metal usually assumes the base shape is the MOLD (inner shape).
        # So we offset by +Thickness.
        
        try:
            # Using 1e-4 tolerance, join=0 (rounded corners if needed, though we already filleted)
            # If we filleted, the corners are round. 
            solid = shell.makeOffsetShape(fp.Thickness, 0.001, fill=True)
            fp.Shape = solid
        except Exception as e:
            FreeCAD.Console.PrintError(f"SheetMetalFromSolid: Thicken failed: {e}\n")
            fp.Shape = shell # Fallback to shell invocation

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


# View Provider
if SheetMetalTools.isGuiLoaded():
    Gui = FreeCAD.Gui

    class SMFromSolidViewProvider(SheetMetalTools.SMViewProvider):
        def getIcon(self):
            return os.path.join(SheetMetalTools.icons_path, "SheetMetal_FromSolid.svg")

        def getTaskPanel(self, obj):
            return SMFromSolidTaskPanel(obj)
            
    class SMFromSolidTaskPanel:
        def __init__(self, obj):
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("CreateFromSolid.ui") # We need to create this UI file!
            # Or we can build it programmatically if we don't want to create a .ui file, 
            # but SheetMetalTools relies on .ui.
            # Wait, `CreateBaseShape.ui` exists. Maybe I can reuse/modify a similar one or create a new one.
            # I will create a new UI file `CreateFromSolid.ui` as well.
            
            SheetMetalTools.taskConnectSpin(obj, self.form.spinRadius, "Radius")
            SheetMetalTools.taskConnectSpin(obj, self.form.spinThickness, "Thickness")
            SheetMetalTools.taskConnectSpin(obj, self.form.spinKFactor, "KFactor")
            
            # Selection for Remove Faces
            self.selFaces = SheetMetalTools.taskConnectSelection(
                self.form.btnRemoveFaces, self.form.listRemoveFaces,
                obj, ["Face"], self.form.btnClearFaces, "removeFaces", hideObject=False
            )
            # Constrain selection to the base object
            self.selFaces.ConstrainToObject = obj.baseObject

            # Selection for Rip Edges
            self.selEdges = SheetMetalTools.taskConnectSelection(
                self.form.btnRipEdges, self.form.listRipEdges,
                obj, ["Edge"], self.form.btnClearEdges, "ripEdges", hideObject=False
            )
            self.selEdges.ConstrainToObject = obj.baseObject

        def accept(self):
            SheetMetalTools.taskAccept(self)
            SheetMetalTools.taskSaveDefaults(self.obj, smFromSolidDefaultVars)
            return True

        def reject(self):
            SheetMetalTools.taskReject(self)
            return True


    class FromSolidCommandClass:
        """Convert a solid to a sheet metal object."""

        def GetResources(self):
            return {
                "Pixmap": os.path.join(SheetMetalTools.icons_path, "SheetMetal_FromSolid.svg"),
                "MenuText": translate("SheetMetal", "Convert to Sheet Metal"),
                "Accel": "C, S",
                "ToolTip": translate("SheetMetal", "Convert a solid to a sheet metal object"),
            }

        def Activated(self):
            sel_ex = Gui.Selection.getSelectionEx()
            if not sel_ex:
                SheetMetalTools.smWarnDialog("Please select a solid object first.")
                return
            
            selection_item = sel_ex[0]
            base_obj = selection_item.Object
            
            # Ensure it has Shape
            if not hasattr(base_obj, "Shape"):
                 SheetMetalTools.smWarnDialog("Selection is not a geometric object.")
                 return

            new_obj, active_body = SheetMetalTools.smCreateNewObject(base_obj, "SheetMetal")
            if new_obj is None:
                return

            SMFromSolid(new_obj)
            SMFromSolidViewProvider(new_obj.ViewObject)
            
            new_obj.baseObject = base_obj
            
            # Process pre-selected sub-elements
            faces = []
            edges = []
            for sub in selection_item.SubElementNames:
                if sub.startswith("Face"):
                    faces.append(sub)
                elif sub.startswith("Edge"):
                    edges.append(sub)
            
            if faces:
                new_obj.removeFaces = [(base_obj, faces)]
            if edges:
                new_obj.ripEdges = [(base_obj, edges)]

            # We assume the user wants to work on the selected object.
            
            SheetMetalTools.smAddNewObject(base_obj, new_obj, active_body, SMFromSolidTaskPanel)

        def IsActive(self):
            return len(Gui.Selection.getSelection()) == 1

    Gui.addCommand("SheetMetal_FromSolid", FromSolidCommandClass())
