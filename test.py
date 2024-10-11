import os
import re
from datetime import date

def find_photoshops():
    root_path = "/Applications"
    photoshop_apps = []

    names = [
        f"Adobe Photoshop CC {i}"
        for i in range(2014, 2020)
        ]

    names.extend([
            f"Adobe Photoshop {i}"
            for i in range(2020, date.today().year + 1)
            ])

    for item in os.listdir(root_path):
        full_path = os.path.join(root_path, item)
        
        if item in names:        
            if os.path.isdir(full_path):
                app_inside_folder = os.path.join(full_path, item + ".app")
                if os.path.exists(app_inside_folder):
                    photoshop_apps.append(app_inside_folder)
            else:
                photoshop_apps.append(full_path)

    return photoshop_apps





# def find_photoshops():
#     years_list = [
#         f"Adobe Photoshop CC {i}"
#         for i in range(2014, 2020)
#         ]

#     years_list.extend([
#             f"Adobe Photoshop {i}"
#             for i in range(2020, date.today().year)
#             ])

a = find_photoshops()
print(a)