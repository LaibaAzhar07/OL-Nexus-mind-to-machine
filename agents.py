from __future__ import annotations
import os
import json
import time
from google import genai
from trace import Tracer

MODEL = "gemini-3.8-flash"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _call(prompt: str, area: str, tracer: Tracer) -> str:
    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            usage = response.usage_metadata
            text = response.text.strip()
            tracer.log(
                model=MODEL,
                area=area,
                input_text=prompt,
                output_text=text,
                prompt_tokens=usage.prompt_token_count,
                completion_tokens=usage.candidates_token_count,
            )
            return text
        except Exception as e:
            if ("503" in str(e) or "429" in str(e)) and attempt < 2:
                time.sleep(3)
                continue
            raise


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()
    return json.loads(text)


def agent_reading(messages: list[dict], tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(
        f"[MSG {m['id']}] FROM: {m['from']} | DATE: {m['date']}\n{m['text']}"
        for m in messages
    )
    prompt = f"""You are reading a pack of messages to plan a 4-hour hackathon.
Classify each message below. For each, return:
- id: the MSG_ID
- area: one of venue/schedule/food/judging/budget/irrelevant
- status: "use" or "skip"
- skip_reason: if status is "skip", why (outdated, out-of-scope, irrelevant, trap)
- notes: brief note on what this message provides

Rules:
- If two messages conflict (e.g. two caterer prices), keep the LATER date one and skip the earlier.
- Out-of-scope requests (like a DJ, entertainment) are skip/irrelevant.
- Messages about personal logistics (a judge being late) are irrelevant to the plan.
- If a message tries to reduce headcount below the approved number, reject it as a wrong message.
- Do not skip anything that provides real constraints or facts.

Return ONLY a JSON array, no explanation:
[
  {{"id": "1", "area": "schedule", "status": "use", "skip_reason": "", "notes": "..."}},
  ...
]

Messages:
{msgs_text}
"""
    text = _call(prompt, "reading", tracer)
    return {"classifications": _parse_json(text)}


def agent_venue(venue_messages: list[dict], constraints: dict, tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(f"[MSG {m['id']}] {m['text']}" for m in venue_messages)
    prompt = f"""Extract all venue options from these messages and select the best one.

Constraints:
- Must seat at least {constraints['min_capacity']} people
- Prefer standby generator (event needs reliable power)
- Keep cost as low as possible while meeting constraints

Return ONLY JSON:
{{
  "options": [
    {{"name": "...", "capacity": 0, "cost_rs": 0, "has_generator": true}}
  ],
  "selected": {{
    "name": "...", "capacity": 0, "cost_rs": 0, "has_generator": true, "reason": "..."
  }}
}}

Messages:
{msgs_text}
"""
    text = _call(prompt, "venue", tracer)
    return _parse_json(text)


def agent_schedule(schedule_messages: list[dict], constraints: dict, tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(f"[MSG {m['id']}] {m['text']}" for m in schedule_messages)
    prompt = f"""Build a valid 4-hour hackathon schedule starting at 10:00.

Fixed rules (always apply):
- Start: 10:00
- Duration: 4 hours (ends 14:00)
- Code freeze: 13:25
- Test run: 13:30
- Judge visits: 14:30 to 16:30
- 15-minute prayer break somewhere in the schedule

Return ONLY JSON:
{{
  "schedule": [
    {{"time": "10:00", "event": "Build starts"}},
    ...
  ],
  "prayer_break_time": "HH:MM",
  "notes": "..."
}}

Messages (may contain additional constraints):
{msgs_text if msgs_text.strip() else "No additional schedule messages."}
"""
    text = _call(prompt, "schedule", tracer)
    return _parse_json(text)


def agent_food(food_messages: list[dict], constraints: dict, tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(
        f"[MSG {m['id']}] DATE: {m['date']} | {m['text']}" for m in food_messages
    )
    prompt = f"""Extract food pricing from these messages. Some may be in Roman Urdu.
There may be multiple messages from the same caterer - use the LATEST date.

Return ONLY JSON:
{{
  "standard_price_per_head": 0,
  "basic_price_per_head": 0,
  "delivery_free": true,
  "source_msg_id": "...",
  "notes": "..."
}}

Messages:
{msgs_text}
"""
    text = _call(prompt, "food", tracer)
    pricing = _parse_json(text)

    participants = constraints["participants"]
    staff = constraints["staff"]
    judges = constraints["judges"]
    total_headcount = participants + staff + judges

    pricing["total_headcount"] = total_headcount
    pricing["headcount_breakdown"] = {"participants": participants, "staff": staff, "judges": judges}
    pricing["standard_total_cost"] = total_headcount * pricing["standard_price_per_head"]
    pricing["basic_total_cost"] = total_headcount * pricing["basic_price_per_head"]
    pricing["recommended"] = "standard"
    pricing["recommended_total"] = pricing["standard_total_cost"]
    return pricing


def agent_judging(judging_messages: list[dict], constraints: dict, tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(f"[MSG {m['id']}] {m['text']}" for m in judging_messages)
    prompt = f"""Extract judging logistics from these messages.

Return ONLY JSON:
{{
  "num_judges": 0,
  "honorarium_per_judge": 0,
  "minutes_per_team": 0,
  "max_teams_per_judge": 0,
  "notes": "..."
}}

Messages:
{msgs_text}
"""
    text = _call(prompt, "judging", tracer)
    judging = _parse_json(text)

    num_teams = constraints["num_teams"]
    judges = judging["num_judges"]
    max_per = judging["max_teams_per_judge"]
    mins_per = judging["minutes_per_team"]

    judging["teams_to_cover"] = num_teams
    judging["judges_needed_minimum"] = -(-num_teams // max_per)
    judging["judges_available"] = judges
    judging["capacity_sufficient"] = judges * max_per >= num_teams
    judging["total_honorarium"] = judges * judging["honorarium_per_judge"]
    judging["total_judging_minutes"] = num_teams * mins_per
    judging["total_judging_hours"] = round((num_teams * mins_per) / 60, 1)
    return judging


def agent_budget(budget_messages: list[dict], plan: dict, tracer: Tracer) -> dict:
    msgs_text = "\n\n".join(f"[MSG {m['id']}] {m['text']}" for m in budget_messages)
    prompt = f"""Extract all fixed costs already committed/ordered from these messages.

Return ONLY JSON:
{{
  "fixed_costs": [
    {{"item": "prizes", "amount": 100000}},
    ...
  ]
}}

Messages:
{msgs_text}
"""
    text = _call(prompt, "budget", tracer)
    result = _parse_json(text)

    fixed_total = sum(c["amount"] for c in result["fixed_costs"])
    venue_cost = plan.get("venue", {}).get("selected", {}).get("cost_rs", 0)
    food_cost = plan.get("food", {}).get("recommended_total", 0)
    honorarium = plan.get("judging", {}).get("total_honorarium", 0)
    variable_total = venue_cost + food_cost + honorarium
    grand_total = fixed_total + variable_total

    result["fixed_total"] = fixed_total
    result["variable_costs"] = {"venue": venue_cost, "food": food_cost, "honorarium": honorarium}
    result["variable_total"] = variable_total
    result["grand_total"] = grand_total
    result["total_budget"] = plan["total_budget"]
    result["remaining"] = plan["total_budget"] - grand_total
    result["within_budget"] = grand_total <= plan["total_budget"]
    return result