import hashlib
import time

from .utils import (
    dynamo,
    format_response,
    parse_body,
    TABLE_NAME,
    python_obj_to_dynamo_obj,
    dynamo_obj_to_python_obj,
)
from .input_validation import (
    validate_username,
    validate_elo_key,
    validate_word_id,
    validate_letter_id,
    validate_schema,
)
from . import bad_words
from . import words_ids
from . import elo

PROFILE_KEY1 = "player"
GAME_KEY1 = "game"
ELO_KEY_WORD_COUNT = 5

CREATE_PROFILE_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_username, "name": "username"},
    ],
}
GET_PROFILE_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_elo_key, "name": "elo_key"},
    ],
}
UPDATE_PROFILE_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_elo_key, "name": "elo_key"},
        {"type": validate_username, "name": "username"},
    ],
}
GAME_LOOKUP_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_elo_key, "name": "elo_key"},
        {"type": validate_word_id, "name": "game_id"},
    ],
}
IMPORT_GAMES_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_elo_key, "name": "elo_key"},
        {
            "type": list,
            "name": "games",
            "elements": {
                "type": dict,
                "fields": [
                    {"type": validate_word_id, "name": "game_id"},
                    {"type": validate_letter_id, "name": "password"},
                ],
            },
        },
    ],
}


def profile_id_from_key(elo_key):
    return hashlib.sha256(elo_key.encode()).hexdigest()


def _profile_output(profile):
    return {
        "profile_id": profile["key2"],
        "username": profile["username"],
        "elo": int(profile["elo"]),
        "wins": int(profile["wins"]),
        "losses": int(profile["losses"]),
        "draws": int(profile["draws"]),
    }


def get_profile_item(profile_id):
    if not profile_id:
        return None
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": PROFILE_KEY1, "key2": profile_id}),
    )
    if "Item" not in response:
        return None
    return dynamo_obj_to_python_obj(response["Item"])


def save_profile_item(profile):
    dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(profile),
    )


def _get_game_item(game_id):
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": GAME_KEY1, "key2": game_id}),
    )
    if "Item" not in response:
        return None
    return dynamo_obj_to_python_obj(response["Item"])


def add_game_to_profile(profile, game_id, password):
    games = [g for g in profile.get("games", []) if g["game_id"] != game_id]
    games.append({"game_id": game_id, "password": password})
    profile["games"] = games
    save_profile_item(profile)


def _live_games_for_profile(profile):
    live_entries = []
    live_games = []
    changed = False
    for entry in profile.get("games", []):
        game = _get_game_item(entry["game_id"])
        if not game:
            changed = True
            continue
        live_entries.append(entry)
        live_games.append({"game_id": entry["game_id"], "expiration": int(game["expiration"])})
    if changed:
        profile["games"] = live_entries
        save_profile_item(profile)
    return live_games


def _validate_username_or_error(event, username):
    if not username or len(username) > 16:
        return format_response(
            event=event,
            http_code=400,
            body="Your username is invalid, please try again.",
        )
    if bad_words.has_bad_word(username):
        return format_response(
            event=event,
            http_code=400,
            body="We have detected inappropriate language in your username. If this is an error, "
            'please create a support ticket in the "Help" menu and we will whitelist the name.',
        )
    return None


def create_profile_route(event):
    body = validate_schema(parse_body(event["body"]), CREATE_PROFILE_SCHEMA)
    username = body.get("username")
    error = _validate_username_or_error(event, username)
    if error:
        return error
    elo_key = words_ids.generate_id(k=ELO_KEY_WORD_COUNT)
    profile_id = profile_id_from_key(elo_key)
    profile = {
        "key1": PROFILE_KEY1,
        "key2": profile_id,
        "username": username,
        "elo": elo.DEFAULT_ELO,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "games": [],
        "created_at": int(time.time()),
    }
    write_response = dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(profile),
        ConditionExpression="attribute_not_exists(key2)",
    )
    if (
        "ResponseMetadata" not in write_response
        or "HTTPStatusCode" not in write_response["ResponseMetadata"]
        or write_response["ResponseMetadata"]["HTTPStatusCode"] != 200
    ):
        return format_response(
            event=event,
            http_code=507,
            body="Could not write to the database. Whatever you were trying to do, it did not happen.",
        )
    output = _profile_output(profile)
    output["elo_key"] = elo_key
    return format_response(event=event, http_code=200, body=output)


