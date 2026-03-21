import time
from threading import Lock

import cv2
from flask import Flask, Response

APP = Flask(__name__)
CAP = cv2.VideoCapture(0)
LOCK = Lock()
LAST_FRAME = None


def _grab_loop():
    global LAST_FRAME
    while True:
        ok, frame = CAP.read()
        if not ok:
            time.sleep(0.05)
            continue
        with LOCK:
            LAST_FRAME = frame.copy()


def _gen():
    while True:
        with LOCK:
            frame = None if LAST_FRAME is None else LAST_FRAME.copy()
        if frame is None:
            time.sleep(0.05)
            continue
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")


@APP.route("/video")
def video():
    return Response(_gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    import threading

    t = threading.Thread(target=_grab_loop, daemon=True)
    t.start()
    APP.run(host="0.0.0.0", port=5000)
