from datetime import datetime

from app.extensions import db
from app.models.core import gen_uuid


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text, nullable=True)
    resources = db.Column(db.JSON, default=list)  # approved learning resources metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "trainer_id": self.trainer_id,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "resources": self.resources or [],
            "is_active": self.is_active,
        }


class TrainingRequirement(db.Model):
    __tablename__ = "training_requirements"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    manager_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    subject = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(128), nullable=False)
    required_skills = db.Column(db.JSON, default=list)  # ["SQL", "Python"]
    qualifications = db.Column(db.JSON, default=list)  # ["B.Tech", "M.Sc"]
    min_experience_years = db.Column(db.Float, default=0.0)
    required_certifications = db.Column(db.JSON, default=list)
    min_training_experience_years = db.Column(db.Float, default=0.0)
    availability_needed = db.Column(db.JSON, default=dict)  # {"days": [...], "hours_per_week": N}

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    status = db.Column(db.String(32), default="OPEN")  # OPEN, MATCHED, CLOSED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "manager_id": self.manager_id,
            "subject": self.subject,
            "domain": self.domain,
            "required_skills": self.required_skills or [],
            "qualifications": self.qualifications or [],
            "min_experience_years": self.min_experience_years,
            "required_certifications": self.required_certifications or [],
            "min_training_experience_years": self.min_training_experience_years,
            "availability_needed": self.availability_needed or {},
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
        }


class TrainerMatch(db.Model):
    __tablename__ = "trainer_matches"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    requirement_id = db.Column(db.String(36), db.ForeignKey("training_requirements.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=False)

    match_percentage = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    matched_criteria = db.Column(db.JSON, default=list)
    missing_criteria = db.Column(db.JSON, default=list)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "requirement_id": self.requirement_id,
            "trainer_id": self.trainer_id,
            "match_percentage": round(self.match_percentage, 2),
            "rank": self.rank,
            "matched_criteria": self.matched_criteria or [],
            "missing_criteria": self.missing_criteria or [],
        }


class Enrollment(db.Model):
    """Represents an employee's assignment to a course/training with a trainer."""

    __tablename__ = "enrollments"

    STATUSES = ("ASSIGNED", "IN_PROGRESS", "COMPLETED", "DEADLINE_EXPIRED")

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=True)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    requirement_id = db.Column(db.String(36), db.ForeignKey("training_requirements.id"), nullable=True)
    assigned_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    status = db.Column(db.String(32), default="ASSIGNED")
    progress_percent = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)  # deadline
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "employee_id": self.employee_id,
            "trainer_id": self.trainer_id,
            "course_id": self.course_id,
            "requirement_id": self.requirement_id,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
