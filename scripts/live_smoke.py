"""Explicit opt-in public research; saves a fictional-profile demo snapshot."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
from careerpilot.models import Profile
from careerpilot.tinyfish_client import TinyFish
from careerpilot.research import run_research
from careerpilot.llm import Reasoner
from datetime import date
load_dotenv()
profile = Profile(graduation_year=date.today().year+1)
report = run_research(profile, TinyFish(), Reasoner(), lambda e: print(e['stage'], e['status'], e['detail'], flush=True))
out = Path(__file__).resolve().parent.parent / "samples/live_report.json"
out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
print(f"SAVED {len(report.sources)} real sources to {out}")
if not report.sources:
    raise SystemExit(1)
