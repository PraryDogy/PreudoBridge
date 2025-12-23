from AppKit import NSBitmapImageRep, NSBundle, NSPNGFileType, NSWorkspace


@classmethod
    def uti_generator(cls, filepath: str, size: int = 512):
        """
        Возвращает uti filetype, {image_size: QImage, image_size: QImage, }
        image_size ссылается на Static.image_sizes, то есть будет возвращен
        словарик с QImage, соответвующий всем размерам из Static.image_sizes
        """

        def get_bytes_icon(filepath: str):
            icon = Utils._ws.iconForFile_(filepath)
            tiff = icon.TIFFRepresentation()
            rep = NSBitmapImageRep.imageRepWithData_(tiff)
            png = rep.representationUsingType_properties_(NSPNGFileType, None)
            return bytes(png)
        
        def get_errored_icon():
            uti_filetype_ = "public.data"
            return uti_filetype_, Dynamic.uti_data[uti_filetype_]
        
        def set_uti_data(uti_filetype: str, qimage: QImage):
            Dynamic.uti_data[uti_filetype] = {}
            for i in Static.image_sizes:
                resized_qimage = Utils.scaled(qimage, i)
                Dynamic.uti_data[uti_filetype][i] = resized_qimage

        def get_symlink_bytes(filepath: str):
            icon = Utils._ws.iconForFile_(filepath)
            tiff_bytes = icon.TIFFRepresentation()[:-1].tobytes()
            return hashlib.md5(tiff_bytes).hexdigest()

        uti_filetype, _ = Utils._ws.typeOfFile_error_(filepath, None)

        if uti_filetype == "public.symlink":
            symlink_bytes = get_symlink_bytes(filepath)
            if symlink_bytes in Dynamic.uti_data:
                return symlink_bytes, Dynamic.uti_data[symlink_bytes]
            
            bytes_icon = get_bytes_icon(filepath)
            qimage = QImage()
            qimage.loadFromData(bytes_icon)
            set_uti_data(symlink_bytes, qimage)

            uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{symlink_bytes}.png")
            if not os.path.exists(uti_png_icon_path):
                qimage = QImage.fromData(bytes_icon)
                qimage = Utils.scaled(qimage, size)
                qimage.save(uti_png_icon_path, "PNG")
            return symlink_bytes, Dynamic.uti_data[symlink_bytes]
        
        if uti_filetype == "com.apple.application-bundle":
            bundle = NSBundle.bundleWithPath_(filepath).bundleIdentifier()

            if bundle in Dynamic.uti_data:
                return bundle, Dynamic.uti_data[bundle]

            bytes_icon = get_bytes_icon(filepath)
            qimage = QImage()
            qimage.loadFromData(bytes_icon)
            set_uti_data(bundle, qimage)

            uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{bundle}.png")
            if not os.path.exists(uti_png_icon_path):
                qimage = QImage.fromData(bytes_icon)
                qimage = Utils.scaled(qimage, size)
                qimage.save(uti_png_icon_path, "PNG")

            return bundle, Dynamic.uti_data[bundle]

        if not uti_filetype:
            return get_errored_icon()

        if uti_filetype in Dynamic.uti_data:
            return uti_filetype, Dynamic.uti_data[uti_filetype]

        uti_png_icon_path = os.path.join(Static.external_uti_dir, f"{uti_filetype}.png")

        if not os.path.exists(uti_png_icon_path):
            bytes_icon = get_bytes_icon(filepath)

            qimage = QImage.fromData(bytes_icon)
            qimage = Utils.scaled(qimage, size)
            qimage.save(uti_png_icon_path, "PNG")

        qimage = QImage(uti_png_icon_path)
        if qimage.isNull():
            return get_errored_icon()

        set_uti_data(uti_filetype, qimage)
        return uti_filetype, Dynamic.uti_data[uti_filetype]