import FreeCAD, os
from SheetMetalLogger import SMLogger

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
    def smWarnDialog(msg):
        diag = QtGui.QMessageBox(
            QtGui.QMessageBox.Warning,
            FreeCAD.Qt.translate("QMessageBox", "Error in macro MessageBox"),
            msg,
        )
        diag.setWindowModality(QtCore.Qt.ApplicationModal)
        diag.exec_()
    
    def HideObjects(*args):
        from FreeCAD import Gui
        for arg in args:
            if arg:
                obj = Gui.ActiveDocument.getObject(arg.Name)
                if obj:
                    obj.Visibility = False

else:
    def smWarnDialog(msg):
        SMLogger.warning(msg)

    def HideObjects(*args):
        pass

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
