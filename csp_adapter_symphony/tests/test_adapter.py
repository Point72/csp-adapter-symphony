"""Tests for the Symphony adapter using symphony-bdk-python."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from csp_adapter_symphony import (
    SymphonyAdapterConfig,
    SymphonyMessage,
    SymphonyRoomMapper,
    extract_mentions_from_text,
    format_with_message_ml,
    is_bot_mentioned,
    mention_by_email,
    mention_by_id,
    mention_user,
    mention_users,
)
from csp_adapter_symphony.adapter import (
    _check_bdk_available,
    _get_user_mentions,
    _handle_elements_action,
    _handle_message_sent,
)
from csp_adapter_symphony.mention import format_at_mention


class TestMentionFunctions:
    """Tests for mention utility functions."""

    def test_mention_user_with_email(self):
        """Test mention_user with email address."""
        result = mention_user("user@example.com")
        assert result == '<mention email="user@example.com" />'

    def test_mention_user_with_id(self):
        """Test mention_user with user ID."""
        result = mention_user("12345")
        assert result == '<mention uid="12345" />'

    def test_mention_user_with_numeric_id(self):
        """Test mention_user with numeric user ID."""
        result = mention_user(12345)
        assert result == '<mention uid="12345" />'

    def test_mention_user_empty(self):
        """Test mention_user with empty string."""
        result = mention_user("")
        assert result == ""

    def test_mention_user_none(self):
        """Test mention_user with None-like input."""
        result = mention_user()
        assert result == ""

    def test_mention_by_email(self):
        """Test mention_by_email function."""
        result = mention_by_email("user@example.com")
        assert result == '<mention email="user@example.com" />'

    def test_mention_by_email_empty(self):
        """Test mention_by_email with empty string."""
        result = mention_by_email("")
        assert result == ""

    def test_mention_by_id(self):
        """Test mention_by_id function."""
        result = mention_by_id("12345")
        assert result == '<mention uid="12345" />'

    def test_mention_by_id_int(self):
        """Test mention_by_id with integer."""
        result = mention_by_id(12345)
        assert result == '<mention uid="12345" />'

    def test_mention_by_id_empty(self):
        """Test mention_by_id with empty string."""
        result = mention_by_id("")
        assert result == ""

    def test_mention_users(self):
        """Test mention_users with multiple identifiers."""
        result = mention_users(["12345", "user@example.com"])
        assert result == '<mention uid="12345" /> <mention email="user@example.com" />'

    def test_mention_users_custom_separator(self):
        """Test mention_users with custom separator."""
        result = mention_users(["12345", "67890"], separator=", ")
        assert result == '<mention uid="12345" />, <mention uid="67890" />'

    def test_mention_users_empty_list(self):
        """Test mention_users with empty list."""
        result = mention_users([])
        assert result == ""

    def test_mention_users_with_empty_items(self):
        """Test mention_users filters out empty items."""
        result = mention_users(["12345", "", "67890"])
        assert result == '<mention uid="12345" /> <mention uid="67890" />'

    def test_extract_mentions_from_text(self):
        """Test extracting mentions from MessageML text."""
        text = 'Hello <mention uid="12345" /> and <mention uid="67890" />'
        result = extract_mentions_from_text(text)
        assert result == ["12345", "67890"]

    def test_extract_mentions_empty_text(self):
        """Test extracting mentions from text without mentions."""
        text = "Hello world"
        result = extract_mentions_from_text(text)
        assert result == []

    def test_is_bot_mentioned(self):
        """Test is_bot_mentioned function."""
        text = '<mention uid="12345" /> hello'
        assert is_bot_mentioned(text, "12345") is True
        assert is_bot_mentioned(text, "99999") is False

    def test_format_at_mention(self):
        """Test format_at_mention function."""
        result = format_at_mention("John Doe", "12345")
        # format_at_mention returns a standard mention tag
        assert result == '<mention uid="12345" />'


class TestFormatWithMessageML:
    """Tests for MessageML formatting."""

    def test_to_message_ml(self):
        """Test converting to MessageML format."""
        input_text = "This & that < ${variable} #{hashtag}"
        expected_output = "This &#38; that &lt; &#36;{variable} &#35;{hashtag}"
        assert format_with_message_ml(input_text) == expected_output

    def test_from_message_ml(self):
        """Test converting from MessageML format."""
        input_text = "This &#38; that &lt; &#36;{variable} &#35;{hashtag}"
        expected_output = "This & that < ${variable} #{hashtag}"
        assert format_with_message_ml(input_text, to_message_ml=False) == expected_output

    def test_no_changes(self):
        """Test text without special characters."""
        input_text = "Regular text without special characters"
        assert format_with_message_ml(input_text) == input_text
        assert format_with_message_ml(input_text, to_message_ml=False) == input_text

    def test_greater_than_escape(self):
        """Test escaping greater than sign."""
        input_text = "a > b"
        expected_output = "a &gt; b"
        assert format_with_message_ml(input_text) == expected_output


class TestSymphonyMessage:
    """Tests for SymphonyMessage struct and methods."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = SymphonyMessage(
            user="John Doe",
            user_email="john@example.com",
            user_id="12345",
            room="Test Room",
            msg="Hello, World!",
        )
        assert msg.user == "John Doe"
        assert msg.user_email == "john@example.com"
        assert msg.user_id == "12345"
        assert msg.room == "Test Room"
        assert msg.msg == "Hello, World!"

    def test_message_defaults(self):
        """Test message default values."""
        msg = SymphonyMessage()
        assert msg.user == ""
        assert msg.user_email == ""
        assert msg.user_id == ""
        assert msg.tags == []
        assert msg.room == ""
        assert msg.msg == ""
        assert msg.form_id == ""
        assert msg.form_values == {}
        assert msg.stream_id == ""

    def test_mention(self):
        """Test mention method."""
        msg = SymphonyMessage(user_id="12345", user_email="user@example.com")
        assert msg.mention() == '<mention uid="12345" />'
        assert msg.mention(use_email=True) == '<mention email="user@example.com" />'

    def test_mention_no_user_id(self):
        """Test mention method without user_id."""
        msg = SymphonyMessage()
        assert msg.mention() == ""

    def test_reply(self):
        """Test reply method."""
        msg = SymphonyMessage(room="Test Room", user_id="12345", stream_id="abc123")
        reply = msg.reply("Thanks!")
        assert reply.room == "Test Room"
        assert reply.msg == "Thanks!"
        assert reply.stream_id == "abc123"

    def test_reply_with_mention(self):
        """Test reply method with author mention."""
        msg = SymphonyMessage(room="Test Room", user_id="12345")
        reply = msg.reply("Thanks!", mention_author=True)
        assert '<mention uid="12345" />' in reply.msg
        assert "Thanks!" in reply.msg

    def test_direct_reply(self):
        """Test direct_reply method."""
        msg = SymphonyMessage(user="John", user_id="12345")
        dm = msg.direct_reply("Private message")
        assert dm.room == "IM"
        assert dm.user_id == "12345"
        assert dm.user == "John"
        assert dm.msg == "Private message"

    def test_is_direct_message(self):
        """Test is_direct_message method."""
        im_msg = SymphonyMessage(room="IM")
        room_msg = SymphonyMessage(room="Test Room")
        assert im_msg.is_direct_message() is True
        assert room_msg.is_direct_message() is False

    def test_mentions_user(self):
        """Test mentions_user method."""
        msg = SymphonyMessage(tags=["12345", "67890"])
        assert msg.mentions_user("12345") is True
        assert msg.mentions_user("99999") is False

    def test_get_mentioned_users(self):
        """Test get_mentioned_users method."""
        msg = SymphonyMessage(tags=["12345", "67890"])
        assert msg.get_mentioned_users() == ["12345", "67890"]

    def test_is_form_submission(self):
        """Test is_form_submission method."""
        form_msg = SymphonyMessage(form_id="test_form")
        regular_msg = SymphonyMessage()
        assert form_msg.is_form_submission() is True
        assert regular_msg.is_form_submission() is False

    def test_get_form_value(self):
        """Test get_form_value method."""
        msg = SymphonyMessage(form_values={"name": "John", "age": "30"})
        assert msg.get_form_value("name") == "John"
        assert msg.get_form_value("missing", "default") == "default"
        assert msg.get_form_value("missing") is None

    def test_with_message(self):
        """Test with_message method."""
        msg = SymphonyMessage(room="Test Room", user_id="12345")
        new_msg = msg.with_message("New content")
        assert new_msg.msg == "New content"
        assert new_msg.room == "Test Room"
        assert new_msg.user_id == "12345"

    def test_to_room_classmethod(self):
        """Test to_room class method."""
        msg = SymphonyMessage.to_room("Test Room", "Hello!")
        assert msg.room == "Test Room"
        assert msg.msg == "Hello!"

    def test_to_user_classmethod(self):
        """Test to_user class method."""
        msg = SymphonyMessage.to_user("12345", "Hello!")
        assert msg.room == "IM"
        assert msg.user_id == "12345"
        assert msg.msg == "Hello!"

    def test_to_stream_classmethod(self):
        """Test to_stream class method."""
        msg = SymphonyMessage.to_stream("abc123", "Hello!")
        assert msg.stream_id == "abc123"
        assert msg.msg == "Hello!"


