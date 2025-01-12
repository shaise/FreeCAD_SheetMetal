# -*- coding: utf-8 -*-
##############################################################################
#
#  SheetMetalBend.py
#
#  Copyright 2024 Shai Seger <shaise at gmail dot com>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
##############################################################################

import math
import os
import re
import FreeCAD
import importDXF
import importSVG
import Part

translate = FreeCAD.Qt.translate

mod_path = os.path.dirname(__file__)
icons_path = os.path.join(mod_path, "Resources", "icons")
panels_path = os.path.join(mod_path, "Resources", "panels")
language_path = os.path.join(mod_path, "translations")
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
smEpsilon = FreeCAD.Base.Precision.approximation()
print("======> Epsilon:", + smEpsilon)
smForceRecompute = False
smObjectsToRecompute = set()

class SMException(Exception):
    ''' Sheet Metal Custom Exception '''

def isGuiLoaded():
    if hasattr(FreeCAD, "GuiUp"):
        return FreeCAD.GuiUp
    return False
    
if isGuiLoaded():
    from PySide import QtCore, QtGui
    from FreeCAD import Gui

    def smWarnDialog(msg):
        diag = QtGui.QMessageBox(
            QtGui.QMessageBox.Warning,
            FreeCAD.Qt.translate("QMessageBox", "Error in macro MessageBox"),
            msg,
        )
        diag.setWindowModality(QtCore.Qt.ApplicationModal)
        diag.exec_()

    class SMSingleSelectionObserver:
        ''' used for tasks that needs to be aware of selection changes '''
        def __init__(self):
            self.button = None

        def addSelection(self, document, obj, element, position):
            taskSingleSelectionChanged(self.button)
    
    smSingleSelObserver = SMSingleSelectionObserver()
    Gui.Selection.addObserver(smSingleSelObserver)

    def smSelectGreedy():
        if hasattr(Gui.Selection, "setSelectionStyle"): # compatibility with FC link version
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.GreedySelection)

    def smSelectNormal():
        if hasattr(Gui.Selection, "setSelectionStyle"): # compatibility with FC link version
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)


    def smHideObjects(*args):
        for arg in args:
            if arg:
                obj = Gui.ActiveDocument.getObject(arg.Name)
                if obj:
                    obj.Visibility = False

    # Task panel helper code
    def taskPopulateSelectionList(qwidget, baseObject):
        qwidget.clear()
        obj, items = baseObject
        if not isinstance(items, list):
            items = [items]
        for subf in items:
            # FreeCAD.Console.PrintLog("item: " + subf + "\n")
            item = QtGui.QTreeWidgetItem(qwidget)
            item.setText(0, obj.Name)
            item.setIcon(0, QtGui.QIcon(":/icons/Tree_Part.svg"))
            item.setText(1, subf)

    def taskPopulateSelectionSingle(textbox, baseObject):
        if baseObject is None:
            textbox.setText("")
        elif isinstance(baseObject, tuple):
            obj, items = baseObject
            item = "None" if len(items) == 0 else items[0]
            textbox.setText(f"{obj.Name}: {item}")
        else:
            textbox.setText(baseObject.Name)
            
    def updateSelectionElements(obj, allowedTypes):
        if not obj:
            return

        sel = Gui.Selection.getSelectionEx()[0]
        if not sel.HasSubObjects:
            return

        subItems = []
        for element in sel.SubElementNames:
            if smStripTrailingNumber(element) in allowedTypes:
                subItems.append(element)
        if len(subItems) == 0:
            return
        #print(sel.Object, subItems)
        obj.baseObject = (sel.Object, subItems)

    def _taskToggleSelectionMode(isChecked, addRemoveButton, treeWidget, obj, allowedTypes):
        if isChecked:
            obj.Visibility=False
            obj.baseObject[0].Visibility=True
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj.baseObject[0],obj.baseObject[1])
            smSelectGreedy()
            addRemoveButton.setText('Preview')
        else:
            updateSelectionElements(obj, allowedTypes)
            Gui.Selection.clearSelection()
            smSelectNormal()
            obj.Document.recompute()
            obj.baseObject[0].Visibility=False
            obj.Visibility=True
            addRemoveButton.setText('Select')
            taskPopulateSelectionList(treeWidget, obj.baseObject)
    
    def taskConnectSelection(addRemoveButton, treeWidget, obj, allowedTypes):
        taskPopulateSelectionList(treeWidget, obj.baseObject)
        addRemoveButton.toggled.connect(
            lambda value: _taskToggleSelectionMode(value, addRemoveButton, treeWidget, 
                                                   obj, allowedTypes))
        
    def _taskToggleSingleSelMode(task, isChecked, button, textbox, obj, selProperty, allowedTypes):
        prop = getattr(obj, selProperty)
        if isinstance(prop, tuple):
            prop = prop[0]
        baseObject = obj.baseObject[0] if hasattr(obj, "baseObject") else None
        Gui.Selection.clearSelection()
        if isChecked:
            if smSingleSelObserver.button is not None:
                smSingleSelObserver.button.toggle()
            if baseObject is not None:
                baseObject.Visibility=True
            obj.Visibility=False
            prop.Visibility=True
            button.activeTypes = allowedTypes
            button.activeObject = obj
            button.activeProperty = selProperty
            button.saveText = button.text()
            smSingleSelObserver.button = button
            textbox.setText(f"Select {button.saveText}...")
            button.setText("Cancel...")
        else:
            smSingleSelObserver.button = None
            if baseObject is not None:
                baseObject.Visibility=False
            obj.Visibility=True
            prop.Visibility=False
            task.activeSelection = {}
            taskPopulateSelectionSingle(textbox, prop)
            button.setText(button.saveText)

    def taskConnectSelectionSingle(task, button, textbox, obj, selProperty, allowedTypes):
        taskPopulateSelectionSingle(textbox, getattr(obj, selProperty))
        button.setCheckable(True)
        button.toggled.connect(
            lambda value: _taskToggleSingleSelMode(
                task, value, button, textbox, obj, selProperty, allowedTypes))
        
    def taskSingleSelectionChanged(button):
        if button is None:
            return
        selobj = Gui.Selection.getSelectionEx()[0]
        if len(selobj.SubElementNames) != 1:
            return
        selitem = selobj.SubElementNames[0]
        selobj = selobj.Object
        if isinstance(button.activeTypes, tuple):
            # make sure object is of disired type or linked to one
            objType, subObjTypes = button.activeTypes
            if not selobj.isDerivedFrom(objType):
                if selobj.isDerivedFrom("App::Link"):
                    selobj = selobj.LinkedObject
                elif selobj.isDerivedFrom("Part::Part2DObject"):
                    selobj = selobj.Objects[0]
                if not (selobj.isDerivedFrom(objType)):
                    return
        else:
            subObjTypes = button.activeTypes
        if len(subObjTypes) == 0 or smStripTrailingNumber(selitem) in subObjTypes:
            baseObject = selobj if len(subObjTypes) == 0 else (selobj, [selitem])
            setattr(button.activeObject, button.activeProperty, baseObject)
            button.activeObject.Document.recompute()
            button.toggle()


    def _taskRecomputeObject(obj):
        if hasattr(obj, "ManualRecompute") and obj.ManualRecompute:
            return
        obj.recompute()

    def _taskRecomputeDocument(obj = None):
        if obj is not None:
            if hasattr(obj, "ManualRecompute") and obj.ManualRecompute:
                return
            obj.Document.recompute()
        else:
            FreeCAD.ActiveDocument.recompute()

    def _taskUpdateValue(value, obj, objvar, callback):
        setattr(obj, objvar, value)
        try:  # avoid intermitant changes
            _taskRecomputeObject(obj)
        except:
            pass
        if callback is not None:
            callback(value)

    def _taskUpdateColor(formvar, obj, objvar, callback):
        value = formvar.property("color").name()
        setattr(obj, objvar, value)
        try:  # avoid intermitant changes
            _taskRecomputeObject(obj)
        except:
            pass
        if callback is not None:
            callback(value)

    def _taskEditFinished(obj):
        if hasattr(obj, "Object"):
            obj = obj.Object
        if hasattr(obj, "Document"):
            _taskRecomputeDocument(obj)

    def _getVarValue(obj, objvar):
        if not hasattr(obj, objvar):
            # Can happen if an old file is loaded and some props were renamed
            obj.recompute()
        return getattr(obj, objvar)
    
    def taskConnectSpin(task, formvar, objvar, callback = None, customObj = None):
        obj = task.obj if customObj is None else customObj
        formvar.setProperty("value", _getVarValue(obj, objvar))
        if customObj is None:
            Gui.ExpressionBinding(formvar).bind(obj, objvar)
        # keyboardTracking is set to False to avoid recompute on every key press
        formvar.setProperty("keyboardTracking",False)
        formvar.valueChanged.connect(lambda value: _taskUpdateValue(value, obj, objvar, callback))
        #formvar.editingFinished.connect(lambda: _taskEditFinished(obj))

    def taskConnectCheck(task, formvar, objvar, callback = None, customObj = None):
        obj = task.obj if customObj is None else customObj
        formvar.setChecked(_getVarValue(obj, objvar))
        if callback is not None:
            callback(formvar.isChecked())
        formvar.toggled.connect(lambda value: _taskUpdateValue(value, obj, objvar, callback))

    def taskConnectEnum(task, formvar, objvar, callback = None, customObj = None, customList = None):
        obj = task.obj if customObj is None else customObj
        val = _getVarValue(obj, objvar)
        enumlist = task.obj.getEnumerationsOfProperty(objvar) if customList is None else customList
        formvar.setProperty("currentIndex", enumlist.index(val))
        formvar.currentIndexChanged.connect(lambda value: _taskUpdateValue(value, obj, objvar, callback))

    def taskConnectColor(task, formvar, objvar, callback = None, customObj = None):
        obj = task.obj if customObj is None else customObj
        formvar.setProperty("color", _getVarValue(obj, objvar))
        formvar.changed.connect(lambda: _taskUpdateColor(formvar, obj, objvar, callback))

    def taskAccept(task, addRemoveButton = None):
        if addRemoveButton is not None and addRemoveButton.isChecked():
            addRemoveButton.toggle()
        if smSingleSelObserver.button is not None:
            smSingleSelObserver.button.toggle()
        FreeCAD.ActiveDocument.recompute()
        task.obj.Document.commitTransaction()
        Gui.Control.closeDialog()
        Gui.ActiveDocument.resetEdit()
        return True

    def taskReject(task, addRemoveButton = None):
        if addRemoveButton is not None and addRemoveButton.isChecked():
            smSelectNormal()
        if smSingleSelObserver.button is not None:
            smSingleSelObserver.button.toggle()
        FreeCAD.ActiveDocument.abortTransaction()
        Gui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()
        Gui.ActiveDocument.resetEdit()
      
    def taskSaveDefaults(obj, varList):
        for var in varList:
            if isinstance(var, tuple):
                var, saveVar = var
            else:
                saveVar = "default" + var
            val = getattr(obj, var)
            if hasattr(val, "Value"):
                val = val.Value
            if isinstance(val, bool):
                params.SetBool(saveVar, val)
            elif isinstance(val, float):
                params.SetFloat(saveVar, val)
            elif isinstance(val, int):
                params.SetInt(saveVar, val)
            else:
                params.SetString(saveVar, str(val))

    def taskRestoreDefaults(obj, varList):
        for var in varList:
            if isinstance(var, tuple):
                var, saveVar = var
            else:
                saveVar = "default" + var
            val = getattr(obj, var)
            if hasattr(val, "Value"):
                val = val.Value
            if isinstance(val, bool):
                newVal = params.GetBool(saveVar, val)
            elif isinstance(val, float):
                newVal = params.GetFloat(saveVar, val)
            elif isinstance(val, int):
                newVal = params.GetInt(saveVar, val)
            else:
                newVal = params.GetString(saveVar, str(val))
            setattr(obj, var, newVal)

    def taskLoadUI(*args):
        if len(args) == 1:
            path = os.path.join(panels_path, args[0])
            return Gui.PySideUic.loadUi(path)           
        forms = []
        for uiFile in args:
            path = os.path.join(panels_path, uiFile)
            forms.append(Gui.PySideUic.loadUi(path))
        return forms
    
    def smGuiExportSketch(sketches, fileType, fileName, useDialog = True):
        if useDialog:
            filePath, _ = QtGui.QFileDialog.getSaveFileName(
                Gui.getMainWindow(),
                translate("SheetMetal","Export unfold sketch"),
                fileName,                       # Default file path
                f"Vector Files (*.{fileType})"  # File type filters
            )
        else:
            filePath = fileName
        if filePath:
            if fileType == "dxf":
                importDXF.export(sketches, filePath)
            else:
                importSVG.export(sketches, filePath)
    
    def smAddNewObject(baseObj, newObj, activeBody, taskPanel = None):
        if activeBody is not None:
            activeBody.addObject(newObj)
        viewConf = GetViewConfig(baseObj)
        SetViewConfig(newObj, viewConf)
        Gui.Selection.clearSelection()
        #newObj.baseObject[0].ViewObject.Visibility = False
        baseObj.ViewObject.Visibility = False
        FreeCAD.ActiveDocument.recompute()
        if taskPanel is not None:
            dialog = taskPanel(newObj)
            Gui.Control.showDialog(dialog)
        return
    
    def smCreateNewObject(baseObj, name, allowPartDesign = True):
        doc = FreeCAD.ActiveDocument
        activeBody = None
        view = Gui.ActiveDocument.ActiveView
        if hasattr(view, 'getActiveObject'):
            activeBody = view.getActiveObject('pdbody')
        if not allowPartDesign or not smIsPartDesign(baseObj):
            doc.openTransaction(name)
            newObj = doc.addObject("Part::FeaturePython", name)
            activeBody = None
        else:
            if not smIsOperationLegal(activeBody, baseObj):
                return None, None
            doc.openTransaction(name)
            newObj = doc.addObject("PartDesign::FeaturePython", name)
        return (newObj, activeBody)
 

    #************************************************************************************
    #* View providers for part and part design
    #************************************************************************************

    class SMViewProvider:
        "A View provider for sheetmetal objects. supports Part/Part-Design types"

        def __init__(self, obj):
            obj.Proxy = self
            self.Object = obj.Object

        def attach(self, obj):
            self.Object = obj.Object
            return

        def setupContextMenu(self, viewObject, menu):
            action = menu.addAction(FreeCAD.Qt.translate(
                "QObject", "Edit %1").replace("%1", viewObject.Object.Label))
            action.triggered.connect(
                lambda: self.startDefaultEditMode(viewObject))
            return False

        def startDefaultEditMode(self, viewObject):
            viewObject.Document.setEdit(viewObject.Object, 0)

        def updateData(self, fp, prop):
            return

        def getDisplayModes(self, obj):
            modes = []
            return modes

        def setDisplayMode(self, mode):
            return mode

        def onChanged(self, vp, prop):
            return

        def __getstate__(self):
            #        return {'ObjectName' : self.Object.Name}
            return None

        def __setstate__(self, state):
            self.loads(state)

        # dumps and loads replace __getstate__ and __setstate__ post v. 0.21.2
        def dumps(self):
            return None

        def loads(self, state):
            if state is not None:
                doc = FreeCAD.ActiveDocument
                self.Object = doc.getObject(state['ObjectName'])

        def claimChildren(self):
            objs = []
            if not smIsPartDesign(self.Object) and hasattr(self.Object, "baseObject"):
                objs.append(self.Object.baseObject[0])
            if hasattr(self.Object, "Sketch"):
                objs.append(self.Object.Sketch)
            return objs

        def setEdit(self, vobj, mode):
            if not hasattr(self, "getTaskPanel"):
                return False
            taskd = self.getTaskPanel(vobj.Object)
            if smIsPartDesign(self.Object):
                self.Object.ViewObject.Visibility = True
            FreeCAD.ActiveDocument.openTransaction(self.Object.Name)
            Gui.Control.showDialog(taskd)
            return True

        def unsetEdit(self, _vobj, _mode):
            Gui.Control.closeDialog()
            if hasattr(self.Object, "baseObject"):
                self.Object.baseObject[0].ViewObject.Visibility = False
            self.Object.ViewObject.Visibility = True
            return False


