from pathlib import Path
from datetime import date
from docx import Document
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parent.parent / "samples"
root.mkdir(exist_ok=True)
lines = ["CareerPilot Sample Student — fictional profile", "B.Tech Computer Science, third year",
         f"Expected graduation: {date.today().year + 1}", "Skills: Python, SQL, Git, machine learning",
         "Project: tabular classification with cross-validation and documented experiments.",
         "Career target: AI engineering internship in India or eligible remote work.",
         "Availability: 10 hours weekly. No work authorization claims are supplied."]
doc = Document()
for line in lines:
    doc.add_paragraph(line)
doc.save(root / "sample_resume.docx")
c = canvas.Canvas(str(root / "sample_resume.pdf"))
for i,line in enumerate(lines):
    c.drawString(45, 790-i*28, line.replace("—", "-"))
c.save()
print("Created fictional sample PDF and DOCX.")
