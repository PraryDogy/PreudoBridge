import cv2

def get_thumbnail(video_path, time_sec=1, output_path="thumbnail.jpg"):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
    success, frame = cap.read()
    if success:
        cv2.imwrite(output_path, frame)
    cap.release()


src = "/Volumes/Shares/Studio/MIUZ/Video/Digital/Ready/2025/2. Февраль/MIUZ 31.01.25 1 (727x727).mp4"
src = "/Volumes/Shares/Studio/MIUZ/Video/Digital/Ready/2025/2. Февраль/MIUZ 02.25 new coll.mov"
get_thumbnail(src)