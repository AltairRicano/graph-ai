"""`graph populate [<ruta>]`: el único que materializa carpetas, índices y gemelos.

Lee solo el JSON. Nunca sobreescribe un gemelo con contenido. Mantiene al día
las listas estructurales de todos los índices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import graph_io, templates
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.graph_io import Graph
from grafo_ia.paths import (
    ESTADO_DOCS,
    ESTADO_INDEX_ID,
    MASTER_ID,
    is_estado,
    is_under,
    node_name,
    parent_index_id,
    project_rel,
    to_rel,
    twin_path,
)
from grafo_ia.rewrite import write_text_atomic

ESTADO_TEMPLATE = {tipo: name for name, tipo in ESTADO_DOCS.items()}


@dataclass
class PopulateResult:
    created: list[str] = field(default_factory=list)
    indexes_updated: list[str] = field(default_factory=list)


def children_map(graph: Graph) -> dict[str, tuple[list[tuple[str, str]], list[tuple[str, str]]]]:
    kids: dict[str, tuple[list, list]] = {nid: ([], []) for nid, n in graph.nodes.items() if n["tipo"] == "indice"}
    for nid, node in graph.nodes.items():
        parent = parent_index_id(nid, node["tipo"])
        if parent is None or parent not in kids:
            continue
        label = node_name(nid) if node["tipo"] != "indice" else node["nombre"]
        (kids[parent][0] if node["tipo"] == "indice" else kids[parent][1]).append((nid, label))
    for folders, files in kids.values():
        folders.sort(key=lambda x: x[1].casefold())
        files.sort(key=lambda x: x[1].casefold())
    return kids


def _in_scope(node_id: str, tipo: str, scope: str) -> bool:
    if scope == "":
        return True
    rel = project_rel(node_id, tipo)
    return rel is not None and is_under(rel, scope)


def populate(root: Path, graph: Graph, scope: str = "") -> PopulateResult:
    res = PopulateResult()
    kids = children_map(graph)
    fecha = templates.today()
    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        tipo = node["tipo"]
        path = twin_path(root, node_id)
        if tipo == "indice":
            # los índices son estructurales y baratos: siempre se crean o se refrescan
            folders, files = kids.get(node_id, ([], []))
            if path.exists():
                new = templates.update_index(path.read_text(encoding="utf-8"), folders, files, fecha)
                if new is not None:
                    write_text_atomic(path, new)
                    res.indexes_updated.append(node_id)
            else:
                report = node_id not in (MASTER_ID, ESTADO_INDEX_ID)
                write_text_atomic(path, templates.render_index(folders, files, fecha, report=report))
                res.created.append(node_id)
            continue
        if path.exists() or not (_in_scope(node_id, tipo, scope) or is_estado(node_id)):
            continue
        if tipo == "codigo":
            write_text_atomic(path, templates.render_code_shell(fecha))
        else:
            write_text_atomic(path, templates.render_estado(ESTADO_TEMPLATE[tipo], fecha))
        res.created.append(node_id)
    return res


def report(res: PopulateResult) -> None:
    print(f"populate: {plural(len(res.created), 'archivo creado', 'archivos creados')}, "
          f"{plural(len(res.indexes_updated), 'índice actualizado', 'índices actualizados')}")


def register(sub) -> None:
    p = sub.add_parser("populate", help="materializa carpetas, índices y gemelos vacíos a partir del JSON")
    p.add_argument("ruta", nargs="?", help="acota a esta carpeta (por defecto, todo)")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    scope = to_rel(root, args.ruta, cwd_of(args)) if args.ruta else ""
    graph = graph_io.load(root)
    res = populate(root, graph, scope)
    report(res)
    return 0
