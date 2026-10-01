"""`graph incomplete [<ruta>...]`: chequeo de sincronía bajo demanda.

Listas en orden de prioridad: primero los desactualizados (el gemelo existe
pero ya miente sobre el código), luego los faltantes (vacíos), luego
pendientes por crear y huérfanos (más funciones sin sección o secciones sin
función, enlaces ambiguos y sin texto a
mostrar, y gemelos que pesan más que su código, como aviso). Los triviales
(`.graph/trivial`) con gemelo vacío no se listan: no piden contenido.
No depende del Watcher. Siempre sale con 0: informa, no bloquea.
"""

from __future__ import annotations

from grafo_ia import graph_io, states
from grafo_ia.commands._common import cwd_of, print_list, root_of
from grafo_ia.paths import to_rel


def register(sub) -> None:
    p = sub.add_parser("incomplete", help="lista, por prioridad, desactualizados, faltantes, pendientes por crear y huérfanos")
    p.add_argument("rutas", nargs="*", help="acota a estas rutas")
    p.set_defaults(func=run)


def print_report(rep: states.Report) -> None:
    print_list("desactualizados", rep.desactualizados)
    print_list("faltantes", rep.faltantes)
    if rep.desalineados:
        print_list("secciones desalineadas con el código", (f"{a.rel}: {a.describe()}" for a in rep.desalineados))
    print_list("pendientes por crear", (f"{p.source}:{p.line} {p.link} ({p.reason})" for p in rep.pendientes))
    print_list("huérfanos", rep.huerfanos)
    if rep.ambiguos:
        print_list("enlaces ambiguos", (f"{p.source}:{p.line} {p.link} ({p.reason})" for p in rep.ambiguos))
    if rep.sin_alias:
        print_list("enlaces sin texto a mostrar", (f"{p.source}:{p.line} {p.link}" for p in rep.sin_alias))
    if rep.extensos:
        print_list("gemelos más largos que su código (toca consolidar)",
                   (f"{rel}: {twin} caracteres de gemelo, {code} de código" for rel, twin, code in rep.extensos))


def run(args) -> int:
    root = root_of(args)
    scopes = [to_rel(root, r, cwd_of(args)) for r in args.rutas] or None
    if scopes and "" in scopes:
        scopes = None
    graph = graph_io.load(root)
    print_report(states.report(root, graph, scopes, check_symbols=True))
    return 0
