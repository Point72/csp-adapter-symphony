# Symphony Bot Setup

This guide will help you set up a Symphony bot application using csp-adapter-symphony.

> [!TIP]
> Find relevant docs with GitHub's search function, use `repo:Point72/csp-adapter-symphony type:wiki <search terms>` to search the documentation Wiki Pages.

## Prerequisites

- A Symphony environment with admin access
- Python 3.10 or higher
- Authentication credentials (RSA key pair OR certificate)

## Creating a Bot Account

Follow [the documentation for creating an RSA Authentication bot](https://docs.developers.symphony.com/bots/authentication/rsa-authentication).

Take note of:

- The Bot's username
- The Bot's RSA private key (`.pem` file) OR certificate file

## Basic Configuration

The adapter uses chatom's `SymphonyConfig` for connection settings:

```python
from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
)

adapter = SymphonyAdapter(config)
```

## Authentication Methods

### RSA Private Key Authentication

The most common method. You provide an RSA private key file.

```python
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
)
```

### Private Key Content (Inline)

For secrets management, you can provide the private key content directly:

```python
from pydantic import SecretStr
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_content=SecretStr("""-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""),
)
```

### Certificate-Based Authentication

Some Symphony environments require certificate-based authentication. This typically uses a combined certificate and private key file (also called a combined PEM file).

A combined PEM file contains both the certificate and private key:

```
-----BEGIN CERTIFICATE-----
MIIDxTCCAq2gAwIBAgIQAq...
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----
```

To use certificate authentication:

```python
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot@domain.com",
    bot_certificate_path="/path/to/combined.pem",
)
```

**Creating a combined PEM file:**

If you have separate certificate and key files, combine them:

```bash
cat certificate.crt private-key.pem > combined.pem
```

Or if you have a PKCS#12 (.p12) file:

```bash
openssl pkcs12 -in certificate.p12 -out combined.pem -nodes
```

## Extended Configuration (SymphonyAdapterConfig)

For adapter-specific options, use `SymphonyAdapterConfig` which extends chatom's `SymphonyConfig`:

```python
from csp_adapter_symphony import SymphonyAdapter, SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
    # Adapter-specific options
    error_room="Bot Errors",
    inform_client=True,
    max_attempts=5,
)

adapter = SymphonyAdapter(config)
```

### Adapter-Specific Options

| Option                | Type    | Default  | Description                           |
| --------------------- | ------- | -------- | ------------------------------------- |
| `error_room`          | `str`   | `None`   | Room name for error notifications     |
| `inform_client`       | `bool`  | `False`  | Notify users when message send fails  |
| `max_attempts`        | `int`   | `10`     | Max retry attempts (-1 for unlimited) |
| `initial_interval_ms` | `int`   | `500`    | Initial retry interval in ms          |
| `multiplier`          | `float` | `2.0`    | Retry backoff multiplier              |
| `max_interval_ms`     | `int`   | `300000` | Maximum retry interval in ms          |
| `datafeed_version`    | `str`   | `"v2"`   | Datafeed version ("v1" or "v2")       |
| `ssl_verify`          | `bool`  | `True`   | Whether to verify SSL certificates    |

## Custom Host Configuration

Some Symphony deployments use different hosts for different API endpoints. For example:

- Pod API: `pod.company.symphony.com`
- Agent API: `agent.company.symphony.com`
- Session Auth: `auth.company.symphony.com`
- Key Manager: `km.company.symphony.com`

You can configure each endpoint separately:

```python
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",           # Default/fallback host
    pod_host="pod.company.symphony.com",   # Pod API host
    agent_host="agent.company.symphony.com",  # Agent API host
    session_auth_host="auth.company.symphony.com",  # Session Auth host
    key_manager_host="km.company.symphony.com",     # Key Manager host
    bot_username="my-bot",
    bot_certificate_path="/path/to/combined.pem",
)
```

> [!NOTE]
> If only `host` is specified, all endpoints will use that host. Use the separate host options only when your Symphony environment requires different endpoints.

## SSL Configuration

### Custom CA Certificate

If your Symphony environment uses a custom or self-signed certificate, specify the CA certificate bundle:

```python
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
    trust_store_path="/path/to/ca-bundle.pem",
)
```

### Disabling SSL Verification

> [!WARNING]
> Disabling SSL verification is **not recommended** for production use. Only use this for development or testing environments.

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
    ssl_verify=False,  # Disables SSL certificate verification
)
```

## Proxy Configuration

To connect through a proxy:

```python
from pydantic import SecretStr
from chatom.symphony import SymphonyConfig

config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/private-key.pem",
    proxy_host="proxy.company.com",
    proxy_port=8080,
    proxy_username="proxy-user",
    proxy_password=SecretStr("proxy-password"),
)
```

## Using the Adapter

Once configured, create the adapter and use it in a CSP graph:

```python
from datetime import datetime, timedelta

import csp

from chatom.symphony import SymphonyConfig
from csp_adapter_symphony import SymphonyAdapter, SymphonyMessage


config = SymphonyConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    bot_private_key_path="/path/to/key.pem",
)


@csp.graph
def my_bot():
    adapter = SymphonyAdapter(config)

    # Subscribe to messages
    messages = adapter.subscribe()

    # Process messages...
    csp.print("Received", messages)


if __name__ == "__main__":
    csp.run(
        my_bot,
        starttime=datetime.now(),
        endtime=timedelta(hours=8),
        realtime=True,
    )
```

## Configuration Summary

| Config Class                                 | Use Case                                                    |
| -------------------------------------------- | ----------------------------------------------------------- |
| `chatom.symphony.SymphonyConfig`             | Basic connection settings (host, auth, proxy)               |
| `csp_adapter_symphony.SymphonyAdapterConfig` | Extended with CSP adapter options (retries, error handling) |

Both config classes work with `SymphonyAdapter`. Use `SymphonyAdapterConfig` when you need the extended options.

## Next Steps

- See [Examples](Examples) for usage examples
- See [API Reference](API-Reference) for detailed API documentation
