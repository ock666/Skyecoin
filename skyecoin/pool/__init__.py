import json
import hashlib
import time
import threading
import logging
from collections import deque
from typing import Optional

from skyecoin.models.block import Block, create_block
from skyecoin.models.transaction import Transaction, create_coinbase_transaction

logger = logging.getLogger(__name__)


class PoolManager:
    def __init__(self, db, chain, mempool, wallet, config, nodes):
        self.db = db
        self.chain = chain
        self.mempool = mempool
        self.wallet = wallet
        self.config = config
        self.nodes = nodes
        self._lock = threading.Lock()
        self._running = True

        self.workers: dict[str, dict] = {}
        self.shares: deque[dict] = deque(maxlen=1000)
        self._current_job: Optional[dict] = None
        self._current_nonce_start = 0
        self._nonce_range_size = 5_000_000

        self.stats = {
            "total_shares": 0,
            "blocks_found": 0,
            "active_workers": 0,
            "pool_hashrate": 0.0,
        }

    def subscribe_worker(self, worker_address: str, worker_name: str = "") -> dict:
        with self._lock:
            is_new = worker_address not in self.workers
            self.workers[worker_address] = {
                "name": worker_name or worker_address[:10],
                "shares": 0,
                "last_share_time": time.time(),
                "hashrate": 0.0,
                "connected_since": self.workers[worker_address]["connected_since"] if not is_new else time.time(),
            }
            if is_new:
                logger.info("Pool worker subscribed: %s (%s)", worker_name or worker_address[:10], worker_address)
        return {
            "pool_difficulty": self.config.pool_difficulty,
            "message": "Subscribed to Skyecoin Pool",
        }

    def get_work(self) -> dict:
        with self._lock:
            last = self.chain.get_last_block()
            if not last:
                return {"error": "No blocks yet"}

            block_index = last["block_index"] + 1
            pending = self.mempool.get_transactions(max_count=50)
            total_fees = sum(tx.fee for tx in pending)

            coinbase = create_coinbase_transaction(
                miner_address=self.wallet["address"],
                block_index=block_index,
                coinbase_reward=self.chain.get_current_reward(),
                total_fees=total_fees,
            )
            txs = [coinbase] + pending

            from skyecoin.mining.difficulty import calculate_difficulty
            chain_diff = calculate_difficulty(self.db, self.config)

            start_nonce = self._current_nonce_start
            end_nonce = start_nonce + self._nonce_range_size
            self._current_nonce_start = end_nonce

            block = create_block(
                block_index=block_index,
                previous_hash=last["block_hash"],
                transactions=txs,
                difficulty=chain_diff,
                miner_private_key_pem=self.wallet["private_key"],
            )

            self._current_job = {
                "block": block,
                "start_nonce": start_nonce,
                "end_nonce": end_nonce,
                "chain_difficulty": chain_diff,
                "pool_difficulty": self.config.pool_difficulty,
            }

            return {
                "job_id": f"{block_index}:{start_nonce}",
                "block_index": block_index,
                "previous_hash": last["block_hash"],
                "target": block.header_hash(),
                "difficulty": chain_diff,
                "pool_difficulty": self.config.pool_difficulty,
                "nonce_start": start_nonce,
                "nonce_end": end_nonce,
                "tx_count": len(txs),
            }

    def submit_share(self, worker_address: str, nonce: int, timestamp: float) -> dict:
        with self._lock:
            job = self._current_job
            if not job:
                return {"accepted": False, "reason": "No active job"}

            block = job["block"]
            start = job["start_nonce"]
            end = job["end_nonce"]

            if nonce < start or nonce >= end:
                return {"accepted": False, "reason": "Nonce out of assigned range"}

            block.nonce = nonce
            block.timestamp = timestamp
            header_hash = block.header_hash()
            hash_int = int.from_bytes(hashlib.sha256(header_hash.encode()).digest(), "big")

            pool_target = 2 ** (256 - self.config.pool_difficulty)
            chain_target = 2 ** (256 - job["chain_difficulty"])

            if hash_int >= pool_target:
                return {"accepted": False, "reason": "Share below pool difficulty"}

            self.shares.append({
                "worker": worker_address,
                "nonce": nonce,
                "timestamp": timestamp,
                "block_index": block.block_index,
            })
            self.stats["total_shares"] += 1

            if worker_address in self.workers:
                self.workers[worker_address]["shares"] += 1
                self.workers[worker_address]["last_share_time"] = time.time()

            self.stats["active_workers"] = sum(
                1 for w in self.workers.values() if time.time() - w["last_share_time"] < 120
            )

            if hash_int < chain_target:
                block.sign(self.wallet["private_key"])
                accepted, msg = self.chain.accept_block(block)
                if accepted:
                    self.stats["blocks_found"] += 1
                    self.nodes.broadcast_block(block)
                    return {
                        "accepted": True,
                        "block_found": True,
                        "block_hash": block.block_hash,
                        "block_index": block.block_index,
                        "message": f"Block {block.block_index} mined by pool!",
                    }
                else:
                    return {"accepted": True, "block_found": False, "reason": f"Block rejected: {msg}"}

            return {"accepted": True, "block_found": False, "message": "Share accepted"}

    def get_pool_stats(self) -> dict:
        with self._lock:
            self.stats["active_workers"] = sum(
                1 for w in self.workers.values() if time.time() - w["last_share_time"] < 120
            )
            return {
                **self.stats,
                "workers": len(self.workers),
                "pending_payout": self._calculate_pending_payout(),
                "pool_fee_percent": self.config.pool_fee_percent,
                "pool_difficulty": self.config.pool_difficulty,
                "workers_detail": [
                    {
                        "address": addr[:12] + "...",
                        "name": w["name"],
                        "shares": w["shares"],
                        "hashrate": w["hashrate"],
                    }
                    for addr, w in sorted(self.workers.items(), key=lambda x: x[1]["shares"], reverse=True)[:20]
                ],
            }

    def _calculate_pending_payout(self) -> float:
        reward = self.chain.get_current_reward()
        pool_fee = reward * (self.config.pool_fee_percent / 100)
        return reward - pool_fee
