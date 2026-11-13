"""Skill-gap engine: compares an employee's demonstrated proficiency for a
skill (derived from assessment performance / training results) against the
required competency level and classifies the gap.

All inputs are plain numbers/strings so this stays testable without a DB.
"""

MAJOR_GAP_THRESHOLD = 0.5   # assessed/required ratio below this => MAJOR gap
MODERATE_GAP_THRESHOLD = 0.8  # below this (but >= major) => MODERATE gap
STRONG_THRESHOLD = 1.0       # at/above required => STRONG


def classify_skill_level(assessed_level, required_level):
    """assessed_level and required_level are both on a 0-100 scale.

    Returns (gap_level, strength_label) where:
      gap_level in {NONE, MODERATE, MAJOR}
      strength_label in {STRONG, MODERATE, WEAK}
    """
    if required_level is None or required_level <= 0:
        # No explicit requirement recorded - grade purely on demonstrated skill.
        if assessed_level >= 80:
            return "NONE", "STRONG"
        if assessed_level >= 50:
            return "MODERATE", "MODERATE"
        return "MAJOR", "WEAK"

    ratio = assessed_level / required_level

    if ratio >= STRONG_THRESHOLD:
        return "NONE", "STRONG"
    if ratio >= MODERATE_GAP_THRESHOLD:
        return "MODERATE", "MODERATE"
    if ratio >= MAJOR_GAP_THRESHOLD:
        return "MODERATE", "WEAK"
    return "MAJOR", "WEAK"


def derive_assessed_level(assessment_percentages):
    """assessment_percentages: list of floats (0-100) from assessments tagged
    with this skill. Returns the average, or 0 if no data."""
    if not assessment_percentages:
        return 0.0
    return sum(assessment_percentages) / len(assessment_percentages)


def build_skill_gap_report(employee_skill_data):
    """employee_skill_data: list of dicts:
      {"skill_name": str, "required_level": float, "assessment_percentages": [float,...]}

    Returns a list of {"skill_name", "assessed_level", "required_level",
    "gap_level", "strength_label"} - this is what gets persisted as
    CompetencyRecord rows.
    """
    report = []
    for item in employee_skill_data:
        assessed = derive_assessed_level(item.get("assessment_percentages", []))
        required = item.get("required_level")
        gap_level, strength = classify_skill_level(assessed, required)
        report.append(
            {
                "skill_name": item["skill_name"],
                "assessed_level": round(assessed, 2),
                "required_level": required,
                "gap_level": gap_level,
                "strength_label": strength,
            }
        )
    return report
