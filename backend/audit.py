"""Append-only audit trail of agent-loop activity -> output/audit_trail.json.

One entry per chat turn: when it ran, which tools the agent called with short
args/results, validator retries, token usage, and why the loop stopped.

The file is a JSON array that only ever grows. Each append reads the array, adds
one entry, and atomically replaces the file (write temp + rename), so a crash can't
leave half-written JSON. Existing entries are never edited or removed. If the file
is ever unreadable, it is moved aside (never deleted) and a new array is started.
"""

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_FIELD_CHARS = 200
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
CARD_RE = re.compile(r"\b(?:\d[ -]?){12,19}\b")  # card-like digit runs
_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def short(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    """Compact, redacted string for the log: JSON-ish, emails masked, truncated."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    text = value if isinstance(value, str) else json.dumps(value, default=str, separators=(",", ":"))
    text = CARD_RE.sub("<card-number>", EMAIL_RE.sub("<email>", text))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def steps_from_messages(messages: list[ModelMessage]) -> list[dict]:
    """Flatten this turn's messages into an ordered list of loop steps."""
    steps: list[dict] = []
    for m in messages:
        if isinstance(m, ModelResponse):
            ts = m.timestamp.isoformat(timespec="milliseconds") if m.timestamp else None
            calls = [p for p in m.parts if isinstance(p, ToolCallPart)]
            steps.append({"time": ts, "type": "model_response", "tool_calls": len(calls),
                          "finish_reason": m.finish_reason})
            for p in calls:
                steps.append({"time": ts, "type": "tool_call", "tool": p.tool_name, "args": short(p.args)})
        elif isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, ToolReturnPart):
                    steps.append({"time": p.timestamp.isoformat(timespec="milliseconds"), "type": "tool_result",
                                  "tool": p.tool_name, "result": short(p.content)})
                elif isinstance(p, RetryPromptPart):
                    steps.append({"time": p.timestamp.isoformat(timespec="milliseconds"), "type": "retry",
                                  "tool": p.tool_name, "reason": short(p.content)})
    return steps


def append(entry: dict) -> None:
    """Append one entry. Never truncates or rewrites existing entries."""
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries: list = []
        if AUDIT_PATH.exists():
            try:
                loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
                entries = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                # Preserve the unreadable file rather than overwrite it.
                AUDIT_PATH.rename(AUDIT_PATH.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
        entries.append(entry)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(AUDIT_PATH)


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]
