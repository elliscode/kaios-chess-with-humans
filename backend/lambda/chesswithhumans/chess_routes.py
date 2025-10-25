from .utils import (
    dynamo,
    format_response,
    parse_body,
    TABLE_NAME,
    python_obj_to_dynamo_obj,
    dynamo_obj_to_python_obj,
)
from .input_validation import (
    validate_word_id,
    validate_letter_id,
    validate_username,
    validate_schema,
    validate_move,
)
import time
from . import bad_words
from . import words_ids
from . import letter_ids
import io
import chess
import chess.pgn

CREATE_GAME_SCHEMA = {
    "type": dict,
    "fields": [
        # {"type": str, "name": "device_id"},
        # {"type": validate_username, "name": "player_one_username"},
    ],
}
JOIN_GAME_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        # {"type": validate_username, "name": "player_two_username"},
    ],
}
GET_GAME_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        {"type": validate_letter_id, "name": "password"},
    ],
}
MAKE_MOVE_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        {"type": validate_letter_id, "name": "password"},
        {"type": validate_move, "name": "move"},
    ],
}
FETCH_GAME_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        {"type": validate_letter_id, "name": "password"},
    ],
}


#    game = parse_pgn_game(game_owner_data["pgn_string"])
def parse_pgn_game(pgn_string) -> chess.pgn.GameNode:
    return chess.pgn.read_game(io.StringIO(pgn_string)).end()


def get_game_route(event):
    body = validate_schema(parse_body(event["body"]), GET_GAME_SCHEMA)
    game_id = body["game_id"]
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": "game", "key2": game_id}),
    )
    if "Item" not in response:
        return format_response(
            event=event,
            http_code=404,
            body="Game ID not found in the database",
        )
    # If it is, check passwords
    game_data = dynamo_obj_to_python_obj(response["Item"])
    if game_data["player_one_password"] == body["password"]:
        player_id = 1
    elif game_data["player_two_password"] == body["password"]:
        player_id = 2
    else:
        return format_response(
            event=event,
            http_code=401,
            body="Player is not allowed to play",
        )
    pieces = {}
    legal_moves = []
    try:
        game_node: chess.pgn.GameNode = parse_pgn_game(game_data["pgn_string"])
        pieceMap: dict[int, chess.Piece] = game_node.board().piece_map()
        whose_turn: int = 1 if game_node.turn() else 2
        for square, piece in pieceMap.items():
            if piece.symbol() not in pieces:
                pieces[piece.symbol()] = []
            pieces[piece.symbol()].append(chess.square_name(square))
        for move in game_node.board().legal_moves:
            legal_moves.append(move.uci())
    except:
        return format_response(
            event=event,
            http_code=500,
            body="This game is not valid, please start a new game and abandon this game",
        )
    return format_response(
        event=event,
        http_code=200,
        body={
            "game_id": game_id,
            "player_id": player_id,
            "whose_turn": whose_turn,
            "pieces": pieces,
            "legal_moves": legal_moves,
        },
    )


def create_game_route(event):
    # check if the ID for the join is in the database
    body = validate_schema(parse_body(event["body"]), CREATE_GAME_SCHEMA)
    player_one_username = 'Player 1' # body["player_one_username"]
    if bad_words.has_bad_word(player_one_username):
        return format_response(
            event=event,
            http_code=400,
            body="We have detected inappropriate language in your username. If this is an error, "
            'please create a support ticket in the "Help" menu and we will whitelist the name.',
        )
    # if its an acceptable username, create a new game and send back the invite link
    player_one_password = letter_ids.generate_id()
    game_id = words_ids.generate_id()
    # Initialize a game object
    game = chess.pgn.Game()
    exporter = chess.pgn.StringExporter(headers=False, variations=True, comments=False)
    pgn_string = game.accept(exporter)
    # Write it to the database
    write_response = dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(
            {
                "key1": "game",
                "key2": game_id,
                "player_one_username": player_one_username,
                "player_one_password": player_one_password,
                "pgn_string": pgn_string,
                "expiration": int(time.time()) + (7 * 24 * 60 * 60),
            }
        ),
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
    # Return the 1st player ID and the current gameboard
    return format_response(
        event=event,
        http_code=200,
        body={
            "game_id": game_id,
            "player_one_username": player_one_username,
            "player_one_password": player_one_password,
        },
    )


