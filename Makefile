SHELL := /bin/bash

.PHONY: dist

dist:
	rm -fr build/
	mkdir -p build/crabhi.foxbox
	cp addon.xml icon.png fanart.jpg main.py build/crabhi.foxbox
	cd build && zip -r crabhi.foxbox.zip crabhi.foxbox
