import hashlib
import os

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

    def get_uti_filetype(self):
        uti_filetype, _ = self._ws.typeOfFile_error_(self.path, None)
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
    
    def set_uti_data(self, uti_bytes_img: bytes, size: int = 512):
        """
        
        вынести в QRunnable потом

        """

        qimage = QImage()
        qimage.loadFromData(uti_bytes_img)
        qimage = Utils.scaled(qimage, size)

        Dynamic.uti_data[self.uti_filetype] = {"src": qimage}
        for i in Static.image_sizes:
            resized_qimage = Utils.scaled(qimage, i)
            Dynamic.uti_data[self.uti_filetype][i] = resized_qimage
        save_path = os.path.join(Static.external_uti_dir, f"{self.uti_filetype}.png")
        qimage.save(save_path, "PNG")

    def get_uti_bundle(self):
        return NSBundle.bundleWithPath_(self.path).bundleIdentifier()
    
    def worker(self) -> dict[int | str, QImage]:
        type_symlink = "public.symlink"
        type_application = "com.apple.application-bundle"
        empty_icon = "public.data"

        if self.uti_filetype in Dynamic.uti_data:
            return Dynamic.uti_data[self.uti_filetype]

        elif self.uti_filetype == type_symlink:
            self.uti_filetype = self.get_uti_bytes_hash()
            if self.uti_filetype not in Dynamic.uti_data:
                self.set_uti_data(self.get_uti_bytes_img())
        
        elif self.uti_filetype == type_application:
            self.uti_filetype = self.get_uti_bundle()
            if self.uti_filetype not in Dynamic.uti_data:
                self.set_uti_data(self.get_uti_bytes_img())

        elif self.uti_filetype not in Dynamic.uti_data:
            self.set_uti_data(self.get_uti_bytes_img())

        elif self.uti_filetype is None:
            self.uti_filetype = empty_icon

        try:
            qimage = Dynamic.uti_data[self.uti_filetype]
        except KeyError:
            print("set uti data key error", self.data.uti_type)
            qimage = QImage()
        return qimage