# csp symphony adapter

A [csp](https://github.com/point72/csp) adapter for [Symphony](https://symphony.com) using the official [Symphony BDK for Python](https://github.com/finos/symphony-bdk-python).

[![Build Status](https://github.com/Point72/csp-adapter-symphony/actions/workflows/build.yaml/badge.svg?branch=main&event=push)](https://github.com/Point72/csp-adapter-symphony/actions/workflows/build.yaml)
[![codecov](https://codecov.io/gh/Point72/csp-adapter-symphony/branch/main/graph/badge.svg)](https://codecov.io/gh/Point72/csp-adapter-symphony)
[![GitHub issues](https://img.shields.io/github/issues/point72/csp-adapter-symphony.svg)](https://github.com/point72/csp-adapter-symphony/issues)
[![License](https://img.shields.io/github/license/Point72/csp-adapter-symphony)](https://github.com/Point72/csp-adapter-symphony)
[![PyPI](https://img.shields.io/pypi/v/csp-adapter-symphony.svg)](https://pypi.python.org/pypi/csp-adapter-symphony)

## Features

The Symphony adapter allows for reading and writing of messages from the [Symphony](https://symphony.com/) message platform using the official [Symphony BDK (Bot Development Kit)](https://github.com/finos/symphony-bdk-python).

Key features:

- **BDK Integration**: Uses the official Symphony BDK for robust and maintainable Symphony integration
- **Direct Messages**: Full support for sending and receiving direct messages (IMs)
- **User Mentions**: Easy-to-use mention utilities for @mentioning users
- **Form Handling**: Support for Symphony Elements (interactive forms)
- **Presence Management**: Set and monitor bot presence status

[More information is available in our wiki](https://github.com/Point72/csp-adapter-symphony/wiki)

## Quick Start

### Configuration

Create a BDK configuration file (`~/.symphony/config.yaml`):

```yaml
host: company.symphony.com

bot:
    username: my-bot
    privateKey:
        path: /path/to/bot-private-key.pem
```

### Basic Example

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

# Load configuration from ~/.symphony/config.yaml
config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")


@csp.node
def reply_to_hello(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Reply to messages containing 'hello'."""
    if "hello" in msg.msg.lower():
        # Reply in the same room, mentioning the user
        return msg.reply(f"Hello {msg.mention()}!", mention_author=False)


@csp.node
def handle_dm(msg: ts[SymphonyMessage]) -> ts[SymphonyMessage]:
    """Handle direct messages."""
    if msg.is_direct_message():
        return msg.reply("Thanks for the DM!")


def graph():
    adapter = SymphonyAdapter(config)

    # Subscribe to messages (unroll to get individual messages)
    msgs = csp.unroll(adapter.subscribe())

    # Process and respond
    responses = reply_to_hello(msgs)
    dm_responses = handle_dm(msgs)

    # Publish responses
    adapter.publish(responses)
    adapter.publish(dm_responses)


if __name__ == "__main__":
    csp.run(graph, realtime=True, endtime=timedelta(hours=8))
```

### Sending Direct Messages

```python
# Send a DM to a specific user
dm = SymphonyMessage.to_user(user_id="12345", msg="Hello via DM!")
adapter.publish(dm)

# Or reply to a message with a DM
dm = incoming_msg.direct_reply("This is a private response")
adapter.publish(dm)
```

### Working with Mentions

```python
from csp_adapter_symphony import mention_user, mention_users, mention_by_id

# Mention by user ID
text = f"Hello {mention_by_id('12345')}!"

# Mention by email
text = f"Hello {mention_user('user@example.com')}!"

# Mention multiple users
text = f"Hello {mention_users(['12345', '67890'])}!"

# Check if a message mentions a specific user
if incoming_msg.mentions_user("12345"):
    # Handle mention...
```

## Chat Framework

[`csp-bot`](https://github.com/Point72/csp-bot) is a framework for writing cross-platform, command oriented chat bots.

## Installation

Install with `pip`:

```bash
pip install csp csp-adapter-symphony
```

Install with `conda`:

```bash
conda install csp csp-adapter-symphony -c conda-forge
```

## Configuration Options

The adapter can be configured in several ways:

### From BDK Config File (Recommended)

```python
# From ~/.symphony directory
config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")

# From any path
config = SymphonyAdapterConfig.from_file("/path/to/config.yaml")
```

### From Individual Parameters

```python
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
    error_room="Error Notifications",  # Optional: room for error messages
    inform_client=True,  # Optional: notify users of send failures
)
```

### Certificate-Based Authentication

For environments using certificate authentication:

```python
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot@domain.com",
    certificate_path="/path/to/combined.pem",  # Combined cert+key file
)
```

### Custom Host Configuration

For deployments with separate API endpoints:

```python
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    pod_host="pod.company.symphony.com",       # Pod API
    agent_host="agent.company.symphony.com",   # Agent API
    session_auth_host="auth.company.symphony.com",  # Session Auth
    key_manager_host="km.company.symphony.com",     # Key Manager
    bot_username="my-bot",
    certificate_path="/path/to/combined.pem",
)
```

### SSL Configuration

```python
# Custom CA certificate
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
    ssl_trust_store_path="/path/to/ca-bundle.pem",
)

# Disable SSL verification (development only!)
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
    ssl_verify=False,
)
```

See the [Setup Guide](https://github.com/Point72/csp-adapter-symphony/wiki/Setup) for detailed configuration options.

## Migration from v0.3.x

Version 0.4.0 introduces the Symphony BDK integration. Key changes:

1. **Dependencies**: `requests` and `tenacity` are replaced by `symphony-bdk-python`
1. **Configuration**: Optionally use `SymphonyAdapterConfig.from_file()` or `from_symphony_dir()` instead of manual URL configuration
1. **Direct Messages**: Now work correctly using `room="IM"` with `user_id`
1. **Message Methods**: New helper methods like `.reply()`, `.direct_reply()`, `.mention()`

## License

This software is licensed under the Apache 2.0 license. See the [LICENSE](https://github.com/Point72/csp-adapter-symphony/blob/main/LICENSE) file for details.
