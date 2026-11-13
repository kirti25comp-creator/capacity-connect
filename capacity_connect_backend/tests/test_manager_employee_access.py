from tests.conftest import auth_headers


def test_manager_sees_only_own_employees(client, full_org_setup):
    s = full_org_setup
    resp = client.get("/api/manager/employees", headers=auth_headers(s["manager1_token"]))
    assert resp.status_code == 200
    emails = [e["email"] for e in resp.get_json()["employees"]]
    assert s["emp1"]["email"] in emails
    assert s["emp2"]["email"] not in emails


def test_manager_cannot_edit_another_managers_employee(client, full_org_setup):
    s = full_org_setup
    resp = client.put(
        f"/api/manager/employees/{s['emp2']['id']}",
        json={"job_title": "Hacked Title"},
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 403


def test_manager_cannot_view_another_managers_employee_progress(client, full_org_setup):
    s = full_org_setup
    resp = client.get(
        f"/api/manager/employees/{s['emp2']['id']}/progress",
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 403


def test_manager_cannot_assign_training_to_non_owned_employee(client, full_org_setup):
    s = full_org_setup
    req_resp = client.post(
        "/api/manager/training-requirements",
        json={
            "subject": "Python Fundamentals",
            "domain": "python",
            "required_skills": ["python"],
            "start_date": "2026-09-01",
            "end_date": "2026-12-01",
        },
        headers=auth_headers(s["manager1_token"]),
    )
    assert req_resp.status_code == 201
    req_id = req_resp.get_json()["training_requirement"]["id"]

    resp = client.post(
        f"/api/manager/training-requirements/{req_id}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp2"]["id"]],  # belongs to manager2, not manager1
        },
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 403
    assert "invalid" in resp.get_json()


def test_employee_cannot_access_manager_endpoints(client, full_org_setup):
    s = full_org_setup
    resp = client.get("/api/manager/employees", headers=auth_headers(s["emp1_token"]))
    assert resp.status_code == 403
