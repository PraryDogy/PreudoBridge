import os
from AppKit import NSImage, NSBitmapImageRep, NSPNGFileType

SRC_DIR = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources"
OUT_DIR = "./uti_icons"
SIZE = 512

os.makedirs(OUT_DIR, exist_ok=True)

def icns_to_png(src, dst):
    img = NSImage.alloc().initWithContentsOfFile_(src)
    if not img:
        return

    img.setSize_((SIZE, SIZE))
    rep = NSBitmapImageRep.imageRepWithData_(img.TIFFRepresentation())
    png = rep.representationUsingType_properties_(NSPNGFileType, None)

    with open(dst, "wb") as f:
        f.write(png)

for name in os.listdir(SRC_DIR):
    if name.endswith(".icns"):
        icns_to_png(
            os.path.join(SRC_DIR, name),
            os.path.join(OUT_DIR, name.replace(".icns", ".png"))
        )
