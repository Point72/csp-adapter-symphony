import json
import logging
import threading
from queue import Queue
from typing import Dict, List, Optional, Tuple, Union

import csp
import requests
from csp import ts
from csp.impl.enum import Enum
from csp.impl.pushadapter import PushInputAdapter
from csp.impl.wiring import py_push_adapter_def

from .adapter_config import SymphonyAdapterConfig, SymphonyRoomMapper
from .message import SymphonyMessage, format_with_message_ml

__all__ = ("Presence", "SymphonyAdapter", "send_symphony_message")

log = logging.getLogger(__file__)


def _sync_create_data_feed(datafeed_create_url: str, header: Dict[str, str], datafeed_id: str = "") -> Tuple[requests.Response, str]:
    r = requests.post(
        url=datafeed_create_url,
        headers=header,
        json={"tag": datafeed_id} if datafeed_id else None,
    )
    datafeed_id = r.json()["id"]
    log.info(f"created symphony datafeed with id={datafeed_id}")
    return r, datafeed_id


def _get_or_create_datafeed(datafeed_create_url: str, header: Dict[str, str], datafeed_id: str = "") -> Tuple[requests.Response, str]:
    """
    It is considered best practice that bot's only create and read from one datafeed. If your bot goes down, it should re-authenticate,
    and try to read from the previously created datafeed. If this fails then you should create a new datafeed, and begin reading from this new datafeed.
    """
    r = requests.get(
        url=datafeed_create_url,
        headers=header,
        params={"tag": datafeed_id} if datafeed_id else None,
    )
    existing_datafeeds = r.json()
    if not existing_datafeeds:
        return _sync_create_data_feed(datafeed_create_url, header, datafeed_id)
    return r, existing_datafeeds[0]["id"]


class Presence(csp.Enum):
    AVAILABLE = Enum.auto()
    AWAY = Enum.auto()


def send_symphony_message(msg: str, room_id: str, message_create_url: str, header: Dict[str, str]):
    """Wrap message string and send it to symphony"""
    out_json = {"message": f"<messageML>{msg}</messageML>"}
    url = message_create_url.format(sid=room_id)
    return requests.post(
        url=url,
        json=out_json,
        headers=header,
    )


def create_im_stream(user_id: Union[str, List[str]], im_create_url: str, header: Dict[str, str]) -> Optional[str]:
    response = requests.post(
        url=im_create_url,
        json=[user_id] if isinstance(user_id, str) else user_id,
        headers=header,
    )

    if response.status_code != 200:
        return None

    try:
        return response.json().get("id")
    except requests.JSONDecodeError:
        return None


def _get_user_mentions(payload):
    # try to extract user mentions
    user_mentions = []
    try:
        payload_data = json.loads(payload.get("data", "{}"))
        for value in payload_data.values():
            if value["type"] == "com.symphony.user.mention":
                # if its a user mention (the only supported one for now),
                # then grab the payload
                user_id = str(value["id"][0]["value"])
                user_mentions.append(user_id)
    finally:
        return user_mentions


def _handle_event(event: dict, room_ids: set, room_mapper: SymphonyRoomMapper) -> Optional[SymphonyMessage]:
    if ("type" not in event) or ("payload" not in event):
        return None
    if event["type"] == "MESSAGESENT":
        payload = event.get("payload", {}).get("messageSent", {}).get("message")
        if payload:
            payload_stream_id = payload.get("stream", {}).get("streamId")
            if payload_stream_id and (not room_ids or payload_stream_id in room_ids):
                user = payload.get("user", {}).get("displayName", "USER_ERROR")
                user_email = payload.get("user", {}).get("email", "USER_ERROR")
                user_id = str(payload.get("user", {}).get("userId", "USER_ERROR"))
                user_mentions = _get_user_mentions(payload)
                msg = payload.get("message", "MSG_ERROR")

                # room name or "IM" for direct message
                room_type = payload.get("stream", {}).get("streamType", "ROOM")
                if room_type == "ROOM":
                    room_name = room_mapper.get_room_name(payload_stream_id)
                elif room_type == "IM":
                    # register the room name for the user so bot can respond
                    room_mapper.set_im_id(user, payload_stream_id)
                    room_name = "IM"
                else:
                    room_name = ""

                if room_name:
                    return SymphonyMessage(
                        user=user,
                        user_email=user_email,
                        user_id=user_id,
                        tags=user_mentions,
                        room=room_name,
                        msg=msg,
                    )
    elif event["type"] == "SYMPHONYELEMENTSACTION":
        payload = event.get("payload").get("symphonyElementsAction", {})
        payload_stream_id = payload.get("stream", {}).get("streamId")

        if not payload_stream_id:
            return None

        if room_ids and payload_stream_id not in room_ids:
            return None

        user = event.get("initiator", {}).get("user", {}).get("displayName", "USER_ERROR")
        user_email = event.get("initiator", {}).get("user", {}).get("email", "USER_ERROR")
        user_id = str(event.get("initiator", {}).get("user", {}).get("userId", "USER_ERROR"))
        user_mentions = _get_user_mentions(event.get("initiator", {}))
        form_id = payload.get("formId", "FORM_ID_ERROR")
        form_values = payload.get("formValues", {})

        # room name or "IM" for direct message
        room_type = payload.get("stream", {}).get("streamType", "ROOM")
        if room_type == "ROOM":
            room_name = room_mapper.get_room_name(payload_stream_id)
        elif room_type == "IM":
            # register the room name for the user so bot can respond
            room_mapper.set_im_id(user, payload_stream_id)
            room_name = "IM"
        else:
            room_name = ""

        if room_name:
            return SymphonyMessage(
                user=user,
                user_email=user_email,
                user_id=user_id,
                tags=user_mentions,
                room=room_name,
                form_id=form_id,
                form_values=form_values,
            )


