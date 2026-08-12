import pytest
from skyecoin.crypto import generate_keypair
from skyecoin.models.transaction import Transaction, create_transaction, create_coinbase_transaction


class TestTransaction:
    def test_create_and_sign(self):
        priv, pub, addr = generate_keypair()
        tx = create_transaction(priv, addr, 10.0, 0.001)
        assert tx.verify()
        assert tx.amount == 10.0
        assert tx.fee == 0.001
        assert len(tx.tx_hash) == 64
        assert tx.sender == addr

    def test_tampered_transaction_fails_verification(self):
        priv, pub, addr = generate_keypair()
        tx = create_transaction(priv, addr, 10.0, 0.001)
        tx.amount = 100.0
        assert not tx.verify()

    def test_coinbase_transaction(self):
        tx = create_coinbase_transaction("test_address", 1, 50.0, 0.5)
        assert tx.verify()
        assert tx.sender == "COINBASE"
        assert tx.amount == 50.5
        assert tx.fee == 0.0

    def test_to_dict_and_from_dict(self):
        priv, pub, addr = generate_keypair()
        tx = create_transaction(priv, addr, 10.0, 0.001)
        d = tx.to_dict()
        tx2 = Transaction.from_dict(d)
        assert tx2.verify()
        assert tx2.tx_hash == tx.tx_hash
        assert tx2.amount == tx.amount

    def test_invalid_signature_fails(self):
        _, _, addr = generate_keypair()
        tx = Transaction(sender=addr, recipient=addr, amount=10.0)
        tx.public_key_hex = "deadbeef"
        tx.signature = "bad:sig"
        tx.tx_hash = tx.compute_hash()
        assert not tx.verify()

    def test_different_recipient(self):
        priv, pub, sender = generate_keypair()
        _, _, recipient = generate_keypair()
        tx = create_transaction(priv, recipient, 5.0, 0.001)
        assert tx.verify()
        assert tx.sender == sender
        assert tx.recipient == recipient
