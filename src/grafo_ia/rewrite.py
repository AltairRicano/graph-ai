"""Reescritura de enlaces en texto, usando las posiciones exactas del parser.

Nunca se hace regex a ciegas sobre el archivo: lo que está dentro de bloques
de código o código inline no se toca.
"""

from __future__ import annotations

import os
import posixpath
import tempfile
from pathlib import Path
from typing import Callable

from grafo_ia import parser
from grafo_ia.paths import folder_rel_of_index


def rewrite_links(text: str, fn: Callable[[parser.Link], str | None]) -> tuple[str, int]:
    """Aplica `fn` a cada enlace; si devuelve texto, reemplaza el enlace completo."""
    doc = parser.parse(text)
    edits: dict[int, list[tuple[int, int, str]]] = {}
    count = 0
    for link in parser.links(doc):
        new = fn(link)
        if new is None:
            continue
        edits.setdefault(link.line, []).append((link.start, link.end, new))
        count += 1
    if not count:
        return text, 0
    lines = list(doc.lines)
    for i, items in edits.items():
        line = lines[i]
        for start, end, new in sorted(items, reverse=True):
            line = line[:start] + new + line[end:]
        lines[i] = line
    return "".join(lines), count


def display_text(link: parser.Link) -> str:
    """Lo que queda cuando se quitan los corchetes: el alias por convención."""
    if link.alias is not None:
        return link.alias
    if link.section:
        return link.section.split("#")[-1]
    base = posixpath.basename(link.target.replace("\\", "/"))
    return base[:-3] if base.endswith(".md") else base


def retarget(old_text: str, old_id: str, new_id: str, new_ids: set[str], tipo: str | None = None) -> str:
    """Nuevo texto de destino conservando la forma en que estaba escrito."""
    t = old_text.replace("\\", "/").strip()
    if t.startswith("./") or t.startswith("../"):
        return new_id
    if t == old_id:
        return new_id
    if old_id.endswith(".md") and new_id.endswith(".md") and t == old_id[:-3]:
        return new_id[:-3]
    if tipo == "indice" and t == folder_rel_of_index(old_id):
        return folder_rel_of_index(new_id)
    # forma corta: mismo número de componentes, si sigue siendo única
    had_md = t.endswith(".md")
    k = t.count("/") + 1
    cand = "/".join(new_id.split("/")[-k:])
    matches = [i for i in new_ids if i == cand or i.endswith("/" + cand)]
    if len(matches) == 1:
        return cand[:-3] if cand.endswith(".md") and not had_md else cand
    return new_id


def ensure_writable(paths) -> None:
    """Verifica permisos antes de escribir nada: un fallo a medias dejaría enlaces rotos."""
    from grafo_ia.errors import GraphError

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


def prune_empty_dirs(start: Path, stop: Path) -> None:
    """Borra carpetas vacías desde `start` hacia arriba, sin pasar de `stop`."""
    start, stop = start.absolute(), stop.absolute()
    cur = start
    while cur != stop and stop in cur.parents:
        try:
            cur.rmdir()
        except OSError:
            return
        cur = cur.parent
