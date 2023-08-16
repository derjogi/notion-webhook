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


def add_all_after(cuttoff_time):
    cutoff = parse_time(cuttoff_time)

    all_matching = []

    for key, val in data.items():
        start_time = val.get("start_time", None)
        if start_time is not None:
            time = parse_time(start_time)
            if cutoff < time:
                val.setdefault("vimeo_id", key)
                all_matching.append(val)

    print(all_matching)
    for val in all_matching:
        ZapierToNotion.run(val)

def filter_with_id(id):
    if id in data:
        return data[id]

    values_containing_key = [v for k, v in data.items() if id in v.values()]
    if len(values_containing_key) != 1:
        print("Uh oh, somehow didn't find exactly one value for "+ id + ": ", values_containing_key)
    return values_containing_key[0]

if __name__ == "__main__":
    load_dotenv()
    zapier_token = os.getenv("ZAPIER_STORAGE_TOKEN")

    data = get_from_storage_for_zapier(zapier_token)

    add_all_after("2023-08-03T00:00:00Z")
    # vimeo_id = "846307763"
    # x = filter_with_id(vimeo_id)
    # nested_vimeo_id = "850952377"
    # y = filter_with_id(nested_vimeo_id)

    # print(x, y)
