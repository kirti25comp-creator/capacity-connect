from tests.conftest import auth_headers


def test_admin_cannot_list_departments_of_other_org(client, two_orgs):
    """Create a department in org A, then try to reach it as org B's admin."""
    resp = client.post(
        "/api/admin/departments",
        json={"name": "Engineering"},
        headers=auth_headers(two_orgs["token_a"]),
    )
    assert resp.status_code == 201
    dept_id = resp.get_json()["department"]["id"]

    # org B admin's department list must never include org A's department.
    resp_b = client.get("/api/admin/departments", headers=auth_headers(two_orgs["token_b"]))
    assert resp_b.status_code == 200
    dept_ids_b = [d["id"] for d in resp_b.get_json()["departments"]]
    assert dept_id not in dept_ids_b


def test_idor_update_department_across_orgs_is_rejected(client, two_orgs):
    """Classic IDOR check: org B admin tries to PUT/DELETE org A's department
    id directly. Must be rejected as not-found (never leak existence or allow
    the edit)."""
    resp = client.post(
        "/api/admin/departments",
        json={"name": "Engineering"},
        headers=auth_headers(two_orgs["token_a"]),
    )
    dept_id = resp.get_json()["department"]["id"]

    resp = client.put(
        f"/api/admin/departments/{dept_id}",
        json={"name": "Hacked"},
        headers=auth_headers(two_orgs["token_b"]),
    )
    assert resp.status_code == 404

    resp = client.delete(
        f"/api/admin/departments/{dept_id}",
        headers=auth_headers(two_orgs["token_b"]),
    )
    assert resp.status_code == 404

    # Confirm org A's department is untouched.
    resp = client.get("/api/admin/departments", headers=auth_headers(two_orgs["token_a"]))
    names = [d["name"] for d in resp.get_json()["departments"]]
    assert "Engineering" in names
    assert "Hacked" not in names


def test_login_scoped_by_organization_code_prevents_cross_org_login(client, two_orgs):
    """A user email is unique per-organization, not globally, so logging in
    with the wrong organization_code for a same-named account must fail."""
    resp = client.post(
        "/api/auth/login",
        json={
            "email": "admin@acme.demo",
            "password": "Password123!",
            "organization_code": two_orgs["org_b"]["code"],
        },
    )
    assert resp.status_code == 401
