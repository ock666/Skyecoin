import json
import logging
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from skyecoin.config import Config, setup_logging
from skyecoin.storage import Database
from skyecoin.chain import ChainManager
from skyecoin.mempool import Mempool
from skyecoin.network import NodeManager
from skyecoin.events import event_bus
from skyecoin.api.schemas import (
    TransactionRequest,
    PeerRegisterRequest,
    StatsResponse,
    BalanceResponse,
    WalletResponse,
    MessageResponse,
)
from skyecoin.models.transaction import create_transaction
from skyecoin.crypto import generate_keypair

logger = logging.getLogger(__name__)


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title="Skyecoin", version="2.0.0", docs_url="/docs")

    db = Database(config.db_path)
    mempool = Mempool()
    chain = ChainManager(db, mempool, config)
    nodes = NodeManager(db, config.host, config.port, config.bootstrap_nodes)

    wallet = db.get_wallet()
    if not wallet:
        priv_pem, pub_pem, address = generate_keypair()
        db.set_wallet(priv_pem, pub_pem, address)
        wallet = db.get_wallet()
        logger.info("Generated new wallet: %s", address)

    chain.initialize(wallet["address"], wallet["public_key"])
    nodes.start_discovery()

    web_dir = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
    templates = Jinja2Templates(directory=str(web_dir / "templates"))

    # =========================================================================
    # WebSocket - Real-time events
    # =========================================================================

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        sub = await event_bus.subscribe()
        logger.info("WebSocket client connected (%d total)", event_bus.subscriber_count)
        try:
            history = await event_bus.get_history(limit=50)
            for event in history:
                await ws.send_json(event)

            while True:
                event = await sub.queue.get()
                try:
                    await ws.send_json(event)
                except Exception:
                    break
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await sub.close()
            logger.info("WebSocket client disconnected (%d remaining)", event_bus.subscriber_count)

    # =========================================================================
    # Web UI Routes
    # =========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        stats = chain.get_chain_stats()
        blocks = chain.get_recent_blocks(limit=10)
        w = dict(db.get_wallet())
        w["_balance"] = chain.get_balance(w["address"])
        return templates.TemplateResponse(request, "index.html", {
            "stats": stats,
            "blocks": blocks,
            "peers": nodes.get_nodes(),
            "mempool_txs": mempool.get_all(),
            "wallet": w,
        })

    @app.get("/views/stats", response_class=HTMLResponse)
    async def view_stats(request: Request):
        stats = chain.get_chain_stats()
        stats["peer_count"] = len(nodes.get_nodes())
        return templates.TemplateResponse(request, "partials/stats.html", {
            "stats": stats,
        })

    @app.get("/views/blocks", response_class=HTMLResponse)
    async def view_blocks(request: Request, limit: int = 10):
        blocks = chain.get_recent_blocks(limit=limit)
        return templates.TemplateResponse(request, "partials/block_list.html", {
            "blocks": blocks,
        })

    @app.get("/views/mempool", response_class=HTMLResponse)
    async def view_mempool(request: Request):
        txs = mempool.get_all()
        return templates.TemplateResponse(request, "partials/mempool.html", {
            "mempool_txs": txs,
        })

    @app.get("/views/peers", response_class=HTMLResponse)
    async def view_peers(request: Request):
        peers = nodes.get_nodes()
        return templates.TemplateResponse(request, "partials/peers.html", {
            "peers": peers,
        })

    @app.get("/views/history/{address}", response_class=HTMLResponse)
    async def view_history(request: Request, address: str, limit: int = 20):
        txs = chain.get_address_history(address, limit=limit)
        return templates.TemplateResponse(request, "partials/history.html", {
            "transactions": txs, "address": address,
        })

    # =========================================================================
    # REST API Routes (JSON)
    # =========================================================================

    @app.get("/api/stats")
    async def get_stats():
        stats = chain.get_chain_stats()
        return {
            "height": stats["height"],
            "difficulty": stats["difficulty"],
            "mempool_size": stats["mempool_size"],
            "peer_count": len(nodes.get_nodes()),
            "last_block_hash": stats["last_block_hash"],
            "last_block_time": stats["last_block_time"],
            "total_transactions": stats["total_transactions"],
        }

    @app.get("/api/chain")
    async def get_chain(limit: int = 50, offset: int = 0):
        return chain.get_recent_blocks(limit=limit)

    @app.get("/api/block/{block_index}")
    async def get_block(block_index: int):
        block = chain.get_block(block_index)
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
        return block

    @app.get("/api/mempool")
    async def get_mempool():
        return [tx.to_dict() for tx in mempool.get_all()]

    @app.get("/api/balance/{address}")
    async def get_balance(address: str):
        balance = chain.get_balance(address)
        return {"address": address, "balance": balance}

    @app.get("/api/history/{address}")
    async def get_history(address: str, limit: int = 50):
        return chain.get_address_history(address, limit=limit)

    @app.get("/api/peers")
    async def get_peers():
        return nodes.get_nodes()

    @app.get("/api/difficulty")
    async def get_difficulty():
        last = chain.get_last_block()
        return {
            "difficulty": last["difficulty"] if last else config.difficulty,
            "block_time_target": config.target_block_time,
            "adjust_interval": config.difficulty_adjust_interval,
        }

    @app.post("/api/transactions/new", response_model=MessageResponse)
    async def new_transaction(tx_req: TransactionRequest):
        private_key = tx_req.sender_private_key or wallet["private_key"]
        try:
            tx = create_transaction(
                sender_private_key_pem=private_key,
                recipient=tx_req.recipient,
                amount=tx_req.amount,
                fee=tx_req.fee,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create transaction: {e}")

        from skyecoin.validation import validate_transaction_for_mempool
        valid, reason = validate_transaction_for_mempool(tx, db)
        if not valid:
            raise HTTPException(status_code=400, detail=reason)

        if mempool.add_transaction(tx):
            nodes.broadcast_transaction(tx)
            asyncio.create_task(event_bus.publish("tx_pending", tx.to_dict()))
            return MessageResponse(message=f"Transaction accepted: {tx.tx_hash}")
        else:
            raise HTTPException(status_code=400, detail="Transaction rejected")

    @app.post("/api/block", response_model=MessageResponse)
    async def submit_block(block_data: dict):
        from skyecoin.models.block import Block
        from skyecoin.validation import validate_block

        try:
            block = Block.from_dict(block_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid block data: {e}")

        if not validate_block(block):
            raise HTTPException(status_code=400, detail="Block validation failed")

        accepted, msg = chain.accept_block(block)
        if not accepted:
            raise HTTPException(status_code=400, detail=msg)

        stats = chain.get_chain_stats()
        asyncio.create_task(event_bus.publish("block_mined", {
            "block_index": block.block_index,
            "block_hash": block.block_hash,
            "miner_address": block.miner_address,
            "tx_count": len(block.transactions),
            "nonce": block.nonce,
            "difficulty": block.difficulty,
            "height": stats["height"],
        }))
        nodes.broadcast_block(block)
        return MessageResponse(message=f"Block accepted: {block.block_hash}")

    @app.post("/api/peers/register")
    async def register_peer(peer: PeerRegisterRequest):
        nodes.register_node(peer.address)
        asyncio.create_task(event_bus.publish("peer_joined", {
            "address": peer.address,
            "peer_count": len(nodes.get_nodes()),
        }))
        try:
            import httpx
            client = httpx.Client(timeout=5.0)
            client.post(f"http://{peer.address}/api/peers/register", json={
                "address": f"{config.host}:{config.port}",
            })
            client.close()
        except Exception:
            pass
        return {
            "message": f"Registered: {peer.address}",
            "peers": nodes.get_nodes(),
        }

    @app.post("/api/peers/gossip")
    async def gossip(data: dict):
        sender = data.get("sender", "")
        remote_peers = data.get("peers", [])

        if sender and sender != nodes.address:
            nodes.register_node(sender)
        for peer in remote_peers:
            if peer != nodes.address:
                nodes.register_node(peer)

        return {"peers": nodes.get_nodes(), "sender": nodes.address}

    @app.post("/api/peers/resolve", response_model=MessageResponse)
    async def resolve():
        if nodes.resolve_conflicts():
            return MessageResponse(message="Chain was updated from peers")
        if nodes.resolve_conflicts():
            return MessageResponse(message="Chain was updated from peers")
        return MessageResponse(message="Chain is already up to date")

    @app.get("/api/wallet")
    async def get_wallet():
        w = db.get_wallet()
        balance = chain.get_balance(w["address"])
        return {
            "address": w["address"],
            "public_key": w["public_key"],
            "balance": balance,
        }

    @app.get("/api/wallet/key")
    async def get_wallet_key():
        w = db.get_wallet()
        balance = chain.get_balance(w["address"])
        return {
            "address": w["address"],
            "public_key": w["public_key"],
            "private_key": w["private_key"],
            "balance": balance,
        }

    @app.post("/api/wallet/generate")
    async def generate_wallet():
        priv_pem, pub_pem, address = generate_keypair()
        db.set_wallet(priv_pem, pub_pem, address)
        balance = chain.get_balance(address)
        return {
            "address": address,
            "public_key": pub_pem,
            "private_key": priv_pem,
            "balance": balance,
        }

    @app.get("/api/transactions/{tx_hash}")
    async def get_transaction(tx_hash: str):
        row = db.fetchone("SELECT * FROM transactions WHERE tx_hash = ?", (tx_hash,))
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return dict(row)

    app.state.db = db
    app.state.chain = chain
    app.state.mempool = mempool
    app.state.nodes = nodes
    app.state.config = config
    app.state.wallet = wallet

    return app


def run():
    config = Config.load()
    setup_logging()
    app = create_app(config)
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    run()
