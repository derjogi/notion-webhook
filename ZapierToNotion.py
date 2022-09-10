import os

import requests
from dotenv import load_dotenv

load_dotenv()
input_data={"vimeo_id": "747918504", "vimeo_url": "some_fake_url"}
from datetime import datetime

token = os.getenv("NOTION_BEARER_TOKEN")
headers = {
    "Accept": "application/json",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token
}
ERR = "Error"
OP_RES = "OPERATION_RESULT"
STATUS_CODE = "status_code"

def process_new_video(input_data):
    print("Calling with data: \n", input_data)
    database = input_data.get("database", "6abfe101febd4a69bf470c850062013f")  # Defaults to Master Meetings DB
    project_name = input_data.get("project", "")  # Defaults to an empty project
    topic_name = input_data.get("topic_name", project_name)
    start_time = input_data.get("start_time", datetime.now().isoformat())
    recording_url = input_data['vimeo_url']
    # Return some error-ish state by default
    to_be_returned = {STATUS_CODE: 400, OP_RES: "Returned early", "database": database, "project": project_name, "page_id": "Not Found"}

    ### First  we  define some internal helper functions.

    def check_request(response, *params):
        if response.status_code > 299:
            print("Encountered error: " + response.text)
            print("Request was: ", params)
            to_be_returned[OP_RES] = ERR
            to_be_returned[STATUS_CODE] = response.status_code

        return response

    ### this add_to_db is the most important one.
    def add_to_db():

        # Internal helper API functions. Each will update to_be_returned with 'Error' if something failed.

        def create_new_page(database, headers, properties):
            url = "https://api.notion.com/v1/pages"
            payload = {'parent': {'type': 'database_id', 'database_id': database},
                       'properties': properties
                       }
            response = requests.post(url, json=payload, headers=headers)
            return check_request(response, url, payload)

        def set_field_on_page(headers, page_id, property):
            url = "https://api.notion.com/v1/pages/" + page_id
            payload = {"properties": property}
            response = requests.patch(url, json=payload, headers=headers)
            return check_request(response, url, payload)

        def get_page_property(headers, page_id, property):
            url = "https://api.notion.com/v1/pages/" + page_id + "/properties/" + property
            response = requests.get(url, headers=headers)
            return check_request(response, url)

        def get_newest_page(database, headers, project_name):
            url = "https://api.notion.com/v1/databases/" + database + "/query"
            payload = {
                "filter": {"property": "Project", "select": {"equals": project_name}},
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
                "page_size": 1
            }
            response = requests.post(url, json=payload, headers=headers)
            return check_request(response, url, payload)

        db_response = get_newest_page(database, headers, project_name)
        if to_be_returned[OP_RES] == ERR:
            return to_be_returned

        if db_response.json()["results"]:
            results = db_response.json()["results"][0]
            print(results)
            page_id = results["id"]
            print("page_id: ", page_id)
            to_be_returned["page_id"] = page_id

            page_properties_response = get_page_property(headers, page_id, "Recording")
            if to_be_returned[OP_RES] == ERR:
                return to_be_returned

            page_property = page_properties_response.json()
            if not page_property["url"]:
                print("URL is empty, it can be set")
                set_field_on_page(headers, page_id, {"Recording": recording_url})
                if to_be_returned[OP_RES] != ERR:
                    to_be_returned[OP_RES] = "OK"
                    to_be_returned[STATUS_CODE] = 200
                return to_be_returned
            else:
                print("URL wasn't empty! Let's create a new page!")
        else:
            print("Didn't find any matching entries; this might be the first one. Create it.")

        properties = {
            "Name": {
                "title": [{
                    "text": {
                        "content": topic_name
                    }
                }]
            },
            "Recording": {
                "url": recording_url
            },
            "Project": {
                "select": {
                    "name": project_name
                }
            },
            "Meeting%20time": {
                "date": {
                    "start": start_time
                }
            }
        }
        new_page_response = create_new_page(database, headers, properties)
        if to_be_returned[OP_RES] != ERR:
            to_be_returned[OP_RES] = "OK"
            to_be_returned[STATUS_CODE] = 200

        to_be_returned["page_id"] = new_page_response.json()["id"]
        return to_be_returned

    ### End of add_to_db()

    def check_notion_database(database):
        # Return some error-ish state by default
        to_be_returned[STATUS_CODE] = 400
        to_be_returned[OP_RES] = "Returned early"

        # Creating some helper functions. Each will update to_be_returned with 'Error' if something failed.

        def query_database(database, headers):
            url = "https://api.notion.com/v1/databases/" + database + "/query"
            response = requests.post(url, headers=headers)
            return check_request(response, url)

        def get_prop(value, props):
            value_props = props.get(value, {})
            if "rich_text" in value_props:
                rich_text = value_props["rich_text"]
                if rich_text:
                    return rich_text[0].get("plain_text")
            elif "title" in value_props:
                title = value_props["title"]
                if title:
                    return title[0].get("plain_text")

        def drop_nones(d: dict) -> dict:
            """Recursively drop Nones in dict d and return a new dict"""
            dd = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    dd[k] = drop_nones(v)
                elif isinstance(v, (list, set, tuple)):
                    # note: Nones in lists are not dropped
                    # simply add "if vv is not None" at the end if required
                    dd[k] = type(v)(drop_nones(vv) if isinstance(vv, dict) else vv
                                    for vv in v)
                elif v is not None:
                    dd[k] = v
            return dd

        db_response = query_database(database, headers)
        if to_be_returned[OP_RES] == ERR:
            return to_be_returned


        results = db_response.json()["results"]
        all_values = {"projects": []}
        for result in results:
            props = result["properties"]

            name = get_prop("Name", props)
            if name:
                db = get_prop("Database ID", props)
                search = get_prop("Search Keyword", props)
                column = get_prop("Column Name", props)
                value = get_prop("Value", props)

                all_values["projects"].append({
                    "name": name,
                    "properties": {
                        "db": db, "search": search, "column": column, "value": value
                    }
                })

        res = drop_nones(all_values)
        print(res)
        return res

    ### End of Helper methods

    ### Start of main
    # Schema:
    # {
    #   "projects" : [
    #       {
    #         "name": "Notion",
    #         "properties": {"db": db, "search": search, "column": column, "value": value}
    #       },
    #       {name, properties}, {name, properties}, ...
    #   ]
    # }

    zapier_db = "f82fec4581174a53979783b106dab3d0"
    projects_defined_in_notion = check_notion_database(zapier_db)
    topic_orig = input_data["topic_name"]
    topic_lowercase = topic_orig.lower()
    known_projects = []

    for project in projects_defined_in_notion["projects"]:
        properties = project["properties"]
        project_name = project["name"]
        known_projects.append(project_name)
        search = properties["search"]
        if search.lower() in topic_lowercase:
            if properties["db"]:
                database = properties["db"]
            response = add_to_db()
            return response
    # If we haven't found a matching project:
    return {STATUS_CODE: 200, "result": "OK, but ignored. Could not associate video title " + topic_orig +
                                        ". Known Projects: " + str(known_projects) +
                                        "  To add it, add a new entry to https://www.notion.so/seeds-explorers/f82fec4581174a53979783b106dab3d0?v=67ce9d0acaf14827b6283ae98c50e906"
            }

def get_from_storage_for_zapier(vimeo_id):
    url = "https://store.zapier.com/api/records?secret=" + os.getenv("ZAPIER_STORAGE_TOKEN")
    response = requests.get(url)
    entries = response.json()
    return entries[vimeo_id]


# Functions to call if running locally:

from_zapier = get_from_storage_for_zapier(input_data["vimeo_id"])
print(from_zapier)
input_data.update(from_zapier)
# return \
process_new_video(input_data)

fake_input_data = {
    "recordingUrl": "https://some/fake/custom/url",
    "topic_name": "SEEDS | Some new DHO we don't know yet"
}
# print(process_new_video(fake_input_data))
