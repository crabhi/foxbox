#!/usr/bin/env python
"""Usage: downloader.py [--verbose]

Checks the FoxBox web database status and periodically

1. Extracts link information (title, video url, metadata resolution).
2. Downloads files based on the wanted status from the web database.

This program runs until stopped.

Options:
-v, --verbose   Verbose output
"""

import copy
import logging
import os
import re
import sys
import time
import traceback

import docopt
import pathvalidate
import pyrebase
import youtube_dl

ITERATION_MIN_SECONDS = 15
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCYHUGcSPqRZ6sNQgYWW0YQtSNX5f-ffIY",
    "authDomain": "fox-box.firebaseapp.com",
    "databaseURL": "https://fox-box.firebaseio.com",
    "serviceAccount": "serviceAccountCredentials.json",
    "storageBucket": "fox-box.appspot.com",
}
DOWNLOAD_FOLDER = "Videos"
LOG = logging.getLogger(__name__)
IGNORED_FILES = re.compile(r"\.part[^.]*$")


def _extract_info(db):
    LOG.info("Downloading new links...")
    links = db.child("links/new").get().val() or {}

    LOG.info("Found %s new links.", len(links))

    with youtube_dl.YoutubeDL({"logger": logging.getLogger("youtube-dl")}) as ydl:
        for key, new_link in sorted(links.items(), key=lambda it: it[1]["time_added"]):
            LOG.info("Extracting info for %s", new_link["url"])
            # noinspection PyBroadException
            try:
                new_link["_result"] = {
                    "type": "success",
                    "info_dict": ydl.extract_info(new_link["url"], download=False)
                }
            except Exception as ex:  # pylint: disable=broad-except
                LOG.exception("Error downloading link key %s", key)
                new_link["_result"] = {
                    "type": "error",
                    "message": traceback.format_exc()
                }

            db.child("links/extracted").child(key).set(new_link)
            db.child("links/new").child(key).remove()


def _extract_downloadables(item, path):
    item_type = item.get("_type", "video")

    if item_type == "playlist":
        queue = []

        for i, it in enumerate(item["entries"]):
            queue.extend(_extract_downloadables(it, path + ("entries", i)))

        return queue

    else:
        return [(path, item)]


def _save_under_path(db, path, value):
    LOG.debug("Saving to %s", path)
    dbpath = db
    for folder in path:
        dbpath = dbpath.child(folder)

    dbpath.set(value)


def _download_files(db, folder):
    os.makedirs(folder, exist_ok=True)

    db_vals = (db.child("links/extracted").get().val() or {}).items()

    download_queue = [(("links", "extracted", key, "_result", "info_dict") + path, item)
                      for key, videos in sorted(db_vals, key=lambda it: it[1]["time_added"])
                      for path, item in _extract_downloadables(videos["_result"]["info_dict"], tuple())
                      if videos["_result"]["type"] == "success"]

    download_queue = sorted(download_queue,
                            key=(lambda it:
                                 # Already downloading items first.
                                 (it[1].get("_foxbox_download_status", {"type": "NEW"})["type"] == "IN_PROGRESS",
                                  # Single items first
                                  "playlist" not in it[1],
                                  # And if it's a series, start with the low numbers.
                                  # - minus because the order is reversed so that True goes before False
                                  -it[1].get("season_number", 0),
                                  -it[1].get("episode_number", 0))),
                            reverse=True)

    for path, info_dict in download_queue:
        download_status = info_dict.get("_foxbox_download_status", {"type": "NEW"})["type"]

        if download_status not in ["FAILED", "SUCCESS"]:
            LOG.info("Downloading %s", "/".join(map(str, path)))
            with youtube_dl.YoutubeDL({
                "outtmpl": os.path.join(folder, _prepare_filename(info_dict)),
                "logger": logging.getLogger("youtube-dl"),
                "progress_hooks": [print],
            }) as ydl:
                info_dict["_foxbox_download_status"] = {
                    "type": "IN_PROGRESS",
                }

                _save_under_path(db, path, info_dict)

                try:
                    # youtube-dl mutates info_dict causing JSON serialization errors when uploading metadata
                    ydl.process_info(copy.deepcopy(info_dict))
                except Exception as error:  # pylint: disable=broad-except
                    info_dict["_foxbox_download_status"] = {
                        "type": "FAILED",
                        "message": str(error),
                    }
                else:
                    info_dict["_foxbox_download_status"] = {
                        "type": "SUCCESS",
                    }

                _save_under_path(db, path, info_dict)

