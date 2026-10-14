from datetime import date
from pathlib import Path
import html
import json
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from careerpilot.models import Profile, Constraints, Report
from careerpilot.resume_parser import extract_resume, explicit_skills
from careerpilot.llm import Reasoner
from careerpilot.tinyfish_client import TinyFish
from careerpilot.research import run_research
from careerpilot.engine import select_portfolio, competencies, gaps_for

load_dotenv()
ROOT = Path(__file__).parent
st.set_page_config(page_title="CareerPilot · Your next move, with evidence", page_icon="◈", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1320px}
[data-testid="stSidebar"]{border-right:1px solid #e2e8f0}
h1,h2,h3{letter-spacing:-.035em!important} h1{font-size:3rem!important;line-height:1.08!important}
.eyebrow{color:#2563eb;font-size:11px;font-weight:800;letter-spacing:2px;margin-bottom:13px}
.hero{background:linear-gradient(115deg,#10213f,#163e68);padding:34px 38px;border-radius:20px;color:white;margin:12px 0 25px}
.hero h1{color:white!important;max-width:820px;margin:0 0 12px}.hero p{color:#c4d5ea;max-width:780px;font-size:16px}
.tag{display:inline-block;background:#e8f0ff;color:#2454a6;padding:4px 9px;border-radius:5px;font-size:11px;font-weight:700;margin:0 6px 8px 0}
.card-title{font-size:19px;font-weight:750;line-height:1.35;margin:6px 0 8px;color:#162b4d}
.muted{font-size:13px;color:#66758b}.reason{border-left:3px solid #55b6a1;padding:8px 13px;background:#f0f8f6;font-size:14px;margin:12px 0}
[data-testid="stMetric"]{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px}
[data-testid="stMetricValue"]{font-size:1.85rem}.stButton>button{border-radius:8px}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px}
footer{visibility:hidden}.footnote{font-size:12px;color:#708097;margin-top:30px;border-top:1px solid #e2e8f0;padding-top:16px}
</style>""", unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value))


def item_card(entry):
    item = entry["item"]
    with st.container(border=True):
        st.markdown(f'<span class="tag">{esc(item.category.upper())}</span><span class="tag">{esc(entry["eligibility"].upper())}</span><span class="tag">{esc(item.availability.replace("_", " "))}</span>', unsafe_allow_html=True)
        cols = st.columns([5, 1])
        cols[0].markdown(f'<div class="card-title">{esc(item.title)}</div><div class="muted">{esc(item.provider)}</div>', unsafe_allow_html=True)
        cols[1].metric("Fit score", entry["score"])
        st.write(item.description)
        st.markdown(f'<div class="reason">{esc(entry["decision"])}</div>', unsafe_allow_html=True)
        cost = "Unknown cost" if item.cost is None else ("No paid tools budgeted" if item.category == "project" else "Free content") if item.cost == 0 else f"{item.currency or '?'} {item.cost:g}"
        st.caption(f"{item.weekly_hours:g} h/week · {item.weeks} weeks (planning estimate)  |  {cost}  |  Deadline: {item.deadline or 'unknown'}")
        if item.skills:
            st.caption("Skills: " + " · ".join(item.skills[:8]))
        if item.source_url:
            st.link_button("Inspect official source ↗", item.source_url)
        if item.application_url:
            st.link_button("Application information ↗", item.application_url)
        with st.expander("Evidence & decision breakdown"):
            st.caption(item.origin + " · Checked " + item.checked_at[:19] + " UTC")
            st.write(item.eligibility_reason)
            for fact in item.facts:
                st.markdown(f"**{fact.field.replace('_', ' ').title()}** · {fact.value}")
                st.text(fact.quote[:650])
            if not item.facts:
                st.info("Planning advice, or no supported field extracted. No verification is implied.")
            st.dataframe(pd.DataFrame([{"Component": k.replace("_", " ").title(), "Value / 100": v} for k, v in entry["components"].items()]), hide_index=True, width="stretch")
            st.caption("Missing: " + (", ".join(item.missing_fields) or "No external admission fields for this proposal"))


with st.sidebar:
    st.markdown("## ◈ CareerPilot")
    st.caption("YOUR CAREER, WITH A PLAN")
    st.divider()
    page = st.radio("Workspace", ["Overview", "Profile", "Portfolio", "Skill gaps", "Roadmap", "Network", "Research lab"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Your planning constraints**")
    hours = st.slider("Available hours / week", 0, 30, 10, help="After existing commitments. Updates selection immediately.")
    budget = st.number_input("Total budget", min_value=0, value=2000, step=500)
    currency = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP"])
    weeks = st.select_slider("Planning horizon", [4, 8, 12, 16, 24], value=12)
    st.caption("Estimates are adjustable in Portfolio. Unknown costs never count as free.")
    with st.expander("Integration settings"):
        tf_key = st.text_input("TinyFish key (optional override)", type="password")
        ai_key = st.text_input("OpenAI key (optional override)", type="password")
        ai_model = st.text_input("OpenAI model", value=os.getenv("OPENAI_MODEL", ""), placeholder="A model available to your API project")
        st.caption("Keys remain in this session. They are never written to the report.")
    reasoner = Reasoner(ai_key or None, ai_model or None)
    client = TinyFish(tf_key or None)
    st.caption("● TinyFish key available" if client.key else "○ TinyFish key missing")
    st.caption("● GPT configured (not yet validated)" if reasoner.available else "○ GPT not configured · conservative mode")

constraints = Constraints(weekly_hours=hours, budget=budget, currency=currency, weeks=weeks)
if "profile" not in st.session_state:
    st.session_state.profile = Profile(graduation_year=date.today().year + 1)
profile = st.session_state.profile
report = st.session_state.get("report")
plan = select_portfolio(report.opportunities, profile, constraints) if report else None

if page == "Overview":
    st.markdown('<div class="eyebrow">PERSONAL CAREER INTELLIGENCE / POWERED BY TINYFISH</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero"><h1>Your ambition.<br>A plan grounded in evidence.</h1><p>Discover real opportunities. Investigate the requirements. Build a career portfolio that fits your time, your budget, and your next move.</p></div>', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    a.metric("Sources investigated", len(report.sources) if report else "—")
    b.metric("Selected activities", len(plan["selected"]) if plan else "—")
    c.metric("Need verification", len(plan["conditional"]) if plan else "—")
    d.metric("Weekly capacity", f"{hours} h")
    st.markdown("### A portfolio, built around you")
    a,b,c = st.columns(3)
    for col, number, title, body in [(a,"01","Understand your starting point","Upload your resume, confirm your strengths, and tell us where you want to go."),(b,"02","Investigate the real world","TinyFish searches, reads source pages, and resolves questions in a live browser."),(c,"03","Choose your next moves","A transparent engine balances skill coverage, eligibility, time, and budget.")]:
        with col.container(border=True):
            st.markdown(f'<div class="eyebrow">{number}</div><div class="card-title">{title}</div>', unsafe_allow_html=True)
            st.write(body)
    st.markdown("### Start with your profile, or explore a real research snapshot")
    st.write("Open **Profile** to create a new plan. The snapshot below uses a fictional student and public pages actually retrieved through TinyFish. It is historical evidence, not a fresh availability check.")
    snapshot = ROOT / "samples/live_report.json"
    if snapshot.exists() and st.button("Explore captured live research", type="primary"):
        loaded = Report.model_validate_json(snapshot.read_text(encoding="utf-8-sig"))
        st.session_state.report = loaded
        st.session_state.profile = loaded.profile
        st.session_state.snapshot = True
        st.rerun()
    if report:
        st.success(f"Portfolio ready for {profile.role}. Open Portfolio or Roadmap in the sidebar.")
        st.caption(f"{report.mode} · Captured {report.generated_at[:19]} UTC")

elif page == "Profile":
    st.markdown('<div class="eyebrow">01 / YOUR STARTING POINT</div>', unsafe_allow_html=True)
    st.title("A little context. A better plan.")
    st.write("Resume content is processed for career advice. Only role and broad constraints are sent to TinyFish searches; GPT receives resume text only when configured and you request analysis.")
    upload = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])
    if upload and st.button("Read resume"):
        try:
            text = extract_resume(upload.getvalue(), upload.name)
            st.session_state.resume_text = text
            st.session_state.extracted_skills = ", ".join(explicit_skills(text))
            st.success("Text extracted. Confirm the detected skills below; mentions do not establish proficiency.")
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("resume_text"):
        with st.expander("Extracted text (this session only)"):
            st.text(st.session_state.resume_text[:12000])
        if reasoner.available and st.button("Analyze resume with GPT"):
            try:
                with st.spinner("Extracting supported profile facts…"):
                    data = reasoner.profile(st.session_state.resume_text)
                supported = [s["name"] for s in data.get("skills", []) if s.get("quote") and s["quote"] in st.session_state.resume_text]
                st.session_state.extracted_skills = ", ".join(supported)
                st.session_state.gpt_profile = data
            except Exception:
                st.error("GPT analysis failed. Check model and credentials; manual entry remains available.")
    if st.session_state.get("gpt_profile"):
        st.json(st.session_state.gpt_profile, expanded=False)
    with st.form("profile_form"):
        a,b = st.columns(2)
        role = a.text_input("Target role", profile.role)
        location = b.text_input("Preferred location", profile.location)
        skills = st.text_input("Confirmed skills (comma-separated)", st.session_state.get("extracted_skills", ", ".join(profile.skills)))
        projects = st.text_area("Existing projects and commitments", profile.projects)
        a,b = st.columns(2)
        stage = a.text_input("Academic stage", profile.academic_stage)
        graduation = b.number_input("Expected graduation year (0 if unknown)", min_value=0, max_value=2100, value=profile.graduation_year or 0)
        companies = st.text_input("Target companies (optional)", profile.companies)
        categories = st.multiselect("Research categories", list(["course", "internship", "competition", "program", "networking"]), default=profile.categories)
        remote = st.checkbox("Consider remote opportunities (geographic eligibility still applies)", profile.remote)
        confirmed = st.checkbox("I have reviewed these profile facts and my available hours.")
        submit = st.form_submit_button("Save profile", type="primary")
    if submit:
        if not role.strip() or not confirmed:
            st.error("Add a target role and confirm your profile before saving.")
        else:
            updated = Profile(role=role.strip(), location=location.strip(), academic_stage=stage,
                              graduation_year=graduation or None, skills=[s.strip() for s in skills.split(",") if s.strip()],
                              projects=projects, companies=companies, remote=remote, categories=categories)
            if updated != profile:
                st.session_state.pop("report", None)
            st.session_state.profile = updated
            st.success("Profile saved. Open Research lab to start live discovery.")

elif page == "Research lab":
    st.markdown('<div class="eyebrow">02 / REAL SOURCES, REAL EXECUTION</div>', unsafe_allow_html=True)
    st.title("Follow the evidence.")
    st.write(f"Researching **{profile.role}** · **{profile.location}**. Up to ten candidate pages across your selected categories.")
    if not reasoner.available:
        st.warning("GPT is not configured. Live TinyFish research still works; extraction stays conservative and all external eligibility remains uncertain until you review it.")
    if st.button("Start live TinyFish research", type="primary", disabled=not bool(client.key)):
        with st.status("Investigating public sources…", expanded=True) as progress:
            result = run_research(
                profile=profile,
                client=client,
                reasoner=reasoner,
                callback=lambda event: st.write(f"{event['stage']} · {event['status']} — {event['detail']}"),
                constraints=constraints,
            )
            st.session_state.report = result
            st.session_state.snapshot = False
            progress.update(label=f"Research complete · {len(result.sources)} sources retrieved", state="complete" if result.sources else "error")
        st.rerun()
    if report:
        st.caption(f"{report.mode} · {report.generated_at}")
        st.dataframe(pd.DataFrame(report.events), hide_index=True, width="stretch")
        with st.expander("Investigate a specific unresolved question in the browser", expanded=False):
            st.write("Use this only for a real interaction: opening eligibility tabs, expanding FAQs, or applying public filters. No applications or logins.")
            options = [s.url for s in report.sources]
            if options:
                url = st.selectbox("Previously retrieved source", options)
                question = st.text_area("Specific interaction and question", "Open the eligibility or FAQ section and capture the requirements with exact supporting excerpts.")
                allowed = st.checkbox("Run this metered, read-only browser investigation")
                blocked = st.session_state.get("automation_pending", False)
                if st.button("Investigate with TinyFish browser", disabled=not allowed or blocked):
                    st.session_state.automation_pending = True
                    try:
                        with st.spinner("Browser investigation running. No simulated steps are shown."):
                            result = client.automate(url, question)
                        report.automation = result
                        st.session_state.report = report
                        st.session_state.automation_pending = False
                    except Exception as exc:
                        st.error(str(exc))
                        st.warning("Execution may be unresolved. Inspect recent runs before starting another.")
                if st.button("Inspect recent automation runs"):
                    try:
                        st.json(client.list_runs())
                    except Exception as exc:
                        st.error(str(exc))
                run_id = st.text_input("Run ID to inspect")
                if run_id and st.button("Check run status"):
                    try:
                        current_run = client.get_run(run_id)
                        st.json(current_run)
                        state = current_run.get("status", "") if isinstance(current_run, dict) else ""
                        if state in ("COMPLETED", "FAILED", "CANCELLED"):
                            st.session_state.automation_pending = False
                            st.success("This run is terminal. You can start a new investigation on the next interaction.")
                    except Exception as exc:
                        st.error(str(exc))
        if report.automation:
            st.markdown("### Actual browser result")
            st.caption("Raw browser evidence requires review; it does not automatically approve eligibility.")
            st.json(report.automation)
        for source in report.sources:
            with st.expander(source.title or source.url):
                st.link_button("Open source", source.url)
                st.caption("Retrieved " + source.checked_at)
                st.text(source.text[:14000])

else:
    if not report:
        st.title("Your next move starts here.")
        st.info("Set up your Profile, then start Research lab. Or load the captured real-source snapshot from Overview.")
        st.stop()
    if st.session_state.get("snapshot"):
        st.caption("CAPTURED RESEARCH · historical public-source snapshot · refresh before acting")
    if page == "Portfolio":
        st.markdown('<div class="eyebrow">03 / YOUR TARGET CAREER PORTFOLIO</div>', unsafe_allow_html=True)
        st.title("Fewer distractions. Better next moves.")
        st.write("A practical combination of learning, proof of skill, and opportunity investigation. Scores are heuristics—not hiring probabilities.")
        a,b,c,d = st.columns(4)
        a.metric("Selected", len(plan["selected"]))
        b.metric("Peak weekly effort", f"{max(plan['weekly_load'], default=0):g} h")
        c.metric("Planned spending", f"{currency} {plan['spend']:g}")
        d.metric("Needs verification", len(plan["conditional"]))
        with st.expander("Review eligibility & adjust planning estimates"):
            st.caption("Use the source evidence to review every mandatory criterion. Confirmation is your assessment, not automated verification. Unknown costs remain unknown.")
            options = {o.id: o for o in report.opportunities}
            chosen = st.selectbox("Activity", list(options), format_func=lambda k: options[k].title)
            item = options[chosen]
            estimate = st.number_input("Planning hours per week", min_value=0.5, max_value=40.0, value=float(item.weekly_hours), step=0.5, key="effort_"+chosen)
            assessed = st.checkbox("I checked all mandatory conditions and satisfy them", key="review_"+chosen)
            if st.button("Apply this review"):
                item.weekly_hours = estimate
                if assessed and item.eligibility != "ineligible":
                    item.eligibility = "eligible"
                    item.eligibility_reason = "User-confirmed after reviewing source conditions; not an independent verification."
                st.rerun()
        tabs = st.tabs([f"Selected · {len(plan['selected'])}", f"Verify first · {len(plan['conditional'])}", f"Deprioritized · {len(plan['skipped'])}"])
        for tab, key in zip(tabs, ["selected", "conditional", "skipped"]):
            with tab:
                if not plan[key]:
                    st.info("No activities in this group under your current constraints.")
                for entry in plan[key]:
                    item_card(entry)
        st.download_button("Download evidence & portfolio JSON", json.dumps({"report":report.model_dump(mode="json"),"constraints":constraints.model_dump(),"selection": [{"id":r["item"].id,"decision":r["decision"]} for r in plan["selected"]]}, indent=2), "careerpilot-portfolio.json", "application/json")
    elif page == "Skill gaps":
        st.markdown('<div class="eyebrow">04 / FROM POTENTIAL TO PROOF</div>', unsafe_allow_html=True)
        st.title("Make your next skill visible.")
        st.info("Competencies below are role hypotheses, not universal employer requirements. A missing resume mention means not yet evidenced, not incapable.")
        rows = []
        for skill in competencies(profile.role):
            sources = [o.title for o in report.opportunities if o.category != "project" and skill.lower() in [s.lower() for s in o.skills]]
            rows.append({"Competency":skill, "Profile evidence":"User-confirmed" if skill.lower() in [s.lower() for s in profile.skills] else "Not yet evidenced", "Sources mentioning skill":len(sources), "Next action":"Demonstrate in a reproducible project" if skill in gaps_for(profile) else "Retain and strengthen evidence"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown("### The learning → evidence connection")
        st.write("Investigate a relevant course, practice one missing competency, and produce an artifact with evaluation and documentation. Continue eligible applications in parallel; a course is not a prerequisite unless the opportunity explicitly says so.")
    elif page == "Roadmap":
        st.markdown('<div class="eyebrow">05 / A PLAN YOU CAN ACTUALLY KEEP</div>', unsafe_allow_html=True)
        st.title("Your next weeks, with purpose.")
        st.caption("Planning estimates, not provider commitments. Change capacity in the sidebar to recalculate.")
        st.bar_chart(pd.DataFrame({"Planned hours":plan["weekly_load"]}, index=[f"W{i+1}" for i in range(weeks)]), color="#2563eb")
        for entry in plan["selected"]:
            with st.container(border=True):
                st.markdown(f"**Weeks {entry['start_week']}–{entry['end_week']} · {entry['item'].title}**")
                st.write(entry["decision"])
                st.caption(f"{entry['item'].weekly_hours:g} hours/week · {entry['item'].effort_basis}")
        st.markdown("### Before you commit")
        st.write("Review uncertain eligibility and costs in Portfolio. Keep active application deadlines ahead of optional learning. Browser evidence remains available in Research lab.")
    elif page == "Network":
        st.markdown('<div class="eyebrow">06 / CONNECT THROUGH THE WORK</div>', unsafe_allow_html=True)
        st.title("A reason to connect.")
        network = [e for e in plan["conditional"]+plan["selected"]+plan["skipped"] if e["item"].category == "networking"]
        if not network:
            st.info("No networking source was retrieved. Include networking in your profile and research again.")
        for entry in network:
            item_card(entry)
            st.caption(f"Suggested action: read this team's public work on {profile.role}, reproduce one example, and draft one specific question. No contact is sent automatically.")

st.markdown('<div class="footnote">CareerPilot · TinyFish discovers and investigates. GPT interprets when configured. Python applies the constraints. Evidence stays attached.</div>', unsafe_allow_html=True)
