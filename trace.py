from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

VALID_AREAS = {"reading", "venue", "schedule", "food", "judging", "budget"}

@dataclass
class TraceEntry:
    call_num: int
    model: str
    area: str
    input_text: str
    output_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class RejectedMessage:
    msg_id: str
    sender: str
    text: str
    reason: str

class Tracer:
    def __init__(self):
        self.entries: list[TraceEntry] = []
        self.rejected: list[RejectedMessage] = []
        self._call_count = 0

    def log(self, model, area, input_text, output_text, prompt_tokens, completion_tokens):
        assert area in VALID_AREAS, f"Invalid area tag: {area}"
        self._call_count += 1
        entry = TraceEntry(self._call_count, model, area, input_text, output_text,
                           prompt_tokens, completion_tokens, prompt_tokens + completion_tokens)
        self.entries.append(entry)
        return entry

    def reject(self, msg_id, sender, text, reason):
        self.rejected.append(RejectedMessage(msg_id, sender, text, reason))

    def total_tokens(self):
        return sum(e.total_tokens for e in self.entries)

    def print_trace(self):
        sep = "-" * 70
        print("\n" + "=" * 70)
        print("EXECUTION TRACE")
        print("=" * 70)
        for e in self.entries:
            print(f"\n[Call {e.call_num}] model={e.model} | area={e.area}")
            print(f"  tokens: prompt={e.prompt_tokens} completion={e.completion_tokens} total={e.total_tokens}")
            inp = e.input_text.replace("\n", " ")
            print(f"  INPUT : {inp[:200]}{'...' if len(inp)>200 else ''}")
            out = e.output_text.replace("\n", " ")
            print(f"  OUTPUT: {out[:300]}{'...' if len(out)>300 else ''}")
            print(sep)
        if self.rejected:
            print("\nREJECTED MESSAGES")
            print("=" * 70)
            for r in self.rejected:
                print(f"  [MSG {r.msg_id}] FROM: {r.sender}")
                print(f"  TEXT  : {r.text[:150]}")
                print(f"  REASON: {r.reason}")
                print(sep)
        print(f"\nTOTAL TOKENS USED: {self.total_tokens()}")
        print(f"TOTAL MODEL CALLS: {len(self.entries)}")
        print("=" * 70 + "\n")

    def to_dict(self):
        return {
            "calls": [{"call_num": e.call_num, "model": e.model, "area": e.area,
                        "prompt_tokens": e.prompt_tokens, "completion_tokens": e.completion_tokens,
                        "total_tokens": e.total_tokens, "input": e.input_text, "output": e.output_text}
                       for e in self.entries],
            "rejected": [{"msg_id": r.msg_id, "sender": r.sender, "text": r.text, "reason": r.reason}
                          for r in self.rejected],
            "total_tokens": self.total_tokens(),
            "total_calls": len(self.entries),
        }