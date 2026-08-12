import hashlib
import json
import random
import time
import logging
from skyecoin.models.block import Block

logger = logging.getLogger(__name__)


def mine_block(block: Block, stop_event=None) -> bool:
    target = 2 ** (256 - block.difficulty)
    logger.info(
        "Mining block %d with difficulty %d (target: %s...)",
        block.block_index,
        block.difficulty,
        hex(target)[:20],
    )

    attempts = 0
    start = time.time()

    while True:
        if stop_event and stop_event.is_set():
            return False

        block.nonce = random.randint(0, 2**63 - 1)
        block.timestamp = time.time()
        header_hash = block.header_hash()
        hash_int = int.from_bytes(
            hashlib.sha256(header_hash.encode()).digest(), "big"
        )
        attempts += 1

        if hash_int < target:
            elapsed = time.time() - start
            logger.info(
                "Block %d mined! Nonce: %d, Attempts: %d, Time: %.1fs (%.0f H/s)",
                block.block_index,
                block.nonce,
                attempts,
                elapsed,
                attempts / elapsed if elapsed > 0 else 0,
            )
            block.sign()
            return True

        if attempts % 100000 == 0:
            elapsed = time.time() - start
            rate = attempts / elapsed if elapsed > 0 else 0
            logger.debug(
                "Mining... %d attempts, %.0f H/s", attempts, rate
            )


def validate_proof(block: Block) -> bool:
    target = 2 ** (256 - block.difficulty)
    header_hash = block.header_hash()
    hash_int = int.from_bytes(
        hashlib.sha256(header_hash.encode()).digest(), "big"
    )
    return hash_int < target
