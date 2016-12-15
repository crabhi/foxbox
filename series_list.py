# encoding: utf-8

from __future__ import print_function

import json
import Queue
import re
import threading
import urllib2
import urlparse

from BeautifulSoup import BeautifulSoup

FIREBASE_SECRET = "gVIXtw3rR1maX3K0HcIwnFvnqq32gS3LTaYljKZV"

MISSING_ICON = ("https://raw.githubusercontent.com/anastazie/hladovaLiska/" +
                "73eb35dbbb920a6787c9a2eed3501a763e9fbb0d/www/img/liska.png")

URL_REGEX = re.compile(r"https?://[^.]*\.?my-hit.org.+")



def get_html(url, post=None, ref=None):
    print("FoxBox requesting {}".format(url))

    request = urllib2.Request(url, post)

    host = urlparse.urlsplit(url).hostname

    request.add_header('User-Agent',
                       'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; Mozilla/4.0 (compatible; ' +
                       'MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.4506' +
                       '.2152; .NET CLR 3.5.30729; .NET4.0C)')
    request.add_header('Host', host)
    request.add_header('Accept', '*/*')
    request.add_header('Accept-Language', 'ru-RU')
    request.add_header('Referer', ref)

    try:
        f = urllib2.urlopen(request)
    except IOError as e:
        print("FoxBox", e)
        return None

    html = f.read()

    return html


def get_all():
    response = json.load(urllib2.urlopen(
        "https://fox-box.firebaseio.com/serialy.json?auth={}".format(FIREBASE_SECRET)))

    serialy = [{
        "name": val.get("name", "{} - Loading...".format(val["web_url"])),
        "img": val.get("img", MISSING_ICON),
        "web_url": val["web_url"],
        "playlist": val.get("playlist", []),
        "db_key": key,
        "timestamp": val["timestamp"]
       } for key, val in sorted(response.items(), key=lambda it: it[1]["timestamp"], reverse=True)
    ]

    load_missing(serialy)

    return serialy


def load_missing(serialy):
    """
    Loads (and uploads missing information in a background thread).
    """
    q = Queue.Queue()

    for s in serialy:
        if not URL_REGEX.match(s["web_url"]):
            s["name"] = "Can't load {}".format(s["web_url"])
        else:
            q.put(s)

    def loader():
        while True:
            try:
                item = q.get_nowait()
                try:
                    if len(item["playlist"]) == 0:
                        process_serie(item)
                    q.task_done()
                except Exception as e:
                    print("Error during processing {}".format(item["web_url"]))
                    print(e)
            except Queue.Empty:
                break

    t = threading.Thread(target=loader)
    t.start()


def process_serie(serie):
    if not serie["web_url"].endswith("/"):
        serie["web_url"] += "/"

    page_str = get_html(serie["web_url"])
    page = BeautifulSoup(page_str, convertEntities=BeautifulSoup.ALL_ENTITIES)

    title = page.find("h1")
    if title:
        serie["name"] = title.text

    img = [div.img["src"]
           for div
           in title.parent.findAll("div", {"class": re.compile("div-serial-poster")})
           if div.get("data-serial-id", False)]

    serie["img"] = urlparse.urljoin(serie["web_url"], img[0]) if len(img) > 0 else MISSING_ICON

    playlist_url = serie["web_url"] + "playlist.txt"
    playlist_str = get_html(playlist_url)

    serie["playlist"] = json.loads(playlist_str)["playlist"]

    req = urllib2.Request(
        "https://fox-box.firebaseio.com/serialy/{}.json?auth={}".format(
            urllib2.quote(serie["db_key"]), FIREBASE_SECRET),
        json.dumps(serie),
        {'Content-Type': 'application/json'})

    req.get_method = lambda: "PUT"

    urllib2.urlopen(req)

    # print("SERIE", serie)
    return serie


if __name__ == "__main__":
    print(get_all())
