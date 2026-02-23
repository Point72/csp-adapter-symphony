# Adapter Config

`SymphonyAdapterConfig` requires:

- `app_token`: App Token
- `bot_token`: OAuth Bot Token

An SSL context can be provided optionally in the `ssl` argument.

See [Setup](Setup) for more information.

# Adapter Manager

`SlackAdapterManager` takes a single argument `config`, an instance of `SlackAdapterConfig`.
It provides two methods:

- `subscribe() -> ts[[SlackMessage]]`: Subscribe to messages (`SlackMessage`) from channels in which the Bot is present, and DMs
- `publish(ts[SlackMessage])`: Publish messages (`SlackMessage`)

> [!NOTE]
>
> `subscribe` returns a list of `SlackMessage`, but `publish` takes an individual `SlackMessage`.
> This is for API symmetry with the [csp-adapter-symphony](https://github.com/point72/csp-adapter-symphony).
> `csp.unroll` can be used to unroll the list of `ts[List[SlackMessage]]` into `ts[SlackMessage]`.

```python
from csp_adapter_slack import SlackAdapterConfig, SlackAdapterManager


def graph():
    adapter = SlackAdapterManager(
      config=SlackAdapterConfig(
        app_token=".app_token",
        bot_token=".bot_token",
      ),
    )

    csp.print("All Messages", adapter.subscribe())
```

See [Examples](Examples) for more examples.

# Chat Framework

`csp-chat` is a framework for writing cross-platform, command oriented chat bots.
It will be released in 2025 with initial support for `Slack`, `Symphony`, and `Discord`.
