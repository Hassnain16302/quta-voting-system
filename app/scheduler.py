# In voting_system/app/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
# REMOVE: from app import create_app

# Keep scheduler instance global
scheduler = BackgroundScheduler(daemon=True)

# Store the app instance globally within the scheduler module
_app_instance = None

def check_and_archive_elections():
    # ... (app context setup) ...
    with _app_instance.app_context():
        print(f"[{datetime.utcnow()}] Scheduler: Checking for ended elections...")
        try:
            from app import db
            # Import both Election and ElectionStatisticsArchive
            from app.models import Election, ElectionStatisticsArchive
            from app.utils.statistics import archive_statistics_from_blockchain
            from sqlalchemy.orm import joinedload # Import for optimization

            now = datetime.utcnow()

            # ✅ UPDATED QUERY:
            # Find elections where end_time has passed
            ended_elections_query = Election.query.filter(Election.end_time <= now)

            # Eagerly load archive status to avoid N+1 queries later
            # This fetches related archive entries in the same query
            ended_elections = ended_elections_query.options(
                joinedload(Election.archived_stats) # Assumes a relationship named 'archived_stats' exists
            ).all()

            # Filter in Python: Keep only those WITHOUT archive entries
            elections_to_archive = [
                e for e in ended_elections if not e.archived_stats
            ]


            if not elections_to_archive:
                print("Scheduler: No ended elections found requiring archiving.")
                return

            for election in elections_to_archive:
                print(f"Scheduler: Found ended election ID {election.id} without archive. Attempting to archive...")
                try:
                    # Archive the results
                    archive_statistics_from_blockchain(election.id)

                    # ✅ OPTIONAL: Mark as closed AFTER successful archiving
                    # Although not strictly needed for the filter now,
                    # keeping is_closed might be useful for UI flags.
                    # Ensure election object is fresh if needed
                    election_to_update = db.session.get(Election, election.id)
                    if election_to_update:
                        election_to_update.is_closed = True
                        db.session.commit()
                    
                    print(f"✅ Scheduler: Successfully archived election ID {election.id}.")

                except Exception as archive_err:
                    db.session.rollback() # Rollback setting is_closed if archiving failed
                    print(f"❌ Scheduler: Failed to archive election ID {election.id}. Error: {archive_err}")
                    _app_instance.logger.error(f"Scheduler failed to archive election {election.id}: {archive_err}")

        except Exception as e:
            print(f"❌ Scheduler: An error occurred during the check: {e}")
            _app_instance.logger.error(f"Scheduler error during check_and_archive_elections: {e}")


def start_scheduler(app): # ✅ Accept app as an argument
    """Starts the background scheduler if it's not already running."""
    global _app_instance
    _app_instance = app # ✅ Store the app instance

    if not scheduler.running:
        scheduler.add_job(
            func=check_and_archive_elections,
            trigger="interval",
            minutes=1,
            id="archive_job",
            replace_existing=True
        )
        try:
            scheduler.start()
            print("⏰ Background scheduler started.")
        except Exception as e:
            print(f"❌ Error starting scheduler: {e}")
            app.logger.error(f"Error starting scheduler: {e}")
    else:
        print("⏰ Background scheduler already running.")