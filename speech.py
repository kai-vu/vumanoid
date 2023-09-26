import rlvoice
import logging
import time

log = logging.getLogger(__name__)

class SpeechProduction:
    def __init__(self, audio=None, rate=None, enabled=True, **kwargs):
        self.audio = audio
        self.enabled = enabled

        if self.enabled:
            log.info('Loading text-to-speech...')
            self.engine = rlvoice.init(**kwargs)
            if rate:
                self.engine.setProperty('rate', rate)
            log.info(f'Text-to-speech loaded: {self.engine.getProperty("voice")}')
    
    def speak(self, text):
        if self.enabled:
            if self.audio:
                self.audio.lock()
                time.sleep(0.5)
            log.debug(f'Saying {text}')
            self.engine.say(text)
            self.engine.runAndWait()
            if self.audio:
                time.sleep(0.5)
                self.audio.unlock()