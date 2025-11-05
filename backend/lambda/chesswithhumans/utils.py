import json
import os
import urllib
import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

DOMAIN_NAME = os.environ.get("DOMAIN_NAME")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")
APIGW_WS_ENDPOINT = os.environ.get("APIGW_WS_ENDPOINT")

apigw = boto3.client("apigatewaymanagementapi", endpoint_url=APIGW_WS_ENDPOINT)
dynamo = boto3.client("dynamodb")


def format_response(event, http_code, body, headers=None):
    if isinstance(body, str):
        body = {"message": body}
    domain_name = "*"
    all_headers = {
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Origin": domain_name,
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Expose-Headers": "x-csrf-token",
    }
    if headers is not None:
        all_headers.update(headers)
    return {
        "statusCode": http_code,
        "body": json.dumps(body),
        "headers": all_headers,
    }


def parse_body(body):
    if isinstance(body, dict):
        return body
    elif body.startswith("{"):
        return json.loads(body)
    else:
        return dict(urllib.parse.parse_qsl(body))


def dynamo_obj_to_python_obj(dynamo_obj: dict) -> dict:
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k, v in dynamo_obj.items()}


def python_obj_to_dynamo_obj(python_obj: dict) -> dict:
    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in python_obj.items()}


def path_equals(event, method, path):
    event_path = event.get("path")
    event_method = event.get("httpMethod")
    return event_method == method and (event_path == path or event_path == path + "/" or path == "*")
