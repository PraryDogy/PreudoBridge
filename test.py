import time
from system.shared_utils import ReadImage

src = "/Users/evlosh/Downloads/Пленка летняя/R1-09909-0027.TIF"
src = "/Users/evlosh/Downloads/Canon-eos-r-raw-00012.cr3"


start = time.time()
a = ReadImage._read_raw(src)
tiff_time = time.time() - start
print("TIFF read time:", tiff_time, "seconds")

start = time.time()
b = ReadImage._read_quicklook(src)
ql_time = time.time() - start
print("QuickLook read time:", ql_time, "seconds")

if tiff_time < ql_time:
    print("TIFF чтение быстрее")
elif ql_time < tiff_time:
    print("QuickLook чтение быстрее")
else:
    print("Оба метода работают примерно с одинаковой скоростью")
