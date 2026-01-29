# Examples

The following examples demonstrate how to use the Symphony CSP adapter with chatom.

## Basic Echo Bot

A simple bot that echoes messages containing "hello":

```python
from datetime import datetime, timedelta

import csp
from csp import ts

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter, SymphonyMessage


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
)


@csp.node
def echo_hello(messages: ts[[SymphonyMessage]]) -> ts[SymphonyMessage]:
    """Reply when someone says hello."""
    if csp.ticked(messages):
        for msg in messages:
            if "hello" in msg.content.lower():
                return SymphonyMessage(
                    stream_id=msg.stream_id,
                    content=f"Hello back, {msg.author_id}!",
                )


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Subscribe to all messages
    messages = adapter.subscribe()

    # Generate responses
    responses = echo_hello(messages)

    # Publish responses
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(
        my_bot,
        starttime=datetime.now(),
        endtime=timedelta(hours=8),
        realtime=True,
    )
```

## Filtering by Room

Subscribe to messages from specific rooms:

```python
from datetime import datetime, timedelta

import csp

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Subscribe to specific rooms by name or stream ID
    messages = adapter.subscribe(rooms={"Bot Room", "Support"})
    # Or by stream ID
    messages = adapter.subscribe(rooms={"streamId123", "streamId456"})

    # Process messages...
    csp.print("Filtered messages", messages)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Using Mentions

Check for mentions and create mentions in responses:

```python
from datetime import datetime, timedelta

import csp
from csp import ts

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import (
    SymphonyAdapter,
    SymphonyMessage,
    mention_user_by_uid,
    format_hashtag,
)


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)

BOT_USER_ID = "12345"


@csp.node
def handle_mentions(messages: ts[[SymphonyMessage]]) -> ts[SymphonyMessage]:
    """Respond when the bot is mentioned."""
    if csp.ticked(messages):
        for msg in messages:
            if msg.mentions_user(BOT_USER_ID):
                # Mention the user back
                response_content = (
                    f"Hi {mention_user_by_uid(int(msg.author_id))}! "
                    f"You mentioned me. Check out {format_hashtag('help')} for commands."
                )
                return SymphonyMessage(
                    stream_id=msg.stream_id,
                    content=response_content,
                )


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)
    messages = adapter.subscribe()
    responses = handle_mentions(messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Presence Management

Set the bot's presence status:

```python
from datetime import datetime, timedelta

import csp

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter, SymphonyPresenceStatus


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Set presence to available at start
    presence = csp.const(SymphonyPresenceStatus.AVAILABLE)
    adapter.publish_presence(presence)

    # Subscribe and process messages
    messages = adapter.subscribe()
    csp.print("Messages", messages)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Processing Individual Messages

Unroll message batches to process individually:

```python
from datetime import datetime, timedelta

import csp
from csp import ts

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter, SymphonyMessage


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.node
def process_single_message(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Process a single message."""
    if csp.ticked(msg):
        # Respond to commands
        if msg.content.startswith("!ping"):
            return SymphonyMessage(
                stream_id=msg.stream_id,
                content="Pong!",
            )


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Get message batches
    message_batches = adapter.subscribe()

    # Unroll to individual messages
    individual_messages = csp.unroll(message_batches)

    # Process each message
    responses = process_single_message(individual_messages)

    # Publish responses
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Using SymphonyAdapterConfig

Use extended config for adapter-specific options:

```python
from datetime import datetime, timedelta

import csp

from csp_adapter_symphony import SymphonyAdapter, SymphonyAdapterConfig


# Extended config with adapter options
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
    # Adapter-specific options
    error_room="Bot Errors",  # Send errors to this room
    inform_client=True,       # Notify users of send failures
    max_attempts=5,           # Retry attempts
    ssl_verify=True,          # Verify SSL certificates
)


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)
    messages = adapter.subscribe()
    csp.print("Messages", messages)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Certificate-Based Authentication

Use certificate authentication instead of RSA key:

```python
from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot@domain.com",
    bot_certificate_path="/path/to/combined-cert-and-key.pem",
)

adapter = SymphonyAdapter(config)
```

## Accessing the Backend Directly

Access chatom's SymphonyBackend for additional operations:

```python
from datetime import datetime, timedelta

import csp

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Access the underlying backend
    backend = adapter.symphony_backend

    # Use backend methods (sync wrapper)
    # user = backend.sync.fetch_user(email="user@example.com")

    messages = adapter.subscribe()
    csp.print("Messages", messages)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Using the Generic chatom CSP Layer

You can also use chatom's generic CSP layer directly:

```python
from datetime import datetime, timedelta

import csp

from chatom.csp import BackendAdapter
from chatom.symphony import SymphonyBackend, SymphonyConfig


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)

# Create backend directly
backend = SymphonyBackend(config=config)

# Use generic BackendAdapter
adapter = BackendAdapter(backend)


@csp.graph
def my_bot():
    messages = adapter.subscribe()
    csp.print("Messages", messages)
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```

## Combining Multiple Streams

Process messages from different sources:

```python
from datetime import datetime, timedelta

import csp
from csp import ts

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter, SymphonyMessage


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.node
def combine_and_process(
    room_messages: ts[[SymphonyMessage]],
) -> ts[SymphonyMessage]:
    """Process all incoming messages."""
    if csp.ticked(room_messages):
        for msg in room_messages:
            # Log all messages
            print(f"[{msg.stream_id}] {msg.author_id}: {msg.content}")

            # Respond to specific commands
            if msg.content.startswith("!help"):
                return SymphonyMessage(
                    stream_id=msg.stream_id,
                    content="Available commands: !help, !ping, !status",
                )


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Subscribe to all messages
    messages = adapter.subscribe()

    # Process
    responses = combine_and_process(messages)

    # Publish
    adapter.publish(responses)


if __name__ == "__main__":
    csp.run(my_bot, starttime=datetime.now(), endtime=timedelta(hours=8), realtime=True)
```
