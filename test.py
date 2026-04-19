import subprocess

file = "/Users/evlosh/Downloads/IMAGE 2026-02-03 17:41:33.jpg"

subprocess.run([
    "exiftool",
    "-Rating=4",
    "-overwrite_original",
    file
])

