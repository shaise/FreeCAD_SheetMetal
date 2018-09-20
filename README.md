# FreeCAD SheetMetal Workbench
A simple sheet metal workbench for FreeCAD

![Demo Workflow](../master/Resources/SheetMetal4.gif)

#### Developers:
* Folding tools:  Shai Seger [@shaise](https://github.com/shaise)  
                  Based and inspired by Javier Martínez's ([@JMG1](https://github.com/JMG1)) code
* Unfolding tool: Copyright 2014 by Ulrich Brammer <ulrich1a[at]users.sourceforge.net> AKA [@ulrich1a](https://github.com/ulrich1a)

#### Installation
For installation and how to use, please visit:  
http://theseger.com/projects/2015/06/sheet-metal-addon-for-freecad/  
Starting from FreeCAD 0.17 it can be installed via the [Addon Manager](https://github.com/FreeCAD/FreeCAD-addons) (from Tools menu)

#### Release notes: 
* V0.2.03 20 Sep 2018:  Merge easyw PR: Add seperate color for inner sketch lines. (issue #46). Change Gui layout
* V0.2.02 15 Sep 2018:  Add color selection for unfold sketches (issue #41)
* V0.2.01 15 Sep 2018:  Fix bug when not generating sketch (issue #42). Support separate color for bend lines (issue #41)
* V0.2.00 04 Sep 2018:  Make SheetMetal compatible with Python 3 and QT 5
* V0.1.40 20 Aug 2018:  Merge Ulrich's V20 unfolder script - supports many more sheet metal cases and more robust
* V0.1.32 25 Jun 2018:  New feature: Option to separately unfold bends. Thank you jaisejames!
* V0.1.31 25 Jun 2018:  Support ellipses and parabolas, Try standard sketch conversion first
* V0.1.30 25 Jun 2018:  <br/>
New feature: Generate unfold sketch with folding marks. Issue #33. Thank you easyw-fc! <br/>
New feature: K-Factor foe unfolding is now editable. Issue #30 <br/>
* V0.1.21 19 Jun 2018:  Fixed back negative bend angles, restrict miter to +/- 80 degrees
* V0.1.20 19 Jun 2018:  <br/>
Add bend extension to make the bended wall wider<br/>
Add relief shape selection (rounded or flat)<br/>
Double clicking on a bent in the tree view, brings a dialog to select different faces (good when editing the base object breaks the bend, and new faces need to be selected)<br/>
Setting miter angle now works with unfold command<br/>
Thank you jaisejames for all these new features!!
* V0.1.13 10 May 2018:  Change unbending method so shape refinement can work.
* V0.1.12 25 Mar 2018:  Allow negative bend angles. Change XPM icons to SVG
* V0.1.11 01 Feb 2018:  fix Issue #23: when there is a gap only on one side, an extra face is added to the other
* V0.1.10 11 Nov 2017:  Add miter option to bends. By @jaisejames
* V0.1.02 22 Jun 2017:  Fix nesting bug, when saving and loading file
* V0.1.01 03 Mar 2017:  Support version 0.17. (strting from build 10423)
* V0.0.13 07 Sep 2015:  Add negative gaps for extrude function. (per deveee request)
* V0.012  07 Sep 2015:  Fix issue submitted by deveee
* V0.010  13 Jun 2015:  Add Ulrich's great unfolding tool. Thanks!!!
* V0.002  12 Jun 2015:  Fix Save/Load issues  
* V0.001  11 Jun 2015:  Initial version
