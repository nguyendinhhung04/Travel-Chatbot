"""UTF-8 terminal diagnostics for data sent to Gemini."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any


def print_gemini_request(
    stage: str,
    messages: Sequence[Any],
    *,
    response_schema: dict[str, Any] | None = None,
) -> None:
    """Print the full Gemini input content without credentials or HTTP headers."""
    payload: dict[str, Any] = {
        "stage": stage,
        "messages": [
            {
                "type": getattr(message, "type", type(message).__name__),
                "content": getattr(message, "content", None),
            }
            for message in messages
        ],
    }
    if response_schema is not None:
        payload["responseSchema"] = response_schema

    request_json = json.dumps(payload, ensure_ascii=False, indent=2)
    output = f"Gemini request data:\n{request_json}\n"
    stdout_buffer = getattr(sys.stdout, "buffer", None)
    if stdout_buffer is not None:
        stdout_buffer.write(output.encode("utf-8"))
        stdout_buffer.flush()
        return
    print(output, end="", flush=True)


__all__ = ["print_gemini_request"]
