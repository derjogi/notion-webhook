import os
import requests
from dotenv import load_dotenv

load_dotenv()
notion_token = os.getenv("NOTION_BEARER_TOKEN")
zapier_token = os.getenv("ZAPIER_STORAGE_TOKEN")

# Running this manually sometimes to check the past few meetings are all recorded properly,
# especially useful if a group was meeting but notion just wasn't set up.
def sync_videos_from_the_last_x_days(days):
    # input_data={"vimeo_id": "750078933", "vimeo_url": "https://vimeo.com/750078933", "vimeo_title": "HFFC: HFFC: Seeds Currency Working Group"}
    zapier_store_url = "https://store.zapier.com/api/records?secret=" + zapier_token
    response = requests.get(zapier_store_url)
    formatted = response.json()
    for key in formatted:
        value = formatted.get(key)
        video_time = datetime.fromisoformat(value["start_time"]).replace(tzinfo=None)
        diff = datetime.utcnow() - video_time
        if diff.days <= days:
            print("Processing")
            value["vimeo_title"] = value["topic_name"]
            value["vimeo_url"] = "https://vimeo.com/" + key
            process_new_video(value)

### Everything below here should be copied to zapier; + update the above two tokens!

from datetime import datetime
import urllib.parse as parse

headers = {
    "Accept": "application/json",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + notion_token
}
ERR = "Error"
OP_RES = "operation_result"
STATUS_CODE = "status_code"

def process_new_video(input_data):
    print("Calling with data: \n", input_data)
    database = input_data.get("database", "6abfe101febd4a69bf470c850062013f")  # Defaults to Master Meetings DB
    vimeo_title = input_data.get("vimeo_title", "No Title")
    project_name = input_data.get("project", vimeo_title)  # Defaults to an empty project
    topic_name = input_data.get("topic_name", vimeo_title)
    start_time = input_data.get("start_time", datetime.now().isoformat())
    recording_url = input_data.get('vimeo_url', "https://vimeo.com/" + input_data['vimeo_id'])
    transcript_url = input_data.get("transcript_url", None)
    chat_url = input_data.get("chat_url", None)
    # Return some error-ish state by default
    to_be_returned = {STATUS_CODE: -1, OP_RES: "Returned early", "database": database, "project": project_name, "page_id": "Not Found"}

    ### First  we  define some internal helper functions.
    def check_response(response, *params):
        if response.status_code > 299:
            print("Encountered error: " + response.text)
            print("Request was: ", params)
            to_be_returned[OP_RES] = ERR
            to_be_returned[STATUS_CODE] = response.status_code

        return response

    ### this add_to_db is the most important one.
    def add_to_db():
        db_response = get_last_five_pages_for_project(database, headers, project_name)
        if to_be_returned[OP_RES] == ERR:
            return to_be_returned

        if db_response.json()["results"]:
            first_with_empty_date = False
            counter = 0
            for page in db_response.json()["results"]:
                counter += 1
                print(page)
                page_id = page["id"]
                print("page_id: ", page_id)
                to_be_returned["page_id"] = page_id

                page_props = page["properties"]
                meeting_time = page_props.get("Meeting time", {}).get("date", {})
                if meeting_time is None:
                    if counter == 1:
                        first_with_empty_date = True
                    continue
                if meeting_time.get("start") is None:
                    if counter == 1:
                        first_with_empty_date = True
                    continue
                meeting_time = meeting_time.get("start")
                planned_meeting_time = parse_time(meeting_time).replace(tzinfo=None)
                recording_time = parse_time(start_time).replace(tzinfo=None)
                recording_vs_planned_time_diff = (planned_meeting_time - recording_time).days
                if not -1 <= recording_vs_planned_time_diff <= 1:
                    print("Not the right entry, meeting time and recording time are too different: "
                          + planned_meeting_time.isoformat() + " & " + recording_time.isoformat())
                    continue

                try:
                    meeting_name = page_props["Name"]["title"][0]["text"]["content"]
                    if meeting_name in topic_name:
                        print("Found a page that matches the meeting name and recording time, updating that if it's lacking a field.")
                        update_empty_field(page_id, page_props["Recording"]["url"], {"Recording": recording_url})
                        if transcript_url is not None:
                            update_empty_field(page_id, page_props["Transcript"]["url"], {"Transcript": transcript_url})
                        if chat_url is not None:
                            update_empty_field(page_id, page_props["Chat"]["url"], {"Chat": chat_url})
                        return to_be_returned
                except:
                    print("Found a page that matches the recording time, updating that if it's lacking a url.")
                    update_empty_field(page_id, page_props["Recording"]["url"], {"Recording": recording_url})
                    if transcript_url is not None:
                        update_empty_field(page_id, page_props["Transcript"]["url"], {"Transcript": transcript_url})
                    if chat_url is not None:
                        update_empty_field(page_id, page_props["Chat"]["url"], {"Chat": chat_url})
                    return to_be_returned

            if first_with_empty_date:
                print("None of the fetched entries matched the time, but the latest one didn't have a date. Assuming this is the right one, let's use that!")
                page = db_response.json()["results"][0]
                page_id = page["id"]
                page_props = page["properties"]
                update_empty_field(page_id, page_props["Meeting time"]["date"], {"Meeting time": {"date": {"start": start_time}}})
                update_empty_field(page_id, page_props["Recording"]["url"], {"Recording": recording_url})
                if transcript_url is not None:
                    update_empty_field(page_id, page_props["Transcript"]["url"], {"Transcript": transcript_url})
                if chat_url is not None:
                    update_empty_field(page_id, page_props["Chat"]["url"], {"Chat": chat_url})
                return to_be_returned
            else:
                print("None of the fetched entries matched the time, so let's create a new page")
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

    ### Helper functions for add_to_db(). Each will update to_be_returned with 'Error' if something failed.
    def create_new_page(database, headers, properties):
        url = "https://api.notion.com/v1/pages"
        payload = {'parent': {'type': 'database_id', 'database_id': database},
                   'properties': properties
                   }
        response = requests.post(url, json=payload, headers=headers)
        return check_response(response, url, payload)

    def set_field_on_page(headers, page_id, property):
        url = "https://api.notion.com/v1/pages/" + page_id
        payload = {"properties": property}
        response = requests.patch(url, json=payload, headers=headers)
        return check_response(response, url, payload)

    def update_empty_field(page_id, field, property_value):
        if not field:
            print("Field is empty, it can be set")

            set_field_on_page(headers, page_id, property_value)
            if to_be_returned[OP_RES] != ERR:
                to_be_returned[OP_RES] = "OK"
                to_be_returned[STATUS_CODE] = 200
        else:
            print("Field wasn't empty! Not doing anything.")

    def get_page_property(headers, page_id, property):
        url = "https://api.notion.com/v1/pages/" + page_id + "/properties/" + property
        response = requests.get(url, headers=headers)
        return check_response(response, url)

    def get_newest_page(database, headers, project_name):
        url = "https://api.notion.com/v1/databases/" + database + "/query"
        payload = {
            "filter": {"property": "Project", "select": {"equals": project_name}},
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 1
        }
        response = requests.post(url, json=payload, headers=headers)
        return check_response(response, url, payload)

    def get_last_five_pages_for_project(database, headers, project_name):
        url = "https://api.notion.com/v1/databases/" + database + "/query"
        payload = {
            "filter": {"property": "Project", "select": {"equals": project_name}},
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 5
        }
        response = requests.post(url, json=payload, headers=headers)
        return check_response(response, url, payload)

    def parse_time(time):
        try:
            return datetime.fromisoformat(time)
        except ValueError:
            return datetime.strptime(time, "%Y-%m-%dT%H:%M:%S%z")


    ### checking what's in the notion db already so we know what to update
    def check_notion_database(database):
        # Return some error-ish state by default
        to_be_returned[STATUS_CODE] = -1
        to_be_returned[OP_RES] = "Returned early"

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

    ### Helper functions for check_notion_database(). Each will update to_be_returned with 'Error' if something failed.
    def query_database(database, headers):
        url = "https://api.notion.com/v1/databases/" + database + "/query"
        response = requests.post(url, headers=headers)
        return check_response(response, url)

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

    ### End of Helper methods

    ### Main routine for proccess_new_video:
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
    topic_lowercase = topic_name.lower()
    known_projects = []

    for project in projects_defined_in_notion["projects"]:
        properties = project["properties"]
        project_name = project["name"]
        known_projects.append(project_name)
        search = properties["search"]
        if search.lower() in topic_lowercase:
            if "db" in properties:
                database = properties["db"]
            response = add_to_db()
            return response
    # If we haven't found a matching project:
    return {STATUS_CODE: 200, "result": "OK, but ignored. Could not associate video title " + topic_name +
                                        ". Known Projects: " + str(known_projects) +
                                        "  To add it, add a new entry to https://www.notion.so/seeds-explorers/f82fec4581174a53979783b106dab3d0?v=67ce9d0acaf14827b6283ae98c50e906"
            }

