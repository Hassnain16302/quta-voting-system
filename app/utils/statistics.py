from collections import defaultdict
from app import db
from app.models import (
    Candidate,
    Election,
    User,
    ElectionStatisticsArchive
)
from app.blockchain import load_contract_instance, get_all_votes


def archive_statistics_from_blockchain(election_id):
    """
    Archives the election results from blockchain into ElectionStatisticsArchive.
    Cleans old archive data for the same election_id to avoid duplication.
    """
    print(f"📦 Archiving results for election ID {election_id}...")

    # Clean archive if it exists for this election
    ElectionStatisticsArchive.query.filter_by(election_id=election_id).delete()
    db.session.flush()

    election = Election.query.get(election_id)
    if not election:
        print("❌ Election not found.")
        return

    # Load contract
    try:
        w3, contract = load_contract_instance(election.contract_address)
    except Exception as e:
        print(f"❌ Failed to load contract: {e}")
        # Propagate error to show a flash message to the admin
        raise Exception("Failed to connect to the blockchain contract.") from e

    # Get candidates and vote counts
    candidates = Candidate.query.filter_by(election_id=election_id).all()


    try:
        # ✅ FIXED: Pass the election_id to the function call
        vote_counts = get_all_votes(contract, w3, election_id, candidates)
    except Exception as e:
        print(f"❌ Failed to get votes from blockchain: {e}")
        # Propagate a more specific error to the user
        raise Exception("Failed to retrieve vote counts from the blockchain.") from e

    total_votes = sum(vote_counts.values())
    total_voters = User.query.filter(
        User.is_eligible_voter == True,
        User.email != "admin@university.com"
    ).count()

    for c in candidates:
        user = User.query.get(c.user_id)
        if not user:
            continue  # skip orphaned candidate
        archive = ElectionStatisticsArchive(
            election_id=election_id,
            candidate_name=user.full_name,
            candidate_email=user.email,
            designation=c.designation,
            vote_count=vote_counts.get(c.id, 0),
            title=election.title,
            votes_cast=total_votes,
            total_voters=total_voters
        )
        db.session.add(archive)

    db.session.commit()
    print(f"✅ Archived results for election {election_id}")

def get_live_results(election):
    """
    Returns a leaderboard dictionary from live blockchain vote counts.
    Format: { designation: [(candidate_name, vote_count), ...] }
    """
    print(f"🔍 Fetching live results for election ID {election.id}...")

    try:
        w3, contract = load_contract_instance(election.contract_address)
    except Exception as e:
        print(f"❌ Could not load contract: {e}")
        return {}

    candidates = Candidate.query.filter_by(election_id=election.id).all()
    candidate_ids = [c.id for c in candidates]

    try:
        vote_counts = get_all_votes(contract, w3, candidate_ids)
    except Exception as e:
        print(f"❌ Could not get votes from blockchain: {e}")
        return {}

    leaderboard = defaultdict(list)
    for c in candidates:
        user = User.query.get(c.user_id)
        if not user:
            continue
        vote_count = vote_counts.get(c.id, 0)
        leaderboard[c.designation].append((user.full_name, vote_count))

    for desig in leaderboard:
        leaderboard[desig].sort(key=lambda x: x[1], reverse=True)

    print(f"📋 Live leaderboard: {dict(leaderboard)}")
    return leaderboard
