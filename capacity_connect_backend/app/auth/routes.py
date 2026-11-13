import datetime
import re
import secrets

from flask import Blueprint, g, jsonify, request

from app.auth.utils import generate_token, log_audit_event, token_required
from app.extensions import db
from app.models.core import Organization, User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _org_code(name):
    base = re.sub(r"[^A-Z0-9]", "", name.upper())[:8] or "ORG"
    return f"{base}-{secrets.token_hex(3).upper()}"


@auth_bp.route("/register-organization", methods=["POST"])
def register_organization():
    """Company registration. Creates the organization (inactive, pending mock
    verification) and its first ADMIN user."""
    data = request.get_json(force=True, silent=True) or {}
    org_name = (data.get("organization_name") or "").strip()
    admin_email = (data.get("admin_email") or "").strip().lower()
    admin_password = data.get("admin_password") or ""
    admin_name = (data.get("admin_name") or "").strip()
    registration_number = (data.get("registration_number") or "").strip()

    if not org_name or not admin_email or not admin_password or not admin_name:
        return jsonify({"error": "organization_name, admin_name, admin_email and admin_password are required"}), 400
    if not EMAIL_RE.match(admin_email):
        return jsonify({"error": "Invalid email format"}), 400
    if len(admin_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    org = Organization(
        name=org_name,
        code=_org_code(org_name),
        registration_number=registration_number,
        verification_status="PENDING",
        verification_source="MOCK_MCA_DEMO",
        is_active=False,
    )
    db.session.add(org)
    db.session.flush()

    admin = User(
        organization_id=org.id,
        email=admin_email,
        full_name=admin_name,
        role="ADMIN",
        is_active=True,
        activated_at=datetime.datetime.utcnow(),
    )
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()

    return jsonify(
        {
            "message": "Organization registered. Verification is pending (DEMO/MOCK verification, not a real MCA lookup).",
            "organization": org.to_dict(),
            "admin_user": admin.to_dict(),
        }
    ), 201


@auth_bp.route("/verify-organization/<org_id>", methods=["POST"])
def verify_organization_demo(org_id):
    """Clearly-labelled MOCK/DEMO verification. Does NOT call any real government
    or MCA API. In this hackathon prototype, verification simply checks that a
    registration_number was supplied and marks the org as MOCK_VERIFIED."""
    org = db.session.get(Organization, org_id)
    if org is None:
        return jsonify({"error": "Organization not found"}), 404

    if org.registration_number:
        org.verification_status = "MOCK_VERIFIED"
    else:
        org.verification_status = "REJECTED"
    db.session.commit()

    return jsonify(
        {
            "message": "This is a MOCK/DEMO verification result only. No real MCA API was called.",
            "organization": org.to_dict(),
        }
    )


@auth_bp.route("/activate-organization/<org_id>", methods=["POST"])
def activate_organization(org_id):
    org = db.session.get(Organization, org_id)
    if org is None:
        return jsonify({"error": "Organization not found"}), 404
    if org.verification_status != "MOCK_VERIFIED":
        return jsonify({"error": "Organization must be MOCK_VERIFIED before activation"}), 400
    org.is_active = True
    db.session.commit()
    return jsonify({"organization": org.to_dict()})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    org_code = (data.get("organization_code") or "").strip()

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    query = User.query.filter_by(email=email)
    if org_code:
        org = Organization.query.filter_by(code=org_code).first()
        if org is None:
            return jsonify({"error": "Invalid credentials"}), 401
        query = query.filter_by(organization_id=org.id)

    user = query.first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account is not active"}), 403

    org = db.session.get(Organization, user.organization_id)
    if org and not org.is_active:
        return jsonify({"error": "Organization is not yet active"}), 403

    token = generate_token(user)
    g.current_user = user
    log_audit_event(action="LOGIN", resource="user", resource_id=user.id)

    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    # Stateless JWTs: logout is handled client-side by discarding the token.
    # We still record the event for audit purposes.
    log_audit_event(action="LOGOUT", resource="user", resource_id=g.current_user.id)
    return jsonify({"message": "Logged out"})


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": g.current_user.to_dict()})


@auth_bp.route("/activate-invite", methods=["POST"])
def activate_invite():
    """Employee/trainer/manager sets their password after being invited by an
    admin or manager (see /api/admin/employees invitation flow)."""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    org_code = (data.get("organization_code") or "").strip()
    new_password = data.get("new_password") or ""

    if not email or not org_code or not new_password:
        return jsonify({"error": "email, organization_code and new_password are required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    org = Organization.query.filter_by(code=org_code).first()
    if org is None:
        return jsonify({"error": "Invalid organization code"}), 404

    user = User.query.filter_by(email=email, organization_id=org.id).first()
    if user is None:
        return jsonify({"error": "Invitation not found"}), 404
    if user.activated_at is not None:
        return jsonify({"error": "Account already activated"}), 400

    user.set_password(new_password)
    user.activated_at = datetime.datetime.utcnow()
    user.is_active = True
    db.session.commit()

    return jsonify({"message": "Account activated", "user": user.to_dict()})
