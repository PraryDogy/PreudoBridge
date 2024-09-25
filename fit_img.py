from PIL import Image


class FitImg:
    @staticmethod
    def fit(img: Image.Image, w: int, h: int) -> Image.Image:
        imw, imh = img.size

        if -3 < imw - imh < 3:
            imw, imh = imw, imw

        if w > h:

            if imw > imh:
                delta = imw/imh
                neww, newh = w, int(w/delta)
            else:
                delta = imh/imw
                neww, newh = int(h/delta), h
        
        else:

            if imw > imh:
                delta = imw/imh
                neww, newh = w, int(w/delta)
            else:
                delta = imh/imw
                neww, newh = int(h/delta), h

        return img.resize((neww, newh))