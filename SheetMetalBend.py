import SheetMetalSolidBend
from SheetMetalTools import isGuiLoaded

# kept around for compatibility with old files
SMSolidBend = SheetMetalSolidBend.SMSolidBend

if isGuiLoaded():
    import SheetMetalSolidBendCmd
    SMBendViewProviderTree = SheetMetalSolidBendCmd.SMBendViewProviderTree
    SMBendViewProviderFlat = SheetMetalSolidBendCmd.SMBendViewProviderFlat
