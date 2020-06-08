import FreeCAD 

def engineering_mode_enabled():
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/SheetMetal")
    return FSParam.GetInt("EngineeringUXMode", 0) # 0 = disabled, 1 = enabled
