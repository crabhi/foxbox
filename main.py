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

import BaseHTTPServer
import socket, threading
import sys, json

import binascii
import struct
import base64
import math
import xml.etree.ElementTree
import xml.sax
import string
import unicodedata
import Queue
import thread

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


def get_HTML(url, post=None, ref=None):
    # xbmc.log(url)

    request = urllib2.Request(url, post)

    host = urlparse.urlsplit(url).hostname

    request.add_header('User-Agent',
                       'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)')
    request.add_header('Host', host)
    request.add_header('Accept', '*/*')
    request.add_header('Accept-Language', 'ru-RU')
    request.add_header('Referer', ref)

    try:
        f = urllib2.urlopen(request)
    except IOError, e:
        if hasattr(e, 'reason'):
            xbmc.log('We failed to reach a server.')
        elif hasattr(e, 'code'):
            xbmc.log('The server couldn\'t fulfill the request.')

    html = f.read()

    return html


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
    global movie_url, IP_ADDRESS, PORT_NUMBER, PROXY_THREADS
    # -- parameters
    movie_url = urllib.unquote_plus(params['file'][0])
    img = urllib.unquote_plus(params['img'][0]).decode("utf-8")
    name = urllib.unquote_plus(params['name'][0]).decode("utf-8")

    print(locals())

    # xbmc.log('-------------')
    # xbmc.log(type_)

    # -- run video Proxy server ---
    t = threading.Thread(target=VideoProxy)
    t.start()

    SERVER_STARTED.wait()



    # -- wait and play video ------
    # time.sleep(5)
    player = AdobeHDS_Player()
    player.Init(movie_url, name, img)
    player.play_start()


class AdobeHDS_Player(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self)

    def Init(self, url, name, img):
        self.url = url
        self.name = name
        self.img = img

    def play_start(self):
        video = 'http://{}:{}/?video={}'.format(IP_ADDRESS, PORT_NUMBER, base64.urlsafe_b64encode(self.url))
        i = xbmcgui.ListItem(self.name, path=urllib.unquote(video), thumbnailImage=self.img)
        self.play(video, i)

    def __del__(self):
        pass


# -------------------------------------------------------------------------------
# -------------------------------------------------------------------------------
IP_ADDRESS = '127.0.0.1'
PORT_NUMBER = 18899
PROXY_THREADS = 7

pSocket = None

SERVER_STARTED = threading.Event()


# -------------------------------------------------------------------------------
class GetUrl(object):
    def __init__(self, url, fragnum):
        self.url = url
        self.fragNum = fragnum
        self.data = None
        self.decode = None
        self.errCount = 0


QueueUrl = Queue.PriorityQueue()
QueueUrlDone = Queue.PriorityQueue()

M6Item = None
prevAudioTS = -1;
prevVideoTS = -1;
baseTS = 0;


def workerRun():
    global QueueUrl, QueueUrlDone, M6Item, PROXY_THREADS
    while not QueueUrl.empty() and M6Item.status == 'DOWNLOADING' and QueueUrlDone.qsize() < int(PROXY_THREADS) * 3:
        item = QueueUrl.get()[1]
        # print 'Processing Fragment: ',item.fragNum
        fragUrl = item.url
        try:
            item.data = M6Item.getFile(fragUrl)
            QueueUrlDone.put((item.fragNum, item))
            # print fragUrl
        except HTTPError, e:
            xbmc.log(str(e))
            if item.errCount > 3:
                M6Item.status = 'STOPPED'
                # raise
            else:
                item.errCount += 1
                QueueUrl.put((item.fragNum, item))
        QueueUrl.task_done()
    # If we have exited the previous loop with error
    while not QueueUrl.empty():
        # print 'Ignore fragment', QueueUrl.get()[1].fragNum
        QueueUrl.get()


def worker():
    global M6Item
    try:
        workerRun()
    except Exception, e:
        print('ERROR worker', e)
        M6Item.status = 'STOPPED'
        thread.interrupt_main()


def workerqdRun():
    global QueueUrlDone, M6Item
    currentFrag = 1
    while currentFrag <= M6Item.nbFragments and M6Item.status == 'DOWNLOADING':
        item = QueueUrlDone.get()[1]
        # print 'Done Fragment: ' + str(item.fragNum)
        if currentFrag == item.fragNum:
            # M6Item.verifyFragment(item.data)
            if not M6Item.decodeFragment(item):
                raise Exception('decodeFrament')
            M6Item.videoFragment(item.fragNum, item.decode)
            # print 'Fragment', currentFrag, 'OK'
            currentFrag += 1
            requeue = False
        else:
            # print 'Requeue', item.fragNum
            QueueUrlDone.put((item.fragNum, item))
            requeue = True
        QueueUrlDone.task_done()
        if requeue:
            time.sleep(1)
    # If we have exited the previous loop with error
    if currentFrag > M6Item.nbFragments:
        M6Item.status = 'COMPLETED'
    else:
        while not QueueUrlDone.empty():
            # print 'Ignore fragment', QueueUrlDone.get()[1].fragNum
            pass


