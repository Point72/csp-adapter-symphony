import http.client
import json
import logging
import ssl
import threading
from datetime import timedelta
from functools import cached_property
from tempfile import NamedTemporaryFile
from typing import Callable, Dict, List, Optional, Union

import requests
import tenacity
from pydantic import BaseModel, Field, FilePath, computed_field, field_validator

__all__ = ("SymphonyAdapterConfig", "SymphonyRoomMapper")

log = logging.getLogger(__file__)


class SymphonyAdapterConfig(BaseModel):
    """A config class that holds the required information to interact with Symphony. Includes helper methods to make REST API calls to Symphony."""

    auth_host: str = Field(descrption="Authentication host, like `company-api.symphony.com`")
    session_auth_path: str = Field(descrption="Path to authenticate session, like `/sessionauth/v1/authenticate`")
    key_auth_path: str = Field(description="Path to authenticate key, like `/keyauth/v1/authenticate`")
    message_create_url: str = Field(
        description="String path to create a message, like `https://SYMPHONY_HOST/agent/v4/stream/{{sid}}/message/create`"
    )
    presence_url: str = Field(description="String path to create a message, like `https://SYMPHONY_HOST/pod/v2/user/presence`")
    datafeed_create_url: str = Field(description="String path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds`")
    datafeed_delete_url: str = Field(
        description="Format-string path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds/{{datafeed_id}}`"
    )
    datafeed_read_url: str = Field(
        description="Format-string path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds/{{datafeed_id}}/read`"
    )
    room_search_url: str = Field(description="Format-string path to create datafeed, like `https://SYMPHONY_HOST/pod/v3/room/search`")
    room_info_url: str = Field(description="Format-string path to create datafeed, like `https://SYMPHONY_HOST/pod/v3/room/{{room_id}}/info`")
    room_members_url: Optional[str] = Field(
        None, description="Format-string path to get room members in a room, like `https://SYMPHONY_HOST/pod/v2/room/{{room_id}}/membership/list`"
    )
    cert_string: Union[str, FilePath] = Field(description="Pem format string of client certificate")
    key_string: Union[str, FilePath] = Field(description="Pem format string of client private key")
    error_room: Optional[str] = Field(
        None,
        description="A room to direct error messages to, if a message fails to be sent over symphony, or if the SymphonyReaderPushAdapter crashes",
    )
    inform_client: bool = Field(False, description="Whether to inform the intended recipient of a failed message that the message failed")
    max_attempts: int = Field(10, description="Max attempts for datafeed and message post requests before raising exception. If -1, no maximum")
    initial_interval_ms: int = Field(500, description="Initial interval to wait between attempts, in milliseconds")
    multiplier: float = Field(2.0, description="Multiplier between attempt delays for exponential backoff")
    max_interval_ms: int = Field(300000, description="Maximum delay between retry attempts, in milliseconds")

    @field_validator("cert_string")
    def load_cert_if_file(cls, v):
        if "BEGIN CERTIFICATE" in v:
            return v
        with open(v, "r") as fp:
            return fp.read()

    @field_validator("key_string")
    def load_key_if_file(cls, v):
        if "BEGIN PRIVATE KEY" in v:
            return v
        with open(v, "r") as fp:
            return fp.read()

    # The type hint ignore is due to mypy possibly throwing a
    # 'Decorated property not supported' error
    @computed_field  # type: ignore[misc]
    @cached_property
    def header(self) -> Dict[str, str]:
        """Returns header from authentication. This performs a network request. The result gets cached for re-use"""
        return _symphony_session(
            auth_host=self.auth_host,
            session_auth_path=self.session_auth_path,
            key_auth_path=self.key_auth_path,
            cert_string=self.cert_string,
            key_string=self.key_string,
        )

    def get_retry_decorator(self) -> Callable:
        """Returns a tenacity retry decorator that can wrap arbitrary functions"""
        exp_wait = tenacity.wait_exponential(
            min=timedelta(milliseconds=self.initial_interval_ms), max=timedelta(milliseconds=self.max_interval_ms), multiplier=self.multiplier
        )
        stop = tenacity.stop_after_attempt(self.max_attempts) if self.max_attempts != -1 else tenacity.stop_never
        return tenacity.retry(
            reraise=True,
            stop=stop,
            wait=exp_wait,
            retry=tenacity.retry_if_exception_type(requests.RequestException),
            before_sleep=tenacity.before_sleep_log(log, logging.DEBUG),
        )

    def get_room_id(self, room_name: str) -> Optional[str]:
        """Given a room name, returns the corresponding room id, if it can be found. This performs a network request."""
        return _get_room_id(room_name=room_name, room_search_url=self.room_search_url, header=self.header)

    def get_user_ids_in_room(self, room_id: Optional[str] = None, room_name: Optional[str] = None) -> List[str]:
        """Given a room id or room name, returns the user id's of the users in the room. Exactly one of 'room_id' or 'room_name' must be set."""
        room_name_is_none = room_name is None
        room_id_is_none = room_id is None

        if room_name_is_none and room_id_is_none:
            raise ValueError("One of 'room_name' and 'room_id' must not be None")

        elif not room_name_is_none and not room_id_is_none:
            raise ValueError("At most one of 'room_name' and 'room_id' must be set.")

        elif room_name_is_none and not room_id_is_none:
            return _get_user_ids_in_room(room_id=room_id, room_members_url=self.room_members_url, header=self.header)

        # Last case, must get room_id from room_name
        if (true_room_id := self.get_room_id(room_name)) is None:
            return []
        return _get_user_ids_in_room(room_id=true_room_id, room_members_url=self.room_members_url, header=self.header)

    def get_room_name(self, room_id: str) -> Optional[str]:
        """Given room_id, returns the name of the room."""
        return _get_room_name(room_id=room_id, room_info_url=self.room_info_url, header=self.header)


