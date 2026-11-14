"""Escritura de documentos: se comprueban los permisos antes y cada archivo se reemplaza de una vez."""

from __future__ import annotations

import os
import secrets
import stat
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
    """Reemplaza el archivo de una vez, con los permisos que tendría si se hubiera escrito directo.

    El temporal no se crea con mkstemp: ese lo deja en 600 y, tras el replace, el documento queda ilegible
    para el resto del equipo (en un directorio con ACL por defecto, además, con la máscara en ---). Creado
    con 666, el sistema aplica el umask o la ACL heredada; si el documento ya existía, conserva su modo.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path.parent / f".grafo-{secrets.token_hex(8)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if path.exists():
            os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
