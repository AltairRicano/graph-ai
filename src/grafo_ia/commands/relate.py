"""`graph relate <origen> <destino> [--add r] [--remove r]`: edita `relaciones`.

1. Solo aristas que ya existen (el gemelo de origen menciona al destino).
2. Solo tipos de la taxonomía.
3. La lista nunca queda vacía.
Sin banderas, solo muestra la lista.
"""

from __future__ import annotations

from grafo_ia import graph_io
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.errors import GraphError
from grafo_ia.graph_io import TAXONOMY
from grafo_ia.paths import resolve_arg


def register(sub) -> None:
    p = sub.add_parser("relate", help="muestra o edita las relaciones de una arista")
    p.add_argument("origen")
    p.add_argument("destino")
    p.add_argument("--add", action="append", default=[], metavar="RELACIÓN")
    p.add_argument("--remove", action="append", default=[], metavar="RELACIÓN")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    cwd = cwd_of(args)
    for r in args.add + args.remove:
        if r not in TAXONOMY:
            raise GraphError(f"'{r}' no está en la taxonomía: {', '.join(TAXONOMY)}")
    with graph_io.transaction(root) as graph:
        src = resolve_arg(root, graph.nodes, args.origen, cwd)
        dst = resolve_arg(root, graph.nodes, args.destino, cwd)
        for t, arg in ((src, args.origen), (dst, args.destino)):
            if t.node_id is None:
                raise GraphError(f"{arg} no está en el grafo")
        rels = graph.relations(src.node_id, dst.node_id)
        if rels is None:
            raise GraphError(f"no existe la arista {src.node_id} -> {dst.node_id}: el documento de origen tiene que "
                             f"mencionar al destino con [[...]] (y regenerarse con `graph update`)")
        new = list(rels)
        for r in args.add:
            if r not in new:
                new.append(r)
        new = [r for r in new if r not in args.remove]
        if not new:
            raise GraphError("la lista de relaciones no puede quedar vacía")
        if new != rels:
            graph.set_edge(src.node_id, dst.node_id, new)
    print(f"{src.node_id} -> {dst.node_id}: {', '.join(new)}")
    return 0
