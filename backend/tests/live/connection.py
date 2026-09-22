"""Live API clients that do not hang up on themselves.

The SDK hands the websocket library its default 20 second ping timeout, and the
Live API does not reliably pong inside that window, so a perfectly healthy
connection gets killed after a minute or two. Measured: the default dies around
90-130s, while one connection with the timeout off ran for 391s.

This only affects clients built on the Python websockets library. The browser
does its own keepalive and gives no such knob, so the product path is unaffected
and does not need this.
"""

from typing import Any

from google import genai


def live_client(**kwargs: Any) -> genai.Client:
    client = genai.Client(**kwargs)
    options = getattr(getattr(client, "_api_client", None), "_websocket_ssl_ctx", None)
    if isinstance(options, dict):
        # Forwarded straight into websockets.connect as keyword arguments.
        options["ping_timeout"] = None
    return client
