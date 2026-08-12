import hashlib
import logging
from skyecoin.models.block import Block
from skyecoin.models.transaction import Transaction
from skyecoin.storage import Database

logger = logging.getLogger(__name__)


def validate_block_structure(block: Block) -> bool:
    if block.block_index < 0:
        return False
    if not block.previous_hash or len(block.previous_hash) != 64:
        return False
    if not block.transactions:
        return False
    if block.difficulty < 1:
        return False
    if not block.miner_address:
        return False
    return True


def validate_proof_of_work(block: Block) -> bool:
    target = 2 ** (256 - block.difficulty)
    header_hash = block.header_hash()
    hash_int = int.from_bytes(hashlib.sha256(header_hash.encode()).digest(), "big")
    return hash_int < target


def validate_block_signature(block: Block) -> bool:
    if not block.miner_signature or not block.miner_public_key:
        return False
    return block.verify()


def validate_block(block: Block) -> bool:
    if not validate_block_structure(block):
        logger.warning("Block %d: invalid structure", block.block_index)
        return False
    if not validate_proof_of_work(block):
        logger.warning("Block %d: invalid proof of work", block.block_index)
        return False
    if not validate_block_signature(block):
        logger.warning("Block %d: invalid miner signature", block.block_index)
        return False
    for tx in block.transactions:
        if not tx.verify():
            logger.warning("Block %d: invalid transaction %s", block.block_index, tx.tx_hash)
            return False
    if block.transactions:
        coinbase_count = sum(1 for tx in block.transactions if tx.sender == "COINBASE")
        if coinbase_count != 1:
            logger.warning("Block %d: expected 1 coinbase, got %d", block.block_index, coinbase_count)
            return False
    return True


def validate_chain(db: Database) -> bool:
    blocks = db.fetchall("SELECT * FROM blocks ORDER BY block_index")
    if not blocks:
        return True
    prev_hash = None
    for row in blocks:
        block = db.get_block(row["block_index"])
        if not block:
            return False
        b = Block.from_dict(block)
        if prev_hash is not None and b.previous_hash != prev_hash:
            logger.warning("Chain broken at block %d", b.block_index)
            return False
        prev_hash = b.block_hash
    return True


def validate_transaction_for_mempool(tx: Transaction, db: Database) -> tuple[bool, str]:
    if tx.sender == "COINBASE":
        return False, "Coinbase transactions cannot be submitted to mempool"
    if not tx.verify():
        return False, "Invalid transaction signature"
    available = db.get_balance(tx.sender)
    needed = tx.amount + tx.fee
    if available < needed:
        return False, f"Insufficient balance: have {available}, need {needed}"
    return True, ""



def check_coinbase_reward(block: Block, expected_reward: float, total_fees: float) -> bool:
    coinbase = next((tx for tx in block.transactions if tx.sender == "COINBASE"), None)
    if not coinbase:
        return False
    expected = expected_reward + total_fees
    return abs(coinbase.amount - expected) < 0.0001
