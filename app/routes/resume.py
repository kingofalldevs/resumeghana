"""
Resume routes: builder, template picker, save, view, download.
"""
import os
import base64
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from app import db
from app.models import Resume, ResumeSection
from app.services.resume_builder import build_resume_html, TEMPLATES

resume_bp = Blueprint("resume", __name__)


def _extract_text_from_pdf(file):
    """Extract text from uploaded PDF."""
    try:
        reader = PdfReader(file)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return ""


def _parse_resume_text(text):
    """Parse resume text with AI and return structured data."""
    from app.services.ai_service import get_suggestions
    # Simple fallback - in production you'd use a dedicated parse API
    return {
        "name": "",
        "role": "",
        "skills": text[:500] if text else "",
        "experience": text[500:1500] if len(text) > 500 else text,
        "education": text[1500:] if len(text) > 1500 else "",
    }


@resume_bp.route("/build", methods=["GET", "POST"])
@login_required
def builder():
    """Multi-step resume builder (6 steps including template choice)."""
    if request.method == "POST":
        resume_data = {}
        if "resume_file" in request.files:
            file = request.files["resume_file"]
            if file.filename:
                text = _extract_text_from_pdf(file)
                if text:
                    resume_data = _parse_resume_text(text)

        if not resume_data:
            experience = request.form.get("experience")
            if not experience:
                parts = []
                for i in range(5):
                    co = request.form.get(f"experience_{i}_company", "").strip()
                    yr = request.form.get(f"experience_{i}_years", "").strip()
                    desc = request.form.get(f"experience_{i}_description", "").strip()
                    if co or yr or desc:
                        parts.append(f"{co} ({yr})\n{desc}")
                experience = "\n\n---\n\n".join(parts)
            education = request.form.get("education")
            if not education:
                edu_parts = []
                for i in range(5):
                    sch = request.form.get(f"education_{i}_school", "").strip()
                    dur = request.form.get(f"education_{i}_duration", "").strip()
                    sk = request.form.get(f"education_{i}_skills", "").strip()
                    if sch or dur or sk:
                        edu_parts.append(f"{sch} ({dur})\n{sk}")
                education = "\n\n---\n\n".join(edu_parts)
            resume_data = {
                "name": request.form.get("name"),
                "phone": request.form.get("phone"),
                "email": request.form.get("email"),
                "country": request.form.get("country"),
                "job_type": request.form.get("job_type"),
                "job_level": request.form.get("job_level"),
                "years_experience": request.form.get("years_experience"),
                "location_target": request.form.get("location_target"),
                "functional_focus": request.form.get("functional_focus"),
                "role": request.form.get("role"),
                "skills": request.form.get("skills"),
                "abilities": request.form.get("abilities"),
                "career_objective": request.form.get("career_objective"),
                "experience": experience,
                "education": education,
                "certifications": request.form.get("certifications"),
                "relevant_coursework": request.form.get("relevant_coursework"),
                "links": request.form.get("links"),
            }
            if "profile_photo" in request.files:
                photo = request.files["profile_photo"]
                if photo.filename:
                    fn = secure_filename(photo.filename)
                    photo.save(os.path.join(current_app.config["UPLOAD_FOLDER"], fn))
                    resume_data["photo_filename"] = fn

        template_name = request.form.get("template_name", "modern_minimal")
        resume_data["template_name"] = template_name

        if not resume_data.get("skills") or not resume_data.get("experience"):
            flash("Please provide at least Skills and Experience.", "error")
            return redirect(url_for("resume.builder"))

        session["resume_data"] = resume_data
        return redirect(url_for("resume.template_picker"))

    return render_template("builder.html", templates=TEMPLATES)


