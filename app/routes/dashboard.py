"""
Dashboard routes: view resumes, create new, usage stats.
"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models import Resume, AIUsage
from sqlalchemy import func

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    """Dashboard home: resume cards and usage stats."""
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.updated_at.desc()).limit(20).all()
    total_tokens = (
        db.session.query(func.sum(AIUsage.tokens_used))
        .filter(AIUsage.user_id == current_user.id)
        .scalar()
        or 0
    )
    return render_template(
        "dashboard/index.html",
        resumes=resumes,
        total_tokens=int(total_tokens),
    )
