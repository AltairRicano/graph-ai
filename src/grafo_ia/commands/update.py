"""`graph update <ruta>...`: confirma sincronía de forma consciente.

Código: exige código existente y gemelo con contenido; guarda el hash actual
como `last_synced_hash`, una instantánea del código para `graph diff`
(`last_synced_blob`, si hay git) y regenera las aristas del gemelo.
Documento de Estado_Proyecto (`Estado_Proyecto/Plan.md`): solo regenera aristas.
En ambos casos mueve `fecha_actualizacion` del header (frontmatter) a hoy; las
fechas de cada sección son independientes y no se tocan.
Acepta varias rutas y las valida todas antes de confirmar ninguna. Carpetas
no: confirmar una carpeta daría por buenos gemelos que nadie revisó. Si las
funciones del código no cuadran con los `###` de `## Funciones`, avisa (no bloquea).
"""

from __future__ import annotations

from pathlib import Path

from grafo_ia import graph_io, snapshots, templates, trivial
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.edges import Resolver, TwinCache, regenerate
from grafo_ia.errors import GraphError
from grafo_ia.graph_io import Graph
from grafo_ia.hashing import hash_bytes
from grafo_ia.paths import GRAPH_DIR, Target, resolve_arg, twin_path
from grafo_ia.rewrite import write_text_atomic
from grafo_ia.states import alignment, twin_has_content


def register(sub) -> None:
    p = sub.add_parser("update", help="confirma que el gemelo está al día (guarda el hash y regenera aristas)")
    p.add_argument("rutas", nargs="+", metavar="ruta", help="uno o más archivos o documentos de Estado_Proyecto")
    p.set_defaults(func=run)


def confirm(root: Path, graph: Graph, cache: TwinCache, t: Target, resolver: Resolver | None = None) -> tuple[str | None, set[str], set[str]]:
    """Guarda hash e instantánea (solo código) y regenera aristas. -> (hash, aristas nuevas, aristas quitadas)."""
    h = None
    if t.kind == "codigo":
        data = (root / t.rel).read_bytes()
        h = hash_bytes(data)
        node = graph.nodes[t.node_id]
        node["last_synced_hash"] = h
        old_blob = node.pop(snapshots.ATTR, None)
        blob = snapshots.save(root, data)
        if blob:
            node[snapshots.ATTR] = blob
        if old_blob != blob:
            snapshots.release(root, graph, old_blob)
        graph.dirty = True
    added, removed = regenerate(graph, cache, t.node_id, resolver)
    return h, added, removed


def _check(root: Path, cache: TwinCache, t: Target, trivial_rules: list[str]) -> bool:
    """Valida un blanco sin escribir nada. -> False si no hay nada que confirmar (trivial vacío)."""
    if t.node_id is None:
        raise GraphError(f"{t.rel or '.'} no está en el grafo (usa `graph add`)")
    if t.kind == "indice":
        raise GraphError(f"{t.rel or '.'}: update no acepta carpetas, la sincronía se confirma archivo por archivo "
                         f"(puedes pasar varios archivos a la vez)")
    if t.kind == "codigo":
        if not (root / t.rel).is_file():
            raise GraphError(f"{t.rel} ya no existe: su gemelo es huérfano (usa `graph prune` o `graph remove`)")
        if not twin_has_content(cache, t.node_id):
            if trivial.is_trivial(trivial_rules, t.rel):
                return False
            raise GraphError(f"el gemelo no existe o está vacío, créalo primero: {GRAPH_DIR}/{t.node_id}")
    return True


def run(args) -> int:
    root = root_of(args)
    cache = TwinCache(root)
    trivial_rules = trivial.load_rules(root)
    results = []
    with graph_io.transaction(root) as graph:
        targets = []
        for ruta in dict.fromkeys(args.rutas):
            t = resolve_arg(root, graph.nodes, ruta, cwd_of(args))
            targets.append((t, _check(root, cache, t, trivial_rules)))
        for t, pending in targets:
            if not pending:
                results.append((t, None, set(), set()))
                continue
            h, added, removed = confirm(root, graph, cache, t)
            text = cache.text(t.node_id)
            if text is not None:
                touched = templates.touch_updated(text)
                if touched != text:
                    write_text_atomic(twin_path(root, t.node_id), touched)
            results.append((t, h, added, removed))
    fresh = TwinCache(root)
    for t, h, added, removed in results:
        if t.kind == "codigo" and h is None:
            print(f"{t.rel}: trivial sin contenido, nada que confirmar")
            continue
        if t.kind == "codigo":
            print(f"{t.rel}: sincronizado ({h[:12]})")
        else:
            print(f"{t.node_id}: aristas regeneradas")
        for x in sorted(added):
            print(f"  + {x}")
        for x in sorted(removed):
            print(f"  - {x}")
        if t.kind == "codigo":
            a = alignment(root, t.rel, fresh)
            if a is not None:
                print(f"[AVISO] el gemelo no cuadra con las funciones del código ({a.describe()})")
    return 0