# Else: In case no gui is loaded
else:
    def smWarnDialog(msg):
        SMLogger.warning(msg)

    def smHideObjects(*args):
        pass

def smStripTrailingNumber(item):
    return re.sub(r'\d+$', '', item)

def smAddToRecompute(obj):
    smObjectsToRecompute.add(obj)

def smRemoveFromRecompute(obj):
    smObjectsToRecompute.discard(obj)

    

def smBelongToBody(item, body):
    if body is None:
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False

def smIsSketchObject(obj):
    return obj.TypeId.startswith("Sketcher::")

def smGetParentBody(obj):
    if hasattr(obj, "getParent"):
        return obj.getParent()
    if hasattr(obj, "getParents"): # probably FreeCadLink version
        if len(obj.getParents()) == 0:
            return False
        return obj.getParents()[0][0]
    return None

def smIsPartDesign(obj):
    if smIsSketchObject(obj):
        parent = smGetParentBody(obj)
        if parent is None:
            return False
        return isinstance(parent, Part.BodyBase)
    return obj.TypeId.startswith("PartDesign::")

def smIsOperationLegal(body, selobj):
    # FreeCAD.Console.PrintLog(str(selobj) + " " + str(body) + " " + str(smBelongToBody(selobj, body)) + "\n")
    if smIsPartDesign(selobj) and not smBelongToBody(selobj, body):
        smWarnDialog(
            translate(
            "QMessageBox",
            "The selected geometry does not belong to the active Body.\n"
            "Please make the container of this item active by\n"
            "double clicking on it.",
            )
        )
        return False
    return True

