import datetime

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_activate_org(client, org_name, code_suffix, admin_email, admin_password="Password123!"):
    resp = client.post(
        "/api/auth/register-organization",
        json={
            "organization_name": org_name,
            "admin_name": f"{org_name} Admin",
            "admin_email": admin_email,
            "admin_password": admin_password,
            "registration_number": f"REG-{code_suffix}",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    org = resp.get_json()["organization"]

    resp = client.post(f"/api/auth/verify-organization/{org['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["organization"]["verification_status"] == "MOCK_VERIFIED"

    resp = client.post(f"/api/auth/activate-organization/{org['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["organization"]["is_active"] is True

    return org


def login(client, email, password="Password123!"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def two_orgs(client):
    """Sets up two fully activated organizations, each with an admin, so
    cross-org isolation tests have real data to work with."""
    org_a = register_and_activate_org(client, "Acme Corp", "A1", "admin@acme.demo")
    org_b = register_and_activate_org(client, "Globex Inc", "B1", "admin@globex.demo")
    token_a = login(client, "admin@acme.demo")
    token_b = login(client, "admin@globex.demo")
    return {
        "org_a": org_a,
        "org_b": org_b,
        "token_a": token_a,
        "token_b": token_b,
    }


def invite_and_activate(client, admin_token, endpoint, email, full_name, org_code, extra=None):
    """Helper: admin/manager invites a user, then the user claims the invite
    via /api/auth/activate-invite (as they would after clicking an email
    link), setting their own password."""
    payload = {"email": email, "full_name": full_name}
    if extra:
        payload.update(extra)
    resp = client.post(endpoint, json=payload, headers=auth_headers(admin_token))
    assert resp.status_code == 201, resp.get_json()
    user = resp.get_json()["user"]

    resp = client.post(
        "/api/auth/activate-invite",
        json={"email": email, "organization_code": org_code, "new_password": "Password123!"},
    )
    assert resp.status_code == 200, resp.get_json()
    return user


@pytest.fixture()
def full_org_setup(client):
    """A single fully-populated, activated organization: admin, manager
    (with one employee assigned), a second unrelated manager+employee pair
    (to test cross-manager isolation), and a trainer with a course +
    assessment. Returns a dict of tokens/ids for use across test modules."""
    org = register_and_activate_org(client, "Acme Corp", "A1", "admin@acme.demo")
    admin_token = login(client, "admin@acme.demo")
    org_code = org["code"]

    manager1 = invite_and_activate(client, admin_token, "/api/admin/managers", "manager1@acme.demo", "Manager One", org_code)
    manager2 = invite_and_activate(client, admin_token, "/api/admin/managers", "manager2@acme.demo", "Manager Two", org_code)
    manager1_token = login(client, "manager1@acme.demo")
    manager2_token = login(client, "manager2@acme.demo")

    emp1 = invite_and_activate(
        client, manager1_token, "/api/admin/employees", "emp1@acme.demo", "Employee One", org_code,
        extra={"skills": [{"name": "python", "required_level": 70}]},
    )
    emp2 = invite_and_activate(
        client, manager2_token, "/api/admin/employees", "emp2@acme.demo", "Employee Two", org_code,
        extra={"skills": [{"name": "sql", "required_level": 80}]},
    )
    emp1_token = login(client, "emp1@acme.demo")
    emp2_token = login(client, "emp2@acme.demo")

    trainer_resp = client.post(
        "/api/admin/trainers",
        json={
            "email": "trainer1@acme.demo",
            "full_name": "Trainer One",
            "trainer_type": "INTERNAL",
            "availability": {"days": ["mon", "wed"], "hours_per_week": 10},
        },
        headers=auth_headers(admin_token),
    )
    assert trainer_resp.status_code == 201, trainer_resp.get_json()
    trainer_profile = trainer_resp.get_json()["trainer_profile"]
    client.post(
        "/api/auth/activate-invite",
        json={"email": "trainer1@acme.demo", "organization_code": org_code, "new_password": "Password123!"},
    )
    trainer_token = login(client, "trainer1@acme.demo")

    client.post(
        "/api/trainer/profile/domains",
        json={"domain_name": "python", "skill_name": "python", "proficiency": "EXPERT"},
        headers=auth_headers(trainer_token),
    )
    client.post(
        "/api/trainer/profile/experience",
        json={"domain": "python", "years": 5, "training_delivery_years": 3},
        headers=auth_headers(trainer_token),
    )

    course_resp = client.post(
        "/api/trainer/courses",
        json={"title": "Python Fundamentals", "domain": "python", "description": "..."},
        headers=auth_headers(trainer_token),
    )
    assert course_resp.status_code == 201
    course = course_resp.get_json()["course"]

    assessment_resp = client.post(
        "/api/trainer/assessments",
        json={
            "course_id": course["id"],
            "title": "Python Fundamentals Quiz",
            "passing_percentage": 60,
            "max_attempts": 2,
            "requires_training_completion": True,
            "min_progress_percent_required": 100,
            "questions": [
                {
                    "text": "2 + 2 = ?",
                    "marks": 1,
                    "options": [
                        {"text": "3", "is_correct": False},
                        {"text": "4", "is_correct": True},
                    ],
                },
                {
                    "text": "Python is dynamically typed?",
                    "marks": 1,
                    "options": [
                        {"text": "True", "is_correct": True},
                        {"text": "False", "is_correct": False},
                    ],
                },
            ],
        },
        headers=auth_headers(trainer_token),
    )
    assert assessment_resp.status_code == 201
    assessment = assessment_resp.get_json()["assessment"]

    return {
        "org": org,
        "org_code": org_code,
        "admin_token": admin_token,
        "manager1_token": manager1_token,
        "manager2_token": manager2_token,
        "manager1_id": manager1["id"],
        "manager2_id": manager2["id"],
        "emp1": emp1,
        "emp2": emp2,
        "emp1_token": emp1_token,
        "emp2_token": emp2_token,
        "trainer_profile": trainer_profile,
        "trainer_token": trainer_token,
        "course": course,
        "assessment": assessment,
    }
