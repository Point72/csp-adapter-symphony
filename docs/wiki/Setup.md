# Symphony Bot Setup

This guide will help you set up a new Symphony bot application using the Symphony BDK.

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

## Authentication Methods

The adapter supports two authentication methods:

### RSA Private Key Authentication

The most common method. You provide an RSA private key file.

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
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
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot@domain.com",
    certificate_path="/path/to/combined.pem",
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

## BDK Configuration

The adapter uses the Symphony BDK for Python, which requires a YAML or JSON configuration file.

### Basic Configuration

Create a configuration file at `~/.symphony/config.yaml`:

```yaml
host: company.symphony.com

bot:
    username: my-bot-username
    privateKey:
        path: /path/to/bot-private-key.pem
```

### Configuration with Environment-Specific Settings

For more complex setups:

```yaml
scheme: https
host: company.symphony.com
port: 443

bot:
    username: my-bot-username
    privateKey:
        path: /path/to/bot-private-key.pem

datafeed:
    version: v2  # Recommended
    retry:
        maxAttempts: 6
        initialIntervalMillis: 2000
        multiplier: 1.5
        maxIntervalMillis: 10000

retry:
    maxAttempts: 6
    initialIntervalMillis: 2000
    multiplier: 1.5
    maxIntervalMillis: 10000
```

### Private Key Options

You can specify the private key in several ways:

**From a file path:**

```yaml
bot:
    username: my-bot
    privateKey:
        path: /path/to/private-key.pem
```

**Inline content (useful for secrets management):**

```yaml
bot:
    username: my-bot
    privateKey:
        content: |
            -----BEGIN RSA PRIVATE KEY-----
            MIIEowIBAAKCAQEA...
            -----END RSA PRIVATE KEY-----
```

## Loading Configuration in Python

### From ~/.symphony directory (Recommended)

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig.from_symphony_dir("config.yaml")
```

### From any file path

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig.from_file("/path/to/config.yaml")
```

### From individual parameters

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
)
```

### From an existing BdkConfig

```python
from symphony.bdk.core.config.loader import BdkConfigLoader
from csp_adapter_symphony import SymphonyAdapterConfig

bdk_config = BdkConfigLoader.load_from_symphony_dir("config.yaml")
config = SymphonyAdapterConfig.from_bdk_config(bdk_config)
```

## Additional Configuration Options

The `SymphonyAdapterConfig` supports additional options beyond BDK configuration:

| Option                | Type    | Default  | Description                           |
| --------------------- | ------- | -------- | ------------------------------------- |
| `error_room`          | `str`   | `None`   | Room name for error notifications     |
| `inform_client`       | `bool`  | `False`  | Notify users when message send fails  |
| `max_attempts`        | `int`   | `10`     | Max retry attempts (-1 for unlimited) |
| `initial_interval_ms` | `int`   | `500`    | Initial retry interval in ms          |
| `multiplier`          | `float` | `2.0`    | Retry backoff multiplier              |
| `max_interval_ms`     | `int`   | `300000` | Maximum retry interval in ms          |
| `datafeed_version`    | `str`   | `"v2"`   | Datafeed version ("v1" or "v2")       |

Example:

```python
config = SymphonyAdapterConfig.from_symphony_dir(
    "config.yaml",
    error_room="Bot Error Notifications",
    inform_client=True,
    max_attempts=20,
)
```

## Custom Host Configuration

Some Symphony deployments use different hosts for different API endpoints. For example:

- Pod API: `pod.company.symphony.com`
- Agent API: `agent.company.symphony.com`
- Session Auth: `auth.company.symphony.com`
- Key Manager: `km.company.symphony.com`

You can configure each endpoint separately:

### In Python

```python
from csp_adapter_symphony import SymphonyAdapterConfig

config = SymphonyAdapterConfig(
    host="company.symphony.com",           # Default/fallback host
    pod_host="pod.company.symphony.com",   # Pod API host
    agent_host="agent.company.symphony.com",  # Agent API host
    session_auth_host="auth.company.symphony.com",  # Session Auth host
    key_manager_host="km.company.symphony.com",     # Key Manager host
    bot_username="my-bot",
    certificate_path="/path/to/combined.pem",
)
```

### In YAML Configuration

```yaml
host: company.symphony.com

pod:
    host: pod.company.symphony.com
agent:
    host: agent.company.symphony.com
sessionAuth:
    host: auth.company.symphony.com
keyManager:
    host: km.company.symphony.com

bot:
    username: my-bot
    certificate:
        path: /path/to/combined.pem
```

> [!NOTE]
> If only `host` is specified, all endpoints will use that host. Use the separate host options only when your Symphony environment requires different endpoints.

## SSL Configuration

### Custom CA Certificate

If your Symphony environment uses a custom or self-signed certificate, specify the CA certificate bundle:

```python
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
    ssl_trust_store_path="/path/to/ca-bundle.pem",
)
```

### Disabling SSL Verification

> [!WARNING]
> Disabling SSL verification is **not recommended** for production use. Only use this for development or testing environments.

```python
config = SymphonyAdapterConfig(
    host="company.symphony.com",
    bot_username="my-bot",
    private_key_path="/path/to/private-key.pem",
    ssl_verify=False,  # Disables SSL certificate verification
)
```

## Next Steps

- See [Examples](Examples) for usage examples
- See [API Reference](API-Reference) for detailed API documentation
