import os
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import SymphonyAdapter, SymphonyAdapterConfig, SymphonyMessage, mention_user

AGENT_HOST = os.environ["AGENT_HOST"]
SYMPHONY_MESSAGE_CREATE_URL = f"https://{AGENT_HOST}/agent/v4/stream/{{sid}}/message/create"
SYMPHONY_DATAFEED_CREATE_URL = f"https://{AGENT_HOST}/agent/v5/datafeeds"
SYMPHONY_DATAFEED_DELETE_URL = f"https://{AGENT_HOST}/agent/v5/datafeeds/{{datafeed_id}}"
SYMPHONY_DATAFEED_READ_URL = f"https://{AGENT_HOST}/agent/v5/datafeeds/{{datafeed_id}}/read"
SYMPHONY_ROOM_SEARCH_URL = f"https://{AGENT_HOST}/pod/v3/room/search"
SYMPHONY_ROOM_INFO_URL = f"https://{AGENT_HOST}/pod/v3/room/{{room_id}}/info"
SYMPHONY_IM_CREATE_URL = f"https://{AGENT_HOST}/pod/v1/im/create"
SYMPHONY_ROOM_MEMBERS_URL = f"https://{AGENT_HOST}/pod/v2/room/{{room_id}}/membership/list"
SYMPHONY_PRESENCE_URL = f"https://{AGENT_HOST}/pod/v2/user/presence"
AUTH_HOST = AGENT_HOST.replace(".symphony", "-api.symphony")
SESSION_AUTH_PATH = "/sessionauth/v1/authenticate"
KEY_AUTH_PATH = "/keyauth/v1/authenticate"


config = SymphonyAdapterConfig(
    symphony_host=AGENT_HOST,
    auth_host=AUTH_HOST,
    session_auth_path=SESSION_AUTH_PATH,
    key_auth_path=KEY_AUTH_PATH,
    message_create_url=SYMPHONY_MESSAGE_CREATE_URL,
    presence_url=SYMPHONY_PRESENCE_URL,
    datafeed_create_url=SYMPHONY_DATAFEED_CREATE_URL,
    datafeed_delete_url=SYMPHONY_DATAFEED_DELETE_URL,
    datafeed_read_url=SYMPHONY_DATAFEED_READ_URL,
    room_search_url=SYMPHONY_ROOM_SEARCH_URL,
    room_info_url=SYMPHONY_ROOM_INFO_URL,
    im_create_url=SYMPHONY_IM_CREATE_URL,
    room_members_url=SYMPHONY_ROOM_MEMBERS_URL,
    cert=os.environ["CERT_PATH"],
    key=os.environ["KEY_PATH"],
)


@csp.node
def reply_hi_when_mentioned(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Add a reaction to every message that starts with hello."""
    if "hello" in msg.msg.lower():
        return SymphonyMessage(
            room=msg.room,
            msg=f"Hello {mention_user(msg.user_id)}!",
        )


def graph():
    # Create a SymphonyAdapter object
    adapter = SymphonyAdapter(config)

    # Subscribe and unroll the messages
    msgs = csp.unroll(adapter.subscribe())

    # Print it out locally for debugging
    csp.print("msgs", msgs)

    # Add the reaction node
    responses = reply_hi_when_mentioned(msgs)

    # Print it out locally for debugging
    csp.print("responses", responses)

    # Publish the responses
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(seconds=120))
