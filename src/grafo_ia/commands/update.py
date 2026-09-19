"""`graph update <ruta>`: confirma sincronía de forma consciente.

Código: exige código existente y gemelo con contenido; guarda el hash actual
como `last_synced_hash` y regenera las aristas del gemelo.
Documento de Estado_Proyecto (`Estado_Proyecto/Plan.md`): solo regenera aristas.
En ambos casos mueve `fecha_actualizacion` del header (frontmatter) a hoy; las
fechas de cada sección son independientes y no se tocan.
Carpetas no: se confirma archivo por archivo.
"""

from __future__ import annotations

from grafo_ia import graph_io, templates
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.edges import TwinCache, regenerate
from grafo_ia.errors import GraphError
from grafo_ia.hashing import hash_file
from grafo_ia.paths import GRAPH_DIR, resolve_arg, twin_path
from grafo_ia.rewrite import write_text_atomic
from grafo_ia.states import twin_has_content


def register(sub) -> None:
    p = sub.add_parser("update", help="confirma que el gemelo está al día (guarda el hash y regenera aristas)")
    p.add_argument("ruta")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    cache = TwinCache(root)
    with graph_io.transaction(root) as graph:
        t = resolve_arg(root, graph.nodes, args.ruta, cwd_of(args))
        if t.node_id is None:
            raise GraphError(f"{t.rel or '.'} no está en el grafo (usa `graph add`)")
        if t.kind == "indice":
            raise GraphError("update no acepta carpetas: la sincronía se confirma archivo por archivo")
        if t.kind == "codigo":
            code = root / t.rel
            if not code.is_file():
                raise GraphError(f"{t.rel} ya no existe: su gemelo es huérfano (usa `graph prune` o `graph remove`)")
            if not twin_has_content(cache, t.node_id):
                raise GraphError(f"el gemelo no existe o está vacío, créalo primero: {GRAPH_DIR}/{t.node_id}")
            h = hash_file(code)
            graph.nodes[t.node_id]["last_synced_hash"] = h
            graph.dirty = True
        added, removed = regenerate(graph, cache, t.node_id)
        text = cache.text(t.node_id)
        if text is not None:
            touched = templates.touch_updated(text)
            if touched != text:
                write_text_atomic(twin_path(root, t.node_id), touched)
    if t.kind == "codigo":
        print(f"{t.rel}: sincronizado ({h[:12]})")
    else:
        print(f"{t.node_id}: aristas regeneradas")
    for x in sorted(added):
        print(f"  + {x}")
    for x in sorted(removed):
        print(f"  - {x}")
    return 0
