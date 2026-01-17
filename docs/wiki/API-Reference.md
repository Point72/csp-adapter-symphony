# API Reference

## SymphonyAdapterConfig

Configuration class for the Symphony adapter.

### Class Methods

#### `from_file(config_path, **kwargs)`

Create a config from a BDK configuration file.

```python
config = SymphonyAdapterConfig.from_file("/path/to/config.yaml")
```

#### `from_symphony_dir(relative_path="config.yaml", **kwargs)`

Create a config from a file in `~/.symphony` directory.

```python
config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")
```

#### `from_bdk_config(bdk_config, **kwargs)`

Create a config from an existing BdkConfig object.

```python
from symphony.bdk.core.config.loader import BdkConfigLoader
bdk_config = BdkConfigLoader.load_from_file("/path/to/config.yaml")
config = SymphonyAdapterConfig.from_bdk_config(bdk_config)
```

### Constructor Parameters

| Parameter              | Type    | Description                                                    |
| ---------------------- | ------- | -------------------------------------------------------------- |
| `host`                 | `str`   | Base Symphony host (e.g., `company.symphony.com`)              |
| `bot_username`         | `str`   | The bot's username from Symphony admin console                 |
| `private_key_path`     | `str`   | Path to RSA private key file                                   |
| `private_key_content`  | `str`   | RSA private key content (alternative to path)                  |
| `certificate_path`     | `str`   | Path to certificate file for cert-based auth                   |
| `certificate_content`  | `str`   | Certificate content (alternative to path)                      |
| `pod_host`             | `str`   | Host for Pod API (if different from main host)                 |
| `agent_host`           | `str`   | Host for Agent API (if different from main host)               |
| `session_auth_host`    | `str`   | Host for Session Auth API (if different from main host)        |
| `key_manager_host`     | `str`   | Host for Key Manager API (if different from main host)         |
| `ssl_trust_store_path` | `str`   | Path to custom CA certificate bundle                           |
| `ssl_verify`           | `bool`  | Whether to verify SSL certificates (default: `True`)           |
| `error_room`           | `str`   | Room for error notifications                                   |
| `inform_client`        | `bool`  | Whether to notify on send failures (default: `False`)          |
| `max_attempts`         | `int`   | Maximum retry attempts (default: `10`, use `-1` for unlimited) |
| `initial_interval_ms`  | `int`   | Initial retry interval in ms (default: `500`)                  |
| `multiplier`           | `float` | Retry backoff multiplier (default: `2.0`)                      |
| `max_interval_ms`      | `int`   | Maximum retry interval in ms (default: `300000`)               |
| `datafeed_version`     | `str`   | Datafeed version `"v1"` or `"v2"` (default: `"v2"`)            |

### Properties

| Property        | Type        | Description                        |
| --------------- | ----------- | ---------------------------------- |
| `bdk_config`    | `BdkConfig` | The underlying BDK configuration   |
| `error_room`    | `str`       | Room for error notifications       |
| `inform_client` | `bool`      | Whether to notify on send failures |
| `max_attempts`  | `int`       | Maximum retry attempts             |

______________________________________________________________________

## SymphonyAdapter

The main adapter class for Symphony integration with CSP.

### Constructor

```python
adapter = SymphonyAdapter(config: SymphonyAdapterConfig)
```

### Methods

#### `subscribe(rooms=None, exit_msg="") -> ts[[SymphonyMessage]]`

Subscribe to Symphony messages.

| Parameter  | Type       | Description                           |
| ---------- | ---------- | ------------------------------------- |
| `rooms`    | `Set[str]` | Room names to listen to (empty = all) |
| `exit_msg` | `str`      | Message to send on shutdown           |

Returns a time series of `SymphonyMessage` lists.

```python
@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)
    messages = csp.unroll(adapter.subscribe())
    csp.print("msg", messages)
```

#### `publish(msg: ts[SymphonyMessage])`

Publish messages to Symphony.

```python
@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)
    # ... create response messages ...
    adapter.publish(responses)
```

#### `publish_presence(presence: ts[Presence], timeout=5.0)`

Publish bot presence status updates.

```python
@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)
    presence = csp.const(Presence.AVAILABLE)
    adapter.publish_presence(presence)
```

______________________________________________________________________

## SymphonyMessage

A struct representing Symphony messages.

### Fields

