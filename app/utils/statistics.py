from collections import defaultdict
from app import db
from app.models import (
    Candidate,
    Election,
    User,
    ElectionStatisticsArchive
)
from app.blockchain import load_contract_instance, get_all_votes

import os
from web3 import Web3
from app.models import db, Candidate, Election, ElectionStatisticsArchive


def archive_statistics_from_blockchain(election_id):
    election = Election.query.get(election_id)
    if not election:
        raise ValueError("Election not found.")

    # 1. Connect to the blockchain
    rpc_url = os.getenv("WEB3_PROVIDER_URI", "https://ethereum-sepolia-rpc.publicnode.com")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    contract = load_contract_instance(w3, election.contract_address)

    # 2. Fetch candidates in the EXACT order they were added to the blockchain
    candidates = Candidate.query.filter_by(election_id=election_id).order_by(Candidate.id.asc()).all()

    # 3. Query the blockchain using the array index (0, 1, 2...)
    for index, c in enumerate(candidates):
        
        # THE FIX: Use 'index' instead of 'c.id'
        blockchain_vote_count = contract.functions.getVotes(index).call()
        
        archive_entry = ElectionStatisticsArchive(
            election_id=election.id,
            candidate_name=c.user.full_name,
            designation=c.designation,
            vote_count=blockchain_vote_count
        )
        db.session.add(archive_entry)
        
    db.session.commit()


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
