import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from .models import Fact, Opportunity, Report, Source, now
from .engine import gaps_for, project_proposals
from .resume_parser import explicit_skills
from .tinyfish_client import canonical, safe_url

REGISTRY = json.loads((Path(__file__).resolve().parent.parent / "config/sources.json").read_text())


def extract_conservative(source, category):
    """No unsupported dates/eligibility: excerpts are evidence, advice is labeled."""
    text = source.text
    skills = explicit_skills(text)
    facts = []
    for skill in skills[:6]:
        match = re.search(r"[^\n]{0,100}\b" + re.escape(skill) + r"\b[^\n]{0,140}", text, re.I)
        if match:
            facts.append(Fact(field="skill_mention", value=skill, quote=match.group(0).strip(), source_url=source.url))
    free = re.search(r"[^\n]*(?:completely free|free of charge|at no cost)[^\n]*", text, re.I) if category == "course" else None
    if free:
        facts.append(Fact(field="cost", value="0", quote=free.group(0).strip(), source_url=source.url))
    return Opportunity(
        id=hashlib.sha256(canonical(source.url).encode()).hexdigest()[:12],
        title=source.title or urlparse(source.url).hostname, category=category,
        provider=urlparse(source.url).hostname or "Unknown", source_url=source.url,
        description="Source retrieved successfully. Review the supporting excerpts and mandatory conditions before committing.",
        skills=skills, facts=facts, cost=0 if free else None,
        missing_fields=["deadline", "eligibility", "availability"] + ([] if free else ["cost"]),
        advice="Investigate the official requirements; this candidate has not been approved as eligible.",
    )


def enhance(item, source, profile, reasoner):
    data = reasoner.json(
        "Extract one specific opportunity, not unrelated listings on the same page. Return "
        "{title, description, skills: [string], advice, facts: [{field, value, quote}]}. "
        "Allowed fact fields: deadline (ISO date), cost (number), currency, application_url, availability "
        "(open/upcoming_confirmed/recurring_unconfirmed/closed), prerequisite, eligibility_rule. "
        "Each fact requires an EXACT contiguous source quote. Do not assess eligibility. "
        "Skills must be supported in the page. advice must relate to the profile. "
        "Do not interpret incidental page navigation or unrelated jobs as this opportunity.",
        {"profile": profile.model_dump(), "url": source.url, "text": source.text[:18000]},
    )
    item.title = str(data.get("title") or item.title)[:200]
    item.description = str(data.get("description") or item.description)[:1600]
    item.advice = str(data.get("advice") or item.advice)[:1200]
    for raw in data.get("facts", [])[:15]:
        quote = str(raw.get("quote", "")).strip()
        if len(quote) < 5 or quote not in source.text:
            continue
        field, value = str(raw.get("field")), str(raw.get("value"))
        fact = Fact(field=field, value=value, quote=quote, source_url=source.url)
        item.facts.append(fact)
        try:
            if field == "deadline" and value in quote:
                item.deadline = date.fromisoformat(value)
            elif field == "cost":
                number = float(value)
                literal_number = re.search(r"(?<![\d.])" + re.escape(value) + r"(?![\d.])", quote)
                explicitly_free = number == 0 and re.search(r"(?:completely free|free of charge|at no cost)", quote, re.I)
                if number >= 0 and (literal_number or explicitly_free):
                    item.cost = number
            elif field == "currency" and len(value) == 3:
                item.currency = value.upper()
            elif field == "application_url" and value in source.links:
                item.application_url = safe_url(value)
            elif field == "availability" and value in ("open", "upcoming_confirmed", "recurring_unconfirmed", "closed"):
                item.availability = value
        except (ValueError, TypeError):
            continue
    item.missing_fields = [name for name, val in {"deadline": item.deadline, "cost": item.cost,
                                                "eligibility": None, "availability": None if item.availability == "unknown" else item.availability}.items() if val is None]
    item.origin = "TinyFish evidence · GPT-assisted extraction · eligibility needs review"
    return item


def run_research(profile, client, reasoner=None, callback=None, constraints=None):
    report = Report(profile=profile, gaps=gaps_for(profile))
    if reasoner and reasoner.available:
        report.mode = "GPT-assisted evidence extraction"
    def event(stage, status, detail, url=None):
        row = {"time": now(), "stage": stage, "status": status, "detail": detail, "url": url}
        report.events.append(row)
        if callback:
            callback(row)
    seen = set()
    candidates = []
    for category in profile.categories:
        if category not in REGISTRY:
            continue
        spec = REGISTRY[category]
        # Public role and constraints only; no resume or direct personal identifiers.
        query = f"{profile.role} {profile.location} {spec['query']}"
        if category == "course":
            query += " " + " ".join(gaps_for(profile)[:2])
            if constraints and constraints.budget == 0:
                query += " free"
        if category == "internship":
            if profile.graduation_year:
                query += f" graduating {profile.graduation_year}"
            if profile.remote:
                query += " remote or local"
        if category in ("internship", "competition", "program"):
            query += f" {date.today().year}"
        if profile.companies and category == "internship":
            query += " " + profile.companies[:150]
        event("Search", "running", query)
        try:
            response = client.search(query, spec["domains"])
            count = 0
            for hit in response.get("results", []):
                url = hit.get("url", "")
                try:
                    key = canonical(url)
                except ValueError:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((category, url, hit.get("title", "")))
                count += 1
                if count == 2:
                    break
            event("Search", "complete", f"{count} distinct {category} candidates discovered")
        except Exception as exc:
            event("Search", "failed", str(exc))
    for start in range(0, len(candidates), 5):
        batch = candidates[start:start + 5]
        event("Fetch", "running", f"Investigating {len(batch)} public sources")
        try:
            response = client.fetch([r[1] for r in batch])
            for error in response.get("errors", []):
                event("Fetch", "failed", str(error))
            for record in response.get("results", []):
                url = record.get("url") or record.get("final_url")
                match = next((r for r in batch if r[1] == url), None)
                if not match or not record.get("text"):
                    continue
                source = Source(url=record.get("final_url") or url, title=record.get("title") or match[2],
                                text=record["text"], links=[x for x in record.get("links", []) if isinstance(x, str)])
                report.sources.append(source)
                item = extract_conservative(source, match[0])
                if reasoner and reasoner.available:
                    try:
                        item = enhance(item, source, profile, reasoner)
                    except Exception:
                        event("GPT", "failed", "Extraction failed; preserving conservative source excerpts.", source.url)
                report.opportunities.append(item)
                event("Fetch", "complete", f"{len(item.facts)} supporting excerpts extracted", source.url)
        except Exception as exc:
            event("Fetch", "failed", str(exc))
    if report.sources:
        report.opportunities.extend(project_proposals(profile))
    event("Portfolio", "complete", f"{len(report.sources)} sources investigated; unknowns preserved")
    return report
