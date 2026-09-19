"""SHA-256 con saltos de línea normalizados (`\\r\\n` -> `\\n`) para `last_synced_hash`.

Git puede convertir los saltos de línea según el SO; sin normalizar, el mismo
código daría dos hashes. Solo identifica cambios, no protege nada.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK = 64 * 1024


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def hash_file(path: Path | str, chunk_size: int = CHUNK) -> str:
    """Hash por bloques. Un `\\r` al final de un bloque se guarda para unirlo
    con el siguiente: si el `\\n` cae en el otro bloque, el par no se partiría."""
    h = hashlib.sha256()
    carry = b""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            data = carry + chunk
            if data.endswith(b"\r"):
                carry, data = b"\r", data[:-1]
            else:
                carry = b""
            h.update(data.replace(b"\r\n", b"\n"))
    h.update(carry)
    return h.hexdigest()
