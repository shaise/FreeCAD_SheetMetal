########################################################################
#
#  SheetMetalUnfoldCmd.py
#
#  Copyright 2014, 2018 Ulrich Brammer <ulrich@Pauline>
#  Copyright 2023 Ondsel Inc.
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
########################################################################

import os
import sys

import FreeCAD
import Part

import SheetMetalBendCuts
import SheetMetalKfactor
import SheetMetalTools
import SheetMetalUnfolder
from engineering_mode import engineering_mode_enabled

translate = FreeCAD.Qt.translate
SMLogger = SheetMetalTools.SMLogger

if sys.version_info.major == 3 and sys.version_info.minor < 10:
    NewUnfolderAvailable = False
    FreeCAD.Console.PrintWarning(
        translate("SheetMetal",
            "Python version is too old for the new unfolder\n"
            "Reverting to the old one\n"
            )
        )
elif SheetMetalTools.smIsNetworkxAvailable():
    import SheetMetalNewUnfolder
    import networkx as nx

    if not hasattr(nx, "Graph"):
        NewUnfolderAvailable = False
    else:
        from SheetMetalNewUnfolder import BendAllowanceCalculator

        NewUnfolderAvailable = True
else:
    NewUnfolderAvailable = False
    FreeCAD.Console.PrintWarning(
        translate("SheetMetal",
            "Networkx dependency is missing and required for the new Unfolder\n"
            "Try uninstalling SheetMetal, refresh Addon Manager's cache, and reinstall\n"
            )
        )

# IMPORTANT: please remember to change the element map version in case
# of any changes in modeling logic.
smElementMapVersion = "sm1."

# List of properties to be saved as defaults.
smUnfoldDefaultVars = [
    "KFactorStandard",
    "GenerateSketch",
    "SeparateSketchLayers",
    "GenerateBendCuts",
    "BendCutMaxMaterial",
    "BendCutMaxCut",
    "BendCutEdgeOffset",
    "BendCutShapeMode",
]
smUnfoldNonSavedDefaultVars = [
    "UnfoldTransparency",
    "SketchColor",
    "InternalColor",
    "BendLineColor",
    "BendLabelColor",
    "CutSketchColor",
    "ExportType",
]

GENSKETCHCOLOR = "#000080"
OUTLINESKETCHCOLOR = "#c00000"
BENDLINESKETCHCOLOR = "#ff5733"
BENDLABELCOLOR = "#33ff33"
BENDCUTSKETCHCOLOR = "#00c0ff"
KFACTOR = 0.40


###################################################################################################
# Helper functions
###################################################################################################

def smUnfoldExportSketches(obj, useDialog=True):
    if len(obj.UnfoldSketches) == 0:
        return
    sketches = []
    if len(obj.UnfoldSketches) == 1:
        sketchNames = [obj.UnfoldSketches[0]]
    else:
        sketchNames = obj.UnfoldSketches
    for name in sketchNames:
        sketch = obj.Document.getObject(name)
        if sketch is None:
            return
        sketches.append(sketch)
    exptype = obj.Proxy.ExportType
    expname = obj.Label.removesuffix("_Unfold")
    filename = f"{FreeCAD.ActiveDocument.Name}-{expname}.{exptype}"
    SheetMetalTools.smGuiExportSketch(sketches, exptype, filename, useDialog)


###################################################################################################
# Object class
###################################################################################################

