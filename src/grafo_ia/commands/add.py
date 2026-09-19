"""`graph add [<ruta>]`: la reconciliación de `init`, acotada a una carpeta.

Sin argumento toma la carpeta actual. Crea sus índices y nodos y materializa
las cáscaras (llama a `populate`), sin pedir confirmación de exclusiones.
En la raíz converge con `init`.
"""

from __future__ import annotations

from grafo_ia import graph_io
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.errors import GraphError
from grafo_ia.paths import GRAPH_DIR, to_rel
from grafo_ia.reconciliation import reconcile, summary


def register(sub) -> None:
    p = sub.add_parser("add", help="agrega (reconcilia) una carpeta o archivo al grafo")
    p.add_argument("ruta", nargs="?", default=".", help="por defecto, la carpeta actual")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    scope = to_rel(root, args.ruta, cwd_of(args))
    if scope == GRAPH_DIR or scope.startswith(GRAPH_DIR + "/"):
        raise GraphError("los comandos reciben rutas del proyecto, no de .graph")
    with graph_io.transaction(root) as graph:
        changes = reconcile(root, graph, scope)
        pop = populate(root, graph, scope)
    print(summary(changes))
    excluded = changes.scan.excluded if changes.scan else []
    if scope and excluded and excluded[0][0] == scope:
        print(f"[AVISO] {scope} está excluido ({excluded[0][1]})")
    for rel, reason in changes.skipped:
        print(f"[AVISO] se omitió {rel}: {reason}")
    for old, new in changes.moved.items():
        print(f"  movido: {old} -> {new}")
    print(f"populate: {plural(len(pop.created), 'archivo creado', 'archivos creados')}")
    return 0
