"""`graph diff [<carpeta>...]`: qué cambió en una carpeta desde la última confirmación de su índice.

Lista los archivos que entraron (`+`), salieron (`-`) y se modificaron (`~`)
respecto a lo que guardó `graph update` / `graph multiedit`. Los que entran o
salen son los que desactualizan el índice; los modificados son informativos:
decidir si el cambio altera lo que el índice dice le toca a quien lo escribió.
Sin rutas, recorre todas las carpetas con algo que reportar; un archivo pide
la carpeta que lo contiene. Solo lee: nunca toca el grafo ni el código.
Siempre sale con 0.
"""

from __future__ import annotations

from grafo_ia import graph_io, states
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.edges import TwinCache
from grafo_ia.exclusion import Exclusion, walk
from grafo_ia.paths import to_rel


def register(sub) -> None:
    p = sub.add_parser("diff", help="archivos que entraron, salieron o cambiaron en una carpeta desde que se confirmó su índice")
    p.add_argument("rutas", nargs="*", help="carpetas (por defecto, todas las que tienen cambios)")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    graph = graph_io.load(root)
    cache = TwinCache(root)
    scopes = [to_rel(root, r, cwd_of(args)) for r in args.rutas] or None
    explicit = scopes is not None and "" not in scopes
    rep = states.report(root, graph, scopes if explicit else None, cache, links=False)
    on_disk = states.disk_files(walk(root, Exclusion(root), ""))
    shown = 0
    for rel in sorted(rep.folders):
        st = rep.folders[rel]
        modified = states.modified_files(root, graph, rel, on_disk.get(rel) or [])
        if not (st.entered or st.left or modified):
            if explicit:
                extra = f": {'; '.join(st.reasons)}" if st.reasons else ""
                print(f"{st.shown} ({st.state}): sin cambios en sus archivos desde la última confirmación{extra}")
                shown += 1
            continue
        print(f"{st.shown} ({st.state})")
        for n in st.entered:
            print(f"  + {n}")
        for n in st.left:
            print(f"  - {n}")
        for n in modified:
            print(f"  ~ {n}")
        shown += 1
    if not shown:
        print("sin cambios desde la última confirmación")
    return 0
