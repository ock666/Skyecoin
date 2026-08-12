<div id="top"></div>

![Contributors][contributors-shield]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![GPLv3 License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/ock666/skyecoin">
    <h1>🐍 Skyecoin</h1>
  </a>

  <h3 align="center">Skyecoin</h3>

  <p align="center">
    Version 2.0.0 — An Educational Toy Blockchain
    <br />
    <a href="https://github.com/ock666/skyecoin"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/ock666/skyecoin/issues">Report Bug</a>
    ·
    <a href="https://github.com/ock666/skyecoin/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#docker-deployment">Docker Deployment</a></li>
    <li><a href="#web-ui">Web UI</a></li>
    <li><a href="#api-reference">API Reference</a></li>
    <li><a href="#features">Features</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

Skyecoin is a complete rewrite of the original Serpentcoin project — a fully functional **educational toy blockchain** designed for learning how blockchains work under the hood. It features a clean, modern architecture with a real-time web UI, SQLite storage, ECDSA cryptography, and a UTXO-based transaction model.

Originally adapted from Daniel van Flymen's classic tutorial and expanded upon, Skyecoin v2 is a ground-up rebuild addressing every architectural flaw of the original while preserving its educational spirit.

> **Learn Blockchains by Building One:** https://hackernoon.com/learn-blockchains-by-building-one-117428612f46

Here's why:
* To understand blockchain internals — transactions, UTXOs, mining, consensus, forks
* A fun, interactive way to experiment with blockchain mechanics
* Something to tinker with, break, and learn from

If you're curious about how Bitcoin works, Skyecoin lets you see every hash, every nonce attempt, and every block propagate in real-time.

<p align="right">(<a href="#top">back to top</a>)</p>



### Built With

* [FastAPI](https://fastapi.tiangolo.com/) — Async web framework with automatic OpenAPI docs
* [cryptography](https://cryptography.io/) — ECDSA secp256k1 signing and verification
* [SQLite](https://sqlite.org/) — Persistent UTXO, block, peer, and wallet storage
* [Uvicorn](https://www.uvicorn.org/) — ASGI server with WebSocket support
* [Pydantic](https://docs.pydantic.dev/) — Data validation and serialization
* [Jinja2](https://jinja.palletsprojects.com/) — Server-side HTML templating
* [htmx](https://htmx.org/) — Lightweight dynamic UI without JavaScript frameworks
* [httpx](https://www.python-httpx.org/) — Async HTTP client for P2P networking
* [Docker](https://www.docker.com/) — Containerized deployment

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* Python 3.10+
* pip

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/ock666/skyecoin.git
   cd skyecoin
   ```

2. Install the package
   ```sh
   pip install -e ".[dev]"
   ```

3. Run the node
   ```sh
   python run.py
   ```

4. Open the web UI
   ```
   http://localhost:5000
   ```

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- USAGE -->
## Usage

### Start the Node

```sh
# Basic node with web UI
python run.py

# Node with built-in miner (difficulty 4 is fast, 16 is moderate)
python run.py --miner --difficulty 4

# Custom port
python run.py --port 5001

# Enable debug logging
python run.py --debug
```

### Run a Separate Miner

```sh
# Mine via the local node (uses node's wallet)
python -m skyecoin.cli.miner --node http://127.0.0.1:5000 --difficulty 16

# Standalone miner with its own chain
python -m skyecoin.cli.miner --standalone --difficulty 4

# Use a specific wallet key
python -m skyecoin.cli.miner --standalone --private-key my_key.pem
```

### Run Tests

```sh
pytest tests/ -v
```

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- DOCKER -->
## Docker Deployment

Skyecoin ships with Docker and docker-compose for easy deployment to servers, NAS devices, or Unraid.

```sh
# Deploy to Unraid server via rsync + docker compose
./deploy.sh

# Manual docker-compose
docker compose up -d --build

# With built-in miner
docker compose --profile miner up -d

# View logs
docker compose logs -f
```

The `skyecoin_data` Docker volume persists the blockchain, wallet keys, and peer list across container rebuilds.

### Configuration

Create `data/config.json` or set environment variables:

```json
{
  "difficulty": 16,
  "target_block_time": 60,
  "difficulty_adjust_interval": 10,
  "coinbase_reward": 50.0,
  "halving_interval": 2100,
  "lottery_bonus": 25.0,
  "bootstrap_nodes": ["192.168.1.50:5000"]
}
```

Environment variables: `SKYECOIN_HOST`, `SKYECOIN_PORT`, `SKYECOIN_DIFFICULTY`, etc.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- WEB UI -->
## Web UI

Skyecoin includes a full web dashboard with live WebSocket updates at `http://localhost:5000`.

| Tab | Description |
|-----|-------------|
| **Dashboard** | Live chain stats, mining visualizer with pulse animation, recent blocks |
| **Blocks** | Block explorer — click any block to see full details, transactions, signatures |
| **Mempool** | Pending transactions waiting to be mined, real-time updates |
| **Wallet** | View balance, send transactions, view keys, transaction history |
| **Peers** | Peer network graph, add/remove peers, resolve chain conflicts |
| **📒 Addresses** | Saved address book (localStorage), QR code generation, one-click send |
| **🔧 Sandbox** | Craft transactions with live preview, cost breakdown, validation |
| **🖥️ Nodes** | Multi-node dashboard — monitor remote nodes side-by-side |
| **🧪 Sim Lab** | Double-spend attack simulator, chain fork visualizer |
| **🏅 Leaderboard** | Top miners by blocks found |
| **🏆 Achievements** | 10 unlockable badges (Genesis, Centurion, Halving, Whale, etc.) |
| **API** | Full REST endpoint reference with live JSON view |
| **/docs** | Auto-generated Swagger OpenAPI documentation |

All data updates in real-time via WebSocket — no polling, no page refreshes.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- API -->
## API Reference

The full API is documented at `http://localhost:5000/docs` (Swagger UI).

### Blockchain

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Chain height, difficulty, mempool size, peer count |
| `GET` | `/api/chain?limit=50` | Recent blocks |
| `GET` | `/api/block/{index}` | Block details with full transaction list |
| `GET` | `/api/block/diff/{index}` | Compare block with its predecessor |
| `GET` | `/api/difficulty` | Current mining difficulty and epoch settings |
| `GET` | `/api/reward` | Coinbase reward, halving info, lottery rules |

### Transactions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mempool` | Pending transactions |
| `GET` | `/api/balance/{address}` | Address balance (UTXO sum) |
| `GET` | `/api/history/{address}` | Transaction history for an address |
| `GET` | `/api/utxo/{address}` | UTXO set with lock heights and amounts |
| `POST` | `/api/transactions/new` | Submit a transaction to the mempool |
| `GET` | `/api/transactions/{tx_hash}` | Look up a specific transaction |

### P2P Networking

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/peers` | List connected peers |
| `POST` | `/api/peers/register` | Register a new peer |
| `POST` | `/api/peers/gossip` | Exchange peer lists (auto-discovery) |
| `POST` | `/api/peers/resolve` | Trigger chain consensus (longest chain wins) |

### Mining & Wallet

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/block` | Submit a forged block |
| `GET` | `/api/wallet` | Node wallet address, public key, balance |
| `GET` | `/api/wallet/key` | Full wallet including private key (internal use) |
| `POST` | `/api/wallet/generate` | Generate a new wallet |
| `GET` | `/api/leaderboard` | Top miners by blocks found |
| `GET` | `/api/achievements` | Unlockable badges and progress |

### Real-time

| Method | Endpoint | Description |
|--------|----------|-------------|
| `WS` | `/ws` | WebSocket stream: `block_mined`, `tx_pending`, `peer_joined` |

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- FEATURES -->
## Features

### Cryptography
- **ECDSA secp256k1** — Bitcoin-standard elliptic curve cryptography
- **HASH160 address derivation** — `RIPEMD160(SHA256(public_key))` for wallet addresses
- **Transaction signing** — Every transaction is signed with the sender's private key and verified against their public key

### UTXO Model
- **Unspent Transaction Output tracking** — Balances computed from UTXOs, not chain scanning
- **Proper UTXO spending** — Sender UTXOs are consumed and new ones created atomically
- **Change outputs** — When a UTXO overpays, change is returned to the sender
- **Time-locked transactions** — UTXOs can be locked until a future block height

### Mining
- **SHA-256 Proof of Work** — Random nonce search with target difficulty
- **Dynamic difficulty adjustment** — Every 10 blocks, targets 60-second block times
- **Halving events** — Coinbase reward halves every 2,100 blocks (configurable)
- **Block lottery** — Golden nonces and hash patterns earn bonus rewards

### Consensus
- **Longest valid chain wins** — Nodes sync with peers and adopt longer valid chains
- **Block validation** — Proof-of-work, miner signature, and all transaction signatures verified
- **Coinbase validation** — Checks reward matches halving schedule + fees + lottery bonus

### P2P Networking
- **HTTP-based node communication** — REST API for block/transaction broadcasting
- **Peer auto-discovery** — Bootstrap from known nodes, gossip peer lists every 30 seconds
- **Two-way handshake** — When a peer registers with you, you register back
- **Dead peer cleanup** — Stale peers removed after 5 minutes of inactivity

### Storage
- **SQLite with WAL mode** — Fast, ACID-compliant storage for blocks, transactions, UTXOs, peers, wallet
- **Named Docker volume** — Chain data persists across container restarts and rebuilds
- **JSON config file** — Human-readable configuration with environment variable overrides

### Web UI
- **Real-time WebSocket updates** — Blocks, transactions, and peers update live
- **Clickable block explorer** — Expand any block to see full details, miner signature, and transactions
- **Mining visualizer** — Pulse animation on the dashboard when new blocks arrive
- **Audio cues** — Sine-wave chime when your node mines a block
- **Multi-node dashboard** — Monitor remote nodes side-by-side
- **Transaction sandbox** — Preview TXs with cost breakdown before submitting
- **Double-spend simulator** — Submit conflicting transactions and watch one get rejected
- **Fork visualizer** — See how chain forks resolve with longest-chain consensus
- **Achievement badges** — 10 unlockable milestones from Genesis to Whale
- **Leaderboard** — Top miners ranked by blocks found

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- ARCHITECTURE -->
## Architecture

```
skyecoin/
├── crypto/            # ECDSA secp256k1 keygen, signing, address derivation
├── models/            # Block and Transaction data models
│   ├── block.py       # Block structure, merkle root, mining, signing
│   └── transaction.py # TX structure, signing, verification, coinbase
├── validation/        # Block, transaction, and chain validation
├── storage/           # SQLite database layer (blocks, UTXOs, peers, wallet)
├── mining/            # SHA-256 PoW and difficulty epoch adjustment
│   └── difficulty.py  # Every 10 blocks: ±1 difficulty toward 60s target
├── network/           # P2P node discovery, gossip, broadcasting, consensus
├── events.py          # Async pub/sub EventBus for WebSocket broadcasting
├── chain.py           # Chain manager — orchestration layer
├── mempool.py         # Pending transaction pool with fee-prioritization
├── config.py          # JSON + env var configuration management
├── app.py             # FastAPI application with all routes and WebSocket
├── api/
│   └── schemas.py     # Pydantic models for request/response validation
├── cli/
│   └── miner.py       # CLI miner (standalone or node-connected modes)
├── web/
│   ├── templates/     # Jinja2 HTML templates with htmx
│   │   ├── index.html # Main single-page application
│   │   └── partials/  # Reusable template fragments
│   └── static/
│       └── css/       # Dark theme stylesheet
├── Dockerfile         # Python 3.12-slim container
├── docker-compose.yml # Node + optional miner service
├── deploy.sh          # Rsync + Docker Compose deploy script
└── run.py             # CLI entry point for the node
```

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] ECDSA secp256k1 cryptography
- [x] UTXO-based transaction model with SQLite storage
- [x] SHA-256 Proof of Work with dynamic difficulty adjustment
- [x] Halving events (every 2,100 blocks)
- [x] Block lottery (golden nonces and hash patterns)
- [x] Time-locked transactions
- [x] P2P peer discovery with gossip protocol
- [x] Longest-chain consensus with chain sync
- [x] FastAPI REST API with OpenAPI auto-docs
- [x] Real-time WebSocket events (blocks, transactions, peers)
- [x] Full web dashboard with 12 tabs
- [x] Clickable block explorer with transaction details
- [x] Live mining visualizer with audio cues
- [x] Address book with QR code generation
- [x] Transaction sandbox with preview and validation
- [x] Multi-node monitoring dashboard
- [x] Double-spend attack simulator
- [x] Chain fork visualizer
- [x] Achievement badge system
- [x] Miner leaderboard
- [x] Docker + docker-compose deployment
- [x] Unraid deployment via deploy script
- [ ] Multi-signature (M-of-N) addresses
- [ ] Advanced scripting / smart contract-lite opcodes
- [ ] Mobile-responsive progressive web app
- [ ] Integration test suite for P2P scenarios

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this project better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the GPLv3 License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Oskar Petersen — [LinkedIn](https://www.linkedin.com/in/oskar-petersen-39a849185/) — oskargjerlevpetersen@gmail.com

Project Link: [https://github.com/ock666/skyecoin](https://github.com/ock666/skyecoin)

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [Satoshi Nakamoto](https://bitcoin.org/bitcoin.pdf) — Bitcoin whitepaper
* [Daniel van Flymen](https://hackernoon.com/learn-blockchains-by-building-one-117428612f46) — Original blockchain tutorial that inspired Serpentcoin
* [FastAPI](https://fastapi.tiangolo.com/) — Exceptional Python web framework
* [cryptography](https://cryptography.io/) — Robust cryptographic library
* [htmx](https://htmx.org/) — Hypermedia-driven UI without complexity
* [Img Shields](https://shields.io) — README badges

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/ock666/skyecoin.svg?style=for-the-badge
[contributors-url]: https://github.com/ock666/skyecoin/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/ock666/skyecoin.svg?style=for-the-badge
[forks-url]: https://github.com/ock666/skyecoin/network/members
[stars-shield]: https://img.shields.io/github/stars/ock666/skyecoin.svg?style=for-the-badge
[stars-url]: https://github.com/ock666/skyecoin/stargazers
[issues-shield]: https://img.shields.io/github/issues/ock666/skyecoin.svg?style=for-the-badge
[issues-url]: https://github.com/ock666/skyecoin/issues
[license-shield]: https://img.shields.io/github/license/ock666/skyecoin?style=for-the-badge
[license-url]: https://github.com/ock666/skyecoin/blob/main/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/oskar-petersen-39a849185/