def get_profile_route(event):
    body = validate_schema(parse_body(event["body"]), GET_PROFILE_SCHEMA)
    profile_id = profile_id_from_key(body["elo_key"])
    profile = get_profile_item(profile_id)
    if not profile:
        return format_response(
            event=event,
            http_code=404,
            body="ELO key not recognized",
        )
    output = _profile_output(profile)
    output["games"] = _live_games_for_profile(profile)
    return format_response(event=event, http_code=200, body=output)


def game_lookup_route(event):
    body = validate_schema(parse_body(event["body"]), GAME_LOOKUP_SCHEMA)
    profile_id = profile_id_from_key(body["elo_key"])
    profile = get_profile_item(profile_id)
    if not profile:
        return format_response(
            event=event,
            http_code=404,
            body="ELO key not recognized",
        )
    game_id = body["game_id"]
    for entry in profile.get("games", []):
        if entry["game_id"] != game_id:
            continue
        if not _get_game_item(game_id):
            profile["games"] = [g for g in profile["games"] if g["game_id"] != game_id]
            save_profile_item(profile)
            return format_response(event=event, http_code=200, body={"in_game": False})
        return format_response(event=event, http_code=200, body={"in_game": True, "password": entry["password"]})
    return format_response(event=event, http_code=200, body={"in_game": False})


def import_games_route(event):
    body = validate_schema(parse_body(event["body"]), IMPORT_GAMES_SCHEMA)
    profile_id = profile_id_from_key(body["elo_key"])
    profile = get_profile_item(profile_id)
    if not profile:
        return format_response(
            event=event,
            http_code=404,
            body="ELO key not recognized",
        )
    existing_ids = {g["game_id"] for g in profile.get("games", [])}
    imported = 0
    for candidate in body.get("games", []):
        game_id = candidate["game_id"]
        password = candidate["password"]
        if game_id in existing_ids:
            continue
        game = _get_game_item(game_id)
        if not game:
            continue
        if password != game.get("player_one_password") and password != game.get("player_two_password"):
            continue
        profile.setdefault("games", []).append({"game_id": game_id, "password": password})
        existing_ids.add(game_id)
        imported += 1
    if imported:
        save_profile_item(profile)
    return format_response(event=event, http_code=200, body={"imported": imported})


def update_profile_route(event):
    body = validate_schema(parse_body(event["body"]), UPDATE_PROFILE_SCHEMA)
    profile_id = profile_id_from_key(body["elo_key"])
    profile = get_profile_item(profile_id)
    if not profile:
        return format_response(
            event=event,
            http_code=404,
            body="ELO key not recognized",
        )
    username = body["username"]
    error = _validate_username_or_error(event, username)
    if error:
        return error
    profile["username"] = username
    save_profile_item(profile)
    return format_response(event=event, http_code=200, body=_profile_output(profile))


def _bump_record(profile, score):
    if score == 1:
        profile["wins"] = int(profile.get("wins", 0)) + 1
    elif score == 0:
        profile["losses"] = int(profile.get("losses", 0)) + 1
    else:
        profile["draws"] = int(profile.get("draws", 0)) + 1


def apply_elo_for_game_result(game_data, winner):
    # winner: 1, 2, or None for a draw
    p1_id = game_data.get("player_one_profile_id")
    p2_id = game_data.get("player_two_profile_id")
    if not p1_id and not p2_id:
        game_data["elo_applied"] = True
        return
    p1 = get_profile_item(p1_id) if p1_id else None
    p2 = get_profile_item(p2_id) if p2_id else None
    score_p1 = 0.5 if winner is None else (1 if winner == 1 else 0)
    if p1 and p2:
        new_p1_elo, new_p2_elo = elo.apply_result(int(p1["elo"]), int(p2["elo"]), score_p1)
        p1["elo"] = new_p1_elo
        p2["elo"] = new_p2_elo
        _bump_record(p1, score_p1)
        _bump_record(p2, 1 - score_p1)
        save_profile_item(p1)
        save_profile_item(p2)
    elif p1:
        _bump_record(p1, score_p1)
        save_profile_item(p1)
    elif p2:
        _bump_record(p2, 1 - score_p1)
        save_profile_item(p2)
    game_data["elo_applied"] = True
