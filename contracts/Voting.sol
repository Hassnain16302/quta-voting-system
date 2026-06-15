// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @title Voting contract adapted for single-submitter architecture (admin submits votes for voterIds)
contract Voting {
    address public admin;

    struct Election {
        uint256 id;
        string title;
    }

    struct Candidate {
        uint256 id;
        address user;   // optional: Ethereum address of candidate
        bool active;
    }

    // electionId => Election metadata
    mapping(uint256 => Election) public elections;

    // electionId => voterId => hasVoted?
    mapping(uint256 => mapping(uint256 => bool)) public hasVotedById;

    // electionId => candidateId => votes
    mapping(uint256 => mapping(uint256 => uint256)) public votes;

    // electionId => list of candidates
    mapping(uint256 => Candidate[]) public electionCandidates;

    // electionId => registered voters (by voterId)
    mapping(uint256 => mapping(uint256 => bool)) public eligibleVoterIds;

    // --- Events ---
    /* note: we emit voterId (uint256) rather than an address */
    event VoteCastById(uint256 indexed electionId, uint256 indexed voterId, uint256[] candidateIds, uint256 timestamp);
    event CandidateAdded(uint256 indexed electionId, uint256 indexed candidateId, address user);
    event VoterAddedById(uint256 indexed electionId, uint256 indexed voterId);
    event UserDeactivatedById(uint256 indexed electionId, uint256 indexed voterId);

    constructor() {
        admin = msg.sender;
    }

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can call this function");
        _;
    }




    // --- Admin: add participants ---
    function addCandidate(uint256 electionId, address user) public onlyAdmin returns (uint256) { // Add "returns (uint256)"
    uint256 newId = electionCandidates[electionId].length;
    electionCandidates[electionId].push(Candidate(newId, user, true));
    emit CandidateAdded(electionId, newId, user);
    return newId; // ✅ ADD THIS LINE
}

    /// Register a voter using a numeric voterId (admin-only)
    function addVoterById(uint256 electionId, uint256 voterId) public onlyAdmin {
        require(!eligibleVoterIds[electionId][voterId], "VoterId already registered");
        eligibleVoterIds[electionId][voterId] = true;
        emit VoterAddedById(electionId, voterId);
    }

    function deactivateVoterById(uint256 electionId, uint256 voterId) public onlyAdmin {
        eligibleVoterIds[electionId][voterId] = false;
        emit UserDeactivatedById(electionId, voterId);
    }

    /**
     * voteBulkById: admin/account that deploys contract will submit votes on behalf of a voterId.
     * - msg.sender MUST be admin (this prevents anyone else faking voters)
     * - the contract enforces eligibility by voterId and one-vote-per-voterId
     */
    function voteBulkById(
        uint256 electionId,
        uint256 voterId,
        uint256[] memory candidateIds
    )
        public
        onlyAdmin
    {
        require(eligibleVoterIds[electionId][voterId], "VoterId not eligible");
        require(!hasVotedById[electionId][voterId], "VoterId has already voted");

        for (uint256 i = 0; i < candidateIds.length; i++) {
            uint256 cid = candidateIds[i];
            require(cid < electionCandidates[electionId].length, "Invalid candidate id");
            require(electionCandidates[electionId][cid].active, "Candidate not active");
            votes[electionId][cid] += 1;
        }

        hasVotedById[electionId][voterId] = true;
        emit VoteCastById(electionId, voterId, candidateIds, block.timestamp);
    }

    // --- Results view ---
    function getResults(uint256 electionId, uint256 candidateId) public view returns (uint256) {
        return votes[electionId][candidateId];
    }

    function getCandidateCount(uint256 electionId) public view returns (uint256) {
        return electionCandidates[electionId].length;
    }

    function getCandidate(uint256 electionId, uint256 candidateId)
        public
        view
        returns (uint256, address, bool)
    {
        Candidate memory c = electionCandidates[electionId][candidateId];
        return (c.id, c.user, c.active);
    }



    // helper: check has voted by id
    function hasVotedByVoterId(uint256 electionId, uint256 voterId) public view returns (bool) {
        return hasVotedById[electionId][voterId];
    }

    // helper: check eligibility
    function isVoterIdEligible(uint256 electionId, uint256 voterId) public view returns (bool) {
        return eligibleVoterIds[electionId][voterId];
    }
}
