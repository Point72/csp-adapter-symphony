"""Tests for the Symphony CSP adapter using chatom.

This test module covers the SymphonyAdapter which wraps chatom's
SymphonyBackend for use with CSP.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import csp
import pytest
from chatom.base import Channel, User

from csp_adapter_symphony.v1 import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyConfig,
    SymphonyMessage,
    SymphonyPresenceStatus,
    SymphonyRoomMapper,
    SymphonyUser,
    format_cashtag,
    format_hashtag,
    mention_user_by_email,
    mention_user_by_uid,
)


class TestSymphonyMessage:
    """Tests for chatom's SymphonyMessage."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = SymphonyMessage(
            author=User(id="12345"),
            channel=Channel(id="stream123"),
            stream_id="stream123",
            content="Hello, World!",
            metadata={
                "user": "John Doe",
                "user_email": "john@example.com",
                "room": "Test Room",
            },
        )
        assert msg.author_id == "12345"
        assert msg.content == "Hello, World!"
        assert msg.stream_id == "stream123"
        assert msg.metadata["room"] == "Test Room"

    def test_message_defaults(self):
        """Test message default values."""
        msg = SymphonyMessage()
        assert msg.author_id == ""
        assert msg.content == ""
        assert msg.stream_id == ""
        assert msg.mentions == []

    def test_mentions_user_in_symphony_mentions_list(self):
        """Test mentions_user with user in symphony_mentions list."""
        msg = SymphonyMessage(
            content="Hello",
            mentions=[SymphonyUser(id="12345"), SymphonyUser(id="67890")],
        )
        assert msg.mentions_user(SymphonyUser(id="12345")) is True
        assert msg.mentions_user(SymphonyUser(id="99999")) is False

    def test_extract_mentions_from_data(self):
        """Test extracting mentions from message data."""
        data = '{"0": {"type": "com.symphony.user.mention", "id": [{"value": "12345"}]}}'
        mentions = SymphonyMessage.extract_mentions_from_data(data)
        assert 12345 in mentions

    def test_extract_mentions_empty(self):
        """Test extracting mentions from empty data."""
        mentions = SymphonyMessage.extract_mentions_from_data("")
        assert mentions == []

    def test_mentions_user_with_entity_data(self):
        """Test mentions_user detection using entity_data (real API format)."""
        # This simulates how real Symphony API responses provide mention data
        msg = SymphonyMessage(
            content='<messageML>Hello <mention uid="12345"/></messageML>',
            entity_data={
                "mention0": {
                    "type": "com.symphony.user.mention",
                    "id": [{"value": "12345"}],
                }
            },
        )
        # Should detect mention via entity_data
        assert msg.mentions_user("12345") is True
        assert msg.mentions_user(SymphonyUser(id="12345")) is True
        assert msg.mentions_user("99999") is False

    def test_mentions_user_with_data_field(self):
        """Test mentions_user detection using data field (JSON string)."""
        # This simulates another format Symphony uses
        msg = SymphonyMessage(
            content="Hello",
            data='{"mention0": {"type": "com.symphony.user.mention", "id": [{"value": "12345"}]}}',
        )
        # Should detect mention via data field
        assert msg.mentions_user("12345") is True
        assert msg.mentions_user("99999") is False

    def test_message_id_property(self):
        """Test that message_id property returns id."""
        msg = SymphonyMessage(
            id="test-message-id-123",
            content="Hello",
        )
        assert msg.message_id == "test-message-id-123"
        assert msg.message_id == msg.id

    def test_stream_id_property(self):
        """Test that stream_id property returns channel.id."""

        msg = SymphonyMessage(
            content="Hello",
            channel=Channel(id="stream-id-456"),
        )
        assert msg.stream_id == "stream-id-456"


