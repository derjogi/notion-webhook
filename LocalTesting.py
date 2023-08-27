import json
import os
import requests
from dotenv import load_dotenv


import ZapierToNotion

def get_from_storage_for_zapier(zapier_token):
    url = "https://store.zapier.com/api/records?&secret=" + zapier_token
    response = requests.get(url)
    return response.json()

# Get all since July 10 and process them

from datetime import datetime

def parse_time(time):
    try:
        return datetime.fromisoformat(time)
    except ValueError:
        return datetime.strptime(time, "%Y-%m-%dT%H:%M:%S%z")


def get_all_after(data, cuttoff_time):
    cutoff = parse_time(cuttoff_time)

    all_matching = {}

    for key, val in data.items():
        start_time = val.get("start_time", None)
        if start_time is not None:
            time = parse_time(start_time)
            if cutoff < time:
                val.setdefault("vimeo_id", key)
                topic = val.get("topic_name", val.get("vimeo_title", None))
                if "SEEDS" in topic:
                    all_matching[key] = val

    return all_matching

def get_videos_from_vimeo():
    with open("vimeo.json", "r") as f:
        as_json = json.load(f)
    subset = {}
    for data in as_json["data"]:
        split = data["description"].split("\n")
        vimeo_id = data["uri"][len("/videos/"):]
        if not vimeo_id.isdigit():
            print("Entry with failed vimeo_id: ", data)
            pass
        entry = {
            "vimeo_id": vimeo_id,
            "vimeo_title": data["name"],
            "start_time": split[1][:-6] # removes the ' (UTC)' suffix
            }
        subset[vimeo_id] = entry
    return subset

def update_vimeo_id(key, vimeo_id):
    url = "https://store.zapier.com/api/records?&secret=" + zapier_token
    payload = {"action": "set_child_value",
               "data": {
                   "key": key,
                    "vimeo_id": vimeo_id
               }}

    response = requests.patch(url, payload)
    print(response)


def add_to_zapier_store(payload, zapier_token):
    url = "https://store.zapier.com/api/records?&secret=" + zapier_token
    response = requests.post(url, data=json.dumps(payload))
    check_response(response)


def remove_old_zapier_entries(how_many_to_keep, from_zapier, zapier_token):
    # First we need to remove all entries (Their API is very basic, don't know whether I can just remove one entry...)
    # ... and then add all those we want to keep again.

    sorted_by_date = sorted(from_zapier.items(), key=lambda x: x[1].get("start_time", "0"), reverse=True)
    print(sorted_by_date)   # just in case, printing this so I can recover if something goes wrong
    keep = sorted_by_date[:how_many_to_keep]
    print(keep)     # again, recovery reasons

    url = "https://store.zapier.com/api/records?&secret=" + zapier_token
    response = requests.delete(url)
    check_response(response)
    response = requests.post(url, json=keep)
    check_response(response)


def check_response(response):
    if response.status_code > 299:
        print(response.json())
        raise Exception(f"Something went wrong: {response.json}")
    return response.json()


def add_missing_to_zapier(from_vimeo, from_zapier, zapier_token):
    add_to_zapier = {}
    for key, entry in from_vimeo.items():
        try:
            ZapierToNotion.filter_with_id(entry["vimeo_id"], from_zapier)
        except:
            # not found, so we'll have to add this one.
            add_to_zapier[key] = entry
    add_to_zapier_store(add_to_zapier, zapier_token)
    return add_to_zapier


def add_missing_to_notion(new_entries):
    for entry in new_entries:
        confirmation = input(f"Add to Notion?(y/Y)\nEntry:\t{entry}")
        if "y" in confirmation or "Y" in confirmation:
            ZapierToNotion.run(entry)


def get_from_notion():
    notion_token = os.getenv("NOTION_BEARER_TOKEN")
    headers = {
        "Accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + notion_token
    }
    url = "https://api.notion.com/v1/databases/6abfe101febd4a69bf470c850062013f/query"
    payload = {
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": 100
    }
    response = requests.post(url, json=payload, headers=headers)
    return check_response(response)


def has_id(from_notion, vimeo_id):
    for entry in from_notion["results"]:
        if url := entry["properties"]["Recording"]["url"]:
            if vimeo_id in url:
                return entry


if __name__ == "__main__":
    load_dotenv()
    zapier_token = os.getenv("ZAPIER_STORAGE_TOKEN")

    from_notion = get_from_notion()

    # with open("zapier_update.json") as zk:
    #     zapier_entries = json.load(zk)
    # as_dict = {}
    # for entry in zapier_entries:
    #     as_dict[entry[0]]=entry[1]

    # add_to_zapier_store(zapier_entries, zapier_token)

    from_zapier = get_from_storage_for_zapier(zapier_token)

    # remove_old_zapier_entries(150, from_zapier, zapier_token)

    # from_vimeo = get_videos_from_vimeo()

    # added_to_zapier = add_missing_to_zapier(from_vimeo, from_zapier, zapier_token)

    # add_missing_to_notion(added_to_zapier)


    all_matching = get_all_after(from_zapier, "2023-08-16T15:03:07Z")

    sorted_by_time = sorted(all_matching.items(), key=lambda x: x[1]["start_time"])

    for key, val in sorted_by_time:
        if not has_id(from_notion, val["vimeo_id"]):
            ZapierToNotion.run(val)

    # for val in all_matching:
    #     ZapierToNotion.run(val)
    # vimeo_id = "846307763"
    # x = ZapierToNotion.filter_with_id(vimeo_id, data)
    # nested_vimeo_id = "850952377"
    # y = filter_with_id(nested_vimeo_id)

    # print(x, y)