class SymphonyReaderPushAdapterImpl(PushInputAdapter):
    def __init__(
        self,
        config: SymphonyAdapterConfig,
        rooms: set,
        exit_msg: str = "",
        room_mapper: Optional[SymphonyRoomMapper] = None,
    ):
        """Setup Symphony Reader

        Args:
            config (SymphonyAdapterConfig): Config specifying the url's to query symphony

            rooms (set): set of initial rooms for the bot to enter
            exit_msg (str): message to send on shutdown
            room_mapper (SymphonyRoomMapper): convenience object to map rooms that bot dynamically discovers
        """
        self._thread = None
        self._running = False
        self._config = config

        # message and datafeed
        self._datafeed_id = config.datafeed_id

        # rooms to enter by default
        self._rooms = rooms
        self._room_ids = set()
        self._exit_msg = exit_msg
        if room_mapper is None:
            room_mapper = SymphonyRoomMapper.from_config(config)
        self._room_mapper = room_mapper

    def _delete_datafeed_if_set(self):
        if self._datafeed_id:
            delete_url = self._config.datafeed_delete_url.format(datafeed_id=self._datafeed_id)
            resp = requests.delete(url=delete_url, headers=self._config.header)
            log.info(f"Deleted datafeed with url={delete_url}: resp={resp}")
            self._datafeed_id = self._config.datafeed_id  # set to default value

    def _set_new_datafeed(self):
        self._delete_datafeed_if_set()
        resp, datafeed_id = _get_or_create_datafeed(self._config.datafeed_create_url, self._config.header, self._datafeed_id)
        if resp.status_code == 403:
            raise Exception("Reached maximum number of active datafeeds. Cannot create new datafeed.")
        elif resp.status_code not in (200, 201, 204):
            raise Exception(f"ERROR: bad status ({resp.status_code}) from _get_or_create_datafeed. Cannot create new datafeed.")
        else:
            self._url = self._config.datafeed_read_url.format(datafeed_id=datafeed_id)
            self._datafeed_id = datafeed_id

    def start(self, starttime, endtime):
        self._set_new_datafeed()
        for room in self._rooms:
            room_id = self._room_mapper.get_room_id(room)
            if not room_id:
                raise Exception(f"ERROR: unable to find Symphony room named {room}")
            self._room_ids.add(room_id)

        # start reader thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = True
        self._thread.start()

    def stop(self):
        if self._running:
            # in order to unblock current requests.get, send a message to one of the rooms we are listening on
            self._running = False
            try:
                self._delete_datafeed_if_set()
                if self._exit_msg:
                    send_symphony_message(self._exit_msg, next(iter(self._room_ids)), self._config.message_create_url, self._config.header)
            except Exception:
                log.exception("Error on sending exit message and deleting datafeed on shutdown")
            self._thread.join()

    def _get_new_ack_id_and_messages(self, ack_id: str) -> Tuple[str, List[SymphonyMessage]]:
        ret = []
        resp = requests.post(url=self._url, headers=self._config.header, json={"ackId": ack_id})
        if resp.status_code == 400:
            # Bad datafeed, we need a new one
            self._set_new_datafeed()
            return "", []

        elif resp.status_code == 200:
            msg_json = resp.json()
            if "ackId" in msg_json:
                ack_id = msg_json["ackId"]
            events = msg_json.get("events", [])
            for m in events:
                maybe_msg = _handle_event(m, self._room_ids, self._room_mapper)
                if maybe_msg is not None:
                    ret.append(maybe_msg)
        return ack_id, ret

    def _run(self):
        ack_id = ""
        get_new_messages_func = self._config.get_retry_decorator()(self._get_new_ack_id_and_messages)
        while self._running:
            try:
                ack_id, ret = get_new_messages_func(ack_id)
            except Exception as exc:
                # On the final failure, this happens
                # No need to retry these calls, we are failing anyways
                error_msg = "An exception occured trying to interact with datafeed, max_attempts exceeded. Symphony Reader is shutting down..."
                log.error(error_msg)
                if self._config.error_room and (error_room_id := self._room_mapper.get_room_id(self._config.error_room)):
                    send_symphony_message(error_msg, error_room_id, self._config.message_create_url, self._config.header)
                raise exc
            if ret:
                self.push_tick(ret)


