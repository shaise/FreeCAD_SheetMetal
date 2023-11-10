import FreeCAD
from PySide import QtCore, QtGui

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

    @classmethod
    def warningBox(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        QtGui.QMessageBox.warning(None, "Warning", message)
        FreeCAD.Console.PrintWarning(message + "\n")

    @classmethod
    def errorBox(cls, *args):
        message = ""
        for x in args:
            message += str(x)
        QtGui.QMessageBox.warning(None, "Error", message)
        FreeCAD.Console.PrintError(message + "\n")



class UnfoldException(Exception):
    pass

class BendException(Exception):
    pass

class TreeException(Exception):
    pass




