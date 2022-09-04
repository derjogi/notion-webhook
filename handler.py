import json
from datetime import datetime

import requests
from ZapierToNotion import call_notion_api


def hello(event, context):
    print(event)
    result = "Some string"
    body = {
        "message": "Go Serverless v3.0! Your function executed successfully!",
        "input": event,
        "response": result
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

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
    body = json.loads(event['body'])
    print(body)

    results = call_notion_api(body)
    return {"statusCode": 200, "body": json.dumps(results)}
