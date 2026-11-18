from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("ERROR: GEMINI_API_KEY not set. Add it to .env or export it.")
    sys.exit(1)

from parser import load_messages
from planner import build_plan, update_plan
from trace import Tracer
from ui import print_plan

PLAN_FILE = "plan_output.json"
TRACE_FILE = "trace_output.txt"

def main():
    parser = argparse.ArgumentParser(description="Hackathon Planner Agent")
    parser.add_argument("messages_file", help="Path to messages.txt")
    parser.add_argument("--new", metavar="MESSAGE_TEXT",
                        help="New message text for incremental update", default=None)
    parser.add_argument("--new-file", metavar="FILE",
                        help="File with new messages for incremental update", default=None)
    args = parser.parse_args()

    tracer = Tracer()
    is_update = (args.new is not None or args.new_file is not None)
    existing_plan = None

    if is_update:
        if Path(PLAN_FILE).exists():
            with open(PLAN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_plan = data.get("plan", data)
        else:
            print("No existing plan found. Running full build first.")
            is_update = False

    if is_update:
        if args.new:
            new_messages = [{"id": "new_1", "from": "update", "date": "today", "text": args.new}]
        else:
            new_messages = load_messages(args.new_file)
        print(f"\nProcessing {len(new_messages)} new message(s) as incremental update...")
        final_plan = update_plan(new_messages, existing_plan, tracer)
    else:
        messages = load_messages(args.messages_file)
        print(f"\nLoaded {len(messages)} messages from '{args.messages_file}'")
        print("Running full plan build...\n")
        final_plan = build_plan(messages, tracer)

    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump({"plan": final_plan, "trace": tracer.to_dict()}, f, indent=2, ensure_ascii=False)

    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tracer.print_trace()
    trace_text = buf.getvalue()
    with open(TRACE_FILE, "w", encoding="utf-8") as f:
        f.write(trace_text)

    print_plan(final_plan, tracer)

    print(f"\nOutputs saved:")
    print(f"  Plan + trace JSON : {PLAN_FILE}")
    print(f"  Trace text        : {TRACE_FILE}")

if __name__ == "__main__":
    main()