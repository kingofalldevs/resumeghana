"""
AI API routes: suggestions, enhance. Rate limited.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.services.ai_service import get_suggestions, enhance_section

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/suggest", methods=["POST"])
@login_required
def suggest():
    """Get AI suggestions for resume wizard step."""
    data = request.get_json() or {}
    step = int(data.get("step", 1))
    form_data = data.get("formData", data)
    result, error = get_suggestions(step, form_data, user_id=current_user.id)
    if error:
        status = 503 if "HF_API_TOKEN not set" in error or "huggingface-hub SDK is not installed" in error else 500
        return jsonify({"error": error}), status
    return jsonify(result)


@ai_bp.route("/enhance", methods=["POST"])
@login_required
def enhance():
    """Enhance a resume section with AI."""
    data = request.get_json() or {}
    section_type = data.get("section_type", "experience")
    content = data.get("content", "")
    result, error = enhance_section(section_type, content, user_id=current_user.id)
    if error:
        status = 503 if "HF_API_TOKEN not set" in error else 500
        return jsonify({"error": error}), status
    return jsonify({"enhanced": result})