def is_autolink_enabled():
    return params.GetInt("AutoLinkBendRadius", 0)

def use_old_unfolder():
    return params.GetBool("UseOldUnfolder", False)

def GetViewConfig(obj):
    if smIsSketchObject(obj):
        return None
    viewconf = {} 
    if hasattr(obj.ViewObject, "ShapeColor"): 
        viewconf["objShapeCol"] = obj.ViewObject.ShapeColor 
        viewconf["objShapeTsp"] = obj.ViewObject.Transparency 
        viewconf["objDiffuseCol"] = obj.ViewObject.DiffuseColor 
        # TODO: Make the individual face colors be retained 
        # needDiffuseColorExtension = ( len(selobj.ViewObject.DiffuseColor) < len(selobj.Shape.Faces) ) 
    else:
        return None
    return viewconf 
 
 
def SetViewConfig(obj, viewconf): 
    if hasattr(obj.ViewObject, "ShapeColor") and viewconf: 
        obj.ViewObject.ShapeColor = viewconf["objShapeCol"] 
        obj.ViewObject.Transparency = viewconf["objShapeTsp"] 
        obj.ViewObject.DiffuseColor = viewconf["objDiffuseCol"] 

def getOriginalBendObject(obj):
    for item in obj.OutListRecursive:
        if hasattr(item, "Proxy"):
            proxy = item.Proxy.__class__.__name__
            if (proxy == 'SMBaseBend'
            or proxy == 'SMBendWall'
            or proxy == 'SMSolidBend'
            or proxy == 'SMFoldWall'
            ):
                if not getOriginalBendObject(item):
                    return item
    return None

