from tests.conftest import auth_headers


def test_manager_can_recompute_own_employee_skill_gaps(client, full_org_setup):
    s = full_org_setup
    resp = client.post(
        f"/api/competency/employees/{s['emp1']['id']}/recompute",
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 200
    report = resp.get_json()["skill_gap_report"]
    # emp1 has skill "python" with required_level 70 and no assessment history yet
    python_entry = next(r for r in report if r["skill_name"] == "python")
    assert python_entry["gap_level"] == "MAJOR"  # 0 assessed vs 70 required


def test_manager_cannot_recompute_another_managers_employee(client, full_org_setup):
    s = full_org_setup
    resp = client.post(
        f"/api/competency/employees/{s['emp2']['id']}/recompute",
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 403


def test_employee_can_view_own_skill_gaps_after_recompute(client, full_org_setup):
    s = full_org_setup
    client.post(f"/api/competency/employees/{s['emp1']['id']}/recompute", headers=auth_headers(s["manager1_token"]))
    resp = client.get("/api/employee/skill-gaps", headers=auth_headers(s["emp1_token"]))
    assert resp.status_code == 200
    assert len(resp.get_json()["skill_gaps"]) >= 1


def test_trainer_quality_alert_requires_minimum_feedback_count(client, full_org_setup):
    """A single bad piece of feedback should NOT raise a trainer quality
    alert - only a repeated pattern (>= MIN_FEEDBACK_COUNT_FOR_ALERT) should."""
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
    req_id = req_resp.get_json()["training_requirement"]["id"]
    assign_resp = client.post(
        f"/api/manager/training-requirements/{req_id}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    enrollment_id = assign_resp.get_json()["enrollments"][0]["id"]

    resp = client.post(
        "/api/employee/feedback",
        json={"enrollment_id": enrollment_id, "trainer_rating": 1, "course_rating": 1, "comments": "poor"},
        headers=auth_headers(s["emp1_token"]),
    )
    assert resp.status_code == 201

    alerts_resp = client.get("/api/manager/trainer-quality-alerts", headers=auth_headers(s["manager1_token"]))
    assert alerts_resp.status_code == 200
    assert alerts_resp.get_json()["alerts"] == []  # not enough feedback yet to alert


def test_manager_can_remove_trainer_from_own_assignment(client, full_org_setup):
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
    req_id = req_resp.get_json()["training_requirement"]["id"]
    assign_resp = client.post(
        f"/api/manager/training-requirements/{req_id}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    enrollment_id = assign_resp.get_json()["enrollments"][0]["id"]

    resp = client.post(
        f"/api/manager/enrollments/{enrollment_id}/remove-trainer",
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["enrollment"]["trainer_id"] is None


def test_admin_can_suspend_trainer_organization_wide(client, full_org_setup):
    s = full_org_setup
    resp = client.post(
        f"/api/admin/trainers/{s['trainer_profile']['id']}/suspend",
        headers=auth_headers(s["admin_token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["trainer_profile"]["is_active"] is False


def test_manager_cannot_suspend_trainer(client, full_org_setup):
    s = full_org_setup
    resp = client.post(
        f"/api/admin/trainers/{s['trainer_profile']['id']}/suspend",
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 403
