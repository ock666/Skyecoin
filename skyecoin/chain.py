import hashlib
import json
import time
import logging
from typing import Optional

from skyecoin.config import Config
from skyecoin.storage import Database
from skyecoin.models.block import Block, create_block
from skyecoin.models.transaction import Transaction, create_coinbase_transaction
from skyecoin.validation import validate_block, validate_chain
from skyecoin.mempool import Mempool
from skyecoin.mining.difficulty import calculate_difficulty

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

    def get_current_reward(self) -> float:
        height = self.db.get_block_count()
        if height == 0:
            return self.config.coinbase_reward
        halvings = (height - 1) // self.config.halving_interval
        reward = self.config.coinbase_reward / (2 ** halvings)
        return max(reward, 0.000001)

    def check_lottery(self, block_hash: str, nonce: int) -> tuple[bool, str]:
        suffix = block_hash[-self.config.min_lottery_zeros:]
        prefix = block_hash[:self.config.min_lottery_zeros]
        if suffix == "0" * self.config.min_lottery_zeros:
            return True, f"Golden suffix: {self.config.lottery_bonus} SC bonus!"
        if prefix == "0" * self.config.min_lottery_zeros:
            return True, f"Golden prefix: {self.config.lottery_bonus} SC bonus!"
        if nonce % 777777 == 0:
            return True, f"Lucky nonce: {self.config.lottery_bonus} SC bonus!"
        return False, ""

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

        expected_reward = self.get_current_reward()
        won, lottery_msg = self.check_lottery(block.block_hash, block.nonce)
        if won:
            expected_reward += self.config.lottery_bonus

        total_fees = sum(tx.fee for tx in block.transactions if tx.sender != "COINBASE")
        coinbase = next((tx for tx in block.transactions if tx.sender == "COINBASE"), None)
        if coinbase:
            if abs(coinbase.amount - (expected_reward + total_fees)) > 0.0001:
                return False, f"Invalid coinbase: {coinbase.amount} != {expected_reward + total_fees}"

        if expected_reward < self.config.coinbase_reward:
            logger.info("Halving at block %d: reward now %.6f SC", block.block_index, expected_reward)

        block_dict = block.to_dict()
        if not self.db.insert_block(block_dict):
            return False, "Block already exists"

        self._update_utxos_for_block(block)

        included_hashes = {tx.tx_hash for tx in block.transactions if tx.sender != "COINBASE"}
        self.mempool.remove_transactions(included_hashes)
        self.mempool.purge_expired()

        status = "Accepted"
        if won:
            status = f"Lottery won! {lottery_msg}"
        logger.info("%s block %d: %s (%d txs)", status, block.block_index, block.block_hash[:12], len(block.transactions))
        return True, f"Block {status.lower()}"

    def _update_utxos_for_block(self, block: Block):
        for tx in block.transactions:
            if tx.sender == "COINBASE":
                self.db.add_utxo_with_lock(tx.tx_hash, 0, tx.recipient, tx.amount, 0)
            else:
                needed = tx.amount + tx.fee
                utxos = [
                    u for u in self.db.get_utxos_for_address(tx.sender)
                    if u.get("lock_until_block", 0) <= block.block_index
                ]
                spent = 0.0
                for utxo in utxos:
                    if spent >= needed:
                        break
                    self.db.execute("UPDATE utxos SET spent = 1 WHERE id = ?", (utxo["id"],))
                    spent += utxo["amount"]
                lock_height = getattr(tx, "lock_until_block", 0)
                self.db.add_utxo_with_lock(tx.tx_hash, 0, tx.recipient, tx.amount, lock_height)
                if spent > needed:
                    change = spent - needed
                    change_tx_hash = tx.tx_hash + "_change"
                    self.db.add_utxo_with_lock(change_tx_hash, 0, tx.sender, change, 0)
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
            "difficulty": calculate_difficulty(self.db, self.config),
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

    def get_total_burned(self) -> float:
        row = self.db.fetchone(
            "SELECT COALESCE(SUM(amount), 0) as bal FROM utxos WHERE address LIKE 'BURN%' AND spent = 0"
        )
        return row["bal"] if row else 0.0

    def get_address_history(self, address: str, limit: int = 50) -> list[dict]:
        rows = self.db.fetchall(
            """SELECT * FROM transactions
               WHERE (sender = ? OR recipient = ?) AND block_index IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (address, address, limit),
        )
        return [dict(r) for r in rows]
