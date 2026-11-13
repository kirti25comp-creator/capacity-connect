import os

from flask.cli import FlaskGroup

from app import create_app
from app.extensions import db

app = create_app()
cli = FlaskGroup(create_app=lambda: app)


@app.cli.command("init-db")
def init_db():
    """Create all tables (SQLite hackathon prototype - no migrations)."""
    with app.app_context():
        db.create_all()
    print("Database tables created.")


@app.cli.command("seed-db")
def seed_db():
    from app.seed import run_seed

    with app.app_context():
        run_seed()
    print("Demo data seeded.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