def workerqd():
    global M6Item
    try:
        workerqdRun()
    except Exception, e:
        # print 'ERROR workerqd'
        M6Item.status = 'STOPPED'
        thread.interrupt_main()


validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)


def removeDisallowedFilenameChars(filename):
    "Remove invalid filename characters"
    filename = filename.decode('ASCII', 'ignore')
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    cleanedFilename = cleanedFilename.replace(' ', '_')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)


class M6(object):
    def __init__(self, url, dest='', proxy=None):
        self.status = 'INIT'
        self.url = url
        self.proxy = proxy
        self.bitrate = 0
        self.duration = 0
        self.nbFragments = 0
        self.tagHeaderLen = 11
        self.prevTagSize = 4

        urlp = urlparse.urlparse(url)

        fn = os.path.basename(urlp.path)
        self.localfilename = \
            os.path.join(dest, os.path.splitext(fn)[0]) + '.flv'
        self.localfilename = removeDisallowedFilenameChars(self.localfilename)
        self.urlbootstrap = ''
        self.bootstrapInfoId = ''
        self.baseUrl = urlparse.urlunparse((urlp.scheme, urlp.netloc,
                                            os.path.dirname(urlp.path),
                                            '', '', ''))
        if hasUrllib3:
            self.pm = urllib3.PoolManager(num_pools=100)

        self.html = self.getManifest(self.url)
        self.manifest = xml.etree.ElementTree.fromstring(self.html)
        self.parseManifest()
        # self.pm = urllib3.connection_from_url(self.urlbootstrap)
        # ---
        global prevAudioTS
        global prevVideoTS
        global baseTS

        prevAudioTS = -1
        prevVideoTS = -1
        baseTS = 0

        # print '#################'

    def download(self):
        global QueueUrl, QueueUrlDone, M6Item, PROXY_THREADS
        M6Item = self
        self.status = 'DOWNLOADING'
        # print self.status
        # print 'nbFragments:   '+ str(self.nbFragments)
        # print 'PROXY_THREADS: '+ str(PROXY_THREADS)
        # self.outFile = open(self.localfilename, "wb")

        for i in range(self.nbFragments):
            fragUrl = self.urlbootstrap + 'Seg1-Frag' + str(i + 1)
            # xbmc.log(fragUrl)
            QueueUrl.put((i + 1, GetUrl(fragUrl, i + 1)))

        # print '[Queue len]:   '+ str(QueueUrl.qsize())

        t = threading.Thread(target=workerqd)
        # t.daemon = True
        t.start()
        # print 'Proxy process run'

        for i in range(int(PROXY_THREADS)):
            # print 'Run downloader '+ str(i)
            t = threading.Thread(target=worker)
            # t.daemon = True
            t.start()

        # QueueUrl.join()
        # QueueUrlDone.join()
        while self.status == 'DOWNLOADING':
            try:
                # print '[Queue len]:   '+ str(QueueUrl.qsize())
                time.sleep(3)
            except (KeyboardInterrupt, Exception), e:
                print(e)
                self.status = 'STOPPED'
        # self.outFile.close()
        if self.status != 'STOPPED':
            self.status = 'COMPLETED'

    def getInfos(self):
        infos = {}
        infos['status'] = self.status
        infos['localfilename'] = self.localfilename
        infos['proxy'] = self.proxy
        infos['url'] = self.url
        infos['bitrate'] = self.bitrate
        infos['duration'] = self.duration
        infos['nbFragments'] = self.nbFragments
        infos['urlbootstrap'] = self.urlbootstrap
        infos['baseUrl'] = self.baseUrl
        infos['drmId'] = self.drmAdditionalHeaderId
        return infos

    def getFile(self, url):
        txheaders = {'User-Agent':
                         'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:17.0) Gecko/20100101 Firefox/17.0',
                     'X-DevTools-Emulate-Network-Conditions-Client-Id': '22D8BD39-46AD-4AE2-8BCA-4FDDCD99E9B2',
                     'Keep-Alive': '600',
                     'Connection': 'keep-alive'
                     }
        request = urllib2.Request(url, None, txheaders)
        response = urllib2.urlopen(request)
        return response.read()

    def getManifest(self, url):
        self.status = 'GETTING MANIFEST'
        return self.getFile(url)  # xml.etree.ElementTree.fromstring(self.getFile(url))

    def parseManifest(self):
        self.status = 'PARSING MANIFEST'
        try:
            root = self.manifest
            # Duration
            self.duration = float(root.find("{http://ns.adobe.com/f4m/1.0}duration").text)
            # nombre de fragment"
            self.nbFragments = int(math.ceil(self.duration / 3))
            # streamid
            self.streamid = root.findall("{http://ns.adobe.com/f4m/1.0}media")[-1]
            # media
            self.media = None
            for media in root.findall('{http://ns.adobe.com/f4m/1.0}media'):
                if int(media.attrib['bitrate']) > self.bitrate:
                    self.media = media
                    self.bitrate = int(media.attrib['bitrate'])
                    self.bootstrapInfoId = media.attrib['bootstrapInfoId']

                    try:
                        self.drmAdditionalHeaderId = media.attrib['drmAdditionalHeaderId']
                    except:
                        self.drmAdditionalHeaderId = None

                    self.flvHeader = base64.b64decode(media.find("{http://ns.adobe.com/f4m/1.0}metadata").text)
            # Bootstrap URL
            self.urlbootstrap = self.media.attrib["url"]
            # urlbootstrap
            self.urlbootstrap = self.baseUrl + "/" + self.urlbootstrap
        except Exception, e:
            print("Not possible to parse the manifest")
            print(e)
            sys.exit(-1)

    def stop(self):
        self.status = 'STOPPED'

    def videoFragment(self, fragNum, data):
        global pSocket
        start = M6Item.videostart(fragNum, data)
        if fragNum == 1:
            self.videoBootstrap()
        pSocket.wfile.write(data[start:])

    def videoBootstrap(self):
        global pSocket
        bootstrap = "464c560105000000090000000012"
        bootstrap += "%06X" % (len(self.flvHeader),)
        bootstrap += "%06X%08X" % (0, 0)
        pSocket.wfile.write(binascii.a2b_hex(bootstrap))
        pSocket.wfile.write(self.flvHeader)
        pSocket.wfile.write(binascii.a2b_hex("%08X" % (len(self.flvHeader) + 11)))
        # pSocket.wfile.write(binascii.a2b_hex("000002cf0800000400000000000000af0011900000000f0800020200000000")) # 00019209

    def videostart(self, fragNum, fragData):
        start = fragData.find("mdat") + 4
        '''
        if (fragNum == 1):
            start = fragData.find("mdat") + 12
            start += 0
        else:
            start = fragData.find("mdat") + 4

        start = fragData.find("mdat") + 12
        # For all fragment (except frag1)
        if (fragNum == 1):
            start += 0
        else:
            # Skip 2 FLV tags
            tagLen, = struct.unpack_from(">L", fragData, start)  # Read 32 bits (big endian)
            tagLen &= 0x00ffffff  # Take the last 24 bits
            start += tagLen + self.tagHeaderLen + 4 +18 # 11 = tag header len ; 4 = tag footer len  +18
        '''
        return start

    def readBoxHeader(self, data, pos=0):
        boxSize, = struct.unpack_from(">L", data,
                                      pos)  # Read 32 bits (big endian)struct.unpack_from(">L", data, pos)  # Read 32 bits (big endian)
        boxType = data[pos + 4: pos + 8]
        if boxSize == 1:
            boxSize, = struct.unpack_from(">Q", data, pos + 8)  # Read 64 bits (big endian)
            boxSize -= 16
            pos += 16
        else:
            boxSize -= 8
            pos += 8
        if boxSize <= 0:
            boxSize = 0
        return (pos, boxType, boxSize)

    def verifyFragment(self, data):
        pos = 0
        fragLen = len(data)
        while pos < fragLen:
            pos, boxType, boxSize = self.readBoxHeader(data, pos)
            if boxType == 'mdat':
                slen = len(data[pos:])
                # print 'mdat %s' % (slen,)
                if boxSize and slen == boxSize:
                    return True
                else:
                    boxSize = fragLen - pos
            pos += boxSize
        return False

    def decodeFragment(self, item):
        item.decode = 'mdat'

        global prevAudioTS
        global prevVideoTS
        global baseTS

        fragPos = 0
        fragLen = len(item.data)
        if not self.verifyFragment(item.data):
            # print "Skipping fragment number", item.fragNum
            return False
        while fragPos < fragLen:
            fragPos, boxType, boxSize = self.readBoxHeader(item.data, fragPos)
            if boxType == 'mdat':
                # fragLen = fragPos + boxSize   # !!!
                break
            fragPos += boxSize

        cnt = 1
        while fragPos < fragLen:
            packetType = self.readInt8(item.data, fragPos)
            packetSize = self.readInt24(item.data, fragPos + 1)
            packetTS = self.readInt24(item.data, fragPos + 4)
            packetTS |= self.readInt8(item.data, fragPos + 7) << 24

            if packetTS & 0x80000000:
                packetTS &= 0x7FFFFFFF
                # ---
                struct.pack_into(">L", item.data, fragPos, int(packetTS & 0x00FFFFFF))
                struct.pack_into(">c", item.data, fragPos, ((packetTS & 0xFF000000) >> 24))

            if (baseTS == 0 and ((packetType == 0x08) or (packetType == 0x09))):
                baseTS = packetTS

            if (baseTS > 1000):
                packetTS -= baseTS;
                # ---
                struct.pack_into(">L", item.data, fragPos, int(packetTS & 0x00FFFFFF))
                struct.pack_into(">c", item.data, fragPos, ((packetTS & 0xFF000000) >> 24))

            totalTagLen = self.tagHeaderLen + packetSize + self.prevTagSize
            # -- save decoded data
            if packetSize > 32:
                if packetType == 0x08 and packetTS >= prevAudioTS - 8 * 5:  # -- AUDIO  (time_code duration = 8)
                    item.decode += item.data[fragPos:fragPos + totalTagLen]
                    cnt += 1
                    prevAudioTS = packetTS
                elif packetType == 0x09 and packetTS >= prevVideoTS - 8 * 5:  # -- VIDEO  (time_code duration = 8)
                    item.decode += item.data[fragPos:fragPos + totalTagLen]  # +'#'+str(cnt)+'#'
                    cnt += 1
                    prevVideoTS = packetTS

            # time.sleep(1)
            if packetType in (10, 11):
                print("This stream is encrypted with Akamai DRM. Decryption of such streams isn't currently possible with this script.")
                return False
            if packetType in (40, 41):
                print("This stream is encrypted with FlashAccess DRM. Decryption of such streams isn't currently possible with this script.")
                return False
            fragPos += totalTagLen
        return True

    def readInt8(self, data, pos):
        return ord(struct.unpack_from(">c", data, pos)[0])

    def readInt24(self, data, pos):
        return struct.unpack_from(">L", "\0" + data[pos:pos + 3], 0)[0]


