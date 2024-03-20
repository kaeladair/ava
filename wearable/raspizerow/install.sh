#!/bin/bash
cd ~
sudo apt-get -y update
sudo apt-get -y upgrade
sudo apt-get -y install python3-dev
sudo apt-get -y install libasound2-dev
sudo apt install -y python3-pip
sudo pip3 install numpy
sudo pip3 install requests
sudo pip3 install pyaudio

sudo pip3 install --upgrade adafruit-python-shell
wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/i2smic.py
sudo python3 i2smic.py

read -p "Enter your Supabase URL: " supabase_url
read -p "Enter your Auth Token: " auth_token
sudo sh -c "echo \"SUPABASE_URL=$supabase_url\" >> /etc/environment"
sudo sh -c "echo \"AUTH_TOKEN=$auth_token\" >> /etc/environment"

echo "Setup complete. Please reboot your device for the changes to take effect."