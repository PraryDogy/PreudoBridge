from system.utils import Utils
import os

src = "/Users/Loshkarev/Desktop/batat4240_delete_--ar_5877_--raw_--v_7_817b3c96-7335-4ea5-ab63-026da652b100.tif"
root, filename = os.path.split(src)



thumb_path = Utils.create_thumb_path(
    filename=filename,
    mod=os.stat(src).st_mtime,
    rel_parent=root,
    fs_id="dsfsdfsd-wefwef-wefe"
)

print(thumb_path)