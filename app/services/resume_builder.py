"""
Resume builder service: injects data into templates and generates HTML.
Uses AI to generate professional summary, polish bullets, and add career value.
"""
import json
import os
import re
from jinja2 import Template

# Template names available
TEMPLATES = [
    "modern_minimal",
    "corporate_professional",
    "creative_designer",
    "simple_ats",
]


def _load_template(template_name: str) -> str:
    """Load template HTML by name."""
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "resume_templates", f"{template_name}.html")
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return _get_fallback_template()


def _get_fallback_template() -> str:
    """Minimal fallback template."""
    return """
<div class="resume-container" style="max-width: 800px; margin: 0 auto; font-family: Inter, sans-serif;">
    <h1>{{ full_name }}</h1>
    {% if role %}<p style="color:#64748b; margin-bottom:.5rem;">{{ role }}</p>{% endif %}
    {% if summary %}<h2>Professional Summary</h2><p>{{ summary }}</p>{% endif %}
    <h2>Experience</h2>
    <div>{{ experience | safe }}</div>
    <h2>Skills</h2>
    <div>{{ skills | safe }}</div>
    <h2>Education</h2>
    <div>{{ education | safe }}</div>
    {% if career_value %}<h2>Career Objective</h2><p>{{ career_value }}</p>{% endif %}
</div>
"""


def _ai_enhance(resume_data: dict) -> dict:
    """
    Use AI to generate a professional summary, polish experience bullets,
    optimize keywords, and write a career value statement.
    Returns dict with enhanced fields. Falls back gracefully on error.
    """
    from app.services.ai_service import _hf_json

    role = resume_data.get("role", "Professional")
    name = resume_data.get("name", "Candidate")
    skills = resume_data.get("skills", "")
    experience_raw = resume_data.get("experience", "")
    education = resume_data.get("education", "")
    career_objective = resume_data.get("career_objective", "") or resume_data.get("abilities", "")
    job_level = resume_data.get("job_level", "")
    years_exp = resume_data.get("years_experience", "")

    system_prompt = """You are a senior resume writer. Given a candidate's raw resume data, produce polished, professional content.

Return ONLY valid JSON with these keys:
{
  "professional_summary": "A 2-3 sentence professional summary highlighting the candidate's experience, key strengths, and value proposition for the target role. Written in third-person implied (no 'I'). Include industry keywords.",
  "experience_bullets": ["Bullet 1", "Bullet 2", ...],
  "career_value": "A 2-3 sentence closing statement about the candidate's career goals and what unique value they bring to the target role. Forward-looking and specific."
}

Rules for experience_bullets:
- Each bullet MUST start with a strong action verb (Led, Managed, Developed, Implemented, etc.)
- Fix any grammar or spelling errors
- Add quantifiable impact where reasonable (without fabricating numbers)
- Optimize with ATS-friendly keywords for the target role
- Keep each bullet to 1-2 lines max
- Group related items and make them achievement-oriented
- Maintain the original meaning — do not invent new work history"""

    user_content = f"""Target Role: {role}
Career Level: {job_level}
Years of Experience: {years_exp}
Skills: {skills}
Career Objective: {career_objective}
Education: {education}

Raw Experience:
{experience_raw}"""

    try:
        data, _ = _hf_json(system_prompt, user_content, temperature=0.5)
        return {
            "professional_summary": data.get("professional_summary", ""),
            "experience_bullets": data.get("experience_bullets", []),
            "career_value": data.get("career_value", ""),
        }
    except Exception:
        # Graceful fallback — return empty so the builder uses raw data
        return {}


def build_resume_html(resume_data: dict, template_name: str = "modern_minimal") -> str:
    """
    Build final HTML resume by injecting data into the selected template.
    Uses AI to enhance content before rendering.
    """
    template_name = template_name if template_name in TEMPLATES else "modern_minimal"
    html = _load_template(template_name)

    # Run AI enhancement
    enhanced = _ai_enhance(resume_data)

    # Professional summary — AI-generated or fallback to user input
    summary = enhanced.get("professional_summary", "")
    if not summary:
        summary = resume_data.get("career_objective", "") or resume_data.get("abilities", "")

    # Experience — AI-polished bullets or formatted raw input
    ai_bullets = enhanced.get("experience_bullets", [])
    if ai_bullets:
        experience = _format_bullet_list(ai_bullets)
    else:
        experience = _format_experience(resume_data.get("experience", ""))

    # Career value — AI-generated closing statement
    career_value = enhanced.get("career_value", "")

    skills = _format_skills(resume_data.get("skills", ""))
    education = _format_education(resume_data.get("education", ""))

    full_name = resume_data.get("name", "Your Name")

    context = {
        "full_name": full_name,
        "summary": summary,
        "experience": experience,
        "skills": skills,
        "education": education,
        "career_value": career_value,
        "email": resume_data.get("email", ""),
        "phone": resume_data.get("phone", ""),
        "country": resume_data.get("country", ""),
        "links": resume_data.get("links", ""),
        "role": resume_data.get("role", ""),
        "certifications": resume_data.get("certifications", ""),
    }

    t = Template(html)
    return t.render(**context)


def _format_bullet_list(bullets: list) -> str:
    """Format a list of bullet strings into styled HTML."""
    if not bullets:
        return "<p>No experience listed.</p>"
    items = []
    for b in bullets:
        b = b.strip()
        if not b:
            continue
        # Remove leading bullet chars if present
        b = re.sub(r"^[•\-–—]\s*", "", b)
        items.append(f"<li>{b}</li>")
    return f'<ul>{"".join(items)}</ul>' if items else "<p>No experience listed.</p>"


def _format_experience(text: str) -> str:
    """Format experience text as HTML with proper bullets."""
    if not text:
        return "<p>No experience listed.</p>"
    # Split by section dividers or newlines
    lines = [l.strip() for l in text.replace("---", "\n").split("\n") if l.strip()]
    items = []
    for line in lines:
        line = re.sub(r"^[•\-–—]\s*", "", line)
        if line:
            items.append(f"<li>{line}</li>")
    return f'<ul>{"".join(items)}</ul>' if items else f"<p>{text}</p>"


def _format_skills(text: str) -> str:
    """Format skills as HTML tags."""
    if not text:
        return "<p>No skills listed.</p>"
    # Split on commas, semicolons, or newlines
    parts = [p.strip() for p in re.split(r"[,;\n]+", text) if p.strip()]
    tags = " ".join(f'<span class="skill-tag">{s}</span>' for s in parts)
    return f'<div class="skills">{tags}</div>' if tags else f"<p>{text}</p>"


def _format_education(text: str) -> str:
    """Format education as HTML."""
    if not text:
        return "<p>No education listed.</p>"
    lines = [l.strip() for l in text.replace("---", "\n").split("\n") if l.strip()]
    return "<br>".join(lines) if lines else f"<p>{text}</p>"
