import pytest
from serpentcoin.crypto import generate_keypair, sign_data, verify_signature, load_private_key, public_key_to_address, public_key_hex


class TestCrypto:
    def test_generate_keypair(self):
        priv, pub, addr = generate_keypair()
        assert priv.startswith("-----BEGIN PRIVATE KEY-----")
        assert pub.startswith("-----BEGIN PUBLIC KEY-----")
        assert len(addr) == 40

    def test_sign_and_verify(self):
        priv, pub, addr = generate_keypair()
        data = b"test message"
        key = load_private_key(priv)
        sig = sign_data(key, data)
        pub_key = key.public_key()
        assert verify_signature(pub_key, data, sig)
        assert not verify_signature(pub_key, data, sig + "ff")
        assert not verify_signature(pub_key, b"different", sig)

    def test_address_derivation(self):
        priv, pub, addr = generate_keypair()
        key = load_private_key(priv)
        pub_key = key.public_key()
        assert public_key_to_address(pub_key) == addr
        assert len(addr) == 40

    def test_different_keys_different_addresses(self):
        _, _, addr1 = generate_keypair()
        _, _, addr2 = generate_keypair()
        assert addr1 != addr2
