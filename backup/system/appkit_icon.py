import hashlib
import os

from AppKit import NSBitmapImageRep, NSBundle, NSPNGFileType, NSWorkspace
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, pyqtSignal

from cfg import Dynamic, Static
from system.tasks import AnyTaskLoader, UThreadPool
from system.utils import Utils


class AppKitIcon(QObject):
    finished_ = pyqtSignal(dict)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self._ws = NSWorkspace.sharedWorkspace()
        self.uti_filetype = self.get_uti_filetype()

    def get_uti_filetype(self) -> str:
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
    
    def get_qimages(self):
        """
        Вернет словарик:
        {"src": QImage, int: QImage, int: QImage, ...}
        значения наполняются из Static.image_sizes
        Например
        Static.image_sizes = [50, 70, 100, 170]
        {"src": QImage, 50: QImage, 70: QImage, 100: QImage, 170: QImage}
        """
        
        type_symlink = "public.symlink"
        type_application = "com.apple.application-bundle"
        empty_icon = "public.data"

        conds = (
            self.uti_filetype is None,
            self.uti_filetype is not None and "dyn." in self.uti_filetype
        )

        if any(conds):
            self.uti_filetype = empty_icon

        conds = (
           self.uti_filetype in Dynamic.uti_data,
           self.uti_filetype != type_application 
        )

        need_new_img = False

        if all(conds):
            self.finish_qimages()
            return

        if self.uti_filetype == type_symlink:
            self.uti_filetype = self.get_uti_bytes_hash()
            if self.uti_filetype not in Dynamic.uti_data:
                need_new_img = True
        
        elif self.uti_filetype == type_application:
            self.uti_filetype = self.get_uti_bundle()
            if self.uti_filetype not in Dynamic.uti_data:
                need_new_img = True

        elif self.uti_filetype not in Dynamic.uti_data:
            need_new_img = True

        if need_new_img:
            uti_bytes_png = self.get_uti_bytes_img()
            self.any_task = AnyTaskLoader(cmd = lambda: self.set_uti_data(uti_bytes_png))
            self.any_task.sigs.finished_.connect(self.finish_qimages)
            UThreadPool.start(self.any_task)
        else:
            self.finish_qimages()

    def finish_qimages(self):
        try:
            qimages = Dynamic.uti_data[self.uti_filetype]
        except KeyError:
            print("set uti data key error", self.uti_filetype, self.path)
            qimages = {"src": QImage()}
            for size in Static.image_sizes:
                qimages[size] = QImage()
        self.finished_.emit(qimages)