class SMUnfold:
    """Class object for the unfold command."""

    def __init__(self, obj, selobj, sel_elements):
        """Add wall or Wall with radius bend."""
        selobj, sel_elements = SheetMetalTools.smUpdateLinks(obj, selobj, sel_elements)
        SheetMetalTools.smAddProperty(obj,
            "App::PropertyLinkSub",
            "baseObject",
            translate("App::Property", "Base Object"),
            (selobj, sel_elements),
        )
        self.addVerifyProperties(obj)
        SheetMetalTools.taskRestoreDefaults(obj, smUnfoldDefaultVars)
        # Setup transient properties.
        self.SketchColor = GENSKETCHCOLOR
        self.InternalColor = OUTLINESKETCHCOLOR
        self.BendLineColor = BENDLINESKETCHCOLOR
        self.BendLabelColor = BENDLABELCOLOR
        self.CutSketchColor = BENDCUTSKETCHCOLOR
        self.UnfoldTransparency = 0
        self.ExportType = "dxf"
        self.visibleSketches = []
        SheetMetalTools.taskRestoreDefaults(self, smUnfoldNonSavedDefaultVars)
        obj.Proxy = self
        self.UnfoldSketches = []

    def addVerifyProperties(self, obj):
        SheetMetalTools.smAddProperty(obj,
            "App::PropertyFloatConstraint",
            "KFactor",
            translate("SheetMetal", "Manual K-Factor value"),
            (0.4, 0.0, 2.0, 0.01),
        )
        SheetMetalTools.smAddEnumProperty(obj,
            "KFactorStandard",
            translate("SheetMetal", "K-Factor standard"),
            ["ansi", "din"],
            "ansi",
        )
        SheetMetalTools.smAddProperty(obj,
            "App::PropertyString",
            "MaterialSheet",
            translate("SheetMetal", "Material definition sheet"),
            "_manual",
            readOnly=True,
        )
        SheetMetalTools.smAddBoolProperty(obj,
            "ManualRecompute",
            translate("SheetMetal", "If set, object recomputation will be done on demand only"),
            False,
        )
        SheetMetalTools.smAddBoolProperty(obj,
            "GenerateSketch",
            translate("SheetMetal", "Generate unfold sketch"),
            False,
        )
        SheetMetalTools.smAddBoolProperty(obj,
            "SeparateSketchLayers",
            translate(
                "SheetMetal",
                "Generate separated unfold sketches for outline, inner lines and bend lines",
            ),
            False,
        )
        SheetMetalTools.smAddProperty(obj,
            "App::PropertyStringList",
            "UnfoldSketches",
            translate("SheetMetal", "Generated sketches"),
            None,
            "Hidden",
            attribs=8,  # Output only - no recompute if changed
        )
        SheetMetalTools.smAddBoolProperty(obj,
            "ShowBendAngles",
            translate("SheetMetal", "Show bend angles on the unfold sketch"),
            True,
        )
        SheetMetalTools.smAddLengthProperty(obj,
                "FontSize",
                translate("App::Property", "Font size for bend angle labels"),
                2.0)
        SheetMetalTools.smAddBoolProperty(obj,
            "GenerateBendCuts",
            translate("SheetMetal",
                "Generate laser bend-relief (hinge) cuts along the bend lines"),
            False,
        )
        SheetMetalTools.smAddLengthProperty(obj,
                "BendCutMaxMaterial",
                translate("SheetMetal",
                    "Maximum length of an uncut material bridge in the relief pattern"),
                8.0)
        SheetMetalTools.smAddLengthProperty(obj,
                "BendCutMaxCut",
                translate("SheetMetal",
                    "Maximum length of a single cut segment in the relief pattern"),
                3.0)
        SheetMetalTools.smAddLengthProperty(obj,
                "BendCutEdgeOffset",
                translate("SheetMetal",
                    "Margin left uncut at each end of the bend line"),
                5.0)
        SheetMetalTools.smAddEnumProperty(obj,
            "BendCutShapeMode",
            translate("SheetMetal", "Relief cut profile source"),
            ["straight", "sketch"],
            "straight",
        )
        SheetMetalTools.smAddProperty(obj,
            "App::PropertyLink",
            "BendCutProfileSketch",
            translate("SheetMetal",
                "Sketch defining a custom relief cut profile (e.g. dogbone, wave, "
                "chevron), tiled along each cut segment. Only used when "
                "'BendCutShapeMode' is 'sketch'"),
            None,
        )
        # SheetMetalTools.smAddProperty(
        #     obj,
        #     "App::PropertyBool",
        #     "DetachFromBody",
        #     translate
        #     ( "SheetMetal", "Make unfolded shape independent of the object's body"),
        #     False
        # )

    def getElementMapVersion(self, _fp, ver, _prop, restored):
        if not restored:
            return smElementMapVersion + ver
        return None

    def onChanged(self, obj, prop):
        if prop == "Visibility":
            isVisible = obj.Visibility
            visibleSketches = obj.Proxy.visibleSketches if isVisible else []
            for sketchName in obj.UnfoldSketches:
                sketch = obj.Document.getObject(sketchName)
                if sketch is not None:
                    if isVisible and sketchName in visibleSketches:
                        sketch.Visibility = True
                    elif not isVisible:
                        if sketch.Visibility:
                            visibleSketches.append(sketchName)
                            sketch.Visibility = False
            if not isVisible:
                obj.Proxy.visibleSketches = visibleSketches

    def getBendCutProfile(self, obj):
        """Return the normalized (tileable) relief profile wire to use for
        bend-relief cuts, or None to use plain straight cuts.

        Never raises: an invalid/missing profile sketch just falls back to
        straight cuts (with a logged warning), so a recompute never fails
        because of a bad selection here.
        """
        if obj.BendCutShapeMode != "sketch":
            return None
        sketch = obj.BendCutProfileSketch
        if sketch is None:
            SMLogger.warning(translate("SheetMetal",
                "Bend relief shape is set to 'From sketch' but no profile "
                "sketch is selected; using straight cuts instead.\n"))
            return None
        valid, msg = SheetMetalBendCuts.validate_profile_sketch(sketch)
        if not valid:
            SMLogger.warning(translate("SheetMetal",
                "Bend relief profile sketch is not usable ({}); using "
                "straight cuts instead.\n").format(msg))
            return None
        return SheetMetalBendCuts.normalize_profile_sketch(sketch)

    def newUnfolder(self, obj, baseObject, baseFace):
        """Use new unfolder system."""
        FreeCAD.Console.PrintMessage("Using V2 unfolding system\n")
        if obj.MaterialSheet in ["_manual", "_none"]:
            bac = BendAllowanceCalculator.from_single_value(obj.KFactor, obj.KFactorStandard)
        else:
            print("Using MDS:", obj.MaterialSheet)
            sheet = FreeCAD.ActiveDocument.getObject(obj.MaterialSheet)
            if sheet is None:
                sheet = FreeCAD.ActiveDocument.getObjectsByLabel(obj.MaterialSheet)[0]
            bac = BendAllowanceCalculator.from_spreadsheet(sheet)
        sel_face, unfolded_shape, bend_lines, root_normal, bend_infodata = SheetMetalNewUnfolder.getUnfold(
            bac, baseObject, baseFace
        )

        sketches = []
        if obj.GenerateSketch and unfolded_shape is not None:
            label_infodata = bend_infodata if obj.ShowBendAngles else []

            # Bend-relief cuts are a pure post-process of `bend_infodata`,
            # computed *before* it gets filtered above for label display
            # purposes - the two are independent switches. This never
            # touches `bend_lines`/`unfolded_shape`/fold geometry itself.
            #
            # IMPORTANT (coordinate frame): `bend_infodata[i].line` lives
            # in the "flattened, origin-aligned" frame that `getUnfold()`
            # aligns everything to internally (call it frame A). The
            # `bend_lines` *parameter* that `getUnfoldSketches()` expects,
            # on the other hand, is `bend_lines` as *returned* by
            # `getUnfold()`, which has already been transformed back into
            # the raw "in-place" frame (frame B) - `getUnfoldSketches()`
            # re-aligns frame B to a (newly, independently recomputed)
            # origin-aligned frame A' via its own `sketch_align_transform`
            # and applies it once, forward, to whatever it's given in
            # that parameter. Frame A and frame A' share the same
            # rotation (both derived from the same root/selected face)
            # but can differ in translation, since they're computed from
            # the bounding boxes of two different shapes (the full
            # unfold's sketch lines vs. just the outer wire re-extracted
            # from `unfolded_shape`).
            #
            # So: geometry already in frame A (like our relief cuts, or
            # like `bend_labels` below) must *not* be hop through another
            # forward transform meant for frame-B data, or it gets
            # transformed twice. `getUnfoldSketches()` itself sidesteps
            # this for bend labels by pre-applying the *inverse* of its
            # transform before merging them in, so the later forward pass
            # cancels back out. We do the same for the merged-sketch
            # substitution below.
            bend_lines_for_sketch = bend_lines
            extra_cut_layer_edges = None
            if obj.GenerateBendCuts and bend_infodata:
                profile = self.getBendCutProfile(obj)
                cut_compound, fallback_edges = SheetMetalBendCuts.build_relief_cuts(
                    bend_infodata,
                    obj.BendCutMaxCut.Value,
                    obj.BendCutMaxMaterial.Value,
                    obj.BendCutEdgeOffset.Value,
                    profile,
                )
                if fallback_edges:
                    # Bends too short for the requested pattern keep their
                    # plain solid bend line instead of being dropped.
                    cut_compound = Part.makeCompound([cut_compound, Part.makeCompound(fallback_edges)])

                if SheetMetalBendCuts.DEBUG:
                    FreeCAD.Console.PrintMessage(
                        f"[BendCuts] bend_infodata: {len(bend_infodata)} bend(s), "
                        f"lengths={[round(bi.line.Length, 3) for bi in bend_infodata]}\n")
                    FreeCAD.Console.PrintMessage(
                        f"[BendCuts] cut_compound (frame A, pre-fix) BoundBox={cut_compound.BoundBox}\n")

                if obj.SeparateSketchLayers:
                    # Keep the existing dashed "_Sketch_Bends" layer as-is
                    # and add the cut pattern as its own extra layer, built
                    # directly (bypassing getUnfoldSketches' internal
                    # merge/transform), exactly like the existing
                    # "_Sketch_Bend_Labels" layer already does with its
                    # own frame-A `bend_labels` data - no extra transform
                    # needed here.
                    extra_cut_layer_edges = cut_compound
                else:
                    # Single merged sketch: substitute the real cut
                    # geometry for the plain bend line so the exported
                    # sketch shows actual segmented cuts, not a solid
                    # line on top of them. `bend_lines_for_sketch` is
                    # about to receive one forward alignment transform
                    # from `getUnfoldSketches()` (meant for frame-B data),
                    # so pre-cancel it here since our data is already in
                    # frame A - mirrors how `bend_labels_transformed` is
                    # built inside `getUnfoldSketches()`.
                    cut_sketch_profile, _cut_inner, _cut_holes = SheetMetalNewUnfolder.SketchExtraction.extract_manually(
                        unfolded_shape, root_normal)
                    merge_align_transform = SheetMetalNewUnfolder.SketchExtraction.move_to_origin(
                        cut_sketch_profile, sel_face)
                    bend_lines_for_sketch = cut_compound.transformed(merge_align_transform.inverse())

                    if SheetMetalBendCuts.DEBUG:
                        FreeCAD.Console.PrintMessage(
                            f"[BendCuts] merge_align_transform (T)={merge_align_transform}\n")
                        FreeCAD.Console.PrintMessage(
                            f"[BendCuts] bend_lines (frame B, unmodified) BoundBox={bend_lines.BoundBox}\n")
                        FreeCAD.Console.PrintMessage(
                            f"[BendCuts] cut_compound after T^-1 correction BoundBox="
                            f"{bend_lines_for_sketch.BoundBox}\n")

            sketches = SheetMetalNewUnfolder.getUnfoldSketches(
                obj.Label,
                sel_face,
                unfolded_shape, 
                bend_lines_for_sketch,
                root_normal, 
                obj.UnfoldSketches,
                obj.SeparateSketchLayers,
                obj.Proxy.SketchColor,
                obj.Proxy.BendLineColor,
                obj.Proxy.InternalColor,
                bend_infodata=label_infodata,
                bend_label_color=obj.Proxy.BendLabelColor,
                bend_label_size=obj.FontSize,
            )
            if extra_cut_layer_edges is not None and extra_cut_layer_edges.Edges:
                cut_sketch = SheetMetalNewUnfolder.SketchExtraction.edges_to_sketch_object(
                    extra_cut_layer_edges.Edges,
                    f"{obj.Label}_Sketch_BendCuts",
                    obj.UnfoldSketches,
                    obj.Proxy.CutSketchColor,
                )
                sketches.append(cut_sketch)
        return unfolded_shape, sketches

    def oldUnfolder(self, obj, baseObject, baseFace):
        """Use old unfolder system.

        Note: Bend-relief cuts (`GenerateBendCuts`) are only supported
        through the new unfolder, which is the only one that provides
        per-bend `BendInfo` data. The task panel disables the bend-cuts
        controls when the old unfolder is active.
        """
        FreeCAD.Console.PrintMessage("Using V1 unfolding system\n")
        kFactorTable = {1: obj.KFactor}
        if obj.MaterialSheet != "_manual" and obj.MaterialSheet != "_none":
            lookupTable = SheetMetalKfactor.KFactorLookupTable(obj.MaterialSheet)
            kFactorTable = lookupTable.k_factor_lookup

        shape, foldComp, norm, _thename, _err_cd, _fSel, _obN = SheetMetalUnfolder.getUnfold(
                kFactorTable, baseObject, baseFace, obj.KFactorStandard)

        sketches = []
        if obj.GenerateSketch and shape is not None:
            sketches = SheetMetalUnfolder.getUnfoldSketches(
                obj.Label,
                shape,
                foldComp.Edges,
                norm,
                obj.UnfoldSketches,
                obj.SeparateSketchLayers,
                obj.Proxy.SketchColor,
                bendSketchColor=obj.Proxy.BendLineColor,
                internalSketchColor=obj.Proxy.InternalColor,
            )
        return shape, sketches

    def execute(self, fp):
        """Print a short message when doing a recomputation.

        Note:
            This method is mandatory.

        """
        self.addVerifyProperties(fp)
        baseObj, baseFace = SheetMetalTools.smGetSubElementName(fp.baseObject[1][0])
        if baseObj is None:
            baseObj = fp.baseObject[0]
        if not NewUnfolderAvailable or SheetMetalTools.use_old_unfolder():
            shape, sketches = self.oldUnfolder(fp, baseObj, baseFace)
        else:
            shape, sketches = self.newUnfolder(fp, baseObj, baseFace)

        fp.Shape = shape
        parent = SheetMetalTools.smGetParentBody(fp)
        sketchList = []
        for sketch in sketches:
            if sketch is not None:
                sketchList.append(sketch.Name)
                if parent is not None and SheetMetalTools.smGetParentBody(sketch) is None:
                    parent.addObject(sketch)

        # Remove non-used sketches.
        for prop in fp.UnfoldSketches:
            if not prop in sketchList:
                item = fp.Document.getObject(prop)
                if item is not None:
                    fp.Document.removeObject(item.Name)

        fp.UnfoldSketches = sketchList
        SheetMetalTools.smRemoveFromRecompute(fp)


