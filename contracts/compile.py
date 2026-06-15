from solcx import compile_standard, install_solc
import json
from pathlib import Path

# This only runs on your local machine, so the download will work!
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
                        "*": ["abi", "evm.bytecode.object"]
                    }
                }
            },
        },
        solc_version="0.8.0",
    )

    abi = compiled["contracts"]["Voting.sol"]["Voting"]["abi"]
    bytecode = compiled["contracts"]["Voting.sol"]["Voting"]["evm"]["bytecode"]["object"]

    # Save the compiled data directly into the app folder
    output_path = Path(__file__).parent.parent / "app" / "compiled_contract.json"
    with open(output_path, "w") as f:
        json.dump({"abi": abi, "bytecode": bytecode}, f)
        
    print(f"✅ Contract compiled successfully! Saved to {output_path}")

if __name__ == "__main__":
    main()