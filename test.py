import io

from AppKit import NSBitmapImageRep, NSPNGFileType, NSWorkspace
from PIL import Image

from system.utils import Utils

src = "/Volumes/Macintosh HD/Users/Loshkarev/Documents/Разное/Progs/PreudoBridge.app/Contents/Resources/icons/arrow_left.svg"
uti_filetype = Utils.get_uti_type(src)

_ws = NSWorkspace.sharedWorkspace()
icon = _ws.iconForFile_(src)
tiff = icon.TIFFRepresentation()
rep = NSBitmapImageRep.imageRepWithData_(tiff)
png = rep.representationUsingType_properties_(NSPNGFileType, None)
img = Image.open(io.BytesIO(bytes(png)))
img.show()
