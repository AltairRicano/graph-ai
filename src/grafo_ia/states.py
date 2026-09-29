"""Estados de sincronía de los nodos de código y las listas de `graph incomplete`.

El estado nunca se guarda: se calcula al vuelo comparando hash y filesystem.
- huérfano: el código ya no existe (y el nodo sigue en el grafo)
- faltante: el gemelo no existe o está vacío (sin contar frontmatter)
- desactualizado: el hash actual no coincide con `last_synced_hash`
- ok: todo lo demás
`incomplete`, `status` y `pre-commit` usan `report()`, así los números cuadran.
Con `check_symbols=True` además cruza funciones del código con secciones del gemelo
(`desalineados`); es un aviso aparte, no un estado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from grafo_ia import parser, symbols
from grafo_ia.edges import Resolver, TwinCache, scan_links
from grafo_ia.graph_io import Graph
from grafo_ia.hashing import hash_file
from grafo_ia.paths import is_estado, is_under, project_rel

OK = "ok"
DESACTUALIZADO = "desactualizado"
FALTANTE = "faltante"
HUERFANO = "huérfano"


@dataclass
class PendingRef:
    source: str
    line: int  # 1-based
    link: str
    reason: str


@dataclass
class Report:
    ok: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    desactualizados: list[str] = field(default_factory=list)
    pendientes: list[PendingRef] = field(default_factory=list)
    huerfanos: list[str] = field(default_factory=list)
    ambiguos: list[PendingRef] = field(default_factory=list)
    sin_alias: list[PendingRef] = field(default_factory=list)
    desalineados: list[symbols.Alignment] = field(default_factory=list)


def twin_has_content(cache: TwinCache, node_id: str) -> bool:
    text = cache.text(node_id)
    return text is not None and not parser.is_empty(text)


def code_state(root: Path, node: dict, cache: TwinCache, hasher: Callable[[str], str | None] | None = None) -> str:
    """`hasher(rel)` permite hashear otra versión del código (lo staged en pre-commit)."""
    rel = node["id"][:-3]
    code = root / rel
    if hasher is None and not code.is_file():
        return HUERFANO
    if not twin_has_content(cache, node["id"]):
        return FALTANTE
    current = hasher(rel) if hasher else hash_file(code)
    if current is None:
        return HUERFANO
    if current != node.get("last_synced_hash"):
        return DESACTUALIZADO
    return OK


def _in_scope(rel: str | None, scopes: list[str] | None) -> bool:
    if scopes is None:
        return True
    if rel is None:
        return False
    return any(is_under(rel, s) for s in scopes)


def alignment(root: Path, rel: str, cache: TwinCache) -> symbols.Alignment | None:
    """Cruce funciones/secciones de un archivo con gemelo escrito (None si cuadra o no aplica)."""
    doc = cache.doc(rel + ".md")
    if doc is None or not symbols.supported(rel):
        return None
    try:
        code = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return symbols.align(rel, code, doc)


def report(root: Path, graph: Graph, scopes: list[str] | None = None, cache: TwinCache | None = None,
           links: bool = True, check_symbols: bool = False) -> Report:
    cache = cache or TwinCache(root)
    rep = Report()
    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        if node["tipo"] != "codigo":
            continue
        rel = node_id[:-3]
        if not _in_scope(rel, scopes):
            continue
        state = code_state(root, node, cache)
        {OK: rep.ok, FALTANTE: rep.faltantes, DESACTUALIZADO: rep.desactualizados, HUERFANO: rep.huerfanos}[state].append(rel)
        if check_symbols and state in (OK, DESACTUALIZADO):
            a = alignment(root, rel, cache)
            if a is not None:
                rep.desalineados.append(a)
    if links:
        resolver = Resolver(graph.nodes)
        for node_id in sorted(graph.nodes):
            node = graph.nodes[node_id]
            rel = project_rel(node_id, node["tipo"])
            if scopes is not None and (is_estado(node_id) or not _in_scope(rel, scopes)):
                continue
            scan = scan_links(graph, resolver, cache, node_id)
            for link, reason in scan.pending:
                rep.pendientes.append(PendingRef(node_id, link.line + 1, link.raw, reason))
            for link, cands in scan.ambiguous:
                rep.ambiguos.append(PendingRef(node_id, link.line + 1, link.raw, "ambiguo: " + ", ".join(cands)))
            for link in scan.no_alias:
                rep.sin_alias.append(PendingRef(node_id, link.line + 1, link.raw, "sin texto a mostrar"))
    return rep
