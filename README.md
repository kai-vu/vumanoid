# VUmanoid 🤖

Starter code for Vrije Universiteit Intro to AI creative crafting / hackathon day.

## Installation

Create and activate an virtual environment, as follows:

```bash
$ git clone git@github.com:kai-vu/vumanoid.git
$ cd vumanoid/
$ python -m venv env
$ source env/bin/activate
```

After have installed and activated the environment, install all the dependencies:

```bash
$ pip install -r requirements.txt
```

After that, you can run the _following command_ and access the application at [127.0.0.1:5000](http://127.0.0.1:5000/) on your browser.

```bash
$ python application.py
```

## Download model

To download the `yolov3.weights`, just run:

```bash
$ cd models/
$ python dl-weights.py
```

## Credits
Many thanks to the following projects:

- https://github.com/diegoinacio/object-detection-flask-opencv
- https://github.com/mallorbc/whisper_mic/
- https://github.com/Akul-AI/rlvoice-1/