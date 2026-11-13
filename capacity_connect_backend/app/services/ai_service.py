"""CAPACITY AI backend.

Pipeline: User Question -> Intent Detection -> RBAC Validation ->
Authorized Database Query -> Verified Data -> Natural Language Response.

`detect_intent` is pure (keyword-based DEMO mode, no external calls) so it is
unit-testable in isolation. The query functions always take the *authenticated,
DB-loaded* user object and scope every query by that user's role/org - a
Manager can only ever see their own team's data, an Admin sees their whole
organization, and nothing else. If ANTHROPIC_API_KEY is configured, callers may
swap in a real LLM for the natural-language phrasing step (see
route in api/ai.py) - but intent -> query -> authorization always happens
through this same DB-scoped path first; the LLM (if used) only rephrases
`verified_data` computed here into prose and is never allowed to invent
figures or execute unscoped queries itself.
"""

import re

from sqlalchemy import func

from app.extensions import db
from app.models.assessment import Assessment, AssessmentResult
from app.models.core import User
from app.models.employee import EmployeeProfile, ManagerEmployeeAssignment
from app.models.misc import CompetencyRecord
from app.models.training import Course, Enrollment
from app.services.ai_intent import INTENTS, detect_intent, render_natural_language_response  # noqa: F401


def _managed_employee_ids(manager):
    rows = ManagerEmployeeAssignment.query.filter_by(
        organization_id=manager.organization_id, manager_id=manager.id
    ).all()
    return [r.employee_id for r in rows]


def _extract_course_title(question):
    match = re.search(r"(?:course|assessment)\s+(?:called|named|titled)?\s*[\"']?([A-Za-z0-9 \-]+)[\"']?", question, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def query_who_failed_course(user, question):
    """Manager: scoped to their team. Admin: org-wide."""
    title_fragment = _extract_course_title(question)

    q = (
        db.session.query(AssessmentResult, User, Assessment)
        .join(User, AssessmentResult.employee_id == User.id)
        .join(Assessment, AssessmentResult.assessment_id == Assessment.id)
        .filter(AssessmentResult.organization_id == user.organization_id)
        .filter(AssessmentResult.passed.is_(False))
    )

    if title_fragment:
        q = q.filter(Assessment.title.ilike(f"%{title_fragment}%"))

    if user.role == "MANAGER":
        emp_ids = _managed_employee_ids(user)
        if not emp_ids:
            return {"employees": [], "note": "You have no employees assigned to you."}
        q = q.filter(AssessmentResult.employee_id.in_(emp_ids))
    elif user.role != "ADMIN":
        return {"error": "Only MANAGER or ADMIN roles may query this."}

    rows = q.all()
    employees = [
        {"employee_name": u.full_name, "assessment": a.title, "percentage": r.percentage}
        for (r, u, a) in rows
    ]
    return {"employees": employees, "count": len(employees)}


def query_who_needs_retraining(user, question):
    q = CompetencyRecord.query.filter_by(organization_id=user.organization_id).filter(
        CompetencyRecord.gap_level == "MAJOR"
    )

    if user.role == "MANAGER":
        emp_ids = _managed_employee_ids(user)
        if not emp_ids:
            return {"employees": [], "note": "You have no employees assigned to you."}
        q = q.filter(CompetencyRecord.employee_id.in_(emp_ids))
    elif user.role != "ADMIN":
        return {"error": "Only MANAGER or ADMIN roles may query this."}

    records = q.all()
    user_ids = list({r.employee_id for r in records})
    users_by_id = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    results = [
        {
            "employee_name": users_by_id[r.employee_id].full_name if r.employee_id in users_by_id else r.employee_id,
            "skill": r.skill_name,
            "gap_level": r.gap_level,
        }
        for r in records
    ]
    return {"employees_needing_retraining": results, "count": len(results)}


def query_team_average_score(user, question):
    q = db.session.query(func.avg(AssessmentResult.percentage)).filter(
        AssessmentResult.organization_id == user.organization_id
    )

    if user.role == "MANAGER":
        emp_ids = _managed_employee_ids(user)
        if not emp_ids:
            return {"average_score": None, "note": "You have no employees assigned to you."}
        q = q.filter(AssessmentResult.employee_id.in_(emp_ids))
    elif user.role != "ADMIN":
        return {"error": "Only MANAGER or ADMIN roles may query this."}

    avg = q.scalar()
    return {"average_score": round(avg, 2) if avg is not None else None}


def query_department_pass_rate(user, question):
    if user.role != "ADMIN":
        return {"error": "Only ADMIN may query organization-wide department statistics."}

    rows = (
        db.session.query(EmployeeProfile.department_id, AssessmentResult.passed)
        .join(User, EmployeeProfile.user_id == User.id)
        .join(AssessmentResult, AssessmentResult.employee_id == User.id)
        .filter(EmployeeProfile.organization_id == user.organization_id)
        .all()
    )

    stats = {}
    for dept_id, passed in rows:
        d = stats.setdefault(dept_id, {"total": 0, "passed": 0})
        d["total"] += 1
        if passed:
            d["passed"] += 1

    result = [
        {
            "department_id": dept_id,
            "pass_rate": round(v["passed"] / v["total"] * 100, 2) if v["total"] else 0,
            "total_assessments": v["total"],
        }
        for dept_id, v in stats.items()
    ]
    return {"department_pass_rates": result}


def query_best_performing_manager(user, question):
    if user.role != "ADMIN":
        return {"error": "Only ADMIN may query organization-wide manager performance."}

    assignments = ManagerEmployeeAssignment.query.filter_by(organization_id=user.organization_id).all()
    manager_to_employees = {}
    for a in assignments:
        manager_to_employees.setdefault(a.manager_id, []).append(a.employee_id)

    scores = []
    for manager_id, emp_ids in manager_to_employees.items():
        avg = (
            db.session.query(func.avg(AssessmentResult.percentage))
            .filter(AssessmentResult.employee_id.in_(emp_ids))
            .filter(AssessmentResult.organization_id == user.organization_id)
            .scalar()
        )
        manager = db.session.get(User, manager_id)
        scores.append(
            {
                "manager_name": manager.full_name if manager else manager_id,
                "team_average_score": round(avg, 2) if avg is not None else None,
                "team_size": len(emp_ids),
            }
        )

    scores.sort(key=lambda s: (s["team_average_score"] or 0), reverse=True)
    return {"manager_rankings": scores}


QUERY_HANDLERS = {
    "WHO_FAILED_COURSE": query_who_failed_course,
    "WHO_NEEDS_RETRAINING": query_who_needs_retraining,
    "TEAM_AVERAGE_SCORE": query_team_average_score,
    "DEPARTMENT_PASS_RATE": query_department_pass_rate,
    "BEST_PERFORMING_MANAGER": query_best_performing_manager,
}


def answer_question(user, question):
    """Full pipeline entry point used by the /api/ai/ask route."""
    intent = detect_intent(question)
    if intent == "UNKNOWN" or intent not in QUERY_HANDLERS:
        return {
            "intent": intent,
            "verified_data": {},
            "answer": render_natural_language_response(intent, {}),
        }

    verified_data = QUERY_HANDLERS[intent](user, question)
    answer = render_natural_language_response(intent, verified_data)
    return {"intent": intent, "verified_data": verified_data, "answer": answer}
