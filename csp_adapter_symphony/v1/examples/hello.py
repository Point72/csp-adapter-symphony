"""Example Symphony bot that replies "Hello!" to greetings.

This example demonstrates:
- Loading configuration from environment variables
- Subscribing to messages
- Replying with user mentions

Environment Variables Required:
    SYMPHONY_HOST: Your Symphony pod hostname
    SYMPHONY_BOT_USERNAME: Bot's service account username
    SYMPHONY_BOT_COMBINED_CERT_PATH: Path to combined cert file

Optional:
    AUTH_HOST: Auth host (defaults to SYMPHONY_HOST with -api suffix)
"""

import os
from datetime import timedelta

import csp
from chatom.base import Message
from csp import ts

from csp_adapter_symphony.v1 import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
    SymphonyPresenceStatus,
    mention_user_by_uid,
)

# Customize - set these environment variables or modify directly
SYMPHONY_HOST = os.environ["SYMPHONY_HOST"]
# Auth host is typically different - e.g., replacing ".symphony" with "-api.symphony"
AUTH_HOST = os.environ.get("AUTH_HOST", SYMPHONY_HOST.replace(".symphony", "-api.symphony"))

# Configuration with all separate hosts
config = SymphonyAdapterConfig(
    host=SYMPHONY_HOST,  # Default/fallback host
    pod_host=SYMPHONY_HOST,  # Pod API host (for room info, presence, etc.)
    agent_host=SYMPHONY_HOST,  # Agent API host (for messages, datafeed)
    session_auth_host=AUTH_HOST,  # Session Auth host (for authentication)
    key_manager_host=AUTH_HOST,  # Key Manager host (for key auth)
    bot_certificate_path=os.environ["SYMPHONY_BOT_COMBINED_CERT_PATH"],
    bot_username=os.environ["SYMPHONY_BOT_USERNAME"],
    ssl_verify=False,
)

print(f"Symphony Host: {SYMPHONY_HOST}")
print(f"Auth Host: {AUTH_HOST}")
print(f"Bot username: {config.bot_username}")
print(f"Certificate: {os.environ['SYMPHONY_BOT_COMBINED_CERT_PATH']}")


@csp.node
def reply_to_hello(msg: ts[Message]) -> ts[SymphonyMessage]:
    """Reply to messages containing 'hello'."""
    if "hello" in msg.text.lower():
        # Create a mention for the author and reply in the same channel
        mention = mention_user_by_uid(msg.author_id)
        reply = msg.as_reply(f"Hello {mention}!")
        return reply


def graph():
    # Create a SymphonyAdapter object
    adapter = SymphonyAdapter(config)

    # Set bot presence to available
    adapter.publish_presence(csp.const(SymphonyPresenceStatus.AVAILABLE))

    # Subscribe and unroll the messages
    # Use rooms={"Room1", "Room2"} to limit to specific rooms
    msgs = csp.unroll(adapter.subscribe())

    # Print messages locally for debugging
    csp.print("Received:", msgs)

    # Handle different types of messages
    hello_responses = reply_to_hello(msgs)

    # Publish all responses
    adapter.publish(hello_responses)


if __name__ == "__main__":
    print("Starting Symphony bot...")
    print("The bot will run for 2 minutes. Press Ctrl+C to stop earlier.")
    csp.run(graph, realtime=True, endtime=timedelta(minutes=2))
    print("Bot stopped.")
