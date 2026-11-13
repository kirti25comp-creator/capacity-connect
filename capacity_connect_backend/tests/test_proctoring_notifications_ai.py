from tests.conftest import auth_headers


def test_notifications_are_scoped_to_the_authenticated_user_only(client, full_org_setup):
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
    client.post(
        f"/api/manager/training-requirements/{req_id}/assign",
        json={
            "trainer_id": s["trainer_profile"]["id"],
            "course_id": s["course"]["id"],
            "employee_ids": [s["emp1"]["id"]],
        },
        headers=auth_headers(s["manager1_token"]),
    )

    emp1_notifs = client.get("/api/notifications", headers=auth_headers(s["emp1_token"])).get_json()["notifications"]
    emp2_notifs = client.get("/api/notifications", headers=auth_headers(s["emp2_token"])).get_json()["notifications"]
    assert any(n["notif_type"] == "TRAINING_ASSIGNED" for n in emp1_notifs)
    assert not any(n["notif_type"] == "TRAINING_ASSIGNED" for n in emp2_notifs)


def test_proctoring_event_never_declares_cheating(client, full_org_setup):
    """Proctoring status must only ever be CLEAR or REVIEW_REQUIRED."""
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
    client.put(
        f"/api/training/enrollments/{enrollment_id}/progress",
        json={"progress_percent": 100},
        headers=auth_headers(s["emp1_token"]),
    )
    questions = client.get(
        f"/api/assessments/{s['assessment']['id']}", headers=auth_headers(s["emp1_token"])
    ).get_json()["assessment"]["questions"]
    answers = {q["id"]: q["options"][0]["id"] for q in questions}
    submit_resp = client.post(
        f"/api/assessments/{s['assessment']['id']}/submit",
        json={"enrollment_id": enrollment_id, "answers": answers},
        headers=auth_headers(s["emp1_token"]),
    )
    result_id = submit_resp.get_json()["result"]["id"]

    resp = client.post(
        f"/api/assessments/results/{result_id}/proctoring-events",
        json={"event_type": "MULTIPLE_FACES"},
        headers=auth_headers(s["emp1_token"]),
    )
    assert resp.status_code == 201
    event = resp.get_json()["event"]
    assert event["status"] in ("CLEAR", "REVIEW_REQUIRED")
    assert event["status"] == "REVIEW_REQUIRED"  # MULTIPLE_FACES is HIGH severity

    summary_resp = client.get(
        f"/api/assessments/results/{result_id}/proctoring-summary", headers=auth_headers(s["manager1_token"])
    )
    assert summary_resp.status_code == 200
    assert summary_resp.get_json()["overall_status"] == "REVIEW_REQUIRED"


def test_ai_manager_scope_vs_admin_scope(client, full_org_setup):
    s = full_org_setup

    resp = client.post(
        "/api/ai/ask", json={"question": "What's our team's average score?"}, headers=auth_headers(s["manager1_token"])
    )
    assert resp.status_code == 200
    assert resp.get_json()["intent"] == "TEAM_AVERAGE_SCORE"

    resp = client.post(
        "/api/ai/ask",
        json={"question": "Which manager has the best performance?"},
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 200
    assert "error" in resp.get_json()["verified_data"]  # managers may not query org-wide manager rankings

    resp = client.post(
        "/api/ai/ask",
        json={"question": "Which manager has the best performance?"},
        headers=auth_headers(s["admin_token"]),
    )
    assert resp.status_code == 200
    assert "manager_rankings" in resp.get_json()["verified_data"]


def test_ai_endpoint_forbidden_for_employees_and_trainers(client, full_org_setup):
    s = full_org_setup
    resp = client.post("/api/ai/ask", json={"question": "who failed?"}, headers=auth_headers(s["emp1_token"]))
    assert resp.status_code == 403
    resp = client.post("/api/ai/ask", json={"question": "who failed?"}, headers=auth_headers(s["trainer_token"]))
    assert resp.status_code == 403
