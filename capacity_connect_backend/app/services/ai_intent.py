"""Pure pieces of the CAPACITY AI pipeline: intent detection and natural
language response templating. Deliberately has zero DB/SQLAlchemy dependency
so it can be unit tested in total isolation. The DB-backed, RBAC-enforcing
query layer lives in ai_service.py.
"""

import re

INTENTS = (
    "WHO_FAILED_COURSE",
    "WHO_NEEDS_RETRAINING",
    "TEAM_AVERAGE_SCORE",
    "DEPARTMENT_PASS_RATE",
    "BEST_PERFORMING_MANAGER",
    "UNKNOWN",
)


def detect_intent(question):
    q = question.lower().strip()

    if re.search(r"\bfail(ed|ing)?\b", q):
        return "WHO_FAILED_COURSE"
    if "retrain" in q or "skill gap" in q or "need training" in q:
        return "WHO_NEEDS_RETRAINING"
    if "average score" in q or "avg score" in q:
        return "TEAM_AVERAGE_SCORE"
    if "pass rate" in q and "department" in q:
        return "DEPARTMENT_PASS_RATE"
    if "best" in q and "manager" in q:
        return "BEST_PERFORMING_MANAGER"
    return "UNKNOWN"


def render_natural_language_response(intent, verified_data):
    """DEMO mode: template-based phrasing over verified_data only. No numbers
    are ever invented here - everything comes from `verified_data`, which is
    always produced by an authorization-scoped database query."""
    if "error" in verified_data:
        return verified_data["error"]

    if intent == "WHO_FAILED_COURSE":
        emps = verified_data.get("employees", [])
        if not emps:
            return "No matching failed results were found for the data you're authorized to see."
        lines = [f"- {e['employee_name']} ({e['assessment']}, {e['percentage']:.1f}%)" for e in emps]
        return f"{len(emps)} result(s) found:\n" + "\n".join(lines)

    if intent == "WHO_NEEDS_RETRAINING":
        emps = verified_data.get("employees_needing_retraining", [])
        if not emps:
            return "No employees with a major skill gap were found."
        lines = [f"- {e['employee_name']}: {e['skill']} (gap: {e['gap_level']})" for e in emps]
        return f"{len(emps)} employee(s) flagged for retraining:\n" + "\n".join(lines)

    if intent == "TEAM_AVERAGE_SCORE":
        avg = verified_data.get("average_score")
        if avg is None:
            return "No assessment results are available yet for this scope."
        return f"The average assessment score is {avg}%."

    if intent == "DEPARTMENT_PASS_RATE":
        rows = verified_data.get("department_pass_rates", [])
        if not rows:
            return "No department assessment data is available yet."
        lines = [
            f"- Department {r['department_id']}: {r['pass_rate']}% pass rate ({r['total_assessments']} results)"
            for r in rows
        ]
        return "Department pass rates:\n" + "\n".join(lines)

    if intent == "BEST_PERFORMING_MANAGER":
        rows = verified_data.get("manager_rankings", [])
        if not rows:
            return "No manager performance data is available yet."
        top = rows[0]
        return (
            f"Top-performing manager: {top['manager_name']} "
            f"(team average {top['team_average_score']}%, team size {top['team_size']})."
        )

    return (
        "I couldn't confidently map that question to a supported CAPACITY AI "
        "query yet. Try rephrasing, e.g. 'Who failed the Python assessment?'"
    )
