"""Mention utilities for Symphony MessageML.

This module provides functions for creating user mentions in Symphony's
MessageML format.
"""

from typing import List, Union

__all__ = (
    "mention_user",
    "mention_users",
    "mention_by_email",
    "mention_by_id",
    "extract_mentions_from_text",
)


def mention_user(email_or_userid: str = "") -> str:
    """Create a mention tag for a user.

    Automatically detects whether the input is an email or user ID
    and creates the appropriate mention tag.

    Args:
        email_or_userid: Either an email address or a user ID.

    Returns:
        A MessageML mention tag, or empty string if no input provided.

    Examples:
        >>> mention_user("user@example.com")
        '<mention email="user@example.com" />'
        >>> mention_user("12345")
        '<mention uid="12345" />'
    """
    if not email_or_userid:
        return ""

    email_or_userid = str(email_or_userid).strip()
    if "@" in email_or_userid:
        return f'<mention email="{email_or_userid}" />'
    else:
        return f'<mention uid="{email_or_userid}" />'


def mention_by_email(email: str) -> str:
    """Create a mention tag using an email address.

    Args:
        email: The user's email address.

    Returns:
        A MessageML mention tag.

    Example:
        >>> mention_by_email("user@example.com")
        '<mention email="user@example.com" />'
    """
    if not email:
        return ""
    return f'<mention email="{email.strip()}" />'


def mention_by_id(user_id: Union[str, int]) -> str:
    """Create a mention tag using a user ID.

    Args:
        user_id: The user's Symphony ID.

    Returns:
        A MessageML mention tag.

    Example:
        >>> mention_by_id(12345)
        '<mention uid="12345" />'
    """
    if not user_id:
        return ""
    return f'<mention uid="{user_id}" />'


def mention_users(identifiers: List[str], separator: str = " ") -> str:
    """Create mention tags for multiple users.

    Args:
        identifiers: List of email addresses or user IDs.
        separator: String to use between mentions.

    Returns:
        A string of mention tags separated by the given separator.

    Example:
        >>> mention_users(["12345", "user@example.com"])
        '<mention uid="12345" /> <mention email="user@example.com" />'
    """
    mentions = [mention_user(identifier) for identifier in identifiers if identifier]
    return separator.join(filter(None, mentions))


def extract_mentions_from_text(text: str) -> List[str]:
    """Extract user IDs from mention tags in MessageML text.

    Args:
        text: MessageML text containing mention tags.

    Returns:
        List of user IDs mentioned in the text.

    Example:
        >>> extract_mentions_from_text('Hello <mention uid="12345" /> and <mention uid="67890" />')
        ['12345', '67890']
    """
    import re

    mentions = []
    # Match uid mentions
    uid_pattern = r'<mention\s+uid="([^"]+)"\s*/>'
    for match in re.finditer(uid_pattern, text):
        mentions.append(match.group(1))
    return mentions


def format_at_mention(display_name: str, user_id: str) -> str:
    """Create a formatted @mention with display text.

    This creates a mention that will show the display name in the Symphony
    client while linking to the user's profile.

    Args:
        display_name: The text to display (typically the user's name).
        user_id: The user's Symphony ID.

    Returns:
        A formatted mention string.

    Note:
        In MessageML, the display text is not customizable - Symphony
        will display the user's actual name. This function creates a
        standard mention tag; the display_name parameter is for reference only.
    """
    return mention_by_id(user_id)


def is_bot_mentioned(text: str, bot_id: str) -> bool:
    """Check if a specific user (typically the bot) is mentioned in text.

    Args:
        text: The MessageML text to check.
        bot_id: The bot's user ID.

    Returns:
        True if the bot is mentioned, False otherwise.

    Example:
        >>> is_bot_mentioned('<mention uid="12345" /> hello', "12345")
        True
    """
    return str(bot_id) in extract_mentions_from_text(text)
