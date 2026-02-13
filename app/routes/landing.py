"""
Landing page and public routes.
"""
from flask import Blueprint, render_template

landing_bp = Blueprint("landing", __name__)


@landing_bp.route("/")
def index():
    """Landing page with hero, features, testimonials."""
    return render_template("landing/index.html")