@resume_bp.route("/templates")
@login_required
def template_picker():
    """Show template picker after resume form is filled."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("Please fill in your resume details first.", "error")
        return redirect(url_for("resume.builder"))

    template_info = {
        "modern_minimal": {
            "label": "Modern Minimal",
            "desc": "Simple, elegant, and focused on readability. Best for tech and product roles.",
        },
        "corporate_professional": {
            "label": "Corporate Professional",
            "desc": "Crisp formal layout for finance, operations, and leadership positions.",
        },
        "creative_designer": {
            "label": "Creative Designer",
            "desc": "Expressive format with visual flair while staying ATS-safe.",
        },
        "simple_ats": {
            "label": "Simple ATS",
            "desc": "Maximum compatibility with applicant tracking systems. Clean and direct.",
        },
    }
    return render_template(
        "template_picker.html",
        templates=TEMPLATES,
        template_info=template_info,
        resume_name=resume_data.get("name", "Your Resume"),
    )


@resume_bp.route("/templates/preview", methods=["POST"])
@login_required
def template_preview():
    """AJAX endpoint: render resume with a given template and return HTML."""
    resume_data = session.get("resume_data")
    if not resume_data:
        return jsonify({"error": "No resume data in session."}), 400

    data = request.get_json() or {}
    template_name = data.get("template_name", "modern_minimal")
    if template_name not in TEMPLATES:
        template_name = "modern_minimal"

    html = build_resume_html(resume_data, template_name)
    return jsonify({"html": html})


@resume_bp.route("/templates/select", methods=["POST"])
@login_required
def template_select():
    """Final template selection: save resume and redirect to view."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("Session expired. Please start over.", "error")
        return redirect(url_for("resume.builder"))

    template_name = request.form.get("template_name", "modern_minimal")
    if template_name not in TEMPLATES:
        template_name = "modern_minimal"

    resume_data["template_name"] = template_name
    session["resume_data"] = resume_data

    # Save to database
    title = f"Resume - {resume_data.get('role', 'Untitled')}"
    resume = Resume(
        user_id=current_user.id,
        title=title,
        template_name=template_name,
    )
    db.session.add(resume)
    db.session.flush()

    sections_data = [
        ("personal", {"name": resume_data.get("name"), "email": resume_data.get("email"), "phone": resume_data.get("phone"), "country": resume_data.get("country"), "links": resume_data.get("links"), "role": resume_data.get("role")}),
        ("summary", {"raw": resume_data.get("career_objective", "") or resume_data.get("abilities", "")}),
        ("experience", {"raw": resume_data.get("experience", "")}),
        ("education", {"raw": resume_data.get("education", "")}),
        ("skills", {"raw": resume_data.get("skills", "")}),
    ]
    for section_type, content in sections_data:
        sec = ResumeSection(resume_id=resume.id, section_type=section_type, content=content)
        db.session.add(sec)

    db.session.commit()

    # Render with chosen template and show
    html = build_resume_html(resume_data, template_name)
    flash("Resume created and saved to dashboard.", "success")
    return render_template("tailored.html", content=html, resume_id=resume.id)


@resume_bp.route("/save", methods=["POST"])
@login_required
def save():
    """Save resume from session to database."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("No resume data to save.", "error")
        return redirect(url_for("resume.builder"))

    title = request.form.get("title", f"Resume - {resume_data.get('role', 'Untitled')}")
    template_name = resume_data.get("template_name", "modern_minimal")

    resume = Resume(
        user_id=current_user.id,
        title=title,
        template_name=template_name,
    )
    db.session.add(resume)
    db.session.flush()

    # Store full resume data in sections for easy retrieval
    sections_data = [
        ("personal", {"name": resume_data.get("name"), "email": resume_data.get("email"), "phone": resume_data.get("phone"), "country": resume_data.get("country"), "links": resume_data.get("links"), "role": resume_data.get("role")}),
        ("summary", {"raw": resume_data.get("career_objective", "") or resume_data.get("abilities", "")}),
        ("experience", {"raw": resume_data.get("experience", "")}),
        ("education", {"raw": resume_data.get("education", "")}),
        ("skills", {"raw": resume_data.get("skills", "")}),
    ]
    for section_type, content in sections_data:
        sec = ResumeSection(resume_id=resume.id, section_type=section_type, content=content)
        db.session.add(sec)

    db.session.commit()
    flash("Resume saved to dashboard.", "success")
    return redirect(url_for("dashboard.index"))


def _resume_to_data(resume):
    """Build resume_data dict from Resume model for template rendering."""
    data = {"name": resume.title, "role": "", "email": "", "phone": "", "country": "", "links": "", "career_objective": "", "experience": "", "education": "", "skills": ""}
    for sec in resume.sections:
        c = sec.content or {}
        if sec.section_type == "personal":
            data["name"] = c.get("name", data["name"])
            data["role"] = c.get("role", "")
            data["email"] = c.get("email", "")
            data["phone"] = c.get("phone", "")
            data["country"] = c.get("country", "")
            data["links"] = c.get("links", "")
        elif sec.section_type == "summary":
            data["career_objective"] = c.get("raw", c.get("text", ""))
        else:
            data[sec.section_type] = c.get("raw", c.get("text", ""))
    return data


@resume_bp.route("/resume/<int:id>")
@login_required
def view(id):
    """View a saved resume."""
    resume = Resume.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = _resume_to_data(resume)
    html = build_resume_html(data, resume.template_name)
    return render_template("tailored.html", content=html)


@resume_bp.route("/resume/<int:id>/download")
@login_required
def download(id):
    """Download resume as HTML (print to PDF from browser)."""
    resume = Resume.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = _resume_to_data(resume)
    html = build_resume_html(data, resume.template_name)
    return render_template("tailored.html", content=html)


# Legacy route for PDF upload from landing
@resume_bp.route("/build/upload", methods=["POST"])
def build_upload():
    """Handle PDF upload from landing - redirect to login if needed."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("resume.builder")))
    return redirect(url_for("resume.builder"))
