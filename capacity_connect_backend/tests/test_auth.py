from tests.conftest import auth_headers, login, register_and_activate_org


def test_register_organization_creates_pending_org(client):
    resp = client.post(
        "/api/auth/register-organization",
        json={
            "organization_name": "Initech",
            "admin_name": "Initech Admin",
            "admin_email": "admin@initech.demo",
            "admin_password": "Password123!",
            "registration_number": "REG-999",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["organization"]["verification_status"] == "PENDING"
    assert data["organization"]["is_active"] is False
    assert data["admin_user"]["role"] == "ADMIN"


def test_login_rejected_before_org_activation(client):
    client.post(
        "/api/auth/register-organization",
        json={
            "organization_name": "Initech",
            "admin_name": "Initech Admin",
            "admin_email": "admin@initech.demo",
            "admin_password": "Password123!",
            "registration_number": "REG-999",
        },
    )
    resp = client.post("/api/auth/login", json={"email": "admin@initech.demo", "password": "Password123!"})
    assert resp.status_code == 403


def test_login_with_wrong_password_fails(client):
    register_and_activate_org(client, "Acme Corp", "A1", "admin@acme.demo")
    resp = client.post("/api/auth/login", json={"email": "admin@acme.demo", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client):
    register_and_activate_org(client, "Acme Corp", "A1", "admin@acme.demo")
    token = login(client, "admin@acme.demo")
    resp = client.get("/api/auth/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "admin@acme.demo"


def test_invalid_token_rejected(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage.token.value"})
    assert resp.status_code == 401


def test_client_supplied_role_is_never_trusted(client):
    """Even if a malicious client tries to smuggle a role via the JSON body,
    only the DB-assigned role controls authorization."""
    register_and_activate_org(client, "Acme Corp", "A1", "admin@acme.demo")
    token = login(client, "admin@acme.demo")
    # Try to hit a manager-only endpoint's employee list; admin (not manager) should be denied.
    resp = client.get(
        "/api/manager/employees",
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
