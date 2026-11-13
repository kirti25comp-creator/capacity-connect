import datetime

from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.assessment import AssessmentResult
from app.models.core import User
from app.models.employee import EmployeeProfile, ManagerEmployeeAssignment
from app.models.misc import CompetencyRecord, Certificate, TrainerQualityReview
from app.models.trainer import TrainerProfile
from app.models.training import Course, Enrollment, TrainerMatch, TrainingRequirement
from app.services.matching_db import compute_matches_for_requirement
from app.services.notification_service import notify_training_assigned

manager_bp = Blueprint("manager", __name__, url_prefix="/api/manager")


def _my_employee_ids():
    """The single source of truth for 'which employees belong to this
    manager'. Every manager-scoped endpoint below uses this - a manager can
    never enumerate or act on another manager's employees, regardless of what
    id they pass in the request."""
    rows = ManagerEmployeeAssignment.query.filter_by(
        organization_id=g.current_user.organization_id, manager_id=g.current_user.id
    ).all()
    return {r.employee_id for r in rows}


def _assert_own_employee(employee_id):
    return employee_id in _my_employee_ids()


@manager_bp.route("/employees", methods=["GET"])
@token_required
@roles_required("MANAGER")
def list_my_employees():
    emp_ids = _my_employee_ids()
    if not emp_ids:
        return jsonify({"employees": []})
    users = User.query.filter(User.id.in_(emp_ids), User.organization_id == g.current_user.organization_id).all()
    profiles = {
        p.user_id: p
        for p in EmployeeProfile.query.filter(EmployeeProfile.user_id.in_(emp_ids)).all()
    }
    result = []
    for u in users:
        entry = u.to_dict()
        profile = profiles.get(u.id)
        entry["profile"] = profile.to_dict() if profile else None
        result.append(entry)
    return jsonify({"employees": result})


@manager_bp.route("/employees/<employee_id>", methods=["PUT"])
@token_required
@roles_required("MANAGER")
def edit_employee(employee_id):
    if not _assert_own_employee(employee_id):
        return jsonify({"error": "Forbidden: not your employee"}), 403

    profile = EmployeeProfile.query.filter_by(
        user_id=employee_id, organization_id=g.current_user.organization_id
    ).first()
    if profile is None:
        return jsonify({"error": "Employee profile not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    # Managers may edit permitted fields only - not role, not email, not org.
    if "job_title" in data:
        profile.job_title = data["job_title"]
    if "skills" in data:
        profile.skills = data["skills"]
    if "department_id" in data:
        profile.department_id = data["department_id"]

    db.session.commit()
    log_audit_event("EDIT_EMPLOYEE", "employee_profile", profile.id)
    return jsonify({"employee_profile": profile.to_dict()})


@manager_bp.route("/employees/<employee_id>/progress", methods=["GET"])
@token_required
@roles_required("MANAGER")
def employee_progress(employee_id):
    if not _assert_own_employee(employee_id):
        return jsonify({"error": "Forbidden: not your employee"}), 403
    enrollments = Enrollment.query.filter_by(
        employee_id=employee_id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"enrollments": [e.to_dict() for e in enrollments]})


@manager_bp.route("/employees/<employee_id>/assessment-results", methods=["GET"])
@token_required
@roles_required("MANAGER")
def employee_assessment_results(employee_id):
    if not _assert_own_employee(employee_id):
        return jsonify({"error": "Forbidden: not your employee"}), 403
    results = AssessmentResult.query.filter_by(
        employee_id=employee_id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"results": [r.to_dict() for r in results]})


@manager_bp.route("/employees/<employee_id>/skill-gaps", methods=["GET"])
@token_required
@roles_required("MANAGER")
def employee_skill_gaps(employee_id):
    if not _assert_own_employee(employee_id):
        return jsonify({"error": "Forbidden: not your employee"}), 403
    records = CompetencyRecord.query.filter_by(
        employee_id=employee_id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"skill_gaps": [r.to_dict() for r in records]})


@manager_bp.route("/employees/<employee_id>/certificates", methods=["GET"])
@token_required
@roles_required("MANAGER")
def employee_certificates(employee_id):
    if not _assert_own_employee(employee_id):
        return jsonify({"error": "Forbidden: not your employee"}), 403
    certs = Certificate.query.filter_by(
        employee_id=employee_id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"certificates": [c.to_dict() for c in certs]})


