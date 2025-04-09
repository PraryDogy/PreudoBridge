import os

volume = None
for i in os.scandir("/Volumes"):
    volume = i.path
    break
main_dir = os.path.join(os.path.expanduser("~"), "Downloads")
main_dir = volume + main_dir

print(main_dir)