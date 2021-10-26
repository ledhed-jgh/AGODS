from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gpiozero import LED
from time import sleep
from annotation import Annotator
from PIL import Image
from tflite_runtime.interpreter import Interpreter
from configparser import ConfigParser

import time
import argparse
import io
import re
import sys
import logging
import numpy as np
import picamera
import picamera.array


### Motion Detection ###
alarm = LED(22)

### Handle Command Line Arguments ###
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False)
parser.add_argument(
    '--model', help='File path of .tflite file.',
    required=False)
parser.add_argument(
    '--labels', help='File path of labels file.',
    required=False)
parser.add_argument(
    '--threshold',
    help='Score threshold for detected objects.',
    required=False,
    type=float)
parser.add_argument(
    '--config', help='Configuration file.',
    required=False)
parser.add_argument(
    '--image', help='Image output path and file name.',
    required=False,
    default='agods.jpg')
parser.add_argument(
    '--debug', help='Enable degugging output.',
    required=False,
    action='store_true')
parser.add_argument(
    '--interval', help='Object Detection interval in seconds.',
    required=False,
    type=int)
parser.add_argument(
    '--help', help='Print help message.',
    required=False,
    action='store_true')
args = parser.parse_args()

HELP = """
usage: agods.py [arg] ...
Options and arguments:
--config     : User specified config file (default: /boot/agods.ini)
--debug      : Provides console output and image output for troubleshooting
               and camera alignment
--help       : Print this help message and exit
--image      : Alternative path to save degug image (default: agods.jpg)
--interval   : Object Detection interval in seconds (default: 60)
--labels     : Path to TensorFlow labels file (default: agods_labels.txt)
--model      : Path to TensorFlow model file (default: agods.tflite)
--threshold  : Object Detection confidence threshold (default: 0.5)
"""

if args.help:
  print(HELP)
  sys.exit()

### Vars from Config file ###
conf = ConfigParser()
if args.config is not None:
  conf.read(args.config)
else:
  conf.read('/boot/agods.ini')

CAMERA_HEIGHT     = int(conf.get("Camera","height"))
CAMERA_WIDTH      = int(conf.get("Camera","width"))
CAMERA_ROTATION   = int(conf.get("Camera","rotation"))
CAMERA_BRIGHTNESS = int(conf.get("Camera","brightness"))
OD_THRESHOLD      = float(conf.get("Object Detection","threshold"))
OD_LABELS         = conf.get("Object Detection","label_file")
OD_MODELS         = conf.get("Object Detection","model_file")
OD_CATEGORIES     = [float(x) for x in conf.get("Object Detection","categories").strip().split(",")]
OD_INTERVAL       = int(conf.get("Object Detection","interval"))
LOGGING           = conf.get("Other","logging")
LOG_FILE          = conf.get("Other","log_file")


### TensorFlow Vars ###
if args.labels is not None: OD_LABELS = args.labels
if args.model is not None: OD_MODELS = args.model
if args.threshold is not None: OD_THRESHOLD = args.threshold
if args.interval is not None: OD_INTERVAL = args.interval
if args.image is not None: IMAGE_PATH = args.image


#Defaults if not set
if OD_THRESHOLD is None: OD_THRESHOLD = 0.5
if OD_LABELS is None: OD_LABELS = 'agods_labels.txt'
if OD_MODELS is None: OD_MODELS = 'agods.tflite'
if OD_CATEGORIES is None: OD_CATEGORIES = [0.0]
if OD_INTERVAL is None: OD_INTERVAL = 60
if CAMERA_WIDTH is None: CAMERA_WIDTH = 640
if CAMERA_HEIGHT is None: CAMERA_HEIGHT = 368
if CAMERA_ROTATION is None: CAMERA_ROTATION = 0
if CAMERA_BRIGHTNESS is None: CAMERA_BRIGHTNESS = 50
if LOGGING is None: LOGGING = False
if LOG_FILE is None: LOG_FILE = '/var/log/agods.log'

DEBUG = args.debug

### Logging ###
if LOGGING:
  logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    level=logging.DEBUG)

