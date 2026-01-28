import cv2
import cairosvg
import numpy as np

png_data = cairosvg.svg2png(url="file.svg")
nparr = np.frombuffer(png_data, np.uint8)
image = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
cv2.imshow("SVG", image)
cv2.waitKey(0)
cv2.destroyAllWindows()
