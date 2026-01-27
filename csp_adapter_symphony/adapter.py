"""Symphony adapter using symphony-bdk-python.

This module provides a csp adapter for Symphony using the official
Symphony BDK (Bot Development Kit) for Python.
"""

import asyncio
import json
import logging
import ssl
import threading
from queue import Queue
from typing import List, Optional, Set

import csp
from csp import ts
from csp.impl.enum import Enum
from csp.impl.pushadapter import PushInputAdapter
from csp.impl.wiring import py_push_adapter_def

# Import BDK types - these are required at runtime
try:
    from symphony.bdk.core.auth.exception import AuthUnauthorizedError
    from symphony.bdk.core.service.datafeed.real_time_event_listener import RealTimeEventListener
    from symphony.bdk.core.symphony_bdk import SymphonyBdk
    from symphony.bdk.gen.agent_model.v4_initiator import V4Initiator
    from symphony.bdk.gen.agent_model.v4_message_sent import V4MessageSent
    from symphony.bdk.gen.agent_model.v4_symphony_elements_action import V4SymphonyElementsAction

    _BDK_AVAILABLE = True
except ImportError:
    _BDK_AVAILABLE = False
    # Define placeholder types for type checking when BDK is not installed
    AuthUnauthorizedError = Exception
    RealTimeEventListener = object
    SymphonyBdk = None
    V4Initiator = None
    V4MessageSent = None
    V4SymphonyElementsAction = None

from .adapter_config import SymphonyAdapterConfig, SymphonyRoomMapper
from .message import SymphonyMessage, format_with_message_ml

__all__ = ("Presence", "SymphonyAdapter", "send_symphony_message")

log = logging.getLogger(__name__)


def _check_bdk_available():
    """Check if symphony-bdk-python is available."""
    if not _BDK_AVAILABLE:
        raise ImportError("symphony-bdk-python is required but not installed. Install it with: pip install symphony-bdk-python")


class Presence(csp.Enum):
    """Presence status for Symphony users."""

    AVAILABLE = Enum.auto()
    BUSY = Enum.auto()
    AWAY = Enum.auto()
    ON_THE_PHONE = Enum.auto()
    BE_RIGHT_BACK = Enum.auto()
    IN_A_MEETING = Enum.auto()
    OUT_OF_OFFICE = Enum.auto()
    OFF_WORK = Enum.auto()


def _get_user_mentions(data: str) -> List[str]:
    """Extract user mentions from message data payload.

    Args:
        data: JSON string containing message data.

    Returns:
        List of user IDs mentioned in the message.
    """
    user_mentions = []
    try:
        payload_data = json.loads(data or "{}")
        for value in payload_data.values():
            if isinstance(value, dict) and value.get("type") == "com.symphony.user.mention":
                # Extract user ID from mention
                id_list = value.get("id", [])
                for id_item in id_list:
                    if isinstance(id_item, dict) and "value" in id_item:
                        user_mentions.append(str(id_item["value"]))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return user_mentions


def _handle_message_sent(
    initiator: V4Initiator,
    event: V4MessageSent,
    room_ids: Set[str],
    room_mapper: SymphonyRoomMapper,
) -> Optional[SymphonyMessage]:
    """Convert a V4MessageSent event to a SymphonyMessage.

    Args:
        initiator: The event initiator.
        event: The message sent event.
        room_ids: Set of room IDs to filter (empty means accept all).
        room_mapper: Room mapper for name/ID resolution.

    Returns:
        A SymphonyMessage if the event matches filters, None otherwise.
    """
    message = event.message
    if not message:
        return None

    stream = message.stream
    if not stream:
        return None

    stream_id = stream.stream_id
    if room_ids and stream_id not in room_ids:
        return None

    user = initiator.user if initiator else None
    user_name = user.display_name if user else "USER_ERROR"
    user_email = user.email if user else "USER_ERROR"
    user_id = str(user.user_id) if user else "USER_ERROR"

    # Extract mentions from message data
    user_mentions = _get_user_mentions(message.data or "")

    # Determine room type and name
    stream_type = stream.stream_type
    log.debug(f"_handle_message_sent: stream_type={stream_type}, stream_id={stream_id}")
    if stream_type == "ROOM":
        room_name = room_mapper.get_room_name(stream_id)
        if not room_name:
            # Register the room for future lookups
            room_name = stream_id
    elif stream_type == "IM":
        # Register the IM stream for the user so bot can respond
        room_mapper.set_im_id(user_name, stream_id)
        room_mapper.set_im_id(user_id, stream_id)
        room_name = "IM"
    else:
        room_name = stream_id

    return SymphonyMessage(
        user=user_name,
        user_email=user_email,
        user_id=user_id,
        tags=user_mentions,
        room=room_name,
        msg=message.message or "",
        stream_id=stream_id,
    )


