"""`graph diff [<ruta>...] [--symbols]`: qué cambió en el código desde el último `graph update`.

Compara la instantánea que guardó `update` (ver `snapshots`) contra el archivo
actual y, si el lenguaje se chequea (ver `symbols`), dice qué funciones tocó
el cambio: son las secciones del gemelo a revisar. Sin rutas, recorre todos los
desactualizados; una carpeta acota a los desactualizados que tiene adentro.
Solo lee: nunca toca el grafo ni el código. Siempre sale con 0.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from grafo_ia import graph_io, snapshots, states, symbols
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.edges import TwinCache
from grafo_ia.errors import GraphError
from grafo_ia.graph_io import Graph
from grafo_ia.paths import is_under, resolve_arg


def register(sub) -> None:
    p = sub.add_parser("diff", help="cambios del código desde el último update y secciones a revisar")
    p.add_argument("rutas", nargs="*", help="archivos o carpetas (por defecto, todos los desactualizados)")
    p.add_argument("--symbols", action="store_true", help="solo las secciones a revisar, sin el diff")
    p.set_defaults(func=run)


def _targets(root: Path, graph: Graph, cache: TwinCache, args) -> list[tuple[str, bool]]:
    """(ruta, pedida explícitamente) de cada archivo a comparar."""
    def stale(scope: str) -> list[str]:
        out = []
        for nid in sorted(graph.nodes):
            node = graph.nodes[nid]
            if node["tipo"] == "codigo" and is_under(nid[:-3], scope):
                if states.code_state(root, node, cache) == states.DESACTUALIZADO:
                    out.append(nid[:-3])
        return out

    if not args.rutas:
        return [(r, False) for r in stale("")]
    found: list[tuple[str, bool]] = []
    for arg in args.rutas:
        t = resolve_arg(root, graph.nodes, arg, cwd_of(args))
        if t.node_id is None:
            raise GraphError(f"{t.rel or '.'} no está en el grafo")
        if t.kind == "codigo":
            found.append((t.rel, True))
        elif t.kind == "indice":
            found += [(r, False) for r in stale(t.rel)]
        else:
            raise GraphError(f"{t.rel}: los documentos de Estado_Proyecto no tienen código que comparar")
    return list(dict.fromkeys(found))


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def show(root: Path, graph: Graph, cache: TwinCache, rel: str, explicit: bool, only_symbols: bool) -> None:
    node = graph.nodes[rel + ".md"]
    state = states.code_state(root, node, cache)
    if state == states.HUERFANO:
        print(f"==> {rel} (huérfano) <==\nel código ya no existe")
        return
    if state == states.OK:
        if explicit:
            print(f"==> {rel} (ok) <==\nsin cambios desde el último `graph update`")
        return
    blob = node.get(snapshots.ATTR)
    print(f"==> {rel} ({state}) <==")
    if not blob:
        why = ("nunca se confirmó con `graph update`" if not node.get("last_synced_hash")
               else "el último `graph update` es anterior a las instantáneas o no hay git en .graph")
        print(f"sin instantánea: {why}; compara con `git diff`")
        return
    old = snapshots.load(root, blob)
    if old is None:
        print(f"no se pudo leer la instantánea {blob[:12]} del repo de .graph")
        return
    old_text, new_text = _text(old), _text((root / rel).read_bytes())
    t = symbols.touched(rel, old_text, new_text)
    if t is not None:
        print(f"secciones a revisar: {t.describe()}")
    if only_symbols:
        return
    lines = difflib.unified_diff(
        old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile=f"a/{rel} (último update)", tofile=f"b/{rel} (actual)",
    )
    for line in lines:
        print(line if line.endswith("\n") else line + "\n", end="")


def run(args) -> int:
    root = root_of(args)
    graph = graph_io.load(root)
    cache = TwinCache(root)
    targets = _targets(root, graph, cache, args)
    if not targets:
        print("nada desactualizado")
        return 0
    for i, (rel, explicit) in enumerate(targets):
        if i:
            print()
        show(root, graph, cache, rel, explicit, args.symbols)
    return 0
