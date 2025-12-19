import io

from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
from PIL import Image

from system.utils import Utils

src = '/Users/Loshkarev/Documents/Разное/Progs/Visual Studio Code.app'
uti_filetype = Utils.get_uti_type(src)

_ws = NSWorkspace.sharedWorkspace()
if uti_filetype == "com.apple.application-bundle":
    icon = _ws.iconForFile_(src)
    tiff = icon.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff)
    png = rep.representationUsingType_properties_(NSPNGFileType, None)
    img = Image.open(io.BytesIO(bytes(png)))
    img.show()


1