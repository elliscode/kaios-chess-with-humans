# ▄▖▌            ▘▗ ▌   ▌
# ▌ ▛▌█▌▛▘▛▘  ▌▌▌▌▜▘▛▌  ▛▌▌▌▛▛▌▀▌▛▌▛▘
# ▙▖▌▌▙▖▄▌▄▌  ▚▚▘▌▐▖▌▌  ▌▌▙▌▌▌▌█▌▌▌▄▌

import traceback

from chesswithhumans.utils import (
    format_response,
    path_equals,
)
from chesswithhumans.chess_routes import (
    check_turn_route,
    join_game_route,
    create_game_route,
    get_game_route,
    make_move_route,
)
from chesswithhumans.web_socket_routes import (
    web_socket_route,
)


def lambda_handler(event, context):
    try:
        print(event, context)
        result = route(event, context)
        print(result)
        return result
    except Exception:
        traceback.print_exc()
        return format_response(event=event, http_code=500, body="Internal server error")


# Only using POST because I want to prevent CORS preflight checks, and setting a
# custom header counts as "not a simple request" or whatever, so I need to pass
# in the CSRF token (don't want to pass as a query parameter), so that really
# only leaves POST as an option, as GET has its body removed by AWS somehow
#
# see https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#simple_requests
def route(event, context):
    if path_equals(event=event, method="POST", path="/get"):
        return get_game_route(event)
    if path_equals(event=event, method="POST", path="/join"):
        return join_game_route(event)
    if path_equals(event=event, method="POST", path="/create"):
        return create_game_route(event)
    if path_equals(event=event, method="POST", path="/move"):
        return make_move_route(event)
    if path_equals(event=event, method="POST", path="/is-it-my-turn"):
        return check_turn_route(event)
    if 'requestContext' in event and 'routeKey' in event['requestContext']:
        return web_socket_route(event, context)
    return format_response(event=event, http_code=403, body={"message": "Forbidden"})
