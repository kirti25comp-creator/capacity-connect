import datetime

from tests.conftest import auth_headers


def _create_requirement(client, token, **overrides):
    payload = {
        "subject": "Python Fundamentals",
        "domain": "python",
        "required_skills": ["python"],
        "min_experience_years": 3,
        "min_training_experience_years": 2,
        "availability_needed": {"days": ["mon"], "hours_per_week": 5},
        "start_date": "2026-09-01",
        "end_date": "2026-12-01",
    }
    payload.update(overrides)
    resp = client.post("/api/manager/training-requirements", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["training_requirement"]


def test_trainer_matching_uses_real_db_data_not_hardcoded(client, full_org_setup):
    s = full_org_setup
    req = _create_requirement(client, s["manager1_token"])

    resp = client.get(
        f"/api/manager/training-requirements/{req['id']}/matches", headers=auth_headers(s["manager1_token"])
    )
    assert resp.status_code == 200
    matches = resp.get_json()["matches"]
    assert len(matches) == 1
    match = matches[0]
    assert match["trainer_id"] == s["trainer_profile"]["id"]
    assert match["rank"] == 1
    assert match["match_percentage"] > 0
    assert "domain: python" in match["matched_criteria"]


def test_manager_cannot_see_another_managers_requirement_matches(client, full_org_setup):
    s = full_org_setup
    req = _create_requirement(client, s["manager1_token"])
    resp = client.get(
        f"/api/manager/training-requirements/{req['id']}/matches", headers=auth_headers(s["manager2_token"])
    )
    assert resp.status_code == 404


def test_assign_training_creates_enrollment_and_notifies_employee(client, full_org_setup):
    s = full_org_setup
    req = _create_requirement(client, s["manager1_token"])

    resp = client.post(
        f"/api/manager/training-requirements/{req['id']}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 201
    enrollment = resp.get_json()["enrollments"][0]
    assert enrollment["status"] == "ASSIGNED"

    notif_resp = client.get("/api/notifications", headers=auth_headers(s["emp1_token"]))
    types = [n["notif_type"] for n in notif_resp.get_json()["notifications"]]
    assert "TRAINING_ASSIGNED" in types

    return enrollment


def test_progress_update_transitions_lifecycle(client, full_org_setup):
    s = full_org_setup
    req = _create_requirement(client, s["manager1_token"], end_date="2027-01-01")
    assign_resp = client.post(
        f"/api/manager/training-requirements/{req['id']}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    enrollment_id = assign_resp.get_json()["enrollments"][0]["id"]

    resp = client.put(
        f"/api/training/enrollments/{enrollment_id}/progress",
        json={"progress_percent": 40},
        headers=auth_headers(s["emp1_token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["enrollment"]["status"] == "IN_PROGRESS"

    resp = client.put(
        f"/api/training/enrollments/{enrollment_id}/progress",
        json={"progress_percent": 100},
        headers=auth_headers(s["emp1_token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["enrollment"]["status"] == "COMPLETED"


def test_deadline_sweep_expires_overdue_enrollments(client, full_org_setup):
    s = full_org_setup
    # end_date in the past
    req = _create_requirement(client, s["manager1_token"], start_date="2020-01-01", end_date="2020-02-01")
    assign_resp = client.post(
        f"/api/manager/training-requirements/{req['id']}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    enrollment_id = assign_resp.get_json()["enrollments"][0]["id"]

    resp = client.post("/api/training/deadline-sweep", headers=auth_headers(s["admin_token"]))
    assert resp.status_code == 200
    expired_ids = [e["id"] for e in resp.get_json()["expired_enrollments"]]
    assert enrollment_id in expired_ids

    resp = client.put(
        f"/api/training/enrollments/{enrollment_id}/progress",
        json={"progress_percent": 50},
        headers=auth_headers(s["emp1_token"]),
    )
    assert resp.status_code == 400  # cannot progress a DEADLINE_EXPIRED enrollment without explicit extension


def test_manager_can_extend_expired_deadline_explicitly(client, full_org_setup):
    s = full_org_setup
    req = _create_requirement(client, s["manager1_token"], start_date="2020-01-01", end_date="2020-02-01")
    assign_resp = client.post(
        f"/api/manager/training-requirements/{req['id']}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )
    enrollment_id = assign_resp.get_json()["enrollments"][0]["id"]
    client.post("/api/training/deadline-sweep", headers=auth_headers(s["admin_token"]))

    future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    resp = client.post(
        f"/api/training/enrollments/{enrollment_id}/extend",
        json={"new_end_date": future_date},
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["enrollment"]["status"] in ("ASSIGNED", "IN_PROGRESS")
