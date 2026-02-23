"""Message models and utilities for Symphony adapter.

This module provides the SymphonyMessage struct and utility functions
for working with Symphony's MessageML format.
"""

from typing import List

from csp import Struct

from .mention import mention_user

__all__ = ("SymphonyMessage", "format_with_message_ml")


def format_with_message_ml(text: str, to_message_ml: bool = True) -> str:
    """Convert text to/from MessageML format.

    MessageML requires certain characters to be escaped. This function
    handles the conversion in both directions.

    Args:
        text: The text to convert.
        to_message_ml: If True, escape special characters for MessageML.
                       If False, unescape MessageML back to plain text.

    Returns:
        The converted text.
    """
    pairs = [
        ("&", "&#38;"),
        ("<", "&lt;"),
        (">", "&gt;"),
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
    """A message structure for Symphony communication.

    This struct represents both incoming and outgoing Symphony messages.

    Attributes:
        user: Display name of the message author.
        user_email: Email address of the author (useful for mentions).
        user_id: User ID of the author (useful for mentions and DMs).
        tags: List of user IDs mentioned in the message.
        room: Room name, "IM" for direct messages, or stream ID.
        msg: The message content (can be plain text or MessageML).
        form_id: Form ID for Symphony Elements action responses.
        form_values: Form field values for Symphony Elements actions.
        stream_id: The Symphony stream ID (set automatically for incoming messages).

    Examples:
        # Send a message to a room
        msg = SymphonyMessage(room="My Room", msg="Hello, World!")

        # Send a direct message to a user by ID
        msg = SymphonyMessage(room="IM", user_id="12345", msg="Hello!")

        # Reply to a user with a mention
        msg = SymphonyMessage(
            room=incoming_msg.room,
            msg=f"Hello {incoming_msg.mention()}!"
        )
    """

    user: str = ""
    user_email: str = ""
    user_id: str = ""
    tags: List[str] = []
    room: str = ""
    msg: str = ""
    form_id: str = ""
    form_values: dict = {}
    stream_id: str = ""

    def mention(self, use_email: bool = False) -> str:
        """Create a mention tag for the message author.

        Args:
            use_email: If True, use email for the mention instead of user ID.

        Returns:
            A MessageML mention tag string.

        Example:
            >>> msg = SymphonyMessage(user_id="12345", user_email="user@example.com")
            >>> msg.mention()
            '<mention uid="12345" />'
            >>> msg.mention(use_email=True)
            '<mention email="user@example.com" />'
        """
        if use_email and self.user_email:
            return mention_user(self.user_email)
        return mention_user(self.user_id) if self.user_id else ""

    def reply(
        self,
        text: str,
        mention_author: bool = False,
    ) -> "SymphonyMessage":
        """Create a reply message to this message.

        Args:
            text: The reply text content.
            mention_author: If True, prepend a mention of the original author.

        Returns:
            A new SymphonyMessage configured to reply to this message.

        Example:
            >>> incoming = SymphonyMessage(room="My Room", user_id="12345")
            >>> reply = incoming.reply("Thanks!", mention_author=True)
            >>> reply.msg
            '<mention uid="12345" /> Thanks!'
        """
        if mention_author and self.user_id:
            text = f"{self.mention()} {text}"

        return SymphonyMessage(
            room=self.room,
            msg=text,
            stream_id=self.stream_id,
        )

    def direct_reply(self, text: str) -> "SymphonyMessage":
        """Create a direct message (IM) reply to the author.

        Args:
            text: The message text content.

        Returns:
            A new SymphonyMessage configured as a DM to the author.

        Example:
            >>> incoming = SymphonyMessage(user_id="12345")
            >>> dm = incoming.direct_reply("This is private")
            >>> dm.room
            'IM'
        """
        return SymphonyMessage(
            room="IM",
            user_id=self.user_id,
            user=self.user,
            msg=text,
        )

    def is_direct_message(self) -> bool:
        """Check if this message is a direct message (IM).

        Returns:
            True if this is a direct message, False otherwise.
        """
        return self.room == "IM"

    def mentions_user(self, user_id: str) -> bool:
        """Check if this message mentions a specific user.

        Args:
            user_id: The user ID to check for.

        Returns:
            True if the user is mentioned, False otherwise.
        """
        return str(user_id) in self.tags

    def get_mentioned_users(self) -> List[str]:
        """Get the list of mentioned user IDs.

        Returns:
            List of user IDs mentioned in this message.
        """
        return list(self.tags)

    def is_form_submission(self) -> bool:
        """Check if this message is a form submission.

        Returns:
            True if this is a form submission, False otherwise.
        """
        return bool(self.form_id)

    def get_form_value(self, key: str, default=None):
        """Get a form field value.

        Args:
            key: The form field name.
            default: Default value if field is not present.

        Returns:
            The form field value, or default if not found.
        """
        return self.form_values.get(key, default)

    def with_message(self, msg: str) -> "SymphonyMessage":
        """Create a copy of this message with different content.

        Args:
            msg: The new message content.

        Returns:
            A new SymphonyMessage with the updated content.
        """
        return SymphonyMessage(
            user=self.user,
            user_email=self.user_email,
            user_id=self.user_id,
            tags=self.tags,
            room=self.room,
            msg=msg,
            form_id=self.form_id,
            form_values=self.form_values,
            stream_id=self.stream_id,
        )

    @classmethod
    def to_room(cls, room: str, msg: str) -> "SymphonyMessage":
        """Create a message to a specific room.

        Args:
            room: The room name or stream ID.
            msg: The message content.

        Returns:
            A new SymphonyMessage configured for the room.
        """
        return cls(room=room, msg=msg)

    @classmethod
    def to_user(cls, user_id: str, msg: str) -> "SymphonyMessage":
        """Create a direct message to a specific user.

        Args:
            user_id: The target user's ID.
            msg: The message content.

        Returns:
            A new SymphonyMessage configured as a DM.
        """
        return cls(room="IM", user_id=user_id, msg=msg)

    @classmethod
    def to_stream(cls, stream_id: str, msg: str) -> "SymphonyMessage":
        """Create a message to a specific stream.

        Args:
            stream_id: The Symphony stream ID.
            msg: The message content.

        Returns:
            A new SymphonyMessage configured for the stream.
        """
        return cls(stream_id=stream_id, msg=msg)
