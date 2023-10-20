import os
import time
import cv2
import numpy as np
import logging
from datetime import datetime
import requests
from tqdm import tqdm
from urllib.parse import urlparse

from camera_settings import check_settings, reset_settings
from state import State


log = logging.getLogger(__name__)

FONT = cv2.FONT_HERSHEY_PLAIN

def download(url):
    fname = os.path.basename(urlparse(url).path)
    path = os.path.join("models", fname)
    if not os.path.exists(path):
        log.info(f'Downloading {url}')
        response = requests.get(url, allow_redirects=True, stream=True)
        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024 #1 Kibibyte
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
        with open(path, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)
        progress_bar.close()


class ObjectDetection:
    def __init__(self, detect_faces = True, detect_objects = True, use_emojis=True, dnn_model = 'yolov3-tiny'):
        self.detect_objects = detect_objects
        self.detect_faces = detect_faces
        self.use_emojis = use_emojis

        check_settings()
        PROJECT_PATH = os.path.abspath(os.getcwd())
        MODELS_PATH = os.path.join(PROJECT_PATH, "models")
        
        log.info(f'Loading DNN model {dnn_model}')
        if not dnn_model:
            dnn_model = 'yolov3-tiny'
            print("no model specified, defaulting to 'yolov3-tiny'")

        # see also https://github.com/pjreddie/darknet/tree/master/cfg
        download(f"https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/{dnn_model}.cfg")
        download(f"https://pjreddie.com/media/files/{dnn_model}.weights")
        self.MODEL = cv2.dnn.readNet(
            os.path.join(MODELS_PATH, f"{dnn_model}.weights"),
            os.path.join(MODELS_PATH, f"{dnn_model}.cfg"),
        )

        self.CLASSES = []
        with open(os.path.join(MODELS_PATH, "coco.names"), "r") as f:
            self.CLASSES = [line.strip() for line in f.readlines()]
        
        if self.use_emojis:
            self.EMOJIS = []
            emoji_path = os.path.join(MODELS_PATH, "coco.emojis")
            with open(emoji_path, encoding='utf-8', errors='ignore') as f:
                self.EMOJIS = [line.strip() for line in f.readlines()]

        self.OUTPUT_LAYERS = [
            self.MODEL.getLayerNames()[i - 1]
            for i in self.MODEL.getUnconnectedOutLayers()
        ]
        self.COLORS = np.random.uniform(0, 255, size=(len(self.CLASSES), 3))
        self.COLORS /= (np.sum(self.COLORS**2, axis=1) ** 0.5 / 255)[np.newaxis].T

        face_model = 'haarcascade_frontalface_default.xml'
        # see also: https://github.com/opencv/opencv/tree/master/data/haarcascades
        download(f'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/{face_model}')
        self.face_cascade = cv2.CascadeClassifier(os.path.join("models", face_model))

        self.last_seen_time = {}

    def detectObj(self, snap, threshold=0.5):
        height, width, channels = snap.shape
        class_ids = []
        confidences = []
        boxes = []

        if self.detect_objects:
            blob = cv2.dnn.blobFromImage(
                snap, 1/255, (416, 416), swapRB=True, crop=False
            )
            self.MODEL.setInput(blob)
            outs = self.MODEL.forward(self.OUTPUT_LAYERS)

            # Showing informations on the screen
            for out in outs:
                for detection in out:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    if confidence > threshold:
                        # * Object detected
                        center_x = int(detection[0]*width)
                        center_y = int(detection[1]*height)
                        w = int(detection[2]*width)
                        h = int(detection[3]*height)

                        # * Rectangle coordinates
                        x = int(center_x - w/2)
                        y = int(center_y - h/2)

                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
        indexes = list(cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4))

        if self.detect_faces:
            gray = cv2.cvtColor(snap, cv2.COLOR_BGR2GRAY)
            faces, face_confidences = self.face_cascade.detectMultiScale2(gray, 1.1, 4)
            boxes += list(faces)
            confidences += [i / 100 for i in face_confidences]
            for _ in range(len(faces)):
                class_ids.append(0) # class 0 = person
                indexes.append(len(indexes)) # show boxes with last indexes


        new_seen = set()
        now = datetime.now()
        for i in range(len(boxes)):
            if i in indexes:
                x, y, w, h = boxes[i]
                label = str(self.CLASSES[class_ids[i]])
                color = self.COLORS[i]
                cv2.rectangle(snap, (x, y), (x + w, y + h), color, 2)
                cv2.putText(snap, label, (x, y - 5), FONT, 2, color, 2)

                # Keep track of last seen things
                seen = label
                if self.use_emojis:
                    seen = str(self.EMOJIS[class_ids[i]])
                last = self.last_seen_time.get(seen, None)
                if (not last) or (now - last).seconds > 5:
                    new_seen.add(seen)
                self.last_seen_time[seen] = now
        if new_seen:
            State.input('SEE', ', '.join(new_seen))
        return snap


