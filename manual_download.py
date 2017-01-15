import json
import sys
import os
import subprocess

data = json.load(sys.stdin)


directory = "/home/pi/Videos/" + data["serialy"]["-KaRjNMLXokj28lC9pQM"]["name"]
if not os.path.exists(directory):
    os.makedirs(directory)

for item in data["serialy"]["-KaRjNMLXokj28lC9pQM"]["playlist"]:
    print(item["comment"])
    file_link = item["file"].replace("http://", "hds://")
    file_name = os.path.join(directory, item["comment"] + ".flv")
    subprocess.call(["livestreamer", "-o", file_name, file_link, "--best"])
