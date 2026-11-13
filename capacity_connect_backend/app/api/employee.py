from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.employee import EmployeeProfile
from app.models.misc import Certificate, CompetencyRecord, Feedback
from app.models.training import Enrollment

employee_bp = Blueprint("employee", __name__, url_prefix="/api/employee")


@employee_bp.route("/profile", methods=["GET"])
@token_required
@roles_required("EMPLOYEE")
def my_profile():
    profile = EmployeeProfile.query.filter_by(
        user_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()
    if profile is None:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"profile": profile.to_dict()})


@employee_bp.route("/enrollments", methods=["GET"])
@token_required
@roles_required("EMPLOYEE")
def my_enrollments():
    enrollments = Enrollment.query.filter_by(
        employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"enrollments": [e.to_dict() for e in enrollments]})


@employee_bp.route("/certificates", methods=["GET"])
@token_required
@roles_required("EMPLOYEE")
def my_certificates():
    certs = Certificate.query.filter_by(
        employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"certificates": [c.to_dict() for c in certs]})


@employee_bp.route("/skill-gaps", methods=["GET"])
@token_required
@roles_required("EMPLOYEE")
def my_skill_gaps():
    records = CompetencyRecord.query.filter_by(
        employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"skill_gaps": [r.to_dict() for r in records]})


@employee_bp.route("/feedback", methods=["POST"])
@token_required
@roles_required("EMPLOYEE")
def submit_feedback():
    data = request.get_json(force=True, silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    enrollment = Enrollment.query.filter_by(
        id=enrollment_id, employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()
    if enrollment is None:
        return jsonify({"error": "Invalid enrollment_id (must be your own enrollment)"}), 400

    feedback = Feedback(
        organization_id=g.current_user.organization_id,
        employee_id=g.current_user.id,
        trainer_id=enrollment.trainer_id,
        course_id=enrollment.course_id,
        enrollment_id=enrollment.id,
        trainer_rating=data.get("trainer_rating"),
        course_rating=data.get("course_rating"),
        material_rating=data.get("material_rating"),
        comments=data.get("comments"),
    )
    db.session.add(feedback)
    db.session.commit()
    log_audit_event("SUBMIT_FEEDBACK", "feedback", feedback.id)

    from app.services.trainer_quality_db import recompute_trainer_quality

    if enrollment.trainer_id:
        recompute_trainer_quality(enrollment.trainer_id, g.current_user.organization_id)
        db.session.commit()

    return jsonify({"feedback": feedback.to_dict()}), 201
