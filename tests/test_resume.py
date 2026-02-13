"""
Resume route tests.
"""
import pytest


def test_builder_requires_login(client):
    """Builder redirects to login when not authenticated."""
    r = client.get("/build", follow_redirects=False)
    assert r.status_code in (302, 401)
    # If redirect, should go to login
    if r.status_code == 302:
        assert "login" in r.location.lower()


def test_dashboard_requires_login(client):
    """Dashboard redirects when not authenticated."""
    r = client.get("/dashboard/", follow_redirects=False)
    assert r.status_code in (302, 401)


def test_landing_loads(client):
    """Landing page loads for anonymous users."""
    r = client.get("/")
    assert r.status_code == 200
