from app.extensions import db
from app.models.assessment import AssessmentResult
from app.models.core import User
from app.models.employee import ManagerEmployeeAssignment
from app.models.misc import Feedback, TrainerQualityReview
from app.models.training import Enrollment
from app.services.notification_service import (
    notify_admin_trainer_alert,
    notify_manager_trainer_quality_alert,
)
from app.services.trainer_quality import compute_trainer_quality_snapshot, should_raise_quality_alert


def recompute_trainer_quality(trainer_id, organization_id):
    from app.models.trainer import TrainerProfile

    trainer = TrainerProfile.query.filter_by(id=trainer_id, organization_id=organization_id).first()
    if trainer is None:
        return None

    feedback_rows = Feedback.query.filter_by(trainer_id=trainer_id, organization_id=organization_id).all()
    ratings = [f.trainer_rating for f in feedback_rows if f.trainer_rating is not None]

    enrollments = Enrollment.query.filter_by(trainer_id=trainer_id, organization_id=organization_id).all()
    total_enrollments = len(enrollments)
    completed = len([e for e in enrollments if e.status == "COMPLETED"])
    completion_rate = (completed / total_enrollments) if total_enrollments else 0.0

    enrollment_ids = [e.id for e in enrollments]
    results = (
        AssessmentResult.query.filter(AssessmentResult.enrollment_id.in_(enrollment_ids)).all()
        if enrollment_ids
        else []
    )
    pass_rate = (len([r for r in results if r.passed]) / len(results)) if results else 0.0

    snapshot = compute_trainer_quality_snapshot(ratings, completion_rate, pass_rate)
    trainer.rating_avg = snapshot["rating_avg"]
    trainer.completion_rate = snapshot["completion_rate"]
    trainer.pass_rate = snapshot["pass_rate"]

    should_alert, reasons = should_raise_quality_alert(snapshot)
    if should_alert:
        existing_open = TrainerQualityReview.query.filter_by(
            trainer_id=trainer_id, organization_id=organization_id, status="OPEN"
        ).first()
        if existing_open is None:
            review = TrainerQualityReview(
                organization_id=organization_id,
                trainer_id=trainer_id,
                reason="; ".join(reasons),
                metrics_snapshot=snapshot,
                status="OPEN",
            )
            db.session.add(review)

            # Notify managers who currently have this trainer assigned, plus admins.
            affected_enrollments = [e for e in enrollments if e.status in ("ASSIGNED", "IN_PROGRESS")]
            manager_ids = {e.assigned_by for e in affected_enrollments if e.assigned_by}
            for manager_id in manager_ids:
                notify_manager_trainer_quality_alert(manager_id, organization_id, trainer_id, reasons)

            admins = User.query.filter_by(organization_id=organization_id, role="ADMIN").all()
            for admin in admins:
                notify_admin_trainer_alert(admin.id, organization_id, trainer_id, reasons)

    return snapshot
