# API Reference

## SymphonyAdapter

The main adapter class for Symphony integration with CSP. Wraps chatom's SymphonyBackend.

### Constructor

```python
from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)
adapter = SymphonyAdapter(config)
```

### Properties

| Property           | Type              | Description                   |
| ------------------ | ----------------- | ----------------------------- |
| `config`           | `SymphonyConfig`  | The Symphony configuration    |
| `backend`          | `BackendBase`     | The underlying chatom backend |
| `symphony_backend` | `SymphonyBackend` | The chatom SymphonyBackend    |

### Methods

#### `subscribe(rooms=None, skip_own=True, skip_history=True) -> ts[[SymphonyMessage]]`

Subscribe to Symphony messages.

| Parameter      | Type       | Description                                         |
| -------------- | ---------- | --------------------------------------------------- |
| `rooms`        | `Set[str]` | Rooms to filter by ID or name (optional)            |
| `skip_own`     | `bool`     | Skip messages from the bot itself (default: True)   |
| `skip_history` | `bool`     | Skip messages before stream started (default: True) |

Returns a time series of `SymphonyMessage` lists.

```python
@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)

    # Subscribe to all rooms
    messages = adapter.subscribe()

    # Or filter by room name or ID
    messages = adapter.subscribe(rooms={"Bot Room", "Support"})
    messages = adapter.subscribe(rooms={"abc123def456"})
```

#### `publish(msg: ts[SymphonyMessage])`

Publish messages to Symphony.

| Parameter | Type                  | Description             |
| --------- | --------------------- | ----------------------- |
| `msg`     | `ts[SymphonyMessage]` | Time series of messages |

```python
@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)

    response = csp.const(SymphonyMessage(
        stream_id="stream123",
        content="Hello, World!",
    ))
    adapter.publish(response)
```

#### `publish_presence(presence: ts[SymphonyPresenceStatus], timeout=5.0)`

Publish presence status updates.

| Parameter  | Type                         | Description                     |
| ---------- | ---------------------------- | ------------------------------- |
| `presence` | `ts[SymphonyPresenceStatus]` | Time series of presence values  |
| `timeout`  | `float`                      | API call timeout (default: 5.0) |

```python
from csp_adapter_symphony import SymphonyPresenceStatus

@csp.graph
def my_graph():
    adapter = SymphonyAdapter(config)

    presence = csp.const(SymphonyPresenceStatus.AVAILABLE)
    adapter.publish_presence(presence)
```

______________________________________________________________________

## SymphonyAdapterConfig

Extended configuration class with adapter-specific options. Inherits from chatom's `SymphonyConfig`.

### Constructor Parameters

All parameters from `SymphonyConfig`, plus:

| Parameter              | Type    | Description                                         |
| ---------------------- | ------- | --------------------------------------------------- |
| `error_room`           | `str`   | Room for error notifications (optional)             |
| `inform_client`        | `bool`  | Notify on send failures (default: `False`)          |
| `max_attempts`         | `int`   | Maximum retry attempts (default: `10`)              |
| `initial_interval_ms`  | `int`   | Initial retry interval in ms (default: `500`)       |
| `multiplier`           | `float` | Retry backoff multiplier (default: `2.0`)           |
| `max_interval_ms`      | `int`   | Maximum retry interval in ms (default: `300000`)    |
| `datafeed_version`     | `str`   | Datafeed version `"v1"` or `"v2"` (default: `"v2"`) |
| `ssl_trust_store_path` | `str`   | Path to custom CA certificate bundle                |
| `ssl_verify`           | `bool`  | Verify SSL certificates (default: `True`)           |

### Methods

#### `get_bdk_config() -> BdkConfig`

Get a BdkConfig for use with symphony-bdk-python.

```python
bdk_config = config.get_bdk_config()
```

#### `create_backend() -> SymphonyBackend`

Create a chatom SymphonyBackend from this config.

```python
backend = config.create_backend()
```

______________________________________________________________________

## SymphonyMessage (from chatom)

Pydantic model for Symphony messages.

### Properties

