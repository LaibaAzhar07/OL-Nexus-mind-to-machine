from __future__ import annotations
import json
import re
from trace import Tracer
from agents import (agent_reading, agent_venue, agent_schedule,
                    agent_food, agent_judging, agent_budget)

SCHEDULE_RULES = {
    "start_time": "10:00", "duration_hours": 4,
    "code_freeze": "13:25", "test_run": "13:30",
    "judge_visits_start": "14:30", "judge_visits_end": "16:30",
    "prayer_break_minutes": 15,
}

OUT_OF_SCOPE_KEYWORDS = ["dj", "disc jockey", "band", "entertainment",
                          "decoration", "photographer", "videographer"]

def _is_out_of_scope(text: str):
    lower = text.lower()
    for kw in OUT_OF_SCOPE_KEYWORDS:
        if kw in lower:
            return f"Out of scope: '{kw}' requests are not part of the hackathon plan."
    return None

def _filter_messages(classifications, messages, tracer):
    msg_map = {m["id"]: m for m in messages}
    area_messages = {"venue": [], "schedule": [], "food": [],
                     "judging": [], "budget": [], "reading": []}
    for c in classifications:
        mid = str(c["id"])
        msg = msg_map.get(mid)
        if not msg:
            continue
        oos = _is_out_of_scope(msg["text"])
        if oos:
            tracer.reject(mid, msg["from"], msg["text"], oos)
            continue
        if c["status"] == "skip":
            reason = c.get("skip_reason", "Classified as skip by reading agent.")
            tracer.reject(mid, msg["from"], msg["text"], reason)
            continue
        area = c.get("area", "irrelevant")
        if area in area_messages:
            area_messages[area].append(msg)
    return area_messages

def _extract_constraints(messages, existing_plan):
    if existing_plan:
        return {
            "total_budget": existing_plan.get("total_budget", 650000),
            "participants": existing_plan.get("participants", 150),
            "num_teams": existing_plan.get("teams", 50),
            "staff": existing_plan.get("staff", 10),
            "judges": existing_plan.get("judging", {}).get("num_judges", 20),
        }
    budget = 650000
    participants = 150
    staff = 10
    judges = 20
    for msg in messages:
        text = msg["text"]
        b = re.search(r'Rs\s*([\d,]+)', text)
        if b and "budget" in text.lower():
            budget = int(b.group(1).replace(",", ""))
        p = re.search(r'(\d+)\s*students', text)
        if p:
            participants = int(p.group(1))
        s = re.search(r'(\d+)\s*staff', text)
        if s:
            staff = int(s.group(1))
        j = re.search(r'(\d+)\s*judges', text)
        if j:
            judges = int(j.group(1))
    return {"total_budget": budget, "participants": participants,
            "num_teams": participants // 3, "staff": staff, "judges": judges}

def build_plan(messages, tracer, existing_plan=None):
    reading_result = agent_reading(messages, tracer)
    classifications = reading_result["classifications"]
    area_messages = _filter_messages(classifications, messages, tracer)
    constraints = _extract_constraints(messages, existing_plan)

    plan = existing_plan.copy() if existing_plan else {
        "total_budget": constraints["total_budget"],
        "participants": constraints["participants"],
        "teams": constraints["num_teams"],
        "staff": constraints["staff"],
    }

    if area_messages["venue"] or existing_plan is None:
        min_cap = constraints["participants"] + constraints["staff"] + constraints["judges"]
        plan["venue"] = agent_venue(area_messages["venue"], {"min_capacity": min_cap}, tracer)

    if area_messages["schedule"] or existing_plan is None:
        plan["schedule"] = agent_schedule(area_messages["schedule"], SCHEDULE_RULES, tracer)

    if area_messages["food"] or existing_plan is None:
        plan["food"] = agent_food(area_messages["food"],
            {"participants": constraints["participants"],
             "staff": constraints["staff"],
             "judges": constraints["judges"]}, tracer)

    if area_messages["judging"] or existing_plan is None:
        plan["judging"] = agent_judging(area_messages["judging"],
            {"num_teams": constraints["num_teams"]}, tracer)

    if area_messages["budget"] or existing_plan is None:
        plan["budget"] = agent_budget(area_messages["budget"], plan, tracer)

    return plan

def update_plan(new_messages, existing_plan, tracer):
    return build_plan(new_messages, tracer, existing_plan=existing_plan)