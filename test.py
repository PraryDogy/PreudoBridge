import subprocess
import plistlib
import os

def get_device_and_uuid(mp):
    # получаем device
    df_res = subprocess.run(
        ["df", mp],
        capture_output=True,
        text=True
    )
    device = df_res.stdout.splitlines()[1].split()[0]

    # получаем UUID
    du_res = subprocess.run(
        ["diskutil", "info", device],
        capture_output=True,
        text=True
    )

    uuid = None
    for line in du_res.stdout.splitlines():
        if "Volume UUID" in line:
            uuid = line.split(":")[1].strip()
            break

    return mp, device, uuid


volumes = [i.path for i in os.scandir("/Volumes")]

for i in volumes:
    res = get_device_and_uuid(i)