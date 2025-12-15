from AppKit import NSWorkspace, NSBitmapImageRep, NSPNGFileType
import os

def save_filetype_icon_to_desktop(file_path):
    ws = NSWorkspace.sharedWorkspace()

    # получить UTI типа файла
    uti, _ = ws.typeOfFile_error_(file_path, None)

    # получить иконку типа файла
    icon = ws.iconForFileType_(uti)

    # конвертация в PNG
    tiff = icon.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff)
    png = rep.representationUsingType_properties_(NSPNGFileType, None)



src = "/Users/Loshkarev/Desktop/Диадема_1.png"
save_filetype_icon_to_desktop(src)