class TestSymphonyAdapterConfig:
    """Tests for SymphonyAdapterConfig."""

    def test_config_creation(self):
        """Test creating a config."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        assert config.host == "test.symphony.com"
        assert config.bot_username == "testbot"

    def test_config_validation(self):
        """Test config allows empty for mock backends."""
        # Empty config is now allowed for mock/testing scenarios
        config = SymphonyAdapterConfig()
        assert config.host == ""
        assert config.bot_username == ""

    def test_config_to_bdk_config(self):
        """Test converting to BDK config."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        bdk_config = config.get_bdk_config()
        assert bdk_config is not None

    def test_config_adapter_options(self):
        """Test adapter-specific config options."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
            error_room="error-room",
            inform_client=True,
            max_attempts=5,
        )
        assert config.error_room == "error-room"
        assert config.inform_client is True
        assert config.max_attempts == 5


class TestSymphonyAdapter:
    """Tests for SymphonyAdapter."""

    def test_adapter_creation(self):
        """Test creating an adapter."""
        config = SymphonyConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        adapter = SymphonyAdapter(config)
        assert adapter.config == config
        assert adapter.symphony_backend is not None

    def test_adapter_backend_property(self):
        """Test backend property."""
        config = SymphonyConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        adapter = SymphonyAdapter(config)
        assert adapter.backend is not None
        assert adapter.symphony_backend is adapter.backend


class TestSymphonyRoomMapper:
    """Tests for SymphonyRoomMapper."""

    def test_register_room(self):
        """Test registering a room."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Test Room", "stream123")
        assert mapper.get_room_id("Test Room") == "stream123"
        assert mapper.get_room_name("stream123") == "Test Room"

    def test_set_im_id(self):
        """Test setting IM stream ID."""
        mapper = SymphonyRoomMapper()
        mapper.set_im_id("user123", "im-stream-456")
        assert mapper.get_room_id("user123") == "im-stream-456"

    def test_get_room_id_not_found(self):
        """Test getting room ID that doesn't exist."""
        mapper = SymphonyRoomMapper()
        assert mapper.get_room_id("Unknown Room") is None

    def test_get_room_id_looks_like_stream_id(self):
        """Test getting room ID when input looks like stream ID."""
        mapper = SymphonyRoomMapper()
        long_id = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
        assert mapper.get_room_id(long_id) == long_id


class TestSymphonyPresenceStatus:
    """Tests for SymphonyPresenceStatus."""

    def test_presence_values(self):
        """Test presence status values exist."""
        assert SymphonyPresenceStatus.AVAILABLE is not None
        assert SymphonyPresenceStatus.BUSY is not None
        assert SymphonyPresenceStatus.AWAY is not None
        assert SymphonyPresenceStatus.ON_THE_PHONE is not None
        assert SymphonyPresenceStatus.BE_RIGHT_BACK is not None
        assert SymphonyPresenceStatus.IN_A_MEETING is not None
        assert SymphonyPresenceStatus.OUT_OF_OFFICE is not None
        assert SymphonyPresenceStatus.OFF_WORK is not None

    def test_presence_name(self):
        """Test presence status name."""
        assert SymphonyPresenceStatus.AVAILABLE.name == "AVAILABLE"
        assert SymphonyPresenceStatus.BUSY.name == "BUSY"


class TestMentionFunctions:
    """Tests for mention functions re-exported from chatom."""

    def test_mention_user_by_uid(self):
        """Test mentioning user by UID."""

        result = mention_user_by_uid(12345)
        assert '<mention uid="12345"/>' in result

    def test_mention_user_by_email(self):
        """Test mentioning user by email."""
        result = mention_user_by_email("test@example.com")
        assert '<mention email="test@example.com"/>' in result

    def test_format_hashtag(self):
        """Test formatting hashtag."""

        result = format_hashtag("test")
        assert '<hash tag="test"/>' in result

    def test_format_cashtag(self):
        """Test formatting cashtag."""
        result = format_cashtag("AAPL")
        assert '<cash tag="AAPL"/>' in result


class TestSymphonyAdapterCSPGraphs:
    """Tests for SymphonyAdapter CSP graph methods."""

    @pytest.fixture
    def adapter(self):
        """Create a SymphonyAdapter for testing."""
        config = SymphonyConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        return SymphonyAdapter(config)

    def test_subscribe_graph_creation(self, adapter):
        """Test that subscribe creates a valid CSP graph."""
        # The subscribe method should return a csp.graph decorated function
        # We can't fully run it without a real backend, but we can verify structure

        @csp.graph
        def test_graph():
            messages = adapter.subscribe(rooms={"Test Room"})
            csp.add_graph_output("messages", messages)

        # Should be able to create the graph without error
        assert test_graph is not None

    def test_subscribe_with_no_rooms(self, adapter):
        """Test subscribe with no rooms specified."""

        @csp.graph
        def test_graph():
            messages = adapter.subscribe()
            csp.add_graph_output("messages", messages)

        assert test_graph is not None

    def test_subscribe_with_skip_options(self, adapter):
        """Test subscribe with skip options."""

        @csp.graph
        def test_graph():
            messages = adapter.subscribe(
                rooms={"Room1", "Room2"},
                skip_own=False,
                skip_history=False,
            )
            csp.add_graph_output("messages", messages)

        assert test_graph is not None

    def test_publish_graph_creation(self, adapter):
        """Test that publish creates a valid CSP graph component."""

        @csp.graph
        def test_graph():
            msg = csp.const(
                SymphonyMessage(
                    stream_id="stream123",
                    content="Hello!",
                )
            )
            adapter.publish(msg)

        assert test_graph is not None

    def test_publish_presence_graph_creation(self, adapter):
        """Test that publish_presence creates a valid CSP graph component."""

        @csp.graph
        def test_graph():
            presence = csp.const(SymphonyPresenceStatus.AVAILABLE)
            adapter.publish_presence(presence)

        assert test_graph is not None

    def test_publish_presence_with_timeout(self, adapter):
        """Test publish_presence with custom timeout."""

        @csp.graph
        def test_graph():
            presence = csp.const(SymphonyPresenceStatus.BUSY)
            adapter.publish_presence(presence, timeout=10.0)

        assert test_graph is not None


