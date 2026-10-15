"""Run with FreeCAD's Test framework, or unittest in the FreeCAD console."""
import unittest
from unittest.mock import patch

import FreeCAD
import Part

from SheetMetalBendCuts import BareEdgeBendInfo, build_relief_cuts, build_wave_cuts


class TestBendCuts(unittest.TestCase):
    def test_wave_contours(self):
        edge = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(100, 0, 0))
        cuts = build_wave_cuts(edge, 10, 1, 5, 0.6, 1)
        self.assertTrue(cuts.isValid())
        self.assertEqual(len(cuts.Wires), 9)
        for i, wire in enumerate(cuts.Wires):
            self.assertTrue(wire.isClosed())
            self.assertTrue(Part.Face(wire).isValid())
            self.assertAlmostEqual(wire.BoundBox.XLength, 10)
            self.assertAlmostEqual(wire.BoundBox.YLength, 1.6)
            self.assertGreater(wire.CenterOfMass.y * (-1 if i % 2 else 1), 0)
            self.assertEqual({e.Curve.TypeId for e in wire.Edges},
                             {"Part::GeomLine", "Part::GeomCircle"})
            if i:
                self.assertAlmostEqual(wire.distToShape(cuts.Wires[i - 1])[0], 1)
        self.assertGreaterEqual(cuts.BoundBox.XMin, 5)
        self.assertLessEqual(cuts.BoundBox.XMax, 95)

        # Placement must follow the bend, including reversed and diagonal lines.
        placed = edge.copy()
        placed.rotate(FreeCAD.Vector(), FreeCAD.Vector(0, 0, 1), 137)
        placed.translate(FreeCAD.Vector(20, 30, 0))
        expected = cuts.copy()
        expected.rotate(FreeCAD.Vector(), FreeCAD.Vector(0, 0, 1), 137)
        expected.translate(FreeCAD.Vector(20, 30, 0))
        actual = build_wave_cuts(placed, 10, 1, 5, 0.6, 1)
        self.assertAlmostEqual(actual.common(expected).Length, expected.Length, places=5)

        for gap, depth, bridge in ((.6, 1, 1), (1.2, 2, 2), (.3, .5, .5), (.6, 1, 5)):
            cuts = build_wave_cuts(edge, 6 * depth, bridge, depth, gap, depth)
            for a, b in zip(cuts.Wires, cuts.Wires[1:]):
                self.assertAlmostEqual(a.distToShape(b)[0], bridge)

    def test_defaults_from_thickness(self):
        from SheetMetalUnfoldCmd import SMUnfold

        doc = FreeCAD.newDocument("WaveDefaults")
        try:
            plate = doc.addObject("Part::Feature", "Plate")
            obj = doc.addObject("PartDesign::FeaturePython", "Unfold")
            plate.Shape = Part.makeBox(20, 40, 2)
            face = next("Face" + str(i + 1) for i, f in enumerate(plate.Shape.Faces)
                        if f.normalAt(0, 0).z > .99)
            SMUnfold(obj, plate, [face])
            initial = {"BendCutMaxCut": 3, "BendCutMaxMaterial": 8,
                       "BendCutEdgeOffset": 5, "BendCutWaveGap": .6, "BendCutWaveDepth": 1}
            for thickness in (.5, 1, 2):
                plate.Shape = Part.makeBox(20, 40, thickness)
                for name, value in initial.items():
                    setattr(obj, name, value)
                obj.Proxy.applyWaveDefaults(obj)
                for name, factor in zip(initial, (6, 1, 1, .6, 1)):
                    self.assertAlmostEqual(getattr(obj, name).Value, factor * thickness)

            for name, value in initial.items():
                setattr(obj, name, value)
            obj.BendCutMaxMaterial = 4  # Preserve a custom value independently.
            obj.setExpression("BendCutWaveGap", "0.6 mm")  # Even if equal to the default.
            obj.Proxy.applyWaveDefaults(obj)
            self.assertEqual(obj.BendCutMaxMaterial.Value, 4)
            self.assertEqual(obj.BendCutWaveGap.Value, .6)
            self.assertEqual(obj.BendCutMaxCut.Value, 12)
        finally:
            FreeCAD.closeDocument(doc.Name)

    def test_short_bends_and_invalid_sizes(self):
        short = BareEdgeBendInfo(Part.makeLine(FreeCAD.Vector(), FreeCAD.Vector(12, 0, 0)))
        cuts, fallback = build_relief_cuts([short], 10, 1, 5, wave_gap=0.6, wave_depth=1)
        self.assertEqual(len(cuts.Edges), 0)
        self.assertEqual(fallback, [])  # Never export a full bend line as a cut.
        for sizes in ((2, 1, 0, .6, 1), (10, 0, 0, .6, 1),
                      (10, 1, -1, .6, 1), (10, 1, 0, 0, 1)):
            with self.assertRaises(ValueError):
                build_wave_cuts(short.line, *sizes)

    def test_existing_modes(self):
        bend = BareEdgeBendInfo(Part.makeLine(FreeCAD.Vector(), FreeCAD.Vector(100, 0, 0)))
        straight, fallback = build_relief_cuts([bend], 10, 8, 5)
        self.assertTrue(straight.Edges)
        self.assertFalse(fallback)
        self.assertEqual({e.Curve.TypeId for e in straight.Edges}, {"Part::GeomLine"})
        sketch, _ = build_relief_cuts([bend], 10, 8, 5,
                                    [FreeCAD.Vector(), FreeCAD.Vector(1, 0, 0)])
        self.assertAlmostEqual(straight.common(sketch).Length, straight.Length)

    def test_export_after_edit_in_body(self):
        import SheetMetalTools
        from SheetMetalUnfoldCmd import SMUnfold, smUnfoldExportSketches

        doc = FreeCAD.newDocument("WaveExportRegression")
        try:
            body = doc.addObject("PartDesign::Body", "Body")
            fold = body.newObject("PartDesign::Feature", "Fold")
            # A 20 mm long, 90-degree bend, thickness 1 mm and inside radius 2 mm.
            bend = Part.makeCylinder(3, 20).cut(Part.makeCylinder(2, 20))
            bend = bend.common(Part.makeBox(3, 3, 20))
            fold.Shape = bend.multiFuse([
                Part.makeBox(1, 30, 20, FreeCAD.Vector(2, -30, 0)),
                Part.makeBox(30, 1, 20, FreeCAD.Vector(-30, 2, 0)),
            ])
            face = next("Face" + str(i + 1) for i, f in enumerate(fold.Shape.Faces)
                        if f.Surface.TypeId == "Part::GeomPlane"
                        and f.normalAt(0, 0).x > .99 and f.Area > 100)
            obj = body.newObject("PartDesign::FeaturePython", "Unfold")
            SMUnfold(obj, fold, [face])
            obj.MaterialSheet = "_manual"
            obj.GenerateSketch = True
            obj.GenerateBendCuts = True
            obj.BendCutShapeMode = "wave"
            obj.BendCutMaxCut = 6
            obj.BendCutMaxMaterial = 1
            obj.BendCutEdgeOffset = 1
            obj.BendCutWaveGap = .6
            obj.BendCutWaveDepth = 1
            obj.SeparateSketchLayers = False
            doc.recompute()
            self.assertNotIn("Invalid", obj.State)

            with patch.object(SheetMetalTools, "smGuiExportSketch", create=True) as export:
                # This is the same object-only recompute used by the task panel.
                obj.BendCutWaveGap = .7
                obj.recompute()
                self.assertIn("Touched", obj.State)
                smUnfoldExportSketches(obj, False)
                export.assert_called_once()
                self.assertNotIn("Touched", obj.State)
                sketch = export.call_args.args[0][0]
                self.assertEqual(len(sketch.Shape.Wires), 4)  # Outline + three waves.
                self.assertTrue(all(w.isClosed() for w in sketch.Shape.Wires))

                export.reset_mock()
                obj.BendCutWaveGap = 0
                smUnfoldExportSketches(obj, False)
                self.assertIn("Invalid", obj.State)
                export.assert_not_called()
        finally:
            FreeCAD.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()
