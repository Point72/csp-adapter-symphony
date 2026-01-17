# Examples

The following examples demonstrate how to use the Symphony adapter with CSP.

## Basic Hello Bot

A simple bot that replies "Hello!" when someone says hello:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

# Load configuration from ~/.symphony/config.yaml
config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def reply_to_hello(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Reply when someone says hello."""
    if "hello" in msg.msg.lower():
        return msg.reply(f"Hello {msg.mention()}!")


def graph():
    adapter = SymphonyAdapter(config)

    # Subscribe to all messages
    messages = csp.unroll(adapter.subscribe())

    # Log incoming messages
    csp.print("Received", messages)

    # Generate and publish responses
    responses = reply_to_hello(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Direct Message Handler

Handle direct messages differently from room messages:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def handle_message(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Handle DMs and room messages differently."""
    if msg.is_direct_message():
        # Respond to DMs
        return msg.reply("Thanks for the DM! How can I help?")
    elif "help" in msg.msg.lower():
        # Send help privately
        return msg.direct_reply("Here's some help information...")


def graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())
    responses = handle_message(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Sending to Specific Users

Send direct messages to specific users:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def notify_admins(msg: ts[SymphonyMessage]) -> ts[[SymphonyMessage]]:
    """Notify admin users when certain keywords are detected."""
    ADMIN_IDS = ["12345", "67890"]

    if "urgent" in msg.msg.lower():
        # Send DM to each admin
        return [
            SymphonyMessage.to_user(admin_id, f"Urgent message from {msg.user}: {msg.msg}")
            for admin_id in ADMIN_IDS
        ]
    return []


def graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())
    notifications = csp.unroll(notify_admins(messages))
    adapter.publish(notifications)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Working with Mentions

Handle messages that mention the bot:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
    mention_user,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")

BOT_USER_ID = "your-bot-user-id"


@csp.node
def handle_mentions(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Only respond when the bot is mentioned."""
    if msg.mentions_user(BOT_USER_ID):
        # Bot was mentioned
        mentioned_users = msg.get_mentioned_users()
        other_mentions = [u for u in mentioned_users if u != BOT_USER_ID]

        if other_mentions:
            # Someone else was also mentioned
            mentions_text = " ".join(mention_user(u) for u in other_mentions)
            return msg.reply(f"I see you mentioned {mentions_text} too!")
        else:
            return msg.reply("You called? How can I help?")


def graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())
    responses = handle_mentions(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Form Handling (Symphony Elements)

Handle form submissions:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def handle_forms(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Handle form submissions."""
    if msg.is_form_submission():
        if msg.form_id == "feedback_form":
            rating = msg.get_form_value("rating", "not provided")
            comments = msg.get_form_value("comments", "none")
            return msg.reply(f"Thanks for your feedback! Rating: {rating}")
        elif msg.form_id == "request_form":
            request_type = msg.get_form_value("type")
            return msg.reply(f"Processing your {request_type} request...")


def graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())
    responses = handle_forms(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Setting Bot Presence

Update the bot's presence status:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    Presence,
    SymphonyAdapter,
    SymphonyAdapterConfig,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


def graph():
    adapter = SymphonyAdapter(config)

    # Set initial presence
    initial_presence = csp.const(Presence.AVAILABLE)
    adapter.publish_presence(initial_presence)

    # Could also change presence based on conditions
    # adapter.publish_presence(presence_updates)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Subscribing to Specific Rooms

Listen to only specific rooms:

```python
from datetime import timedelta

import csp
from csp import ts

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def echo(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Echo messages back."""
    return msg.reply(f"Echo: {msg.msg}")


def graph():
    adapter = SymphonyAdapter(config)

    # Only subscribe to specific rooms
    rooms_to_monitor = {"General", "Support", "Engineering"}
    messages = csp.unroll(adapter.subscribe(rooms=rooms_to_monitor))

    # Exit message when shutting down
    # adapter.subscribe(rooms=rooms_to_monitor, exit_msg="Bot is shutting down...")

    responses = echo(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Error Handling with Error Room

Configure error notifications to a dedicated room:

```python
from datetime import timedelta

import csp

from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyAdapterConfig,
    SymphonyMessage,
)

# Configure with error room
config = SymphonyAdapterConfig.from_symphony_dir(
    "config.yaml",
    error_room="Bot Error Notifications",
    inform_client=True,  # Notify users when messages fail
)


def graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())

    # If message sending fails, errors go to "Bot Error Notifications" room
    adapter.publish(messages)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

## Using with csp-bot Framework

For more complex chatbot functionality, see the [`csp-bot`](https://github.com/Point72/csp-bot) framework which provides:

- Command routing and parsing
- Cross-platform support (Symphony, Slack, Discord)
- Middleware and plugins
- State management
