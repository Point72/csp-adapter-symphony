from time import sleep
from unittest.mock import MagicMock, call, patch

import csp
import pytest
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyMessage,
    format_with_message_ml,
    mention_user,
    send_symphony_message,
)
from csp_adapter_symphony.adapter import _handle_event
from csp_adapter_symphony.adapter_config import SymphonyAdapterConfig, SymphonyRoomMapper

SAMPLE_EVENTS = [
    {
        "type": "MESSAGESENT",
        "payload": {
            "messageSent": {
                "message": {
                    "stream": {"streamId": "a-stream-id", "streamType": "ROOM"},
                    "user": {"displayName": "Sender User", "email": "sender@user.blerg", "userId": "sender-user-id"},
                    "data": '{"key": {"type": "com.symphony.user.mention", "id": [{"value":"a-mentioned-user-id"}] } }',
                    "message": "a test message @a-mentioned-user-name",
                },
            },
        },
    },
    # TODO
    # {
    #     "type": "SYMPHONYELEMENTSACTION",
    # },
]


@csp.node
def hello(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    if csp.ticked(msg):
        text = f"Hello <@{msg.user_id}>!"
        return SymphonyMessage(
            room="another sample room",
            msg=text,
        )


class TestSymphony:
    def test_handle_event_messagesent(self):
        mock_room_mapper = MagicMock()
        mock_room_mapper.get_room_name.return_value = "Test Room"

        event = {
            "type": "MESSAGESENT",
            "payload": {
                "messageSent": {
                    "message": {
                        "stream": {"streamId": "123", "streamType": "ROOM"},
                        "user": {"displayName": "John Doe", "email": "john@example.com", "userId": 456},
                        "message": "Hello, world!",
                        "data": '{"key": {"type": "com.symphony.user.mention", "id": [{"value":"789"}] } }',
                    }
                }
            },
        }

        result = _handle_event(event, set(), mock_room_mapper)

        assert isinstance(result, SymphonyMessage)
        assert result.user == "John Doe"
        assert result.user_email == "john@example.com"
        assert result.user_id == "456"
        assert result.room == "Test Room"
        assert result.msg == "Hello, world!"
        assert result.tags == ["789"]

    def test_handle_event_messagesent_im(self):
        mock_room_mapper = MagicMock()

        event = {
            "type": "MESSAGESENT",
            "payload": {
                "messageSent": {
                    "message": {
                        "stream": {"streamId": "123", "streamType": "IM"},
                        "user": {"displayName": "John Doe", "email": "john@example.com", "userId": 456},
                        "message": "Hello, world!",
                    }
                }
            },
        }

        result = _handle_event(event, set(), mock_room_mapper)

        assert isinstance(result, SymphonyMessage)
        assert result.room == "IM"
        mock_room_mapper.set_im_id.assert_called_once_with("John Doe", "123")

    def test_handle_event_symphonyelementsaction(self):
        mock_room_mapper = MagicMock()
        mock_room_mapper.get_room_name.return_value = "Test Room"

        event = {
            "type": "SYMPHONYELEMENTSACTION",
            "initiator": {"user": {"displayName": "John Doe", "email": "john@example.com", "userId": 456}},
            "payload": {
                "symphonyElementsAction": {"stream": {"streamId": "123", "streamType": "ROOM"}, "formId": "test_form", "formValues": {"key": "value"}}
            },
        }

        result = _handle_event(event, set(), mock_room_mapper)

        assert isinstance(result, SymphonyMessage)
        assert result.user == "John Doe"
        assert result.user_email == "john@example.com"
        assert result.user_id == "456"
        assert result.room == "Test Room"
        assert result.form_id == "test_form"
        assert result.form_values == {"key": "value"}

    def test_handle_event_invalid(self):
        mock_room_mapper = MagicMock()

        event = {"type": "INVALID"}

        result = _handle_event(event, set(), mock_room_mapper)

        assert result is None

    def test_send_symphony_message(self):
        msg = "test_msg"
        room_id = "test_room_id"
        message_create_url = "message/create/url"
        header = {"Authorization": "Bearer Blerg"}
        with patch("requests.post") as requests_mock:
            send_symphony_message(msg, room_id, message_create_url, header)
        assert requests_mock.call_args_list == [
            call(
                url="message/create/url",
                json={"message": "\n        <messageML>\n        test_msg\n        </messageML>\n        "},
                headers={"Authorization": "Bearer Blerg"},
            )
        ]

    def test_room_mapper(self):
        room_mapper = SymphonyRoomMapper("room/search/url", "room/info/url", {"authorization": "bearer blerg"})

        with patch("requests.get") as requests_get_mock, patch("requests.post") as requests_post_mock:
            requests_get_mock.return_value.status_code = 200
            requests_get_mock.return_value.json.return_value = {"roomAttributes": {"name": "a sample room"}}
            requests_post_mock.return_value.status_code = 200
            requests_post_mock.return_value.json.return_value = {
                "rooms": [{"roomAttributes": {"name": "another sample room"}, "roomSystemInfo": {"id": "an id"}}]
            }

            # call twice for both paths
            assert room_mapper.get_room_name("anything") == "a sample room"
            assert room_mapper.get_room_name("anything") == "a sample room"
            # call twice for both paths
            assert room_mapper.get_room_id("another sample room") == "an id"
            assert room_mapper.get_room_id("another sample room") == "an id"

            room_mapper.set_im_id("username", "id")
            assert room_mapper.get_room_id("username") == "id"

    def test_mention_user(self):
        assert mention_user("blerg@blerg.com") == '<mention email="blerg@blerg.com" />'
        assert mention_user("blergid") == '<mention uid="blergid" />'

    def test_to_message_ml(self):
        input_text = "This & that < ${variable} #{hashtag}"
        expected_output = "This &#38; that &lt; &#36;{variable} &#35;{hashtag}"
        assert format_with_message_ml(input_text) == expected_output

    def test_from_message_ml(self):
        input_text = "This &#38; that &lt; &#36;{variable} &#35;{hashtag}"
        expected_output = "This & that < ${variable} #{hashtag}"
        assert format_with_message_ml(input_text, to_message_ml=False) == expected_output

    def test_no_changes(self):
        input_text = "Regular text without special characters"
        assert format_with_message_ml(input_text) == input_text
        assert format_with_message_ml(input_text, to_message_ml=False) == input_text

    @pytest.mark.parametrize("existing_datafeed", [True, False])
    @pytest.mark.parametrize("inform_client", [True, False])
    def test_symphony_instantiation(self, existing_datafeed, inform_client, caplog):
        with (
            patch("requests.get") as requests_get_mock,
            patch("requests.post") as requests_post_mock,
            patch("requests.delete") as requests_delete_mock,
            patch("ssl.SSLContext") as ssl_context_mock,
            patch("http.client.HTTPSConnection") as https_client_connection_mock,
            patch("csp_adapter_symphony.adapter_config.NamedTemporaryFile") as named_temporary_file_mock,
        ):
            # mock https connection
            https_connection_mock = MagicMock()
            https_client_connection_mock.return_value = https_connection_mock
            https_connection_mock.getresponse.return_value.status = 200
            https_connection_mock.getresponse.return_value.read.return_value = b'{"token": "a-fake-token"}'

            # mock temporary file creation for cert / key
            named_temporary_file_mock.return_value.__enter__.return_value.name = "a_temp_file"

            # mock get request response based on url
            def get_request(url, headers, json=None):
                assert url in ("https://symphony.host/pod/v3/room/{room_id}/info", "https://symphony.host/agent/v5/datafeeds")
                resp_mock = MagicMock()
                resp_mock.status_code = 200
                if url == "https://symphony.host/pod/v3/room/{room_id}/info":
                    resp_mock.json.return_value = {"roomAttributes": {"name": "a sample room"}}
                elif url == "https://symphony.host/agent/v5/datafeeds":
                    if existing_datafeed:
                        resp_mock.json.return_value = [{"id": "an id", "type": "fanout"}]
                    else:
                        resp_mock.json.return_value = []  # no existing datafeeds
                return resp_mock

            requests_get_mock.side_effect = get_request

            # mock post request response based on url
            def post_request(url, headers, json=None):
                assert url in (
                    # create datafeed
                    "https://symphony.host/agent/v5/datafeeds",
                    # read messages in room
                    "https://symphony.host/agent/v5/datafeeds/{datafeed_id}/read",
                    # room lookup
                    "https://symphony.host/pod/v3/room/search",
                    # send message
                    "https://symphony.host/agent/v4/stream/{sid}/message/create",
                )
                resp_mock = MagicMock()
                resp_mock.status_code = 200
                if url == "https://symphony.host/agent/v5/datafeeds":
                    # create datafeed
                    resp_mock.json.return_value = {"id": "an id"}
                elif url == "https://symphony.host/agent/v5/datafeeds/{datafeed_id}/read":
                    # read messages in room
                    resp_mock.json.return_value = {"id": "an id", "events": SAMPLE_EVENTS * 3}
                elif url == "https://symphony.host/pod/v3/room/search":
                    # room lookup
                    resp_mock.json.return_value = {"rooms": [{"roomAttributes": {"name": "another sample room"}, "roomSystemInfo": {"id": "an id"}}]}
                elif url == "https://symphony.host/agent/v4/stream/{sid}/message/create":
                    if inform_client:
                        resp_mock.json.return_value = {}
                        resp_mock.status_code = 401
                        ...
                    # send message
                sleep(0.1)
                return resp_mock

            requests_post_mock.side_effect = post_request
            config = SymphonyAdapterConfig(
                auth_host="auth.host",
                session_auth_path="/sessionauth/v1/authenticate",
                key_auth_path="/keyauth/v1/authenticate",
                message_create_url="https://symphony.host/agent/v4/stream/{{sid}}/message/create",
                presence_url="https://symphony.host/pod/v2/user/presence",
                datafeed_create_url="https://symphony.host/agent/v5/datafeeds",
                datafeed_delete_url="https://symphony.host/agent/v5/datafeeds/{{datafeed_id}}",
                datafeed_read_url="https://symphony.host/agent/v5/datafeeds/{{datafeed_id}}/read",
                room_search_url="https://symphony.host/pod/v3/room/search",
                room_info_url="https://symphony.host/pod/v3/room/{{room_id}}/info",
                cert_string="BEGIN CERTIFICATE:my_cert_string",  # hack to bypass file opening
                key_string="BEGIN PRIVATE KEY:my_key_string",  # hack to bypass file opening
                error_room=None if not inform_client else "another sample room",
                inform_client=inform_client,
            )
            # instantiate
            adapter = SymphonyAdapter(config)

            # assert auth worked properly to get token
            assert named_temporary_file_mock.return_value.__enter__.return_value.write.call_args_list == [
                call("BEGIN CERTIFICATE:my_cert_string"),
                call("BEGIN PRIVATE KEY:my_key_string"),
            ]
            assert ssl_context_mock.return_value.load_cert_chain.call_args_list == [
                # session token
                call(certfile="a_temp_file", keyfile="a_temp_file"),
                # key manager token
                call(certfile="a_temp_file", keyfile="a_temp_file"),
            ]

            @csp.graph
            def graph():
                # send a fake slack message to the app
                # stop = send_fake_message(clientmock, reqmock, am)

                # send a response
                resp = hello(csp.unroll(adapter.subscribe()))
                adapter.publish(resp)

                csp.add_graph_output("response", resp)

                # stop after first messages
                done_flag = csp.count(resp) == 2
                done_flag = csp.filter(done_flag, done_flag)
                csp.stop_engine(done_flag)

            # run the graph
            resp = csp.run(graph, realtime=True)

            assert len(resp["response"]) == 2
            assert resp["response"][0][1] == SymphonyMessage(
                room="another sample room",
                msg="Hello <@sender-user-id>!",
            )

            assert requests_get_mock.call_count == 2
            assert requests_get_mock.call_args_list == [
                call(
                    url="https://symphony.host/agent/v5/datafeeds",
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                ),
                call(
                    "https://symphony.host/pod/v3/room/{room_id}/info",
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                ),
            ]
            assert requests_post_mock.call_count >= 5
            if existing_datafeed:
                assert (
                    call(
                        url="https://symphony.host/agent/v5/datafeeds",
                        headers={
                            "sessionToken": "a-fake-token",
                            "keyManagerToken": "a-fake-token",
                            "Accept": "application/json",
                        },
                    )
                    not in requests_post_mock.call_args_list
                )
            else:
                assert (
                    call(
                        url="https://symphony.host/agent/v5/datafeeds",
                        headers={
                            "sessionToken": "a-fake-token",
                            "keyManagerToken": "a-fake-token",
                            "Accept": "application/json",
                        },
                    )
                    in requests_post_mock.call_args_list
                )
            assert (
                call(
                    url="https://symphony.host/agent/v5/datafeeds/{datafeed_id}/read",
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                    json={"ackId": ""},
                )
                in requests_post_mock.call_args_list
            )
            assert (
                call(
                    url="https://symphony.host/pod/v3/room/search",
                    json={"query": "another sample room"},
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                )
                in requests_post_mock.call_args_list
            )
            assert (
                call(
                    url="https://symphony.host/agent/v4/stream/{sid}/message/create",
                    json={"message": "\n        <messageML>\n        Hello <@sender-user-id>!\n        </messageML>\n        "},
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                )
                in requests_post_mock.call_args_list
            )
            assert requests_delete_mock.call_count == 1
            assert requests_delete_mock.call_args_list == [
                call(
                    url="https://symphony.host/agent/v5/datafeeds/{datafeed_id}",
                    headers={
                        "sessionToken": "a-fake-token",
                        "keyManagerToken": "a-fake-token",
                        "Accept": "application/json",
                    },
                )
            ]
            if inform_client:
                # Check if the expected message is in the logs
                assert "Cannot send message to room:" in caplog.text

                # If you want to be more specific, you can check individual records:
                for record in caplog.records:
                    if "Cannot send message to room:" in record.message:
                        assert record.levelname == "ERROR"
                        break

                assert (
                    call(
                        url="https://symphony.host/agent/v4/stream/{sid}/message/create",
                        json={"message": "\n        <messageML>\n        ERROR: Could not send messsage on Symphony\n        </messageML>\n        "},
                        headers={
                            "sessionToken": "a-fake-token",
                            "keyManagerToken": "a-fake-token",
                            "Accept": "application/json",
                        },
                    )
                    in requests_post_mock.call_args_list
                )
