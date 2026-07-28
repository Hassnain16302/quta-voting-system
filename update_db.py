from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE elections ADD COLUMN active_offline_voter_id INTEGER NULL;"))
        db.session.commit()
        print("✅ Successfully added 'active_offline_voter_id' to Aiven!")
    except Exception as e:
        print("⚠️ Error:", str(e))