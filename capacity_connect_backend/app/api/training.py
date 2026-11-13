import datetime

from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.training import Enrollment
from app.services.notification_service import (
    notify_deadline_expired_employee,
    notify_manager_deadline_expired,
    notify_manager_training_completed,
)
from app.services.training_lifecycle import can_transition, compute_status_for_date

training_bp = Blueprint("training", __name__, url_prefix="/api/training")


@training_bp.route("/enrollments/<enrollment_id>/progress", methods=["PUT"])
@token_required
@roles_required("EMPLOYEE")
def update_progress(enrollment_id):
    enrollment = Enrollment.query.filter_by(
        id=enrollment_id, employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()
    if enrollment is None:
        return jsonify({"error": "Enrollment not found"}), 404
    if enrollment.status in ("COMPLETED", "DEADLINE_EXPIRED"):
        return jsonify({"error": f"Cannot update progress on a {enrollment.status} enrollment"}), 400

    data = request.get_json(force=True, silent=True) or {}
    progress = data.get("progress_percent")
    if progress is None or not (0 <= progress <= 100):
        return jsonify({"error": "progress_percent must be between 0 and 100"}), 400

    enrollment.progress_percent = progress
    today = datetime.date.today()
    new_status = compute_status_for_date(enrollment.status, enrollment.end_date, today, progress)

    if new_status != enrollment.status and can_transition(enrollment.status, new_status):
        enrollment.status = new_status
        if new_status == "COMPLETED":
            enrollment.completed_at = datetime.datetime.utcnow()
            if enrollment.assigned_by:
                notify_manager_training_completed(enrollment.assigned_by, enrollment)

    db.session.commit()
    return jsonify({"enrollment": enrollment.to_dict()})


@training_bp.route("/deadline-sweep", methods=["POST"])
@token_required
@roles_required("ADMIN")
def deadline_sweep():
    """Scans all non-terminal enrollments in this organization and expires any
    past their deadline. Intended to be triggered by a scheduled job (e.g. a
    daily cron hitting this endpoint) - deliberately NOT automatic/unlimited
    extension logic; expiry just flags status + notifies, a manager must act
    explicitly to grant any extension."""
    today = datetime.date.today()
    enrollments = Enrollment.query.filter(
        Enrollment.organization_id == g.current_user.organization_id,
        Enrollment.status.in_(["ASSIGNED", "IN_PROGRESS"]),
        Enrollment.end_date < today,
    ).all()

    expired = []
    for e in enrollments:
        e.status = "DEADLINE_EXPIRED"
        notify_deadline_expired_employee(e)
        if e.assigned_by:
            notify_manager_deadline_expired(e.assigned_by, e)
        expired.append(e)

    db.session.commit()
    log_audit_event("DEADLINE_SWEEP", "enrollment", None, {"expired_count": len(expired)})
    return jsonify({"expired_enrollments": [e.to_dict() for e in expired], "count": len(expired)})


@training_bp.route("/enrollments/<enrollment_id>/extend", methods=["POST"])
@token_required
@roles_required("MANAGER")
def extend_deadline(enrollment_id):
    """Explicit, one-at-a-time manager-granted extension. There is no
    unlimited/automatic extension mechanism - each extension requires this
    deliberate manager action and is audit-logged."""
    enrollment = Enrollment.query.filter_by(
        id=enrollment_id, organization_id=g.current_user.organization_id, assigned_by=g.current_user.id
    ).first()
    if enrollment is None:
        return jsonify({"error": "Enrollment not found or not assigned by you"}), 404
    if enrollment.status != "DEADLINE_EXPIRED":
        return jsonify({"error": "Only DEADLINE_EXPIRED enrollments can be extended"}), 400

    data = request.get_json(force=True, silent=True) or {}
    try:
        new_end_date = datetime.date.fromisoformat(data.get("new_end_date", ""))
    except ValueError:
        return jsonify({"error": "new_end_date must be YYYY-MM-DD"}), 400
    if new_end_date <= datetime.date.today():
        return jsonify({"error": "new_end_date must be in the future"}), 400

    enrollment.end_date = new_end_date
    enrollment.status = "IN_PROGRESS" if enrollment.progress_percent > 0 else "ASSIGNED"
    db.session.commit()
    log_audit_event("EXTEND_DEADLINE", "enrollment", enrollment.id, {"new_end_date": str(new_end_date)})
    return jsonify({"enrollment": enrollment.to_dict()})
