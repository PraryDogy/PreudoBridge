import os



volumes = [
    os.path.join("/Volumes", i)
    for i in os.listdir("/Volumes")
    if os.path.ismount(os.path.join("/Volumes", i))
    ]

print(volumes)