###################################################################################################
# Gui code
###################################################################################################

if SheetMetalTools.isGuiLoaded():

    from PySide import QtGui, QtCore

    Gui = FreeCAD.Gui

    mds_help_url = "https://github.com/shaise/FreeCAD_SheetMetal#material-definition-sheet"
    last_selected_mds = "none"


    ###############################################################################################
    # View Provider
    ###############################################################################################

    class SMUnfoldViewProvider(SheetMetalTools.SMViewProvider):
        """Part / Part WB style ViewProvider."""

        def getIcon(self):
            return os.path.join(SheetMetalTools.icons_path, "SheetMetal_Unfold.svg")

        def claimChildren(self):
            objs = []
            for itemName in self.Object.UnfoldSketches:
                item = self.Object.Document.getObject(itemName)
                if item is not None:
                    objs.append(item)
            return objs

        def getTaskPanel(self, obj):
            return SMUnfoldTaskPanel(obj)


    ###############################################################################################
    # Task Panel
    ###############################################################################################

    class SMUnfoldTaskPanel:
        """Task Panel for the unfold function."""

        def __init__(self, obj):
            QtCore.QDir.addSearchPath("Icons", SheetMetalTools.icons_path)
            self.obj = obj
            self.form = SheetMetalTools.taskLoadUI("UnfoldOptions.ui")

            # Make sure all properties are added.
            obj.Proxy.addVerifyProperties(obj)

            self.setupUi(obj)

        def _boolToState(self, bool):
            return QtCore.Qt.Checked if bool else QtCore.Qt.Unchecked

        def _isManualKSelected(self):
            return self.form.availableMds.currentIndex() == (self.form.availableMds.count() - 1)

        def _isNoMdsSelected(self):
            return self.form.availableMds.currentIndex() == 0

        def _updateSelectedMds(self):
            count = self.form.availableMds.count()
            currentIndex = self.form.availableMds.currentIndex()
            if currentIndex == 0:
                newsheet = "_none"
            elif currentIndex == count - 1:
                newsheet = "_manual"
            else:
                newsheet = self.form.availableMds.currentText()
            if newsheet != self.obj.MaterialSheet:
                self.obj.MaterialSheet = newsheet
                self.recomputeObject()

        def _getLastSelectedMdsIndex(self):
            materialSheet = self.obj.MaterialSheet
            if materialSheet == "_none":
                return 0
            elif materialSheet == "_manual":
                return self.form.availableMds.count() - 1
            for i in range(self.form.availableMds.count()):
                if self.form.availableMds.itemText(i) == materialSheet:
                    return i
            return -1

        def checkKFactorValid(self):
            if self.obj.MaterialSheet == "_none":
                msg = translate("Logger",
                                "Unfold operation needs to know K-factor value(s) to be used.")
                SMLogger.warning(msg)
                msg += translate(
                    "QMessageBox",
                    "<ol>\n"
                    "<li>Either select 'Manual K-factor'</li>\n"
                    "<li>Or use a <a href='{}'>Material Definition Sheet</a></li>\n"
                    "</ol>",
                ).format(mds_help_url)
                SheetMetalTools.smWarnDialog(msg)
                return False
            return True

        def setupUi(self, obj):
            self.updateKFactor(True)
            if obj.Proxy.ExportType == "dxf":
                self.form.dxfExport.setChecked(True)
            else:
                self.form.svgExport.setChecked(True)
            self.SketchColor = GENSKETCHCOLOR
            self.InternalColor = OUTLINESKETCHCOLOR
            self.BendLineColor = BENDLINESKETCHCOLOR
            self.BendLabelColor = BENDLABELCOLOR
            self.CutSketchColor = BENDCUTSKETCHCOLOR
            # Bend-relief cuts need per-bend BendInfo data, only available
            # through the new unfolder. Computed early: `chkSketchChange`
            # (invoked below as a side effect of `taskConnectCheck`)
            # depends on it.
            self.bendCutsAvailable = NewUnfolderAvailable and not SheetMetalTools.use_old_unfolder()
            self.populateMdsList()
            SheetMetalTools.taskConnectSelectionSingle(self.form.pushFace, self.form.txtFace, obj,
                                                       "baseObject", ["Face"])
            SheetMetalTools.taskConnectColor(obj.Proxy, self.form.genColor, "SketchColor")
            SheetMetalTools.taskConnectColor(obj.Proxy, self.form.bendColor, "BendLineColor")
            SheetMetalTools.taskConnectColor(obj.Proxy, self.form.internalColor, "InternalColor")
            SheetMetalTools.taskConnectColor(obj.Proxy, self.form.bendLabelColor, "BendLabelColor")
            SheetMetalTools.taskConnectColor(obj.Proxy, self.form.cutColor, "CutSketchColor")
            SheetMetalTools.taskConnectCheck(obj, self.form.chkSketch, "GenerateSketch",
                                             self.chkSketchChange)
            SheetMetalTools.taskConnectCheck(obj, self.form.chkSeparate, "SeparateSketchLayers",
                                             self.chkSketchChange)
            SheetMetalTools.taskConnectCheck(obj, self.form.chkAngleLabels, "ShowBendAngles",
                                             self.chkSketchChange)
            SheetMetalTools.taskConnectCheck(obj, self.form.chkBendCuts, "GenerateBendCuts",
                                             self.chkBendCutsChange)
            SheetMetalTools.taskConnectSpin(obj, self.form.maxMaterialDist, "BendCutMaxMaterial")
            SheetMetalTools.taskConnectSpin(obj, self.form.maxCutDist, "BendCutMaxCut")
            SheetMetalTools.taskConnectSpin(obj, self.form.cutEdgeOffset, "BendCutEdgeOffset")
            SheetMetalTools.taskConnectSelectionSingle(self.form.pushCutSketch,
                                                       self.form.txtCutSketch, obj,
                                                       "BendCutProfileSketch",
                                                       ("Sketcher::SketchObject", []))
            SheetMetalTools.taskConnectCheck(obj, self.form.chkManualUpdate, "ManualRecompute",
                                             self.chkManualChanged)
            SheetMetalTools.taskConnectCheck(obj, self.form.chkManualUpdate, "ManualRecompute",
                                             self.chkManualChanged)
            SheetMetalTools.taskConnectSpin(obj, self.form.floatKFactor, "KFactor")
            SheetMetalTools.taskConnectSpin(obj.Proxy, self.form.transSpin, "UnfoldTransparency",
                                            bindFunction=False)
            SheetMetalTools.taskConnectSpin(obj, self.form.fontSize, "FontSize")
            self.form.pushUnfold.clicked.connect(self.unfoldPressed)
            self.form.pushExport.clicked.connect(self.doExport)
            self.form.availableMds.currentIndexChanged.connect(self.availableMdsChacnge)
            self.form.dxfExport.toggled.connect(self.exportTypeChanged)
            self.form.kfactorAnsi.toggled.connect(self.kfactorStdChanged)
            self.form.radioSketchCut.toggled.connect(self.cutShapeChanged)

            if obj.BendCutShapeMode == "sketch":
                self.form.radioSketchCut.setChecked(True)
            else:
                self.form.radioStraightCut.setChecked(True)

            if not self.bendCutsAvailable:
                self.form.chkBendCuts.setChecked(False)
                self.form.chkBendCuts.setToolTip(translate("SheetMetal",
                    "Bend relief cuts require the new unfolder (networkx), "
                    "which is not currently active."))

            self.availableMdsChacnge()
            self.chkSketchChange()
            # self.form.update()

        def updateKFactor(self, updateCheck):
            if self.obj.KFactorStandard == "ansi":
                if updateCheck:
                    self.form.kfactorAnsi.setChecked(True)
                self.form.floatKFactor.setProperty("value", self.obj.KFactor)
                self.form.floatKFactor.setProperty("maximum", 1.0)
            else:
                if updateCheck:
                    self.form.kfactorDin.setChecked(True)
                self.form.floatKFactor.setProperty("maximum", 2.0)
                self.form.floatKFactor.setProperty("value", self.obj.KFactor)

        def kfactorStdChanged(self):
            if self.form.kfactorAnsi.isChecked():
                self.obj.KFactorStandard = "ansi"
                self.obj.KFactor /= 2.0
            else:
                self.obj.KFactorStandard = "din"
                self.obj.KFactor *= 2.0
            self.updateKFactor(False)

        def recomputeObject(self, closeTask=False):
            SheetMetalTools.smForceRecompute = True
            if closeTask:
                SheetMetalTools.taskAccept(self)
            else:
                FreeCAD.ActiveDocument.recompute()
            SheetMetalTools.smForceRecompute = False
            # if len(self.obj.UnfoldSketches) > 0:
            #     FreeCAD.ActiveDocument.recompute()

        def checkBendCutsValid(self):
            if not (self.form.chkBendCuts.isChecked() and self.form.chkBendCuts.isEnabled()):
                return True
            if self.form.radioStraightCut.isChecked():
                return True
            sketch = self.obj.BendCutProfileSketch
            if sketch is None:
                SheetMetalTools.smWarnDialog(translate("SheetMetal",
                    "Bend relief shape is set to 'From sketch'.\n"
                    "Please select a profile sketch, or switch back to 'Straight'."))
                return False
            valid, msg = SheetMetalBendCuts.validate_profile_sketch(sketch)
            if not valid:
                SheetMetalTools.smWarnDialog(translate("SheetMetal",
                    "The selected bend relief profile sketch is not usable:\n{}"
                ).format(msg))
                return False
            return True

        def accept(self):
            if not self.checkKFactorValid():
                return False
            if not self.checkBendCutsValid():
                return False
            self.recomputeObject(True)
            self.obj.ViewObject.Transparency = self.obj.Proxy.UnfoldTransparency
            SheetMetalTools.taskSaveDefaults(self.obj, smUnfoldDefaultVars)
            SheetMetalTools.taskSaveDefaults(self.obj.Proxy, smUnfoldNonSavedDefaultVars)
            # self._updateSelectedMds()
            # kFactorTable = self.getKFactorTable()
            return None

        def reject(self):
            FreeCAD.ActiveDocument.abortTransaction()
            Gui.Control.closeDialog()
            FreeCAD.ActiveDocument.recompute()

        def doExport(self):
            smUnfoldExportSketches(self.obj)

        def populateMdsList(self):
            sheetnames = SheetMetalKfactor.getSpreadSheetNames()
            self.form.availableMds.clear()

            self.form.availableMds.addItem(translate("SheetMetal", "Please select"))
            for mds in sheetnames:
                if mds.Label.startswith("material_"):
                    self.form.availableMds.addItem(mds.Label)
            self.form.availableMds.addItem(translate("SheetMetal", "Manual K-Factor"))

            selMdsIndex = self._getLastSelectedMdsIndex()
            if selMdsIndex > 0:
                self.form.availableMds.setCurrentIndex(selMdsIndex)
            elif len(sheetnames) == 1:
                self.form.availableMds.setCurrentIndex(1)
            elif engineering_mode_enabled() or len(sheetnames) > 1:
                self.form.availableMds.setCurrentIndex(0)
            else:
                self.form.availableMds.setCurrentIndex(1)

        def chkSketchChange(self, _value=None):
            genSketch = self.form.chkSketch.isChecked()
            self.form.chkSeparate.setEnabled(genSketch)
            self.form.genColor.setEnabled(genSketch)
            splitSketch = genSketch and self.form.chkSeparate.isChecked()
            self.form.bendColor.setEnabled(splitSketch)
            self.form.internalColor.setEnabled(splitSketch)
            unfoldUpdated = not self.obj in SheetMetalTools.smObjectsToRecompute
            exportEnabled = genSketch and len(self.obj.UnfoldSketches) > 0 and unfoldUpdated
            self.form.groupExport.setEnabled(exportEnabled)
            # Bend cuts only make sense when a sketch is actually being
            # generated at all - the whole sub-panel collapses with it.
            # (self.bendCutsAvailable is False when the old unfolder is
            # active; bend cuts stay disabled regardless of genSketch.)
            self.form.chkBendCuts.setEnabled(genSketch and self.bendCutsAvailable)
            self.chkBendCutsChange()

        def chkBendCutsChange(self, _value=None):
            genCuts = self.form.chkBendCuts.isChecked() and self.form.chkBendCuts.isEnabled()
            self.form.groupBendCutsBody.setEnabled(genCuts)
            useSketch = genCuts and self.form.radioSketchCut.isChecked()
            self.form.groupCutShape.setVisible(useSketch)

        def cutShapeChanged(self, _value=None):
            self.obj.BendCutShapeMode = "sketch" if self.form.radioSketchCut.isChecked() else "straight"
            self.chkBendCutsChange()

        def exportTypeChanged(self):
            self.obj.Proxy.ExportType = "dxf" if self.form.dxfExport.isChecked() else "svg"

        def chkManualChanged(self, value):
            self.form.pushUnfold.setEnabled(value)

        def unfoldPressed(self):
            if not self.checkKFactorValid():
                return False
            if not self.checkBendCutsValid():
                return False
            self.recomputeObject()
            self.chkSketchChange()
            return None

        def availableMdsChacnge(self):
            self.form.groupManualFactor.setEnabled(self._isManualKSelected())
            self._updateSelectedMds()
            #self.form.kFactSpin.setEnabled(isManualK)


    ###############################################################################################
    # Commands
    ###############################################################################################

    class SMUnfoldCommandClass:
        """Unfold object."""

        def GetResources(self):
            __dir__ = os.path.dirname(__file__)
            iconPath = os.path.join(__dir__, "Resources", "icons")
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(iconPath, "SheetMetal_Unfold.svg"),
                    "MenuText": translate("SheetMetal", "Unfold"),
                    "Accel": "U",
                    "ToolTip": translate(
                        "SheetMetal",
                        "Flatten folded sheet metal object.\n"
                        "1. Select flat face on sheetmetal shape.\n"
                        "2. Change parameters from task Panel to create "
                        "unfold Shape & Flatten drawing.",
                        ),
                    }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            selparent = SheetMetalTools.smGetParentBody(selobj)
            name = "Unfold" if selparent is None else f"{selparent.Name}_Unfold"
            label = "Unfold" if selparent is None else f"{selparent.Label}_Unfold"
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, name, False)
            if newObj is None:
                return
            newObj.Label = label
            SMUnfold(newObj, selobj, sel.SubElementNames)
            SMUnfoldViewProvider(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, newObj, activeBody, SMUnfoldTaskPanel)

        def IsActive(self):
            if (len(Gui.Selection.getSelection()) != 1
                    or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
            ):
                return False
            selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
            return isinstance(selFace.Surface, Part.Plane)


    class SMRecomputeUnfoldsCommandClass:
        """Recompute all unfold objects marked for manual recompute."""

        def GetResources(self):
            __dir__ = os.path.dirname(__file__)
            iconPath = os.path.join(__dir__, "Resources", "icons")
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(iconPath, "SheetMetal_UnfoldUpdate.svg"),
                    "MenuText": translate("SheetMetal", "Unfold Update"),
                    "Accel": "UU",
                    "ToolTip": translate(
                        "SheetMetal",
                        "Update all unfold objects.\n"
                        ),
                    }

        def Activated(self):
            SheetMetalTools.smForceRecompute = True
            for obj in list(SheetMetalTools.smObjectsToRecompute):
                obj.touch()
            FreeCAD.ActiveDocument.recompute()
            SheetMetalTools.smForceRecompute = False

        def IsActive(self):
            return len(SheetMetalTools.smObjectsToRecompute) > 0


    class SMUnfoldUnattendedCommandClass:
        """Unfold object."""

        def GetResources(self):
            __dir__ = os.path.dirname(__file__)
            iconPath = os.path.join(__dir__, "Resources", "icons")
            return {
                    # The name of a svg file available in the resources.
                    "Pixmap": os.path.join(iconPath, "SheetMetal_UnfoldUnattended.svg"),
                    "MenuText": translate("SheetMetal", "Unattended Unfold"),
                    "Accel": "U",
                    "ToolTip": translate(
                        "SheetMetal",
                        "Flatten folded sheet metal object with default options\n"
                        "1. Select flat face on sheetmetal shape.\n"
                        "2. Click this command to unfold the object with last used parameters.",
                        ),
                    }

        def Activated(self):
            sel = Gui.Selection.getSelectionEx()[0]
            selobj = sel.Object
            selparent = SheetMetalTools.smGetParentBody(selobj)
            name = "Unfold" if selparent is None else f"{selparent.Name}_Unfold"
            label = "Unfold" if selparent is None else f"{selparent.Label}_Unfold"
            newObj, activeBody = SheetMetalTools.smCreateNewObject(selobj, name, False)
            if newObj is None:
                return
            newObj.Label = label
            SMUnfold(newObj, selobj, sel.SubElementNames)
            SMUnfoldViewProvider(newObj.ViewObject)
            SheetMetalTools.smAddNewObject(selobj, newObj, activeBody)
            selobj.Visibility = True
            return

        def IsActive(self):
            if (len(Gui.Selection.getSelection()) != 1
                    or len(Gui.Selection.getSelectionEx()[0].SubElementNames) != 1
            ):
                return False
            selFace = Gui.Selection.getSelectionEx()[0].SubObjects[0]
            return isinstance(selFace.Surface, Part.Plane)


    Gui.addCommand("SheetMetal_UnattendedUnfold", SMUnfoldUnattendedCommandClass())
    Gui.addCommand("SheetMetal_Unfold", SMUnfoldCommandClass())
    Gui.addCommand("SheetMetal_UnfoldUpdate", SMRecomputeUnfoldsCommandClass())
