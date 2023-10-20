from flask import Flask, render_template, request, Response, redirect, url_for, g
from flask_bootstrap import Bootstrap
import logging
from datetime import datetime
import platform
import os

from vision import VideoStreaming, ObjectDetection, reset_settings
from hearing import MicrophoneStreaming
from speech import SpeechProduction
from state import State
from gpt import GPTConnection
from arduino import Arduino
from mindmup import MindMup

app = Flask(__name__)
log = app.logger
Bootstrap(app)

logging.basicConfig(level=logging.INFO)

# Configure setup
TITLE = "VUmanoid"
VIDEO_PREVIEW = USE_SPEECH = USE_MIC = USE_ARDUINO = True
USE_ARDUINO = True

AUDIO = MicrophoneStreaming(ok_speech_threshold=0.4, enabled=USE_MIC, model='tiny')
SPEECH = SpeechProduction(audio=AUDIO, rate=128, enabled=USE_SPEECH)
OBJECT_DETECTION = ObjectDetection(dnn_model = 'yolov3-tiny', detect_faces = True, 
                                   detect_objects = True)
VIDEO = VideoStreaming(OBJECT_DETECTION, cam_index=0, preview=VIDEO_PREVIEW)
MINDMAP = MindMup('mindmup/tutorial.mup')

STATE = State(f"state-{datetime.now():%Y%m%d-%H%M%S}.txt")
STATE.register_action('SAY', lambda content: SPEECH.speak(content))

persona = """You are a humanoid robot with sensors and actuators. You recieve inputs and respond with outputs that both start with a capitalized keyword. For now, the input keywords are HEAR (for audio speech transcription) and SEE (for object detection, encoded as emojis); the output keywords are WAIT (no content) and SAY (for speech production). Your task is to answer questions about the things you see, but only when you hear a question. For example, if you get:
    SEE 🚲
you respond: WAIT
    HEAR How many wheels does it have?
you respond: SAY A bicycle has two wheels.
"""
GPT = GPTConnection(STATE, persona, MINDMAP.parse(), os.getenv("OPENAI_API_KEY"))
PROCESS_INPUT = GPT.respond

ARDUINO = Arduino(serial_port='/dev/cu.usbmodem142101', enabled = USE_ARDUINO,
                  pin_modes={13:'O'})

# Register web interface
@app.route("/")
def home():
    return render_template(
        "index.html", 
        title=TITLE, preview=VIDEO._preview, platform=platform.system().lower(),
        secret = str(GPT.get_key()))

@app.route("/video_feed")
def video_feed():
    return Response(VIDEO.show(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/audio_feed")
def audio_feed():
    return Response(AUDIO.show(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/arduino_feed")
def arduino_feed():
    return Response(ARDUINO.show(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/state", methods=["POST", "GET"])
def get_or_set_state():
    if request.method == 'POST':
        message = request.get_data().decode('utf-8')
        log.info(message)
        STATE.log(message)

        if message[0] == '<':
            keyword, content = message[1:].split(' ', 1)
            PROCESS_INPUT(keyword, content)

        return Response(status = 200) 
    elif request.method == 'GET':
        return STATE.read()

@app.route("/secret_set", methods=["POST"])
def secret_set():
    data = request.get_json(force=True)
    api_key = data.get('secret')
    if api_key:
        GPT.set_key(api_key)
        return Response(status = 200) 
    return Response(status = 404) 

# Camera settings
@app.route("/camera_set", methods=["POST"])
def camera_set():
    data = request.get_json(force=True)
    if 'cam_preview' in data:
        VIDEO.preview = data['cam_preview']
        log.info(f"cam_preview: {VIDEO.preview}")
        return Response(status = 200)
    elif 'cam_flip' in data:
        VIDEO.flipH = data['cam_flip']
        log.info(f"cam_flip: {VIDEO.flipH}")
        return Response(status = 200)
    elif 'cam_detect' in data:
        VIDEO.detect = data['cam_detect']
        log.info(f"cam_flip: {VIDEO.detect}")
        return Response(status = 200) 
    elif 'cam_exposure' in data:
        VIDEO.exposure = data['cam_exposure']
        log.info(f"cam_exposure: {VIDEO.exposure}")
        return Response(status = 200)
    elif 'cam_contrast' in data:
        VIDEO.contrast = data['cam_contrast']
        log.info(f"cam_contrast: {VIDEO.contrast}")
        return Response(status = 200)
    elif 'cam_reset' in data:
        reset_settings()
        log.info(f"cam_reset")
        return Response(status = 200) 


if __name__ == "__main__":
    STATE.clear()
    app.run(debug=True, use_reloader=False)
