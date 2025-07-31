# -*- coding: utf-8 -*-
###################################################################################
#
#  SheetMetalExtraToolbar.py
#
#  Copyright 2025 by @zokhasan
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
#
###################################################################################

import FreeCAD
from SheetMetalTools import params


def add_extra_toolbar() -> None:
    """Add 'Create sketch' button in Sheet Metal workbench.

    Add a 'Create sketch' button by the way adding information to
    the user.cfg file (like the 'Customize...' tool does).
    Set the 'wasSetupExtraToolbar' parameter in user.cfg file, which will
    allow skipping 'setup_toolbar()' function called  from 'check_setup()'
    the next time FreeCAD is launched.
    """
    toolbar = FreeCAD.ParamGet("User parameter: BaseApp/Workbench/SMWorkbench/Toolbar/SM_Helper")
    toolbar.SetString("Name", "Sheet Metal Helper")          # Name Custom toolbar
    toolbar.SetBool("Active", 1)                             # Activate toolbar
    toolbar.SetString("PartDesign_NewSketch", "PartDesign")  # Add Sketch button(from PartDesign)
    params.SetBool("wasSetupExtraToolbar", True)


def setup_toolbar() -> None:
    """Call add_extra_toolbar() if 'Create sketch' button isn't added.

    Check if 'Create sketch' button is in a user's custom toolbars,
    and if found, set 'wasSetupExtraToolbar' parameter in user.cfg,
    if not, call 'add_extra_toolbar()' function.
    """
    if FreeCAD.ParamGet("User parameter: BaseApp/Workbench/SMWorkbench").HasGroup("Toolbar"):
        sm_toolbar = FreeCAD.ParamGet("User parameter: BaseApp/Workbench/SMWorkbench/Toolbar")
        groups = sm_toolbar.GetGroups()
        sketch_button1 = ('String', 'PartDesign_NewSketch', 'PartDesign')
        sketch_button2 = ('String', 'Sketcher_NewSketch', 'Sketcher')
        has_button = False

        for group in groups:
            contents = sm_toolbar.GetGroup(group).GetContents()
            if sketch_button1 in contents or sketch_button2 in contents:
                has_button = True
                break

        if has_button:
            params.SetBool("wasSetupExtraToolbar", True)
        else:
            add_extra_toolbar()
    else:
        add_extra_toolbar()


def check_setup() -> None:
    if not params.GetBool("wasSetupExtraToolbar", False):  # "False" is default value if param doesn't exist
        setup_toolbar()
