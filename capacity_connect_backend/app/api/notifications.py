from flask import Blueprint, g, jsonify, request

from app.auth.utils import roles_required, token_required
from app.extensions import db
from app.models.misc import Announcement, Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@token_required
def list_notifications():
    """Every user - regardless of role - can only ever see their own
    notifications. There is no id parameter to manipulate here at all."""
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    query = Notification.query.filter_by(
        organization_id=g.current_user.organization_id, user_id=g.current_user.id
    )
    if unread_only:
        query = query.filter_by(is_read=False)
    notifications = query.order_by(Notification.created_at.desc()).all()
    return jsonify({"notifications": [n.to_dict() for n in notifications]})


@notifications_bp.route("/<notification_id>/read", methods=["POST"])
@token_required
def mark_read(notification_id):
    n = Notification.query.filter_by(
        id=notification_id, user_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()
    if n is None:
        return jsonify({"error": "Notification not found"}), 404
    n.is_read = True
    db.session.commit()
    return jsonify({"notification": n.to_dict()})


@notifications_bp.route("/announcements", methods=["POST"])
@token_required
@roles_required("ADMIN")
def create_announcement():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("message"):
        return jsonify({"error": "message is required"}), 400
    ann = Announcement(
        organization_id=g.current_user.organization_id,
        created_by=g.current_user.id,
        message=data["message"],
        audience_role=data.get("audience_role"),
    )
    db.session.add(ann)
    db.session.commit()
    return jsonify({"announcement": ann.to_dict()}), 201


@notifications_bp.route("/announcements", methods=["GET"])
@token_required
def list_announcements():
    query = Announcement.query.filter_by(organization_id=g.current_user.organization_id)
    announcements = [
        a
        for a in query.all()
        if a.audience_role is None or a.audience_role == g.current_user.role
    ]
    return jsonify({"announcements": [a.to_dict() for a in announcements]})
