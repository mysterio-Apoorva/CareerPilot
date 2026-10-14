"""Real local Chromium screenshots; no generated UI mockups."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
out = root / "docs/screenshots"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width":1440, "height":1100}, device_scale_factor=1)
    page.set_default_timeout(12000)
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.get_by_role("button", name="Explore captured live research").wait_for(timeout=30000)
    page.screenshot(path=str(out / "01-overview.png"), full_page=True)
    page.get_by_role("button", name="Explore captured live research").click()
    page.get_by_text("Portfolio ready for", exact=False).wait_for(timeout=20000)
    page.screenshot(path=str(out / "02-live-overview.png"), full_page=True)
    for label, name in [("Portfolio", "03-portfolio.png"), ("Skill gaps", "04-skill-gaps.png"),
                        ("Roadmap", "05-roadmap.png"), ("Research lab", "06-research.png")]:
        page.get_by_test_id("stSidebar").get_by_text(label, exact=True).click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(out/name), full_page=True)
    browser.close()
print("Captured six screenshots from the real Streamlit application.")
