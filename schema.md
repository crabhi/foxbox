# Overall schema

    {
      "serialy" : {
        // old format
      },
      "links": {
        "key": link_object
      }
    }

# User link object

## Freshly added

`/links/new`

    {
        "url": user_supplied_url,
        "time_added": now,
    }

When added, FoxBox extracts info and puts the result into the `/links/extracted` list.

If the url already exists in `/links/extracted`, the result is undefined. The operation *should* be idempotent.

## Information extracted

`/links/extracted`

    {
        "url": user_supplied_url,
        "time_added": some_time,
        "_result": {
            "type": "success",
            "info_dict": {
                // information in youtube-dl format
                "_type": undefined|"playlist"|...,
                ...
            }
        }
    }
    
    {
        "url": user_supplied_url,
        "link_added": some_time,
        "_result": {
            "type": "error", 
            "message": "...",
        }
    }

# Video object

`/links/extracted/<serial_id>/_result/info_dict.json`
`/links/extracted/<serial_id>/_result/info_dict/entries/<n>.json`

## Playlist containing other info objects.


    {
        "_type": "playlist",
        "entries": [info_object, ...]
    }

## Plain video

### Waiting for download

`_foxbox_download_status` is undefined

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
    }

### Download in progress

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
        "_foxbox_download_status": {
            "type": "IN_PROGRESS",
            "downloaded_part": 0.441,
            "downloaded_bytes": 24875
        },
    }

### Download failed

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
        "_foxbox_download_status": {
            "type": "FAILED",
            "downloaded_part": 0.441,
            "downloaded_bytes": 24875,
            "message": "..."
        },
    }
    
### Download succeeded

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
        "_foxbox_download_status": {
            "type": "SUCCESS",
            "downloaded_bytes": 24875,
            "file": "Videos/Anna Karenina/s05-e17.flv"
        },
    }

### File to be deleted

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
        "_foxbox_download_status": {
            "type": "TO_DELETE",
            "file": "Videos/Anna Karenina/s05-e17.flv"
        },
    }
    
### File deleted

    {
        "_type": undefined | "video",
        "id": "...",
        "extractor", "MyHitSerial"|"...",
        "title": "...",
        "thumbnail": "...",
        "_foxbox_download_status": {
            "type": "DELETED",
            "file": "Videos/Anna Karenina/s05-e17.flv"
        },
    }
