from solcx import compile_standard, install_solc
import json
from pathlib import Path

install_solc("0.8.0")

def main():
    contract_path = Path(__file__).parent / "Voting.sol"
    source = contract_path.read_text()

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"Voting.sol": {"content": source}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]
                    }
                }
            },
        },
        solc_version="0.8.0",
    )

    # Write ABI to a file for manual inspection (optional)
    abi = compiled["contracts"]["Voting.sol"]["Voting"]["abi"]
    bytecode = compiled["contracts"]["Voting.sol"]["Voting"]["evm"]["bytecode"]["object"]

    (Path(__file__).parent / "VotingABI.json").write_text(json.dumps(abi))
    (Path(__file__).parent / "VotingBytecode.bin").write_text(bytecode)
    print("ABI and Bytecode generated in contracts/ directory.")

if __name__ == "__main__":
    main()
