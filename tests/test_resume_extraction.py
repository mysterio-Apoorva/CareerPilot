import io
from docx import Document
from careerpilot.models import Profile, sample_profile
from careerpilot.resume_parser import extract_resume, parse_profile, apply_extraction, validate_gpt_profile


def test_new_student_has_no_fictional_resume_facts():
    profile = Profile()
    assert profile.skills == []
    assert profile.projects == profile.education == profile.academic_stage == ""
    assert profile.graduation_year is None


def test_arbitrary_skills_and_resume_sections_come_from_document():
    text = """Student A
EDUCATION
B.Tech Mechanical Engineering, Example Institute
Expected graduation: May 2029
Third year
TECHNICAL SKILLS
Languages: Rust, Zig, Elixir, C++, C#
Tools: SolidWorks, ROS2, KiCad
PROJECTS
Autonomous rover with a custom motor controller.
EXPERIENCE
Robotics intern at Example Labs.
CERTIFICATIONS
Embedded Systems Certificate
ACHIEVEMENTS
Led the campus robotics team.
"""
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    parsed = parse_profile(extract_resume(buffer.getvalue(), "robotics.docx"))
    assert parsed.skills == ["Rust", "Zig", "Elixir", "C++", "C#", "SolidWorks", "ROS2", "KiCad"]
    assert "Mechanical Engineering" in parsed.education
    assert parsed.graduation_year == 2029
    assert parsed.academic_stage == "Third year"
    assert "motor controller" in parsed.projects
    assert "Robotics intern" in parsed.experience
    assert "Embedded Systems" in parsed.certifications
    assert "campus robotics" in parsed.achievements
    assert "Python" not in parsed.skills
    for quotes in parsed.evidence.values():
        assert all(quote in text for quote in quotes)


def test_replacing_resume_removes_old_fields_and_keeps_target_preferences():
    old = sample_profile().model_copy(update={"education":"Old degree", "experience":"Old employer"})
    new = apply_extraction(old, parse_profile("Skills: Figma, typography\nProjects\nBrand identity study."))
    assert new.skills == ["Figma", "typography"]
    assert new.projects == "Brand identity study."
    assert new.education == new.experience == new.academic_stage == ""
    assert new.graduation_year is None
    assert new.role == old.role


def test_missing_graduation_is_not_guessed_from_current_year_or_degree_range():
    parsed = parse_profile("Education\nB.Tech 2023–2027\nSkills\nRust")
    assert parsed.graduation_year is None


def test_gpt_values_need_resume_evidence_and_inferences_stay_separate():
    text = "Education\nMSc Robotics\nGraduation: 2028\nSkills: Rust\nProjects\nBuilt a rover."
    data = {
        "education":[{"quote":"MSc Robotics"}],
        "graduation_year":{"value":2028,"quote":"Graduation: 2028"},
        "skills":[{"name":"Rust","quote":"Skills: Rust"},
                  {"name":"Python","quote":"Skills: Rust"},
                  {"name":"Docker","quote":"I use Docker"}],
        "projects":[{"quote":"Built a rover."}],
        "experience":[{"quote":"Worked at NASA"}],
        "inferred_skills":["control theory"]}
    parsed = validate_gpt_profile(data, text)
    assert parsed.skills == ["Rust"]
    assert parsed.education == "MSc Robotics"
    assert parsed.projects == "Built a rover."
    assert parsed.experience == ""
    assert parsed.graduation_year == 2028
    assert "control theory" not in parsed.skills


def test_gpt_cannot_invent_graduation_from_unrelated_year():
    parsed = validate_gpt_profile({"graduation_year":{"value":2028,"quote":"Award: 2028"}}, "Award: 2028")
    assert parsed.graduation_year is None
