from .utils import (
    dynamo,
    format_response,
    parse_body,
    TABLE_NAME,
    python_obj_to_dynamo_obj,
    dynamo_obj_to_python_obj,
    apigw,
    json,
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
CHECK_TURN_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "game_id"},
        {"type": validate_letter_id, "name": "password"},
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
    output = {
        "game_id": game_id,
        "whose_turn": whose_turn,
        "pieces": pieces,
        "legal_moves": legal_moves,
        "player_id": player_id,
    }
    if "en_passant" in game_data:
        output["en_passant"] = game_data["en_passant"]
    if "previous_move" in game_data:
        output["previous_move"] = game_data["previous_move"]
    if "graveyard" in game_data:
        output["graveyard"] = game_data["graveyard"]
    if "piece_taken" in game_data:
        output["piece_taken"] = game_data["piece_taken"]
    return format_response(
        event=event,
        http_code=200,
        body=output,
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
                "whose_turn": int(1),
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
    graveyard = game_data.get("graveyard", [])
    en_passant = False
    piece_taken = None
    try:
        previous_node: chess.pgn.GameNode = parse_pgn_game(game_data["pgn_string"])
        whose_turn: int = 1 if previous_node.turn() else 2
        if whose_turn != player_id:
            return format_response(
                event=event,
                http_code=500,
                body="It is not your turn",
            )
        game_node = previous_node.add_variation(chess.Move.from_uci(move))
        if previous_node.board().is_capture(game_node.move):
            piece_location = game_node.move.to_square
            if previous_node.board().is_en_passant(game_node.move):
                en_passant = True
                file = chess.square_file(game_node.move.to_square)
                rank = chess.square_rank(game_node.move.from_square)
                piece_location = file + (8 * rank)
            piece: str = previous_node.board().piece_at(piece_location).symbol()
            piece_taken = { piece: [ chess.square_name(piece_location) ] }
            graveyard.append(piece)
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
    game_data["whose_turn"] = 1 if whose_turn == 2 else 2
    game_data["previous_move"] = move
    game_data["en_passant"] = en_passant
    game_data["graveyard"] = graveyard
    game_data.pop("piece_taken", None)
    if piece_taken:
        game_data["piece_taken"] = piece_taken
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
    connection_id = None
    if player_id == 1 and 'player_two_connection_id' in game_data:
        connection_id = game_data['player_two_connection_id']
    elif player_id == 2 and 'player_one_connection_id' in game_data:
        connection_id = game_data['player_one_connection_id']
    if connection_id:
        print(f"Writing message to {connection_id}")
        try:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({"event": "move"})
            )
        except apigw.exceptions.GoneException as e:
            print(f"{connection_id} no longer active, not sending any messages")
    else:
        print("Not sending any messages")

    output = {
        "game_id": game_id,
        "whose_turn": whose_turn,
        "pieces": pieces,
        "legal_moves": legal_moves,
        "player_id": player_id,
    }
    if "en_passant" in game_data:
        output["en_passant"] = game_data["en_passant"]
    if "previous_move" in game_data:
        output["previous_move"] = game_data["previous_move"]
    if "graveyard" in game_data:
        output["graveyard"] = game_data["graveyard"]
    if piece_taken:
        output["piece_taken"] = piece_taken
    return format_response(
        event=event,
        http_code=200,
        body=output,
    )


def check_turn_route(event):
    body = validate_schema(parse_body(event["body"]), CHECK_TURN_SCHEMA)
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
    if "whose_turn" in game_data:
        whose_turn = game_data["whose_turn"]
    else:
        try:
            game_node: chess.pgn.GameNode = parse_pgn_game(game_data["pgn_string"])
            whose_turn: int = 1 if game_node.turn() else 2
        except:
            return format_response(
                event=event,
                http_code=500,
                body="This game is not valid, please start a new game and abandon this game",
            )
    return format_response(
        event=event,
        http_code=200 if whose_turn == player_id else 204,
        body={},
    )


if __name__ == "__main__":
    for _ in range(0, 100):
        id_var = words_ids.generate_id()
        print(id_var, not not validate_word_id(id_var))
    pass
