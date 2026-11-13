from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.extensions import db
from app.models.assessment import Assessment, AssessmentResult, ProctoringEvent
from app.models.training import Enrollment
from app.services.assessment_scoring import (
    can_attempt,
    determine_pass,
    score_submission,
    training_completion_satisfied,
)
from app.services.notification_service import notify_assessment_result, notify_manager_assessment_result
from app.services.proctoring_service import overall_status_for_result, record_event

assessments_bp = Blueprint("assessments", __name__, url_prefix="/api/assessments")


@assessments_bp.route("/<assessment_id>", methods=["GET"])
@token_required
@roles_required("EMPLOYEE")
def get_assessment_for_employee(assessment_id):
    """Employees never see is_correct flags before submitting."""
    assessment = Assessment.query.filter_by(
        id=assessment_id, organization_id=g.current_user.organization_id, is_active=True
    ).first()
    if assessment is None:
        return jsonify({"error": "Assessment not found"}), 404
    return jsonify({"assessment": assessment.to_dict(include_questions=True, reveal_answers=False)})


@assessments_bp.route("/<assessment_id>/submit", methods=["POST"])
@token_required
@roles_required("EMPLOYEE")
def submit_assessment(assessment_id):
    assessment = Assessment.query.filter_by(
        id=assessment_id, organization_id=g.current_user.organization_id, is_active=True
    ).first()
    if assessment is None:
        return jsonify({"error": "Assessment not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    enrollment_id = data.get("enrollment_id")
    answers = data.get("answers", {})  # {question_id: option_id}

    enrollment = None
    if enrollment_id:
        enrollment = Enrollment.query.filter_by(
            id=enrollment_id, employee_id=g.current_user.id, organization_id=g.current_user.organization_id
        ).first()
        if enrollment is None:
            return jsonify({"error": "Invalid enrollment_id"}), 400

        if not training_completion_satisfied(
            enrollment.progress_percent,
            assessment.min_progress_percent_required,
            assessment.requires_training_completion,
        ):
            return jsonify(
                {
                    "error": "Required training completion has not been met yet for the final assessment",
                    "progress_percent": enrollment.progress_percent,
                    "required_percent": assessment.min_progress_percent_required,
                }
            ), 403

    previous_attempts = AssessmentResult.query.filter_by(
        assessment_id=assessment_id, employee_id=g.current_user.id
    ).count()
    if not can_attempt(previous_attempts, assessment.max_attempts):
        return jsonify({"error": "Maximum attempts reached for this assessment"}), 403

    questions = [
        {
            "id": q.id,
            "marks": q.marks,
            "options": [{"id": o.id, "is_correct": o.is_correct} for o in q.options],
        }
        for q in assessment.questions
    ]
    score, total_marks, percentage, per_question = score_submission(questions, answers)
    passed = determine_pass(percentage, assessment.passing_percentage)

    result = AssessmentResult(
        organization_id=g.current_user.organization_id,
        assessment_id=assessment_id,
        employee_id=g.current_user.id,
        enrollment_id=enrollment_id,
        attempt_number=previous_attempts + 1,
        raw_answers=answers,
        score=score,
        total_marks=total_marks,
        percentage=percentage,
        passed=passed,
    )
    db.session.add(result)
    db.session.commit()

    notify_assessment_result(result)
    if enrollment and enrollment.assigned_by:
        notify_manager_assessment_result(enrollment.assigned_by, result)
        db.session.commit()

    log_audit_event("SUBMIT_ASSESSMENT", "assessment_result", result.id)
    return jsonify({"result": result.to_dict(), "per_question": per_question}), 201


@assessments_bp.route("/results/<result_id>/proctoring-events", methods=["POST"])
@token_required
@roles_required("EMPLOYEE")
def submit_proctoring_event(result_id):
    """DEMO/SIMULATED proctoring event ingestion - see services/proctoring_service.py."""
    result = AssessmentResult.query.filter_by(
        id=result_id, employee_id=g.current_user.id, organization_id=g.current_user.organization_id
    ).first()
    if result is None:
        return jsonify({"error": "Assessment result not found"}), 404

    data = request.get_json(force=True, silent=True) or {}
    event_type = data.get("event_type")
    try:
        event = record_event(g.current_user.organization_id, result.id, g.current_user.id, event_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    return jsonify({"event": event.to_dict()}), 201


@assessments_bp.route("/results/<result_id>/proctoring-summary", methods=["GET"])
@token_required
@roles_required("MANAGER", "ADMIN", "TRAINER")
def proctoring_summary(result_id):
    result = AssessmentResult.query.filter_by(
        id=result_id, organization_id=g.current_user.organization_id
    ).first()
    if result is None:
        return jsonify({"error": "Assessment result not found"}), 404
    events = ProctoringEvent.query.filter_by(assessment_result_id=result_id).all()
    return jsonify(
        {
            "overall_status": overall_status_for_result(events),
            "events": [e.to_dict() for e in events],
        }
    )


@assessments_bp.route("/results/<result_id>/proctoring-review", methods=["POST"])
@token_required
@roles_required("MANAGER")
def review_proctoring(result_id):
    """A manager reviews REVIEW_REQUIRED events and records their own
    conclusion. The system never auto-declares cheating - only a human
    reviewer marks manager_reviewed / adds notes here."""
    data = request.get_json(force=True, silent=True) or {}
    event_id = data.get("event_id")
    notes = data.get("notes", "")

    event = ProctoringEvent.query.filter_by(
        id=event_id, organization_id=g.current_user.organization_id
    ).first()
    if event is None:
        return jsonify({"error": "Proctoring event not found"}), 404

    event.manager_reviewed = True
    event.manager_notes = notes
    db.session.commit()
    log_audit_event("REVIEW_PROCTORING_EVENT", "proctoring_event", event.id)
    return jsonify({"event": event.to_dict()})
