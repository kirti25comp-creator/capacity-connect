from datetime import datetime

from app.extensions import db
from app.models.core import gen_uuid


class Assessment(db.Model):
    __tablename__ = "assessments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    passing_percentage = db.Column(db.Float, default=60.0)
    time_limit_minutes = db.Column(db.Integer, default=30)
    max_attempts = db.Column(db.Integer, default=1)
    # Only allow the final assessment once required training completion conditions
    # are satisfied. When True, min_progress_percent on the linked enrollment must
    # be reached before submission is accepted.
    requires_training_completion = db.Column(db.Boolean, default=True)
    min_progress_percent_required = db.Column(db.Float, default=100.0)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship("Question", backref="assessment", lazy=True, cascade="all, delete-orphan")

    @property
    def total_marks(self):
        return sum(q.marks for q in self.questions) if self.questions else 0

    def to_dict(self, include_questions=False, reveal_answers=False):
        data = {
            "id": self.id,
            "organization_id": self.organization_id,
            "course_id": self.course_id,
            "trainer_id": self.trainer_id,
            "title": self.title,
            "passing_percentage": self.passing_percentage,
            "time_limit_minutes": self.time_limit_minutes,
            "max_attempts": self.max_attempts,
            "total_marks": self.total_marks,
            "is_active": self.is_active,
        }
        if include_questions:
            data["questions"] = [q.to_dict(reveal_answers=reveal_answers) for q in self.questions]
        return data


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    assessment_id = db.Column(db.String(36), db.ForeignKey("assessments.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    marks = db.Column(db.Float, default=1.0)

    options = db.relationship("AnswerOption", backref="question", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, reveal_answers=False):
        return {
            "id": self.id,
            "text": self.text,
            "marks": self.marks,
            "options": [o.to_dict(reveal_answers=reveal_answers) for o in self.options],
        }


class AnswerOption(db.Model):
    __tablename__ = "answer_options"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    def to_dict(self, reveal_answers=False):
        data = {"id": self.id, "text": self.text}
        if reveal_answers:
            data["is_correct"] = self.is_correct
        return data


class AssessmentResult(db.Model):
    __tablename__ = "assessment_results"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    assessment_id = db.Column(db.String(36), db.ForeignKey("assessments.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    enrollment_id = db.Column(db.String(36), db.ForeignKey("enrollments.id"), nullable=True)

    attempt_number = db.Column(db.Integer, default=1)
    raw_answers = db.Column(db.JSON, nullable=True)  # {question_id: option_id}
    score = db.Column(db.Float, default=0.0)
    total_marks = db.Column(db.Float, default=0.0)
    percentage = db.Column(db.Float, default=0.0)
    passed = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    proctoring_events = db.relationship("ProctoringEvent", backref="assessment_result", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "assessment_id": self.assessment_id,
            "employee_id": self.employee_id,
            "enrollment_id": self.enrollment_id,
            "attempt_number": self.attempt_number,
            "score": self.score,
            "total_marks": self.total_marks,
            "percentage": round(self.percentage, 2),
            "passed": self.passed,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


class ProctoringEvent(db.Model):
    """Demo/simulated AI proctoring event log. Not a real computer-vision pipeline."""

    __tablename__ = "proctoring_events"

    EVENT_TYPES = (
        "FACE_MISSING",
        "MULTIPLE_FACES",
        "CAMERA_INTERRUPTION",
        "SUSPICIOUS_BEHAVIOR",
    )
    STATUSES = ("CLEAR", "REVIEW_REQUIRED")

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    assessment_result_id = db.Column(db.String(36), db.ForeignKey("assessment_results.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    event_type = db.Column(db.String(32), nullable=False)
    severity = db.Column(db.String(16), default="LOW")  # LOW, MEDIUM, HIGH
    status = db.Column(db.String(32), default="CLEAR")  # CLEAR or REVIEW_REQUIRED - never "CHEATING"
    manager_reviewed = db.Column(db.Boolean, default=False)
    manager_notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "assessment_result_id": self.assessment_result_id,
            "employee_id": self.employee_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "status": self.status,
            "manager_reviewed": self.manager_reviewed,
            "manager_notes": self.manager_notes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
