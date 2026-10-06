"""`graph init`: reconciliación completa contra un JSON vacío (o existente).

1. Escaneo y confirmación de exclusiones (vista previa antes de escribir nada).
2. Andamiaje: `.graph/` con `config` (identificador), `exclude`, repo anidado
   y `index.json` con todos los nodos. Solo JSON, ningún gemelo todavía.
3. `populate`: el único que crea archivos.
Correrlo de nuevo no destruye nada; con un `index.json` corrupto lo reconstruye
(se respalda el roto y se pierden los `last_synced_hash`, no el contenido).
"""

from __future__ import annotations

import secrets
import sys
import time
from collections import Counter

from grafo_ia import graph_io, settings, states, trivial
from grafo_ia.commands import hooks
from grafo_ia.commands._common import cwd_of, plural
from grafo_ia.commands.populate import populate
from grafo_ia.errors import CorruptGraphError, GraphError, NoGraphError
from grafo_ia.exclusion import EXCLUDE_FILE, INITIAL_RULES, Exclusion, norm_rule, suggest, walk
from grafo_ia.graph_io import SCHEMA_VERSION, index_path
from grafo_ia.paths import GRAPH_DIR, find_root, graph_dir
from grafo_ia.reconciliation import reconcile, summary

EXCLUDE_HEADER = (
    "# Exclusiones propias del proyecto, una por línea. Se suman a las de por defecto.\n"
    "# Nombre suelto = en cualquier nivel (admite comodines); con '/' = desde la raíz ('/generado' = solo la de la raíz).\n"
    "# Se editan a mano o con `graph ignore`. Las iniciales de abajo también se pueden quitar.\n"
)


def initial_rules() -> list[str]:
    return [r for rules in INITIAL_RULES.values() for r in rules]


def initial_exclude_text() -> str:
    """Encabezado más las reglas iniciales, agrupadas por motivo."""
    groups = "".join(f"\n# {motivo}\n" + "".join(r + "\n" for r in rules) for motivo, rules in INITIAL_RULES.items())
    return EXCLUDE_HEADER + groups
PREVIEW_LIMIT = 40


def ensure_graph_dir(root, name: str | None) -> tuple[str, str]:
    gdir = graph_dir(root)
    gdir.mkdir(exist_ok=True)
    ex = gdir / EXCLUDE_FILE
    if not ex.exists():
        ex.write_text(initial_exclude_text(), encoding="utf-8")
        # solo junto con un `exclude` nuevo: un grafo que ya existía no gana triviales sin pedirlo
        tr = gdir / trivial.TRIVIAL_FILE
        if not tr.exists():
            tr.write_text(trivial.initial_text(), encoding="utf-8")
    nombre = settings.get_value(root, "nombre")
    if name:
        nombre = name
    if not nombre:
        nombre = root.name
    settings.set_value(root, "nombre", nombre)
    ghash = settings.get_value(root, "hash")
    if not ghash:
        ghash = secrets.token_hex(6)  # al azar, una sola vez: sobrevive a mover la carpeta
        settings.set_value(root, "hash", ghash)
    return nombre, ghash


def preview(scan, suggestions) -> None:
    top = Counter(f.split("/")[0] if "/" in f else "." for f in scan.files)
    print(f"Se incluyen {plural(len(scan.files), 'archivo')} en {plural(len(scan.dirs), 'carpeta')}:")
    for d, n in sorted(top.items()):
        print(f"  {d + '/' if d != '.' else '(raíz)'}: {n}")
    print(f"Se excluyen {len(scan.excluded)}:")
    for rel, reason in scan.excluded[:PREVIEW_LIMIT]:
        print(f"  - {rel}  ({reason})")
    if len(scan.excluded) > PREVIEW_LIMIT:
        print(f"  ... y {len(scan.excluded) - PREVIEW_LIMIT} más")
    if suggestions:
        print("Sugerencias de exclusión adicional:")
        for rel, reason in suggestions:
            print(f"  ? {rel}  ({reason})")


