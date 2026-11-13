"""Training lifecycle state machine: ASSIGNED -> IN_PROGRESS -> COMPLETED, or
-> DEADLINE_EXPIRED if the end_date passes before completion.

No unlimited automatic extensions: expiring an enrollment simply changes its
status and flags a manager notification. Any extension must be an explicit,
separate manager action (see api/manager.py extend_enrollment).
"""

VALID_TRANSITIONS = {
    "ASSIGNED": {"IN_PROGRESS", "DEADLINE_EXPIRED", "COMPLETED"},
    "IN_PROGRESS": {"COMPLETED", "DEADLINE_EXPIRED"},
    "COMPLETED": set(),
    "DEADLINE_EXPIRED": {"IN_PROGRESS"},  # only via an explicit manager-granted extension
}


def can_transition(current_status, new_status):
    return new_status in VALID_TRANSITIONS.get(current_status, set())


def compute_status_for_date(current_status, end_date, today, progress_percent):
    """Given the enrollment's current status and today's date, determine what
    the status *should* be. Does not mutate anything - caller applies it."""
    if current_status == "COMPLETED":
        return "COMPLETED"

    if today > end_date and current_status != "COMPLETED":
        return "DEADLINE_EXPIRED"

    if progress_percent >= 100:
        return "COMPLETED"

    if progress_percent > 0 and current_status == "ASSIGNED":
        return "IN_PROGRESS"

    return current_status