class TestGetUserMentions:
    """Tests for _get_user_mentions function."""

    def test_get_user_mentions_valid(self):
        """Test extracting user mentions from valid data."""
        data = '{"key": {"type": "com.symphony.user.mention", "id": [{"value": "12345"}]}}'
        result = _get_user_mentions(data)
        assert result == ["12345"]

    def test_get_user_mentions_multiple(self):
        """Test extracting multiple user mentions."""
        data = '{"key1": {"type": "com.symphony.user.mention", "id": [{"value": "12345"}]}, "key2": {"type": "com.symphony.user.mention", "id": [{"value": "67890"}]}}'
        result = _get_user_mentions(data)
        assert "12345" in result
        assert "67890" in result

    def test_get_user_mentions_empty(self):
        """Test extracting mentions from empty data."""
        result = _get_user_mentions("")
        assert result == []

    def test_get_user_mentions_invalid_json(self):
        """Test extracting mentions from invalid JSON."""
        result = _get_user_mentions("not valid json")
        assert result == []

    def test_get_user_mentions_no_mentions(self):
        """Test extracting mentions when none exist."""
        data = '{"key": {"type": "other.type", "value": "something"}}'
        result = _get_user_mentions(data)
        assert result == []


class TestHandleMessageSent:
    """Tests for _handle_message_sent function."""

    def test_handle_message_sent_basic(self):
        """Test handling a basic message sent event."""
        # Create mock objects
        initiator = MagicMock()
        initiator.user.display_name = "John Doe"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "ROOM"
        event.message.message = "Hello, World!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "stream123")

        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is not None
        assert result.user == "John Doe"
        assert result.user_email == "john@example.com"
        assert result.user_id == "12345"
        assert result.msg == "Hello, World!"
        assert result.stream_id == "stream123"

    def test_handle_message_sent_im(self):
        """Test handling an IM message."""
        initiator = MagicMock()
        initiator.user.display_name = "John Doe"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "im123"
        event.message.stream.stream_type = "IM"
        event.message.message = "Hello!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is not None
        assert result.room == "IM"
        # Check that IM was registered
        assert room_mapper.get_room_id("John Doe") == "im123"

    def test_handle_message_sent_filtered(self):
        """Test that messages from non-matching rooms are filtered."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "ROOM"
        event.message.message = "Hello!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, {"other_stream"}, room_mapper)

        assert result is None

    def test_handle_message_sent_no_message(self):
        """Test handling event with no message."""
        initiator = MagicMock()
        event = MagicMock()
        event.message = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is None


class TestHandleElementsAction:
    """Tests for _handle_elements_action function."""

    def test_handle_elements_action_basic(self):
        """Test handling a basic elements action event."""
        initiator = MagicMock()
        initiator.user.display_name = "John Doe"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.stream.stream_id = "stream123"
        event.stream.stream_type = "ROOM"
        event.form_id = "test_form"
        event.form_values = {"field1": "value1"}

        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "stream123")

        result = _handle_elements_action(initiator, event, set(), room_mapper)

        assert result is not None
        assert result.user == "John Doe"
        assert result.form_id == "test_form"
        assert result.form_values == {"field1": "value1"}

    def test_handle_elements_action_no_stream(self):
        """Test handling event with no stream."""
        initiator = MagicMock()
        event = MagicMock()
        event.stream = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_elements_action(initiator, event, set(), room_mapper)

        assert result is None


class TestSymphonyRoomMapper:
    """Tests for SymphonyRoomMapper class."""

    def test_register_and_get_room(self):
        """Test registering and retrieving a room."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Test Room", "room123")

        assert mapper.get_room_id("Test Room") == "room123"
        assert mapper.get_room_name("room123") == "Test Room"

    def test_get_room_id_not_found(self):
        """Test getting room ID that doesn't exist."""
        mapper = SymphonyRoomMapper()
        assert mapper.get_room_id("Unknown Room") is None

    def test_get_room_id_looks_like_stream_id(self):
        """Test that stream-ID-like strings are returned as-is."""
        mapper = SymphonyRoomMapper()
        stream_id = "abc123def456ghi789jkl012"  # 24 chars, no spaces
        assert mapper.get_room_id(stream_id) == stream_id

    def test_set_im_id(self):
        """Test setting IM stream ID."""
        mapper = SymphonyRoomMapper()
        mapper.set_im_id("john_doe", "im123")

        assert mapper.get_room_id("john_doe") == "im123"
        assert mapper.get_room_name("im123") == "john_doe"


