"""
Utility functions for ResumeGhana.
"""
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return generate_password_hash(password, method="scrypt")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)
