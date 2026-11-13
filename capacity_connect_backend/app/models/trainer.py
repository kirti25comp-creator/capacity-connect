from datetime import datetime

from app.extensions import db
from app.models.core import gen_uuid


class TrainerProfile(db.Model):
    __tablename__ = "trainer_profiles"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)

    trainer_type = db.Column(db.String(16), default="INTERNAL")  # INTERNAL / EXTERNAL
    bio = db.Column(db.Text, nullable=True)
    intro_video_metadata = db.Column(db.JSON, nullable=True)  # {"filename":..., "duration_s":...}
    availability = db.Column(db.JSON, default=dict)  # {"days": [...], "hours_per_week": N}
    is_active = db.Column(db.Boolean, default=True)

    # Cached quality metrics, recomputed by trainer_quality service
    rating_avg = db.Column(db.Float, default=0.0)
    completion_rate = db.Column(db.Float, default=0.0)
    pass_rate = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    domains = db.relationship("TrainerDomain", backref="trainer", lazy=True, cascade="all, delete-orphan")
    certifications = db.relationship("TrainerCertification", backref="trainer", lazy=True, cascade="all, delete-orphan")
    experiences = db.relationship("TrainerExperience", backref="trainer", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, include_related=True):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "trainer_type": self.trainer_type,
            "bio": self.bio,
            "availability": self.availability or {},
            "is_active": self.is_active,
            "rating_avg": self.rating_avg,
            "completion_rate": self.completion_rate,
            "pass_rate": self.pass_rate,
        }
        if include_related:
            data["domains"] = [d.to_dict() for d in self.domains]
            data["certifications"] = [c.to_dict() for c in self.certifications]
            data["experiences"] = [e.to_dict() for e in self.experiences]
        return data


class TrainerDomain(db.Model):
    __tablename__ = "trainer_domains"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=False)
    domain_name = db.Column(db.String(128), nullable=False)
    skill_name = db.Column(db.String(128), nullable=True)
    proficiency = db.Column(db.String(32), default="INTERMEDIATE")  # BEGINNER/INTERMEDIATE/EXPERT

    def to_dict(self):
        return {
            "id": self.id,
            "domain_name": self.domain_name,
            "skill_name": self.skill_name,
            "proficiency": self.proficiency,
        }


class TrainerCertification(db.Model):
    __tablename__ = "trainer_certifications"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    issuer = db.Column(db.String(255), nullable=True)
    issue_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "issuer": self.issuer,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
        }


class TrainerExperience(db.Model):
    __tablename__ = "trainer_experience"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    trainer_id = db.Column(db.String(36), db.ForeignKey("trainer_profiles.id"), nullable=False)
    domain = db.Column(db.String(128), nullable=True)
    years = db.Column(db.Float, default=0.0)
    training_delivery_years = db.Column(db.Float, default=0.0)  # experience specifically training others
    description = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "domain": self.domain,
            "years": self.years,
            "training_delivery_years": self.training_delivery_years,
            "description": self.description,
        }
