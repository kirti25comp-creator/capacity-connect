from app.extensions import db
from app.models.trainer import TrainerProfile
from app.models.training import TrainerMatch
from app.services.matching import rank_trainers_for_requirement


def _requirement_to_dict(req):
    return {
        "domain": req.domain,
        "required_skills": req.required_skills or [],
        "qualifications": req.qualifications or [],
        "min_experience_years": req.min_experience_years or 0,
        "required_certifications": req.required_certifications or [],
        "min_training_experience_years": req.min_training_experience_years or 0,
        "availability_needed": req.availability_needed or {},
    }


def _trainer_to_dict(trainer):
    domains = [d.domain_name for d in trainer.domains]
    skills = [d.skill_name for d in trainer.domains if d.skill_name]
    qualifications = []  # qualifications currently modeled via TrainerCertification.name for the demo
    certifications = [c.name for c in trainer.certifications]
    experience_years = sum((e.years or 0) for e in trainer.experiences)
    training_experience_years = sum((e.training_delivery_years or 0) for e in trainer.experiences)

    return {
        "domains": domains,
        "skills": skills,
        "qualifications": qualifications,
        "experience_years": experience_years,
        "certifications": certifications,
        "training_experience_years": training_experience_years,
        "availability": trainer.availability or {},
        "rating_avg": trainer.rating_avg or 0,
    }


def compute_matches_for_requirement(requirement, persist=True):
    """Loads real trainers from the requirement's organization, scores them
    with the transparent weighted algorithm, and (optionally) persists
    TrainerMatch rows. Returns the persisted (or transient) TrainerMatch
    objects sorted by rank."""
    trainers = TrainerProfile.query.filter_by(
        organization_id=requirement.organization_id, is_active=True
    ).all()

    requirement_dict = _requirement_to_dict(requirement)
    trainer_pairs = [(t.id, _trainer_to_dict(t)) for t in trainers]

    ranked = rank_trainers_for_requirement(requirement_dict, trainer_pairs)

    if persist:
        # Clear any previous match rows for this requirement before recomputing,
        # so results always reflect current database state (never stale/hardcoded).
        TrainerMatch.query.filter_by(requirement_id=requirement.id).delete()

    results = []
    for r in ranked:
        match = TrainerMatch(
            organization_id=requirement.organization_id,
            requirement_id=requirement.id,
            trainer_id=r["trainer_id"],
            match_percentage=r["match_percentage"],
            rank=r["rank"],
            matched_criteria=r["matched_criteria"],
            missing_criteria=r["missing_criteria"],
        )
        if persist:
            db.session.add(match)
        results.append(match)

    return results