class SymphonyRoomMapper:
    def __init__(self, room_search_url: str, room_info_url: str, header: Dict[str, str]):
        self._name_to_id = {}
        self._id_to_name = {}
        self._room_search_url = room_search_url
        self._room_info_url = room_info_url
        self._header = header
        self._lock = threading.Lock()

    @staticmethod
    def from_config(config: SymphonyAdapterConfig) -> "SymphonyRoomMapper":
        return SymphonyRoomMapper(config.room_search_url, config.room_info_url, config.header)

    def get_room_id(self, room_name):
        with self._lock:
            if room_name in self._name_to_id:
                return self._name_to_id[room_name]
            else:
                room_id = _get_room_id(room_name, self._room_search_url, self._header)
                self._name_to_id[room_name] = room_id
                self._id_to_name[room_id] = room_name
                return room_id

    def get_room_name(self, room_id):
        with self._lock:
            if room_id in self._id_to_name:
                return self._id_to_name[room_id]
            else:
                room_name = _get_room_name(room_id, self._room_info_url, self._header)
                self._name_to_id[room_name] = room_id
                self._id_to_name[room_id] = room_name
                return room_name

    def set_im_id(self, user, id):
        with self._lock:
            self._id_to_name[id] = user
            self._name_to_id[user] = id


def _client_cert_post(host: str, request_url: str, cert_file: str, key_file: str) -> str:
    # Define the client certificate settings for https connection
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)

    # Create a connection to submit HTTP requests
    connection = http.client.HTTPSConnection(host, port=443, context=context)

    # Use connection to submit a HTTP POST request
    # Note that we omit content-type headers and the request body per Symphony's docs here:
    # https://rest-api.symphony.com/main/bot-authentication/session-authenticate
    connection.request(method="POST", url=request_url, headers={})

    # Print the HTTP response from the IOT service endpoint
    response = connection.getresponse()

    if response.status != 200:
        raise Exception(f"Cannot connect for symphony handshake to https://{host}{request_url}: {response.status}:{response.reason}")
    data = response.read().decode("utf-8")
    return json.loads(data)


def _symphony_session(
    auth_host: str,
    session_auth_path: str,
    key_auth_path: str,
    cert_string: str,
    key_string: str,
) -> Dict[str, str]:
    """Setup symphony session and return the header

    Args:
        auth_host (str): authentication host, like `company-api.symphony.com`
        session_auth_path (str): path to authenticate session, like `/sessionauth/v1/authenticate`
        key_auth_path (str): path to authenticate key, like `/keyauth/v1/authenticate`
        cert_string (str): pem format string of client certificate
        key_string (str): pem format string of client private key
    Returns:
        Dict[str, str]: headers from authentication
    """
    with NamedTemporaryFile(mode="wt", delete=False) as cert_file:
        with NamedTemporaryFile(mode="wt", delete=False) as key_file:
            cert_file.write(cert_string)
            key_file.write(key_string)

    data = _client_cert_post(auth_host, session_auth_path, cert_file.name, key_file.name)
    session_token = data["token"]

    data = _client_cert_post(auth_host, key_auth_path, cert_file.name, key_file.name)
    key_manager_token = data["token"]

    headers = {
        "sessionToken": session_token,
        "keyManagerToken": key_manager_token,
        "Accept": "application/json",
    }
    return headers


def _get_room_id(room_name: str, room_search_url: str, header: Dict[str, str]) -> Optional[str]:
    """Given a room name, find its room ID"""
    query = {"query": room_name}
    res = requests.post(
        url=room_search_url,
        json=query,
        headers=header,
    )
    if res and res.status_code == 200:
        res_json = res.json()
        for room in res_json["rooms"]:
            # in theory there could be a room whose name is a subset of another, and so the search could return multiple
            # go through search results to find room with name exactly as given
            name = room.get("roomAttributes", {}).get("name")
            if name and name == room_name:
                id = room.get("roomSystemInfo", {}).get("id")
                if id:
                    return id
        return None  # actually no exact matches, or malformed content from symphony
    else:
        log.error(f"ERROR looking up Symphony room_id for room {room_name}: status {res.status_code} text {res.text}")


def _get_user_ids_in_room(room_id: str, room_members_url: str, header: Dict[str, str]) -> List[str]:
    """Given a room id, returns a list of id's as strings for users in the room."""
    res = requests.get(
        url=room_members_url.format(room_id=room_id),
        headers=header,
    )
    user_id_list = []
    if res and res.status_code == 200:
        res_json = res.json()
        for val in res_json:
            if user_id := val.get("id"):
                user_id_list.append(str(user_id))
            else:
                log.error(f"Malformed user {val} in Symphony room with id {room_id}")
    else:
        log.error(
            f"ERROR: failed to query Symphony for room name from id {room_id} via url {room_members_url}: code {res.status_code} text {res.text}"
        )
    return user_id_list


def _get_room_name(room_id: str, room_info_url: str, header: Dict[str, str]):
    """Given a room ID, find its name"""
    url = room_info_url.format(room_id=room_id)
    res = requests.get(
        url,
        headers=header,
    )
    if res and res.status_code == 200:
        res_json = res.json()
        name = res_json.get("roomAttributes", {}).get("name")
        if name:
            return name
        log.error(f"ERROR: malformed response from Symphony room info call to get name from id {room_id} via url {url}: {res_json}")
    else:
        log.error(f"ERROR: failed to query Symphony for room name from id {room_id} via url {url}: code {res.status_code} text {res.text}")
