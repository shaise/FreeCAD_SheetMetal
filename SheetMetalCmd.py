import SheetMetalBendWall
from SheetMetalTools import isGuiLoaded

# kept around for compatibility with old files
SMBendWall = SheetMetalBendWall.SMBendWall

if isGuiLoaded():
    import SheetMetalBendWallCmd
    SMViewProviderTree = SheetMetalBendWallCmd.SMViewProviderTree
    SMViewProviderFlat = SheetMetalBendWallCmd.SMViewProviderFlat
