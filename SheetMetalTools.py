import FreeCAD, os
from SheetMetalLogger import SMLogger
import re

translate = FreeCAD.Qt.translate

mod_path = os.path.dirname(__file__)
icons_path = os.path.join(mod_path, "Resources", "icons")
panels_path = os.path.join(mod_path, "Resources", "panels")
language_path = os.path.join(mod_path, "translations")
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
smEpsilon = 0.0000001

def isGuiLoaded():
    try:
        return FreeCAD.GuiUp
    except:
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
    
    def smHideObjects(*args):
        from FreeCAD import Gui
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
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.GreedySelection)
            addRemoveButton.setText('Preview')
        else:
            updateSelectionElements(obj, allowedTypes)
            Gui.Selection.clearSelection()
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)
            obj.Document.recompute()
            obj.baseObject[0].Visibility=False
            obj.Visibility=True
            addRemoveButton.setText('Select')
            taskPopulateSelectionList(treeWidget, obj.baseObject)
    
    def taskConnectSelection(addRemoveButton, treeWidget, obj, allowedTypes):
        addRemoveButton.toggled.connect(
            lambda value: _taskToggleSelectionMode(value, addRemoveButton, treeWidget, obj, allowedTypes))

    def _taskUpdateValue(value, obj, objvar, callback):
        setattr(obj, objvar, value)
        obj.Document.recompute()
        if callback is not None:
            callback(value)
    
    def taskConnectSpin(task, formvar, objvar, callback = None):
        formvar.setProperty("value", getattr(task.obj, objvar))
        Gui.ExpressionBinding(formvar).bind(task.obj, objvar)
        formvar.valueChanged.connect(lambda value: _taskUpdateValue(value, task.obj, objvar, callback))

    def taskConnectCheck(task, formvar, objvar, callback = None):
        formvar.setChecked(getattr(task.obj, objvar))
        formvar.toggled.connect(lambda value: _taskUpdateValue(value, task.obj, objvar, callback))

    def taskConnectEnum(task, formvar, objvar, callback = None):
        enumlist = task.obj.getEnumerationsOfProperty(objvar)
        formvar.setProperty("currentIndex", enumlist.index(getattr(task.obj, objvar)))
        formvar.currentIndexChanged.connect(lambda value: _taskUpdateValue(value, task.obj, objvar, callback))

    def taskAccept(task, addRemoveButton):
        if addRemoveButton.isChecked():
            addRemoveButton.AddRemove.toggle()
        FreeCAD.ActiveDocument.recompute()
        task.obj.Document.commitTransaction()
        Gui.Control.closeDialog()
        Gui.ActiveDocument.resetEdit()
        return True

    def taskReject(task, addRemoveButton):
        FreeCAD.ActiveDocument.abortTransaction()
        if addRemoveButton.isChecked():
            Gui.Selection.setSelectionStyle(Gui.Selection.SelectionStyle.NormalSelection)
            task.obj.Visibility = True
        Gui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()
      
    def taskSaveDefaults(obj, defaultDict, varList):
        for var in varList:
            defaultDict[var] = getattr(obj, var)

    def taskRestoreDefaults(obj, defaultDict):
        for var, value in defaultDict.items():
            setattr(obj, var, value)

    def taskLoadUI(*args):
        if len(args) == 1:
            path = os.path.join(panels_path, args[0])
            return Gui.PySideUic.loadUi(path)           
        forms = []
        for uiFile in args:
            path = os.path.join(panels_path, uiFile)
            forms.append(Gui.PySideUic.loadUi(path))
        return forms


else:
    def smWarnDialog(msg):
        SMLogger.warning(msg)

    def smHideObjects(*args):
        pass

def smStripTrailingNumber(item):
    return re.sub(r'\d+$', '', item)

def smBelongToBody(item, body):
    if body is None:
        return False
    for obj in body.Group:
        if obj.Name == item.Name:
            return True
    return False

def smIsPartDesign(obj):
    return str(obj).find("<PartDesign::") == 0

def smIsSketchObject(obj):
    return str(obj).find("<Sketcher::") == 0

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

def GetViewConfig(obj): 
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

def smAddProperty(obj, proptype, name, proptip, defval=None, paramgroup="Parameters"):
    """
    Add a property to a given object.

    Args:
    - obj: The object to which the property should be added.
    - proptype: The type of the property (e.g., "App::PropertyLength", "App::PropertyBool").
    - name: The name of the property. Non-translatable.
    - proptip: The tooltip for the property. Need to be translated from outside.
    - defval: The default value for the property (optional).
    - paramgroup: The parameter group to which the property should belong (default is "Parameters").
    """
    if not hasattr(obj, name):
        obj.addProperty(proptype, name, paramgroup, proptip)
        if defval is not None:
            setattr(obj, name, defval)


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
