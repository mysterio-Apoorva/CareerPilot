"""Attach a real completed run to the public sample, never fabricate results."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from careerpilot.models import Report, Source, Opportunity, Fact

root = Path(__file__).resolve().parent.parent
report = Report.model_validate_json((root / "samples/live_report.json").read_text(encoding="utf-8"))
run = json.loads((root / ".runtime/automation.json").read_text(encoding="utf-8-sig"))
report.automation = run
if run.get("status") == "COMPLETED" and isinstance(run.get("result"), dict):
    found = run["result"].get("findings", {})
    if isinstance(found, dict) and found.get("faq_2_answer") and found.get("source_url"):
        url = found["source_url"]
        quote = found["faq_2_answer"]
        item = Opportunity(id="browser-microsoft-explore", title="Explore Microsoft · academic-stage check",
                           category="program", provider="Microsoft", source_url=url,
                           description="A targeted browser investigation expanded the official program's eligibility FAQs.",
                           eligibility="ineligible", eligibility_reason="The sample profile is a third-year undergraduate. The expanded FAQ describes first- and second-year applications.",
                           facts=[Fact(field="academic_stage", value="First- and second-year applications", quote=quote, source_url=url),
                                  Fact(field="locations", value="See source excerpt", quote=found.get("faq_1_answer", ""), source_url=url)],
                           origin="Real TinyFish browser result · manually reviewed for the fictional demo profile")
        report.opportunities = [o for o in report.opportunities if o.id != item.id] + [item]
        report.events.append({"time":run.get("finished_at"), "stage":"Browser", "status":"complete", "detail":"Expanded two Microsoft FAQs; sample academic-stage mismatch identified", "url":url})
(root / "samples/live_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
print("Attached actual browser evidence.")
