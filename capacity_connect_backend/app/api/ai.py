from flask import Blueprint, g, jsonify, request

from app.auth.utils import log_audit_event, roles_required, token_required
from app.services.ai_service import answer_question

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/ask", methods=["POST"])
@token_required
@roles_required("MANAGER", "ADMIN")
def ask():
    """CAPACITY AI: Question -> Intent Detection -> RBAC Validation ->
    Authorized DB Query -> Verified Data -> Natural Language Response.
    Manager AI can only ever see their own team's data; Admin AI sees the
    whole organization. Both are still fully scoped to the caller's
    organization_id - nothing crosses tenant boundaries."""
    data = request.get_json(force=True, silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    result = answer_question(g.current_user, question)
    log_audit_event("AI_QUERY", "ai", None, {"question": question, "intent": result["intent"]})
    return jsonify(result)
