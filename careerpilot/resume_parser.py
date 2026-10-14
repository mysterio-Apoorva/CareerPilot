import io
import re

SKILLS = ["Python", "SQL", "Git", "machine learning", "deep learning", "statistics", "probability",
          "PyTorch", "TensorFlow", "Docker", "deployment", "evaluation", "JavaScript", "React",
          "data analysis", "Excel", "communication", "research", "NLP", "LLMs", "testing"]


def extract_resume(data: bytes, filename: str):
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Please upload a file smaller than 5 MB.")
    try:
        if filename.lower().endswith(".pdf"):
            from pypdf import PdfReader
            if not data.startswith(b"%PDF"):
                raise ValueError("Not a valid PDF.")
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages[:15])
        elif filename.lower().endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
            text += "\n" + "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        else:
            raise ValueError("Upload a PDF or DOCX resume.")
    except Exception as exc:
        raise ValueError("Could not read this resume. Use the manual profile fields below.") from exc
    if len(text.strip()) < 30:
        raise ValueError("No readable text found. Scanned PDFs need OCR; use manual entry for this MVP.")
    return text[:24000]


def explicit_skills(text):
    return [skill for skill in SKILLS if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text, re.I)]