def _confirm(question: str) -> bool:
    try:
        answer = input(f"{question} [s/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("s", "si", "sí", "y", "yes")


def register(sub) -> None:
    p = sub.add_parser("init", help="inicializa el grafo en la carpeta actual (o la reconcilia completa)")
    p.add_argument("-y", "--yes", action="store_true", help="no pedir confirmación (para agentes)")
    p.add_argument("--dry-run", action="store_true", help="solo mostrar la vista previa")
    p.add_argument("--name", help="nombre del grafo (por defecto, el de la carpeta)")
    p.add_argument("--exclude", action="append", default=[], metavar="PATRÓN", help="exclusión extra para .graph/exclude (repetible)")
    p.add_argument("--accept-suggestions", action="store_true", help="agregar las sugerencias a .graph/exclude")
    p.add_argument("--no-git", action="store_true", help="no crear el repo anidado ni instalar hooks")
    p.set_defaults(func=run)


def run(args) -> int:
    root = cwd_of(args)
    try:
        existing = find_root(root)
        if existing != root:
            raise GraphError(f"ya hay un grafo en {existing}; corre `graph init` ahí o usa `graph add` para esta carpeta")
    except NoGraphError:
        pass

    exclusion = Exclusion(root)
    if not (graph_dir(root) / EXCLUDE_FILE).exists():
        exclusion.user_rules.extend(initial_rules())  # la vista previa ya cuenta con las que se van a escribir
    extra = list(args.exclude)
    if extra:
        exclusion.user_rules.extend(r for r in map(norm_rule, extra) if r)
    scan = walk(root, exclusion)
    suggestions = suggest(scan)
    preview(scan, suggestions)
    if args.dry_run:
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            raise GraphError("init necesita confirmación: corre en una terminal o usa --yes")
        if suggestions and _confirm("¿Agregar las sugerencias a .graph/exclude?"):
            args.accept_suggestions = True
        if not _confirm(f"¿Crear/reconciliar el grafo en {root}?"):
            print("cancelado")
            return 0
    if args.accept_suggestions:
        extra += [rel for rel, _ in suggestions]

    nombre, ghash = ensure_graph_dir(root, args.name)
    if extra:
        with open(graph_dir(root) / EXCLUDE_FILE, "a", encoding="utf-8") as f:
            current = set(Exclusion(root).user_rules)
            for e in extra:
                e = norm_rule(e)
                if e and e not in current:
                    f.write(e + "\n")
                    current.add(e)
    if index_path(root).exists():
        try:
            graph_io.load(root)
        except CorruptGraphError as e:
            backup = index_path(root).with_name(f"index.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
            index_path(root).replace(backup)
            print(f"[AVISO] {e}\n        respaldado en {backup.name}; se reconstruye desde cero")

    use_git = not args.no_git and hooks.git_available()
    installed: list[str] = []
    if use_git:
        # antes de reconciliar: el .gitignore que se cree también entra al grafo
        hooks.init_nested(root)
        if hooks.main_toplevel(root) is not None:
            hooks.ensure_main_gitignore(root)
            installed = hooks.install(root)

    with graph_io.transaction(root, create=True) as graph:
        graph.meta.update({"nombre": nombre, "hash": ghash, "schema_version": SCHEMA_VERSION})
        graph.dirty = True
        changes = reconcile(root, graph, "", Exclusion(root))
        pop = populate(root, graph)

    print(summary(changes))
    for rel, reason in changes.skipped:
        print(f"[AVISO] se omitió {rel}: {reason}")
    print(f"populate: {plural(len(pop.created), 'archivo creado', 'archivos creados')}")
    print(f"grafo: {nombre} ({ghash}) en {root / GRAPH_DIR}")
    if installed:
        print("hooks instalados: " + ", ".join(installed))
    # lo que sigue es escribir: se dice aquí para no gastar otro comando en preguntarlo
    todo = states.report(root, graph_io.load(root), links=False).faltantes
    if todo:
        print(f"índices por escribir ({len(todo)}): " + ", ".join(r or "." for r in todo))

    if use_git:
        hooks.mirror_commit(root, "graph init", hooks.main_head(root))
    return 0
