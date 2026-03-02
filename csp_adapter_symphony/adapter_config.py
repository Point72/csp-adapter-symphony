"""Configuration module for Symphony adapter using symphony-bdk-python.

This module provides configuration classes for connecting to Symphony
using the official BDK (Bot Development Kit).
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator

# Import BDK types - handle case when not installed
try:
    from symphony.bdk.core.config.loader import BdkConfigLoader
    from symphony.bdk.core.config.model.bdk_config import BdkConfig

    _BDK_AVAILABLE = True
except ImportError:
    _BDK_AVAILABLE = False
    BdkConfigLoader = None
    BdkConfig = None

__all__ = ("SymphonyAdapterConfig", "SymphonyRoomMapper")

log = logging.getLogger(__name__)


def _check_bdk_available():
    """Check if symphony-bdk-python is available."""
    if not _BDK_AVAILABLE:
        raise ImportError("symphony-bdk-python is required but not installed. Install it with: pip install symphony-bdk-python")


class SymphonyAdapterConfig(BaseModel):
    """A config class that holds the required information to interact with Symphony using the BDK.

    This configuration can be created either from:
    1. A BDK config file path (YAML or JSON)
    2. A BdkConfig object directly
    3. Individual configuration parameters (for backwards compatibility)

    The recommended approach is to use BDK config files for consistency with
    the Symphony BDK ecosystem.
    """

    model_config = {"arbitrary_types_allowed": True}

    # BDK configuration - preferred approach
    bdk_config: Optional[BdkConfig] = Field(
        None,
        description="A BdkConfig object from symphony-bdk-python. If provided, other connection parameters are ignored.",
    )
    bdk_config_path: Optional[str] = Field(
        None,
        description="Path to a BDK config file (YAML or JSON). If provided, bdk_config will be loaded from this file.",
    )

    # Legacy configuration options (for backwards compatibility)
    host: Optional[str] = Field(
        None,
        description="Base URL for Symphony, like `company.symphony.com`. Used when bdk_config is not provided.",
        validation_alias=AliasChoices("host", "symphony_host"),
    )

    # Separate endpoint hosts (if different from main host)
    pod_host: Optional[str] = Field(
        None,
        description="Host for Pod API (if different from main host). Example: pod.symphony.com",
    )
    agent_host: Optional[str] = Field(
        None,
        description="Host for Agent API (if different from main host). Example: agent.symphony.com",
    )
    session_auth_host: Optional[str] = Field(
        None,
        description="Host for Session Auth API (if different from main host). Example: session.symphony.com",
    )
    key_manager_host: Optional[str] = Field(
        None,
        description="Host for Key Manager API (if different from main host). Example: km.symphony.com",
    )

    private_key_path: Optional[str] = Field(
        None,
        description="Path to the bot's RSA private key file.",
        validation_alias=AliasChoices("private_key_path", "key"),
    )
    private_key_content: Optional[str] = Field(
        None,
        description="Content of the bot's RSA private key (PEM format).",
    )
    certificate_path: Optional[str] = Field(
        None,
        description="Path to the bot's certificate file (.pem or .crt) for certificate-based authentication.",
        validation_alias=AliasChoices("certificate_path", "cert", "cert_path"),
    )
    certificate_content: Optional[str] = Field(
        None,
        description="Content of the bot's certificate (PEM format).",
    )
    bot_username: Optional[str] = Field(
        None,
        description="The bot's username as configured in Symphony admin console.",
    )

    # Common options
    error_room: Optional[str] = Field(
        None,
        description="A room to direct error messages to, if a message fails to be sent over symphony.",
    )
    inform_client: bool = Field(
        False,
        description="Whether to inform the intended recipient of a failed message that the message failed.",
    )
    max_attempts: int = Field(
        10,
        description="Max attempts for datafeed and message post requests before raising exception. If -1, no maximum.",
    )
    initial_interval_ms: int = Field(
        500,
        description="Initial interval to wait between attempts, in milliseconds.",
    )
    multiplier: float = Field(
        2.0,
        description="Multiplier between attempt delays for exponential backoff.",
    )
    max_interval_ms: int = Field(
        300000,
        description="Maximum delay between retry attempts, in milliseconds.",
    )
    datafeed_version: str = Field(
        "v2",
        description="Version of datafeed to use ('v1' or 'v2'). V2 is recommended.",
    )
    ssl_trust_store_path: Optional[str] = Field(
        None,
        description="Path to a custom CA certificate bundle file (PEM format) for SSL verification. Use this for self-signed certificates.",
    )
    ssl_verify: bool = Field(
        True,
        description="Whether to verify SSL certificates. Set to False to disable SSL verification (not recommended for production).",
    )

    @model_validator(mode="after")
    def validate_and_build_config(self) -> "SymphonyAdapterConfig":
        """Validate configuration and build BdkConfig if not provided."""
        _check_bdk_available()

        # If bdk_config is already set, we're done
        if self.bdk_config is not None:
            return self

        # Try to load from config file path
        if self.bdk_config_path:
            self.bdk_config = BdkConfigLoader.load_from_file(self.bdk_config_path)
            return self

        # Build from individual parameters
        if self.host and self.bot_username:
            config_dict: Dict[str, Any] = {
                "host": self.host,
                "bot": {
                    "username": self.bot_username,
                },
                "datafeed": {
                    "version": self.datafeed_version,
                    "retry": {
                        "maxAttempts": self.max_attempts if self.max_attempts != -1 else 0,
                        "initialIntervalMillis": self.initial_interval_ms,
                        "multiplier": self.multiplier,
                        "maxIntervalMillis": self.max_interval_ms,
                    },
                },
                "retry": {
                    "maxAttempts": self.max_attempts if self.max_attempts != -1 else 0,
                    "initialIntervalMillis": self.initial_interval_ms,
                    "multiplier": self.multiplier,
                    "maxIntervalMillis": self.max_interval_ms,
                },
            }

            # Add separate endpoint hosts if specified
            if self.pod_host:
                config_dict["pod"] = {"host": self.pod_host}
            if self.agent_host:
                config_dict["agent"] = {"host": self.agent_host}
            if self.session_auth_host:
                config_dict["sessionAuth"] = {"host": self.session_auth_host}
            if self.key_manager_host:
                config_dict["keyManager"] = {"host": self.key_manager_host}

            # Add private key configuration
            if self.private_key_path:
                config_dict["bot"]["privateKey"] = {"path": self.private_key_path}
            elif self.private_key_content:
                config_dict["bot"]["privateKey"] = {"content": self.private_key_content}

            # Add certificate configuration for certificate-based auth
            if self.certificate_path:
                config_dict["bot"]["certificate"] = {"path": self.certificate_path}
            elif self.certificate_content:
                config_dict["bot"]["certificate"] = {"content": self.certificate_content}

            # Add SSL configuration
            if self.ssl_trust_store_path:
                config_dict["ssl"] = {"trustStore": {"path": self.ssl_trust_store_path}}

            self.bdk_config = BdkConfig(**config_dict)

            # Handle ssl_verify=False by patching the config after creation
            if not self.ssl_verify:
                log.warning("SSL verification is disabled. This is not recommended for production use.")
                self._patch_ssl_verify()

            return self

        raise ValueError("Either bdk_config, bdk_config_path, or (host, bot_username, and private_key_path/private_key_content) must be provided.")

    def _patch_ssl_verify(self):
        """Patch the BDK to disable SSL verification.

        This is a workaround since the BDK doesn't expose ssl_verify as a config option.
        It patches the ApiClientFactory to set verify_ssl=False on all clients.
        """
        try:
            from symphony.bdk.core.client.api_client_factory import ApiClientFactory
            from symphony.bdk.gen.configuration import Configuration

            # Patch the Configuration class __init__ to set verify_ssl=False by default
            original_config_init = Configuration.__init__

            def patched_config_init(config_self, *args, **kwargs):
                original_config_init(config_self, *args, **kwargs)
                config_self.verify_ssl = False

            Configuration.__init__ = patched_config_init

            # Also patch _get_client_config in case it's called
            if hasattr(ApiClientFactory, "_get_client_config"):
                original_get_client_config = ApiClientFactory._get_client_config

                def patched_get_client_config(factory_self, context, server_config):
                    config = original_get_client_config(factory_self, context, server_config)
                    config.verify_ssl = False
                    return config

                ApiClientFactory._get_client_config = patched_get_client_config

            log.debug("SSL verification has been disabled via monkey patch")
        except ImportError as e:
            log.warning(f"Could not patch SSL verification - BDK not available: {e}")

    @classmethod
    def from_bdk_config(cls, bdk_config: BdkConfig, **kwargs) -> "SymphonyAdapterConfig":
        """Create a SymphonyAdapterConfig from an existing BdkConfig object.

        Args:
            bdk_config: A BdkConfig object from symphony-bdk-python.
            **kwargs: Additional configuration options (error_room, inform_client, etc.)

        Returns:
            A configured SymphonyAdapterConfig instance.
        """
        return cls(bdk_config=bdk_config, **kwargs)

    @classmethod
    def from_file(cls, config_path: str, **kwargs) -> "SymphonyAdapterConfig":
        """Create a SymphonyAdapterConfig from a BDK config file.

        Args:
            config_path: Path to a BDK config file (YAML or JSON).
            **kwargs: Additional configuration options (error_room, inform_client, etc.)

        Returns:
            A configured SymphonyAdapterConfig instance.
        """
        return cls(bdk_config_path=config_path, **kwargs)

    @classmethod
    def from_symphony_dir(cls, relative_path: str = "config.yaml", **kwargs) -> "SymphonyAdapterConfig":
        """Create a SymphonyAdapterConfig from a config file in ~/.symphony directory.

        Args:
            relative_path: Relative path from ~/.symphony to the config file.
            **kwargs: Additional configuration options.

        Returns:
            A configured SymphonyAdapterConfig instance.
        """
        config_path = Path.home() / ".symphony" / relative_path
        return cls.from_file(str(config_path), **kwargs)


class SymphonyRoomMapper:
    """Thread-safe mapper for Symphony room names and IDs.

    This class maintains a cache of room name to ID mappings and vice versa,
    using the BDK's StreamService to resolve unknown rooms.
    """

    def __init__(self, stream_service=None):
        """Initialize the room mapper.

        Args:
            stream_service: Optional StreamService from SymphonyBdk. If not provided,
                           room resolution will not be available until set.
        """
        self._name_to_id: Dict[str, str] = {}
        self._id_to_name: Dict[str, str] = {}
        self._stream_service = stream_service
        self._lock = threading.Lock()

    def set_stream_service(self, stream_service):
        """Set the stream service for room resolution."""
        self._stream_service = stream_service

    def get_room_id(self, room_name: str) -> Optional[str]:
        """Get the room ID for a given room name.

        Args:
            room_name: The display name of the room.

        Returns:
            The room's stream ID, or None if not found.
        """
        with self._lock:
            if room_name in self._name_to_id:
                return self._name_to_id[room_name]

            # If it looks like a stream ID already, return it
            if len(room_name) > 20 and " " not in room_name:
                return room_name

            return None

    async def get_room_id_async(self, room_name: str) -> Optional[str]:
        """Get the room ID for a given room name, using async BDK calls if needed.

        Args:
            room_name: The display name of the room.

        Returns:
            The room's stream ID, or None if not found.
        """
        # Check cache first
        cached = self.get_room_id(room_name)
        if cached:
            return cached

        # Try to resolve using stream service
        if self._stream_service is None:
            return None

        try:
            from symphony.bdk.gen.pod_model.v2_room_search_criteria import V2RoomSearchCriteria

            results = await self._stream_service.search_rooms(V2RoomSearchCriteria(query=room_name), limit=10)
            if results and results.rooms:
                for room in results.rooms:
                    room_attrs = room.room_attributes
                    room_info = room.room_system_info
                    if room_attrs and room_info and room_attrs.name == room_name:
                        room_id = room_info.id
                        with self._lock:
                            self._name_to_id[room_name] = room_id
                            self._id_to_name[room_id] = room_name
                        return room_id
        except Exception as e:
            log.error(f"Error searching for room '{room_name}': {e}")

        return None

    def get_room_name(self, room_id: str) -> Optional[str]:
        """Get the room name for a given room ID.

        Args:
            room_id: The room's stream ID.

        Returns:
            The room's display name, or None if not found.
        """
        with self._lock:
            return self._id_to_name.get(room_id)

    async def get_room_name_async(self, room_id: str) -> Optional[str]:
        """Get the room name for a given room ID, using async BDK calls if needed.

        Args:
            room_id: The room's stream ID.

        Returns:
            The room's display name, or None if not found.
        """
        # Check cache first
        cached = self.get_room_name(room_id)
        if cached:
            return cached

        # Try to resolve using stream service
        if self._stream_service is None:
            return None

        try:
            room_info = await self._stream_service.get_room_info(room_id)
            if room_info and room_info.room_attributes:
                room_name = room_info.room_attributes.name
                with self._lock:
                    self._name_to_id[room_name] = room_id
                    self._id_to_name[room_id] = room_name
                return room_name
        except Exception as e:
            log.error(f"Error getting room info for '{room_id}': {e}")

        return None

    def set_im_id(self, user_identifier: str, stream_id: str):
        """Register an IM stream ID for a user.

        Args:
            user_identifier: The user's display name or user ID.
            stream_id: The IM stream ID.
        """
        with self._lock:
            self._id_to_name[stream_id] = user_identifier
            self._name_to_id[user_identifier] = stream_id

    def register_room(self, room_name: str, room_id: str):
        """Manually register a room name to ID mapping.

        Args:
            room_name: The display name of the room.
            room_id: The room's stream ID.
        """
        with self._lock:
            self._name_to_id[room_name] = room_id
            self._id_to_name[room_id] = room_name
