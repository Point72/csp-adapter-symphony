from typing import List

from csp import Struct

__all__ = ("SymphonyMessage", "format_with_message_ml")


def format_with_message_ml(text, to_message_ml: bool = True) -> str:
    """If to_message_ml, we convert to message ml by replacing special sequences of character. Else, we convert from message_ml in the same way"""
    pairs = [
        ("&", "&#38;"),
        ("<", "&lt;"),
        ("${", "&#36;{"),
        ("#{", "&#35;{"),
    ]

    for original, msg_ml_version in pairs:
        if to_message_ml:
            text = text.replace(original, msg_ml_version)
        else:
            text = text.replace(msg_ml_version, original)

    return text


class SymphonyMessage(Struct):
    user: str
    user_email: str  # email of the author, for mentions
    user_id: str  # uid of the author, for mentions
    tags: List[str]  # list of user ids in message, for mentions
    room: str
    msg: str
    form_id: str
    form_values: dict
