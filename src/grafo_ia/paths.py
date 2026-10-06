"""Rutas del proyecto, ids de nodo y documentos de `.graph`.

Convenciones:
- archivo `src/main.go`   -> id `src/main.go`: el nodo es el propio archivo de
  código, no tiene documento en `.graph`.
- carpeta `src/features`  -> id `src/features/features.md` (su índice, la ruta
  del documento dentro de `.graph`)
- raíz del proyecto       -> id `Index.md` (el maestro)
- Estado_Proyecto es virtual: solo existe dentro de `.graph`.
Siempre con `/`.
"""

from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from pathlib import Path

from grafo_ia.errors import GraphError, NoGraphError

GRAPH_DIR = ".graph"
MASTER_ID = "Index.md"
ESTADO_DIR = "Estado_Proyecto"
ESTADO_INDEX_ID = f"{ESTADO_DIR}/{ESTADO_DIR}.md"
# nombre final del documento -> tipo de nodo
ESTADO_DOCS = {
    "Tecnologias": "tecnologias",
    "Decisiones": "decisiones",
    "Arquitectura": "arquitectura",
    "Estado": "estado",
    "Plan": "plan",
}
ESTADO_TIPOS = set(ESTADO_DOCS.values())
NODE_TIPOS = {"codigo", "indice"} | ESTADO_TIPOS


def find_root(start: Path | str | None = None) -> Path:
    """Sube por los padres hasta encontrar `.graph`, como git con `.git`."""
    here = Path(start or os.getcwd()).absolute()
    for candidate in (here, *here.parents):
        if (candidate / GRAPH_DIR).is_dir():
            return candidate
    raise NoGraphError(f"no hay {GRAPH_DIR} en {here} ni en sus carpetas padre (usa `graph init`)")


def graph_dir(root: Path) -> Path:
    return root / GRAPH_DIR


def norm_rel(rel: str) -> str:
    """Normaliza una ruta relativa: `/`, sin `./`, `""` para la raíz."""
    rel = rel.replace("\\", "/")
    rel = posixpath.normpath(rel) if rel else ""
    return "" if rel in (".", "") else rel.strip("/")


def to_rel(root: Path, path: Path | str, cwd: Path | str | None = None) -> str:
    """Ruta (absoluta o relativa a `cwd`) -> ruta relativa a la raíz, con `/`."""
    base = Path(cwd) if cwd is not None else Path(os.getcwd())
    absolute = os.path.normpath(os.path.join(os.path.abspath(base), os.fspath(path)))
    root_abs = os.path.normpath(os.path.abspath(root))
    try:
        rel = os.path.relpath(absolute, root_abs)
    except ValueError:  # otra unidad en Windows
        raise GraphError(f"{path} está fuera del proyecto {root}")
    rel = norm_rel(rel)
    if rel == ".." or rel.startswith("../"):
        raise GraphError(f"{path} está fuera del proyecto {root}")
    return rel


def parent_rel(rel: str) -> str:
    return posixpath.dirname(rel)


def code_id(rel: str) -> str:
    return rel


def folder_id(rel: str) -> str:
    if rel == "":
        return MASTER_ID
    return f"{rel}/{posixpath.basename(rel)}.md"


def node_name(node_id: str) -> str:
    """`nombre` del nodo: basename del id sin el `.md` final."""
    base = posixpath.basename(node_id)
    return base[:-3] if base.endswith(".md") else base


def twin_path(root: Path, node_id: str) -> Path:
    return graph_dir(root).joinpath(*node_id.split("/"))


def estado_doc_id(name: str) -> str:
    return f"{ESTADO_DIR}/{name}.md"


def is_estado(node_id: str) -> bool:
    return node_id == ESTADO_INDEX_ID or node_id.startswith(f"{ESTADO_DIR}/")


def folder_rel_of_index(node_id: str) -> str:
    """Carpeta que representa un nodo índice (`""` para el maestro)."""
    return "" if node_id == MASTER_ID else posixpath.dirname(node_id)


def project_rel(node_id: str, tipo: str) -> str | None:
    """Ruta de proyecto del nodo; None para lo que solo vive en `.graph`."""
    if is_estado(node_id):
        return None
    if tipo == "codigo":
        return node_id
    if tipo == "indice":
        return folder_rel_of_index(node_id)
    return None


def parent_index_id(node_id: str, tipo: str) -> str | None:
    """Índice padre derivado de la ruta. El maestro no tiene padre."""
    if node_id == MASTER_ID:
        return None
    if node_id == ESTADO_INDEX_ID:
        return MASTER_ID
    if is_estado(node_id):
        return ESTADO_INDEX_ID
    rel = project_rel(node_id, tipo)
    if rel is None:
        return None
    return folder_id(parent_rel(rel))


def is_under(rel: str, scope: str) -> bool:
    """¿`rel` es `scope` o está dentro de él? `""` cubre todo."""
    return scope == "" or rel == scope or rel.startswith(scope + "/")


@dataclass
class Target:
    """Argumento de ruta ya resuelto contra el grafo."""

    rel: str  # ruta de proyecto (o virtual de Estado_Proyecto)
    node_id: str | None  # None si no hay nodo
    kind: str | None  # "codigo", "indice", "estado" o None
    section: str | None = None


def split_section(arg: str) -> tuple[str, str | None]:
    if "#" in arg:
        path, section = arg.split("#", 1)
        return path, section or None
    return arg, None


def resolve_arg(root: Path, nodes: dict, arg: str, cwd: Path | str | None = None, allow_section: bool = False) -> Target:
    """Traduce un argumento de ruta del usuario a un nodo.

    Rechaza rutas dentro de `.graph`: los comandos reciben rutas del proyecto
    (un índice se nombra con la ruta de su carpeta).
    """
    path, section = split_section(arg) if allow_section else (arg, None)
    rel = to_rel(root, path or ".", cwd)
    if rel == GRAPH_DIR or rel.startswith(GRAPH_DIR + "/"):
        raise GraphError("los comandos reciben rutas del proyecto, no rutas dentro de .graph")

    real_estado = (root / ESTADO_DIR).exists()
    if not real_estado and (rel == ESTADO_DIR or rel.startswith(ESTADO_DIR + "/")):
        if rel == ESTADO_DIR:
            node_id = ESTADO_INDEX_ID
        else:
            name = node_name(rel.split("/", 1)[1])
            node_id = estado_doc_id(name)
        if node_id not in nodes:
            raise GraphError(f"{rel} no es un documento de {ESTADO_DIR}")
        return Target(rel, node_id, "estado", section)

    cid = code_id(rel)
    if rel and cid in nodes and nodes[cid].get("tipo") == "codigo":
        return Target(rel, cid, "codigo", section)
    fid = folder_id(rel)
    if fid in nodes and nodes[fid].get("tipo") == "indice":
        return Target(rel, fid, "indice", section)
    return Target(rel, None, None, section)