def filter_with_id(id, data):
    if id in data:
        return data[id]

    values_containing_key = [v for k, v in data.items() if id in v.values()]
    if len(values_containing_key) > 1:
        raise ValueError("Uh oh, somehow found multiple values for " + id + ": ", values_containing_key)
    if len(values_containing_key) < 1:
        raise ValueError("Didn't find an entry for " + id)
    return values_containing_key[0]

def get_from_storage_for_zapier(vimeo_id):
    encoded = parse.quote_plus(vimeo_id)
    url = "https://store.zapier.com/api/records?key=" + encoded + "&secret=" + zapier_token
    try:
        response = requests.get(url)
        return response.json()[vimeo_id]
    except:
        # get all entries, the ID might be nested inside one of them.
        url = "https://store.zapier.com/api/records?&secret=" + zapier_token
        response = requests.get(url)
        filter_with_id(vimeo_id, response.json())

def run(input_data):
    output = process_new_video(input_data)

    # sync_videos_from_the_last_x_days(10)
    print(output)


if __name__ == "__main__":
# Set fake data if running locally:
    input_data={"vimeo_id":	"855059134",
                "vimeo_url":	"https://vimeo.com/855059134",
                "vimeo_title":	"SEEDS Collaboratory | Strategic Council"}
    from_zapier = get_from_storage_for_zapier(input_data["vimeo_id"])
    print(from_zapier)
    input_data.update(from_zapier)
    run(input_data)
