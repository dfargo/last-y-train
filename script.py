import os
import time
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests
from web3 import Web3
from web3.contract import Contract
from web3.logs import DISCARD
from web3.exceptions import ContractLogicError, TransactionNotFound
from dotenv import load_dotenv

# --- Basic Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger('BridgeEventListener')

# --- Constants ---
# In a real-world scenario, ABIs would be loaded from JSON files.
# For this simulation, we define a simplified ABI for the source bridge contract.
SOURCE_BRIDGE_ABI = json.loads('''
[
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "bytes32", "name": "transactionId", "type": "bytes32"},
            {"indexed": true, "internalType": "address", "name": "sender", "type": "address"},
            {"indexed": true, "internalType": "uint256", "name": "destinationChainId", "type": "uint256"},
            {"indexed": false, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "BridgeTransferInitiated",
        "type": "event"
    }
]
''')

# Simplified ABI for the destination bridge contract for simulation purposes.
DESTINATION_BRIDGE_ABI = json.loads('''
[
    {
        "inputs": [
            {"internalType": "bytes32", "name": "sourceTransactionId", "type": "bytes32"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "releaseTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
''')

@dataclass
class BridgeConfig:
    """Dataclass to hold configuration for the bridge listener."""
    source_chain_rpc: str
    destination_chain_rpc: str
    source_bridge_address: str
    destination_bridge_address: str
    listener_private_key: str # For signing transactions on the destination chain
    start_block: int = 0
    poll_interval_seconds: int = 15

class ChainConnector:
    """Handles connection and contract interaction with a specific blockchain."""

    def __init__(self, rpc_url: str):
        """
        Initializes the connection to a blockchain node via Web3.

        Args:
            rpc_url (str): The HTTP or WebSocket RPC endpoint for the blockchain node.
        """
        self.rpc_url = rpc_url
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.web3.is_connected():
            logger.error(f"Failed to connect to blockchain node at {rpc_url}")
            raise ConnectionError(f"Unable to connect to {rpc_url}")
        logger.info(f"Successfully connected to chain with ID: {self.web3.eth.chain_id}")

    def get_contract(self, address: str, abi: Dict[str, Any]) -> Contract:
        """
        Loads and returns a Web3 contract instance.

        Args:
            address (str): The contract's address.
            abi (Dict[str, Any]): The contract's ABI.

        Returns:
            Contract: A Web3 Contract object.
        """
        checksum_address = self.web3.to_checksum_address(address)
        return self.web3.eth.contract(address=checksum_address, abi=abi)

class BridgeEventHandler:
    """
    Processes events from the source chain and triggers actions on the destination chain.
    This class simulates the 'oracle' or 'validator' role in a bridge.
    """

    def __init__(self, config: BridgeConfig, dest_connector: ChainConnector):
        """
        Initializes the event handler.

        Args:
            config (BridgeConfig): The overall configuration object.
            dest_connector (ChainConnector): The connector for the destination chain.
        """
        self.config = config
        self.dest_connector = dest_connector
        self.dest_bridge_contract = self.dest_connector.get_contract(
            self.config.destination_bridge_address,
            DESTINATION_BRIDGE_ABI
        )
        self.processed_transactions = set() # In-memory store for processed event IDs

    def process_event(self, event: Dict[str, Any]):
        """
        Main logic for processing a single bridge event.
        It checks for duplicates and then simulates the token release on the destination chain.

        Args:
            event (Dict[str, Any]): The event data from web3.py.
        """
        try:
            tx_id = event['args']['transactionId'].hex()
            if tx_id in self.processed_transactions:
                logger.warning(f"Event with tx_id {tx_id} already processed. Skipping.")
                return

            logger.info(f"Processing new event: transactionId={tx_id}")
            # In a real scenario, we would perform more checks (e.g., confirmation count)
            self._simulate_release_tokens(event)

            self.processed_transactions.add(tx_id)
            logger.info(f"Successfully processed event for tx_id {tx_id}")

        except Exception as e:
            logger.error(f"Error processing event {event}: {e}", exc_info=True)

    def _simulate_release_tokens(self, event: Dict[str, Any]):
        """
        Simulates the process of building, signing, and sending a transaction
        to the destination bridge contract to release the corresponding tokens.

        Args:
            event (Dict[str, Any]): The source chain event.
        """
        args = event['args']
        sender_address = args['sender'] # The final recipient of the tokens
        tx_id = args['transactionId']

        logger.info(
            f"Preparing to release {args['amount']} of token {args['token']} "
            f"to {sender_address} on destination chain for source tx_id {tx_id.hex()}"
        )

        # --- This section simulates a real transaction --- #
        # 1. Get the account from private key
        account = self.dest_connector.web3.eth.account.from_key(self.config.listener_private_key)
        wallet_address = account.address

        # 2. Build the transaction
        try:
            nonce = self.dest_connector.web3.eth.get_transaction_count(wallet_address)
            tx_payload = {
                'from': wallet_address,
                'nonce': nonce,
                'gas': 200000, # A sensible default, can be estimated
                'gasPrice': self.dest_connector.web3.eth.gas_price,
            }

            release_tx = self.dest_bridge_contract.functions.releaseTokens(
                tx_id,
                sender_address,
                args['token'],
                args['amount']
            ).build_transaction(tx_payload)

            # 3. Sign the transaction
            signed_tx = self.dest_connector.web3.eth.account.sign_transaction(
                release_tx, private_key=self.config.listener_private_key
            )
            
            # 4. In this simulation, we will NOT send the transaction.
            # Instead, we will log the details.
            # In a real system, you would uncomment the following lines:
            # tx_hash = self.dest_connector.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            # logger.info(f"Submitted release transaction to destination chain. Tx hash: {tx_hash.hex()}")
            # receipt = self.dest_connector.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            # if receipt.status == 0:
            #     raise ContractLogicError("Token release transaction failed on-chain.")

            logger.info(f"[SIMULATION] Would have sent transaction to release tokens.")
            logger.info(f"[SIMULATION] Signed Tx: {signed_tx.hash.hex()}")

        except Exception as e:
            logger.error(f"Failed to build or sign the release transaction for {tx_id.hex()}: {e}", exc_info=True)
            # Implement retry logic or a dead-letter queue here for production systems
            raise