def _handle_elements_action(
    initiator: V4Initiator,
    event: V4SymphonyElementsAction,
    room_ids: Set[str],
    room_mapper: SymphonyRoomMapper,
) -> Optional[SymphonyMessage]:
    """Convert a V4SymphonyElementsAction event to a SymphonyMessage.

    Args:
        initiator: The event initiator.
        event: The elements action event.
        room_ids: Set of room IDs to filter (empty means accept all).
        room_mapper: Room mapper for name/ID resolution.

    Returns:
        A SymphonyMessage if the event matches filters, None otherwise.
    """
    stream = event.stream
    if not stream:
        return None

    stream_id = stream.stream_id
    if room_ids and stream_id not in room_ids:
        return None

    user = initiator.user if initiator else None
    user_name = user.display_name if user else "USER_ERROR"
    user_email = user.email if user else "USER_ERROR"
    user_id = str(user.user_id) if user else "USER_ERROR"

    # Determine room type and name
    stream_type = stream.stream_type
    if stream_type == "ROOM":
        room_name = room_mapper.get_room_name(stream_id)
        if not room_name:
            room_name = stream_id
    elif stream_type == "IM":
        room_mapper.set_im_id(user_name, stream_id)
        room_mapper.set_im_id(user_id, stream_id)
        room_name = "IM"
    else:
        room_name = stream_id

    return SymphonyMessage(
        user=user_name,
        user_email=user_email,
        user_id=user_id,
        tags=[],
        room=room_name,
        form_id=event.form_id or "",
        form_values=event.form_values or {},
        stream_id=stream_id,
    )


class CspRealTimeEventListener(RealTimeEventListener):
    """Real-time event listener that pushes events to a queue for CSP processing."""

    def __init__(
        self,
        message_queue: Queue,
        room_ids: Set[str],
        room_mapper: SymphonyRoomMapper,
    ):
        """Initialize the event listener.

        Args:
            message_queue: Queue to push messages to.
            room_ids: Set of room IDs to filter (empty means accept all).
            room_mapper: Room mapper for name/ID resolution.
        """
        self._queue = message_queue
        self._room_ids = room_ids
        self._room_mapper = room_mapper

    @staticmethod
    async def is_accepting_event(event, bot_info) -> bool:
        """Check if we should handle this event. Accept all events except from the bot itself."""
        try:
            initiator_id = event.initiator.user.user_id if event.initiator and event.initiator.user else None
            bot_id = bot_info.id if bot_info else None
            is_from_bot = initiator_id == bot_id
            log.debug(f"is_accepting_event: initiator_id={initiator_id}, bot_id={bot_id}, accepting={not is_from_bot}")
            return not is_from_bot
        except AttributeError as e:
            log.debug(f"is_accepting_event: AttributeError - {e}, returning True to accept anyway")
            return True  # Accept events even if we can't check the initiator

    async def on_message_sent(self, initiator: V4Initiator, event: V4MessageSent):
        """Handle message sent events."""
        log.debug(f"on_message_sent: Received message event from {initiator.user.display_name if initiator and initiator.user else 'unknown'}")
        msg = _handle_message_sent(initiator, event, self._room_ids, self._room_mapper)
        if msg:
            log.debug(f"on_message_sent: Queuing message: {msg.msg[:50] if msg.msg else 'empty'}")
            self._queue.put(msg)
        else:
            log.debug("on_message_sent: Message filtered out or invalid")

    async def on_symphony_elements_action(self, initiator: V4Initiator, event: V4SymphonyElementsAction):
        """Handle form/elements action events."""
        msg = _handle_elements_action(initiator, event, self._room_ids, self._room_mapper)
        if msg:
            self._queue.put(msg)


