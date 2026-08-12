import hashlib
import json
import time
import logging
from typing import Optional

from skyecoin.crypto import (
    sign_data,
    verify_signature,
    load_private_key,
    load_public_key_from_der,
    public_key_to_address,
    public_key_hex,
)

logger = logging.getLogger(__name__)


class Transaction:
    def __init__(
        self,
        sender: str,
        recipient: str,
        amount: float,
        fee: float = 0.0,
        timestamp: Optional[float] = None,
        public_key_hex_str: str = "",
        private_key_pem: str = "",
    ):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.timestamp = timestamp or time.time()
        self.public_key_hex = public_key_hex_str
        self.signature = ""
        self._private_key_pem = private_key_pem
        self.tx_hash = ""

    def compute_hash(self) -> str:
        data = {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "timestamp": self.timestamp,
            "public_key": self.public_key_hex,
        }
        payload = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def sign(self, private_key_pem: Optional[str] = None):
        pem = private_key_pem or self._private_key_pem
        if not pem:
            raise ValueError("No private key provided for signing")
        private_key = load_private_key(pem)
        pub_key = private_key.public_key()
        self.public_key_hex = public_key_hex(pub_key)
        self.sender = public_key_to_address(pub_key)
        self.tx_hash = self.compute_hash()
        self.signature = sign_data(private_key, self.tx_hash.encode())

    def verify(self) -> bool:
        if self.sender == "COINBASE":
            return True
        if not self.signature or not self.public_key_hex:
            return False
        expected_hash = self.compute_hash()
        if expected_hash != self.tx_hash:
            return False
        try:
            pub_key = load_public_key_from_der(self.public_key_hex)
            expected_address = public_key_to_address(pub_key)
            if expected_address != self.sender:
                return False
            return verify_signature(pub_key, self.tx_hash.encode(), self.signature)
        except Exception:
            return False

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "timestamp": self.timestamp,
            "public_key": self.public_key_hex,
            "signature": self.signature,
            "tx_hash": self.tx_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        tx = cls(
            sender=data["sender"],
            recipient=data["recipient"],
            amount=data["amount"],
            fee=data.get("fee", 0.0),
            timestamp=data["timestamp"],
        )
        tx.public_key_hex = data.get("public_key", "")
        tx.signature = data.get("signature", "")
        tx.tx_hash = data.get("tx_hash", "")
        return tx


def create_coinbase_transaction(
    miner_address: str, block_index: int, coinbase_reward: float, total_fees: float
) -> Transaction:
    tx = Transaction(
        sender="COINBASE",
        recipient=miner_address,
        amount=coinbase_reward + total_fees,
        fee=0.0,
    )
    tx.tx_hash = tx.compute_hash()
    return tx


def create_transaction(
    sender_private_key_pem: str,
    recipient: str,
    amount: float,
    fee: float = 0.0,
) -> Transaction:
    tx = Transaction(
        sender="",
        recipient=recipient,
        amount=amount,
        fee=fee,
    )
    tx.sign(private_key_pem=sender_private_key_pem)
    return tx
