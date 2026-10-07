"""Escritura de documentos: se comprueban los permisos antes y cada archivo se reemplaza de una vez."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from grafo_ia.errors import GraphError


def ensure_writable(paths) -> None:
    """Verifica permisos antes de escribir nada: un lote no debe quedar aplicado a medias."""
    for path in paths:
        path = Path(path)
        parent = path.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not os.access(parent, os.W_OK) or (path.exists() and not os.access(path, os.R_OK)):
            raise GraphError(f"sin permisos de escritura en {parent}; no se cambió nada")


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".grafo-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
