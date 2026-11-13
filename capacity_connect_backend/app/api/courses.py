from flask import Blueprint, g, jsonify

from app.auth.utils import roles_required, token_required
from app.models.training import Course

courses_bp = Blueprint("courses", __name__, url_prefix="/api/courses")


@courses_bp.route("", methods=["GET"])
@token_required
@roles_required("ADMIN", "MANAGER", "TRAINER", "EMPLOYEE")
def list_courses():
    courses = Course.query.filter_by(organization_id=g.current_user.organization_id, is_active=True).all()
    return jsonify({"courses": [c.to_dict() for c in courses]})


@courses_bp.route("/<course_id>", methods=["GET"])
@token_required
@roles_required("ADMIN", "MANAGER", "TRAINER", "EMPLOYEE")
def get_course(course_id):
    course = Course.query.filter_by(id=course_id, organization_id=g.current_user.organization_id).first()
    if course is None:
        return jsonify({"error": "Course not found"}), 404
    return jsonify({"course": course.to_dict()})
