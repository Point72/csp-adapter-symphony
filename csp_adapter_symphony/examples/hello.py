"""Example Symphony bot that replies "Hello!" to greetings.

This example demonstrates:
- Loading configuration from ~/.symphony/config.yaml
- Subscribing to messages
- Replying with user mentions
- Sending direct messages

Before running this example, create a config file at ~/.symphony/config.yaml:

    host: your-company.symphony.com
    bot:
      username: your-bot-username
      privateKey:
        path: /path/to/your/bot-private-key.pem
"""

import os
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    Presence,
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

# Customize - set these environment variables or modify directly
AGENT_HOST = os.environ["AGENT_HOST"]
# Auth host is typically different - e.g., replacing ".symphony" with "-api.symphony"
AUTH_HOST = os.environ.get("AUTH_HOST", AGENT_HOST.replace(".symphony", "-api.symphony"))

# Configuration with all separate hosts
config = SymphonyAdapterConfig(
    host=AGENT_HOST,  # Default/fallback host
    pod_host=AGENT_HOST,  # Pod API host (for room info, presence, etc.)
    agent_host=AGENT_HOST,  # Agent API host (for messages, datafeed)
    session_auth_host=AUTH_HOST,  # Session Auth host (for authentication)
    key_manager_host=AUTH_HOST,  # Key Manager host (for key auth)
    certificate_path=os.environ["SYMPHONY_CERTIFICATE_PATH"],
    bot_username=os.environ["SYMPHONY_BOT_USERNAME"],
    ssl_verify=False,
)

print(f"Agent Host: {AGENT_HOST}")
print(f"Auth Host: {AUTH_HOST}")
print(f"Bot username: {config.bot_username}")
print(f"Certificate: {os.environ['SYMPHONY_CERTIFICATE_PATH']}")


@csp.node
def reply_to_hello(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Reply to messages containing 'hello'."""
    if "hello" in msg.msg.lower():
        # Use the built-in mention() method for easy user mentions
        return msg.reply(f"Hello {msg.mention()}!", mention_author=False)


@csp.node
def handle_dm(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Send a private response to direct messages."""
    if msg.is_direct_message():
        return msg.reply("Thanks for the DM! I received your message.")


@csp.node
def handle_help(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Send help info as a DM when user types 'help'."""
    if "help" in msg.msg.lower() and not msg.is_direct_message():
        # Reply privately with help information
        return msg.direct_reply(
            "Here's how to use this bot:\n"
            "- Say 'hello' to get a greeting\n"
            "- Send me a DM for private conversation\n"
            "- Type 'help' anytime for this message"
        )


def graph():
    # Create a SymphonyAdapter object
    adapter = SymphonyAdapter(config)

    # Set bot presence to available
    adapter.publish_presence(csp.const(Presence.AVAILABLE))

    # Subscribe and unroll the messages
    # Use rooms={"Room1", "Room2"} to limit to specific rooms
    msgs = csp.unroll(adapter.subscribe())

    # Print messages locally for debugging
    csp.print("Received:", msgs)

    # Handle different types of messages
    hello_responses = reply_to_hello(msgs)
    dm_responses = handle_dm(msgs)
    help_responses = handle_help(msgs)

    # Publish all responses
    adapter.publish(hello_responses)
    adapter.publish(dm_responses)
    adapter.publish(help_responses)


if __name__ == "__main__":
    print("Starting Symphony bot...")
    print("The bot will run for 2 minutes. Press Ctrl+C to stop earlier.")
    csp.run(graph, realtime=True, endtime=timedelta(minutes=2))
    print("Bot stopped.")