#
# def _upload_file_structure(filesystem_db, folder):
#     os.makedirs(folder, exist_ok=True)
#     structure_in_db = filesystem_db.get().val() or {"children": {}, "type": "DIRECTORY", "name": folder}
#
#     files_in_db = set(walk_json(structure_in_db))
#     files_on_disk = set((
#         os.path.join(path, filename)
#         for path, _, files in os.walk(folder)
#         for filename in files
#         if not IGNORED_FILES.search(filename)
#     )).union(set((path for path, _1, _2 in os.walk(folder))))
#
#     remove_from_db = files_in_db - set(files_on_disk)
#
#     for file in sorted(remove_from_db, reverse=True):
#         path = file.split(os.path.sep)
#         db_item = structure_in_db
#         for part in path[:-1]:
#             db_item = db_item["children"][part]
#
#         del db_item["children"][path]
#
#     add_to_db = files_on_disk - files_in_db
#
#     for file in sorted(add_to_db):
#         path = file.split(bytes(os.path.sep))
#
#         db_item = structure_in_db
#         for part in path[:-1]:
#             db_item = db_item["children"][part]
#
#         if os.path.isfile(file):
#             new_file = {
#                 "type": "FILE",
#                 "size": os.stat(file).st_size,
#             }
#         elif os.path.isdir(file):
#             new_file = {
#                 "type": "DIRECTORY",
#                 "children": {}
#             }
#
#         db_item["children"][path[-1]] = new_file
#
#     filesystem_db.set(structure_in_db)
#
#
# def walk_json(directory_structure, path=""):
#     if directory_structure["type"] == "DIRECTORY":
#         for key, obj in directory_structure["children"].items():
#             for ret_val in walk_json(obj["children"], os.path.join(path, name)):
#                 yield ret_val
#
#     yield os.path.join(path, directory_structure["name"])


def _prepare_filename(info_dict):

    if "series" in info_dict:
        season = "{:02d}".format(info_dict.get("season_number", 0))
        episode = "{:02d}".format(info_dict.get("episode_number", 0))

        folder = pathvalidate.sanitize_filename(info_dict["series"], replacement_text="_")

        episode_file = pathvalidate.sanitize_filename("s{}-e{}.{}".format(season, episode, info_dict["ext"]),
                                                      replacement_text="_")
        return os.path.join(folder, episode_file)
    else:
        info_copy = dict(info_dict)
        info_copy["title"] = info_dict.get("title", "video")
        return pathvalidate.sanitize_filename("{title}-{id}.{ext}".format(**info_copy))


# def remove_empty_folders(path, remove_root=True):
#     """Recursively removes empty folders.
#
#     :param path - Look for empty folders in this path. If it's not a folder, do nothing.
#     :param remove_root - If there is no file in the folder tree, remove also the folder supplied in `path`?
#     """
#     if not os.path.isdir(path):
#         return
#
#     # remove empty subfolders
#     files = os.listdir(path)
#     if len(files):
#         for f in files:
#             fullpath = os.path.join(path, f)
#             if os.path.isdir(fullpath):
#                 remove_empty_folders(fullpath)
#
#     # if folder empty, delete it
#     files = os.listdir(path)
#     if len(files) == 0 and remove_root:
#         print("Removing empty folder:", path)
#         os.rmdir(path)


def do_single_sync():
    """
    Perform one iteration of synchronization.
    """
    firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
    db = firebase.database()

    _extract_info(db)
    _download_files(db, DOWNLOAD_FOLDER)
    # _upload_file_structure(db.child("filesystem"), DOWNLOAD_FOLDER)


def run_forever():
    "Runs the synchronization forever"
    while True:
        last_time = time.time()
        try:
            do_single_sync()
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as ex:  # pylint: disable=broad-except
            LOG.exception("Programming error - @crabhi probably screwed up")

        wait_time = last_time + ITERATION_MIN_SECONDS - time.time()
        if wait_time > 0:
            LOG.info("Next iteration in %.0d seconds. To stop, press CTRL+C.", wait_time)
            time.sleep(wait_time)


if __name__ == "__main__":
    opts = docopt.docopt(__doc__)
    print(opts)
    logging.basicConfig(level=logging.DEBUG if opts["--verbose"] else logging.INFO)
    run_forever()
