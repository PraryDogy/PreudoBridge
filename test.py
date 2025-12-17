from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
from PIL import Image
from io import BytesIO


def test(filepath: str):
    _ws = NSWorkspace.sharedWorkspace()
    icon = _ws.iconForFile_(filepath)
    tiff = icon.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff)
    png = rep.representationUsingType_properties_(NSPNGFileType, None)
    img = Image.open(BytesIO(bytes(png)))
    img.show()


src = "/Volumes/shares"
test(src)