import os
from cfg import Static
from utils import Utils



volumes = [
    i.path
    for i in os.scandir(os.sep + "Volumes")
]
volumes.remove(Utils.get_system_volume())

print(volumes)