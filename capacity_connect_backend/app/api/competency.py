from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.assessment import Assessment, AssessmentResult
from app.models.employee import EmployeeProfile, ManagerEmployeeAssignment
from app.models.misc import CompetencyRecord
from app.models.training import Course
from app.services.notification_service import notify_manager_skill_gap
from app.services.skill_gap import build_skill_gap_report

competency_bp = Blueprint("competency", __name__, url_prefix="/api/competency")


def _required_level_for_skill(profile, skill_name):
    for s in profile.skills or []:
        if isinstance(s, dict) and s.get("name", "").lower() == skill_name.lower() and s.get("required_level"):
            return s["required_level"]
    return 80.0  # sensible default competency bar for the hackathon demo


@competency_bp.route("/employees/<employee_id>/recompute", methods=["POST"])
@token_required
@roles_required("MANAGER", "ADMIN")
def recompute_skill_gaps(employee_id):
    """Compares employee skills + assessment performance to build a skill-gap
    report and persists CompetencyRecord rows. A manager may only run this for
    their own employees; an admin may run it for anyone in the organization."""
    if g.current_user.role == "MANAGER":
        assignment = ManagerEmployeeAssignment.query.filter_by(
            organization_id=g.current_user.organization_id,
            manager_id=g.current_user.id,
            employee_id=employee_id,
        ).first()
        if assignment is None:
            return jsonify({"error": "Forbidden: not your employee"}), 403

    profile = EmployeeProfile.query.filter_by(
        user_id=employee_id, organization_id=g.current_user.organization_id
    ).first()
    if profile is None:
        return jsonify({"error": "Employee profile not found"}), 404

    skill_names = {s.get("name") for s in (profile.skills or []) if isinstance(s, dict) and s.get("name")}

    results = (
        AssessmentResult.query.join(Assessment, AssessmentResult.assessment_id == Assessment.id)
        .filter(AssessmentResult.employee_id == employee_id, AssessmentResult.organization_id == g.current_user.organization_id)
        .all()
    )
    # For the demo, an assessment's course domain doubles as the "skill" it measures.
    percentages_by_skill = {}
    for r in results:
        assessment = db.session.get(Assessment, r.assessment_id)
        course = db.session.get(Course, assessment.course_id) if assessment else None
        skill = course.domain if course else None
        if skill:
            percentages_by_skill.setdefault(skill, []).append(r.percentage)
            skill_names.add(skill)

    employee_skill_data = [
        {
            "skill_name": name,
            "required_level": _required_level_for_skill(profile, name),
            "assessment_percentages": percentages_by_skill.get(name, []),
        }
        for name in skill_names
    ]

    report = build_skill_gap_report(employee_skill_data)

    # Replace previous computed records for these skills with fresh ones.
    for item in report:
        CompetencyRecord.query.filter_by(
            organization_id=g.current_user.organization_id,
            employee_id=employee_id,
            skill_name=item["skill_name"],
        ).delete()
        record = CompetencyRecord(
            organization_id=g.current_user.organization_id,
            employee_id=employee_id,
            skill_name=item["skill_name"],
            required_level=item["required_level"],
            assessed_level=item["assessed_level"],
            gap_level=item["gap_level"],
            strength_label=item["strength_label"],
            source="assessment_performance",
        )
        db.session.add(record)

        if item["gap_level"] == "MAJOR":
            manager_assignment = ManagerEmployeeAssignment.query.filter_by(
                organization_id=g.current_user.organization_id, employee_id=employee_id
            ).first()
            if manager_assignment:
                notify_manager_skill_gap(
                    manager_assignment.manager_id,
                    g.current_user.organization_id,
                    employee_id,
                    item["skill_name"],
                    item["gap_level"],
                )

    db.session.commit()
    log_audit_event("RECOMPUTE_SKILL_GAPS", "employee_profile", profile.id)
    return jsonify({"skill_gap_report": report})
