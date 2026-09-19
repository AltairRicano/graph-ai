"""`graph prune [<ruta>]`: `remove` en lote, solo sobre huérfanos confirmados.

Borra el nodo, sus aristas y el `.md` de cada gemelo huérfano (código que ya no
existe), con el mismo barrido de dos capas que `remove`. También quita los
índices de carpetas que ya no existen y se quedan sin código. Nunca toca los
"pendientes por crear".
"""

from __future__ import annotations

from grafo_ia import graph_io, states
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.commands.remove import print_result, remove_nodes
from grafo_ia.paths import code_id, folder_rel_of_index, is_estado, is_under, to_rel, MASTER_ID


def register(sub) -> None:
    p = sub.add_parser("prune", help="elimina los gemelos huérfanos (código que ya no existe)")
    p.add_argument("ruta", nargs="?", help="acota a esta ruta (por defecto, todo)")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    scope = to_rel(root, args.ruta, cwd_of(args)) if args.ruta else ""
    with graph_io.transaction(root) as graph:
        rep = states.report(root, graph, [scope] if scope else None, links=False)
        ids = {code_id(r) for r in rep.huerfanos}
        alive = [n[:-3] for n, node in graph.nodes.items() if node["tipo"] == "codigo" and n not in ids]
        for nid, node in graph.nodes.items():
            if node["tipo"] != "indice" or nid == MASTER_ID or is_estado(nid):
                continue
            d = folder_rel_of_index(nid)
            if is_under(d, scope) and not (root / d).is_dir() and not any(is_under(r, d) for r in alive):
                ids.add(nid)
        if not ids:
            print("sin huérfanos")
            return 0
        res = remove_nodes(root, graph, ids)
        populate(root, graph)
    print_result(res, "podados")
    return 0
