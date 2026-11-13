from flask import Blueprint, g, jsonify

from app.auth.utils import roles_required, token_required
from app.models.employee import ManagerEmployeeAssignment
from app.models.misc import Feedback
from app.models.trainer import TrainerProfile

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@feedback_bp.route("/trainers/<trainer_id>", methods=["GET"])
@token_required
@roles_required("ADMIN", "MANAGER")
def feedback_for_trainer(trainer_id):
    trainer = TrainerProfile.query.filter_by(id=trainer_id, organization_id=g.current_user.organization_id).first()
    if trainer is None:
        return jsonify({"error": "Trainer not found"}), 404

    feedback = Feedback.query.filter_by(trainer_id=trainer_id, organization_id=g.current_user.organization_id).all()

    if g.current_user.role == "MANAGER":
        my_employee_ids = {
            r.employee_id
            for r in ManagerEmployeeAssignment.query.filter_by(
                organization_id=g.current_user.organization_id, manager_id=g.current_user.id
            ).all()
        }
        feedback = [f for f in feedback if f.employee_id in my_employee_ids]

    return jsonify({"feedback": [f.to_dict() for f in feedback]})
