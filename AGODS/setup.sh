#!/bin/bash
# Install Dependencies
sudo apt update && sudo apt -y install git libopenjp2-7 libtiff5 python3 python3-pip python3-pip python3-pil python3-picamera

# Add coral repo
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list

# Add google gpg key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

# Install TensorFlow Lite
sudo apt update && sudo apt -y install python3-tflite-runtime

# Move INI file to /boot
sudo chmod 755 agods.ini
sudo chown root.root agods.ini
sudo mv agods.ini /boot/

# Move logrotate file
sudo chmod 644 agods.logrotate
sudo chown root.root agods.logrotate
sudo mv agods.logrotate /etc/logrotate.d/agods

# Setup Services
sudo chmod 755 *.service
sudo chown root.root *.service
sudo mv *.service /etc/systemd/system/
sudo systemctl enable disable-led.service agods.service pir.service

# Disable Camera LED
echo -e "\n# Camera\nstart_x=1\ngpu_mem=128\ndisable_camera_led=1" | sudo tee -a /boot/config.txt > /dev/null

echo -e
echo -e "Remember to run:\n\tsudo raspi-config\nand enable Overlay File system under 'Performance Options'"

echo -e
echo "AGODS Setup Complete"
echo -e
