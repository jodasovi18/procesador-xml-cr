"""Generación y hashing de tokens de agente."""
import hashlib
import secrets


def generar_token() -> str:
    """Token aleatorio url-safe (~43 chars, 256 bits de entropía)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """sha256 hex del token (lo que se guarda en la BD)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
