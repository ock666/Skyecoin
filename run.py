#!/usr/bin/env python3
"""Skyecoin - An educational toy blockchain.

Usage:
    python run.py                    Start the node + web UI
    python run.py --port 5001        Start on a different port
    python run.py --difficulty 3     Easier mining for demos
    python run.py --miner            Start the built-in miner too
    python run.py --help             Show all options
"""

import argparse
import sys
import time
import threading
import logging

from skyecoin.config import Config, setup_logging
from skyecoin.app import create_app

logger = logging.getLogger("skyecoin")


def main():
    parser = argparse.ArgumentParser(
        description="Skyecoin v2 - Educational Toy Blockchain"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--difficulty", type=int, default=4, help="Initial mining difficulty")
    parser.add_argument("--miner", action="store_true", help="Start built-in miner")
    parser.add_argument("--miner-key", type=str, help="Miner private key PEM file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level)

    config = Config()
    config.host = args.host
    config.port = args.port
    config.difficulty = args.difficulty

    app = create_app(config)

    if args.miner:
        from skyecoin.crypto import generate_keypair

        if args.miner_key:
            with open(args.miner_key) as f:
                miner_key = f.read()
        else:
            db = app.state.db
            wallet = db.get_wallet()
            miner_key = wallet["private_key"]
            logger.info("Using node wallet for mining")

        def run_miner():
            from skyecoin.cli.miner import mine_standalone
            mine_standalone(miner_key, config.difficulty)

        miner_thread = threading.Thread(target=run_miner, daemon=True)
        miner_thread.start()
        logger.info("Built-in miner started (difficulty: %d)", config.difficulty)

    import uvicorn
    logger.info("Skyecoin node starting on %s:%d", config.host, config.port)
    print(f"\n  Web UI:  http://{config.host if config.host != '0.0.0.0' else 'localhost'}:{config.port}")
    print(f"  API Docs: http://localhost:{config.port}/docs\n")
    uvicorn.run(app, host=config.host, port=config.port, log_level="warning")


if __name__ == "__main__":
    main()
