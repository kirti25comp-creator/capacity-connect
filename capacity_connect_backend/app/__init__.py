import os

from flask import Flask, jsonify

from app.config import Config
from app.extensions import db


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    # Import models so SQLAlchemy metadata is registered before create_all()/migrations.
    from app import models  # noqa: F401

    register_blueprints(app)
    register_error_handlers(app)
    register_security_headers(app)

    return app


def register_blueprints(app):
    from app.auth.routes import auth_bp
    from app.api.admin import admin_bp
    from app.api.manager import manager_bp
    from app.api.trainer import trainer_bp
    from app.api.employee import employee_bp
    from app.api.courses import courses_bp
    from app.api.training import training_bp
    from app.api.assessments import assessments_bp
    from app.api.feedback import feedback_bp
    from app.api.competency import competency_bp
    from app.api.certificates import certificates_bp
    from app.api.notifications import notifications_bp
    from app.api.ai import ai_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(trainer_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(competency_bp)
    app.register_blueprint(certificates_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(ai_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "capacity-connect-backend"})


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500


def register_security_headers(app):
    @app.after_request
    def set_secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # CSRF: this API is stateless-JWT (Authorization header), not cookie-session
        # based, so classic CSRF does not apply to it the way it would to a
        # cookie-authenticated app. If cookie-based session auth is ever added,
        # Flask-WTF's CSRFProtect should be wired in here.
        return response