class SymphonyReaderPushAdapterImpl(PushInputAdapter):
    """Push adapter implementation for reading Symphony messages using BDK."""

    def __init__(
        self,
        config: SymphonyAdapterConfig,
        rooms: Set[str],
        exit_msg: str = "",
        room_mapper: Optional[SymphonyRoomMapper] = None,
    ):
        """Setup Symphony Reader.

        Args:
            config: Config specifying the BDK configuration.
            rooms: Set of room names to listen to (empty for all rooms).
            exit_msg: Message to send on shutdown.
            room_mapper: Room mapper for name/ID caching.
        """
        _check_bdk_available()
        self._thread = None
        self._running = False
        self._config = config
        self._rooms = rooms
        self._room_ids: Set[str] = set()
        self._exit_msg = exit_msg
        self._room_mapper = room_mapper or SymphonyRoomMapper()
        self._message_queue: Queue = Queue()
        self._bdk: Optional[SymphonyBdk] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._error: Optional[Exception] = None  # Store any fatal error

    def start(self, starttime, endtime):
        """Start the adapter."""
        # Start reader thread with its own event loop
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = True
        self._thread.start()

    def stop(self):
        """Stop the adapter."""
        if self._running:
            self._running = False
            # Signal the thread to stop
            self._message_queue.put(None)
            if self._loop:
                # Cancel the datafeed loop
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5.0)

        # Re-raise any error from the reader thread
        if self._error:
            raise self._error

    def _run(self):
        """Run the datafeed loop in a separate thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_run())
        except AuthUnauthorizedError as e:
            log.error(f"Authentication failed: {e}")
            self._error = RuntimeError(f"Symphony authentication failed: {e}")
            self._running = False
            # Print to stderr for visibility
            import sys

            print(f"\n*** FATAL: Symphony authentication failed: {e} ***\n", file=sys.stderr)
            # Exit the process on auth failure
            import os

            os._exit(1)
        except ssl.SSLError as e:
            log.error(f"SSL error: {e}")
            self._error = RuntimeError(f"Symphony SSL error: {e}")
            self._running = False
            import sys

            print(f"\n*** FATAL: SSL error connecting to Symphony: {e} ***", file=sys.stderr)
            print("If using a self-signed certificate, set ssl_trust_store_path to your CA cert file.", file=sys.stderr)
            print("Or set ssl_verify=False to disable SSL verification (not recommended for production).\n", file=sys.stderr)
            import os

            os._exit(1)
        except FileNotFoundError as e:
            log.error(f"File not found: {e}")
            self._error = e
            self._running = False
            import sys

            print(f"\n*** FATAL: File not found: {e} ***", file=sys.stderr)
            print("Check that private_key_path and certificate_path point to valid files.\n", file=sys.stderr)
            import os

            os._exit(1)
        except Exception as e:
            # Check if it's an SSLError wrapped in another exception
            if "SSL" in str(e) or "ssl" in str(e).lower():
                log.error(f"SSL error: {e}")
                self._error = RuntimeError(f"Symphony SSL error: {e}")
                self._running = False
                import sys

                print(f"\n*** FATAL: SSL error connecting to Symphony: {e} ***", file=sys.stderr)
                print("If using a self-signed certificate, set ssl_trust_store_path to your CA cert file.", file=sys.stderr)
                print("Or set ssl_verify=False to disable SSL verification (not recommended for production).\n", file=sys.stderr)
                import os

                os._exit(1)
            # Check for file not found errors
            if "No such file" in str(e) or "FileNotFoundError" in str(type(e).__name__):
                log.error(f"File not found: {e}")
                self._error = e
                self._running = False
                import sys

                print(f"\n*** FATAL: File not found: {e} ***", file=sys.stderr)
                print("Check that private_key_path and certificate_path point to valid files.\n", file=sys.stderr)
                import os

                os._exit(1)
            log.exception(f"Error in Symphony reader: {e}")
            self._error = e
            self._running = False
            # Exit on any unhandled error to prevent hanging
            import sys

            print(f"\n*** FATAL: Error in Symphony reader: {e} ***\n", file=sys.stderr)
            import os

            os._exit(1)
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
            # Push None to unblock any waiting on the queue
            self._message_queue.put(None)

    async def _async_run(self):
        """Async main loop for reading from Symphony."""
        bdk_config = self._config.bdk_config
        if not bdk_config:
            raise ValueError("BDK config not available")

        async with SymphonyBdk(bdk_config) as bdk:
            self._bdk = bdk
            self._room_mapper.set_stream_service(bdk.streams())

            # Resolve room names to IDs
            for room in self._rooms:
                room_id = await self._room_mapper.get_room_id_async(room)
                if room_id:
                    self._room_ids.add(room_id)
                else:
                    log.warning(f"Could not find room ID for room: {room}")

            # Create and register the event listener
            listener = CspRealTimeEventListener(
                self._message_queue,
                self._room_ids,
                self._room_mapper,
            )

            datafeed_loop = bdk.datafeed()
            datafeed_loop.subscribe(listener)

            log.info("Datafeed loop subscribed, starting...")
            print("Bot is ready and listening for messages...", flush=True)

            # Start a task to process the message queue
            queue_task = asyncio.create_task(self._process_queue())

            try:
                # Run the datafeed loop
                await datafeed_loop.start()
            except asyncio.CancelledError:
                pass
            finally:
                queue_task.cancel()

            # Send exit message if configured
            if self._exit_msg and self._room_ids:
                try:
                    room_id = next(iter(self._room_ids))
                    await bdk.messages().send_message(
                        room_id,
                        f"<messageML>{self._exit_msg}</messageML>",
                    )
                except Exception as e:
                    log.error(f"Error sending exit message: {e}")

    async def _process_queue(self):
        """Process messages from the queue and push to CSP."""
        log.debug("_process_queue: Starting message queue processor")
        while self._running:
            try:
                # Non-blocking check with small timeout
                await asyncio.sleep(0.01)
                messages = []
                while not self._message_queue.empty():
                    msg = self._message_queue.get_nowait()
                    if msg is None:
                        return
                    messages.append(msg)
                if messages:
                    log.debug(f"_process_queue: Pushing {len(messages)} message(s) to CSP")
                    self.push_tick(messages)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.exception(f"Error processing message queue: {e}")


SymphonyReaderPushAdapter = py_push_adapter_def(
    "SymphonyReaderPushAdapter",
    SymphonyReaderPushAdapterImpl,
    ts[[SymphonyMessage]],
    config=object,
    rooms=set,
    exit_msg=str,
    room_mapper=object,
    memoize=False,
)


async def send_symphony_message_async(
    bdk: SymphonyBdk,
    msg: SymphonyMessage,
    room_mapper: SymphonyRoomMapper,
    config: SymphonyAdapterConfig,
) -> bool:
    """Send a message to Symphony using the BDK.

    Args:
        bdk: The SymphonyBdk instance.
        msg: The message to send.
        room_mapper: Room mapper for name/ID resolution.
        config: Adapter configuration.

    Returns:
        True if message was sent successfully, False otherwise.
    """
    log.debug(f"send_symphony_message_async: msg.room={msg.room}, msg.stream_id={msg.stream_id}, msg.msg={msg.msg[:50] if msg.msg else 'empty'}...")
    try:
        message_service = bdk.messages()
        stream_service = bdk.streams()

        # Determine the target stream
        stream_id = None

        if msg.stream_id:
            # Use stream ID if provided directly
            stream_id = msg.stream_id
        elif msg.room == "IM":
            # Create or get IM stream for the user
            if msg.user_id:
                try:
                    stream = await stream_service.create_im(int(msg.user_id))
                    stream_id = stream.id
                    room_mapper.set_im_id(msg.user_id, stream_id)
                except Exception as e:
                    log.error(f"Error creating IM for user {msg.user_id}: {e}")
            elif msg.user:
                # Try to get cached IM stream for user
                stream_id = room_mapper.get_room_id(msg.user)
        else:
            # Regular room - look up by name
            stream_id = await room_mapper.get_room_id_async(msg.room)

        if not stream_id:
            error = f"Cannot find stream ID for: {msg.room}"
            log.error(error)
            if config.error_room:
                error_stream_id = await room_mapper.get_room_id_async(config.error_room)
                if error_stream_id:
                    await message_service.send_message(
                        error_stream_id,
                        f"<messageML>{format_with_message_ml(error)}</messageML>",
                    )
            return False

        # Send the message
        content = msg.msg
        if not content.strip().startswith("<messageML>"):
            content = f"<messageML>{content}</messageML>"

        await message_service.send_message(stream_id, content)
        return True

    except Exception as e:
        log.exception(f"Error sending message: {e}")
        if config.inform_client and msg.room != "IM":
            try:
                stream_id = await room_mapper.get_room_id_async(msg.room)
                if stream_id:
                    await bdk.messages().send_message(
                        stream_id,
                        "<messageML>ERROR: Could not send message on Symphony</messageML>",
                    )
            except Exception:
                pass
        return False


def _send_messages_thread(
    msg_queue: Queue,
    config: SymphonyAdapterConfig,
    room_mapper: SymphonyRoomMapper,
):
    """Thread function to send messages from queue to Symphony."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        bdk_config = config.bdk_config
        if not bdk_config:
            log.error("BDK config not available for sending messages")
            return

        async with SymphonyBdk(bdk_config) as bdk:
            room_mapper.set_stream_service(bdk.streams())

            while True:
                # Get message from queue (blocking)
                msg = await loop.run_in_executor(None, msg_queue.get)
                msg_queue.task_done()

                if msg is None:
                    break

                try:
                    await send_symphony_message_async(bdk, msg, room_mapper, config)
                except Exception:
                    log.exception("Failed sending message to Symphony")

    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


