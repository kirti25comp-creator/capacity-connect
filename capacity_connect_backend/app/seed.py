"""Demo/seed data for the CAPACITY CONNECT hackathon prototype.

Creates TWO organizations (to make cross-org isolation easy to demo/test),
each with an admin, a manager, a couple of employees, and a trainer with a
course + assessment. Run with:

    flask --app run.py init-db
    flask --app run.py seed-db
"""
import datetime

from app.extensions import db
from app.models.core import Department, Organization, User
from app.models.employee import EmployeeProfile, ManagerEmployeeAssignment
from app.models.trainer import TrainerCertification, TrainerDomain, TrainerExperience, TrainerProfile
from app.models.training import Course, TrainingRequirement


def _make_org(name, code, reg_number):
    org = Organization(
        name=name,
        code=code,
        registration_number=reg_number,
        verification_status="MOCK_VERIFIED",
        verification_source="MOCK_MCA_DEMO",
        is_active=True,
    )
    db.session.add(org)
    db.session.flush()
    return org


def _make_user(org, email, name, role, password="Password123!"):
    u = User(
        organization_id=org.id,
        email=email,
        full_name=name,
        role=role,
        is_active=True,
        activated_at=datetime.datetime.utcnow(),
    )
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def _build_organization(name, code, reg_number, suffix):
    org = _make_org(name, code, reg_number)

    admin = _make_user(org, f"admin@{suffix}.demo", f"{name} Admin", "ADMIN")
    manager = _make_user(org, f"manager@{suffix}.demo", f"{name} Manager", "MANAGER")

    dept = Department(organization_id=org.id, name="Engineering")
    db.session.add(dept)
    db.session.flush()

    emp1 = _make_user(org, f"employee1@{suffix}.demo", f"{name} Employee One", "EMPLOYEE")
    emp2 = _make_user(org, f"employee2@{suffix}.demo", f"{name} Employee Two", "EMPLOYEE")

    for emp, skills in (
        (emp1, [{"name": "Python", "level": "Intermediate"}, {"name": "SQL", "level": "Beginner"}]),
        (emp2, [{"name": "SQL", "level": "Intermediate"}, {"name": "Data Analysis", "level": "Beginner"}]),
    ):
        db.session.add(
            EmployeeProfile(
                user_id=emp.id,
                organization_id=org.id,
                department_id=dept.id,
                job_title="Software Engineer",
                skills=skills,
                hire_date=datetime.date(2024, 1, 15),
            )
        )
        db.session.add(
            ManagerEmployeeAssignment(organization_id=org.id, manager_id=manager.id, employee_id=emp.id)
        )

    trainer_user = _make_user(org, f"trainer@{suffix}.demo", f"{name} Trainer", "TRAINER")
    trainer = TrainerProfile(
        user_id=trainer_user.id,
        organization_id=org.id,
        trainer_type="INTERNAL",
        bio="Senior Python & SQL trainer.",
        availability={"days": ["mon", "wed", "fri"], "hours_per_week": 10},
        rating_avg=4.2,
    )
    db.session.add(trainer)
    db.session.flush()

    db.session.add(TrainerDomain(trainer_id=trainer.id, domain_name="python", skill_name="python", proficiency="EXPERT"))
    db.session.add(TrainerDomain(trainer_id=trainer.id, domain_name="python", skill_name="sql", proficiency="EXPERT"))
    db.session.add(
        TrainerCertification(trainer_id=trainer.id, name="AWS Certified", issuer="AWS", issue_date=datetime.date(2023, 1, 1))
    )
    db.session.add(
        TrainerExperience(trainer_id=trainer.id, domain="python", years=6, training_delivery_years=3, description="6 years professional Python + 3 years delivering internal training")
    )

    course = Course(
        organization_id=org.id,
        trainer_id=trainer.id,
        title="Advanced Python",
        domain="python",
        description="Deep dive into advanced Python and SQL for engineers.",
        resources=[{"type": "pdf", "title": "Course Handbook"}],
    )
    db.session.add(course)
    db.session.flush()

    requirement = TrainingRequirement(
        organization_id=org.id,
        manager_id=manager.id,
        subject="Advanced Python",
        domain="python",
        required_skills=["python", "sql"],
        qualifications=[],
        min_experience_years=3,
        required_certifications=["aws certified"],
        min_training_experience_years=2,
        availability_needed={"days": ["mon", "wed"], "hours_per_week": 5},
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=30),
    )
    db.session.add(requirement)

    return {
        "organization": org,
        "admin": admin,
        "manager": manager,
        "employees": [emp1, emp2],
        "trainer_user": trainer_user,
        "trainer_profile": trainer,
        "course": course,
        "requirement": requirement,
    }


def run_seed():
    org_a = _build_organization("Acme Corp", "ACME", "REG-A-001", "acme")
    org_b = _build_organization("Globex Inc", "GLOBEX", "REG-B-002", "globex")
    db.session.commit()

    print("Seeded two organizations for isolation testing:")
    for label, data in (("Acme Corp", org_a), ("Globex Inc", org_b)):
        org = data["organization"]
        print(f"\n{label} (code={org.code}, org_id={org.id})")
        print(f"  admin:    {data['admin'].email} / Password123!")
        print(f"  manager:  {data['manager'].email} / Password123!")
        print(f"  employee: {data['employees'][0].email} / Password123!")
        print(f"  trainer:  {data['trainer_user'].email} / Password123!")

    return {"org_a": org_a, "org_b": org_b}
