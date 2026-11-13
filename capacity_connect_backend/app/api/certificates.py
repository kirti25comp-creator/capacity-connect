from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.core import Organization
from app.models.employee import ManagerEmployeeAssignment
from app.models.training import Enrollment
from app.services.certificate_service import issue_certificate
from app.services.notification_service import notify_certificate_issued

certificates_bp = Blueprint("certificates", __name__, url_prefix="/api/certificates")


@certificates_bp.route("/issue", methods=["POST"])
@token_required
@roles_required("MANAGER", "TRAINER", "ADMIN")
def issue():
    """Issues a certificate for a COMPLETED, passed enrollment. Managers may
    only issue for their own employees; trainers only for their own
    assignments; admins for anyone in the organization."""
    data = request.get_json(force=True, silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    enrollment = Enrollment.query.filter_by(
        id=enrollment_id, organization_id=g.current_user.organization_id
    ).first()
    if enrollment is None:
        return jsonify({"error": "Enrollment not found"}), 404

    if g.current_user.role == "MANAGER":
        assignment = ManagerEmployeeAssignment.query.filter_by(
            organization_id=g.current_user.organization_id,
            manager_id=g.current_user.id,
            employee_id=enrollment.employee_id,
        ).first()
        if assignment is None:
            return jsonify({"error": "Forbidden: not your employee"}), 403
    elif g.current_user.role == "TRAINER":
        from app.models.trainer import TrainerProfile

        trainer_profile = TrainerProfile.query.filter_by(
            user_id=g.current_user.id, organization_id=g.current_user.organization_id
        ).first()
        if trainer_profile is None or enrollment.trainer_id != trainer_profile.id:
            return jsonify({"error": "Forbidden: not your assigned training"}), 403

    if enrollment.status != "COMPLETED":
        return jsonify({"error": "Certificates may only be issued for COMPLETED enrollments"}), 400

    org = db.session.get(Organization, g.current_user.organization_id)
    cert = issue_certificate(org, enrollment, enrollment.employee_id, enrollment.course_id, enrollment.trainer_id)
    db.session.commit()
    notify_certificate_issued(cert)
    db.session.commit()

    log_audit_event("ISSUE_CERTIFICATE", "certificate", cert.id)
    return jsonify({"certificate": cert.to_dict()}), 201
