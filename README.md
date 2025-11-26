# Last-Y-Train: Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a critical component for a cross-chain bridge: the Event Listener. This component—often run by validators or oracles—is responsible for watching for specific events on a source blockchain (e.g., tokens being locked) and initiating corresponding actions on a destination blockchain (e.g., minting wrapped tokens).

This script is designed to be architecturally sound and robust, demonstrating the patterns used in real-world decentralized application backend services.

## Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain to another. A common pattern is "lock-and-mint":

1.  **Lock**: A user sends tokens to a bridge contract on the **Source Chain**. The contract locks these tokens and emits an event (e.g., `BridgeTransferInitiated`) containing details of the transaction.
2.  **Verify**: Off-chain services (known as listeners, oracles, or validators) monitor the Source Chain for these events.
3.  **Mint/Release**: After verifying the event, these services submit a signed transaction to a corresponding bridge contract on the **Destination Chain**. This transaction authorizes the minting or releasing of an equivalent amount of wrapped tokens to the user's address on the new chain.

This script simulates the **Verify** and **Mint/Release** steps. It connects to a source chain, polls for new blocks, filters for `BridgeTransferInitiated` events, and then prepares and signs a transaction to complete the bridge transfer on the destination chain. For safety, the final step of broadcasting the transaction is simulated by logging the signed transaction.

## Code Architecture

The script is designed with a clear separation of concerns, organized into several main classes:

-   `BridgeConfig` (Dataclass):
    A simple data class that holds all necessary configuration parameters, such as RPC endpoints, contract addresses, and private keys. It is populated from environment variables for security.

-   `ChainConnector`:
    This class is a wrapper around the `web3.py` library. Its sole responsibility is to manage the connection to a specific blockchain node (source or destination). It handles Web3 instance creation and provides a clean interface for loading contract objects. This isolates chain-specific connection logic.

-   `BridgeEventHandler`:
    This is the core logic engine. It is responsible for processing a single event that has been detected by the main listener loop. Its tasks include:
    -   Parsing event data.
    -   Checking for duplicates to prevent re-entrancy or double-spending attacks.
    -   Constructing the corresponding transaction for the destination chain (e.g., `releaseTokens`).
    -   Signing the transaction using the listener's private key.
    -   Simulating the broadcast of the transaction.

-   `BridgeEventListener`:
    The main orchestrator class. It initializes all other components and runs the primary infinite loop. Its responsibilities are:
    -   Setting up connections to both source and destination chains via `ChainConnector`.
    -   Managing the state of which blocks have been scanned (`last_processed_block`).
    -   Periodically polling the source chain for new blocks.
    -   Filtering blocks for relevant events from the source bridge contract.
    -   Passing any found events to the `BridgeEventHandler` for processing.
    -   Handling RPC connection errors and other exceptions gracefully.
    
    A conceptual example of its usage in `main.py`:
    ```python
    if __name__ == "__main__":
        config = BridgeConfig.load_from_env()
        listener = BridgeEventListener(config)
        listener.run()
    ```

## How it Works

The script follows a logical, sequential flow:

1.  **Initialization**: Upon starting, the script loads the necessary configuration from a `.env` file.
2.  **Connection**: The `BridgeEventListener` creates two `ChainConnector` instances, one for the source chain and one for the destination chain, establishing a connection to their respective RPC nodes.
3.  **State Restoration**: It determines the block number to start scanning from. If a `START_BLOCK` is provided, it uses that; otherwise, it starts from the current latest block.
4.  **Polling Loop**: The script enters an infinite `while True` loop.
5.  **Block Scanning**: In each iteration, it checks the latest block number on the source chain. If the latest block is ahead of the `last_processed_block`, it defines a range of blocks to scan.
6.  **Event Filtering**: It uses `web3.py`'s event filtering mechanism (`create_filter`) to efficiently query the node for any `BridgeTransferInitiated` events within that block range.
7.  **Event Processing**: If events are found, it iterates through them and passes each one to the `BridgeEventHandler`.
8.  **Transaction Simulation**: The `BridgeEventHandler` decodes the event, builds a `releaseTokens` transaction for the destination chain, signs it with the provided private key, and logs the details of what *would* have been sent to the network.
9.  **State Update**: After processing the events in a block range, the `BridgeEventListener` updates its `last_processed_block` counter to ensure it doesn't scan the same blocks again.
10. **Wait**: The script then sleeps for a configurable interval (`POLL_INTERVAL_SECONDS`) before starting the next iteration of the loop.

## Getting Started

Follow these steps to run the simulation.

**1. Clone the repository:**

```bash
git clone <repository_url>
cd last-y-train
```

**2. Install dependencies:**

Create a virtual environment and install the required packages.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
```

**3. Create a `.env` file:**

Create a file named `.env` in the root of the project and populate it with your specific details. You will need RPC URLs from a service like [Infura](https://infura.io) or [Alchemy](https://www.alchemy.com).

```env
# RPC Endpoints for the chains you want to bridge between (e.g., Sepolia and Mumbai)
SOURCE_CHAIN_RPC="https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID"
DESTINATION_CHAIN_RPC="https://polygon-mumbai.g.alchemy.com/v2/YOUR_ALCHEMY_API_KEY"

# Addresses of the deployed bridge contracts on each chain
SOURCE_BRIDGE_ADDRESS="0x..."
DESTINATION_BRIDGE_ADDRESS="0x..."

# Private key of the "validator" or "oracle" account.
# This account is used to pay for gas to submit the `releaseTokens` transaction on the destination chain.
# IMPORTANT: Use a key from a test wallet with testnet funds ONLY. DO NOT USE A MAINNET KEY.
LISTENER_PRIVATE_KEY="0x..."

# (Optional) The block number to start scanning from. If 0 or not set, starts from the latest block.
START_BLOCK=0

# (Optional) The time in seconds to wait between polling for new blocks.
POLL_INTERVAL_SECONDS=15
```

**4. Run the script:**

Execute the main Python script from your terminal.

```bash
python main.py
```

**Expected Output:**

The script will start logging its activity to the console. When it finds a new `BridgeTransferInitiated` event on the source chain, you will see output similar to this:

```
2023-10-27 14:30:15,123 - INFO - [BridgeEventListener] - Starting bridge event listener. Watching contract 0x...
2023-10-27 14:30:16,456 - INFO - [BridgeEventListener] - Initial block to scan from: 4500123
...
2023-10-27 14:30:31,789 - INFO - [BridgeEventListener] - Scanning for 'BridgeTransferInitiated' events from block 4500124 to 4500125
2023-10-27 14:30:32,912 - INFO - [BridgeEventListener] - Found 1 new events.
2023-10-27 14:30:32,913 - INFO - [BridgeEventHandler] - Processing new event: transactionId=0xabc123...
2023-10-27 14:30:32,914 - INFO - [BridgeEventHandler] - Preparing to release 100000000 of token 0x... to 0x... on destination chain for source transactionId 0xabc123...
2023-10-27 14:30:33,567 - INFO - [BridgeEventHandler] - [SIMULATION] Would have sent transaction to release tokens.
2023-10-27 14:30:33,568 - INFO - [BridgeEventHandler] - [SIMULATION] Signed Tx: 0xdef456...
2023-10-27 14:30:33,569 - INFO - [BridgeEventHandler] - Successfully processed event for transactionId 0xabc123...
```