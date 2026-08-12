import time
import logging
from typing import Optional
import httpx

from serpentcoin.storage import Database
from serpentcoin.models.block import Block
from serpentcoin.models.transaction import Transaction

logger = logging.getLogger(__name__)


class NodeManager:
    def __init__(self, db: Database, host: str, port: int):
        self.db = db
        self.address = f"{host}:{port}"
        self._client = httpx.Client(timeout=10.0)

    def register_node(self, node_address: str) -> bool:
        if node_address == self.address:
            return False
        self.db.add_peer(node_address)
        return True

    def remove_node(self, node_address: str):
        self.db.remove_peer(node_address)

    def get_nodes(self) -> list[str]:
        return self.db.get_peers()

    def broadcast_block(self, block: Block) -> dict[str, str]:
        results = {}
        block_data = block.to_dict()
        for peer in self.get_nodes():
            try:
                url = f"http://{peer}/block"
                resp = self._client.post(url, json=block_data)
                results[peer] = resp.text
            except Exception as e:
                logger.warning("Failed to broadcast block to %s: %s", peer, e)
                results[peer] = f"error: {e}"
        return results

    def broadcast_transaction(self, tx: Transaction) -> dict[str, str]:
        results = {}
        tx_data = tx.to_dict()
        for peer in self.get_nodes():
            try:
                url = f"http://{peer}/transactions/new"
                resp = self._client.post(url, json=tx_data)
                results[peer] = resp.text
            except Exception as e:
                logger.warning("Failed to broadcast tx to %s: %s", peer, e)
                results[peer] = f"error: {e}"
        return results

    def fetch_chain_from_peer(self, peer: str) -> Optional[list[dict]]:
        try:
            url = f"http://{peer}/chain?limit=10000&offset=0"
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch chain from %s: %s", peer, e)
        return None

    def fetch_mempool_from_peer(self, peer: str) -> Optional[list[dict]]:
        try:
            url = f"http://{peer}/mempool"
            resp = self._client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch mempool from %s: %s", peer, e)
        return None

    def resolve_conflicts(self) -> bool:
        peers = self.get_nodes()
        if not peers:
            return False

        replaced = False
        local_height = self.db.get_block_count()

        for peer in peers:
            try:
                url = f"http://{peer}/stats"
                resp = self._client.get(url)
                if resp.status_code != 200:
                    continue
                stats = resp.json()
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

    def close(self):
        self._client.close()
