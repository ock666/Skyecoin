import hashlib
import json
import time
import logging
from typing import Optional

from serpentcoin.config import Config
from serpentcoin.storage import Database
from serpentcoin.models.block import Block, create_block
from serpentcoin.models.transaction import Transaction, create_coinbase_transaction
from serpentcoin.validation import validate_block, validate_chain
from serpentcoin.mempool import Mempool
from serpentcoin.mining.difficulty import calculate_difficulty

logger = logging.getLogger(__name__)


def create_genesis_block(miner_address: str, miner_public_key: str, config: Config) -> Block:
    coinbase = create_coinbase_transaction(
        miner_address=miner_address,
        block_index=0,
        coinbase_reward=config.coinbase_reward,
        total_fees=0.0,
    )
    block = Block(
        block_index=0,
        previous_hash="0" * 64,
        transactions=[coinbase],
        difficulty=config.difficulty,
    )
    block.miner_address = miner_address
    block.miner_public_key = miner_public_key
    block.miner_signature = "GENESIS"
    block.block_hash = block.compute_hash()
    block.nonce = 0
    block.timestamp = time.time()
    return block


class ChainManager:
    def __init__(self, db: Database, mempool: Mempool, config: Config):
        self.db = db
        self.mempool = mempool
        self.config = config

    def initialize(self, miner_address: str, miner_public_key: str):
        if self.db.get_block_count() == 0:
            genesis = create_genesis_block(miner_address, miner_public_key, self.config)
            self.db.insert_block(genesis.to_dict())
            self._update_utxos_for_block(genesis)
            logger.info("Genesis block created: %s", genesis.block_hash)

    def get_last_block(self) -> Optional[dict]:
        return self.db.get_last_block()

    def get_block(self, block_index: int) -> Optional[dict]:
        return self.db.get_block(block_index)

    def get_chain(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return self.db.get_all_blocks(limit=limit, offset=offset)

    def get_balance(self, address: str) -> float:
        return self.db.get_balance(address)

    def get_utxos(self, address: str) -> list[dict]:
        return self.db.get_utxos_for_address(address)

    def accept_block(self, block: Block) -> tuple[bool, str]:
        last_block = self.db.get_last_block()
        expected_index = (last_block["block_index"] + 1) if last_block else 0
        if block.block_index != expected_index:
            return False, f"Invalid block index: {block.block_index} (expected {expected_index})"

        if last_block and block.previous_hash != last_block["block_hash"]:
            return False, "Invalid previous hash"

        if not validate_block(block):
            return False, "Block validation failed"

        block_dict = block.to_dict()
        if not self.db.insert_block(block_dict):
            return False, "Block already exists"

        self._update_utxos_for_block(block)

        included_hashes = {tx.tx_hash for tx in block.transactions if tx.sender != "COINBASE"}
        self.mempool.remove_transactions(included_hashes)
        self.mempool.purge_expired()

        logger.info("Accepted block %d: %s (%d txs)", block.block_index, block.block_hash[:12], len(block.transactions))
        return True, "Block accepted"

    def _update_utxos_for_block(self, block: Block):
        for tx in block.transactions:
            if tx.sender == "COINBASE":
                self.db.add_utxo(tx.tx_hash, 0, tx.recipient, tx.amount)
            else:
                needed = tx.amount + tx.fee
                utxos = self.db.get_utxos_for_address(tx.sender)
                spent = 0.0
                for utxo in utxos:
                    if spent >= needed:
                        break
                    self.db.execute("UPDATE utxos SET spent = 1 WHERE id = ?", (utxo["id"],))
                    spent += utxo["amount"]
                self.db.add_utxo(tx.tx_hash, 0, tx.recipient, tx.amount)
                if spent > needed:
                    change = spent - needed
                    change_tx_hash = tx.tx_hash + "_change"
                    self.db.add_utxo(change_tx_hash, 0, tx.sender, change)
        self.db.commit()

    def rebuild_utxo_set(self):
        logger.info("Rebuilding UTXO set...")
        self.db.execute("DELETE FROM utxos")
        blocks = self.db.fetchall("SELECT block_index FROM blocks ORDER BY block_index")
        for row in blocks:
            block_data = self.db.get_block(row["block_index"])
            if block_data:
                block = Block.from_dict(block_data)
                self._update_utxos_for_block(block)
        self.db.commit()
        logger.info("UTXO set rebuilt")

    def get_chain_stats(self) -> dict:
        count = self.db.get_block_count()
        last = self.db.get_last_block()
        return {
            "height": count,
            "last_block_hash": last["block_hash"] if last else None,
            "last_block_time": last["timestamp"] if last else None,
            "difficulty": last["difficulty"] if last else self.config.difficulty,
            "mempool_size": self.mempool.size(),
            "total_transactions": self._count_transactions(),
        }

    def _count_transactions(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) as c FROM transactions WHERE block_index IS NOT NULL")
        return row["c"] if row else 0

    def get_recent_blocks(self, limit: int = 20) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM blocks ORDER BY block_index DESC LIMIT ?", (limit,))
        blocks = []
        for row in rows:
            b = dict(row)
            tx_count = self.db.fetchone(
                "SELECT COUNT(*) as c FROM transactions WHERE block_index = ?",
                (b["block_index"],),
            )["c"]
            b["tx_count"] = tx_count
            blocks.append(b)
        return blocks

    def get_address_history(self, address: str, limit: int = 50) -> list[dict]:
        rows = self.db.fetchall(
            """SELECT * FROM transactions
               WHERE (sender = ? OR recipient = ?) AND block_index IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (address, address, limit),
        )
        return [dict(r) for r in rows]
