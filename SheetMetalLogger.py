# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalLogger.py
#
#  Copyright 2014, 2018 Ulrich Brammer <ulrich@Pauline>
#  Copyright 2023 Ondsel Inc.
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Library General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU Library General Public
#  License along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
###################################################################################

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



class UnfoldException(Exception):
    pass

class BendException(Exception):
    pass

class TreeException(Exception):
    pass




