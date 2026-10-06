"""Motor de reconciliación: filesystem -> nodos del JSON.

Lo reutilizan `init`, `add`, `post-merge` y el Watcher. Corrido contra un JSON
vacío es la inicialización; corrido de nuevo no destruye nada:
- Nodo de código cuyo archivo desapareció: se va (no tiene documento que cuidar).
- Índice cuya carpeta desapareció: se queda si alguien le escribió contenido
  (es huérfano, lo limpia `prune`); se va si solo tenía las listas.
- Movimiento que se escapó: un nodo desaparecido cuyo `last_synced_hash`
  coincide con un solo archivo nuevo (1 a 1) se mueve con `mv`. Si no es
  1 a 1, no se adivina.
- Nodos nuevos nacen sin hash, y los enlaces que ya los esperaban
  (pendientes) se vuelven aristas.
No escribe índices nuevos: eso es trabajo de `populate`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia.edges import TwinCache, resolve_pending
from grafo_ia.exclusion import Exclusion, Scan, walk
from grafo_ia.graph_io import Graph
from grafo_ia.hashing import hash_file
from grafo_ia.paths import (
    ESTADO_DIR,
    ESTADO_DOCS,
    ESTADO_INDEX_ID,
    MASTER_ID,
    code_id,
    estado_doc_id,
    folder_id,
    folder_rel_of_index,
    graph_dir,
    is_under,
    parent_rel,
    project_rel,
    twin_path,
)
from grafo_ia.rewrite import prune_empty_dirs
from grafo_ia.states import index_has_content


@dataclass
class Changes:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    moved: dict[str, str] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (ruta, razón)
    new_edges: list[tuple[str, str]] = field(default_factory=list)
    scan: Scan | None = None

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.moved)


def fixed_nodes() -> dict[str, str]:
    """Nodos que existen siempre: el maestro y Estado_Proyecto con sus documentos."""
    nodes = {MASTER_ID: "indice", ESTADO_INDEX_ID: "indice"}
    for name, tipo in ESTADO_DOCS.items():
        nodes[estado_doc_id(name)] = tipo
    return nodes


def expected_nodes(scan: Scan, scope: str, changes: Changes) -> dict[str, str]:
    expected: dict[str, str] = {}
    reserved = set(fixed_nodes())
    # cadena de ancestros del alcance
    cur = parent_rel(scope) if scope else ""
    while cur:
        expected[folder_id(cur)] = "indice"
        cur = parent_rel(cur)
    for d in scan.dirs:
        if d.split("/")[0] == ESTADO_DIR:
            changes.skipped.append((d, f"'{ESTADO_DIR}' está reservado para el grafo"))
            continue
        expected[folder_id(d)] = "indice"
    for f in scan.files:
        if f.split("/")[0] == ESTADO_DIR:
            continue
        cid = code_id(f)
        if cid in reserved or cid in expected:
            changes.skipped.append((f, f"su ruta choca con el índice {cid}"))
            continue
        expected[cid] = "codigo"
    # un archivo `a/a.md` (si alguien dejó de excluir los .md) choca con el índice de la carpeta `a`
    for f in scan.files:
        cid = code_id(f)
        if expected.get(cid) == "codigo" and cid == folder_id(parent_rel(f)):
            del expected[cid]
            changes.skipped.append((f, "su ruta choca con el índice de su carpeta"))
    return expected


def _existing_in_scope(graph: Graph, scope: str) -> set[str]:
    out = set()
    for nid, node in graph.nodes.items():
        rel = project_rel(nid, node["tipo"])
        if rel is None or rel == "":
            continue
        if is_under(rel, scope):
            out.add(nid)
    return out


def _detect_moves(root: Path, graph: Graph, vanished: set[str], new: dict[str, str], cache: TwinCache) -> dict[str, str]:
    """Movimientos de archivo 1 a 1 por hash, más las carpetas que se movieron completas."""
    by_hash_old: dict[str, list[str]] = {}
    for nid in vanished:
        node = graph.nodes[nid]
        if node["tipo"] == "codigo" and node.get("last_synced_hash"):
            by_hash_old.setdefault(node["last_synced_hash"], []).append(nid)
    if not by_hash_old:
        return {}
    by_hash_new: dict[str, list[str]] = {}
    for nid, tipo in new.items():
        if tipo != "codigo":
            continue
        try:
            h = hash_file(root / nid)
        except OSError:
            continue
        if h in by_hash_old:
            by_hash_new.setdefault(h, []).append(nid)
    moves = {}
    for h, olds in by_hash_old.items():
        news = by_hash_new.get(h, [])
        if len(olds) == 1 and len(news) == 1:
            moves[olds[0]] = news[0]
    # carpetas: si todo lo movido de D fue a N con la misma ruta relativa, D -> N
    for nid in vanished:
        if graph.nodes[nid]["tipo"] != "indice":
            continue
        d = folder_rel_of_index(nid)
        dests = set()
        for old, newid in list(moves.items()):
            if graph.nodes[old]["tipo"] != "codigo":
                continue
            orel, nrel = old, newid
            if is_under(orel, d) and orel != d:
                suffix = orel[len(d):]
                if not nrel.endswith(suffix):
                    dests.add(None)
                else:
                    dests.add(nrel[: len(nrel) - len(suffix)])
        if len(dests) == 1 and None not in dests:
            n = dests.pop()
            if new.get(folder_id(n)) == "indice":
                moves[nid] = folder_id(n)
    return moves


def reconcile(root: Path, graph: Graph, scope: str = "", exclusion: Exclusion | None = None, cache: TwinCache | None = None) -> Changes:
    exclusion = exclusion or Exclusion(root)
    cache = cache or TwinCache(root)
    changes = Changes()
    scan = walk(root, exclusion, scope)
    changes.scan = scan
    expected = expected_nodes(scan, scope, changes)
    for nid, tipo in fixed_nodes().items():
        if nid not in graph.nodes:
            expected[nid] = tipo

    existing = _existing_in_scope(graph, scope)
    vanished = {n for n in existing if n not in expected}
    new = {n: t for n, t in expected.items() if n not in graph.nodes}

    # 1. movimientos que el Watcher no vio
    moves = _detect_moves(root, graph, vanished, new, cache)
    if moves:
        from grafo_ia.commands.mv import move_nodes, validate_mapping

        try:
            validate_mapping(root, graph, moves)
        except Exception:
            moves = {}
        if moves:
            move_nodes(root, graph, moves, cache)
            changes.moved = dict(moves)
            vanished -= set(moves)
            for dst in moves.values():
                new.pop(dst, None)

    # 2. desaparecidos: el código se va; un índice con contenido escrito queda huérfano
    to_remove = {nid for nid in vanished if graph.nodes[nid]["tipo"] == "codigo"}
    gone = [nid for nid in vanished if graph.nodes[nid]["tipo"] == "indice"]
    kept = [folder_rel_of_index(nid) for nid in gone if index_has_content(cache, nid)]
    for nid in sorted(gone):
        d = folder_rel_of_index(nid)
        if d in kept:
            changes.orphans.append(nid)
        elif not any(is_under(k, d) for k in kept):  # el ancestro de un huérfano se queda para no dejarlo sin padre
            to_remove.add(nid)
    for nid in sorted(to_remove, key=lambda x: -x.count("/")):
        if graph.nodes[nid]["tipo"] != "codigo":
            p = twin_path(root, nid)
            if p.is_file():
                p.unlink()
            prune_empty_dirs(p.parent, graph_dir(root))
        graph.remove_node(nid)
        cache.forget(nid)
        changes.removed.append(nid)

    # 3. nuevos
    for nid in sorted(new):
        graph.add_node(nid, new[nid])
        changes.added.append(nid)
    changes.new_edges = resolve_pending(graph, cache, list(new) + list(changes.moved.values()))
    return changes


def summary(changes: Changes) -> str:
    parts = [f"{len(changes.added)} nuevos", f"{len(changes.removed)} quitados"]
    if changes.moved:
        parts.append(f"{len(changes.moved)} movidos")
    if changes.orphans:
        parts.append(f"{len(changes.orphans)} huérfanos")
    return "reconciliación: " + ", ".join(parts)