# ------------------------------------------------------- Training requirements
@manager_bp.route("/training-requirements", methods=["POST"])
@token_required
@roles_required("MANAGER")
def create_training_requirement():
    data = request.get_json(force=True, silent=True) or {}
    required_fields = ["subject", "domain", "start_date", "end_date"]
    if any(not data.get(f) for f in required_fields):
        return jsonify({"error": f"Required fields: {', '.join(required_fields)}"}), 400

    try:
        start_date = datetime.date.fromisoformat(data["start_date"])
        end_date = datetime.date.fromisoformat(data["end_date"])
    except ValueError:
        return jsonify({"error": "start_date/end_date must be YYYY-MM-DD"}), 400
    if end_date < start_date:
        return jsonify({"error": "end_date must be on or after start_date"}), 400

    req = TrainingRequirement(
        organization_id=g.current_user.organization_id,
        manager_id=g.current_user.id,
        subject=data["subject"],
        domain=data["domain"],
        required_skills=data.get("required_skills", []),
        qualifications=data.get("qualifications", []),
        min_experience_years=data.get("min_experience_years", 0),
        required_certifications=data.get("required_certifications", []),
        min_training_experience_years=data.get("min_training_experience_years", 0),
        availability_needed=data.get("availability_needed", {}),
        start_date=start_date,
        end_date=end_date,
    )
    db.session.add(req)
    db.session.commit()
    log_audit_event("CREATE_TRAINING_REQUIREMENT", "training_requirement", req.id)
    return jsonify({"training_requirement": req.to_dict()}), 201


@manager_bp.route("/training-requirements/<req_id>/matches", methods=["GET"])
@token_required
@roles_required("MANAGER")
def get_trainer_matches(req_id):
    req = TrainingRequirement.query.filter_by(
        id=req_id, organization_id=g.current_user.organization_id, manager_id=g.current_user.id
    ).first()
    if req is None:
        return jsonify({"error": "Training requirement not found"}), 404

    matches = compute_matches_for_requirement(req)
    db.session.commit()
    return jsonify({"matches": [m.to_dict() for m in matches]})


@manager_bp.route("/training-requirements/<req_id>/assign", methods=["POST"])
@token_required
@roles_required("MANAGER")
def assign_training(req_id):
    """Assign a matched trainer + course to one or more employees."""
    req = TrainingRequirement.query.filter_by(
        id=req_id, organization_id=g.current_user.organization_id, manager_id=g.current_user.id
    ).first()
    if req is None:
        return jsonify({"error": "Training requirement not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    trainer_id = data.get("trainer_id")
    course_id = data.get("course_id")
    employee_ids = data.get("employee_ids", [])

    if not trainer_id or not course_id or not employee_ids:
        return jsonify({"error": "trainer_id, course_id and employee_ids are required"}), 400

    trainer = TrainerProfile.query.filter_by(id=trainer_id, organization_id=g.current_user.organization_id).first()
    course = Course.query.filter_by(id=course_id, organization_id=g.current_user.organization_id).first()
    if trainer is None or course is None:
        return jsonify({"error": "Invalid trainer_id or course_id"}), 400

    my_employees = _my_employee_ids()
    invalid = [e for e in employee_ids if e not in my_employees]
    if invalid:
        return jsonify({"error": "Forbidden: some employee_ids are not your employees", "invalid": invalid}), 403

    created = []
    for emp_id in employee_ids:
        enrollment = Enrollment(
            organization_id=g.current_user.organization_id,
            employee_id=emp_id,
            trainer_id=trainer_id,
            course_id=course_id,
            requirement_id=req.id,
            assigned_by=g.current_user.id,
            status="ASSIGNED",
            start_date=req.start_date,
            end_date=req.end_date,
        )
        db.session.add(enrollment)
        db.session.flush()
        notify_training_assigned(enrollment)
        created.append(enrollment)

    req.status = "MATCHED"
    db.session.commit()
    log_audit_event("ASSIGN_TRAINING", "training_requirement", req.id, {"employee_ids": employee_ids})
    return jsonify({"enrollments": [e.to_dict() for e in created]}), 201


@manager_bp.route("/enrollments/<enrollment_id>/remove-trainer", methods=["POST"])
@token_required
@roles_required("MANAGER")
def remove_trainer_from_assignment(enrollment_id):
    """Manager can remove a trainer from their own training assignment
    (e.g. following a quality concern), without affecting the trainer's
    standing anywhere else in the organization."""
    enrollment = Enrollment.query.filter_by(
        id=enrollment_id, organization_id=g.current_user.organization_id, assigned_by=g.current_user.id
    ).first()
    if enrollment is None:
        return jsonify({"error": "Enrollment not found or not created by you"}), 404

    old_trainer_id = enrollment.trainer_id
    enrollment.trainer_id = None
    db.session.commit()
    log_audit_event(
        "REMOVE_TRAINER_FROM_ASSIGNMENT", "enrollment", enrollment.id, {"previous_trainer_id": old_trainer_id}
    )
    return jsonify({"enrollment": enrollment.to_dict()})


@manager_bp.route("/trainer-quality-alerts", methods=["GET"])
@token_required
@roles_required("MANAGER")
def trainer_quality_alerts():
    my_employees = _my_employee_ids()
    if not my_employees:
        return jsonify({"alerts": []})
    my_enrollment_ids = {
        e.id
        for e in Enrollment.query.filter(
            Enrollment.employee_id.in_(my_employees), Enrollment.organization_id == g.current_user.organization_id
        ).all()
    }
    alerts = TrainerQualityReview.query.filter(
        TrainerQualityReview.organization_id == g.current_user.organization_id,
        TrainerQualityReview.enrollment_id.in_(my_enrollment_ids) if my_enrollment_ids else False,
    ).all()
    return jsonify({"alerts": [a.to_dict() for a in alerts]})
