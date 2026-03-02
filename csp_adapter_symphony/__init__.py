"""CSP Adapter for Symphony.

This package provides a csp adapter for Symphony using the official
Symphony BDK (Bot Development Kit) for Python.
"""

__version__ = "0.4.0"

from .adapter import Presence, SymphonyAdapter, send_symphony_message
from .adapter_config import SymphonyAdapterConfig, SymphonyRoomMapper
from .mention import (
    extract_mentions_from_text,
    is_bot_mentioned,
    mention_by_email,
    mention_by_id,
    mention_user,
    mention_users,
)
from .message import SymphonyMessage, format_with_message_ml

__all__ = [
    # Adapter
    "Presence",
    "SymphonyAdapter",
    "send_symphony_message",
    # Config
    "SymphonyAdapterConfig",
    "SymphonyRoomMapper",
    # Message
    "SymphonyMessage",
    "format_with_message_ml",
    # Mentions
    "mention_user",
    "mention_users",
    "mention_by_email",
    "mention_by_id",
    "extract_mentions_from_text",
    "is_bot_mentioned",
]
