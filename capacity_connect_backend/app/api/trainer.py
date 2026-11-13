import os
import uuid

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.utils import secure_filename

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.assessment import AnswerOption, Assessment, Question
from app.models.misc import Feedback
from app.models.trainer import TrainerCertification, TrainerDomain, TrainerExperience, TrainerProfile
from app.models.training import Course, Enrollment

trainer_bp = Blueprint("trainer", __name__, url_prefix="/api/trainer")


def _my_trainer_profile():
    return TrainerProfile.query.filter_by(
        user_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()


def _require_trainer_profile():
    profile = _my_trainer_profile()
    if profile is None:
        return None, (jsonify({"error": "No trainer profile found for this account"}), 404)
    return profile, None


# --------------------------------------------------------------------- Profile
@trainer_bp.route("/profile", methods=["GET"])
@token_required
@roles_required("TRAINER")
def get_my_profile():
    profile, err = _require_trainer_profile()
    if err:
        return err
    return jsonify({"trainer_profile": profile.to_dict()})


@trainer_bp.route("/profile", methods=["PUT"])
@token_required
@roles_required("TRAINER")
def update_my_profile():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    if "bio" in data:
        profile.bio = data["bio"]
    if "availability" in data:
        profile.availability = data["availability"]
    if "trainer_type" in data:
        profile.trainer_type = data["trainer_type"]
    db.session.commit()
    log_audit_event("UPDATE_TRAINER_PROFILE", "trainer_profile", profile.id)
    return jsonify({"trainer_profile": profile.to_dict()})


@trainer_bp.route("/profile/domains", methods=["POST"])
@token_required
@roles_required("TRAINER")
def add_domain():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("domain_name"):
        return jsonify({"error": "domain_name is required"}), 400
    d = TrainerDomain(
        trainer_id=profile.id,
        domain_name=data["domain_name"],
        skill_name=data.get("skill_name"),
        proficiency=data.get("proficiency", "INTERMEDIATE"),
    )
    db.session.add(d)
    db.session.commit()
    return jsonify({"domain": d.to_dict()}), 201


@trainer_bp.route("/profile/certifications", methods=["POST"])
@token_required
@roles_required("TRAINER")
def add_certification():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    import datetime

    c = TrainerCertification(
        trainer_id=profile.id,
        name=data["name"],
        issuer=data.get("issuer"),
        issue_date=datetime.date.fromisoformat(data["issue_date"]) if data.get("issue_date") else None,
        expiry_date=datetime.date.fromisoformat(data["expiry_date"]) if data.get("expiry_date") else None,
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"certification": c.to_dict()}), 201


@trainer_bp.route("/profile/experience", methods=["POST"])
@token_required
@roles_required("TRAINER")
def add_experience():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    e = TrainerExperience(
        trainer_id=profile.id,
        domain=data.get("domain"),
        years=data.get("years", 0),
        training_delivery_years=data.get("training_delivery_years", 0),
        description=data.get("description"),
    )
    db.session.add(e)
    db.session.commit()
    return jsonify({"experience": e.to_dict()}), 201


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


@trainer_bp.route("/profile/intro-video", methods=["POST"])
@token_required
@roles_required("TRAINER")
def upload_intro_video():
    """Stores intro-video metadata only (filename, size). Actual binary is
    saved to a per-org, path-sanitized directory. This never trusts the
    client-supplied filename directly - it is sanitized with secure_filename
    and given a random prefix to prevent path traversal / overwrite attacks."""
    profile, err = _require_trainer_profile()
    if err:
        return err
    if "file" not in request.files:
        return jsonify({"error": "file is required (multipart/form-data)"}), 400
    file = request.files["file"]
    if file.filename == "" or not _allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing filename/extension"}), 400

    safe_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    org_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], g.current_user.organization_id)
    os.makedirs(org_dir, exist_ok=True)
    dest_path = os.path.join(org_dir, stored_name)
    file.save(dest_path)

    profile.intro_video_metadata = {"filename": stored_name, "original_filename": safe_name}
    db.session.commit()
    log_audit_event("UPLOAD_INTRO_VIDEO", "trainer_profile", profile.id)
    return jsonify({"trainer_profile": profile.to_dict()})


# ---------------------------------------------------------------- Courses
@trainer_bp.route("/courses", methods=["POST"])
@token_required
@roles_required("TRAINER")
def create_course():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    course = Course(
        organization_id=g.current_user.organization_id,
        trainer_id=profile.id,
        title=data["title"],
        domain=data.get("domain"),
        description=data.get("description"),
        resources=data.get("resources", []),
    )
    db.session.add(course)
    db.session.commit()
    log_audit_event("CREATE_COURSE", "course", course.id)
    return jsonify({"course": course.to_dict()}), 201


@trainer_bp.route("/courses", methods=["GET"])
@token_required
@roles_required("TRAINER")
def list_my_courses():
    profile, err = _require_trainer_profile()
    if err:
        return err
    courses = Course.query.filter_by(trainer_id=profile.id, organization_id=g.current_user.organization_id).all()
    return jsonify({"courses": [c.to_dict() for c in courses]})


# ------------------------------------------------------------- Assessments
@trainer_bp.route("/assessments", methods=["POST"])
@token_required
@roles_required("TRAINER")
def create_assessment():
    profile, err = _require_trainer_profile()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    course_id = data.get("course_id")
    course = Course.query.filter_by(
        id=course_id, trainer_id=profile.id, organization_id=g.current_user.organization_id
    ).first()
    if course is None:
        return jsonify({"error": "Invalid course_id (must be your own course)"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    assessment = Assessment(
        organization_id=g.current_user.organization_id,
        course_id=course_id,
        trainer_id=profile.id,
        title=data["title"],
        passing_percentage=data.get("passing_percentage", 60.0),
        time_limit_minutes=data.get("time_limit_minutes", 30),
        max_attempts=data.get("max_attempts", 1),
        requires_training_completion=data.get("requires_training_completion", True),
        min_progress_percent_required=data.get("min_progress_percent_required", 100.0),
    )
    db.session.add(assessment)
    db.session.flush()

    for q in data.get("questions", []):
        question = Question(assessment_id=assessment.id, text=q["text"], marks=q.get("marks", 1.0))
        db.session.add(question)
        db.session.flush()
        for opt in q.get("options", []):
            db.session.add(
                AnswerOption(question_id=question.id, text=opt["text"], is_correct=bool(opt.get("is_correct")))
            )

    db.session.commit()
    log_audit_event("CREATE_ASSESSMENT", "assessment", assessment.id)
    return jsonify({"assessment": assessment.to_dict(include_questions=True, reveal_answers=True)}), 201


@trainer_bp.route("/assigned-training", methods=["GET"])
@token_required
@roles_required("TRAINER")
def assigned_training():
    profile, err = _require_trainer_profile()
    if err:
        return err
    enrollments = Enrollment.query.filter_by(
        trainer_id=profile.id, organization_id=g.current_user.organization_id
    ).all()
    return jsonify({"enrollments": [e.to_dict() for e in enrollments]})


@trainer_bp.route("/feedback", methods=["GET"])
@token_required
@roles_required("TRAINER")
def my_feedback():
    profile, err = _require_trainer_profile()
    if err:
        return err
    feedback = Feedback.query.filter_by(trainer_id=profile.id, organization_id=g.current_user.organization_id).all()
    return jsonify(
        {
            "feedback": [f.to_dict() for f in feedback],
            "rating_avg": profile.rating_avg,
            "completion_rate": profile.completion_rate,
            "pass_rate": profile.pass_rate,
        }
    )
