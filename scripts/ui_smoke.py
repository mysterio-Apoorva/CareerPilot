"""Exercise real upload and saved profile flow in the running local app."""
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width":1440, "height":1000})
    page.set_default_timeout(15000)
    page.goto("http://localhost:8501", wait_until="networkidle")
    page.get_by_test_id("stSidebar").get_by_text("Profile", exact=True).click()
    page.locator('input[type="file"]').set_input_files(str(root / "samples/sample_resume.pdf"))
    page.get_by_role("button", name="Read resume", exact=True).click()
    page.get_by_text("Text extracted.", exact=False).wait_for()
    assert "Python" in page.get_by_role("textbox", name="Confirmed skills (comma-separated)").input_value()
    page.get_by_text("I have reviewed these profile facts and my available hours.", exact=True).click()
    page.get_by_role("button", name="Save profile", exact=True).click()
    page.get_by_text("Profile saved.", exact=False).wait_for()
    print("PASS: actual PDF upload, extraction, skill editing fields, profile confirmation and save.")
    page.get_by_test_id("stSidebar").get_by_text("Overview", exact=True).click()
    page.get_by_role("button", name="Explore captured live research").click()
    page.get_by_test_id("stSidebar").get_by_text("Portfolio", exact=True).click()
    page.get_by_role("tab", name="Deprioritized", exact=False).click()
    page.get_by_text("Explore Microsoft · academic-stage check", exact=True).wait_for()
    page.screenshot(path=str(root / "docs/screenshots/07-eligibility-decision.png"), full_page=True)
    print("PASS: actual browser evidence rendered in the ineligible decisions view.")
    browser.close()