def load_labels(path):
  """Loads the labels file. Supports files with or without index numbers."""
  with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    labels = {}
    for row_number, content in enumerate(lines):
      pair = re.split(r'[:\s]+', content.strip(), maxsplit=1)
      if len(pair) == 2 and pair[0].strip().isdigit():
        labels[int(pair[0])] = pair[1].strip()
      else:
        labels[row_number] = pair[0].strip()
  return labels


def set_input_tensor(interpreter, image):
  """Sets the input tensor."""
  tensor_index = interpreter.get_input_details()[0]['index']
  input_tensor = interpreter.tensor(tensor_index)()[0]
  input_tensor[:, :] = image


def get_output_tensor(interpreter, index):
  """Returns the output tensor at the given index."""
  output_details = interpreter.get_output_details()[index]
  tensor = np.squeeze(interpreter.get_tensor(output_details['index']))
  return tensor


def detect_objects(interpreter, image, threshold, categories):
  """Returns a list of detection results, each a dictionary of object info."""
  set_input_tensor(interpreter, image)
  interpreter.invoke()

  # Get all output details
  boxes = get_output_tensor(interpreter, 0)
  classes = get_output_tensor(interpreter, 1)
  scores = get_output_tensor(interpreter, 2)
  count = int(get_output_tensor(interpreter, 3))

  results = []
  for i in range(count):
    if classes[i] in categories and scores[i] >= threshold:
      result = {
          'bounding_box': boxes[i],
          'class_id': classes[i],
          'score': scores[i]
      }
      results.append(result)
  return results


def annotate_objects(annotator, results, labels):
  """Draws the bounding box and label for each object in the results."""
  for obj in results:
    # Convert the bounding box figures from relative coordinates
    # to absolute coordinates based on the original resolution
    ymin, xmin, ymax, xmax = obj['bounding_box']
    xmin = int(xmin * CAMERA_WIDTH)
    xmax = int(xmax * CAMERA_WIDTH)
    ymin = int(ymin * CAMERA_HEIGHT)
    ymax = int(ymax * CAMERA_HEIGHT)

    # Overlay the box, label, and score on the camera preview
    annotator.bounding_box([xmin, ymin, xmax, ymax])
    annotator.text([xmin, ymin], '%s\n%.2f' % (labels[obj['class_id']], obj['score']))

def object_detection():
  load_labels(OD_LABELS)
  interpreter = Interpreter(OD_MODELS)
  interpreter.allocate_tensors()
  _, input_height, input_width, _ = interpreter.get_input_details()[0]['shape']

  with picamera.PiCamera() as camera:
      camera.resolution = (CAMERA_WIDTH, CAMERA_HEIGHT)
      camera.rotation = CAMERA_ROTATION
      camera.brightness = CAMERA_BRIGHTNESS

      with picamera.array.PiRGBArray(camera) as output:
          camera.start_preview()
          sleep(2) 
          #camera.exposure_mode = 'auto'
          #camera.exposure_mode = 'off'
          camera.capture(output, 'rgb', use_video_port=False)
          camera.stop_preview()
          try:
            annotator = Annotator(camera)

            image = Image.fromarray(output.array)
            if DEBUG:
              image.save(IMAGE_PATH)
            image = image.resize((300, 300), Image.NEAREST)

            start_time = time.monotonic()
            results = detect_objects(interpreter, image, OD_THRESHOLD, OD_CATEGORIES)
            elapsed = (time.monotonic() - start_time)

            object_count = 0
            for obj in results:
              object_count +=1

            if object_count > 0:
              if DEBUG:
                print("Detections:" + str(object_count) + ", " + str(round(elapsed, 2)) + " Sec elapsed")
              if LOGGING:
                logging.info("Detections:" + str(object_count) + ", " + str(round(elapsed, 2)) + " Sec elapsed")
              alarm.on()
              sleep(2)
              alarm.off()

          except Exception as e:
            logging.error('Error at %s', 'division', exc_info=e)

          finally:
            output.truncate(0)
#// Object Detection //#


if __name__ == "__main__":
  logging.info("AGODS Service Started")
  while True:
    object_detection()
    sleep(OD_INTERVAL)
