#!/usr/bin/python
# -*- coding: utf-8 -*-
# /*
# *      Copyright (C) 2011 Silen
# *      Copyright (C) 2016 Crabhi
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# */

from __future__ import print_function

import re, os, urllib, cookielib, time
import urlparse

import signal
import subprocess
import socket, threading
import sys

import urllib2

try:
    import urllib3
    from urllib3.exceptions import HTTPError

    hasUrllib3 = True
except ImportError:
    from urllib2 import HTTPError

    hasUrllib3 = False

import series_list

import xbmc, xbmcgui, xbmcplugin, xbmcaddon

Addon = xbmcaddon.Addon(id='crabhi.foxbox')
icon = xbmc.translatePath(os.path.join(Addon.getAddonInfo('path'), 'icon.png'))
fcookies = xbmc.translatePath(os.path.join(Addon.getAddonInfo('path'), r'resources', r'data', r'cookies.txt'))

h = int(sys.argv[1])

host_url = 'https://my-hit.org'
movie_url = None


def showMessage(heading, message, times=3000):
    xbmc.executebuiltin('XBMC.Notification("%s", "%s", %s, "%s")' % (heading, message, times, icon))


def top_list(params):
    series = series_list.get_all()

    if "web_url" not in params:
        return list_all(series)

    else:
        serie, = [m for m in series if m["web_url"] == params["web_url"][0]]
        playlist_path = params.get("playlist_path", [])

        item = {
            "name": serie["name"],
            "img": serie["img"],
            "web_url": serie["web_url"],
            "playlist": serie["playlist"]
        }

        for i in playlist_path:
            playlist_part = item["playlist"][int(i)]

            item["name"] = playlist_part["comment"]
            item["img"] = playlist_part["poster"]
            item["playlist"] = playlist_part["playlist"]

        list_serie(item, playlist_path)


def list_all(series):
    for ser in series:
        i = xbmcgui.ListItem(ser["name"], thumbnailImage=ser.get("img", None))

        u = sys.argv[0] + '?' + urllib.urlencode({
            "mode": "LIST",
            "web_url": ser["web_url"]
        })

        i.setProperty('fanart_image', ser.get("img", None))
        xbmcplugin.addDirectoryItem(h, u, i, isFolder=True)

    xbmcplugin.endOfDirectory(h)


def list_serie(serie_item, current_playlist_path):
    # print(serie_item, current_playlist_path)

    for i, ser in enumerate(serie_item["playlist"]):
        name = ser["comment"]

        if "poster" in ser:
            img = urlparse.urljoin(serie_item["web_url"], ser["poster"])
        else:
            img = serie_item["img"]

        x_item = xbmcgui.ListItem(name, thumbnailImage=img)

        ppath = [("playlist_path", p) for p in current_playlist_path + [i]]

        if "file" in ser:
            params = [("mode", "PLAY"),
                      ("file", ser["file"]),
                      ("img", img.encode("utf-8")),
                      ("name", name.encode("utf-8"))]
            folder = False
            x_item.setInfo(type='video', infoLabels={'title': name.encode("utf-8")})

        else:
            params = ppath + [("mode", "LIST"),
                              ("web_url", serie_item["web_url"])]
            folder = True

        u = sys.argv[0] + '?' + urllib.urlencode(params)
        x_item.setProperty('fanart_image', img)
        xbmcplugin.addDirectoryItem(h, u, x_item, isFolder=folder)

    xbmcplugin.endOfDirectory(h)


def PLAY(params):
    movie_url = params['file'][0]
    img = params['img'][0].decode("utf-8")
    name = params['name'][0].decode("utf-8")

    # TODO: specific for Adobe HDS stream
    hds_url = re.sub("https?", "hds", movie_url)

    player = ProxyPlayer()
    player.initialize(hds_url, name, img)
    player.play_start()


class ProxyPlayer(xbmc.Player):

    def __init__(self):
        xbmc.Player.__init__(self)

    def initialize(self, url, name, img):
        self.url = url
        self.name = name
        self.img = img

        self.stop = False

        self.proxy_thread = threading.Thread(target=self._proxy)
        self.proxy_ready = threading.Event()

    def _proxy(self):
        PID_FILE = os.path.expanduser("~/livestreamer.pid")

        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                old_process = f.read().strip()

            if old_process != "":
                try:
                    os.kill(int(old_process), signal.SIGKILL)
                except:
                    pass

        self.port = get_empty_port()

        self.process = subprocess.Popen(["livestreamer",
                                         "--player-external-http",
                                         "--player-external-http-port", str(self.port),
                                         "--best",
                                         self.url])

        with open(PID_FILE, "w") as f:
            print(self.process.pid, file=f)

        self.proxy_ready.set()

        while self.process.poll() is None:
            if self.stop:
                self.process.kill()
                break

            time.sleep(1)

        print("Player thread exiting")

    def play_start(self):
        self.proxy_thread.start()
        self.proxy_ready.wait()

        time.sleep(5)

        video = 'http://localhost:{}/'.format(self.port)
        i = xbmcgui.ListItem(self.name, path=urllib.unquote(video), thumbnailImage=self.img)
        self.play(video, i)

    def onPlayBackEnded(self):
        print("FoxBox onPlaybackEnded")
        self.stop = True

    def onPlayBackStopped(self):
        print("FoxBox onPlaybackStopped")
        self.stop = True


def get_empty_port():
    """
    :return: Port that is empty at the moment. Note - there is a race condition. When this function returns, the port
             may already be occupied.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    addr, port = s.getsockname()
    s.close()
    return port


# -------------------------------------------------------------------------------
if __name__ == '__main__':
    xbmc.log("Foxbox " + str(sys.argv))

    par_string = sys.argv[2][1:] if sys.argv[2].startswith("?") else sys.argv[2]
    params = urlparse.parse_qs(par_string)

    # get cookies from last session
    cj = cookielib.FileCookieJar(fcookies)
    hr = urllib2.HTTPCookieProcessor(cj)
    opener = urllib2.build_opener(hr)
    urllib2.install_opener(opener)

    mode = params.get("mode", ["LIST"])[0]

    {
        "PLAY": PLAY,
        "LIST": top_list
    }[mode](params)