| Property          | Type        | Description                  |
| ----------------- | ----------- | ---------------------------- |
| `id`              | `str`       | Message ID                   |
| `content`         | `str`       | Message content              |
| `author_id`       | `str`       | Author's user ID             |
| `channel_id`      | `str`       | Channel/stream ID            |
| `stream_id`       | `str`       | Symphony stream ID (alias)   |
| `timestamp`       | `datetime`  | Message timestamp            |
| `mentions`        | `List[int]` | List of mentioned user IDs   |
| `mention_ids`     | `List[str]` | Mentions as strings          |
| `has_mentions`    | `bool`      | Whether message has mentions |
| `message_ml`      | `str`       | MessageML content            |
| `presentation_ml` | `str`       | PresentationML content       |
| `data`            | `str`       | JSON data payload            |
| `metadata`        | `dict`      | Additional metadata          |

### Methods

#### `mentions_user(user_id: str) -> bool`

Check if the message mentions a specific user.

```python
if msg.mentions_user("12345"):
    # Handle mention...
```

#### `extract_mentions_from_data(data: str) -> List[int]` (static)

Extract user mentions from message data JSON.

```python
mentions = SymphonyMessage.extract_mentions_from_data(json_data)
```

______________________________________________________________________

## SymphonyPresenceStatus (from chatom)

Enum for Symphony presence status.

| Value           | Description         |
| --------------- | ------------------- |
| `AVAILABLE`     | Available/Online    |
| `BUSY`          | Busy/Do Not Disturb |
| `AWAY`          | Away/Idle           |
| `ON_THE_PHONE`  | On a phone call     |
| `BE_RIGHT_BACK` | Be right back       |
| `IN_A_MEETING`  | In a meeting        |
| `OUT_OF_OFFICE` | Out of office       |
| `OFF_WORK`      | Off work/Offline    |
| `OFFLINE`       | Offline             |

______________________________________________________________________

## Mention Functions (from chatom)

### `mention_user_by_uid(user_id: int) -> str`

Create a mention by user ID.

```python
from csp_adapter_symphony import mention_user_by_uid

text = f"Hello {mention_user_by_uid(12345)}!"
# Result: Hello <mention uid="12345"/>!
```

### `mention_user_by_email(email: str) -> str`

Create a mention by email address.

```python
from csp_adapter_symphony import mention_user_by_email

text = f"Hello {mention_user_by_email('user@example.com')}!"
# Result: Hello <mention email="user@example.com"/>!
```

### `format_hashtag(tag: str) -> str`

Format a hashtag.

```python
from csp_adapter_symphony import format_hashtag

text = f"Check {format_hashtag('important')}!"
# Result: Check <hash tag="important"/>!
```

### `format_cashtag(tag: str) -> str`

Format a cashtag (stock symbol).

```python
from csp_adapter_symphony import format_cashtag

text = f"Stock: {format_cashtag('AAPL')}"
# Result: Stock: <cash tag="AAPL"/>
```

______________________________________________________________________

## SymphonyRoomMapper

Thread-safe mapper for room name/ID resolution.

### Constructor

```python
from csp_adapter_symphony import SymphonyRoomMapper

mapper = SymphonyRoomMapper()
```

### Methods

#### `register_room(room_name: str, room_id: str)`

Register a room name to ID mapping.

```python
mapper.register_room("My Room", "stream123")
```

#### `get_room_id(room_name: str) -> Optional[str]`

Get room ID from name.

```python
room_id = mapper.get_room_id("My Room")
```

#### `get_room_name(room_id: str) -> Optional[str]`

Get room name from ID.

```python
room_name = mapper.get_room_name("stream123")
```

#### `set_im_id(user_identifier: str, stream_id: str)`

Register an IM stream for a user.

```python
mapper.set_im_id("user123", "im-stream-456")
```

______________________________________________________________________

## chatom CSP Layer

The adapter uses chatom's generic CSP layer under the hood.

### BackendAdapter

Generic CSP adapter that works with any chatom backend.

```python
from chatom.csp import BackendAdapter
from chatom.symphony import SymphonyBackend, SymphonyConfig

backend = SymphonyBackend(config=SymphonyConfig(...))
adapter = BackendAdapter(backend)

@csp.graph
def my_graph():
    messages = adapter.subscribe()
    adapter.publish(responses)
```

### message_reader

Low-level function to create a message time series.

```python
from chatom.csp import message_reader

@csp.graph
def my_graph():
    # Filter by channel ID or name
    messages = message_reader(backend, channels={"Bot Room", "stream123"})
```

### message_writer

Low-level node to write messages.

```python
from chatom.csp import message_writer

@csp.graph
def my_graph():
    message_writer(backend, messages=response_ts)
```
