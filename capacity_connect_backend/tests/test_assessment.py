from tests.conftest import auth_headers


def _assign_and_complete(client, s):
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
    enrollment = assign_resp.get_json()["enrollments"][0]
    return enrollment


def test_assessment_blocked_until_training_complete(client, full_org_setup):
    s = full_org_setup
    enrollment = _assign_and_complete(client, s)

    get_resp = client.get(f"/api/assessments/{s['assessment']['id']}", headers=auth_headers(s["emp1_token"]))
    assert get_resp.status_code == 200
    questions = get_resp.get_json()["assessment"]["questions"]
    assert "is_correct" not in questions[0]["options"][0]  # answers never revealed pre-submission

    answers = {q["id"]: q["options"][0]["id"] for q in questions}
    submit_resp = client.post(
        f"/api/assessments/{s['assessment']['id']}/submit",
        json={"enrollment_id": enrollment["id"], "answers": answers},
        headers=auth_headers(s["emp1_token"]),
    )
    assert submit_resp.status_code == 403  # training not yet 100% complete


def test_assessment_scoring_and_pass_fail(client, full_org_setup):
    s = full_org_setup
    enrollment = _assign_and_complete(client, s)

    client.put(
        f"/api/training/enrollments/{enrollment['id']}/progress",
        json={"progress_percent": 100},
        headers=auth_headers(s["emp1_token"]),
    )

    get_resp = client.get(f"/api/assessments/{s['assessment']['id']}", headers=auth_headers(s["emp1_token"]))
    questions = get_resp.get_json()["assessment"]["questions"]

    q1 = next(q for q in questions if "2 + 2" in q["text"])
    q2 = next(q for q in questions if "dynamically typed" in q["text"])

    # Correct answers are known from the fixture's question definitions:
    # q1's correct option is "4" (added second, so options[1]); q2's correct
    # option is "True" (added first, so options[0]). The employee-facing
    # response never reveals is_correct, so we rely on the fixture's known
    # insertion order rather than any answer-revealing endpoint.
    answers = {q1["id"]: q1["options"][1]["id"], q2["id"]: q2["options"][0]["id"]}

    submit_resp = client.post(
        f"/api/assessments/{s['assessment']['id']}/submit",
        json={"enrollment_id": enrollment["id"], "answers": answers},
        headers=auth_headers(s["emp1_token"]),
    )
    assert submit_resp.status_code == 201
    result = submit_resp.get_json()["result"]
    assert result["score"] == 2
    assert result["percentage"] == 100.0
    assert result["passed"] is True
    return result


def test_certificate_issued_only_after_completed_enrollment(client, full_org_setup):
    s = full_org_setup
    enrollment = _assign_and_complete(client, s)

    # Not yet completed -> issuance rejected
    resp = client.post(
        "/api/certificates/issue",
        json={"enrollment_id": enrollment["id"]},
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 400

    client.put(
        f"/api/training/enrollments/{enrollment['id']}/progress",
        json={"progress_percent": 100},
        headers=auth_headers(s["emp1_token"]),
    )

    resp = client.post(
        "/api/certificates/issue",
        json={"enrollment_id": enrollment["id"]},
        headers=auth_headers(s["manager1_token"]),
    )
    assert resp.status_code == 201
    cert = resp.get_json()["certificate"]
    assert cert["employee_id"] == s["emp1"]["id"]

    resp = client.get("/api/employee/certificates", headers=auth_headers(s["emp1_token"]))
    ids = [c["id"] for c in resp.get_json()["certificates"]]
    assert cert["id"] in ids


def test_manager2_cannot_issue_certificate_for_manager1s_employee(client, full_org_setup):
    s = full_org_setup
    enrollment = _assign_and_complete(client, s)
    client.put(
        f"/api/training/enrollments/{enrollment['id']}/progress",
        json={"progress_percent": 100},
        headers=auth_headers(s["emp1_token"]),
    )
    resp = client.post(
        "/api/certificates/issue",
        json={"enrollment_id": enrollment["id"]},
        headers=auth_headers(s["manager2_token"]),
    )
    assert resp.status_code == 403
