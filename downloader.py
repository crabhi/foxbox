import os
import traceback

import pyrebase
import youtube_dl

config = {
    "apiKey": "AIzaSyCYHUGcSPqRZ6sNQgYWW0YQtSNX5f-ffIY",
    "authDomain": "fox-box.firebaseapp.com",
    "databaseURL": "https://fox-box.firebaseio.com",
    "serviceAccount": "serviceAccountCredentials.json",
    "storageBucket": "fox-box.appspot.com",
}

DOWNLOAD_FOLDER = "Videos"


def extract_info(db):
    links = db.child("links").get().val()

    with youtube_dl.YoutubeDL() as ydl:
        for key, new_link in sorted(links.get("new", []).items(), key=lambda it: it[1]["time_added"]):
            try:
                new_link["_result"] = {
                    "type": "success",
                    "info_dict": ydl.extract_info(new_link["url"], download=False)
                }
            except:
                new_link["_result"] = {
                    "type": "error",
                    "message": traceback.format_exc()
                }

            db.child("links/extracted").child(key).set(new_link)
            db.child("links/new").child(key).remove()

def extract_downloadables(item, path):
    item_type = item.get("_type", "video")

    if item_type == "playlist":
        queue = []

        for i, it in enumerate(item["entries"]):
            queue.extend(extract_downloadables(it, path + ("entries", i)))

        return queue

    else:
        return [(path, item)]


def synchronize_files(db, folder):
    os.makedirs(folder, exist_ok=True)

    files = []

    db_vals = db.child("links/extracted").get().val().items()

    download_queue = [(("links", "extracted", key, "_result", "info_dict") + path, item)
     for key, videos in sorted(db_vals, key=lambda it: it[1]["time_added"])
     for path, item in extract_downloadables(videos["_result"]["info_dict"], (key,))
     if videos["_result"]["type"] == "success"]

    # TODO: prioritize download
    #   - already downloading
    #   - not series
    #   - series/episode number


def main():
    firebase = pyrebase.initialize_app(config)
    db = firebase.database()

    extract_info(db)

    synchronize_files(db, DOWNLOAD_FOLDER)

if __name__ == "__main__":
    main()