# Backwards compatibility function
def send_symphony_message(
    msg: str,
    room_id: str,
    message_create_url: str = "",
    header: dict = None,
    *,
    bdk: SymphonyBdk = None,
):
    """Send a message to Symphony.

    This function is provided for backwards compatibility. For new code,
    use the SymphonyAdapter.publish() method instead.

    Args:
        msg: The message content (will be wrapped in messageML).
        room_id: The stream ID to send to.
        message_create_url: Deprecated, not used with BDK.
        header: Deprecated, not used with BDK.
        bdk: Optional SymphonyBdk instance. If not provided, a warning is logged.
    """
    if bdk is None:
        log.warning("send_symphony_message called without BDK instance. This function is deprecated. Use SymphonyAdapter.publish() instead.")
        return None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(bdk.messages().send_message(room_id, f"<messageML>{msg}</messageML>"))
    finally:
        loop.close()


def _set_presence_sync(config: SymphonyAdapterConfig, presence_value: Presence, timeout: float = 5.0):
    """Synchronously set presence status using BDK."""

    async def _async_set_presence():
        bdk_config = config.bdk_config
        if not bdk_config:
            log.error("BDK config not available for setting presence")
            return

        async with SymphonyBdk(bdk_config) as bdk:
            from symphony.bdk.core.service.presence.presence_service import PresenceStatus

            # Map our Presence enum to BDK PresenceStatus
            status_map = {
                Presence.AVAILABLE: PresenceStatus.AVAILABLE,
                Presence.BUSY: PresenceStatus.BUSY,
                Presence.AWAY: PresenceStatus.AWAY,
                Presence.ON_THE_PHONE: PresenceStatus.ON_THE_PHONE,
                Presence.BE_RIGHT_BACK: PresenceStatus.BE_RIGHT_BACK,
                Presence.IN_A_MEETING: PresenceStatus.IN_A_MEETING,
                Presence.OUT_OF_OFFICE: PresenceStatus.OUT_OF_OFFICE,
                Presence.OFF_WORK: PresenceStatus.OFF_WORK,
            }
            bdk_status = status_map.get(presence_value, PresenceStatus.AVAILABLE)
            await bdk.presence().set_presence(bdk_status, soft=True)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(asyncio.wait_for(_async_set_presence(), timeout=timeout))
    except asyncio.TimeoutError:
        log.error("Timeout setting presence")
    except Exception:
        log.exception("Failed setting presence")
    finally:
        loop.close()


