from PIL import Image, ImageDraw, ImageFont
import serial
import io
import time
import logging
import serial.tools.list_ports

log = logging.getLogger(__name__)
BOARD_IMG = Image.open("static/arduino.png").convert("RGBA")
def get_pin_img_pos(pin_number, analog=False):
    offset = pin_number * 15
    if analog:
        return (361 + offset, 312)
    else:
        return (434 - offset, 40) if (pin_number < 8) else (422 - offset, 40)

ports = [p.name for p in serial.tools.list_ports.comports()]
print('List of ports:')
print(ports)

class Arduino():
    """
    Models an Arduino connection
    """

    def __init__(self, enabled = True, serial_port=None, baud_rate=9600,
            read_timeout=5, pin_modes = ()):
        """
        Initializes the serial connection to the Arduino board
        """
        self.pin_modes = {}
        if enabled:
            try:
                self.conn = serial.Serial(serial_port, baud_rate)
                self.conn.timeout = read_timeout # Timeout for readline()
                if pin_modes:
                    for pin, mode in pin_modes.items():
                        self.set_pin_mode(pin, mode)

            except Exception as e:
                enabled = False
                log.error(e)
            
            
    def set_pin_mode(self, pin_number, mode):
        """
        Performs a pinMode() operation on pin_number
        Internally sends b'M{mode}{pin_number} where mode could be:
        - I for INPUT
        - O for OUTPUT
        - P for INPUT_PULLUP
        """
        command = (''.join(('M',mode,str(pin_number)))).encode()
        log.info(f"Writing {command}")
        self.conn.write(command)
        self.pin_modes[pin_number] = mode

    def digital_read(self, pin_number):
        """
        Performs a digital read on pin_number and returns the value (1 or 0)
        Internally sends b'RD{pin_number}' over the serial connection
        """
        command = (''.join(('RD', str(pin_number)))).encode()
        self.conn.write(command)
        log.info(f"Writing {command}")
        line_received = self.conn.readline().decode().strip()
        log.info(f"Read {line_received}")
        header, value = line_received.split(':') # e.g. D13:1
        if header == ('D'+ str(pin_number)):
            # If header matches
            return int(value)

    def digital_write(self, pin_number, digital_value):
        """
        Writes the digital_value on pin_number
        Internally sends b'WD{pin_number}:{digital_value}' over the serial
        connection
        """
        command = (''.join(('WD', str(pin_number), ':',
            str(digital_value)))).encode()
        log.info(f"Writing {command}")
        self.conn.write(command) 
     
    def analog_read(self, pin_number):
        """
        Performs an analog read on pin_number and returns the value (0 to 1023)
        Internally sends b'RA{pin_number}' over the serial connection
        """
        command = (''.join(('RA', str(pin_number)))).encode()
        self.conn.write(command) 
        log.info(f"Writing {command}")
        line_received = self.conn.readline().decode().strip()
        log.info(f"Read {line_received}")
        header, value = line_received.split(':') # e.g. A4:1
        if header == ('A'+ str(pin_number)):
            # If header matches
            return int(value)

    def analog_write(self, pin_number, analog_value):
        """
        Writes the analog value (0 to 255) on pin_number
        Internally sends b'WA{pin_number}:{analog_value}' over the serial
        connection
        """
        command = (''.join(('WA', str(pin_number), ':',
            str(analog_value)))).encode()
        log.info(f"Writing {command}")
        self.conn.write(command) 

    def show(self):
        while True:
            im = BOARD_IMG
            draw = ImageDraw.Draw(im)
            font = ImageFont.load_default()
            
            for pin, mode in self.pin_modes.items():
                x, y = get_pin_img_pos(pin, analog=False)
                draw.text((x+8, y-30), mode, font=font, fill=(0, 0, 0))

            arr = io.BytesIO()
            im.save(arr, format="png")
            frame = arr.getvalue()
            yield (
                b"--frame\r\n" b"Content-Type: image/png\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.01)


if __name__ == '__main__':

    import time

    a = Arduino(serial_port='/dev/cu.usbmodem142301')
    time.sleep(3)
    a.set_pin_mode(13,'O')
    for i in range(100):
        a.digital_write(13, (i % 2))
        time.sleep(0.2)
    a.set_pin_mode(12,'I')
    time.sleep(1)
    a.digital_write(13,1)
    a.analog_write(5,245)
    print(a.digital_read(12))
    print(a.analog_read(2))
    time.sleep(5)
