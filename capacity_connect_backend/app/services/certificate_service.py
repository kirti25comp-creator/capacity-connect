import secrets
from datetime import date

from app.extensions import db
from app.models.misc import Certificate


def generate_certificate_code(org_code="ORG"):
    return f"CC-{org_code}-{secrets.token_hex(4).upper()}"


def issue_certificate(organization, enrollment, employee_id, course_id, trainer_id):
    """Issues a certificate once completion/pass requirements configured on the
    course/assessment have been satisfied by the caller (see api/training.py)."""
    cert = Certificate(
        certificate_code=generate_certificate_code(organization.code),
        organization_id=organization.id,
        employee_id=employee_id,
        course_id=course_id,
        trainer_id=trainer_id,
        enrollment_id=enrollment.id if enrollment else None,
        completion_date=date.today(),
    )
    db.session.add(cert)
    return cert