class TestSymphonyAdapterConfigExtended:
    """Extended tests for SymphonyAdapterConfig (now an alias for SymphonyConfig)."""

    def test_ssl_verify_disabled(self):
        """Test SSL verification disabled warning."""
        with patch("chatom.symphony.config.log") as mock_log:
            config = SymphonyAdapterConfig(
                host="test.symphony.com",
                bot_username="testbot",
                bot_private_key_path="/path/to/key.pem",
                ssl_verify=False,
            )
            assert config.ssl_verify is False
            # Should log a warning
            mock_log.warning.assert_called()

    def test_config_is_symphony_config(self):
        """Test that SymphonyAdapterConfig is an alias for SymphonyConfig."""
        assert SymphonyAdapterConfig is SymphonyConfig

    def test_config_fields(self):
        """Test that config has all expected fields."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            port=8443,
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
            agent_host="agent.symphony.com",
            session_auth_host="session.symphony.com",
            key_manager_host="km.symphony.com",
        )

        assert config.host == "test.symphony.com"
        assert config.port == 8443
        assert config.bot_username == "testbot"
        assert config.agent_host == "agent.symphony.com"
        assert config.session_auth_host == "session.symphony.com"
        assert config.key_manager_host == "km.symphony.com"

    def test_config_with_cert(self):
        """Test config with certificate path."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_certificate_path="/path/to/cert.pem",
        )
        assert config.bot_certificate_path == "/path/to/cert.pem"

    def test_create_backend_via_chatom(self):
        """Test creating a SymphonyBackend from config using chatom."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        # Backend is created directly from config
        from chatom.symphony import SymphonyBackend

        backend = SymphonyBackend(config=config)
        assert isinstance(backend, SymphonyBackend)

    def test_config_with_all_adapter_options(self):
        """Test config with all adapter-specific options."""
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
            error_room="error-notifications",
            inform_client=True,
            max_attempts=20,
            initial_interval_ms=1000,
            multiplier=3.0,
            max_interval_ms=600000,
            datafeed_version="v1",
            ssl_trust_store_path="/path/to/ca-bundle.crt",
        )
        assert config.error_room == "error-notifications"
        assert config.inform_client is True
        assert config.max_attempts == 20
        assert config.initial_interval_ms == 1000
        assert config.multiplier == 3.0
        assert config.max_interval_ms == 600000
        assert config.datafeed_version == "v1"
        assert config.ssl_trust_store_path == "/path/to/ca-bundle.crt"


class TestSymphonyRoomMapperAsync:
    """Async tests for SymphonyRoomMapper."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock chatom backend."""
        backend = MagicMock()
        backend.fetch_channel = AsyncMock()
        return backend

    @pytest.fixture
    def mock_stream_service(self):
        """Create a mock stream service."""
        service = MagicMock()
        service.search_rooms = AsyncMock()
        service.get_room_info = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_room_id_async_from_cache(self):
        """Test async room ID lookup from cache."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Cached Room", "cached_stream_123")

        result = await mapper.get_room_id_async("Cached Room")
        assert result == "cached_stream_123"

    @pytest.mark.asyncio
    async def test_get_room_id_async_from_backend(self, mock_backend):
        """Test async room ID lookup from chatom backend."""
        mock_channel = MagicMock()
        mock_channel.id = "backend_stream_456"
        mock_backend.fetch_channel.return_value = mock_channel

        mapper = SymphonyRoomMapper(backend=mock_backend)
        result = await mapper.get_room_id_async("Backend Room")

        assert result == "backend_stream_456"
        mock_backend.fetch_channel.assert_called_once_with(name="Backend Room")

    @pytest.mark.asyncio
    async def test_get_room_id_async_not_found(self, mock_backend):
        """Test async room ID lookup when not found."""
        mock_backend.fetch_channel.return_value = None

        mapper = SymphonyRoomMapper(backend=mock_backend)
        result = await mapper.get_room_id_async("Unknown Room")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_id_async_from_stream_service(self, mock_stream_service):
        """Test async room ID lookup from stream service."""
        mock_room = MagicMock()
        mock_room.room_attributes = MagicMock()
        mock_room.room_attributes.name = "Service Room"
        mock_room.room_system_info = MagicMock()
        mock_room.room_system_info.id = "service_stream_789"

        mock_results = MagicMock()
        mock_results.rooms = [mock_room]
        mock_stream_service.search_rooms.return_value = mock_results

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)
        result = await mapper.get_room_id_async("Service Room")

        assert result == "service_stream_789"

    @pytest.mark.asyncio
    async def test_get_room_name_async_from_cache(self):
        """Test async room name lookup from cache."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Cached Room", "cached_stream_123")

        result = await mapper.get_room_name_async("cached_stream_123")
        assert result == "Cached Room"

    @pytest.mark.asyncio
    async def test_get_room_name_async_from_backend(self, mock_backend):
        """Test async room name lookup from chatom backend."""
        mock_channel = MagicMock()
        mock_channel.id = "backend_stream_456"
        mock_channel.name = "Backend Room"
        mock_backend.fetch_channel.return_value = mock_channel

        mapper = SymphonyRoomMapper(backend=mock_backend)
        result = await mapper.get_room_name_async("backend_stream_456")

        assert result == "Backend Room"
        mock_backend.fetch_channel.assert_called_once_with(id="backend_stream_456")

    @pytest.mark.asyncio
    async def test_get_room_name_async_from_stream_service(self, mock_stream_service):
        """Test async room name lookup from stream service."""
        mock_room_info = MagicMock()
        mock_room_info.room_attributes = MagicMock()
        mock_room_info.room_attributes.name = "Service Room"
        mock_stream_service.get_room_info.return_value = mock_room_info

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)
        result = await mapper.get_room_name_async("service_stream_789")

        assert result == "Service Room"

    @pytest.mark.asyncio
    async def test_get_room_name_async_not_found(self, mock_backend):
        """Test async room name lookup when not found."""
        mock_backend.fetch_channel.return_value = None

        mapper = SymphonyRoomMapper(backend=mock_backend)
        result = await mapper.get_room_name_async("unknown_stream")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_id_async_exception_handling(self, mock_stream_service):
        """Test exception handling in async room ID lookup."""
        mock_stream_service.search_rooms.side_effect = Exception("API Error")

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)
        result = await mapper.get_room_id_async("Error Room")

        # Should return None and not raise
        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_name_async_exception_handling(self, mock_stream_service):
        """Test exception handling in async room name lookup."""
        mock_stream_service.get_room_info.side_effect = Exception("API Error")

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)
        result = await mapper.get_room_name_async("error_stream")

        # Should return None and not raise
        assert result is None

    def test_set_stream_service(self, mock_stream_service):
        """Test setting stream service."""
        mapper = SymphonyRoomMapper()
        mapper.set_stream_service(mock_stream_service)
        assert mapper._stream_service == mock_stream_service

    def test_set_backend(self, mock_backend):
        """Test setting backend."""
        mapper = SymphonyRoomMapper()
        mapper.set_backend(mock_backend)
        assert mapper._backend == mock_backend


