import os

import requests
from dotenv import load_dotenv
from datetime import datetime


def call_notion_api(input_data):
    print("Calling with data: \n", input_data)
    database = input_data.get("database", "6abfe101febd4a69bf470c850062013f")  # Defaults to Master Meetings DB
    project_name = input_data.get("projectName", "")  # Defaults to an empty project
    meeting_title = input_data.get("meetingTitle", project_name)
    meeting_time_start = input_data.get("startTime", datetime.now().isoformat())
    recording_url = input_data['recordingUrl']

    # Return some error-ish state by default
    to_be_returned = {"status_code": "400", "result": "Returned early", "database": database, "project": project_name, "page_id": "Not Found"}

    headers = {
        "Accept": "application/json",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.getenv("NOTION_BEARER_TOKEN")
    }

    # Creating some helper API functions. Each will update to_be_returned with 'Error' if something failed.
    def create_new_page(database, headers, properties):
        url = "https://api.notion.com/v1/pages"
        payload = {'parent': {'type': 'database_id', 'database_id': database},
                   'properties': properties
                   }
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code > 299:
            print(response.text)
            to_be_returned["result"] = "Error"
            to_be_returned["status_code"] = str(response.status_code)

        return response

    def set_field_on_page(headers, page_id, property):
        url = "https://api.notion.com/v1/pages/" + page_id
        payload = {"properties": property}
        response = requests.patch(url, json=payload, headers=headers)

        if response.status_code > 299:
            print(response.text)
            to_be_returned["result"] = response  # Todo!
            to_be_returned["status_code"] = str(response.status_code)

        return response

    def get_page_properties(headers, page_id, property_id):
        url = "https://api.notion.com/v1/pages/" + page_id + "/properties/" + property_id
        response = requests.get(url, headers=headers)

        if response.status_code > 299:
            print(response.text)
            to_be_returned["result"] = "Error"

        return response

    def query_database(database, headers, project_name):
        url = "https://api.notion.com/v1/databases/" + database + "/query"
        payload = {
            "filter": {"property": "Project", "select": {"equals": project_name}},
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 1
        }
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code > 299:
            print(response.text)
            to_be_returned["result"] = "Error"

        return response

    db_response = query_database(database, headers, project_name)
    if to_be_returned["result"] == "Error":
        return to_be_returned

    results = db_response.json()["results"][0]
    properties = results["properties"]
    page_id = results["id"]
    name_property_id = properties["Name"]["id"]
    project_property_id = properties["Project"]["id"]
    recording_property_id = properties["Recording"]["id"]
    # dho_property_id = properties["DHO"]["id"]
    meeting_time_property_id = properties["Meeting time"]["id"]
    print({'page_id': page_id, 'recording': recording_property_id})
    print(results)
    to_be_returned["page_id"] = page_id

    page_properties_response = get_page_properties(headers, page_id, recording_property_id)
    if to_be_returned["result"] == "Error":
        return to_be_returned

    recording_property = page_properties_response.json()
    if not recording_property["url"]:
        print("URL is empty, it can be set")

        property_to_update = {recording_property_id: recording_url}

        set_field_on_page(headers, page_id, property_to_update)
        if to_be_returned["result"] != "Error":
            to_be_returned["result"] = "OK"
        return to_be_returned
    else:
        print("URL wasn't empty! Let's create a new page!")

        properties = {
            name_property_id: {
                "title": [{
                    "text": {
                        "content": meeting_title
                    }
                }]
            },
            recording_property_id: {
                "url": recording_url
            },
            project_property_id: {
                "select": {
                    "name": project_name
                }
            },
            meeting_time_property_id: {
                "date": {
                    "start": meeting_time_start
                }
            }
            # We could directly do relations, but we'd need their PageIDs but only have an approximate name, and it's
            # difficult to get the actual 'name' of each Page, as stupid as that sounds!
            # (To get those we'd need to query each unique ID separately)
            # ,
            # dho_property_id: {
            #     "relation": [{
            #         "id": "c8fd6942-43fb-472f-9778-6fe67e215b7c"
            #     }]
            # }
        }
        new_page_response = create_new_page(database, headers, properties)
        if to_be_returned["result"] != "Error":
            to_be_returned["result"] = "OK"
        to_be_returned["page_id"] = new_page_response.json()["id"]
        return to_be_returned


# Functions to call if running locally:
# print(call_notion_api())
