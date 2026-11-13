import uuid
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(64), unique=True, nullable=False)
    registration_number = db.Column(db.String(128), nullable=True)

    # DEMO/MOCK verification fields. This is NOT a real MCA (Ministry of Corporate
    # Affairs) integration - it is a clearly-labelled mock used for the hackathon.
    verification_status = db.Column(
        db.String(32), default="PENDING"
    )  # PENDING, MOCK_VERIFIED, REJECTED
    verification_source = db.Column(db.String(64), default="MOCK_MCA_DEMO")
    is_active = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="organization", lazy=True)
    departments = db.relationship("Department", backref="organization", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "verification_status": self.verification_status,
            "verification_source": self.verification_source,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "email", name="uq_org_email"),
    )

    ROLES = ("ADMIN", "MANAGER", "TRAINER", "EMPLOYEE")

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False
    )
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    invited_at = db.Column(db.DateTime, nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(128), nullable=False)
    resource = db.Column(db.String(128), nullable=True)
    resource_id = db.Column(db.String(36), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
