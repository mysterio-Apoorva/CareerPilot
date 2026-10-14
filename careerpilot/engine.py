"""Transparent heuristics and conservative, deterministic portfolio selection."""
import json
from datetime import date
from pathlib import Path
from .models import Opportunity, Profile, Constraints

WEIGHTS = json.loads((Path(__file__).resolve().parent.parent / "config/scoring.json").read_text())
ROLE_SKILLS = {
    "ai": ["Python", "machine learning", "deep learning", "evaluation", "deployment", "testing"],
    "data": ["Python", "SQL", "statistics", "data analysis", "communication"],
    "quant": ["Python", "probability", "statistics", "research", "testing"],
    "software": ["Git", "testing", "deployment", "Python", "SQL"],
    "frontend": ["JavaScript", "React", "testing", "Git", "deployment"],
}


def competencies(role):
    role = role.lower()
    for key in ROLE_SKILLS:
        if key in role or (key == "ai" and "machine learning" in role):
            return ROLE_SKILLS[key]
    return ["research", "communication", "data analysis"]


def gaps_for(profile):
    known = {s.lower() for s in profile.skills}
    return [s for s in competencies(profile.role) if s.lower() not in known]


def eligibility(item, profile, today=None):
    today = today or date.today()
    if item.availability == "closed" or (item.deadline and item.deadline < today):
        return "ineligible", "Application window is closed."
    if item.eligibility == "ineligible":
        return "ineligible", item.eligibility_reason
    if item.min_graduation or item.max_graduation:
        year = profile.graduation_year
        if year is None:
            return "uncertain", "Graduation year is required but unknown."
        if (item.min_graduation and year < item.min_graduation) or (item.max_graduation and year > item.max_graduation):
            return "ineligible", "Graduation year is outside the verified window."
    if item.allowed_locations and profile.location.casefold() not in [s.casefold() for s in item.allowed_locations]:
        return "ineligible", "Location does not match the stated participation restriction."
    known = {s.lower() for s in profile.skills}
    missing = [s for s in item.required_skills if s.lower() not in known]
    if missing:
        return "uncertain", "Confirm mandatory prerequisites: " + ", ".join(missing)
    return item.eligibility, item.eligibility_reason


def score(item, profile, constraints, today=None):
    today = today or date.today()
    target = {s.lower() for s in competencies(profile.role)}
    gaps = {s.lower() for s in gaps_for(profile)}
    developed = {s.lower() for s in item.skills}
    state, reason = eligibility(item, profile, today)
    relevance = min(1, len(developed & target) / max(1, min(3, len(target))))
    reduction = min(1, len(developed & gaps) / max(1, min(2, len(gaps)))) if gaps else relevance
    affordable = item.cost is not None and (item.cost == 0 or item.currency == constraints.currency) and item.cost <= constraints.budget
    urgency = 0
    if item.deadline:
        days = (item.deadline - today).days
        prep_days = max(2, round(item.weekly_hours / max(1, constraints.weekly_hours) * 7))
        if days >= prep_days:
            urgency = 1 if days <= 14 else (0.6 if days <= 30 else 0.25)
    values = {
        "career_relevance": relevance,
        "gap_reduction": reduction,
        "eligibility_fit": 1 if state == "eligible" else 0.5 if state == "uncertain" else 0,
        "time_efficiency": min(1, 2 / item.weekly_hours),
        "feasibility": 1 if affordable and item.weekly_hours <= constraints.weekly_hours else 0,
        "deadline_readiness": urgency,
    }
    return {"score": round(100 * sum(values[k] * w for k, w in WEIGHTS.items())),
            "components": {k: round(v * 100) for k, v in values.items()}, "eligibility": state, "reason": reason}


def select_portfolio(items, profile, constraints):
    ranked = [(item, score(item, profile, constraints)) for item in items]
    ranked.sort(key=lambda row: (-row[1]["score"], row[0].id))
    selected, conditional, skipped = [], [], []
    used = [0.0] * constraints.weeks
    spent, covered, course_skills = 0.0, set(), set()
    for item, result in ranked:
        entry = {"item": item, **result}
        if result["eligibility"] == "ineligible":
            entry["decision"] = result["reason"]
            skipped.append(entry)
            continue
        if result["eligibility"] == "uncertain":
            entry["decision"] = "Verify eligibility before committing: " + result["reason"]
            conditional.append(entry)
            continue
        if item.cost is None or (item.cost != 0 and item.currency != constraints.currency):
            entry["decision"] = "Confirm cost and currency before allocating budget."
            conditional.append(entry)
            continue
        if item.category in ("internship", "competition", "program") and item.availability not in ("open", "upcoming_confirmed"):
            entry["decision"] = "No confirmed active cycle; keep as a preparation reference."
            conditional.append(entry)
            continue
        skills = {s.lower() for s in item.skills}
        if item.category == "course" and skills and len(skills & course_skills) / len(skills) >= 0.75:
            entry["decision"] = "Overlaps substantially with a selected course."
            skipped.append(entry)
            continue
        if spent + item.cost > constraints.budget:
            entry["decision"] = "Exceeds the remaining total budget."
            skipped.append(entry)
            continue
        length = item.weeks
        slot = None
        for start in range(max(0, constraints.weeks - length + 1)):
            if item.deadline and (item.deadline - date.today()).days < start * 7:
                continue
            if all(used[w] + item.weekly_hours <= constraints.weekly_hours for w in range(start, start + length)):
                slot = start
                break
        if slot is None:
            entry["decision"] = "Does not fit the weekly capacity and planning horizon."
            skipped.append(entry)
            continue
        for w in range(slot, slot + length):
            used[w] += item.weekly_hours
        spent += item.cost
        new = skills - covered
        reinforcement = skills & covered
        entry["decision"] = "Adds " + (", ".join(sorted(new)) or "demonstration practice")
        if reinforcement:
            entry["decision"] += "; reinforces " + ", ".join(sorted(reinforcement))
        entry["start_week"], entry["end_week"] = slot + 1, slot + length
        covered |= skills
        if item.category == "course":
            course_skills |= skills
        selected.append(entry)
    return {"selected": selected, "conditional": conditional, "skipped": skipped,
            "weekly_load": used, "spend": spent, "coverage": sorted(covered)}


def project_proposals(profile):
    gaps = gaps_for(profile)
    tech = any(s.lower() in ("python", "javascript", "sql") for s in profile.skills)
    if tech:
        title = "Ship a measured, reproducible role-specific prototype"
        description = (f"Build a small {profile.role} portfolio artifact. Define a 20-case evaluation set, "
                       "document failures, add reproducible setup and tests, and publish a local demo. "
                       "Use only freely accessible tools; paid hosting is outside this estimate.")
    else:
        title = "Publish an evidence-backed role case study"
        description = f"Investigate a practical {profile.role} problem, compare alternatives, and publish a concise case study with sources and measurable criteria."
    return [Opportunity(id="proposal-project", title=title, category="project", provider="CareerPilot proposal",
                        description=description, skills=gaps[:3] or competencies(profile.role)[:2],
                        eligibility="eligible", eligibility_reason="Self-directed proposal using the confirmed profile; no external admission process.",
                        cost=0, currency=None, weekly_hours=4, weeks=3, missing_fields=[],
                        origin="Planning proposal · not an externally verified opportunity",
                        advice="Practice one gap, measure the result, and show the evidence in your README.")]