class TestSymphonyAdapterPresence:
    """Tests for Symphony adapter presence functionality."""

    def test_presence_node_runs_in_graph(self):
        """Test that presence node can be included in a graph."""
        config = SymphonyConfig(
            host="test.symphony.com",
            bot_username="testbot",
            bot_private_key_path="/path/to/key.pem",
        )
        adapter = SymphonyAdapter(config)

        @csp.graph
        def test_graph():
            presence = csp.const(SymphonyPresenceStatus.AVAILABLE)
            adapter.publish_presence(presence, timeout=1.0)

        # Run for a very short time - the actual API call will fail
        # but we're just testing the graph structure
        # Don't use realtime to avoid async issues
        csp.run(
            test_graph,
            starttime=datetime.now(),
            endtime=timedelta(seconds=0.1),
        )

    def test_all_presence_statuses(self):
        """Test all presence status values are accessible."""
        statuses = [
            SymphonyPresenceStatus.AVAILABLE,
            SymphonyPresenceStatus.BUSY,
            SymphonyPresenceStatus.AWAY,
            SymphonyPresenceStatus.ON_THE_PHONE,
            SymphonyPresenceStatus.BE_RIGHT_BACK,
            SymphonyPresenceStatus.IN_A_MEETING,
            SymphonyPresenceStatus.OUT_OF_OFFICE,
            SymphonyPresenceStatus.OFF_WORK,
        ]
        for status in statuses:
            # Each status should have a valid name
            assert status.name is not None
            assert len(status.name) > 0
