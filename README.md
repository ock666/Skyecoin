# Skyecoin v2

An educational toy blockchain built to understand how blockchain technology works under the hood.

## What's New in v2

Complete rewrite with a clean architecture, proper engineering practices, and a web UI:

- **ECDSA (secp256k1)** cryptography replacing RSA-4096 - proper blockchain-style keys
- **UTXO model** with SQLite storage - fast balance lookups without chain scanning
- **FastAPI** REST API with automatic OpenAPI docs and Pydantic validation
- **Web UI** with live updates showing the chain in real-time
- **Proper testing** with pytest
- **Clean separation of concerns** - crypto, models, validation, storage, mining, networking

## Quick Start

```bash
# Install dependencies
pip install -e "."

# Start the node with web UI
python run.py

# Start the node with built-in mining
python run.py --miner --difficulty 4

# Run a separate miner
python -m skyecoin.cli.miner --standalone --difficulty 4
```

Open **http://localhost:5000** to see the web UI, or **http://localhost:5000/docs** for the API docs.

## Architecture

```
skyecoin/
├── crypto/        # ECDSA key generation, signing, address derivation
├── models/        # Block and Transaction data structures
├── validation/    # Block, transaction, and chain validation
├── storage/       # SQLite database layer (blocks, UTXOs, peers)
├── mining/        # Proof-of-work and difficulty adjustment
├── network/       # P2P node communication and consensus
├── web/           # HTML templates, CSS, JS (htmx-powered UI)
├── api/           # Pydantic schemas for request/response
├── cli/           # CLI miner process
├── chain.py       # Chain manager - orchestrates everything
├── mempool.py     # Pending transaction pool
├── config.py      # Configuration management
└── app.py         # FastAPI application with all routes
```

## Web UI Tabs

- **Dashboard** - Live chain stats and recent blocks
- **Blocks** - Block explorer, search any block by index
- **Mempool** - Pending transactions waiting to be mined
- **Wallet** - View balance, send transactions, transaction history
- **Peers** - Manage P2P network connections
- **API** - Full endpoint reference with live JSON view

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Chain statistics |
| GET | `/api/chain` | Recent blocks |
| GET | `/api/block/{index}` | Block details with transactions |
| GET | `/api/mempool` | Pending transactions |
| GET | `/api/balance/{address}` | Address balance |
| GET | `/api/history/{address}` | Transaction history |
| GET | `/api/peers` | Connected peers |
| GET | `/api/wallet` | Node wallet info |
| GET | `/api/difficulty` | Current difficulty |
| POST | `/api/transactions/new` | Submit transaction |
| POST | `/api/block` | Submit mined block |
| POST | `/api/peers/register` | Register a peer |
| POST | `/api/peers/resolve` | Trigger consensus |

## Mining

The built-in miner uses random nonce search (like real mining but simpler). Difficulty adjusts every 10 blocks targeting 60-second block times.

```bash
# Easy mining for demos (difficulty 2-8)
python -m skyecoin.cli.miner --standalone --difficulty 4

# Mine via a remote node
python -m skyecoin.cli.miner --node http://192.168.1.50:5000

# Use a specific wallet
python -m skyecoin.cli.miner --standalone --private-key my_key.pem
```

## Running Tests

```bash
pytest tests/ -v
```

## Configuration

Create `data/config.json` to customize settings:

```json
{
    "host": "0.0.0.0",
    "port": 5000,
    "difficulty": 4,
    "target_block_time": 60,
    "difficulty_adjust_interval": 10,
    "coinbase_reward": 50.0,
    "fee_per_kb": 0.25,
    "bootstrap_nodes": ["192.168.1.50:5000"]
}
```

## How It Works

1. **Keys**: ECDSA secp256k1 keys generate address = RIPEMD160(SHA256(public_key))
2. **Transactions**: Signed with private key, verified with public key + address check
3. **UTXO**: Unspent Transaction Output model - tracks every coin's origin
4. **Mining**: SHA-256 proof-of-work with dynamic difficulty adjustment
5. **Consensus**: Longest valid chain wins, nodes sync via HTTP
6. **Fees**: Per-byte transaction fees go to miner alongside coinbase reward

## License

GPL-3.0 - See LICENSE.txt
