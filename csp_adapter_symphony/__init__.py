"""CSP Adapter for Symphony.

This package provides a CSP adapter for Symphony by wrapping chatom's
SymphonyBackend. It provides real-time message streaming and processing
using the csp library.

The adapter uses chatom for all Symphony operations:
- Connection management via SymphonyBackend
- Message models via SymphonyMessage
- Presence management via SymphonyPresenceStatus
- Mention formatting utilities
"""

__version__ = "0.5.0"

# Re-export chatom types for convenience
from chatom.symphony import SymphonyBackend, SymphonyConfig, SymphonyMessage, SymphonyRoomMapper, SymphonyUser
from chatom.symphony.mention import (
    format_cashtag,
    format_hashtag,
    mention_user_by_email,
    mention_user_by_uid,
)
from chatom.symphony.presence import SymphonyPresenceStatus

# CSP adapter
from .adapter import SymphonyAdapter

# Alias for backwards compatibility
SymphonyAdapterConfig = SymphonyConfig

__all__ = [
    # Adapter
    "SymphonyAdapter",
    # Config
    "SymphonyAdapterConfig",
    "SymphonyConfig",  # chatom config
    "SymphonyRoomMapper",
    # Backend (from chatom)
    "SymphonyBackend",
    # Message (from chatom)
    "SymphonyMessage",
    # Presence (from chatom)
    "SymphonyPresenceStatus",
    # Mentions (from chatom)
    "mention_user_by_email",
    "mention_user_by_uid",
    "format_hashtag",
    "format_cashtag",
]
