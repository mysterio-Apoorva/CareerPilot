"""Real-browser regression: two different uploaded resumes must not share facts."""
import io
from docx import Document
from playwright.sync_api import sync_playwright, expect


def resume(text):
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    data = io.BytesIO()
    doc.save(data)
    return {"name":"resume.docx", "mimeType":"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer":data.getvalue()}


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width":1440,"height":1100})
    page.set_default_timeout(15000)
    page.goto("http://127.0.0.1:8501", wait_until="networkidle")
    page.get_by_test_id("stSidebar").get_by_text("Profile", exact=True).click()
    skills = page.get_by_role("textbox", name="Confirmed skills (comma-separated)")
    projects = page.get_by_role("textbox", name="Existing projects and commitments")
    assert skills.input_value() == projects.input_value() == ""
    page.locator('input[type="file"]').set_input_files(resume("Student A\nEducation\nB.Tech Robotics\nExpected graduation: 2029\nSkills: Rust, Zig, C++, C#, ROS2\nProjects\nAutonomous rover controller."))
    page.get_by_role("button", name="Read resume", exact=True).click()
    page.get_by_text("Text extracted from", exact=False).wait_for()
    expect(skills).to_have_value("Rust, Zig, C++, C#, ROS2")
    expect(projects).to_have_value("Autonomous rover controller.")
    expect(page.get_by_role("textbox", name="Education", exact=True)).to_have_value("B.Tech Robotics\nExpected graduation: 2029")
    expect(page.get_by_role("spinbutton", name="Expected graduation year (0 if unknown)")).to_have_value("2029")
    page.locator('input[type="file"]').set_input_files(resume("Student B\nSkills: Figma, typography\nProjects\nEditorial design portfolio."))
    expect(skills).to_have_value("")
    page.get_by_role("button", name="Read resume", exact=True).click()
    expect(skills).to_have_value("Figma, typography")
    expect(projects).to_have_value("Editorial design portfolio.")
    expect(page.get_by_role("textbox", name="Education", exact=True)).to_have_value("")
    expect(page.get_by_role("spinbutton", name="Expected graduation year (0 if unknown)")).to_have_value("0")
    browser.close()
print("PASS: fresh profile blank; two different real uploads populate distinct facts; no old education/year/skills leak.")
