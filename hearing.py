import logging
import speech_recognition as sr
import audioop
from PIL import Image, ImageDraw, ImageFont
import io
import torch
import whisper
import queue
import threading
import numpy as np
import time
import platform
import math
from datetime import datetime
import editdistance
import string
import re

from state import State

MIC_IMG = Image.open("static/mic.png").convert("RGBA")

log = logging.getLogger(__name__)

def tokenize(s: str):
    s = s.translate(str.maketrans('', '', string.punctuation))
    return s.lower().split()

class MicrophoneStreaming:
    def __init__(
        self,
        enabled=True,
        model: str = "tiny",
        device: str = ("cuda" if torch.cuda.is_available() else "cpu"),
        english: bool = True,
        verbose: bool = False,
        energy: int = 300,
        pause: float = 0.8,
        dynamic_energy: bool = False,
        model_root: str = "models",
        mic_index: int = None,
        no_speech_threshold: float = 0.5,
        ok_speech_threshold: float = 0.5,
    ):
        self.energy = energy
        self.pause = pause
        self.dynamic_energy = dynamic_energy
        self.verbose = verbose
        self.english = english
        self.no_speech_threshold = no_speech_threshold
        self.ok_speech_threshold = ok_speech_threshold

        self.platform = platform.system().lower()
        self.gpu = (device == 'cuda')

        if self.platform == "darwin":
            if device == "mps":
                log.warning(
                    "Using MPS for Mac, this does not work but may in the future"
                )
                device = "mps"
                device = torch.device(device)

        if (model != "large" and model != "large-v2") and self.english:
            model = model + ".en"
        
        log.info(f'Loading Whisper model {model}')
        self.audio_model = whisper.load_model(model, download_root=model_root).to(
            device
        )

        self.audio_queue = queue.Queue()
        self.last_result_time = (None, datetime.now())
        self.last_ok_text_time = ('', datetime.now())

        self.empty_results = ["", " ", "\n", None]
        self.mic_index  = mic_index
        self.islocked = False

        if self.mic_index is None:
            log.info("No mic index provided, using default")
        self.source = sr.Microphone(sample_rate=16000, device_index=self.mic_index)

        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = self.energy
        self.recorder.pause_threshold = self.pause
        self.recorder.dynamic_energy_threshold = self.dynamic_energy

        if not enabled:
            return

        with self.source:
            self.recorder.adjust_for_ambient_noise(self.source)

        self.recorder.listen_in_background(
            self.source, self.record_callback, phrase_time_limit=2
        )

        self.start()
    
    def start(self):
        self.thread = threading.Thread(target=self.transcribe_forever)
        self.thread.start()
        log.info("Transcribing, you can now talk")
    
    def stop(self):
        log.info("Stopping transcription thread...")
        self.thread.transcribe = False
        self.thread.join()
        log.info("Stopped transcribing, please wait to talk")
    
    def lock(self):
        self.islocked = True

    def locked(self):
        return self.islocked

    def unlock(self):
        self.islocked = False

    def preprocess(self, data):
        return torch.from_numpy(
            np.frombuffer(data, np.int16).flatten().astype(np.float32) / 32768.0
        )

    def get_all_audio(self, min_time: float = -1.0):
        audio = bytes()
        got_audio = False
        time_start = time.time()
        while not got_audio or time.time() - time_start < min_time:
            while not self.audio_queue.empty():
                audio += self.audio_queue.get()
                got_audio = True

        data = sr.AudioData(audio, 16000, 2)
        data = data.get_raw_data()
        return data

    def record_callback(self, _, audio: sr.AudioData) -> None:
        # check if locked
        if not self.locked():
            data = audio.get_raw_data()
            self.audio_queue.put_nowait(data)

    def transcribe_forever(self) -> None:
        while getattr(threading.current_thread(), "transcribe", True):
            try:
                self.transcribe()
            except Exception as e:
                log.error(e)
        log.debug(f'ended transcription loop')

    def transcribe(self, data=None, realtime: bool = False) -> None:
        if data is None:
            audio_data = self.get_all_audio()
        else:
            audio_data = data
        audio_data = self.preprocess(audio_data)
        if self.english:
            result = self.audio_model.transcribe(audio_data, fp16=self.gpu, language="english")
        else:
            result = self.audio_model.transcribe(audio_data, fp16=self.gpu)
        
        # remove repeated substrings
        result['text'] = re.sub(r"(.+?)\1+", r"\1", result['text'])

        if result['text'] not in self.empty_results:
            now = datetime.now()
            self.last_result_time = result, now

            # Check probabilities
            no_speech_probs = [s['no_speech_prob'] for s in result['segments']]
            ok_speech_probs = [math.exp(s['avg_logprob']) for s in result['segments']]
            any_no_speech = any(p > self.no_speech_threshold for p in no_speech_probs)
            all_ok_speech = all(p > self.ok_speech_threshold for p in ok_speech_probs)
            
            # Check text is new
            text = result['text'].strip()
            prev_text, prev_time = self.last_ok_text_time
            words, prev_words = tokenize(text), tokenize(prev_text)
            text_diff = editdistance.eval(words, prev_words)
            time_diff = (now - prev_time).seconds
            text_new = (text_diff > 2) or (time_diff > 5)

            for no, ok in zip(no_speech_probs, ok_speech_probs):
                log.info(f"Transcribed '{text}'; "
                            f"prob: no_speech={no:.2f}, ok={ok:.2f}; "
                            f"ok diff: text={text_diff}, time={time_diff}; ")
            
            if (not any_no_speech) and all_ok_speech and text_new:
                self.last_ok_text_time = (text, datetime.now())
                State.input('HEAR', text)

    def show(self):
        source = sr.Microphone(sample_rate=16000, device_index=self.mic_index)
        while True:
            try:
                with source:
                    buffer = source.stream.read(source.CHUNK)
                    energy = audioop.rms(buffer, source.SAMPLE_WIDTH)
                    rel = min(1, max(0, energy / 5000))
                    
                    w, h = MIC_IMG.size
                    im = Image.new("RGBA", (400,h))

                    # Draw microphone level
                    draw = ImageDraw.Draw(im)
                    draw.rectangle(((0, 0), (w-1, h)), fill=(0, 0, 0))
                    size = (h / 1.5) - int((h / 1.5) * rel)
                    color = (255, 0, 0) if self.locked() else (0, 128, 0)
                    draw.rectangle(((0, size), (w-1, h)), fill=color)
                    im.paste(MIC_IMG, mask=MIC_IMG)

                    # Draw last status
                    font = ImageFont.load_default()
                    result, last_time = self.last_result_time
                    if result:
                        time_str = f'{last_time:%H:%M:%S}'
                        draw.text((w+10, 6), time_str, font=font, fill=(0, 0, 0, 128))
                        text = result['text']
                        segs = result['segments']
                        draw.text((w+10, 24), text, font=font, fill=(0, 0, 0))
                        ok_prob = min([math.exp(s['avg_logprob']) for s in segs])
                        no_prob = max([s['no_speech_prob'] for s in segs])
                        ok = (ok_prob > self.ok_speech_threshold)
                        no = (no_prob < self.no_speech_threshold)
                        pcol = lambda x: (0, 128, 0) if x else (255, 0, 0)
                        ok_str = f'p(ok speech)={ok_prob:.2f}'
                        no_str = f'p(no speech)={no_prob:.2f}'
                        draw.text((w+10, 42), ok_str, font=font, fill=pcol(ok))
                        draw.text((w+150, 42), no_str, font=font, fill=pcol(no))
                    

                    arr = io.BytesIO()
                    im.save(arr, format="png")
                    frame = arr.getvalue()
                    yield (
                        b"--frame\r\n" b"Content-Type: image/png\r\n\r\n" + frame + b"\r\n"
                    )
            except Exception as e:
                log.error(e)
            time.sleep(0.01)
