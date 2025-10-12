import re

FLOAT_REGEX = "^[\\-]{0,1}\\d*[\\.]{0,1}\\d+$"
WORD_ID_REGEX = "[a-z]+\\-[a-z]+\\-[a-z]+"
LETTER_ID_REGEX = "[a-zA-Z0-9]{32}"
ASCII_REGEX = "[\u0020-\u007e]+"


def validate_move(value):
    if isinstance(value, str) and re.match(ASCII_REGEX, value):
        return value
    return None


def validate_word_id(value):
    if isinstance(value, str) and re.match(WORD_ID_REGEX, value):
        return value
    return None


def validate_username(value):
    if isinstance(value, str) and re.match(ASCII_REGEX, value):
        return value
    return None


def validate_letter_id(value):
    if isinstance(value, str) and re.match(LETTER_ID_REGEX, value):
        return value
    return None


def validate_decimal(value):
    if isinstance(value, str) and re.match(FLOAT_REGEX, value):
        return value
    elif isinstance(value, float):
        return str(value)
    return None


def is_valid_against_schema(value, schema):
    if schema["type"] == list or schema["type"] == dict:
        if not isinstance(value, schema["type"]):
            return False
        if schema["type"] == list:
            all_valid = True
            for value_item in value:
                all_valid = all_valid and is_valid_against_schema(value_item, schema["elements"])
            return all_valid
        if schema["type"] == dict:
            all_valid = True
            for field in schema["fields"]:
                if field["name"] not in value and not field.get("optional"):
                    all_valid = False
                    break
                if field["name"] in value:
                    all_valid = all_valid and is_valid_against_schema(value[field["name"]], field)
            return all_valid
    elif callable(schema["type"]):
        if schema["type"].__call__(value):
            return True
        return False
    return False


def validate_schema(value, schema):
    if schema["type"] == list or schema["type"] == dict:
        if not isinstance(value, schema["type"]):
            return None
        if schema["type"] == list:
            output = []
            for value_item in value:
                result = validate_schema(value_item, schema["elements"])
                if not result:
                    return None
                output.append(result)
            return output
        if schema["type"] == dict:
            output = {}
            for field in schema["fields"]:
                if field["name"] not in value and not field.get("optional"):
                    return None
                if field["name"] in value:
                    result = validate_schema(value[field["name"]], field)
                    if not result:
                        return None
                    output[field["name"]] = result
            return output
    elif callable(schema["type"]):
        result = schema["type"].__call__(value)
        if result:
            return result
        return None
    return None


LOCATION_SHARING_SCHEMA = {
    "type": dict,
    "fields": [
        {"type": validate_word_id, "name": "id"},
        {"type": validate_decimal, "name": "lat"},
        {"type": validate_decimal, "name": "lon"},
    ],
}

if __name__ == "__main__":
    print(
        is_valid_against_schema(
            {
                "lat": "40.5123",
                "lon": "-71.4123",
                "id": "absent-topic-into",
            },
            LOCATION_SHARING_SCHEMA,
        )
    )
    print(
        is_valid_against_schema(
            {
                "lat": "40W",
                "lon": "-71S",
                "id": "tuna-orient-midnight",
            },
            LOCATION_SHARING_SCHEMA,
        )
    )
