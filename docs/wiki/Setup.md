This guide will help you setup a new Symphony application.

> [!TIP]
> Find relevant docs with GitHub’s search function, use `repo:Point72/csp-adapter-symphony type:wiki <search terms>` to search the documentation Wiki Pages.

# Symphony Configuration

Follow [the documentation for creating a Certificate Authentication Workflow-based bot](https://docs.developers.symphony.com/bots/authentication/certificate-authentication).

Take note of:

- The Bot's name
- The Bot's Key and Certificate

# Managing Key/Certificate

You should have an `key` and a `cert` from the above steps.

These can be configured directly on the `SymphonyAdapterConfig`:

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(key="BEGIN PRIVATE KEY...", cert="BEGIN CERTIFICATE...")
```

Alternatively, these could be stored in local files and the configuration will read them:

**.gitignore**

```raw
.key
.cert
```

**.key**

```raw
BEGIN PRIVATE KEY
...
```

**.cert**

```raw
BEGIN CERTIFICATE
...
```

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(key=".key", cert=".cert")
```

# Symphony Routes

Symphony is hosted per-deployment.
As such, it can be can be configured in a variety of ways at a variety of URLs.

`SymphonyAdapterConfig` allows for configuration of all the required routes via arguments. Note that some of them are format strings, and thus expect Python format string style placeholders.

- `auth_host`: Authentication host, like `company-api.symphony.com`
- `session_auth_path`: Path to authenticate session, like `/sessionauth/v1/authenticate`
- `key_auth_path`: Path to authenticate key, like `/keyauth/v1/authenticate`
- `message_create_url`: Format-string path to create a message, like `https://SYMPHONY_HOST/agent/v4/stream/{{sid}}/message/create`
- `presence_url`: String path to set presence information, like `https://SYMPHONY_HOST/pod/v2/user/presence`
- `datafeed_create_url`: String path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds`
- `datafeed_delete_url`: Format-string path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds/{{datafeed_id}}`
- `datafeed_read_url`: Format-string path to create datafeed, like `https://SYMPHONY_HOST/agent/v5/datafeeds/{{datafeed_id}}/read`
- `room_search_url`: Format-string path to create datafeed, like `https://SYMPHONY_HOST/pod/v3/room/search`
- `room_info_url`: Format-string path to create datafeed, like `https://SYMPHONY_HOST/pod/v3/room/{{room_id}}/info`
- `room_members_url`: (Optional) Format-string path to get room members in a room, like `https://SYMPHONY_HOST/pod/v2/room/{{room_id}}/membership/list`

# Extra Configuration

The `SymphonyAdapterConfig` has a few extra features that can be adjusted as needed:

- `error_room`: (Optional) A room to direct error messages to, if a message fails to be sent over symphony, or if the adapter crashes
- `inform_client`: Whether to inform the intended recipient of a failed message that the message failed
- `max_attempts`: Max attempts for datafeed and message post requests before raising exception. If -1, no maximum
- `initial_interval_ms`: Initial interval to wait between attempts, in milliseconds
- `multiplier`: Multiplier between attempt delays for exponential backoff
- `max_interval_ms`: maximum delay between retry attempts, in milliseconds
