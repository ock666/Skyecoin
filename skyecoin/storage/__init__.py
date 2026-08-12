import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS blocks (
    block_index INTEGER PRIMARY KEY,
    block_hash TEXT UNIQUE NOT NULL,
    previous_hash TEXT NOT NULL,
    timestamp REAL NOT NULL,
    nonce INTEGER NOT NULL,
    difficulty INTEGER NOT NULL DEFAULT 4,
    miner_address TEXT NOT NULL,
    miner_signature TEXT NOT NULL,
    miner_public_key TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT UNIQUE NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    amount REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL,
    signature TEXT,
    public_key TEXT,
    block_index INTEGER REFERENCES blocks(block_index),
    is_coinbase INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (block_index) REFERENCES blocks(block_index)
);

CREATE TABLE IF NOT EXISTS utxos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT NOT NULL,
    output_index INTEGER NOT NULL DEFAULT 0,
    address TEXT NOT NULL,
    amount REAL NOT NULL,
    spent INTEGER NOT NULL DEFAULT 0,
    lock_until_block INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_utxos_address ON utxos(address, spent);
CREATE INDEX IF NOT EXISTS idx_utxos_txhash ON utxos(tx_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_block ON transactions(block_index);
CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender);
CREATE INDEX IF NOT EXISTS idx_transactions_recipient ON transactions(recipient);