def VideoProxy():
    global IP_ADDRESS, PORT_NUMBER

    server_class = ProxyServer
    print('=== STARTING VIDEO PROXY ====')
    print('= IP:    ' + IP_ADDRESS)
    httpd = server_class((IP_ADDRESS, 0), MyHandler)

    IP_ADDRESS, PORT_NUMBER = httpd.socket.getsockname()

    print('=== VIDEO PROXY LISTENING AT ====')
    print('= IP  :  {}'.format(IP_ADDRESS))
    print('= PORT:  {}'.format(PORT_NUMBER))
    print('==========================')

    SERVER_STARTED.set()

    httpd.serve_forever()


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()

    # -- perform reinitialization of the session on GET request
    def do_GET(s):
        global QueueUrl, QueueUrlDone, M6Item
        CHUNKSIZE = 1024

        # -- get video info ----------------------------
        try:
            video_url = urlparse.parse_qs(urlparse.urlparse(s.path).query).get('video', None)[0]
            video_url = base64.urlsafe_b64decode(video_url)
        except:
            video_url = ''

        if (video_url == ''):
            s.send_response(200)
            s.send_header("Content-type", "text/html")
            s.end_headers()
        else:
            try:
                print('Play: ' + video_url)
                s.send_response(200)
                s.send_header("Connection", "keep-alive")
                s.send_header("Content-Type", "video/mp4")
                # s.send_header("Content-Type", "video/x-flv")
                s.end_headers()
                # --- send video
                global PROXY_THREADS
                global pSocket
                pSocket = s

                st = time.time()
                x = M6(video_url)
                infos = x.getInfos()
                ##                 for item in infos.items():
                ##                    print item[0]+' : '+str(item[1])
                x.download()

                while not QueueUrl.empty():
                    QueueUrl.get()
                    QueueUrl.task_done()

                while not QueueUrlDone.empty():
                    QueueUrlDone.get()
                    QueueUrlDone.task_done()

                M6Item = None

                ##                 print 'Download time:', time.time() - st
                s.server.stop = True
            except:
                s.server.stop = True
                while not QueueUrl.empty():
                    QueueUrl.get()
                    QueueUrl.task_done()

                while not QueueUrlDone.empty():
                    QueueUrlDone.get()
                    QueueUrlDone.task_done()

                M6Item = None


# -------------------------------------------------------------------------------


class ProxyServer(BaseHTTPServer.HTTPServer):
    """http server that reacts to self.stop flag"""

    def serve_forever(self):
        """Handle one request at a time until stopped."""
        self.stop = False
        while not self.stop:
            try:
                print("SERVER START HANDLE")
                self.handle_request()
                print("SERVER END HANDLE")
            except Exception as e:
                print("Handler exception", e)

        print("SERVER closing")
        self.server_close()
        print("SERVER closed")


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

    if mode == 'PLAY':
        PLAY(params)
    else:
        top_list(params)
