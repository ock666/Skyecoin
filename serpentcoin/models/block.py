import hashlib
import json
import time
import logging
from typing import Optional

from serpentcoin.crypto import sign_data, verify_signature, load_private_key, load_public_key_from_der, public_key_hex, public_key_to_address
from serpentcoin.models.transaction import Transaction

logger = logging.getLogger(__name__)


class Block:
    def __init__(
        self,
        block_index: int,
        previous_hash: str,
        transactions: list[Transaction],
        difficulty: int = 4,
        miner_private_key_pem: str = "",
    ):
        self.block_index = block_index
        self.previous_hash = previous_hash
        self.timestamp = time.time()
        self.transactions = transactions
        self.nonce = 0
        self.difficulty = difficulty
        self.miner_address = ""
        self.miner_public_key = ""
        self.miner_signature = ""
        self.block_hash = ""
        self._miner_private_key_pem = miner_private_key_pem

    def header_hash(self) -> str:
        data = {
            "block_index": self.block_index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "merkle_root": self.merkle_root(),
        }
        payload = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def merkle_root(self) -> str:
        if not self.transactions:
            return hashlib.sha256(b"").hexdigest()
        hashes = [hashlib.sha256(json.dumps(tx.to_dict(), sort_keys=True).encode()).hexdigest() for tx in self.transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def compute_hash(self) -> str:
        data = {
            "block_index": self.block_index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "merkle_root": self.merkle_root(),
            "miner_address": self.miner_address,
            "miner_public_key": self.miner_public_key,
        }
        payload = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def sign(self, private_key_pem: Optional[str] = None):
        pem = private_key_pem or self._miner_private_key_pem
        if not pem:
            raise ValueError("No private key provided for signing")
        private_key = load_private_key(pem)
        pub_key = private_key.public_key()
        self.miner_public_key = public_key_hex(pub_key)
        self.miner_address = public_key_to_address(pub_key)
        self.block_hash = self.compute_hash()
        self.miner_signature = sign_data(private_key, self.block_hash.encode())

    def verify(self) -> bool:
        if not self.miner_signature or not self.miner_public_key:
            return False
        expected_hash = self.compute_hash()
        if expected_hash != self.block_hash:
            return False
        try:
            pub_key = load_public_key_from_der(self.miner_public_key)
            expected_address = public_key_to_address(pub_key)
            if expected_address != self.miner_address:
                return False
            return verify_signature(pub_key, self.block_hash.encode(), self.miner_signature)
        except Exception:
            return False

    def to_dict(self) -> dict:
        return {
            "block_index": self.block_index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "merkle_root": self.merkle_root(),
            "miner_address": self.miner_address,
            "miner_public_key": self.miner_public_key,
            "miner_signature": self.miner_signature,
            "block_hash": self.block_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        txs = [Transaction.from_dict(tx) for tx in data.get("transactions", [])]
        block = cls(
            block_index=data["block_index"],
            previous_hash=data["previous_hash"],
            transactions=txs,
            difficulty=data.get("difficulty", 4),
        )
        block.timestamp = data["timestamp"]
        block.nonce = data["nonce"]
        block.miner_address = data.get("miner_address", "")
        block.miner_public_key = data.get("miner_public_key", "")
        block.miner_signature = data.get("miner_signature", "")
        block.block_hash = data.get("block_hash", "")
        return block


def create_block(
    block_index: int,
    previous_hash: str,
    transactions: list[Transaction],
    difficulty: int,
    miner_private_key_pem: str,
) -> Block:
    return Block(
        block_index=block_index,
        previous_hash=previous_hash,
        transactions=transactions,
        difficulty=difficulty,
        miner_private_key_pem=miner_private_key_pem,
    )