class BridgeEventListener:
    """
    The main orchestrator class that listens for events on the source chain.
    """

    def __init__(self, config: BridgeConfig):
        """
        Initializes the main listener service.

        Args:
            config (BridgeConfig): The configuration object.
        """
        self.config = config
        self.source_connector = ChainConnector(config.source_chain_rpc)
        self.dest_connector = ChainConnector(config.destination_chain_rpc)
        self.event_handler = BridgeEventHandler(config, self.dest_connector)
        self.source_bridge_contract = self.source_connector.get_contract(
            config.source_bridge_address, 
            SOURCE_BRIDGE_ABI
        )
        self.last_processed_block = config.start_block or self.source_connector.web3.eth.block_number

    def run(self):
        """
        Starts the main event listening loop.
        """
        logger.info(f"Starting bridge event listener. Watching contract {self.config.source_bridge_address}")
        logger.info(f"Initial block to scan from: {self.last_processed_block}")

        while True:
            try:
                latest_block = self.source_connector.web3.eth.block_number

                if latest_block > self.last_processed_block:
                    from_block = self.last_processed_block + 1
                    to_block = latest_block
                    logger.info(f"Scanning for 'BridgeTransferInitiated' events from block {from_block} to {to_block}")

                    # Create an event filter
                    event_filter = self.source_bridge_contract.events.BridgeTransferInitiated.create_filter(
                        fromBlock=from_block,
                        toBlock=to_block
                    )
                    events = event_filter.get_all_entries()

                    if events:
                        logger.info(f"Found {len(events)} new events.")
                        for event in events:
                            self.event_handler.process_event(event)
                    else:
                        logger.info("No new events found in this range.")

                    self.last_processed_block = to_block

            except requests.exceptions.ConnectionError as e:
                logger.error(f"RPC connection error: {e}. Retrying in {self.config.poll_interval_seconds}s...")
            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            
            time.sleep(self.config.poll_interval_seconds)

def load_config_from_env() -> BridgeConfig:
    """
    Loads configuration from environment variables.
    This is a best practice to avoid hardcoding sensitive data.
    """
    load_dotenv()
    
    required_vars = [
        'SOURCE_CHAIN_RPC', 'DESTINATION_CHAIN_RPC', 
        'SOURCE_BRIDGE_ADDRESS', 'DESTINATION_BRIDGE_ADDRESS',
        'LISTENER_PRIVATE_KEY'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")

    return BridgeConfig(
        source_chain_rpc=os.getenv('SOURCE_CHAIN_RPC'),
        destination_chain_rpc=os.getenv('DESTINATION_CHAIN_RPC'),
        source_bridge_address=os.getenv('SOURCE_BRIDGE_ADDRESS'),
        destination_bridge_address=os.getenv('DESTINATION_BRIDGE_ADDRESS'),
        listener_private_key=os.getenv('LISTENER_PRIVATE_KEY'),
        start_block=int(os.getenv('START_BLOCK', 0)),
        poll_interval_seconds=int(os.getenv('POLL_INTERVAL_SECONDS', 15))
    )

if __name__ == "__main__":
    """
    Entry point for the script.
    """
    try:
        # Load configuration from a .env file for security and flexibility
        config = load_config_from_env()
        
        # Initialize and run the listener
        listener = BridgeEventListener(config)
        listener.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.critical(f"A critical error occurred during initialization: {e}", exc_info=True)
