import time
import logging
from skyecoin.models.transaction import Transaction, create_coinbase_transaction

logger = logging.getLogger(__name__)


class Mempool:
    def __init__(self):
        self._transactions: dict[str, Transaction] = {}
        self._expiry = 3600

    def add_transaction(self, tx: Transaction) -> bool:
        if tx.tx_hash in self._transactions:
            return False
        if not tx.verify():
            return False
        self._transactions[tx.tx_hash] = tx
        return True

    def remove_transaction(self, tx_hash: str):
        self._transactions.pop(tx_hash, None)

    def get_transactions(self, max_count: int = 100) -> list[Transaction]:
        txs = sorted(self._transactions.values(), key=lambda t: t.fee / max(t.amount, 1), reverse=True)
        return txs[:max_count]

    def get_all(self) -> list[Transaction]:
        return list(self._transactions.values())

    def size(self) -> int:
        return len(self._transactions)

    def clear(self):
        self._transactions.clear()

    def remove_transactions(self, tx_hashes: set[str]):
        for h in tx_hashes:
            self._transactions.pop(h, None)

    def purge_expired(self):
        now = time.time()
        expired = [h for h, tx in self._transactions.items() if now - tx.timestamp > self._expiry]
        for h in expired:
            self._transactions.pop(h, None)
        if expired:
            logger.info("Purged %d expired transactions from mempool", len(expired))

    def total_fees(self, transactions: list[Transaction]) -> float:
        return sum(tx.fee for tx in transactions if tx.sender != "COINBASE")

    def get_by_hash(self, tx_hash: str):
        return self._transactions.get(tx_hash)

    def has(self, tx_hash: str) -> bool:
        return tx_hash in self._transactions
