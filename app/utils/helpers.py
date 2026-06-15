# app/utils/helpers.py

from app.models import Candidate
from app import db

def patch_candidates_to_latest_election(election_id):
    """
    Assigns the given election_id to all candidates in the system,
    regardless of their current election_id.
    """
    candidates = Candidate.query.all()  # ✅ No filter on election_id
    for c in candidates:
        c.election_id = election_id
    db.session.commit()