class TestSymphonyAdapterConfig:
    """Tests for SymphonyAdapterConfig class."""

    def test_config_from_bdk_config(self):
        """Test creating config from BdkConfig object."""
        from symphony.bdk.core.config.model.bdk_config import BdkConfig

        # Create a minimal BdkConfig
        bdk_config = BdkConfig(host="test.symphony.com")
        config = SymphonyAdapterConfig(bdk_config=bdk_config)
        assert config.bdk_config == bdk_config

    def test_config_from_file_path(self):
        """Test creating config from file path."""
        with patch("csp_adapter_symphony.adapter_config.BdkConfigLoader") as mock_loader:
            from symphony.bdk.core.config.model.bdk_config import BdkConfig

            mock_bdk_config = BdkConfig(host="test.symphony.com")
            mock_loader.load_from_file.return_value = mock_bdk_config

            config = SymphonyAdapterConfig(bdk_config_path="/path/to/config.yaml")

            mock_loader.load_from_file.assert_called_once_with("/path/to/config.yaml")
            assert config.bdk_config == mock_bdk_config

    def test_config_from_individual_params(self):
        """Test creating config from individual parameters."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
        )

        assert config.bdk_config is not None
        assert config.host == "company.symphony.com"
        assert config.bot_username == "mybot"

    def test_config_missing_required_params(self):
        """Test that missing required params raises error."""
        with pytest.raises(ValueError, match="Either bdk_config"):
            SymphonyAdapterConfig()

    def test_from_file_classmethod(self):
        """Test from_file class method."""
        with patch("csp_adapter_symphony.adapter_config.BdkConfigLoader") as mock_loader:
            from symphony.bdk.core.config.model.bdk_config import BdkConfig

            mock_bdk_config = BdkConfig(host="test.symphony.com")
            mock_loader.load_from_file.return_value = mock_bdk_config

            config = SymphonyAdapterConfig.from_file("/path/to/config.yaml", error_room="errors")

            assert config.bdk_config == mock_bdk_config
            assert config.error_room == "errors"

    def test_from_bdk_config_classmethod(self):
        """Test from_bdk_config class method."""
        from symphony.bdk.core.config.model.bdk_config import BdkConfig

        bdk_config = BdkConfig(host="test.symphony.com")
        config = SymphonyAdapterConfig.from_bdk_config(bdk_config, inform_client=True)

        assert config.bdk_config == bdk_config
        assert config.inform_client is True

    def test_config_with_separate_hosts(self):
        """Test config with separate endpoint hosts."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            pod_host="pod.symphony.com",
            agent_host="agent.symphony.com",
            session_auth_host="auth.symphony.com",
            key_manager_host="km.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
        )

        assert config.bdk_config is not None
        assert config.pod_host == "pod.symphony.com"
        assert config.agent_host == "agent.symphony.com"
        assert config.session_auth_host == "auth.symphony.com"
        assert config.key_manager_host == "km.symphony.com"

    def test_config_with_certificate(self):
        """Test config with certificate-based authentication."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            certificate_path="/path/to/cert.pem",
        )

        assert config.bdk_config is not None
        assert config.certificate_path == "/path/to/cert.pem"

    def test_config_with_certificate_content(self):
        """Test config with certificate content - not supported by BDK, should fail gracefully."""
        # Note: BdkCertificateConfig only supports 'path', not 'content'
        # This tests that we attempt to configure it but the BDK rejects it
        with pytest.raises(TypeError):
            SymphonyAdapterConfig(
                host="company.symphony.com",
                bot_username="mybot",
                certificate_content="-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
            )

    def test_config_with_private_key_content(self):
        """Test config with private key content."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_content="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        )

        assert config.bdk_config is not None
        assert config.private_key_content is not None

    def test_config_with_ssl_trust_store(self):
        """Test config with SSL trust store path."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
            ssl_trust_store_path="/path/to/ca-bundle.pem",
        )

        assert config.bdk_config is not None
        assert config.ssl_trust_store_path == "/path/to/ca-bundle.pem"

    def test_config_with_ssl_verify_false(self):
        """Test config with SSL verification disabled."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
            ssl_verify=False,
        )

        assert config.bdk_config is not None
        assert config.ssl_verify is False

    def test_from_symphony_dir_classmethod(self):
        """Test from_symphony_dir class method."""
        with patch("csp_adapter_symphony.adapter_config.BdkConfigLoader") as mock_loader:
            from symphony.bdk.core.config.model.bdk_config import BdkConfig

            mock_bdk_config = BdkConfig(host="test.symphony.com")
            mock_loader.load_from_file.return_value = mock_bdk_config

            _ = SymphonyAdapterConfig.from_symphony_dir("config.yaml")

            # Should call load_from_file with path in ~/.symphony
            call_args = mock_loader.load_from_file.call_args[0][0]
            assert ".symphony" in call_args
            assert "config.yaml" in call_args

    def test_config_with_custom_retry_settings(self):
        """Test config with custom retry settings."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
            max_attempts=20,
            initial_interval_ms=1000,
            multiplier=3.0,
            max_interval_ms=600000,
        )

        assert config.max_attempts == 20
        assert config.initial_interval_ms == 1000
        assert config.multiplier == 3.0
        assert config.max_interval_ms == 600000

    def test_config_with_datafeed_v1(self):
        """Test config with datafeed v1."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
            datafeed_version="v1",
        )

        assert config.datafeed_version == "v1"

    def test_config_with_error_room_and_inform_client(self):
        """Test config with error handling options."""
        config = SymphonyAdapterConfig(
            host="company.symphony.com",
            bot_username="mybot",
            private_key_path="/path/to/key.pem",
            error_room="Error Notifications",
            inform_client=True,
        )

        assert config.error_room == "Error Notifications"
        assert config.inform_client is True