SymphonyReaderPushAdapter = py_push_adapter_def(
    "SymphonyReaderPushAdapter",
    SymphonyReaderPushAdapterImpl,
    ts[[SymphonyMessage]],
    config=object,
    rooms=set,
    exit_msg=str,
    room_mapper=object,
    memoize=False,  # config is not hashable
)


def _send_messages(
    msg_queue: Queue,
    config: SymphonyAdapterConfig,
    room_mapper: SymphonyRoomMapper,
):
    """Read messages from msg_queue and write to symphony. msg_queue to contain instances of SymphonyMessage, or None to shut down"""
    send_message = config.get_retry_decorator()(send_symphony_message)
    message_create_url = config.message_create_url
    create_im = config.get_retry_decorator()(create_im_stream)
    im_create_url = config.im_create_url
    header = config.header

    def _send_message(
        msg: SymphonyMessage,
    ):
        if msg.room == "IM" and hasattr(msg, "user_id"):
            stream_id = create_im(msg.user_id, im_create_url, header)
            if stream_id:
                room_mapper.set_im_id(msg.user_id, stream_id)
            room_name = msg.user_id
        else:
            room_name = msg.room
        room_id = room_mapper.get_room_id(room_name)
        error, msg_resp = None, None
        if not room_id:
            error = f"Cannot find id for symphony room {room_name} found in SymphonyMessage"
        else:
            msg_resp = send_message(msg.msg, room_id, message_create_url, header)
            if msg_resp.status_code != 200:
                error = f"Cannot send message to room: '{room_name}' - received symphony server response: status_code: {msg_resp.status_code} text: '{msg_resp.text}'"
                # let client know that an error occured
                if config.inform_client:
                    send_message(
                        "ERROR: Could not send messsage on Symphony",
                        room_id,
                        message_create_url,
                        header,
                    )

        if error is not None:
            log.error(error)

            if config.error_room is not None and (error_room_id := room_mapper.get_room_id(config.error_room)):
                formatted_error = format_with_message_ml(error, to_message_ml=True)

                # try to send full error message from Symphony, this might fail if not properly formatted
                error_msg_resp = send_message(
                    formatted_error,
                    error_room_id,
                    message_create_url,
                    header,
                )

                # If we failed sending the full response
                if error_msg_resp.status_code != 200:
                    # just log this error
                    log.error(
                        f"Cannot send message to room {config.error_room} - received symphony server response: {error_msg_resp.status_code} {error_msg_resp.text}"
                    )
                    send_message(
                        f"A message failed to be sent via symphony to room {room_name}, and the error message couldn't be properly displayed.",
                        error_room_id,
                        message_create_url,
                        header,
                    )

    while True:
        msg = msg_queue.get()
        msg_queue.task_done()
        if not msg:  # send None to kill
            break

        try:
            _send_message(msg)
        except Exception:  # don't stop the thread on error
            log.exception("Failed sending message to Symphony")


class SymphonyAdapter:
    def __init__(
        self,
        config: SymphonyAdapterConfig,
    ):
        """Setup Symphony Adapter"""
        self._config = config
        self._room_mapper = SymphonyRoomMapper.from_config(config)

    @csp.graph
    def subscribe(self, rooms: set = set(), exit_msg: str = "") -> ts[[SymphonyMessage]]:
        return SymphonyReaderPushAdapter(
            config=self._config,
            rooms=rooms,
            exit_msg=exit_msg,
            room_mapper=self._room_mapper,
        )

    # take in SymphonyMessage and send to symphony on separate thread
    @csp.node
    def _symphony_write(self, msg: ts[SymphonyMessage]):
        with csp.state():
            s_thread = None
            s_queue = None

        with csp.start():
            s_queue = Queue(maxsize=0)
            s_thread = threading.Thread(
                target=_send_messages,
                args=(
                    s_queue,
                    self._config,
                    self._room_mapper,
                ),
            )
            s_thread.start()

        with csp.stop():
            if s_thread:
                s_queue.put(None)  # send a None to tell the writer thread to exit
                s_queue.join()  # wait till the writer thread is done with the queue
                s_thread.join()  # then join with the thread

        if csp.ticked(msg):
            s_queue.put(msg)

    @csp.node
    def _set_presence(self, presence: ts[Presence], timeout: float = 5.0):
        try:
            ret = requests.post(url=self._config.presence_url, json={"category": presence.name}, headers=self._config.header, timeout=timeout)
            if ret.status_code != 200:
                log.error(f"Cannot set presence - symphony server response: {ret.status_code} {ret.text}")
        except Exception:
            log.exception("Failed setting presence...")

    @csp.graph
    def publish_presence(self, presence: ts[Presence], timeout: float = 5.0):
        self._set_presence(presence=presence, timeout=timeout)

    @csp.graph
    def publish(self, msg: ts[SymphonyMessage]):
        self._symphony_write(msg=msg)