def getElementFromTNP(tnpName):
    names = tnpName.split('.')
    if len(names) > 1:
        FreeCAD.Console.PrintWarning("Warning: Tnp Name still visible: " + tnpName + "\n")
    return names[len(names) - 1].lstrip('?')

def smIsParallel(v1, v2):
    return abs(abs(v1.normalize().dot(v2.normalize())) - 1.0) < smEpsilon

def smIsNormal(v1, v2):
    return abs(v1.dot(v2)) < smEpsilon

def smAddProperty(obj, proptype, name, proptip, defval=None, paramgroup="Parameters", 
                  replacedname = None, readOnly = False, isHiddden = False, attribs = 0):
    """
    Add a property to a given object.

    Args:
    - obj: The object to which the property should be added.
    - proptype: The type of the property (e.g., "App::PropertyLength", "App::PropertyBool").
    - name: The name of the property. Non-translatable.
    - proptip: The tooltip for the property. Need to be translated from outside.
    - defval: The default value for the property (optional).
    - paramgroup: The parameter group to which the property should belong (default is "Parameters").
                  if group name is "Hidden", the property will not be shown in the property editor
    - replacedname: If a property is renamed, for backward compatibility, add the replaced name
                    to the old one so data can be extracted from it in old files
    - readOnly: Property can not be edited
    - isHiddden: Property is not shown in the property editor
    """
    if not hasattr(obj, name):
        if paramgroup == "Hidden":
            isHiddden = True
        obj.addProperty(proptype, name, paramgroup, proptip, attribs, readOnly, isHiddden)
        if defval is not None:
            setattr(obj, name, defval)
        # replaced name is either given or automatically search for 
        #   old lower case version of the same parameter
        if replacedname is None and name[0].isupper():
            replacedname = name[0].lower() + name[1:]
        if replacedname is not None and hasattr(obj, replacedname):
            setattr(obj, name, getattr(obj, replacedname))
            #obj.removeProperty(replacedname)
            obj.setEditorMode(replacedname, 2) # Hide
    


def smAddLengthProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyLength", name, proptip, defval, paramgroup)

def smAddBoolProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyBool", name, proptip, defval, paramgroup)

def smAddDistanceProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyDistance", name, proptip, defval, paramgroup)

def smAddAngleProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyAngle", name, proptip, defval, paramgroup)

def smAddFloatProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyFloat", name, proptip, defval, paramgroup)

def smAddIntProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyInteger", name, proptip, defval, paramgroup)

def smAddStringProperty(obj, name, proptip, defval, paramgroup="Parameters"):
    smAddProperty(obj, "App::PropertyString", name, proptip, defval, paramgroup)


def smAddEnumProperty(
    obj, name, proptip, enumlist, defval=None, paramgroup="Parameters"
):
    if not hasattr(obj, name):
        _tip_ = FreeCAD.Qt.translate("App::Property", proptip)
        obj.addProperty("App::PropertyEnumeration", name, paramgroup, _tip_)
        setattr(obj, name, enumlist)
        if defval is not None:
            setattr(obj, name, defval)

def smGetBodyOfItem(obj):
    if hasattr(obj, "getParent"):
        return obj.getParent()
    elif hasattr(obj, "getParents"): # probably FreeCadLink version
        parent, _ = obj.getParents()[0]
        return parent
    return None

