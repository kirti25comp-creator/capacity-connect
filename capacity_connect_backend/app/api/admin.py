import datetime

from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.core import Department, Organization, User
from app.models.employee import EmployeeProfile, ManagerEmployeeAssignment
from app.models.trainer import TrainerProfile
from app.services.notification_service import notify_admin_org_alert

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _org_scoped(query_cls):
    """Every admin query is implicitly scoped to g.current_user.organization_id
    - admins can never see another organization's rows, even by supplying a
    different id in the URL."""
    return query_cls.query.filter_by(organization_id=g.current_user.organization_id)


# ---------------------------------------------------------------- Departments
@admin_bp.route("/departments", methods=["GET"])
@token_required
@roles_required("ADMIN", "MANAGER")
def list_departments():
    depts = _org_scoped(Department).all()
    return jsonify({"departments": [d.to_dict() for d in depts]})


@admin_bp.route("/departments", methods=["POST"])
@token_required
@roles_required("ADMIN")
def create_department():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    dept = Department(organization_id=g.current_user.organization_id, name=name)
    db.session.add(dept)
    db.session.commit()
    log_audit_event("CREATE_DEPARTMENT", "department", dept.id)
    return jsonify({"department": dept.to_dict()}), 201


@admin_bp.route("/departments/<dept_id>", methods=["PUT"])
@token_required
@roles_required("ADMIN")
def update_department(dept_id):
    dept = Department.query.filter_by(id=dept_id, organization_id=g.current_user.organization_id).first()
    if dept is None:
        return jsonify({"error": "Department not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    if "name" in data:
        dept.name = data["name"].strip()
    db.session.commit()
    log_audit_event("UPDATE_DEPARTMENT", "department", dept.id)
    return jsonify({"department": dept.to_dict()})


@admin_bp.route("/departments/<dept_id>", methods=["DELETE"])
@token_required
@roles_required("ADMIN")
def delete_department(dept_id):
    dept = Department.query.filter_by(id=dept_id, organization_id=g.current_user.organization_id).first()
    if dept is None:
        return jsonify({"error": "Department not found"}), 404
    db.session.delete(dept)
    db.session.commit()
    log_audit_event("DELETE_DEPARTMENT", "department", dept_id)
    return jsonify({"message": "Deleted"})


# ------------------------------------------------------------------ Managers
@admin_bp.route("/managers", methods=["GET"])
@token_required
@roles_required("ADMIN")
def list_managers():
    managers = User.query.filter_by(organization_id=g.current_user.organization_id, role="MANAGER").all()
    return jsonify({"managers": [m.to_dict() for m in managers]})


@admin_bp.route("/managers", methods=["POST"])
@token_required
@roles_required("ADMIN")
def create_manager():
    return _invite_user(role="MANAGER")


# ----------------------------------------------------------------- Trainers
@admin_bp.route("/trainers", methods=["GET"])
@token_required
@roles_required("ADMIN", "MANAGER")
def list_trainers_admin():
    trainers = TrainerProfile.query.filter_by(organization_id=g.current_user.organization_id).all()
    return jsonify({"trainers": [t.to_dict() for t in trainers]})


@admin_bp.route("/trainers", methods=["POST"])
@token_required
@roles_required("ADMIN")
def create_trainer():
    data = request.get_json(force=True, silent=True) or {}
    result = _invite_user(role="TRAINER", return_response=False)
    if isinstance(result, tuple):  # error path from _invite_user
        return result
    user = result

    trainer = TrainerProfile(
        user_id=user.id,
        organization_id=g.current_user.organization_id,
        trainer_type=data.get("trainer_type", "INTERNAL"),
        bio=data.get("bio"),
        availability=data.get("availability", {}),
    )
    db.session.add(trainer)
    db.session.commit()
    log_audit_event("CREATE_TRAINER", "trainer_profile", trainer.id)
    return jsonify({"user": user.to_dict(), "trainer_profile": trainer.to_dict()}), 201


@admin_bp.route("/trainers/<trainer_id>/suspend", methods=["POST"])
@token_required
@roles_required("ADMIN")
def suspend_trainer(trainer_id):
    """Admin can suspend/deactivate a trainer organization-wide. This is
    explicitly a human (admin) action - never automatic, even off the back of
    an AI-generated quality alert."""
    trainer = TrainerProfile.query.filter_by(id=trainer_id, organization_id=g.current_user.organization_id).first()
    if trainer is None:
        return jsonify({"error": "Trainer not found"}), 404
    trainer.is_active = False
    user = db.session.get(User, trainer.user_id)
    if user:
        user.is_active = False
    db.session.commit()
    log_audit_event("SUSPEND_TRAINER", "trainer_profile", trainer.id)
    notify_admin_org_alert(
        g.current_user.id, g.current_user.organization_id, f"Trainer {trainer_id} was suspended organization-wide."
    )
    db.session.commit()
    return jsonify({"trainer_profile": trainer.to_dict()})


# ------------------------------------------------------------------ Employees
@admin_bp.route("/employees", methods=["POST"])
@token_required
@roles_required("ADMIN", "MANAGER")
def invite_employee():
    """Employee invitation. Manager-created employees are auto-assigned to
    that manager; admin-created employees can optionally specify manager_id."""
    data = request.get_json(force=True, silent=True) or {}
    result = _invite_user(role="EMPLOYEE", return_response=False)
    if isinstance(result, tuple):
        return result
    user = result

    department_id = data.get("department_id")
    if department_id:
        dept = Department.query.filter_by(id=department_id, organization_id=g.current_user.organization_id).first()
        if dept is None:
            return jsonify({"error": "Invalid department_id for this organization"}), 400

    profile = EmployeeProfile(
        user_id=user.id,
        organization_id=g.current_user.organization_id,
        department_id=department_id,
        job_title=data.get("job_title"),
        skills=data.get("skills", []),
    )
    db.session.add(profile)

    manager_id = data.get("manager_id") if g.current_user.role == "ADMIN" else g.current_user.id
    if manager_id:
        manager = User.query.filter_by(
            id=manager_id, organization_id=g.current_user.organization_id, role="MANAGER"
        ).first()
        if manager is None:
            return jsonify({"error": "Invalid manager_id for this organization"}), 400
        db.session.add(
            ManagerEmployeeAssignment(
                organization_id=g.current_user.organization_id, manager_id=manager_id, employee_id=user.id
            )
        )

    db.session.commit()
    log_audit_event("INVITE_EMPLOYEE", "user", user.id)
    return jsonify({"user": user.to_dict(), "employee_profile": profile.to_dict()}), 201


def _invite_user(role, return_response=True):
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    full_name = (data.get("full_name") or "").strip()
    if not email or not full_name:
        error = jsonify({"error": "email and full_name are required"}), 400
        return error if return_response else error

    existing = User.query.filter_by(organization_id=g.current_user.organization_id, email=email).first()
    if existing:
        error = jsonify({"error": "A user with this email already exists in this organization"}), 409
        return error if return_response else error

    import secrets

    temp_password = secrets.token_urlsafe(12)
    user = User(
        organization_id=g.current_user.organization_id,
        email=email,
        full_name=full_name,
        role=role,
        is_active=False,  # activated when they claim the invite via /api/auth/activate-invite
        invited_at=datetime.datetime.utcnow(),
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.flush()
    return user if not return_response else (jsonify({"user": user.to_dict()}), 201)
