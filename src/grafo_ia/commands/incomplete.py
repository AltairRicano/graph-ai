"""`graph incomplete [<ruta>...]`: chequeo de sincronía bajo demanda.

Lista los índices por escribir, en orden de prioridad y cada uno con su motivo:
primero los desactualizados (el índice existe pero ya no describe la carpeta:
le entraron o salieron archivos, o un enlace dejó de resolver), luego los
faltantes (sin `## Propósito`), luego enlaces pendientes y huérfanos (más
enlaces ambiguos o sin texto a mostrar, e índices que pesan más que el código de
su carpeta, como aviso). Las carpetas triviales no se listan: no piden contenido.
Un archivo como ruta pide la carpeta que lo contiene.
No depende del Watcher. Siempre sale con 0: informa, no bloquea.
"""

from __future__ import annotations

from grafo_ia import graph_io, states
from grafo_ia.commands._common import cwd_of, print_list, root_of
from grafo_ia.paths import to_rel


def register(sub) -> None:
    p = sub.add_parser("incomplete", help="lista, por prioridad y con su motivo, los índices desactualizados, faltantes, pendientes y huérfanos")
    p.add_argument("rutas", nargs="*", help="acota a estas rutas")
    p.set_defaults(func=run)


def print_report(rep: states.Report) -> None:
    print_list("desactualizados", rep.describe(rep.desactualizados))
    print_list("faltantes", rep.describe(rep.faltantes))
    print_list("pendientes por crear", (f"{p.source}:{p.line} {p.link} ({p.reason})" for p in rep.pendientes))
    print_list("huérfanos", (r or "." for r in rep.huerfanos))
    if rep.ambiguos:
        print_list("enlaces ambiguos", (f"{p.source}:{p.line} {p.link} ({p.reason})" for p in rep.ambiguos))
    if rep.sin_alias:
        print_list("enlaces sin texto a mostrar", (f"{p.source}:{p.line} {p.link}" for p in rep.sin_alias))
    if rep.extensos:
        print_list("índices más largos que el código de su carpeta (repiten lo que el código ya dice)",
                   (f"{rel or '.'}: {size} caracteres de índice, {code} de código" for rel, size, code in rep.extensos))


def run(args) -> int:
    root = root_of(args)
    scopes = [to_rel(root, r, cwd_of(args)) for r in args.rutas] or None
    if scopes and "" in scopes:
        scopes = None
    graph = graph_io.load(root)
    print_report(states.report(root, graph, scopes, check_size=True))
    return 0
