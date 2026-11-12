# Testing SheetMetal

The tests run headless in `FreeCADCmd` and need no GUI.

## Running

With the flatpak FreeCAD, which loads the workbench from its `Mod`
directory:

```
flatpak run --command=FreeCADCmd org.freecad.FreeCAD -t TestSheetMetal
flatpak run --command=FreeCADCmd org.freecad.FreeCAD -t SMTests.testFeatures
flatpak run --command=FreeCADCmd org.freecad.FreeCAD -t SMTests.testFeatures.TestFeatureGeometry.test_Wall_Corner
```

With any other install, use its `FreeCADCmd` (`freecadcmd`, or
`FreeCAD.AppImage freecadcmd`) the same way. The whole suite takes about
20 seconds. The flatpak cannot read the host's `/tmp`; scripts you pass to
it must live under `~/.var/app/org.freecad.FreeCAD/`.

## What is tested

| module | what it checks |
|--------|----------------|
| `SMTests/testFeatures.py` | every feature and its main options recompute into one valid solid with the recorded volume, area, element counts and bound box; exact volumes where they are easy to derive |
| `SMTests/testUnfoldAccuracy.py` | flat pattern length of both unfolders against flats + bend allowance, for K-factors, ANSI/DIN, radii, angles, bend types, downward bends, a U profile and a material spreadsheet; the K-factor lookups |
| `SMTests/testPersistence.py` | all features survive save, reload and a full recompute (proxy, links, geometry); topological names are saved |
| `SMTests/testTNP.py` | topological naming, see [TNP.md](TNP.md) |
| `SMTests/testBendCuts.py`, `testFolder.py`, `testKfactor.py` | bend relief cuts, cylinder unrolling, K-factor spreadsheets |

`TestSheetMetal.py` imports the test classes; add new ones there.
Shared builders (the 100 x 50 x 2 plate, walls, element lookups) are in
`SMTests/helpers.py`.

## Reference geometry

`SMTests/data/featureGeometry.json` holds the values the feature tests
compare against. They were recorded from the code, so a failure means the
geometry changed, not necessarily that it is wrong. After an intended
change, regenerate and review the diff:

```
flatpak run --env=SM_UPDATE_GOLDEN=1 --command=FreeCADCmd \
    org.freecad.FreeCAD -t SMTests.testFeatures
git diff SMTests/data/featureGeometry.json
```

A new case in `CASES` fails with "no reference values" until you do this.
Element counts can differ between OpenCASCADE versions; the values were
recorded with FreeCAD 1.1.4.

## Writing tests

* Build documents with `FreeCAD.newDocument()` in `setUp` and close them in
  `tearDown`.
* Find elements by geometry (`findElement(shape, "Edge", predicate)`),
  never by a hard-coded index.
* Check `"Invalid" in obj.State` after a recompute; a failing feature keeps
  its previous shape, so a geometry check alone can pass by accident.
* When an option is meant to change the geometry, make sure the case
  really differs from the default (some options only apply together with
  another, e.g. `miterangle1` needs `AutoMiter = False`).
* Prefer expected values derived from the definition (see
  `expectedFlatLength` in `testUnfoldAccuracy.py`) over recorded ones.
