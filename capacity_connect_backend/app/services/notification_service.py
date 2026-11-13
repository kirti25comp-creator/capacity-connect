from app.extensions import db
from app.models.misc import Notification


def notify(organization_id, user_id, notif_type, message, payload=None):
    n = Notification(
        organization_id=organization_id,
        user_id=user_id,
        notif_type=notif_type,
        message=message,
        payload=payload or {},
    )
    db.session.add(n)
    return n


# --- Employee-facing notification helpers -------------------------------
def notify_training_assigned(enrollment):
    return notify(
        enrollment.organization_id,
        enrollment.employee_id,
        "TRAINING_ASSIGNED",
        "You have been assigned new training.",
        {"enrollment_id": enrollment.id, "course_id": enrollment.course_id},
    )


def notify_deadline_approaching(enrollment, days_left):
    return notify(
        enrollment.organization_id,
        enrollment.employee_id,
        "DEADLINE_APPROACHING",
        f"Your training deadline is in {days_left} day(s).",
        {"enrollment_id": enrollment.id},
    )


def notify_deadline_expired_employee(enrollment):
    return notify(
        enrollment.organization_id,
        enrollment.employee_id,
        "DEADLINE_EXPIRED",
        "Your training deadline has passed without completion.",
        {"enrollment_id": enrollment.id},
    )


def notify_assessment_available(employee_id, organization_id, assessment):
    return notify(
        organization_id,
        employee_id,
        "ASSESSMENT_AVAILABLE",
        f"A new assessment is available: {assessment.title}",
        {"assessment_id": assessment.id},
    )


def notify_assessment_result(result):
    outcome = "passed" if result.passed else "did not pass"
    return notify(
        result.organization_id,
        result.employee_id,
        "ASSESSMENT_RESULT",
        f"You {outcome} the assessment with {result.percentage:.1f}%.",
        {"assessment_result_id": result.id},
    )


def notify_certificate_issued(certificate):
    return notify(
        certificate.organization_id,
        certificate.employee_id,
        "CERTIFICATE_ISSUED",
        "Your certificate has been issued.",
        {"certificate_id": certificate.id},
    )


# --- Manager-facing notification helpers --------------------------------
def notify_manager_employee_added(manager_id, organization_id, employee_name):
    return notify(
        organization_id, manager_id, "EMPLOYEE_ADDED", f"{employee_name} was added to your team.", {}
    )


def notify_manager_training_completed(manager_id, enrollment):
    return notify(
        enrollment.organization_id,
        manager_id,
        "TRAINING_COMPLETED",
        "An employee completed their assigned training.",
        {"enrollment_id": enrollment.id},
    )


def notify_manager_deadline_expired(manager_id, enrollment):
    return notify(
        enrollment.organization_id,
        manager_id,
        "DEADLINE_EXPIRED",
        "An employee's training deadline has expired.",
        {"enrollment_id": enrollment.id},
    )


def notify_manager_assessment_result(manager_id, result):
    outcome = "passed" if result.passed else "failed"
    return notify(
        result.organization_id,
        manager_id,
        "ASSESSMENT_RESULT",
        f"An employee {outcome} an assessment.",
        {"assessment_result_id": result.id},
    )


def notify_manager_skill_gap(manager_id, organization_id, employee_id, skill_name, gap_level):
    return notify(
        organization_id,
        manager_id,
        "SKILL_GAP",
        f"A {gap_level} skill gap was identified in {skill_name}.",
        {"employee_id": employee_id, "skill_name": skill_name, "gap_level": gap_level},
    )


def notify_manager_trainer_quality_alert(manager_id, organization_id, trainer_id, reasons):
    return notify(
        organization_id,
        manager_id,
        "TRAINER_QUALITY_ALERT",
        "A trainer quality alert was raised for one of your training assignments.",
        {"trainer_id": trainer_id, "reasons": reasons},
    )


# --- Admin-facing notification helpers -----------------------------------
def notify_admin_org_alert(admin_id, organization_id, message, payload=None):
    return notify(organization_id, admin_id, "ORG_ALERT", message, payload or {})


def notify_admin_trainer_alert(admin_id, organization_id, trainer_id, reasons):
    return notify(
        organization_id,
        admin_id,
        "TRAINER_ALERT",
        "A trainer quality alert requires admin attention.",
        {"trainer_id": trainer_id, "reasons": reasons},
    )
