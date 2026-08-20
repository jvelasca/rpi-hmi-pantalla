"""Version unica de la aplicacion, leida de VERSION en la raiz del repo.

Este modulo es la fuente unica de la version en backend. Lee el fichero
VERSION (raiz del repo) en tiempo de importacion y expone ``__version__``.
Si el fichero no existe (p. ej. empaquetado parcial), cae a un fallback seguro.
"""

from __future__ import annotations

from pathlib import Path

# _version.py -> app -> backend -> raiz del repo
_VERSION_PATH = Path(__file__).resolve().parents[2] / "VERSION"

_FALLBACK = "0.3.0"


def _read_version() -> str:
    """Lee VERSION de la raiz del repo, con fallback si no existe."""
    try:
        return _VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return _FALLBACK


__version__ = _read_version()
