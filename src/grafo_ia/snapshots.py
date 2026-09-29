"""Instantáneas del código confirmado por `graph update`, para `graph diff`.

`update` guarda el contenido del archivo como blob en el repo anidado de
`.graph` (`git hash-object -w`) y lo ancla con la ref `refs/grafo/sync/<blob>`
para que `git gc` nunca lo pode; el nodo guarda el id en `last_synced_blob`.
Una ref por blob vigente: al reemplazarse, la vieja se suelta si ningún otro
nodo la usa. Sin git o sin repo anidado no hay instantánea (`diff` lo dice).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from grafo_ia.graph_io import Graph
from grafo_ia.paths import graph_dir

REF_PREFIX = "refs/grafo/sync/"
ATTR = "last_synced_blob"


def _git(root: Path, *args: str, input: bytes | None = None) -> subprocess.CompletedProcess | None:
    from grafo_ia.commands import hooks

    if not hooks.git_available() or not hooks.nested_ok(root):
        return None
    g = graph_dir(root)
    try:
        return subprocess.run(["git", *args], cwd=str(g), input=input, capture_output=True, env=hooks.git_env(g))
    except OSError:
        return None


def save(root: Path, data: bytes) -> str | None:
    """Guarda `data` y devuelve el id del blob, o None si no hay dónde."""
    r = _git(root, "hash-object", "-w", "--no-filters", "--stdin", input=data)
    if r is None or r.returncode != 0:
        return None
    blob = r.stdout.decode("ascii", errors="replace").strip()
    r = _git(root, "update-ref", REF_PREFIX + blob, blob)
    return blob if r is not None and r.returncode == 0 else None


def release(root: Path, graph: Graph, blob: str | None) -> None:
    """Suelta la ref de `blob` si ya ningún nodo la usa."""
    if blob and not any(n.get(ATTR) == blob for n in graph.nodes.values()):
        _git(root, "update-ref", "-d", REF_PREFIX + blob)


def load(root: Path, blob: str) -> bytes | None:
    r = _git(root, "cat-file", "blob", blob)
    return r.stdout if r is not None and r.returncode == 0 else None
