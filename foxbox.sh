#!/usr/bin/env bash

DIR=/home/pi/foxbox
. "$DIR"/env/bin/activate

exec python "$DIR"/downloader.py
