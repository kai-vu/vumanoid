from flask import Flask, render_template, request, Response, redirect, url_for, g
from flask_bootstrap import Bootstrap
import logging
from datetime import datetime
import platform

from vision import VideoStreaming, reset_settings
from hearing import AudioStreaming
from speech import SpeechProduction
from state import State

app = Flask(__name__)
Bootstrap(app)

logging.basicConfig(level=logging.INFO)

# Configure setup
TITLE = "VUmanoid"
PREVIEW = False
AUDIO = AudioStreaming(ok_speech_threshold=0.4)
SPEECH = SpeechProduction(audio=AUDIO, rate=128, enabled=False)
VIDEO = VideoStreaming(cam_index=0, preview=PREVIEW, 
                       detect_faces = True, detect_objects = True)

STATE = State(f"state-{datetime.now():%Y%m%d-%H%M%S}.txt")
STATE.register_action('SAY', lambda content: SPEECH.speak(content))

# Define behaviour (TODO: ChatGPT)
def process_input(keyword, content):
    if keyword == 'HEAR':
        return STATE.output('SAY', f'I hear {content}')
    if keyword == 'SEE':
        return STATE.output('SAY', f'I see {content}')

# Register web interface
@app.route("/")
def home():
    return render_template(
        "index.html", 
        title=TITLE, preview=VIDEO._preview, platform=platform.system().lower())

@app.route("/video_feed")
def video_feed():
    """
    Video streaming route.
    """
    return Response(VIDEO.show(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/audio_feed")
def audio_feed():
    """
    Audio streaming route.
    """
    return Response(AUDIO.show(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/state", methods=["POST", "GET"])
def get_or_set_state():
    if request.method == 'POST':
        message = request.get_data().decode('utf8')
        logging.info(message)
        STATE.log(message)

        if message[0] == '<':
            keyword, content = message[1:].split(' ', 1)
            process_input(keyword, content)

        return Response(status = 200) 
    elif request.method == 'GET':
        return STATE.read()

# Camera settings
@app.route("/camera_set", methods=["POST"])
def camera_set():
    data = request.get_json(force=True)
    if 'cam_preview' in data:
        VIDEO.preview = data['cam_preview']
        app.logger.info(f"cam_preview: {VIDEO.preview}")
        return Response(status = 200)
    elif 'cam_flip' in data:
        VIDEO.flipH = data['cam_flip']
        app.logger.info(f"cam_flip: {VIDEO.flipH}")
        return Response(status = 200)
    elif 'cam_detect' in data:
        VIDEO.detect = data['cam_detect']
        app.logger.info(f"cam_flip: {VIDEO.detect}")
        return Response(status = 200) 
    elif 'cam_exposure' in data:
        VIDEO.exposure = data['cam_exposure']
        app.logger.info(f"cam_exposure: {VIDEO.exposure}")
        return Response(status = 200)
    elif 'cam_contrast' in data:
        VIDEO.contrast = data['cam_contrast']
        app.logger.info(f"cam_contrast: {VIDEO.contrast}")
        return Response(status = 200)
    elif 'cam_reset' in data:
        reset_settings()
        app.logger.info(f"cam_reset")
        return Response(status = 200) 


if __name__ == "__main__":
    STATE.clear()
    app.run(debug=True, use_reloader=False)
