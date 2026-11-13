"""Pure scoring logic for MCQ assessment submissions, independent of the ORM so
it can be unit tested directly."""


def score_submission(questions, answers):
    """
    questions: list of {"id": str, "marks": float, "options": [{"id": str, "is_correct": bool}]}
    answers: dict of {question_id: selected_option_id}

    Returns (score, total_marks, percentage, per_question_results)
    """
    total_marks = sum(q["marks"] for q in questions)
    score = 0.0
    per_question = []

    for q in questions:
        selected_option_id = answers.get(q["id"])
        correct_option_ids = {o["id"] for o in q["options"] if o.get("is_correct")}
        is_correct = selected_option_id in correct_option_ids and selected_option_id is not None
        earned = q["marks"] if is_correct else 0.0
        score += earned
        per_question.append(
            {
                "question_id": q["id"],
                "selected_option_id": selected_option_id,
                "correct": is_correct,
                "marks_earned": earned,
                "marks_possible": q["marks"],
            }
        )

    percentage = (score / total_marks * 100.0) if total_marks > 0 else 0.0
    return score, total_marks, percentage, per_question


def determine_pass(percentage, passing_percentage):
    return percentage >= passing_percentage


def can_attempt(previous_attempt_count, max_attempts):
    return previous_attempt_count < max_attempts


def training_completion_satisfied(progress_percent, min_progress_percent_required, requires_completion):
    if not requires_completion:
        return True
    return progress_percent >= min_progress_percent_required
