import time
import logging
import threading
from typing import Optional
import httpx

from serpentcoin.storage import Database
from serpentcoin.models.block import Block
from serpentcoin.models.transaction import Transaction

logger = logging.getLogger(__name__)


class NodeManager:
    def __init__(self, db: Database, host: str, port: int, bootstrap_nodes: list[str] | None = None):
        self.db = db
        self.host = host
        self.port = port
        self.address = f"{host}:{port}"
        self._client = httpx.Client(timeout=10.0)
        self._running = True
        self._bootstrap_nodes = bootstrap_nodes or []

    def start_discovery(self):
        """Bootstrap into the network and start periodic peer discovery."""
        for node in self._bootstrap_nodes:
            if node != self.address:
                self._introduce_to(node)

        thread = threading.Thread(target=self._discovery_loop, daemon=True)
        thread.start()

    def _introduce_to(self, node: str) -> bool:
        """Introduce ourselves to a peer and learn about their network."""
        try:
            url = f"http://{node}/api/peers/register"
            resp = self._client.post(url, json={"address": self.address})
            if resp.status_code == 200:
                self.register_node(node)
                data = resp.json()
                peer_list = data.get("peers", [])
                for peer in peer_list:
                    if peer != self.address and peer not in self.get_nodes():
                        self.register_node(peer)
                logger.info("Introduced to %s, discovered %d peers", node, len(peer_list))
                return True
        except Exception:
            pass
        return False

    def _discovery_loop(self):
        """Periodically exchange peer lists and discover new nodes."""
        while self._running:
            time.sleep(30)
            peers = list(self.get_nodes())
            for peer in peers:
                try:
                    url = f"http://{peer}/api/peers/gossip"
                    resp = self._client.post(url, json={
                        "peers": self.get_nodes(),
                        "sender": self.address,
                    })
                    if resp.status_code == 200:
                        data = resp.json()
                        for new_peer in data.get("peers", []):
                            if new_peer != self.address:
                                self.register_node(new_peer)
                except Exception:
                    stale_threshold = time.time() - 300
                    self.db.execute(
                        "DELETE FROM peers WHERE address = ? AND last_seen < ?",
                        (peer, stale_threshold),
                    )
                    self.db.commit()

    def register_node(self, node_address: str) -> bool:
        if node_address == self.address:
            return False
        self.db.add_peer(node_address)
        return True

    def remove_node(self, node_address: str):
        self.db.remove_peer(node_address)

    def get_nodes(self) -> list[str]:
        return self.db.get_peers()

    def get_nodes_with_data(self) -> list[dict]:
        rows = self.db.fetchall("SELECT address, last_seen FROM peers ORDER BY last_seen DESC")
        return [{"address": r["address"], "last_seen": r["last_seen"]} for r in rows]

    def broadcast_block(self, block: Block) -> dict[str, str]:
        results = {}
        block_data = block.to_dict()
        for peer in self.get_nodes():
            try:
                url = f"http://{peer}/api/block"
                resp = self._client.post(url, json=block_data)
                results[peer] = resp.text
                self.db.add_peer(peer)
            except Exception as e:
                logger.warning("Failed to broadcast block to %s: %s", peer, e)
                results[peer] = f"error: {e}"
        self.db.commit()
        return results

    def broadcast_transaction(self, tx: Transaction) -> dict[str, str]:
        results = {}
        tx_data = tx.to_dict()
        for peer in self.get_nodes():
            try:
                url = f"http://{peer}/api/transactions/new"
                resp = self._client.post(url, json=tx_data)
                results[peer] = resp.text
                self.db.add_peer(peer)
            except Exception as e:
                logger.warning("Failed to broadcast tx to %s: %s", peer, e)
                results[peer] = f"error: {e}"
        self.db.commit()
        return results

    def fetch_chain_from_peer(self, peer: str) -> Optional[list[dict]]:
        try:
            url = f"http://{peer}/api/chain?limit=10000&offset=0"
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch chain from %s: %s", peer, e)
        return None

    def fetch_stats_from_peer(self, peer: str) -> Optional[dict]:
        try:
            url = f"http://{peer}/api/stats"
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def resolve_conflicts(self) -> bool:
        peers = self.get_nodes()
        if not peers:
            return False

        replaced = False
        local_height = self.db.get_block_count()

        for peer in peers:
            try:
                stats = self.fetch_stats_from_peer(peer)
                if not stats:
                    continue
                remote_height = stats.get("height", 0)

                if remote_height > local_height:
                    logger.info(
                        "Peer %s has longer chain (%d vs %d), syncing...",
                        peer, remote_height, local_height,
                    )
                    remote_chain = self.fetch_chain_from_peer(peer)
                    if remote_chain and self._replace_chain(remote_chain):
                        replaced = True
                        local_height = self.db.get_block_count()
            except Exception as e:
                logger.warning("Error resolving conflicts with %s: %s", peer, e)

        return replaced

    def _replace_chain(self, remote_chain: list[dict]) -> bool:
        if len(remote_chain) <= self.db.get_block_count():
            return False
        for block_data in remote_chain:
            block = Block.from_dict(block_data)
            if block.block_index <= self.db.get_block_count():
                continue
            block_dict = block.to_dict()
            self.db.insert_block(block_dict)
        self.db.rebuild_utxos()
        logger.info("Chain replaced with %d blocks", len(remote_chain))
        return True

    def stop(self):
        self._running = False

    def close(self):
        self._running = False
        self._client.close()
