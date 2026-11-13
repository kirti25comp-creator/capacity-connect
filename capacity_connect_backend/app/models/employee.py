from datetime import datetime

from app.extensions import db
from app.models.core import gen_uuid


class EmployeeProfile(db.Model):
    __tablename__ = "employee_profiles"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"), nullable=True)
    job_title = db.Column(db.String(255), nullable=True)
    skills = db.Column(db.JSON, default=list)  # e.g. [{"name": "SQL", "level": "Intermediate"}]
    hire_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "department_id": self.department_id,
            "job_title": self.job_title,
            "skills": self.skills or [],
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
        }


class ManagerEmployeeAssignment(db.Model):
    __tablename__ = "manager_employee_assignments"
    __table_args__ = (
        db.UniqueConstraint("manager_id", "employee_id", name="uq_manager_employee"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False)
    manager_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "manager_id": self.manager_id,
            "employee_id": self.employee_id,
        }