class TestSymphonyRoomMapperAsync:
    """Tests for SymphonyRoomMapper async methods."""

    @pytest.mark.asyncio
    async def test_get_room_id_async_cached(self):
        """Test get_room_id_async returns cached value."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Test Room", "room123")

        result = await mapper.get_room_id_async("Test Room")
        assert result == "room123"

    @pytest.mark.asyncio
    async def test_get_room_id_async_looks_like_stream_id(self):
        """Test get_room_id_async returns stream-ID-like strings as-is."""
        mapper = SymphonyRoomMapper()
        stream_id = "abc123def456ghi789jkl012"

        result = await mapper.get_room_id_async(stream_id)
        assert result == stream_id

    @pytest.mark.asyncio
    async def test_get_room_id_async_no_stream_service(self):
        """Test get_room_id_async returns None when no stream service."""
        mapper = SymphonyRoomMapper()

        result = await mapper.get_room_id_async("Unknown Room")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_id_async_from_service(self):
        """Test get_room_id_async resolves room from service."""
        mock_stream_service = AsyncMock()
        mock_room = MagicMock()
        mock_room.room_attributes.name = "Test Room"
        mock_room.room_system_info.id = "room123"
        mock_stream_service.search_rooms.return_value = MagicMock(rooms=[mock_room])

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)

        result = await mapper.get_room_id_async("Test Room")
        assert result == "room123"
        # Verify it was cached
        assert mapper.get_room_id("Test Room") == "room123"

    @pytest.mark.asyncio
    async def test_get_room_id_async_service_error(self):
        """Test get_room_id_async handles service errors."""
        mock_stream_service = AsyncMock()
        mock_stream_service.search_rooms.side_effect = Exception("API error")

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)

        result = await mapper.get_room_id_async("Test Room")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_name_async_cached(self):
        """Test get_room_name_async returns cached value."""
        mapper = SymphonyRoomMapper()
        mapper.register_room("Test Room", "room123")

        result = await mapper.get_room_name_async("room123")
        assert result == "Test Room"

    @pytest.mark.asyncio
    async def test_get_room_name_async_no_stream_service(self):
        """Test get_room_name_async returns None when no stream service."""
        mapper = SymphonyRoomMapper()

        result = await mapper.get_room_name_async("room123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_name_async_from_service(self):
        """Test get_room_name_async resolves room name from service."""
        mock_stream_service = AsyncMock()
        mock_room_info = MagicMock()
        mock_room_info.room_attributes.name = "Test Room"
        mock_stream_service.get_room_info.return_value = mock_room_info

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)

        result = await mapper.get_room_name_async("room123")
        assert result == "Test Room"
        # Verify it was cached
        assert mapper.get_room_name("room123") == "Test Room"

    @pytest.mark.asyncio
    async def test_get_room_name_async_service_error(self):
        """Test get_room_name_async handles service errors."""
        mock_stream_service = AsyncMock()
        mock_stream_service.get_room_info.side_effect = Exception("API error")

        mapper = SymphonyRoomMapper(stream_service=mock_stream_service)

        result = await mapper.get_room_name_async("room123")
        assert result is None

    def test_set_stream_service(self):
        """Test setting stream service."""
        mapper = SymphonyRoomMapper()
        mock_service = MagicMock()
        mapper.set_stream_service(mock_service)
        assert mapper._stream_service == mock_service


class TestHandleMessageSentEdgeCases:
    """Additional tests for _handle_message_sent edge cases."""

    def test_handle_message_sent_no_stream(self):
        """Test handling event with no stream."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream = None
        event.message.message = "Hello!"

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is None

    def test_handle_message_sent_no_initiator(self):
        """Test handling event with None initiator."""
        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "ROOM"
        event.message.message = "Hello!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(None, event, set(), room_mapper)

        assert result is not None
        assert result.user == "USER_ERROR"

    def test_handle_message_sent_with_mentions(self):
        """Test handling message with user mentions in data."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "ROOM"
        event.message.message = "Hello @user!"
        event.message.data = '{"0": {"type": "com.symphony.user.mention", "id": [{"value": "67890"}]}}'

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is not None
        assert "67890" in result.tags

    def test_handle_message_sent_unknown_stream_type(self):
        """Test handling message with unknown stream type."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "UNKNOWN"
        event.message.message = "Hello!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, set(), room_mapper)

        assert result is not None
        # Unknown stream type should use stream_id as room name
        assert result.room == "stream123"

    def test_handle_message_sent_matching_room_filter(self):
        """Test that messages matching room filter are accepted."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.message.stream.stream_id = "stream123"
        event.message.stream.stream_type = "ROOM"
        event.message.message = "Hello!"
        event.message.data = None

        room_mapper = SymphonyRoomMapper()
        result = _handle_message_sent(initiator, event, {"stream123"}, room_mapper)

        assert result is not None
        assert result.stream_id == "stream123"


class TestHandleElementsActionEdgeCases:
    """Additional tests for _handle_elements_action edge cases."""

    def test_handle_elements_action_filtered(self):
        """Test that form submissions from non-matching rooms are filtered."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.stream.stream_id = "stream123"
        event.stream.stream_type = "ROOM"
        event.form_id = "test_form"
        event.form_values = {"field1": "value1"}

        room_mapper = SymphonyRoomMapper()
        result = _handle_elements_action(initiator, event, {"other_stream"}, room_mapper)

        assert result is None

    def test_handle_elements_action_im(self):
        """Test handling form submission in IM."""
        initiator = MagicMock()
        initiator.user.display_name = "John"
        initiator.user.email = "john@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.stream.stream_id = "im123"
        event.stream.stream_type = "IM"
        event.form_id = "test_form"
        event.form_values = {"field1": "value1"}

        room_mapper = SymphonyRoomMapper()
        result = _handle_elements_action(initiator, event, set(), room_mapper)

        assert result is not None
        assert result.room == "IM"
        assert result.form_id == "test_form"


