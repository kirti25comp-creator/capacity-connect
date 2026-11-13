"""Competency-based trainer recommendation engine.

The scoring function operates on plain dicts so it can be unit tested without a
database or Flask app context. `match_trainers_for_requirement` in
`app/services/matching_db.py` adapts real ORM objects into these dicts and
persists TrainerMatch rows.
"""

WEIGHTS = {
    "subject_expertise": 0.25,
    "qualification": 0.15,
    "experience": 0.20,
    "certification": 0.10,
    "training_experience": 0.15,
    "availability": 0.10,
    "performance_rating": 0.05,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def _score_subject_expertise(requirement, trainer):
    """Overlap between requirement's domain/required_skills and trainer's
    domains/skills. 1.0 if the trainer covers the primary domain AND all
    required skills; partial credit otherwise."""
    req_domain = (requirement.get("domain") or "").strip().lower()
    req_skills = {s.strip().lower() for s in requirement.get("required_skills", []) if s}

    trainer_domains = {d.strip().lower() for d in trainer.get("domains", []) if d}
    trainer_skills = {s.strip().lower() for s in trainer.get("skills", []) if s}
    trainer_all = trainer_domains | trainer_skills

    domain_score = 1.0 if req_domain and req_domain in trainer_all else 0.0
    if not req_skills:
        skill_score = 1.0
    else:
        matched = req_skills & trainer_all
        skill_score = len(matched) / len(req_skills)

    matched_skills = sorted(req_skills & trainer_all)
    missing_skills = sorted(req_skills - trainer_all)

    # domain counts for half the sub-score, skill coverage the other half
    score = 0.5 * domain_score + 0.5 * skill_score
    return score, matched_skills, missing_skills, domain_score == 1.0


def _score_qualification(requirement, trainer):
    req_quals = {q.strip().lower() for q in requirement.get("qualifications", []) if q}
    trainer_quals = {q.strip().lower() for q in trainer.get("qualifications", []) if q}
    if not req_quals:
        return 1.0, [], []
    matched = req_quals & trainer_quals
    missing = req_quals - trainer_quals
    return len(matched) / len(req_quals), sorted(matched), sorted(missing)


def _score_experience(requirement, trainer):
    min_years = float(requirement.get("min_experience_years", 0) or 0)
    trainer_years = float(trainer.get("experience_years", 0) or 0)
    if min_years <= 0:
        return 1.0, True
    if trainer_years >= min_years:
        return 1.0, True
    # linear partial credit down to 0 at 0 years
    return max(0.0, trainer_years / min_years), False


def _score_certification(requirement, trainer):
    req_certs = {c.strip().lower() for c in requirement.get("required_certifications", []) if c}
    trainer_certs = {c.strip().lower() for c in trainer.get("certifications", []) if c}
    if not req_certs:
        return 1.0, [], []
    matched = req_certs & trainer_certs
    missing = req_certs - trainer_certs
    return len(matched) / len(req_certs), sorted(matched), sorted(missing)


def _score_training_experience(requirement, trainer):
    min_years = float(requirement.get("min_training_experience_years", 0) or 0)
    trainer_years = float(trainer.get("training_experience_years", 0) or 0)
    if min_years <= 0:
        return 1.0, True
    if trainer_years >= min_years:
        return 1.0, True
    return max(0.0, trainer_years / min_years), False


def _score_availability(requirement, trainer):
    needed = requirement.get("availability_needed") or {}
    needed_days = {d.strip().lower() for d in needed.get("days", []) if d}
    trainer_avail = trainer.get("availability") or {}
    trainer_days = {d.strip().lower() for d in trainer_avail.get("days", []) if d}

    if not needed_days:
        day_score = 1.0
    else:
        matched_days = needed_days & trainer_days
        day_score = len(matched_days) / len(needed_days)

    needed_hours = float(needed.get("hours_per_week", 0) or 0)
    trainer_hours = float(trainer_avail.get("hours_per_week", 0) or 0)
    if needed_hours <= 0:
        hours_score = 1.0
    else:
        hours_score = min(1.0, trainer_hours / needed_hours) if trainer_hours else 0.0

    return 0.5 * day_score + 0.5 * hours_score, day_score == 1.0


def _score_performance_rating(trainer):
    rating = float(trainer.get("rating_avg", 0) or 0)  # expected 0-5
    return max(0.0, min(1.0, rating / 5.0))


def score_trainer_against_requirement(requirement, trainer):
    """Returns (match_percentage, matched_criteria, missing_criteria) for a
    single trainer against a single training requirement.

    `requirement` dict keys: domain, required_skills, qualifications,
      min_experience_years, required_certifications,
      min_training_experience_years, availability_needed

    `trainer` dict keys: domains, skills, qualifications, experience_years,
      certifications, training_experience_years, availability, rating_avg
    """
    matched_criteria = []
    missing_criteria = []

    subj_score, matched_skills, missing_skills, domain_hit = _score_subject_expertise(requirement, trainer)
    if domain_hit:
        matched_criteria.append("domain: " + requirement.get("domain", ""))
    else:
        missing_criteria.append("domain: " + requirement.get("domain", ""))
    matched_criteria += [f"skill: {s}" for s in matched_skills]
    missing_criteria += [f"skill: {s}" for s in missing_skills]

    qual_score, matched_quals, missing_quals = _score_qualification(requirement, trainer)
    matched_criteria += [f"qualification: {q}" for q in matched_quals]
    missing_criteria += [f"qualification: {q}" for q in missing_quals]

    exp_score, exp_met = _score_experience(requirement, trainer)
    if requirement.get("min_experience_years", 0):
        label = f"experience >= {requirement.get('min_experience_years')}y"
        (matched_criteria if exp_met else missing_criteria).append(label)

    cert_score, matched_certs, missing_certs = _score_certification(requirement, trainer)
    matched_criteria += [f"certification: {c}" for c in matched_certs]
    missing_criteria += [f"certification: {c}" for c in missing_certs]

    train_exp_score, train_exp_met = _score_training_experience(requirement, trainer)
    if requirement.get("min_training_experience_years", 0):
        label = f"training delivery experience >= {requirement.get('min_training_experience_years')}y"
        (matched_criteria if train_exp_met else missing_criteria).append(label)

    avail_score, avail_met = _score_availability(requirement, trainer)
    if (requirement.get("availability_needed") or {}).get("days"):
        (matched_criteria if avail_met else missing_criteria).append("availability")

    perf_score = _score_performance_rating(trainer)

    total = (
        subj_score * WEIGHTS["subject_expertise"]
        + qual_score * WEIGHTS["qualification"]
        + exp_score * WEIGHTS["experience"]
        + cert_score * WEIGHTS["certification"]
        + train_exp_score * WEIGHTS["training_experience"]
        + avail_score * WEIGHTS["availability"]
        + perf_score * WEIGHTS["performance_rating"]
    )
    match_percentage = round(total * 100, 2)

    breakdown = {
        "subject_expertise": round(subj_score * 100, 2),
        "qualification": round(qual_score * 100, 2),
        "experience": round(exp_score * 100, 2),
        "certification": round(cert_score * 100, 2),
        "training_experience": round(train_exp_score * 100, 2),
        "availability": round(avail_score * 100, 2),
        "performance_rating": round(perf_score * 100, 2),
    }

    return match_percentage, matched_criteria, missing_criteria, breakdown


def rank_trainers_for_requirement(requirement, trainers):
    """trainers: list of (trainer_id, trainer_dict). Returns a list of result
    dicts sorted by match_percentage descending, with rank assigned 1..N.
    Never hardcodes rankings - purely a function of the scores computed above,
    computed from the trainer data passed in (which must originate from the
    database in production use)."""
    results = []
    for trainer_id, trainer in trainers:
        pct, matched, missing, breakdown = score_trainer_against_requirement(requirement, trainer)
        results.append(
            {
                "trainer_id": trainer_id,
                "match_percentage": pct,
                "matched_criteria": matched,
                "missing_criteria": missing,
                "breakdown": breakdown,
                "rating": trainer.get("rating_avg", 0),
                "availability": trainer.get("availability", {}),
            }
        )

    results.sort(key=lambda r: r["match_percentage"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i
    return results
