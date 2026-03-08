# ######################################################################
#
#  SheetMetalText.py
# - Text handling for sheet metal sketches, including bend line labels and dimensions.
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
#
# ######################################################################

import math

import FreeCAD
import Part
from FreeCAD import Base, Vector
import SheetMetalTools

smEpsilon = SheetMetalTools.smEpsilon


# Technical font for dimensions and labels. Made from lines and arcs
# Codes:
# s: start point (absolute)
# l: line to (relative)
# q: quarter arc clockwise, with center point (relative)
# h: half arc clockwise, with center point (relative)

smSketchFont = {
    "0": "s0,2 l0,6 q2,0 l2,0 q0,-2 l0,-6 q-2,0 l-2,0 q0,2",
    "1": "s0,10 l5,0 l0,-10 s0,0 l6,0",
    "2": "s0,8 q2,0 l2,0 h0,-2 l-2,0 s6,0 l-6,0 l0,4, q2,0",
    "3": "s0,8 q2,0 l2,0 h0,-2 l-2,0 s4,6 q0,-2 l0,-2 q-2,0 l-2,0 q0,2",
    "4": "s2,10 l-2,-8 l6,0 s4,0 l0,6",
    "5": "s6,10 l-6,0 l0,-4 l4,0 q0,-2 l0,-2 q-2,0 l-4,0",
    "6": "s6,8 q-2,0 l-2,0 q0,-2 l0,-6 q2,0 l2,0 q,2 l0,2 q-2,0 l0,-4",
    "7": "s0,8 l0,2 l6,0 l-4,-10",
    "8": "s2,6 h0,2 l2,0 h0,-2 l0,-2 s4,6 q0,-2 l0,-2 q-2,0 l-2,0 q0,2 l0,2 q2,0",
    "9": "s9,6 l-4,0 h0,2 l2,0 h0,-2 l0,-6 q-2,0 l-2,0 q0,2",
}