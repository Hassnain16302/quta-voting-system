import json
import os
from web3 import Web3
from flask import current_app
from pathlib import Path
from web3.middleware import geth_poa_middleware 

# ✅ Completely removed solcx imports and install_solc()

def compile_contract():
    """
    - Bypasses live compilation to avoid Render firewall blocks.
    - Reads the pre-compiled ABI and Bytecode from JSON.
    """
    file_path = Path(__file__).parent / "compiled_contract.json"
    
    if not file_path.exists():
        raise FileNotFoundError("compiled_contract.json is missing! Run contracts/compile.py locally first.")
        
    with open(file_path, "r") as f:
        data = json.load(f)
        
    return data["abi"], data["bytecode"]

# ... Keep your existing deploy_contract(), load_contract_instance(), etc. exactly as they are below this point ...



from web3.middleware import geth_poa_middleware # Add this import

def deploy_contract():
    """
    - Connects to Infura/Ganache
    - Injects PoA middleware for Sepolia compatibility
    - Signs and Deploys the compiled Voting.sol contract
    """
    try:
        rpc_url = current_app.config.get("GANACHE_URL")
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # ✅ Inject PoA middleware for Sepolia testnet compatibility
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if not w3.is_connected():
            current_app.logger.critical("Blockchain connection failed")
            raise ConnectionError("Could not connect to blockchain at " + rpc_url)

        abi, bytecode = compile_contract()
        
        # ✅ Use Admin account from environment variables instead of local node accounts
        admin_account = Web3.to_checksum_address(os.getenv("ADMIN_ACCOUNT"))
        admin_private_key = os.getenv("ADMIN_PRIVATE_KEY")
        
        if not admin_private_key or not admin_account:
            raise ValueError("ADMIN_ACCOUNT or ADMIN_PRIVATE_KEY is missing from environment variables.")

        Voting = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # ✅ Build the deployment transaction
        construct_txn = Voting.constructor().build_transaction({
            'from': admin_account,
            'nonce': w3.eth.get_transaction_count(admin_account),
            'gas': 3000000, # Estimated gas for contract deployment
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        })
        
        # ✅ Sign the transaction with your MetaMask Private Key
        signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key=admin_private_key)
        
        # ✅ Send the signed transaction to Infura
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        current_app.logger.info("Deploying contract... waiting for receipt.")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        current_app.logger.info(f"Contract deployed at {tx_receipt.contractAddress}")
        return tx_receipt.contractAddress, abi
        
    except Exception as e:
        current_app.logger.error(f"Deployment failed: {str(e)}")
        raise

from web3.middleware import geth_poa_middleware
from web3 import Web3
from flask import current_app

def load_contract_instance(w3, address=None):
    """
    - Uses the provided Web3 instance (w3) and an address.
    - Injects PoA middleware (Crucial for Sepolia).
    - Returns ONLY the Web3.py contract instance.
    """
    # ✅ 1. Inject PoA middleware for Sepolia compatibility
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except ValueError:
        # If it's already injected, safely ignore the error
        pass 
    
    # ✅ 2. Resolve the contract address
    if not address:
        address = current_app.config.get("CONTRACT_ADDRESS")
    if not address:
        raise ValueError("No contract address provided in Config or argument.")
        
    # ✅ 3. Ensure the address is formatted securely (Checksum)
    checksum_address = Web3.to_checksum_address(address)
    
    # ✅ 4. Load the compiled ABI
    abi, _ = compile_contract()  
    
    # ✅ 5. Create and return ONLY the contract instance
    contract = w3.eth.contract(address=checksum_address, abi=abi)
    return contract

def cast_vote(contract, w3, candidate_id, voter_address):
    """
    Builds unsigned transaction (MetaMask signs it on frontend).
    """
    voter_address = Web3.to_checksum_address(voter_address)
    txn = contract.functions.vote(candidate_id).build_transaction({
        "chainId": 1337,
        "gas": 200000,
        "from": voter_address,
        "nonce": w3.eth.get_transaction_count(voter_address),
    })
    return txn




# In voting_system/app/blockchain.py

# Replace the old get_all_votes function with this one
# In voting_system/app/blockchain.py

def get_all_votes(contract, w3, election_id, candidates_list): # Pass Candidate objects
    """
    - Fetch vote counts for each candidate using their contract_cid.
    - Returns dict {candidate_db_id: vote_count}
    """
    results = {}
    for candidate in candidates_list:
        if candidate.contract_cid is not None:
            try:
                # ✅ Use contract_cid to query the contract
                count = contract.functions.getResults(election_id, candidate.contract_cid).call()
                # Store result using database ID as key
                results[candidate.id] = count
            except Exception as e:
                print(f"⚠️ Error fetching votes for contract_cid {candidate.contract_cid}: {e}")
                results[candidate.id] = 0 # Default to 0 on error
        else:
            # Handle case where candidate wasn't registered on contract (shouldn't happen with the fix)
            print(f"⚠️ Candidate DB ID {candidate.id} has no contract_cid.")
            results[candidate.id] = 0
    return results

# New helper: server-side signing and sending (recommended)
import os
from web3 import Web3

# In voting_system/app/blockchain.py
# In voting_system/app/blockchain.py

def send_signed_transaction(w3, raw_txn):
    admin_private_key = os.getenv("ADMIN_PRIVATE_KEY")
    if not admin_private_key:
        raise ValueError("ADMIN_PRIVATE_KEY is not set in the environment.")

    try:
        signed = w3.eth.account.sign_transaction(raw_txn, private_key=admin_private_key)

        # --- Debugging (Can be removed later) ---
        print("Signed Transaction Object:", signed)
        print("Attributes:", dir(signed))
        # --- End Debugging ---

        # ✅ FIXED: Use the correct attribute 'raw_transaction' (lowercase with underscore)
        if hasattr(signed, 'raw_transaction'):
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction) # Changed here
            print(f"Transaction sent, hash: {tx_hash.hex()}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            print("Transaction receipt received.")
            return receipt
        else:
            # Fallback message, though the debug output confirmed 'raw_transaction' exists
            raise AttributeError("The signed transaction object does not have 'raw_transaction'. Available: " + str(dir(signed)))

    except ValueError as ve:
        print(f"Error during signing or sending: {ve}")
        raise ValueError(f"Failed to sign/send transaction: {ve}") from ve
    except Exception as e:
        print(f"An unexpected error occurred in send_signed_transaction: {e}")
        raise e


def cast_vote_as_admin(contract, w3, election_id, voter_id, candidate_ids):
    """
    Admin account will submit votes on behalf of voter_id.
    """
    admin_addr = w3.eth.accounts[0] if not os.getenv("ADMIN_ACCOUNT") else os.getenv("ADMIN_ACCOUNT")
    # Build transaction using admin account as 'from'
    txn = contract.functions.voteBulkById(election_id, voter_id, candidate_ids).build_transaction({
        "chainId": w3.eth.chain_id,
        "gas": 400000,
        "from": admin_addr,
        "nonce": w3.eth.get_transaction_count(admin_addr),
    })

    # If server has ADMIN_PRIVATE_KEY, sign and send
    if os.getenv("ADMIN_PRIVATE_KEY"):
        receipt = send_signed_transaction(w3, txn)
        return receipt

    # Otherwise return unsigned txn (so an admin UI / metamask can sign it)
    return txn