class TestCheckBdkAvailable:
    """Tests for _check_bdk_available function."""

    def test_check_bdk_available_when_available(self):
        """Test _check_bdk_available doesn't raise when BDK is available."""
        # Should not raise since BDK is installed in test environment
        _check_bdk_available()

    def test_check_bdk_available_when_not_available(self):
        """Test _check_bdk_available raises when BDK is not available."""
        with patch("csp_adapter_symphony.adapter._BDK_AVAILABLE", False):
            with pytest.raises(ImportError, match="symphony-bdk-python is required"):
                _check_bdk_available()


class TestSendSymphonyMessageAsync:
    """Tests for send_symphony_message_async function."""

    @pytest.mark.asyncio
    async def test_send_message_with_stream_id(self, mock_bdk):
        """Test sending a message using stream_id directly."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            stream_id="stream123",
            msg="Hello, World!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is True
        mock_bdk.messages().send_message.assert_called_once()
        call_args = mock_bdk.messages().send_message.call_args
        assert call_args[0][0] == "stream123"

    @pytest.mark.asyncio
    async def test_send_message_with_messageml_wrapper(self, mock_bdk):
        """Test that messages get wrapped in messageML if needed."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            stream_id="stream123",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        call_args = mock_bdk.messages().send_message.call_args
        assert "<messageML>" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_send_message_already_has_messageml(self, mock_bdk):
        """Test that messages with messageML are not double-wrapped."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            stream_id="stream123",
            msg="<messageML>Hello!</messageML>",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        call_args = mock_bdk.messages().send_message.call_args
        # Should not have double messageML tags
        assert call_args[0][1].count("<messageML>") == 1

    @pytest.mark.asyncio
    async def test_send_im_creates_stream(self, mock_bdk):
        """Test sending an IM creates the stream."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            room="IM",
            user_id="12345",
            msg="Hello via DM!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is True
        mock_bdk.streams().create_im.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_send_im_uses_cached_stream(self, mock_bdk):
        """Test sending an IM uses cached stream if available."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            room="IM",
            user="John Doe",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()
        room_mapper.set_im_id("John Doe", "cached_im_stream")

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is True
        # Should use cached stream, not create new one
        mock_bdk.streams().create_im.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_room_by_name(self, mock_bdk):
        """Test sending to a room by name."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            room="Test Room",
            msg="Hello room!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "test_room_stream")

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is True
        call_args = mock_bdk.messages().send_message.call_args
        assert call_args[0][0] == "test_room_stream"

    @pytest.mark.asyncio
    async def test_send_fails_no_stream_id(self, mock_bdk):
        """Test sending fails when stream ID cannot be found."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            room="Unknown Room",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_notifies_error_room(self, mock_bdk):
        """Test that errors are sent to error room if configured."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        msg = SymphonyMessage(
            room="Unknown Room",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
            error_room="Error Notifications",
        )
        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Error Notifications", "error_stream")

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is False
        # Should have sent to error room
        assert mock_bdk.messages().send_message.called

    @pytest.mark.asyncio
    async def test_send_handles_exception(self, mock_bdk):
        """Test that exceptions are handled gracefully."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        mock_bdk.messages().send_message.side_effect = Exception("API Error")

        msg = SymphonyMessage(
            stream_id="stream123",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_informs_client_on_error(self, mock_bdk):
        """Test that client is informed of errors if configured."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        # First call fails, second succeeds (for error notification)
        mock_bdk.messages().send_message.side_effect = [Exception("API Error"), MagicMock()]

        msg = SymphonyMessage(
            room="Test Room",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
            inform_client=True,
        )
        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "test_stream")

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_im_error_creating_stream(self, mock_bdk):
        """Test handling error when creating IM stream."""
        from csp_adapter_symphony.adapter import send_symphony_message_async

        mock_bdk.streams().create_im.side_effect = Exception("Cannot create IM")

        msg = SymphonyMessage(
            room="IM",
            user_id="12345",
            msg="Hello!",
        )
        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()

        result = await send_symphony_message_async(mock_bdk, msg, room_mapper, config)

        # Should fail because stream couldn't be created
        assert result is False


