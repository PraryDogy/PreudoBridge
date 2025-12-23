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

    def get_uti_bundle(self):
        return NSBundle.bundleWithPath_(self.path).bundleIdentifier()
    
    def worker(self) -> dict[int | str, QImage]:
        type_symlink = "public.symlink"
        type_application = "com.apple.application-bundle"
        empty_file = "public.data"

        if self.uti_filetype in Dynamic.uti_data:
            return Dynamic.uti_data[self.uti_filetype]

        if self.uti_filetype == type_symlink:
            # получаем хеш сумму байтов
            appkit_hash = self.get_uti_bytes_hash()
            # если иконка еще не закэширована
            if appkit_hash not in Dynamic.uti_data:
                bytes_icon = self.get_uti_bytes_img()
                qimage = QImage()
                qimage.loadFromData(bytes_icon)
                # добавляем в хэш все размеры иконки по списку Static.image_sizes
                # а так же хэш размера 512 на 512 по ключу "src"
                self.set_uti_data(appkit_hash, qimage)
                # сохраняем иконку
                uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{appkit_hash}.png")
                qimage_for_save: QImage = Dynamic.uti_data[appkit_hash]["src"]
                qimage_for_save.save(uti_png_icon_path, "PNG")
        
        elif self.uti_filetype == type_application:
            bundle = self.get_uti_bundle()
            if bundle not in Dynamic.uti_data:
                bytes_icon = self.get_uti_bytes_img()
                qimage = QImage()
                qimage.loadFromData(bytes_icon)
                Utils.set_uti_data(bundle, qimage)
                uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{bundle}.png")
                qimage_for_save: QImage = Dynamic.uti_data[bundle]["src"]
                qimage_for_save.save(uti_png_icon_path, "PNG")
                qimage.save(uti_png_icon_path, "PNG")

        elif self.uti_filetype is None:
            self.uti_filetype = empty_file

        elif self.uti_filetype not in Dynamic.uti_data:
            bytes_icon = Utils.get_uti_bytes_img(self.data.src)
            qimage = QImage()
            qimage.loadFromData(bytes_icon)
            Utils.set_uti_data(self.data.uti_type, qimage)
            uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{self.data.uti_type}.png")
            qimage_for_save: QImage = Dynamic.uti_data[self.data.uti_type]["src"]
            qimage_for_save.save(uti_png_icon_path, "PNG")
            qimage.save(uti_png_icon_path, "PNG")

        try:
            qimage = Dynamic.uti_data[self.data.uti_type][Thumb.current_image_size]
        except KeyError:
            print("set uti data key error", self.data.uti_type)
            qimage = QImage()
        pixmap = QPixmap.fromImage(qimage)
        self.img_wid.setPixmap(pixmap)