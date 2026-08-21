"""Hashing de la contraseña del panel web (PBKDF2-HMAC-SHA256, stdlib).

Proporciona funciones puras para generar y verificar hashes de contraseña
sin añadir dependencias externas. Se usa ``hashlib.pbkdf2_hmac`` con un salt
aleatorio por hash y ``hmac.compare_digest`` para comparaciones en tiempo
constante (resistente a timing attacks).

Formato de almacenamiento (una sola cadena, separable por ``$``):

    ``pbkdf2_sha256$<iteraciones>$<salt_base64url>$<hash_base64url>``

Uso:
    from backend.app.services.password_hash import hash_password, verify_password

    stored = hash_password("1234")
    assert verify_password("1234", stored)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

#: Contraseña de fábrica por defecto del panel web.
DEFAULT_PASSWORD = "1234"

#: Algoritmo identificado en el prefijo del formato de almacenamiento.
_ALGORITHM = "pbkdf2_sha256"

#: Iteraciones de PBKDF2 (ajustable; 120k es un equilibrio razonable en una Pi).
_ITERATIONS = 120_000

#: Longitud del salt aleatorio en bytes.
_SALT_BYTES = 16


def _b64url(data: bytes) -> str:
    """Codifica bytes en base64url sin relleno."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    """Decodifica base64url sin relleno (tolera valores malformados)."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    """Genera un hash PBKDF2-HMAC-SHA256 de ``password`` con salt aleatorio.

    Args:
        password: Contraseña en texto plano.

    Returns:
        Cadena con formato ``pbkdf2_sha256$<iter>$<salt>$<hash>`` (base64url).
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Verifica ``password`` contra un hash almacenado en tiempo constante.

    Args:
        password: Contraseña en texto plano a comprobar.
        stored: Hash almacenado en el formato de ``hash_password``.

    Returns:
        True si la contraseña coincide; False si no coincide o si ``stored``
        está malformado (sin lanzar excepciones).
    """
    try:
        algorithm, iterations_raw, salt_b64, hash_b64 = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)
