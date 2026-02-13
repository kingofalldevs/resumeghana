"""
Database models for ResumeGhana.
PostgreSQL-ready with JSON fields for flexible resume content.
"""
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import JSON
from app import db


class User(UserMixin, db.Model):
    """User account model."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    resumes = db.relationship("Resume", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    ai_usages = db.relationship("AIUsage", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


class Resume(db.Model):
    """Resume document model."""
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default="My Resume")
    template_name = db.Column(db.String(100), nullable=False, default="modern_minimal")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Future-ready: public sharing
    is_public = db.Column(db.Boolean, default=False)
    public_slug = db.Column(db.String(32), unique=True, index=True)
    views = db.Column(db.Integer, default=0)

    # Relationships
    sections = db.relationship("ResumeSection", backref="resume", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Resume {self.title} (user={self.user_id})>"


class ResumeSection(db.Model):
    """Resume section content (JSON)."""
    __tablename__ = "resume_sections"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False, index=True)
    section_type = db.Column(db.String(50), nullable=False)  # experience, education, skills, summary, etc.
    content = db.Column(JSON, nullable=False, default=dict)

    def __repr__(self):
        return f"<ResumeSection {self.section_type} (resume={self.resume_id})>"


class AIUsage(db.Model):
    """Track AI token usage per user (for billing/limits)."""
    __tablename__ = "ai_usages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tokens_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AIUsage user={self.user_id} tokens={self.tokens_used}>"
