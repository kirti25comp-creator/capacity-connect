from datetime import datetime

from app.extensions import db
from app.models.core import gen_uuid


class CompetencyRecord(db.Model):
    """Stores an employee's evaluated level for a skill, plus any identified gap."""

    __tablename__ = "competency_records"

    GAP_LEVELS = ("NONE", "MODERATE", "MAJOR")
    STRENGTH_LEVELS = ("STRONG", "MODERATE", "WEAK")

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    skill_name = db.Column(db.String(128), nullable=False)
    required_level = db.Column(db.Float, nullable=True)  # 0-100 required proficiency
    assessed_level = db.Column(db.Float, nullable=True)  # 0-100 derived from assessments/training
    gap_level = db.Column(db.String(16), default="NONE")  # NONE, MODERATE, MAJOR
    strength_label = db.Column(db.String(16), nullable=True)  # STRONG, MODERATE, WEAK
    source = db.Column(db.String(64), nullable=True)  # e.g. "assessment:<id>", "training:<id>"
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "skill_name": self.skill_name,
            "required_level": self.required_level,
            "assessed_level": self.assessed_level,
            "gap_level": self.gap_level,
            "strength_label": self.strength_label,
            "source": self.source,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }


class Certificate(db.Model):
    __tablename__ = "certificates"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    certificate_code = db.Column(db.String(64), unique=True, nullable=False)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=True)
    enrollment_id = db.Column(db.String(36), db.ForeignKey("enrollments.id"), nullable=True)

    completion_date = db.Column(db.Date, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "certificate_code": self.certificate_code,
            "employee_id": self.employee_id,
            "course_id": self.course_id,
            "trainer_id": self.trainer_id,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
        }


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=True)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=True)
    enrollment_id = db.Column(db.String(36), db.ForeignKey("enrollments.id"), nullable=True)

    trainer_rating = db.Column(db.Integer, nullable=True)  # 1-5
    course_rating = db.Column(db.Integer, nullable=True)
    material_rating = db.Column(db.Integer, nullable=True)
    comments = db.Column(db.Text, nullable=True)

    # AI feedback-analysis classification. This system never asserts someone is
    # lying; it only ever classifies evidentiary strength.
    analysis_classification = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "trainer_id": self.trainer_id,
            "course_id": self.course_id,
            "trainer_rating": self.trainer_rating,
            "course_rating": self.course_rating,
            "material_rating": self.material_rating,
            "comments": self.comments,
            "analysis_classification": self.analysis_classification,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TrainerQualityReview(db.Model):
    __tablename__ = "trainer_quality_reviews"

    STATUSES = ("OPEN", "TRAINER_REMOVED_FROM_ASSIGNMENT", "TRAINER_SUSPENDED", "DISMISSED")

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=False)
    enrollment_id = db.Column(db.String(36), db.ForeignKey("enrollments.id"), nullable=True)

    reason = db.Column(db.Text, nullable=False)
    metrics_snapshot = db.Column(db.JSON, nullable=True)
    classification = db.Column(db.String(32), nullable=True)  # from feedback analysis
    status = db.Column(db.String(32), default="OPEN")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "trainer_id": self.trainer_id,
            "enrollment_id": self.enrollment_id,
            "reason": self.reason,
            "metrics_snapshot": self.metrics_snapshot,
            "classification": self.classification,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    notif_type = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notif_type": self.notif_type,
            "message": self.message,
            "payload": self.payload,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    audience_role = db.Column(db.String(32), nullable=True)  # None = all roles
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "created_by": self.created_by,
            "message": self.message,
            "audience_role": self.audience_role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
