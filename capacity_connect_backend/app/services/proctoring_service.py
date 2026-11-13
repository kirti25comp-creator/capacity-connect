"""DEMO/SIMULATED AI proctoring support.

This is explicitly a hackathon simulation: it does not run any real computer
vision or webcam analysis. Event submission is accepted from the client
(which, in the demo, would represent a simulated webcam-monitoring widget) and
this module only classifies severity -> CLEAR / REVIEW_REQUIRED. It never
concludes that the candidate cheated - that determination is always left to a
manager during review.
"""

from app.extensions import db
from app.models.assessment import ProctoringEvent

SEVERITY_BY_EVENT = {
    "FACE_MISSING": "MEDIUM",
    "MULTIPLE_FACES": "HIGH",
    "CAMERA_INTERRUPTION": "MEDIUM",
    "SUSPICIOUS_BEHAVIOR": "HIGH",
}

REVIEW_REQUIRED_SEVERITIES = {"HIGH"}


def record_event(organization_id, assessment_result_id, employee_id, event_type):
    if event_type not in ProctoringEvent.EVENT_TYPES:
        raise ValueError(f"Unknown proctoring event_type: {event_type}")

    severity = SEVERITY_BY_EVENT.get(event_type, "LOW")
    status = "REVIEW_REQUIRED" if severity in REVIEW_REQUIRED_SEVERITIES else "CLEAR"

    event = ProctoringEvent(
        organization_id=organization_id,
        assessment_result_id=assessment_result_id,
        employee_id=employee_id,
        event_type=event_type,
        severity=severity,
        status=status,
    )
    db.session.add(event)
    return event


def overall_status_for_result(events):
    """A result is REVIEW_REQUIRED if any of its events are, else CLEAR."""
    if any(e.status == "REVIEW_REQUIRED" for e in events):
        return "REVIEW_REQUIRED"
    return "CLEAR"