def smGetThickness(obj, foldface):
    normal = foldface.normalAt(0, 0)
    theVol = obj.Volume
    if theVol < 0.0001:
        SMLogger.error(
            FreeCAD.Qt.translate(
                "Logger", "Shape is not a real 3D-object or too small for a metal-sheet!"
            )
        )
        return 0

    # Make a first estimate of the thickness
    estimated_thk = theVol / (foldface.Area)
    #  p1 = foldface.CenterOfMass
    p1 = foldface.Vertexes[0].Point
    p2 = p1 + estimated_thk * -1.5 * normal
    e1 = Part.makeLine(p1, p2)
    thkedge = obj.common(e1)
    thk = thkedge.Length
    return thk

def smGetFaceByEdge(selItem, obj):
    selFace = None
    # find face if Edge Selected
    if type(selItem) == Part.Edge:
        Facelist = obj.ancestorsOfType(selItem, Part.Face)
        if Facelist[0].Area < Facelist[1].Area:
            selFace = Facelist[0]
        else:
            selFace = Facelist[1]
    elif type(selItem) == Part.Face:
        selFace = selItem
    return selFace

def smGetIntersectingFace(Face, obj):
    # find Faces that overlap
    face = None
    for face in obj.Faces:
        face_common = face.common(Face)
        if face_common.Faces:
            break
    return face

def smGetIntersectingEdge(Face, obj):
    # find an Edge that overlap
    edge = None
    for edge in obj.Edges:
        face_common = edge.common(Face)
        if face_common.Edges:
            break
    return edge

def smGetAllIntersectingEdges(Face, obj):
    # find Edges that overlap
    edgelist = []
    for edge in obj.Edges:
        face_common = edge.common(Face)
        if face_common.Edges:
            edgelist.append(edge)
    return edgelist

def smIsEqualAngle(ang1, ang2, p=5):
    # compares two angles with a given precision
    result = False
    if round(ang1 - ang2, p) == 0:
        result = True
    if round((ang1 - 2.0 * math.pi) - ang2, p) == 0:
        result = True
    if round(ang1 - (ang2 - 2.0 * math.pi), p) == 0:
        result = True
    return result


class SMLogger:
    @classmethod
    def error(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        FreeCAD.Console.PrintError(message + "\n")

    @classmethod
    def log(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        FreeCAD.Console.PrintLog(message + "\n")

    @classmethod
    def message(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        FreeCAD.Console.PrintMessage(message + "\n")

    @classmethod
    def warning(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        FreeCAD.Console.PrintWarning(message + "\n")

class UnfoldException(Exception):
    pass

class BendException(Exception):
    pass

class TreeException(Exception):
    pass