class TestSetPresenceSync:
    """Tests for _set_presence_sync function."""

    def test_set_presence_available(self):
        """Test setting presence to available."""
        from csp_adapter_symphony.adapter import Presence, _set_presence_sync

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        with patch("csp_adapter_symphony.adapter.SymphonyBdk") as mock_bdk_class:
            mock_bdk = MagicMock()
            mock_bdk.__aenter__ = AsyncMock(return_value=mock_bdk)
            mock_bdk.__aexit__ = AsyncMock(return_value=None)
            mock_bdk.presence.return_value.set_presence = AsyncMock()
            mock_bdk_class.return_value = mock_bdk

            _set_presence_sync(config, Presence.AVAILABLE, timeout=1.0)

            mock_bdk.presence.return_value.set_presence.assert_called_once()

    def test_set_presence_busy(self):
        """Test setting presence to busy."""
        from csp_adapter_symphony.adapter import Presence, _set_presence_sync

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        with patch("csp_adapter_symphony.adapter.SymphonyBdk") as mock_bdk_class:
            mock_bdk = MagicMock()
            mock_bdk.__aenter__ = AsyncMock(return_value=mock_bdk)
            mock_bdk.__aexit__ = AsyncMock(return_value=None)
            mock_bdk.presence.return_value.set_presence = AsyncMock()
            mock_bdk_class.return_value = mock_bdk

            _set_presence_sync(config, Presence.BUSY, timeout=1.0)

            mock_bdk.presence.return_value.set_presence.assert_called_once()

    def test_set_presence_no_config(self):
        """Test setting presence with no BDK config."""
        from symphony.bdk.core.config.model.bdk_config import BdkConfig

        from csp_adapter_symphony.adapter import Presence, _set_presence_sync

        config = SymphonyAdapterConfig(bdk_config=BdkConfig(host="test.symphony.com"))
        # Manually clear the config to simulate missing config
        config.bdk_config = None

        # Should not raise, just log error
        _set_presence_sync(config, Presence.AVAILABLE, timeout=0.1)

    def test_set_presence_timeout(self):
        """Test setting presence handles timeout."""
        from csp_adapter_symphony.adapter import Presence, _set_presence_sync

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        with patch("csp_adapter_symphony.adapter.SymphonyBdk") as mock_bdk_class:
            mock_bdk = MagicMock()

            async def slow_enter(*args):
                import asyncio

                await asyncio.sleep(10)
                return mock_bdk

            mock_bdk.__aenter__ = slow_enter
            mock_bdk.__aexit__ = AsyncMock(return_value=None)
            mock_bdk_class.return_value = mock_bdk

            # Should not raise, just timeout
            _set_presence_sync(config, Presence.AVAILABLE, timeout=0.01)


