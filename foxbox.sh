#!/usr/bin/env bash

DIR=/home/pi/foxbox

cd "$DIR"

. env/bin/activate

exec python downloader.py -f ~/Videos
