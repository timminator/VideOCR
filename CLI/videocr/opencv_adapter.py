import cv2


class Capture:
    def __init__(self, video_path):
        self.path = video_path

    def __enter__(self):
        self.cap = cv2.VideoCapture(self.path)
        if not self.cap.isOpened():
            raise IOError('Can not open video {}.'.format(self.path))
        return self.cap

    def __exit__(self, exc_type, exc_value, traceback):
        self.cap.release()
