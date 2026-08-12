import time
import sys
import signal
import logging
import urllib.request
import json

from serpentcoin.models.block import Block, create_block
from serpentcoin.models.transaction import Transaction, create_coinbase_transaction
from serpentcoin.mining import mine_block

logger = logging.getLogger(__name__)


MODE_STANDALONE = "standalone"
MODE_NODE = "node"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def post_json(url: str, data: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def mine_standalone(miner_private_key_pem: str, difficulty: int = 4):
    from serpentcoin.crypto import load_private_key, public_key_to_address, public_key_hex
    from serpentcoin.storage import Database
    from serpentcoin.config import Config
    from serpentcoin.chain import ChainManager
    from serpentcoin.mempool import Mempool

    config = Config()
    config.difficulty = difficulty
    db = Database(config.db_path)
    mempool = Mempool()
    chain = ChainManager(db, mempool, config)

    priv_key = load_private_key(miner_private_key_pem)
    miner_address = public_key_to_address(priv_key.public_key())
    miner_pub_hex = public_key_hex(priv_key.public_key())

    chain.initialize(miner_address, miner_pub_hex)

    logger.info("Standalone mining started. Difficulty: %d", difficulty)
    logger.info("Miner address: %s", miner_address)

    mining = True

    def stop_handler(sig, frame):
        nonlocal mining
        mining = False
        logger.info("Stopping miner...")

    signal.signal(signal.SIGINT, stop_handler)

    while mining:
        last = chain.get_last_block()
        if not last:
            time.sleep(1)
            continue

        mempool.purge_expired()
        pending = mempool.get_transactions(max_count=50)
        total_fees = sum(tx.fee for tx in pending)

        coinbase = create_coinbase_transaction(
            miner_address=miner_address,
            block_index=last["block_index"] + 1,
            coinbase_reward=config.coinbase_reward,
            total_fees=total_fees,
        )

        txs = [coinbase] + pending

        from serpentcoin.mining.difficulty import calculate_difficulty
        current_difficulty = calculate_difficulty(db, config)

        block = create_block(
            block_index=last["block_index"] + 1,
            previous_hash=last["block_hash"],
            transactions=txs,
            difficulty=current_difficulty,
            miner_private_key_pem=miner_private_key_pem,
        )

        logger.info("Mining block %d with %d transactions", block.block_index, len(txs))
        if mine_block(block):
            accepted, msg = chain.accept_block(block)
            if accepted:
                logger.info("Block %d accepted: %s", block.block_index, block.block_hash[:16])
            else:
                logger.error("Block rejected: %s", msg)
        else:
            logger.info("Mining interrupted")


def mine_via_node(node_url: str, miner_private_key_pem: str):
    from serpentcoin.crypto import load_private_key, public_key_to_address, public_key_hex

    priv_key = load_private_key(miner_private_key_pem)
    miner_address = public_key_to_address(priv_key.public_key())

    logger.info("Mining via node: %s", node_url)
    logger.info("Miner address: %s", miner_address)

    mining = True

    def stop_handler(sig, frame):
        nonlocal mining
        mining = False

    signal.signal(signal.SIGINT, stop_handler)

    while mining:
        try:
            stats = fetch_json(f"{node_url}/api/stats")
            mempool_data = fetch_json(f"{node_url}/api/mempool")
            chain_data = fetch_json(f"{node_url}/api/chain?limit=1")

            if not chain_data:
                time.sleep(2)
                continue

            last_block = chain_data[0]
            block_index = last_block["block_index"] + 1

            pending_txs = [Transaction.from_dict(tx) for tx in mempool_data]
            total_fees = sum(tx.fee for tx in pending_txs)

            coinbase = create_coinbase_transaction(
                miner_address=miner_address,
                block_index=block_index,
                coinbase_reward=50.0,
                total_fees=total_fees,
            )

            txs = [coinbase] + pending_txs
            difficulty = stats["difficulty"]

            block = create_block(
                block_index=block_index,
                previous_hash=last_block["block_hash"],
                transactions=txs,
                difficulty=difficulty,
                miner_private_key_pem=miner_private_key_pem,
            )

            logger.info("Mining block %d (diff: %d, txs: %d)", block_index, difficulty, len(txs))
            if mine_block(block):
                try:
                    result = post_json(f"{node_url}/api/block", block.to_dict())
                    logger.info("Block accepted: %s", result.get("message", ""))
                except Exception as e:
                    logger.error("Failed to submit block: %s", e)
        except Exception as e:
            logger.error("Error in mining loop: %s", e)
            time.sleep(5)


def run_miner():
    import argparse

    parser = argparse.ArgumentParser(description="Serpentcoin Miner")
    parser.add_argument("--standalone", action="store_true", help="Run standalone (with local node)")
    parser.add_argument("--node", type=str, default="http://127.0.0.1:5000", help="Node URL")
    parser.add_argument("--difficulty", type=int, default=4, help="Mining difficulty (standalone)")
    parser.add_argument("--private-key", type=str, help="Private key PEM file or string")

    args = parser.parse_args()

    if args.private_key:
        if args.private_key.startswith("-----"):
            miner_private_key = args.private_key
        else:
            with open(args.private_key) as f:
                miner_private_key = f.read()
    elif not args.standalone:
        try:
            wallet = fetch_json(f"{args.node}/api/wallet")
            miner_private_key = wallet["private_key"]
            logger.info("Using node wallet: %s", wallet["address"])
        except Exception:
            from serpentcoin.crypto import generate_keypair
            priv, pub, addr = generate_keypair()
            miner_private_key = priv
            logger.info("Generated new miner wallet (node unreachable): %s", addr)
    else:
        from serpentcoin.crypto import generate_keypair
        priv, pub, addr = generate_keypair()
        miner_private_key = priv
        logger.info("Generated new miner wallet: %s", addr)

    if args.standalone:
        mine_standalone(miner_private_key, args.difficulty)
    else:
        mine_via_node(args.node, miner_private_key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    run_miner()
