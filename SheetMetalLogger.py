import FreeCAD

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




