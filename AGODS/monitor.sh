#!/bin/bash
sudo service agods stop
python3 ./detect_picamera.py --model ./agods.tflite --labels agods_labels.txt
sudo service agods start