class TestSendSymphonyMessage:
    """Tests for send_symphony_message backwards-compat function."""

    def test_send_without_bdk_warns(self):
        """Test that calling without BDK logs warning."""
        from csp_adapter_symphony.adapter import send_symphony_message

        result = send_symphony_message("Hello", "room123")

        assert result is None

    def test_send_with_bdk(self):
        """Test sending with BDK instance."""
        from csp_adapter_symphony.adapter import send_symphony_message

        mock_bdk = MagicMock()
        mock_bdk.messages.return_value.send_message = AsyncMock(return_value=MagicMock())

        _ = send_symphony_message("Hello", "room123", bdk=mock_bdk)

        mock_bdk.messages.return_value.send_message.assert_called_once()


class TestCspRealTimeEventListener:
    """Tests for CspRealTimeEventListener class."""

    @pytest.mark.asyncio
    async def test_is_accepting_event_from_other_user(self):
        """Test that events from other users are accepted."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        room_mapper = SymphonyRoomMapper()
        listener = CspRealTimeEventListener(Queue(), set(), room_mapper)

        event = MagicMock()
        event.initiator.user.user_id = 12345

        bot_info = MagicMock()
        bot_info.id = 99999  # Different from initiator

        result = await listener.is_accepting_event(event, bot_info)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_accepting_event_from_self(self):
        """Test that events from self are rejected."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        room_mapper = SymphonyRoomMapper()
        listener = CspRealTimeEventListener(Queue(), set(), room_mapper)

        event = MagicMock()
        event.initiator.user.user_id = 12345

        bot_info = MagicMock()
        bot_info.id = 12345  # Same as initiator

        result = await listener.is_accepting_event(event, bot_info)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_accepting_event_with_error(self):
        """Test that events are accepted even if there's an error checking."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        room_mapper = SymphonyRoomMapper()
        listener = CspRealTimeEventListener(Queue(), set(), room_mapper)

        event = MagicMock()
        event.initiator = None  # Will cause AttributeError

        bot_info = MagicMock()

        result = await listener.is_accepting_event(event, bot_info)

        assert result is True  # Accept on error

    @pytest.mark.asyncio
    async def test_on_message_sent(self, mock_initiator, mock_message_event):
        """Test on_message_sent queues messages."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        msg_queue = Queue()
        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "stream123")
        listener = CspRealTimeEventListener(msg_queue, set(), room_mapper)

        await listener.on_message_sent(mock_initiator, mock_message_event)

        assert not msg_queue.empty()
        msg = msg_queue.get()
        assert msg.msg == "Hello, World!"

    @pytest.mark.asyncio
    async def test_on_message_sent_filtered(self, mock_initiator, mock_message_event):
        """Test on_message_sent filters messages not in room_ids."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        msg_queue = Queue()
        room_mapper = SymphonyRoomMapper()
        # Only accept messages from "other_stream"
        listener = CspRealTimeEventListener(msg_queue, {"other_stream"}, room_mapper)

        await listener.on_message_sent(mock_initiator, mock_message_event)

        # Message should be filtered out
        assert msg_queue.empty()

    @pytest.mark.asyncio
    async def test_on_symphony_elements_action(self):
        """Test on_symphony_elements_action queues form submissions."""
        from queue import Queue

        from csp_adapter_symphony.adapter import CspRealTimeEventListener

        msg_queue = Queue()
        room_mapper = SymphonyRoomMapper()
        room_mapper.register_room("Test Room", "stream123")
        listener = CspRealTimeEventListener(msg_queue, set(), room_mapper)

        initiator = MagicMock()
        initiator.user.display_name = "Test User"
        initiator.user.email = "test@example.com"
        initiator.user.user_id = 12345

        event = MagicMock()
        event.stream.stream_id = "stream123"
        event.stream.stream_type = "ROOM"
        event.form_id = "my_form"
        event.form_values = {"field1": "value1"}

        await listener.on_symphony_elements_action(initiator, event)

        assert not msg_queue.empty()
        msg = msg_queue.get()
        assert msg.form_id == "my_form"


class TestProcessQueue:
    """Tests for _process_queue method."""

    @pytest.mark.asyncio
    async def test_process_queue_stops_on_none(self):
        """Test that _process_queue stops when None is pushed."""

        from csp_adapter_symphony.adapter import SymphonyReaderPushAdapterImpl

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        adapter = SymphonyReaderPushAdapterImpl(config, set())
        adapter._running = True
        adapter._message_queue.put(None)

        # Should exit quickly when None is found
        await adapter._process_queue()

    @pytest.mark.asyncio
    async def test_process_queue_handles_messages(self):
        """Test that _process_queue processes messages."""
        import asyncio

        from csp_adapter_symphony.adapter import SymphonyReaderPushAdapterImpl

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        adapter = SymphonyReaderPushAdapterImpl(config, set())
        adapter._running = True
        adapter.push_tick = MagicMock()

        # Add a message then stop
        msg = SymphonyMessage(msg="Test")
        adapter._message_queue.put(msg)

        # Run briefly then stop
        async def stop_after_delay():
            await asyncio.sleep(0.05)
            adapter._running = False

        await asyncio.gather(
            adapter._process_queue(),
            stop_after_delay(),
        )

        # Message should have been pushed
        adapter.push_tick.assert_called()


class TestSymphonyReaderPushAdapterImpl:
    """Tests for SymphonyReaderPushAdapterImpl class."""

    def test_init(self):
        """Test adapter initialization."""
        from csp_adapter_symphony.adapter import SymphonyReaderPushAdapterImpl

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        adapter = SymphonyReaderPushAdapterImpl(config, {"Room1", "Room2"}, exit_msg="Goodbye!")

        assert adapter._rooms == {"Room1", "Room2"}
        assert adapter._exit_msg == "Goodbye!"
        assert adapter._running is False

    def test_start(self):
        """Test adapter start."""
        from csp_adapter_symphony.adapter import SymphonyReaderPushAdapterImpl

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        adapter = SymphonyReaderPushAdapterImpl(config, set())

        with patch.object(adapter, "_run"):
            adapter.start(None, None)

            assert adapter._running is True
            assert adapter._thread is not None

            # Clean up
            adapter._running = False
            adapter._thread.join(timeout=1.0)

    def test_stop(self):
        """Test adapter stop."""
        from csp_adapter_symphony.adapter import SymphonyReaderPushAdapterImpl

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )

        adapter = SymphonyReaderPushAdapterImpl(config, set())
        adapter._running = True
        adapter._thread = MagicMock()
        adapter._loop = MagicMock()

        adapter.stop()

        assert adapter._running is False
        adapter._thread.join.assert_called_once()


class TestSendMessagesThread:
    """Tests for _send_messages_thread function."""

    def test_send_messages_thread_processes_queue(self):
        """Test that _send_messages_thread processes messages."""
        import threading
        from queue import Queue

        from csp_adapter_symphony.adapter import _send_messages_thread

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()
        msg_queue = Queue()

        # Put None immediately to stop the thread
        msg_queue.put(None)

        with patch("csp_adapter_symphony.adapter.SymphonyBdk") as mock_bdk_class:
            mock_bdk = MagicMock()
            mock_bdk.__aenter__ = AsyncMock(return_value=mock_bdk)
            mock_bdk.__aexit__ = AsyncMock(return_value=None)
            mock_bdk.streams.return_value = MagicMock()
            mock_bdk_class.return_value = mock_bdk

            # Run in thread
            thread = threading.Thread(
                target=_send_messages_thread,
                args=(msg_queue, config, room_mapper),
            )
            thread.start()
            thread.join(timeout=2.0)

            assert not thread.is_alive()

    def test_send_messages_thread_sends_message(self):
        """Test that _send_messages_thread sends messages."""
        import threading
        from queue import Queue

        from csp_adapter_symphony.adapter import _send_messages_thread

        config = SymphonyAdapterConfig(
            host="test.symphony.com",
            bot_username="testbot",
            private_key_path="/path/to/key.pem",
        )
        room_mapper = SymphonyRoomMapper()
        msg_queue = Queue()

        # Add a message then stop
        msg = SymphonyMessage(stream_id="stream123", msg="Hello!")
        msg_queue.put(msg)
        msg_queue.put(None)

        with patch("csp_adapter_symphony.adapter.SymphonyBdk") as mock_bdk_class:
            mock_bdk = MagicMock()
            mock_bdk.__aenter__ = AsyncMock(return_value=mock_bdk)
            mock_bdk.__aexit__ = AsyncMock(return_value=None)
            mock_bdk.streams.return_value = MagicMock()
            mock_bdk.messages.return_value.send_message = AsyncMock()
            mock_bdk_class.return_value = mock_bdk

            thread = threading.Thread(
                target=_send_messages_thread,
                args=(msg_queue, config, room_mapper),
            )
            thread.start()
            thread.join(timeout=2.0)

            mock_bdk.messages.return_value.send_message.assert_called()

    def test_send_messages_thread_no_config(self):
        """Test that _send_messages_thread handles missing config."""
        import threading
        from queue import Queue

        from symphony.bdk.core.config.model.bdk_config import BdkConfig

        from csp_adapter_symphony.adapter import _send_messages_thread

        config = SymphonyAdapterConfig(bdk_config=BdkConfig(host="test.symphony.com"))
        config.bdk_config = None  # Clear config

        room_mapper = SymphonyRoomMapper()
        msg_queue = Queue()
        msg_queue.put(None)

        thread = threading.Thread(
            target=_send_messages_thread,
            args=(msg_queue, config, room_mapper),
        )
        thread.start()
        thread.join(timeout=2.0)

        assert not thread.is_alive()