def join_game_route(event):
    body = validate_schema(parse_body(event["body"]), JOIN_GAME_SCHEMA)
    player_two_username = 'Player 2' # body["player_two_username"]
    if bad_words.has_bad_word(player_two_username):
        return format_response(
            event=event,
            http_code=400,
            body="We have detected inappropriate language in your username. If this is an error, "
            'please create a support ticket in the "Help" menu and we will whitelist the name.',
        )
    # check if the game exists
    game_id = body["game_id"]
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": "game", "key2": game_id}),
    )
    if "Item" not in response:
        return format_response(
            event=event,
            http_code=404,
            body="Game ID not found in the database",
        )
    game_data = dynamo_obj_to_python_obj(response["Item"])
    # If it is, check if someone already joined
    if "player_two_password" in game_data:
        return format_response(
            event=event,
            http_code=400,
            body="Someone has already joined",
        )
    player_two_password = letter_ids.generate_id()
    game_data["player_two_username"] = player_two_username
    game_data["player_two_password"] = player_two_password
    # Write it to the database
    write_response = dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(game_data),
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
    # Return the 2nd player ID and the current gameboard
    return format_response(
        event=event,
        http_code=200,
        body={
            "game_id": game_id,
            "player_two_username": player_two_username,
            "player_two_password": player_two_password,
        },
    )


def make_move_route(event):
    body = validate_schema(parse_body(event["body"]), MAKE_MOVE_SCHEMA)
    game_id = body["game_id"]
    response = dynamo.get_item(
        TableName=TABLE_NAME,
        Key=python_obj_to_dynamo_obj({"key1": "game", "key2": game_id}),
    )
    if "Item" not in response:
        return format_response(
            event=event,
            http_code=404,
            body="Game ID not found in the database",
        )
    # If it is, check passwords
    game_data = dynamo_obj_to_python_obj(response["Item"])
    if game_data["player_one_password"] == body["password"]:
        player_id = 1
    elif game_data["player_two_password"] == body["password"]:
        player_id = 2
    else:
        return format_response(
            event=event,
            http_code=401,
            body="Player is not allowed to play",
        )
    move = body["move"]
    try:
        game_node: chess.pgn.GameNode = parse_pgn_game(game_data["pgn_string"])
        whose_turn: int = 1 if game_node.turn() else 2
        if whose_turn != player_id:
            return format_response(
                event=event,
                http_code=500,
                body="It is not your turn",
            )
        game_node = game_node.add_variation(chess.Move.from_uci(move))
    except:
        return format_response(
            event=event,
            http_code=500,
            body="This game is not valid, please start a new game and abandon this game",
        )
    # Initialize a game object
    exporter = chess.pgn.StringExporter(headers=False, variations=True, comments=False)
    pgn_string = game_node.game().accept(exporter)
    game_data["pgn_string"] = pgn_string
    game_data["expiration"] = int(time.time()) + (7 * 24 * 60 * 60)
    # Write it to the database
    write_response = dynamo.put_item(
        TableName=TABLE_NAME,
        Item=python_obj_to_dynamo_obj(game_data),
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
    pieces = {}
    legal_moves = []
    try:
        game_node: chess.pgn.GameNode = parse_pgn_game(game_data["pgn_string"])
        pieceMap: dict[int, chess.Piece] = game_node.board().piece_map()
        whose_turn: int = 1 if game_node.turn() else 2
        for square, piece in pieceMap.items():
            if piece.symbol() not in pieces:
                pieces[piece.symbol()] = []
            pieces[piece.symbol()].append(chess.square_name(square))
        for move in game_node.board().legal_moves:
            legal_moves.append(move.uci())
    except:
        return format_response(
            event=event,
            http_code=500,
            body="This game is not valid, please start a new game and abandon this game",
        )
    return format_response(
        event=event,
        http_code=200,
        body={
            "game_id": game_id,
            "whose_turn": whose_turn,
            "pieces": pieces,
            "legal_moves": legal_moves,
        },
    )


if __name__ == "__main__":
    for _ in range(0, 100):
        id_var = words_ids.generate_id()
        print(id_var, not not validate_word_id(id_var))
    pass
