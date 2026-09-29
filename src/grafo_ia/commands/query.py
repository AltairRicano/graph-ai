"""Consultas de solo lectura: get (con expansión por secciones), neighbors, subgraph, search, status.

Comparten la carga del JSON (sin lock: la escritura es atómica) y la
resolución de rutas/secciones.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field

from grafo_ia import graph_io, parser, states
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.edges import Resolver, TwinCache, is_structural
from grafo_ia.errors import GraphError
from grafo_ia.graph_io import Graph
from grafo_ia.paths import resolve_arg


@dataclass
class Neighbor:
    node_id: str
    relaciones: list[str]
    sections: set = field(default_factory=set)  # secciones del otro nodo (None = completo)
    via: set = field(default_factory=set)  # headings del gemelo origen donde vive el enlace


def _load_target(args, allow_section=True):
    root = root_of(args)
    graph = graph_io.load(root)
    t = resolve_arg(root, graph.nodes, args.ruta, cwd_of(args), allow_section=allow_section)
    if t.node_id is None:
        raise GraphError(f"{t.rel or '.'} no está en el grafo")
    return root, graph, t


def neighbors_of(graph: Graph, cache: TwinCache, node_id: str, section: str | None = None) -> tuple[list[Neighbor], list[Neighbor]]:
    resolver = Resolver(graph.nodes)
    out: dict[str, Neighbor] = {}
    doc = cache.doc(node_id)
    if doc is not None:
        lo, hi = parser.section_range(doc, section) if section else (0, len(doc.lines))
        for link in parser.links(doc):
            if not (lo <= link.line < hi) or is_structural(graph, node_id, doc, link):
                continue
            tid, _ = resolver.resolve(link.target, node_id)
            if tid is None or tid == node_id or graph.relations(node_id, tid) is None:
                continue
            nb = out.setdefault(tid, Neighbor(tid, graph.relations(node_id, tid)))
            nb.sections.add(link.section)
            if link.heading is not None:
                nb.via.add(doc.headings[link.heading].text)
    inc: dict[str, Neighbor] = {}
    target_heading = None
    if section and doc is not None:
        target_heading = parser.find_section(doc, section)
    for s in sorted(graph.adj_in.get(node_id, set())):
        sdoc = cache.doc(s)
        rels = graph.relations(s, node_id) or []
        if section is None:
            nb = Neighbor(s, rels)
            if sdoc is not None:
                for link in parser.links(sdoc):
                    if resolver.resolve(link.target, s)[0] == node_id and link.heading is not None:
                        nb.sections.add(sdoc.headings[link.heading].text)
            inc[s] = nb
            continue
        if sdoc is None:
            continue
        for link in parser.links(sdoc):
            if not link.section or resolver.resolve(link.target, s)[0] != node_id:
                continue
            try:
                h = parser.find_section(doc, link.section)
            except GraphError:
                continue
            if target_heading is not None and h.line == target_heading.line:
                nb = inc.setdefault(s, Neighbor(s, rels))
                if link.heading is not None:
                    nb.sections.add(sdoc.headings[link.heading].text)
    return sorted(out.values(), key=lambda n: n.node_id), sorted(inc.values(), key=lambda n: n.node_id)


def _fmt_sections(secs) -> str:
    named = sorted(s for s in secs if s)
    return ("#" + ", #".join(named)) if named else ""


# ---- get ---------------------------------------------------------------------
def _candidates(out: list[Neighbor], inc: list[Neighbor]):
    """(nodo, sección o None, dirección, relaciones) de cada vecino, salientes primero."""
    for nb in out:
        named = sorted(s for s in nb.sections if s)
        for s in (named if None not in nb.sections and named else [None]):
            yield nb.node_id, s, "saliente", nb.relaciones
    for nb in inc:
        named = sorted(s for s in nb.sections if s)
        for s in (named or [None]):
            yield nb.node_id, s, "entrante", nb.relaciones


def _span(doc: parser.Doc, section: str | None) -> tuple[int, int]:
    return parser.section_range(doc, section) if section else (0, len(doc.lines))


def expand(graph: Graph, cache: TwinCache, start: str, section: str | None, depth: int):
    """Recorrido a lo ancho por secciones, hasta `depth` saltos.

    Regla de bucle: un salto se corta (sin cortar las demás ramas) si aterriza
    en una sección ya leída (o contenida en una ya leída) o si apunta al archivo
    completo de un gemelo ya visitado. Ir y volver entre dos archivos por
    secciones distintas sí se sigue. -> ([(nodo, sección, dirección, relaciones,
    salto, texto)], saltos omitidos)
    """
    visited: dict[str, list[tuple[int, int]]] = {start: [_span(cache.doc(start), section)]}
    queue = deque([(start, section, 0)])
    shown, omitted = [], 0
    while queue:
        node, sec, dist = queue.popleft()
        if dist >= depth:
            continue
        out, inc = neighbors_of(graph, cache, node, sec)
        for nid, s, direction, rels in _candidates(out, inc):
            doc = cache.doc(nid)
            if doc is None:
                continue
            try:
                lo, hi = _span(doc, s)
            except GraphError:
                continue
            seen = visited.get(nid)
            if seen is not None and (s is None or any(a <= lo and hi <= b for a, b in seen)):
                omitted += 1
                continue
            visited.setdefault(nid, []).append((lo, hi))
            shown.append((nid, s, direction, rels, dist + 1, "".join(doc.lines[lo:hi])))
            queue.append((nid, s, dist + 1))
    return shown, omitted


def run_get(args) -> int:
    root, graph, t = _load_target(args)
    cache = TwinCache(root)
    doc = cache.doc(t.node_id)
    if doc is None:
        raise GraphError(f"el gemelo de {t.rel or t.node_id} todavía no existe (usa `graph populate`)")
    content = parser.section_text(doc, t.section) if t.section else doc.text
    print(f"==> {t.node_id}{'#' + t.section if t.section else ''} <==")
    print(content.rstrip("\n"))
    depth = args.depth if args.depth is not None else (1 if args.expand else 0)
    if depth < 0:
        raise GraphError("--depth no puede ser negativo")
    if depth == 0:
        return 0
    shown, omitted = expand(graph, cache, t.node_id, t.section, depth)
    for nid, s, direction, rels, dist, body in shown:
        hop = f", salto {dist}" if depth > 1 else ""
        print(f"\n==> {nid}{'#' + s if s else ''} ({direction}: {', '.join(rels)}{hop}) <==")
        print(body.rstrip("\n"))
    if omitted:
        print(f"\n-- {plural(omitted, 'salto omitido', 'saltos omitidos')}: ya leídos en este recorrido")
    return 0


# ---- neighbors ---------------------------------------------------------------
def _reject_folder(graph: Graph, t, command: str) -> None:
    if graph.tipo(t.node_id) == "indice":
        shown = t.rel or "."
        raise GraphError(f"{shown}: este elemento es una carpeta; `{command}` no aplica a carpetas. "
                         f"Usa `graph get {shown}` para ver lo que contiene")


def run_neighbors(args) -> int:
    root, graph, t = _load_target(args)
    _reject_folder(graph, t, "neighbors")
    cache = TwinCache(root)
    out, inc = neighbors_of(graph, cache, t.node_id, t.section)
    if not args.incoming:
        print(f"salientes ({len(out)})")
        for nb in out:
            print(f"  -> {nb.node_id}{(' ' + _fmt_sections(nb.sections)) if _fmt_sections(nb.sections) else ''} [{', '.join(nb.relaciones)}]")
    if not args.outgoing:
        print(f"entrantes ({len(inc)})")
        for nb in inc:
            where = f" (en: {', '.join(sorted(nb.sections))})" if nb.sections else ""
            print(f"  <- {nb.node_id}{where} [{', '.join(nb.relaciones)}]")
    return 0


# ---- subgraph ----------------------------------------------------------------
def subgraph(graph: Graph, start: str, depth: int, direction: str = "both") -> dict[str, int]:
    seen = {start: 0}
    q = deque([start])
    while q:
        cur = q.popleft()
        if seen[cur] >= depth:
            continue
        nxt = set()
        if direction in ("both", "out"):
            nxt |= graph.adj_out.get(cur, set())
        if direction in ("both", "in"):
            nxt |= graph.adj_in.get(cur, set())
        for n in sorted(nxt):
            if n not in seen:
                seen[n] = seen[cur] + 1
                q.append(n)
    return seen


def run_subgraph(args) -> int:
    root, graph, t = _load_target(args, allow_section=False)
    _reject_folder(graph, t, "subgraph")
    if args.depth < 0:
        raise GraphError("--depth no puede ser negativo")
    seen = subgraph(graph, t.node_id, args.depth, args.direction)
    edges = [(s, d) for (s, d) in sorted(graph.edges) if s in seen and d in seen]
    if args.json:
        data = {
            "directed": True,
            "multigraph": False,
            "graph": {"raiz": t.node_id, "depth": args.depth},
            "nodes": [dict(graph.nodes[n], distancia=seen[n]) for n in sorted(seen, key=lambda x: (seen[x], x))],
            "links": [{"source": s, "target": d, "relaciones": graph.edges[(s, d)]} for s, d in edges],
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"nodos ({len(seen)})")
    for n in sorted(seen, key=lambda x: (seen[x], x)):
        print(f"  {seen[n]}  {n} ({graph.nodes[n]['tipo']})")
    print(f"aristas ({len(edges)})")
    for s, d in edges:
        print(f"  {s} -> {d} [{', '.join(graph.edges[(s, d)])}]")
    return 0


# ---- search ------------------------------------------------------------------
def _meta_matches(meta: dict, filters: list[tuple[str, str]]) -> bool:
    for key, value in filters:
        v = meta.get(key)
        if isinstance(v, list):
            if value not in v:
                return False
        elif str(v) != value:
            return False
    return True


def run_search(args) -> int:
    root = root_of(args)
    graph = graph_io.load(root)
    cache = TwinCache(root)
    filters = []
    for f in args.filter:
        if "=" not in f:
            raise GraphError(f"filtro inválido '{f}': usa campo=valor")
        k, v = f.split("=", 1)
        filters.append((k.strip(), v.strip()))
    if not args.query and not filters:
        raise GraphError("da un texto a buscar o al menos un --filter")
    if args.regex:
        try:
            pattern = re.compile(args.query or "", re.IGNORECASE)
        except re.error as e:
            raise GraphError(f"regex inválida: {e}")
        match = lambda line: pattern.search(line) is not None  # noqa: E731
    else:
        needle = (args.query or "").casefold()
        match = lambda line: needle in line.casefold()  # noqa: E731
    count = 0
    for node_id in sorted(graph.nodes):
        doc = cache.doc(node_id)
        if doc is None or not _meta_matches(doc.meta, filters):
            continue
        if not args.query:
            print(node_id)
            count += 1
        else:
            for i in range(doc.body_start, len(doc.lines)):
                line = doc.lines[i]
                if match(line):
                    h = doc.heading_for_line(i)
                    where = f" [#{doc.headings[h].text}]" if h is not None else ""
                    print(f"{node_id}:{i + 1}{where}: {line.strip()[:200]}")
                    count += 1
                    if count >= args.limit:
                        break
        if count >= args.limit:
            print(f"... (límite de {args.limit} resultados)")
            break
    if count == 0:
        print("sin resultados")
    return 0


# ---- status ------------------------------------------------------------------
def run_status(args) -> int:
    from grafo_ia.commands import hooks, watcher

    root = root_of(args)
    graph = graph_io.load(root)
    rep = states.report(root, graph)
    print(f"ok: {len(rep.ok)}")
    print(f"desactualizado: {len(rep.desactualizados)}")
    print(f"faltante: {len(rep.faltantes)}")
    print(f"pendiente por crear: {len(rep.pendientes)}")
    print(f"huérfano: {len(rep.huerfanos)}")
    msg = hooks.head_mismatch(root)
    if msg:
        print(f"[AVISO] {msg}")
    print(f"watcher: {watcher.describe(root)}")
    return 0


def register(sub) -> None:
    p = sub.add_parser("get", help="contenido de un gemelo o una sección")
    p.add_argument("ruta", metavar="ruta[#sección]")
    p.add_argument("--expand", action="store_true", help="incluye inline el contenido de los vecinos (un salto)")
    p.add_argument("--depth", type=int, metavar="N", help="expande hasta N saltos por secciones, sin repetir lo ya leído (implica --expand)")
    p.set_defaults(func=run_get)

    p = sub.add_parser("neighbors", help="nodos conectados (entrantes y salientes)")
    p.add_argument("ruta", metavar="ruta[#sección]")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--in", dest="incoming", action="store_true", help="solo entrantes")
    g.add_argument("--out", dest="outgoing", action="store_true", help="solo salientes")
    p.set_defaults(func=run_neighbors)

    p = sub.add_parser("subgraph", help="todo lo que hay a N saltos")
    p.add_argument("ruta")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--direction", choices=["both", "out", "in"], default="both")
    p.add_argument("--json", action="store_true", help="salida node-link (para visualización)")
    p.set_defaults(func=run_subgraph)

    p = sub.add_parser("search", help="búsqueda de texto y por frontmatter en los gemelos")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--filter", action="append", default=[], metavar="campo=valor")
    p.add_argument("--regex", action="store_true")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=run_search)

    p = sub.add_parser("status", help="resumen de una línea por estado")
    p.set_defaults(func=run_status)
