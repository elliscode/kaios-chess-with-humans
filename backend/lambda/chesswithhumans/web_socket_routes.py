import json
from .utils import (
    dynamo,
    TABLE_NAME,
    python_obj_to_dynamo_obj,
    dynamo_obj_to_python_obj,
    apigw,
)
from .input_validation import (
    validate_word_id,
    validate_letter_id,
    validate_schema,
)

REGISTER_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        {"type": validate_letter_id, "name": "password"},
    ],
}

def register_websocket_id(connection_id, body):
    game_id = body['game_id']
    password = body['password']
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": "game", "key2": game_id}),
    )
    if "Item" not in response:
        output = {"statusCode": 400, "body": f"Could not register {connection_id} for game {game_id} because game_id is not found in the database"}
        print(output)
        return output
    # If it is, check passwords
    game_data = dynamo_obj_to_python_obj(response["Item"])
    if game_data["player_one_password"] == password:
        connection_id_key = "player_one_connection_id"
    elif game_data["player_two_password"] == password:
        connection_id_key = "player_two_connection_id"
    else:
        output = {"statusCode": 400, "body": f"Could not register {connection_id} for game {game_id} as the wrong password was provided"}
        print(output)
        return output
    game_data[connection_id_key] = connection_id
    write_response = dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(game_data)
    )
    if (
        "ResponseMetadata" not in write_response
        or "HTTPStatusCode" not in write_response["ResponseMetadata"]
        or write_response["ResponseMetadata"]["HTTPStatusCode"] != 200
    ):
        output = {"statusCode": 400, "body": f"Could not register {connection_id} for game {game_id} due to db connection issue"}
        print(output)
        return output
    # Send a response back to this same connection
    event_text = "registered"
    if connection_id_key == "player_one_connection_id" and game_data['whose_turn'] == 1:
        event_text = "move"
    elif connection_id_key == "player_two_connection_id" and game_data['whose_turn'] == 2:
        event_text = "move"
    apigw.post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps({"event": event_text})
    )
    output = {"statusCode": 200, "body": f"Registered {connection_id} for game {game_id}"}
    print(output)
    return output

def web_socket_route(event, context):
    route = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")

    print(f"Received route: {route}, connection: {connection_id}")

    if route == "$connect":
        return {"statusCode": 200, "body": "Connected."}

    elif route == "$disconnect":
        return {"statusCode": 200, "body": "Disconnected."}

    elif route == "register":
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", {})
        print(f"Registration request received from {connection_id}: {message}")
        print(type(message))
        registration_body = validate_schema(message, REGISTER_SCHEMA)
        if not registration_body:
            return {"statusCode": 400, "body": f"Invalid registration payload"}
        print(registration_body)
        return register_websocket_id(connection_id, registration_body)

    elif route == "$default":
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "")
        print(f"Message received from {connection_id}: {message}")

        return {"statusCode": 200, "body": json.dumps({"echo": message})}

    else:
        return {"statusCode": 400, "body": "Unknown route."}