"""`graph ignore`: administra `.graph/exclude` desde el CLI.

- Sin argumentos: lista las reglas propias y recuerda las de por defecto.
- `graph ignore <patrón>...`: agrega reglas y saca del grafo lo que ahora
  queda excluido. Si eso borraría gemelos con contenido, no hace nada sin
  `--force` (el contenido solo se recupera del historial de `.graph`).
- `graph ignore --remove <patrón>...`: quita reglas y reconcilia, así lo que
  vuelve a incluirse regresa como faltante.
Nunca toca el código real.
"""

from __future__ import annotations

from pathlib import Path

from grafo_ia import graph_io
from grafo_ia.commands._common import plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.commands.remove import print_result, remove_nodes
from grafo_ia.edges import TwinCache
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import EXCLUDE_FILE, EXCLUIR, Exclusion, load_user_rules, norm_rule
from grafo_ia.graph_io import Graph
from grafo_ia.paths import graph_dir, project_rel
from grafo_ia.reconciliation import reconcile, summary
from grafo_ia.states import twin_has_content

DEFAULTS = (
    "carpetas ocultas (salvo .github), dependencias/build (node_modules, dist, venv, ...), "
    "agentes/ en la raíz, archivos sensibles (.env, llaves), lockfiles, cruft de editor, binarios, "
    "documentación (.md, .rst, docs/), licencias, pruebas (tests/, test_*.py, *_test.go, *.spec.*) "
    "y plantillas (plantillas/, templates/)"
)


def register(sub) -> None:
    p = sub.add_parser("ignore", help="agrega o quita exclusiones (.graph/exclude) y ajusta el grafo")
    p.add_argument("patrones", nargs="*", metavar="patrón",
                   help="nombre suelto = en cualquier nivel (admite comodines); con '/' = desde la raíz ('/generado')")
    p.add_argument("--remove", action="store_true", help="quita las reglas en vez de agregarlas")
    p.add_argument("--force", action="store_true", help="permite borrar gemelos con contenido")
    p.set_defaults(func=run)


def excluded_nodes(exclusion: Exclusion, graph: Graph) -> set[str]:
    """Nodos de código o carpeta que la exclusión ya no deja entrar."""
    out = set()
    for nid, node in graph.nodes.items():
        rel = project_rel(nid, node["tipo"])
        if not rel:
            continue
        verdict, _ = exclusion.check(rel, node["tipo"] == "indice")
        if verdict == EXCLUIR:
            out.add(nid)
    return out


def _write_rules(root: Path, keep, add: list[str]) -> None:
    """Reescribe `.graph/exclude` conservando comentarios y el orden de las reglas."""
    p = graph_dir(root) / EXCLUDE_FILE
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    out = [ln for ln in lines if not ln.strip() or ln.strip().startswith("#") or keep(norm_rule(ln))]
    out += add
    p.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")


def _list(root: Path) -> int:
    rules = load_user_rules(root)
    print(f"reglas propias en .graph/exclude ({len(rules)})")
    for r in rules:
        print(f"  {r}")
    print(f"por defecto (siempre): {DEFAULTS}")
    return 0


def _add(root: Path, patterns: list[str], force: bool) -> int:
    current = load_user_rules(root)
    new = [p for p in dict.fromkeys(patterns) if p not in current]
    cache = TwinCache(root)
    with graph_io.transaction(root) as graph:
        exclusion = Exclusion(root, sniff_binary=False)
        exclusion.user_rules.extend(new)
        ids = excluded_nodes(exclusion, graph)
        with_content = sorted(i for i in ids if graph.tipo(i) == "codigo" and twin_has_content(cache, i))
        if with_content and not force:
            listed = "".join(f"\n  - {i}" for i in with_content)
            raise GraphError(f"ignorar eso borraría {plural(len(with_content), 'gemelo')} con contenido:{listed}\n"
                             f"repite con --force si es lo que quieres (no se escribió ninguna regla)")
        if new:
            _write_rules(root, lambda r: True, new)
        res = remove_nodes(root, graph, ids, cache)
        populate(root, graph)
    for r in new:
        print(f"regla agregada: {r}")
    for p in patterns:
        if p not in new:
            print(f"ya estaba: {p}")
    if res.removed:
        print_result(res, "fuera del grafo")
    if with_content:
        print(f"[AVISO] se borraron {plural(len(with_content), 'gemelo')} con contenido; "
              f"lo último commiteado sigue en el historial de .graph")
    return 0


def _remove(root: Path, patterns: list[str]) -> int:
    current = load_user_rules(root)
    gone = [p for p in patterns if p in current]
    for p in patterns:
        if p not in current:
            print(f"no es una regla propia: {p}")
    if not gone:
        return 0
    _write_rules(root, lambda r: r not in gone, [])
    with graph_io.transaction(root) as graph:
        changes = reconcile(root, graph, "")
        pop = populate(root, graph)
    for r in gone:
        print(f"regla quitada: {r}")
    print(summary(changes))
    print(f"populate: {plural(len(pop.created), 'archivo creado', 'archivos creados')}")
    return 0


def run(args) -> int:
    root = root_of(args)
    patterns = [r for r in map(norm_rule, args.patrones) if r]
    if not patterns:
        if args.patrones:
            raise GraphError("patrón vacío")
        if args.remove:
            raise GraphError("--remove necesita al menos un patrón")
        return _list(root)
    if args.remove:
        return _remove(root, patterns)
    return _add(root, patterns, args.force)
