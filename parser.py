"""
parser.py - Message file loader.
Reads messages.txt and returns a list of dicts.
No facts are hardcoded here.
"""
from __future__ import annotations
import re
from pathlib import Path

_REQUIRED = {"MSG_ID", "FROM", "DATE", "TEXT"}
_FIELD_LINE = re.compile(r"^(MSG_ID|FROM|DATE|TEXT):\s*(.*)")


def load_messages(path: str = "messages.txt") -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    messages: list[dict] = []
    current: dict[str, list[str]] = {}
    current_key: str | None = None

    for line in text.splitlines():
        m = _FIELD_LINE.match(line)
        if m:
            current_key = m.group(1)
            current.setdefault(current_key, [])
            value = m.group(2).strip()
            if value:
                current[current_key].append(value)
        elif line.strip() == "":
            if current:
                _flush(current, messages)
                current = {}
                current_key = None
        else:
            if current_key and current_key in current:
                current[current_key].append(line.rstrip())

    if current:
        _flush(current, messages)

    return messages


def _flush(raw: dict[str, list[str]], out: list[dict]) -> None:
    missing = _REQUIRED - raw.keys()
    if missing:
        raise ValueError(f"Message block missing fields: {missing}")
    out.append({
        "id":   " ".join(raw["MSG_ID"]).strip(),
        "from": " ".join(raw["FROM"]).strip(),
        "date": " ".join(raw["DATE"]).strip(),
        "text": " ".join(raw["TEXT"]).strip(),
    })


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "messages.txt"
    msgs = load_messages(path)
    print(f"Loaded {len(msgs)} messages\n")
    for msg in msgs:
        print(json.dumps(msg, ensure_ascii=False, indent=2))