CREATE TABLE IF NOT EXISTS peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    last_seen REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    private_key TEXT NOT NULL,
    public_key TEXT NOT NULL,
    address TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, db_path: str = "data/skyecoin.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        try:
            self.conn.execute(
                "ALTER TABLE utxos ADD COLUMN lock_until_block INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def execute(self, sql: str, params=()):
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params):
        return self.conn.executemany(sql, params)

    def fetchone(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def has_users(self) -> bool:
        row = self.fetchone("SELECT COUNT(*) as c FROM users")
        return row["c"] > 0 if row else False

    def get_password_hash(self) -> Optional[str]:
        row = self.fetchone("SELECT password_hash FROM users WHERE id = 1")
        return row["password_hash"] if row else None

    def set_password(self, password_hash: str):
        import time
        self.execute(
            "INSERT OR REPLACE INTO users (id, password_hash, created_at) VALUES (1, ?, ?)",
            (password_hash, time.time()),
        )
        self.commit()

    def get_block_count(self) -> int:
        row = self.fetchone("SELECT COUNT(*) as c FROM blocks")
        return row["c"] if row else 0

    def get_block(self, block_index: int) -> Optional[dict]:
        row = self.fetchone("SELECT * FROM blocks WHERE block_index = ?", (block_index,))
        if not row:
            return None
        block = dict(row)
        txs = self.fetchall(
            "SELECT * FROM transactions WHERE block_index = ? ORDER BY id",
            (block_index,),
        )
        block["transactions"] = [dict(tx) for tx in txs]
        return block

    def get_block_by_hash(self, block_hash: str) -> Optional[dict]:
        row = self.fetchone("SELECT * FROM blocks WHERE block_hash = ?", (block_hash,))
        if not row:
            return None
        block = dict(row)
        txs = self.fetchall(
            "SELECT * FROM transactions WHERE block_index = ? ORDER BY id",
            (block["block_index"],),
        )
        block["transactions"] = [dict(tx) for tx in txs]
        return block

    def get_last_block(self) -> Optional[dict]:
        row = self.fetchone("SELECT MAX(block_index) as idx FROM blocks")
        if not row or row["idx"] is None:
            return None
        return self.get_block(row["idx"])

    def insert_block(self, block: dict) -> bool:
        try:
            self.execute(
                """INSERT OR IGNORE INTO blocks
                   (block_index, block_hash, previous_hash, timestamp, nonce,
                    difficulty, miner_address, miner_signature, miner_public_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    block["block_index"],
                    block["block_hash"],
                    block["previous_hash"],
                    block["timestamp"],
                    block["nonce"],
                    block["difficulty"],
                    block["miner_address"],
                    block["miner_signature"],
                    block["miner_public_key"],
                ),
            )
            for i, tx in enumerate(block["transactions"]):
                self.execute(
                    """INSERT OR IGNORE INTO transactions
                       (tx_hash, sender, recipient, amount, fee, timestamp,
                        signature, public_key, block_index, is_coinbase)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tx["tx_hash"],
                        tx["sender"],
                        tx["recipient"],
                        tx["amount"],
                        tx.get("fee", 0),
                        tx["timestamp"],
                        tx.get("signature", ""),
                        tx.get("public_key", ""),
                        block["block_index"],
                        1 if tx["sender"] == "COINBASE" else 0,
                    ),
                )
            self.commit()
            return True
        except sqlite3.IntegrityError:
            logger.warning("Block %d already exists, skipping", block["block_index"])
            return False

    def delete_blocks_from(self, block_index: int):
        self.execute(
            "DELETE FROM transactions WHERE block_index >= ?", (block_index,)
        )
        self.execute("DELETE FROM blocks WHERE block_index >= ?", (block_index,))
        self.commit()

    def add_utxo(self, tx_hash: str, output_index: int, address: str, amount: float):
        self.execute(
            "INSERT INTO utxos (tx_hash, output_index, address, amount) VALUES (?, ?, ?, ?)",
            (tx_hash, output_index, address, amount),
        )
        self.commit()

    def add_utxo_with_lock(self, tx_hash: str, output_index: int, address: str, amount: float, lock_until_block: int = 0):
        self.execute(
            "INSERT INTO utxos (tx_hash, output_index, address, amount, lock_until_block) VALUES (?, ?, ?, ?, ?)",
            (tx_hash, output_index, address, amount, lock_until_block),
        )
        self.commit()

    def spend_utxos(self, tx_hash: str):
        self.execute("UPDATE utxos SET spent = 1 WHERE tx_hash = ?", (tx_hash,))
        self.commit()

    def get_utxos_for_address(self, address: str) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM utxos WHERE address = ? AND spent = 0 ORDER BY amount DESC",
            (address,),
        )
        return [dict(r) for r in rows]

    def get_balance(self, address: str) -> float:
        row = self.fetchone(
            "SELECT COALESCE(SUM(amount), 0) as bal FROM utxos WHERE address = ? AND spent = 0",
            (address,),
        )
        return row["bal"] if row else 0.0

    def get_all_utxos(self) -> list[dict]:
        rows = self.fetchall("SELECT * FROM utxos WHERE spent = 0 ORDER BY amount DESC")
        return [dict(r) for r in rows]

    def get_pending_utxos(self) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM utxos WHERE spent = 0 ORDER BY amount DESC"
        )
        return [dict(r) for r in rows]

    def rebuild_utxos(self):
        self.execute("DELETE FROM utxos")
        blocks = self.fetchall("SELECT * FROM blocks ORDER BY block_index")
        for block in blocks:
            b = dict(block)
            txs = self.fetchall(
                "SELECT * FROM transactions WHERE block_index = ? ORDER BY id",
                (b["block_index"],),
            )
            for tx in txs:
                tx = dict(tx)
                if tx["sender"] != "COINBASE":
                    self.spend_utxos(tx["tx_hash"])
                self.add_utxo(tx["tx_hash"], 0, tx["recipient"], tx["amount"])
        self.commit()

    def add_peer(self, address: str):
        import time
        self.execute(
            "INSERT OR REPLACE INTO peers (address, last_seen) VALUES (?, ?)",
            (address, time.time()),
        )
        self.commit()

    def remove_peer(self, address: str):
        self.execute("DELETE FROM peers WHERE address = ?", (address,))
        self.commit()

    def get_peers(self) -> list[str]:
        rows = self.fetchall("SELECT address FROM peers")
        return [r["address"] for r in rows]

    def get_wallet(self) -> Optional[dict]:
        row = self.fetchone("SELECT * FROM wallet WHERE id = 1")
        return dict(row) if row else None

    def set_wallet(self, private_key: str, public_key: str, address: str):
        self.execute(
            "INSERT OR REPLACE INTO wallet (id, private_key, public_key, address) VALUES (1, ?, ?, ?)",
            (private_key, public_key, address),
        )
        self.commit()

    def set_config(self, key: str, value: str):
        self.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
        self.commit()

    def get_config(self, key: str, default=None) -> Optional[str]:
        row = self.fetchone("SELECT value FROM config WHERE key = ?", (key,))
        return row["value"] if row else default

    def get_all_blocks(self, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.fetchall(
            "SELECT * FROM blocks ORDER BY block_index DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in rows]

    def get_pending_transactions_count(self) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) as c FROM transactions WHERE block_index IS NULL"
        )
        return row["c"] if row else 0
