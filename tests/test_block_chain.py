import pytest
from skyecoin.crypto import generate_keypair
from skyecoin.models.block import Block
from skyecoin.models.transaction import create_coinbase_transaction, create_transaction
from skyecoin.mining import mine_block, validate_proof
from skyecoin.validation import validate_block, validate_proof_of_work
from skyecoin.mining.difficulty import calculate_difficulty
from skyecoin.storage import Database
from skyecoin.config import Config
from skyecoin.chain import ChainManager
from skyecoin.mempool import Mempool


class TestBlock:
    def test_create_block(self):
        priv, pub, addr = generate_keypair()
        coinbase = create_coinbase_transaction(addr, 1, 50.0, 0.0)
        block = Block(
            block_index=1,
            previous_hash="0" * 64,
            transactions=[coinbase],
            difficulty=4,
            miner_private_key_pem=priv,
        )
        assert block.block_index == 1
        assert block.previous_hash == "0" * 64
        assert len(block.transactions) == 1

    def test_mine_and_validate_block(self):
        priv, pub, addr = generate_keypair()
        coinbase = create_coinbase_transaction(addr, 1, 50.0, 0.0)
        block = Block(
            block_index=1,
            previous_hash="0" * 64,
            transactions=[coinbase],
            difficulty=16,
            miner_private_key_pem=priv,
        )
        assert mine_block(block)
        assert validate_proof(block)
        assert validate_block(block)

    def test_block_signature(self):
        priv, pub, addr = generate_keypair()
        coinbase = create_coinbase_transaction(addr, 1, 50.0, 0.0)
        block = Block(
            block_index=1,
            previous_hash="0" * 64,
            transactions=[coinbase],
            difficulty=16,
            miner_private_key_pem=priv,
        )
        mine_block(block)
        assert block.verify()

    def test_block_to_from_dict(self):
        priv, pub, addr = generate_keypair()
        coinbase = create_coinbase_transaction(addr, 1, 50.0, 0.0)
        block = Block(
            block_index=1,
            previous_hash="0" * 64,
            transactions=[coinbase],
            difficulty=16,
            miner_private_key_pem=priv,
        )
        mine_block(block)
        d = block.to_dict()
        b2 = Block.from_dict(d)
        assert b2.block_hash == block.block_hash
        assert b2.block_index == block.block_index


class TestChain:
    @pytest.fixture
    def fresh_chain(self, tmp_path):
        import shutil
        data_dir = tmp_path / "data"
        config = Config()
        config.data_dir = str(data_dir)
        config.difficulty = 16
        db = Database(config.db_path)
        mempool = Mempool()
        chain = ChainManager(db, mempool, config)
        priv, pub, addr = generate_keypair()
        chain.initialize(addr, pub)
        yield chain, db, mempool, config, priv, addr
        db.close()
        shutil.rmtree(str(data_dir), ignore_errors=True)

    def test_genesis_block(self, fresh_chain):
        chain, db, mempool, config, priv, addr = fresh_chain
        assert db.get_block_count() == 1
        genesis = db.get_block(0)
        assert genesis is not None
        assert genesis["block_index"] == 0
        assert genesis["miner_address"] == addr

    def test_genesis_balance(self, fresh_chain):
        chain, db, mempool, config, priv, addr = fresh_chain
        balance = db.get_balance(addr)
        assert balance == config.coinbase_reward

    def test_mine_next_block(self, fresh_chain):
        chain, db, mempool, config, priv, addr = fresh_chain
        # Add a pending transaction
        tx = create_transaction(priv, addr, 5.0, 0.001)
        mempool.add_transaction(tx)

        # Build and mine a new block
        last = db.get_last_block()
        block = Block(
            block_index=last["block_index"] + 1,
            previous_hash=last["block_hash"],
            transactions=[],
            difficulty=16,
            miner_private_key_pem=priv,
        )
        coinbase = create_coinbase_transaction(addr, block.block_index, config.coinbase_reward, 0.001)
        block.transactions = [coinbase] + mempool.get_transactions()

        assert mine_block(block)
        accepted, msg = chain.accept_block(block)
        assert accepted, msg
        assert db.get_block_count() == 2


class TestMempool:
    def test_add_transaction(self):
        mempool = Mempool()
        priv, pub, addr = generate_keypair()
        tx = create_transaction(priv, addr, 10.0, 0.001)
        assert mempool.add_transaction(tx)
        assert mempool.size() == 1

    def test_duplicate_rejected(self):
        mempool = Mempool()
        priv, pub, addr = generate_keypair()
        tx = create_transaction(priv, addr, 10.0, 0.001)
        mempool.add_transaction(tx)
        assert not mempool.add_transaction(tx)
        assert mempool.size() == 1

    def test_invalid_tx_rejected(self):
        mempool = Mempool()
        _, _, addr = generate_keypair()
        tx = create_coinbase_transaction(addr, 1, 50.0, 0.0)
        tx.sender = "INVALID"
        assert not mempool.add_transaction(tx)
