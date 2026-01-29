"""Symphony adapter for CSP using chatom.

This module provides a CSP adapter for Symphony by wrapping chatom's
SymphonyBackend. It provides Symphony-specific enhancements on top of
the generic chatom CSP layer.
"""

import asyncio
import logging
from typing import Optional, Set

import csp
from chatom.csp import BackendAdapter
from chatom.symphony import SymphonyBackend, SymphonyConfig, SymphonyMessage
from chatom.symphony.presence import SymphonyPresenceStatus
from csp import ts

__all__ = (
    "SymphonyAdapter",
    "SymphonyPresenceStatus",
)

log = logging.getLogger(__name__)


class SymphonyAdapter(BackendAdapter):
    """CSP adapter for Symphony using chatom's SymphonyBackend.

    This adapter wraps chatom's SymphonyBackend and provides a CSP
    interface for reading and writing Symphony messages.

    The adapter handles:
    - Message subscription via datafeed
    - Message publishing
    - Presence management
    - Room/channel name resolution

    Attributes:
        backend: The underlying SymphonyBackend.
        config: The SymphonyConfig used by the backend.

    Example:
        >>> from chatom.symphony import SymphonyConfig
        >>> from csp_adapter_symphony import SymphonyAdapter
        >>>
        >>> config = SymphonyConfig(
        ...     host="company.symphony.com",
        ...     bot_username="my-bot",
        ...     bot_private_key_path="/path/to/key.pem",
        ... )
        >>> adapter = SymphonyAdapter(config)
        >>>
        >>> @csp.graph
        ... def my_bot():
        ...     messages = adapter.subscribe()
        ...     responses = process_messages(messages)
        ...     adapter.publish(responses)
        >>>
        >>> csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8))
    """

    def __init__(self, config: SymphonyConfig):
        """Initialize the Symphony adapter.

        Args:
            config: Symphony configuration from chatom.
        """
        backend = SymphonyBackend(config=config)
        super().__init__(backend)
        self._config = config

    @property
    def config(self) -> SymphonyConfig:
        """Get the Symphony configuration."""
        return self._config

    @property
    def symphony_backend(self) -> SymphonyBackend:
        """Get the underlying SymphonyBackend."""
        return self._backend

    # @csp.graph # NOTE: cannot use decorator, https://github.com/Point72/csp/issues/183
    def subscribe(
        self,
        channels: Optional[Set[str]] = None,
        rooms: Optional[Set[str]] = None,
        skip_own: bool = True,
        skip_history: bool = True,
    ) -> ts[[SymphonyMessage]]:
        """Subscribe to Symphony messages.

        Args:
            channels: Optional set of channels/rooms to filter (alias for rooms).
            rooms: Optional set of rooms to filter. Can be stream IDs or
                room names; names will be resolved to IDs at connection time.
            skip_own: If True, skip messages from the bot itself.
            skip_history: If True, skip messages before stream started.

        Returns:
            Time series of SymphonyMessage lists.

        Example:
            >>> @csp.graph
            ... def my_bot():
            ...     # Subscribe to specific rooms by name or ID
            ...     messages = adapter.subscribe(rooms={"Bot Room", "Support"})
            ...     messages = adapter.subscribe(channels={"abc123def456"})
            ...     # Or all rooms
            ...     messages = adapter.subscribe()
        """
        # Use channels if provided, otherwise fall back to rooms
        filter_channels = channels if channels is not None else rooms
        return super().subscribe(
            channels=filter_channels,
            skip_own=skip_own,
            skip_history=skip_history,
        )

    # @csp.graph. # NOTE: cannot use decorator, https://github.com/Point72/csp/issues/183
    def publish(self, msg: ts[SymphonyMessage]):
        """Publish messages to Symphony.

        Args:
            msg: Time series of SymphonyMessages to send.

        Example:
            >>> @csp.graph
            ... def my_bot():
            ...     response = csp.const(SymphonyMessage(
            ...         channel_id="stream123",
            ...         content="Hello from the bot!",
            ...     ))
            ...     adapter.publish(response)
        """
        # Use the base adapter's publish - it accepts Message which
        # SymphonyMessage inherits from
        super().publish(msg)

    @csp.node
    def _set_symphony_presence(self, presence: ts[SymphonyPresenceStatus], timeout: float = 5.0):
        """Internal node for setting Symphony presence.

        Uses a thread with asyncio.run() to avoid event loop conflicts.
        Creates a new backend instance per call to ensure proper async context.
        """
        if csp.ticked(presence):
            status = presence.name.lower()
            config = self._config
            backend_class = type(self._backend)

            def run_presence():
                async def set_presence_async():
                    # Create new backend for this thread (aiohttp sessions are loop-bound)
                    thread_backend = backend_class(config=config)
                    try:
                        await asyncio.wait_for(thread_backend.connect(), timeout=timeout)
                        await asyncio.wait_for(thread_backend.set_presence(status), timeout=timeout)
                    except asyncio.TimeoutError:
                        log.error("Timeout setting presence")
                    except Exception:
                        log.exception("Failed setting presence")
                    finally:
                        try:
                            await thread_backend.disconnect()
                        except Exception:
                            pass

                try:
                    asyncio.run(set_presence_async())
                except Exception:
                    log.exception("Error in presence thread")

            import threading

            thread = threading.Thread(target=run_presence, daemon=True)
            thread.start()

    # @csp.graph # NOTE: cannot use decorator, https://github.com/Point72/csp/issues/183
    def publish_presence(self, presence: ts[SymphonyPresenceStatus], timeout: float = 5.0):
        """Publish presence status updates.

        Args:
            presence: Time series of SymphonyPresenceStatus values.
            timeout: Timeout for presence API calls.

        Example:
            >>> @csp.graph
            ... def my_bot():
            ...     presence = csp.const(SymphonyPresenceStatus.AVAILABLE)
            ...     adapter.publish_presence(presence)
        """
        self._set_symphony_presence(presence=presence, timeout=timeout)
