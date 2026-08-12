import hashlib
import hmac
import secrets
import logging

from fastapi import Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

HASH_ITERATIONS = 600_000
HASH_ALGORITHM = "sha256"
SALT_LENGTH = 32
AUTH_COOKIE = "skyecoin_auth"
COOKIE_MAX_AGE = 86400 * 30


def _get_secret(request: Request) -> str:
    return request.app.state.config.session_secret


def _sign(value: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=HASH_ITERATIONS,
    )
    return f"{HASH_ITERATIONS}:{salt}:{dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        iterations_str, salt, stored_hash = hashed.split(":")
        iterations = int(iterations_str)
        dk = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=iterations,
        )
        return secrets.compare_digest(dk.hex(), stored_hash)
    except (ValueError, AttributeError):
        return False


def is_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(AUTH_COOKIE, "")
    if not cookie:
        return False
    try:
        value, sig = cookie.split(".", 1)
        expected = _sign(value, _get_secret(request))
        return secrets.compare_digest(sig, expected)
    except (ValueError, TypeError):
        return False


def set_auth_cookie(response: Response, secret: str) -> None:
    token = secrets.token_hex(32)
    sig = _sign(token, secret)
    response.set_cookie(
        AUTH_COOKIE,
        f"{token}.{sig}",
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE)