class SymphonyAdapter:
    """Main adapter class for Symphony integration with CSP."""

    def __init__(self, config: SymphonyAdapterConfig):
        """Initialize the Symphony adapter.

        Args:
            config: Configuration for the adapter.
        """
        _check_bdk_available()
        self._config = config
        self._room_mapper = SymphonyRoomMapper()

    @csp.graph
    def subscribe(self, rooms: Set[str] = None, exit_msg: str = "") -> ts[[SymphonyMessage]]:
        """Subscribe to Symphony messages.

        Args:
            rooms: Set of room names to listen to. If empty, listens to all rooms.
            exit_msg: Optional message to send when shutting down.

        Returns:
            Time series of SymphonyMessage lists.
        """
        if rooms is None:
            rooms = set()
        return SymphonyReaderPushAdapter(
            config=self._config,
            rooms=rooms,
            exit_msg=exit_msg,
            room_mapper=self._room_mapper,
        )

    @csp.node
    def _symphony_write(self, msg: ts[SymphonyMessage]):
        """Internal node for writing messages to Symphony."""
        with csp.state():
            s_thread = None
            s_queue = None

        with csp.start():
            s_queue = Queue(maxsize=0)
            s_thread = threading.Thread(
                target=_send_messages_thread,
                args=(s_queue, self._config, self._room_mapper),
                daemon=True,
            )
            s_thread.start()

        with csp.stop():
            if s_thread:
                s_queue.put(None)
                s_queue.join()
                s_thread.join(timeout=5.0)

        if csp.ticked(msg):
            s_queue.put(msg)

    @csp.node
    def _set_presence(self, presence: ts[Presence], timeout: float = 5.0):
        """Set the bot's presence status."""
        if csp.ticked(presence):
            _set_presence_sync(self._config, presence, timeout)

    @csp.graph
    def publish_presence(self, presence: ts[Presence], timeout: float = 5.0):
        """Publish presence status updates.

        Args:
            presence: Time series of presence status updates.
            timeout: Timeout for presence API calls.
        """
        self._set_presence(presence=presence, timeout=timeout)

    @csp.graph
    def publish(self, msg: ts[SymphonyMessage]):
        """Publish messages to Symphony.

        Args:
            msg: Time series of messages to send.
        """
        self._symphony_write(msg=msg)