| Field         | Type        | Description                   |
| ------------- | ----------- | ----------------------------- |
| `user`        | `str`       | Display name of the author    |
| `user_email`  | `str`       | Email of the author           |
| `user_id`     | `str`       | User ID of the author         |
| `tags`        | `List[str]` | User IDs mentioned in message |
| `room`        | `str`       | Room name, "IM", or stream ID |
| `msg`         | `str`       | Message content               |
| `form_id`     | `str`       | Form ID for Elements actions  |
| `form_values` | `dict`      | Form field values             |
| `stream_id`   | `str`       | Symphony stream ID            |

### Instance Methods

#### `mention(use_email=False) -> str`

Create a mention tag for the message author.

```python
msg.mention()  # '<mention uid="12345" />'
msg.mention(use_email=True)  # '<mention email="user@example.com" />'
```

#### `reply(text, mention_author=False) -> SymphonyMessage`

Create a reply to this message in the same room.

```python
reply = incoming.reply("Thanks!")
reply = incoming.reply("Thanks!", mention_author=True)
```

#### `direct_reply(text) -> SymphonyMessage`

Create a direct message reply to the author.

```python
dm = incoming.direct_reply("Private response")
```

#### `is_direct_message() -> bool`

Check if this is a direct message.

```python
if msg.is_direct_message():
    # Handle DM...
```

#### `mentions_user(user_id) -> bool`

Check if a user is mentioned.

```python
if msg.mentions_user("12345"):
    # Handle mention...
```

#### `get_mentioned_users() -> List[str]`

Get list of mentioned user IDs.

#### `is_form_submission() -> bool`

Check if this is a form submission.

#### `get_form_value(key, default=None)`

Get a form field value.

### Class Methods

#### `to_room(room, msg) -> SymphonyMessage`

Create a message to a room.

```python
msg = SymphonyMessage.to_room("General", "Hello!")
```

#### `to_user(user_id, msg) -> SymphonyMessage`

Create a direct message to a user.

```python
msg = SymphonyMessage.to_user("12345", "Hello!")
```

#### `to_stream(stream_id, msg) -> SymphonyMessage`

Create a message to a specific stream.

```python
msg = SymphonyMessage.to_stream("abc123def456", "Hello!")
```

______________________________________________________________________

## Presence

Enum for bot presence status.

| Value           | Description          |
| --------------- | -------------------- |
| `AVAILABLE`     | Online and available |
| `BUSY`          | Busy                 |
| `AWAY`          | Away from keyboard   |
| `ON_THE_PHONE`  | On a call            |
| `BE_RIGHT_BACK` | Will return shortly  |
| `IN_A_MEETING`  | In a meeting         |
| `OUT_OF_OFFICE` | Out of office        |
| `OFF_WORK`      | Off work             |

______________________________________________________________________

## Mention Functions

### `mention_user(email_or_userid) -> str`

Create a mention tag from email or user ID.

```python
mention_user("12345")  # '<mention uid="12345" />'
mention_user("user@example.com")  # '<mention email="user@example.com" />'
```

### `mention_by_id(user_id) -> str`

Create a mention tag by user ID.

```python
mention_by_id(12345)  # '<mention uid="12345" />'
```

### `mention_by_email(email) -> str`

Create a mention tag by email.

```python
mention_by_email("user@example.com")  # '<mention email="user@example.com" />'
```

### `mention_users(identifiers, separator=" ") -> str`

Create mention tags for multiple users.

```python
mention_users(["12345", "67890"])  # '<mention uid="12345" /> <mention uid="67890" />'
```

### `extract_mentions_from_text(text) -> List[str]`

Extract user IDs from mention tags in text.

```python
extract_mentions_from_text('<mention uid="12345" />')  # ['12345']
```

### `is_bot_mentioned(text, bot_id) -> bool`

Check if a bot is mentioned in text.

```python
is_bot_mentioned('<mention uid="12345" />', "12345")  # True
```

______________________________________________________________________

## Utility Functions

### `format_with_message_ml(text, to_message_ml=True) -> str`

Convert text to/from MessageML format (escaping special characters).

```python
format_with_message_ml("a < b")  # "a &lt; b"
format_with_message_ml("a &lt; b", to_message_ml=False)  # "a < b"
```

______________________________________________________________________

## SymphonyRoomMapper

Thread-safe mapper for room names and IDs.

### Methods

#### `register_room(room_name, room_id)`

Manually register a room name/ID mapping.

#### `get_room_id(room_name) -> Optional[str]`

Get room ID from name (from cache).

#### `get_room_name(room_id) -> Optional[str]`

Get room name from ID (from cache).

#### `set_im_id(user_identifier, stream_id)`

Register an IM stream for a user.
