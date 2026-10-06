"""`graph update <ruta>...`: confirma sincronía de forma consciente.

Para índices y documentos editados a mano (`graph multiedit` ya confirma lo que
escribe). Carpeta: exige que su índice tenga `## Propósito`; guarda qué archivos
tiene hoy la carpeta (`archivos_confirmados`, contra eso se mide si entran o
salen archivos), el hash de cada uno (para `graph diff`) y qué enlaces del
índice resuelven (`enlaces_confirmados`, para notar si uno deja de hacerlo), y
regenera las aristas del índice. Documento de Estado_Proyecto: solo regenera aristas.
En ambos casos mueve `fecha_actualizacion` del header (frontmatter) a hoy; las
fechas de cada sección son independientes y no se tocan.
Acepta varias rutas y las valida todas antes de confirmar ninguna. Un archivo
de código no se confirma: no tiene documento, se confirma el índice de su carpeta.
"""

from __future__ import annotations

from pathlib import Path

from grafo_ia import graph_io, states, templates, trivial
from grafo_ia.commands._common import cwd_of, root_of
from grafo_ia.edges import Resolver, TwinCache, regenerate, scan_links
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import Exclusion
from grafo_ia.graph_io import Graph
from grafo_ia.hashing import hash_file
from grafo_ia.paths import ESTADO_INDEX_ID, GRAPH_DIR, Target, code_id, resolve_arg, twin_path
from grafo_ia.rewrite import write_text_atomic


def register(sub) -> None:
    p = sub.add_parser("update", help="confirma que un índice o documento está al día (guarda los archivos de la carpeta y regenera aristas)")
    p.add_argument("rutas", nargs="+", metavar="ruta", help="una o más carpetas o documentos de Estado_Proyecto")
    p.set_defaults(func=run)


def confirm(root: Path, graph: Graph, cache: TwinCache, t: Target, resolver: Resolver | None = None,
            exclusion: Exclusion | None = None) -> tuple[list[str] | None, set[str], set[str]]:
    """Guarda los archivos de la carpeta y sus hashes (solo índices) y regenera aristas.

    -> (archivos confirmados o None, aristas nuevas, aristas quitadas)
    """
    files = None
    if t.kind == "indice":
        files = states.folder_files(root, t.rel, exclusion)
        graph.nodes[t.node_id][states.CONFIRMED] = files
        for name in files:
            node = graph.nodes.get(code_id(states.join(t.rel, name)))
            if node is not None and node["tipo"] == "codigo":
                try:
                    node["last_synced_hash"] = hash_file(root / states.join(t.rel, name))
                except OSError:
                    continue
        graph.dirty = True
    resolver = resolver or Resolver(graph.nodes)
    added, removed = regenerate(graph, cache, t.node_id, resolver)
    if t.kind == "indice":
        graph.nodes[t.node_id][states.CONFIRMED_LINKS] = states.working_links(
            scan_links(graph, resolver, cache, t.node_id, root=root))
    return files, added, removed


def _check(root: Path, cache: TwinCache, t: Target, trivial_rules: list[str], exclusion: Exclusion) -> None:
    """Valida un blanco sin escribir nada."""
    shown = t.rel or "."
    if t.kind == "codigo":
        raise GraphError(f"{shown} es un archivo de código: no tiene documento que confirmar. "
                         f"Se confirma el índice de su carpeta (`graph update <carpeta>`)")
    if t.node_id is None:
        raise GraphError(f"{shown} no está en el grafo (usa `graph add`)")
    if t.kind != "indice" or t.node_id == ESTADO_INDEX_ID:
        return
    if not (root / t.rel).is_dir():
        raise GraphError(f"{shown} ya no existe: su índice es huérfano (usa `graph prune` o `graph remove`)")
    if not states.has_purpose(cache.doc(t.node_id)):
        files = states.folder_files(root, t.rel, exclusion)
        if any(not trivial.is_trivial(trivial_rules, states.join(t.rel, n)) for n in files):
            raise GraphError(f"el índice de {shown} no tiene `## Propósito`, escríbelo primero: {GRAPH_DIR}/{t.node_id}")


def run(args) -> int:
    root = root_of(args)
    cache = TwinCache(root)
    trivial_rules = trivial.load_rules(root)
    exclusion = Exclusion(root)
    results = []
    with graph_io.transaction(root) as graph:
        targets = []
        for ruta in dict.fromkeys(args.rutas):
            t = resolve_arg(root, graph.nodes, ruta, cwd_of(args))
            _check(root, cache, t, trivial_rules, exclusion)
            targets.append(t)
        for t in targets:
            files, added, removed = confirm(root, graph, cache, t, exclusion=exclusion)
            text = cache.text(t.node_id)
            if text is not None:
                touched = templates.touch_updated(text)
                if touched != text:
                    write_text_atomic(twin_path(root, t.node_id), touched)
            results.append((t, files, added, removed))
    for t, files, added, removed in results:
        if files is not None:
            print(f"{t.rel or '.'}: índice confirmado ({len(files)} archivo{'s' if len(files) != 1 else ''})")
        else:
            print(f"{t.node_id}: aristas regeneradas")
        for x in sorted(added):
            print(f"  + {x}")
        for x in sorted(removed):
            print(f"  - {x}")
    return 0
