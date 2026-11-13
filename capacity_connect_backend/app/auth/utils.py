import datetime
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from app.extensions import db
from app.models.core import AuditLog, User


def generate_token(user):
    """Generate a signed JWT. The role and org are embedded in the token but are
    ALWAYS re-verified against the database on every request - the token's claims
    are never trusted blindly for authorization decisions beyond identifying the
    user record to look up."""
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user.id,
        "org": user.organization_id,
        "role": user.role,
        "iat": now,
        "exp": now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def token_required(f):
    """Verifies the JWT is valid, then loads the *current* user record from the
    database. Role/org used for authorization always come from the freshly
    loaded DB record, never from the token payload alone - this way a
    deactivated user or a role change takes effect immediately."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Missing authentication token"}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        user = db.session.get(User, payload.get("sub"))
        if user is None or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def roles_required(*allowed_roles):
    """Must be stacked under token_required. Checks the DB-loaded user's role,
    never a client-supplied role."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "Authentication required"}), 401
            if user.role not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def require_same_organization(get_org_id_from_resource):
    """Decorator factory for endpoints that load a specific resource by id.

    `get_org_id_from_resource` is a callable that receives the same args/kwargs
    the view receives and must return the organization_id of the resource being
    accessed (or None if the resource doesn't exist, in which case a 404 is
    returned). This enforces organization isolation server-side, independent of
    whatever id the client passed in the URL/body - it can NEVER be bypassed by
    editing an id, because we always check the *actual* owning organization of
    the row against the caller's own organization_id.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "Authentication required"}), 401
            resource_org_id = get_org_id_from_resource(*args, **kwargs)
            if resource_org_id is None:
                return jsonify({"error": "Resource not found"}), 404
            if resource_org_id != user.organization_id:
                log_audit_event(
                    action="CROSS_ORG_ACCESS_DENIED",
                    resource="unknown",
                    resource_id=None,
                    details={"attempted_org": resource_org_id},
                )
                return jsonify({"error": "Forbidden: resource belongs to a different organization"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def log_audit_event(action, resource=None, resource_id=None, details=None):
    user = getattr(g, "current_user", None)
    entry = AuditLog(
        organization_id=user.organization_id if user else None,
        user_id=user.id if user else None,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details or {},
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()