class VideoStreaming(object):
    def __init__(self, object_detection_model, cam_index=0, preview=True):
        super(VideoStreaming, self).__init__()
        self.VIDEO = cv2.VideoCapture(cam_index)

        self.MODEL = object_detection_model

        self._preview = preview
        self._flipH = False
        self._detect = False
        self._initial_exposure = self.VIDEO.get(cv2.CAP_PROP_EXPOSURE)
        self._exposure = self._initial_exposure
        self._initial_contrast = self.VIDEO.get(cv2.CAP_PROP_CONTRAST)
        self._contrast = self._initial_contrast

    @staticmethod
    def rescale_frame(frame, scale):
        width = int(frame.shape[1] * scale)
        height = int(frame.shape[0] * scale)
        dimensions = (width, height)
        return cv2.resize(frame, dimensions, interpolation=cv2.INTER_AREA)

    @property
    def preview(self):
        return self._preview

    @preview.setter
    def preview(self, value):
        self._preview = bool(value)

    @property
    def flipH(self):
        return self._flipH

    @flipH.setter
    def flipH(self, value):
        self._flipH = bool(value)

    @property
    def detect(self):
        return self._detect

    @detect.setter
    def detect(self, value):
        self._detect = bool(value)

    @property
    def exposure(self):
        return self._exposure

    @exposure.setter
    def exposure(self, value):
        self._exposure = self._initial_exposure + float(value)
        self.VIDEO.set(cv2.CAP_PROP_EXPOSURE, self._exposure)

    @property
    def contrast(self):
        return self._contrast

    @contrast.setter
    def contrast(self, value):
        self._contrast = self._initial_contrast + float(value)
        self.VIDEO.set(cv2.CAP_PROP_CONTRAST, self._contrast)

    def show(self):
        while self.VIDEO.isOpened():
            ret, snap = self.VIDEO.read()

            snap = self.rescale_frame(snap, 0.5)

            if self.flipH:
                snap = cv2.flip(snap, 1)

            if ret == True:
                if self._preview:
                    # snap = cv2.resize(snap, (0, 0), fx=0.5, fy=0.5)
                    if self.detect:
                        snap = self.MODEL.detectObj(snap, threshold=0.01)

                else:
                    snap = np.zeros(
                        (
                            int(self.VIDEO.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                            int(self.VIDEO.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        ),
                        np.uint8,
                    )
                    label = "camera disabled"
                    H, W = snap.shape
                    color = (255, 255, 255)
                    cv2.putText(snap, label, (W // 2 - 100, H // 2), FONT, 2, color, 2)
                
                color = (255, 255, 255)
                time_str = f'{datetime.now():%H:%M:%S}'
                cv2.putText(snap, time_str, (2,22), FONT, 2, color, 2)

                frame = cv2.imencode(".jpg", snap)[1].tobytes()
                yield (
                    b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
                time.sleep(0.01)

            else:
                break
