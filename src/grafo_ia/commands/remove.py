"""`graph remove <ruta>`: saca del grafo un archivo o una carpeta completa.

Solo toca el grafo (nodos, aristas y gemelos), nunca el código real. Barrido en
dos capas: (1) JSON: nodos bajo la ruta y sus aristas; (2) texto: los `[[...]]`
de gemelos sobrevivientes que apuntaban a lo borrado se quedan solo con su
texto a mostrar. Todo se calcula antes de escribir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import graph_io
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.edges import Resolver, TwinCache, is_structural
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import Exclusion
from grafo_ia.graph_io import Graph
from grafo_ia.paths import graph_dir, is_under, project_rel, resolve_arg, twin_path
from grafo_ia.rewrite import display_text, ensure_writable, prune_empty_dirs, rewrite_links, write_text_atomic


@dataclass
class RemoveResult:
    removed: list[str] = field(default_factory=list)
    touched: dict[str, int] = field(default_factory=dict)  # gemelo -> enlaces limpiados


def nodes_under(graph: Graph, rel: str) -> set[str]:
    """Todos los nodos de código/índice cuya ruta de proyecto cae bajo `rel`."""
    out = set()
    for nid, node in graph.nodes.items():
        prel = project_rel(nid, node["tipo"])
        if prel is not None and is_under(prel, rel):
            out.add(nid)
    return out


def remove_nodes(root: Path, graph: Graph, ids: set[str], cache: TwinCache | None = None) -> RemoveResult:
    cache = cache or TwinCache(root)
    res = RemoveResult(removed=sorted(ids))
    resolver = Resolver(graph.nodes)  # con los nodos todavía presentes
    sources = set()
    for i in ids:
        sources |= graph.adj_in.get(i, set())
    sources -= ids
    new_texts: dict[str, str] = {}
    for s in sorted(sources):
        text = cache.text(s)
        doc = cache.doc(s)
        if text is None or doc is None:
            continue

        def unlink(link, s=s, doc=doc):
            if is_structural(graph, s, doc, link):
                return None  # las listas de índices las regenera populate
            target, _ = resolver.resolve(link.target, s)
            return display_text(link) if target in ids else None

        new, n = rewrite_links(text, unlink)
        if n:
            new_texts[s] = new
            res.touched[s] = n
    ensure_writable([twin_path(root, s) for s in new_texts] + [twin_path(root, i) for i in ids])
    # a partir de aquí, solo escrituras
    for s, text in new_texts.items():
        write_text_atomic(twin_path(root, s), text)
        cache.put(s, text)
    for i in sorted(ids, key=lambda x: -x.count("/")):
        if graph.tipo(i) != "codigo":  # un nodo de código no tiene documento que borrar
            p = twin_path(root, i)
            if p.is_file():
                p.unlink()
            prune_empty_dirs(p.parent, graph_dir(root))
        graph.remove_node(i)
        cache.forget(i)
    return res


def print_result(res: RemoveResult, verb: str = "eliminados") -> None:
    print(f"{verb}: {plural(len(res.removed), 'nodo')}")
    for r in res.removed:
        print(f"  - {r}")
    if res.touched:
        print(f"documentos tocados (enlaces reducidos a su texto): {len(res.touched)}")
        for s, n in sorted(res.touched.items()):
            print(f"  ~ {s} ({plural(n, 'enlace')})")


def register(sub) -> None:
    p = sub.add_parser("remove", help="saca del grafo un archivo o carpeta (no toca el código real)")
    p.add_argument("ruta")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    with graph_io.transaction(root) as graph:
        target = resolve_arg(root, graph.nodes, args.ruta, cwd_of(args))
        if target.kind == "estado":
            raise GraphError("los documentos de Estado_Proyecto no se eliminan")
        if target.node_id is None:
            raise GraphError(f"{target.rel or '.'} no está en el grafo")
        if target.rel == "":
            raise GraphError("no se puede eliminar la raíz del proyecto")
        ids = nodes_under(graph, target.rel) if target.kind == "indice" else {target.node_id}
        res = remove_nodes(root, graph, ids)
        populate(root, graph)
    print_result(res)
    code = root / target.rel
    if code.exists() and Exclusion(root).is_included(target.rel):
        print(f"[AVISO] {target.rel} sigue existiendo en el proyecto: la siguiente reconciliación "
              f"(add/init/watcher) lo regresará al grafo. Para que no vuelva, usa `graph ignore {target.rel}`.")
    return 0
