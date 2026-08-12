import hashlib
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from cryptography.hazmat.backends import default_backend


CURVE = ec.SECP256K1()
HASH_FUNC = hashes.SHA256()


def generate_keypair():
    private_key = ec.generate_private_key(CURVE, default_backend())
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    address = public_key_to_address(public_key)
    return private_pem, public_pem, address


def public_key_to_address(public_key):
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    sha256_digest = hashlib.sha256(pub_bytes).digest()
    ripemd160 = hashlib.new("ripemd160", sha256_digest).digest()
    return ripemd160.hex()


def load_private_key(private_pem):
    return serialization.load_pem_private_key(
        private_pem.encode(), password=None, backend=default_backend()
    )


def load_public_key_from_pem(public_pem):
    return serialization.load_pem_public_key(
        public_pem.encode(), backend=default_backend()
    )


def load_public_key_from_der(der_hex):
    der_bytes = bytes.fromhex(der_hex)
    return serialization.load_der_public_key(der_bytes, backend=default_backend())


def sign_data(private_key: ec.EllipticCurvePrivateKey, data: bytes) -> str:
    signature = private_key.sign(data, ec.ECDSA(HASH_FUNC))
    r, s = decode_dss_signature(signature)
    return f"{r:x}:{s:x}"


def verify_signature(public_key: ec.EllipticCurvePublicKey, data: bytes, signature_hex: str) -> bool:
    try:
        r_str, s_str = signature_hex.split(":")
        r, s = int(r_str, 16), int(s_str, 16)
        der_sig = encode_dss_signature(r, s)
        public_key.verify(der_sig, data, ec.ECDSA(HASH_FUNC))
        return True
    except Exception:
        return False


def public_key_hex(public_key: ec.EllipticCurvePublicKey) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).hex()
