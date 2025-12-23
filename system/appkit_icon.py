import hashlib

from AppKit import NSBitmapImageRep, NSBundle, NSPNGFileType, NSWorkspace
from PyQt5.QtGui import QImage

from cfg import Dynamic, Static
from system.utils import Utils


class AppKitIcon:
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self._ws = NSWorkspace.sharedWorkspace()
        self.uti_filetype = self.get_uti_filetype()

    def get_uti_filetype(self, filepath: str):
        uti_filetype, _ = self._ws.typeOfFile_error_(filepath, None)
        return uti_filetype
    
    def get_uti_bytes_img(self):
        icon = self._ws.iconForFile_(self.path)
        tiff = icon.TIFFRepresentation()
        rep = NSBitmapImageRep.imageRepWithData_(tiff)
        png = rep.representationUsingType_properties_(NSPNGFileType, None)
        return bytes(png)
        
    def get_uti_bytes_hash(self):
        icon = self._ws.iconForFile_(self.path)
        tiff_bytes = icon.TIFFRepresentation()[:-1].tobytes()
        return hashlib.md5(tiff_bytes).hexdigest()
    
    def set_uti_data(self, uti_filetype: str, qimage: QImage, size: int = 512):
        """
        
        вынести в тред потом

        """
        Dynamic.uti_data[uti_filetype] = {}
        for i in Static.image_sizes:
            resized_qimage = Utils.scaled(qimage, i)
            Dynamic.uti_data[uti_filetype][i] = resized_qimage
        Dynamic.uti_data[uti_filetype]["src"] = Utils.scaled(qimage, size)

    def get_uti_bundle(self, filepath: str):
        return NSBundle.bundleWithPath_(filepath).bundleIdentifier()