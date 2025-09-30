from system.utils import Utils
import os
import time
from cfg import Static

def abs_thumb_path(partial_hash: str) -> str:
    base = os.path.join(
        Static.THUMBNAILS,
        partial_hash[:2],
        partial_hash[2:] + ".jpg"
    )
    return base

def rel_thumb_path(partial_hash: str) -> str:
    base = os.path.join(
        partial_hash[:2],
        partial_hash[2:] + ".jpg"
    )
    return base


src = '/Users/Loshkarev/Desktop/R2018-RLF-0253.tif'
partial_hash = Utils.partial_hash(src)
thumb_path_ = abs_thumb_path(partial_hash)
print(thumb_path_)