from gpiozero import MotionSensor, LED
from signal import pause
from time import sleep
from configparser import ConfigParser

import argparse
import sys

# Suppress TimeLoop's job start/stop messages on stdout
import logging

### Handle Command Line Arguments ###
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False)
parser.add_argument(
    '--config', help='Configuration file.',
    required=False)
parser.add_argument(
    '--debug', help='Enable degugging output.',
    required=False,
    action='store_true')
parser.add_argument(
    '--help', help='Print help message.',
    required=False,
    action='store_true')
args = parser.parse_args()


HELP = """
usage: motion_detect.py [arg] ...
Options and arguments:
--debug     : Provides console output on motion detection
--help      : Print this help message and exit
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

LOGGING           = conf.get("Other","logging")
LOG_FILE          = conf.get("Other","log_file")


#Defaults if not set
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

### Motion Detection ###
pir = MotionSensor(27)
led = LED(4)
alarm = LED(22)

def motion():
        led.on()
        alarm.on()
        if DEBUG:
          print("Motion Detected")
        if LOGGING:
          logging.info("Motion Detected")
        sleep(2)

def noMotion():
     led.off()
     alarm.off()

pir.when_motion = motion
pir.when_no_motion = noMotion
#// Motion Detection //#


pause()
