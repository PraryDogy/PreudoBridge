import logging

import numpy as np
import psd_tools
import psd_tools.psd
import psd_tools.psd.tagged_blocks


def read_psd(src: str) -> np.ndarray:
    try:
        img = psd_tools.PSDImage.open(fp=src)
        img = img.composite(ignore_preview=True)

        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        img = np.array(img)
        return img

    except Exception as e:
        print("psd tools error:", e, src)
        return None
    

psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None


# psd_logger.warning = lambda *args, **kwargs: None
# psd_logger.info = lambda *args, **kwargs: None
# psd_logger.error = lambda *args, **kwargs: None
# psd_logger.debug = lambda *args, **kwargs: None


img = "/Users/Loshkarev/Desktop/MIUZ_0158.psd"
read_psd(img)