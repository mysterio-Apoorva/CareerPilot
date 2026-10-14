from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def now():
    return datetime.now(timezone.utc).isoformat()


class Profile(BaseModel):
    role: str = "AI engineering intern"
    location: str = "India"
    academic_stage: str = "Undergraduate, third year"
    graduation_year: int | None = None
    skills: list[str] = Field(default_factory=lambda: ["Python", "SQL", "Git", "machine learning"])
    projects: str = "Tabular machine learning project with cross-validation"
    companies: str = ""
    remote: bool = True
    categories: list[str] = Field(default_factory=lambda: ["course", "internship", "competition", "program", "networking"])


class Constraints(BaseModel):
    weekly_hours: float = Field(default=10, ge=0, le=80)
    budget: float = Field(default=2000, ge=0)
    currency: str = "INR"
    weeks: int = Field(default=12, ge=1, le=52)


class Fact(BaseModel):
    field: str
    value: str
    quote: str
    source_url: str
    checked_at: str = Field(default_factory=now)
    status: Literal["source-supported", "inferred", "unknown"] = "source-supported"


class Opportunity(BaseModel):
    id: str
    title: str
    category: Literal["course", "internship", "competition", "program", "networking", "project"]
    provider: str
    source_url: str = ""
    application_url: str | None = None
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    eligibility: Literal["eligible", "ineligible", "uncertain"] = "uncertain"
    eligibility_reason: str = "Mandatory conditions have not been fully established."
    availability: Literal["open", "upcoming_confirmed", "recurring_unconfirmed", "closed", "unknown"] = "unknown"
    deadline: date | None = None
    cost: float | None = Field(default=None, ge=0)
    currency: str | None = None
    weekly_hours: float = Field(default=2, gt=0)
    effort_basis: str = "Editable planning estimate; not a provider statement"
    weeks: int = Field(default=4, ge=1)
    min_graduation: int | None = None
    max_graduation: int | None = None
    allowed_locations: list[str] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=lambda: ["deadline", "cost", "eligibility"])
    checked_at: str = Field(default_factory=now)
    advice: str = ""
    origin: str = "TinyFish source extraction"


class Source(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    links: list[str] = Field(default_factory=list)
    checked_at: str = Field(default_factory=now)
    error: str | None = None


class Report(BaseModel):
    profile: Profile
    opportunities: list[Opportunity] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    competency_basis: str = "Role hypothesis; not an employer requirement"
    generated_at: str = Field(default_factory=now)
    mode: str = "Conservative extraction · GPT not configured"
    automation: dict | None = None
