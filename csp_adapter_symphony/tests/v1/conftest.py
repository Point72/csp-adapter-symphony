"""Pytest fixtures and mock BDK for testing."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class MockStream:
    """Mock Symphony stream object."""

    def __init__(self, stream_id: str = "mock_stream_123"):
        self.id = stream_id


class MockRoomInfo:
    """Mock room info response."""

    def __init__(self, name: str = "Test Room", room_id: str = "room123"):
        self.room_attributes = MagicMock()
        self.room_attributes.name = name
        self.room_system_info = MagicMock()
        self.room_system_info.id = room_id


class MockSearchResults:
    """Mock room search results."""

    def __init__(self, rooms=None):
        self.rooms = rooms or []


class MockStreamService:
    """Mock BDK StreamService."""

    def __init__(self):
        self.search_rooms = AsyncMock(return_value=MockSearchResults())
        self.get_room_info = AsyncMock(return_value=None)
        self.create_im = AsyncMock(return_value=MockStream("im_stream_123"))


class MockMessageService:
    """Mock BDK MessageService."""

    def __init__(self):
        self.send_message = AsyncMock(return_value=MagicMock())
        self.sent_messages = []

    async def send_message_tracking(self, stream_id: str, content: str):
        """Track sent messages for testing."""
        self.sent_messages.append({"stream_id": stream_id, "content": content})
        return MagicMock()


class MockPresenceService:
    """Mock BDK PresenceService."""

    def __init__(self):
        self.set_presence = AsyncMock()
        self.last_presence = None


class MockDatafeedLoop:
    """Mock BDK DatafeedLoop."""

    def __init__(self):
        self._listeners = []
        self._started = False
        self._should_stop = False

    def subscribe(self, listener):
        """Subscribe a listener."""
        self._listeners.append(listener)

    async def start(self):
        """Start the datafeed loop (mock - runs briefly then stops)."""
        self._started = True
        # In tests, we'll control when this stops
        import asyncio

        while not self._should_stop:
            await asyncio.sleep(0.01)

    async def stop(self):
        """Stop the datafeed loop."""
        self._should_stop = True

    async def simulate_message(self, initiator, event):
        """Simulate receiving a message for testing."""
        for listener in self._listeners:
            if hasattr(listener, "on_message_sent"):
                await listener.on_message_sent(initiator, event)


class MockSymphonyBdk:
    """Mock SymphonyBdk for testing."""

    def __init__(self, config=None):
        self.config = config
        self._message_service = MockMessageService()
        self._stream_service = MockStreamService()
        self._presence_service = MockPresenceService()
        self._datafeed_loop = MockDatafeedLoop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def messages(self):
        return self._message_service

    def streams(self):
        return self._stream_service

    def presence(self):
        return self._presence_service

    def datafeed(self):
        return self._datafeed_loop


@pytest.fixture
def mock_bdk():
    """Fixture providing a mock SymphonyBdk instance."""
    return MockSymphonyBdk()


@pytest.fixture
def mock_stream_service():
    """Fixture providing a mock StreamService."""
    return MockStreamService()


@pytest.fixture
def mock_message_service():
    """Fixture providing a mock MessageService."""
    return MockMessageService()


@pytest.fixture
def mock_initiator():
    """Fixture providing a mock V4Initiator."""
    initiator = MagicMock()
    initiator.user.display_name = "Test User"
    initiator.user.email = "test@example.com"
    initiator.user.user_id = 12345
    return initiator


@pytest.fixture
def mock_message_event():
    """Fixture providing a mock V4MessageSent event."""
    event = MagicMock()
    event.message.stream.stream_id = "stream123"
    event.message.stream.stream_type = "ROOM"
    event.message.message = "Hello, World!"
    event.message.data = None
    return event
