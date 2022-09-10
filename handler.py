import json
from datetime import datetime
from ZapierToNotion import call_notion_api
from FetchFromNotion import check_notion_database
from dotenv import load_dotenv
load_dotenv()
import requests


def notion(event, context):
    input_data = {
        "projectName": "Notion",
        "recordingUrl": "xyz",
        # Optional:
        "meetingTitle": "HCDC: Notion Weekly Meeting",
        "startTime": datetime.now().isoformat(),
        "database": "6abfe101febd4a69bf470c850062013f",
    }
    print(event)
    input_data = event['body']
    print(input_data)

    results = call_notion_api(input_data)
    return {"statusCode": 200, "body": json.dumps(results)}

def check_from_notion(event, context):
    input_data = event['body']
    results = check_notion_database(input_data)
    return {"statusCode": 200, "body": json.dumps(results)}
