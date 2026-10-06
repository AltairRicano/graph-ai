"""`graph prune [<ruta>]`: `remove` en lote, solo sobre huérfanos confirmados.

Borra el nodo, sus aristas y el `.md` de cada índice huérfano (carpeta que ya no
existe), con el mismo barrido de dos capas que `remove`, y saca los nodos de
archivos de código que ya no existen. Nunca toca los "pendientes por crear".
"""

from __future__ import annotations

from grafo_ia import graph_io
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.commands.remove import print_result, remove_nodes
from grafo_ia.paths import MASTER_ID, is_estado, is_under, project_rel, to_rel


def register(sub) -> None:
    p = sub.add_parser("prune", help="elimina los índices huérfanos (carpetas que ya no existen) y los nodos de archivos borrados")
    p.add_argument("ruta", nargs="?", help="acota a esta ruta (por defecto, todo)")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    scope = to_rel(root, args.ruta, cwd_of(args)) if args.ruta else ""
    with graph_io.transaction(root) as graph:
        ids = set()
        for nid, node in graph.nodes.items():
            if is_estado(nid) or nid == MASTER_ID:
                continue
            rel = project_rel(nid, node["tipo"])
            if not is_under(rel, scope):
                continue
            gone = not (root / rel).is_dir() if node["tipo"] == "indice" else not (root / rel).is_file()
            if gone:
                ids.add(nid)
        if not ids:
            print("sin huérfanos")
            return 0
        res = remove_nodes(root, graph, ids)
        populate(root, graph)
    print_result(res, "podados")
    return 0
