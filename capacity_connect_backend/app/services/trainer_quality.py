"""Trainer quality scoring and feedback-evidence classification.

Important safety property: this module NEVER asserts that a person is lying,
and never automatically penalizes a trainer purely from an AI classification.
It only computes a quality snapshot and an evidentiary classification; a human
(manager for removal-from-assignment, admin for suspension) always makes the
final call.
"""

FEEDBACK_CLASSIFICATIONS = (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "HUMAN_REVIEW_REQUIRED",
)

# Quality alert thresholds - configurable, transparent, and based on real
# aggregate metrics rather than a single complaint.
LOW_RATING_THRESHOLD = 2.5           # out of 5
LOW_PASS_RATE_THRESHOLD = 0.5        # 50%
LOW_COMPLETION_RATE_THRESHOLD = 0.5  # 50%
MIN_FEEDBACK_COUNT_FOR_ALERT = 3     # avoid flagging on a single review


def compute_trainer_quality_snapshot(ratings, completion_rate, pass_rate):
    """ratings: list of 1-5 ints from Feedback.trainer_rating.
    completion_rate / pass_rate: floats 0-1 computed from enrollments/results.
    """
    rating_avg = sum(ratings) / len(ratings) if ratings else 0.0
    return {
        "rating_avg": round(rating_avg, 2),
        "feedback_count": len(ratings),
        "completion_rate": round(completion_rate, 4),
        "pass_rate": round(pass_rate, 4),
    }


def should_raise_quality_alert(snapshot):
    """Returns (should_alert: bool, reasons: list[str]). Requires a minimum
    sample size so a single bad review can't trigger an alert."""
    if snapshot["feedback_count"] < MIN_FEEDBACK_COUNT_FOR_ALERT:
        return False, []

    reasons = []
    if snapshot["rating_avg"] > 0 and snapshot["rating_avg"] < LOW_RATING_THRESHOLD:
        reasons.append(f"Average rating {snapshot['rating_avg']} is below threshold {LOW_RATING_THRESHOLD}")
    if snapshot["pass_rate"] < LOW_PASS_RATE_THRESHOLD:
        reasons.append(f"Pass rate {snapshot['pass_rate']*100:.0f}% is below threshold {LOW_PASS_RATE_THRESHOLD*100:.0f}%")
    if snapshot["completion_rate"] < LOW_COMPLETION_RATE_THRESHOLD:
        reasons.append(
            f"Completion rate {snapshot['completion_rate']*100:.0f}% is below threshold {LOW_COMPLETION_RATE_THRESHOLD*100:.0f}%"
        )

    return (len(reasons) > 0), reasons


def classify_feedback_theme(comments_for_trainer):
    """comments_for_trainer: list of free-text comment strings referencing the
    same alleged issue (e.g. "always late", "unprepared"). This is a simple,
    transparent keyword-overlap heuristic for the hackathon DEMO AI mode - it
    never concludes someone is lying, only how well-supported a theme is by
    independent reports.

    Returns one of FEEDBACK_CLASSIFICATIONS.
    """
    count = len(comments_for_trainer)
    if count == 0:
        return "INSUFFICIENT_EVIDENCE"
    if count == 1:
        return "INSUFFICIENT_EVIDENCE"

    # crude sentiment-direction split: does the theme look consistent or do
    # comments contradict one another (naive keyword check for the demo).
    negative_markers = ("late", "unprepared", "rude", "unclear", "disorganized", "absent", "poor")
    positive_markers = ("great", "excellent", "helpful", "clear", "engaging", "knowledgeable")

    neg = sum(1 for c in comments_for_trainer if any(m in c.lower() for m in negative_markers))
    pos = sum(1 for c in comments_for_trainer if any(m in c.lower() for m in positive_markers))

    if neg > 0 and pos > 0:
        return "CONFLICTING_EVIDENCE"
    if neg >= 3:
        return "SUPPORTED"
    if neg >= 2:
        return "PARTIALLY_SUPPORTED"
    if neg == 1:
        return "INSUFFICIENT_EVIDENCE"
    # Ambiguous or unclear language that a human should read directly.
    return "HUMAN_REVIEW_REQUIRED"
