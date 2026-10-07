"""Dónde vive el estado del proyecto y cómo se nombra cada documento.

`.graph/Estado_Proyecto/` tiene cinco documentos fijos. Un comando los recibe
como `Estado_Proyecto/Estado.md` o solo `Estado`, con `#sección` opcional.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

from grafo_ia.errors import GraphError, NoGraphError

GRAPH_DIR = ".graph"
ESTADO_DIR = "Estado_Proyecto"
# nombre del documento -> tipo (el del frontmatter); en el orden en que se leen
ESTADO_DOCS = {
    "Estado": "estado",
    "Plan": "plan",
    "Decisiones": "decisiones",
    "Tecnologias": "tecnologias",
    "Arquitectura": "arquitectura",
}


def find_root(start: Path | str | None = None) -> Path:
    """Sube por los padres hasta encontrar `.graph`, como git con `.git`."""
    here = Path(start or os.getcwd()).absolute()
    for candidate in (here, *here.parents):
        if (candidate / GRAPH_DIR).is_dir():
            return candidate
    raise NoGraphError(f"no hay {GRAPH_DIR} en {here} ni en sus carpetas padre (usa `graph init`)")


def graph_dir(root: Path) -> Path:
    return root / GRAPH_DIR


def doc_id(name: str) -> str:
    """Como se le muestra al usuario: `Estado_Proyecto/Estado.md`."""
    return f"{ESTADO_DIR}/{name}.md"


def doc_path(root: Path, name: str) -> Path:
    return graph_dir(root) / ESTADO_DIR / f"{name}.md"


def _fold(text: str) -> str:
    """Sin acentos ni mayúsculas: `Tecnologías` y `tecnologias` son el mismo documento."""
    plain = unicodedata.normalize("NFD", text)
    return "".join(c for c in plain if unicodedata.category(c) != "Mn").casefold()


def split_section(arg: str) -> tuple[str, str | None]:
    if "#" in arg:
        path, section = arg.split("#", 1)
        return path, section or None
    return arg, None


def resolve_doc(arg: str) -> tuple[str, str | None]:
    """`Estado_Proyecto/Estado.md#Hecho`, `Estado.md` o `Estado` -> ("Estado", "Hecho")."""
    path, section = split_section(arg.strip())
    rel = path.replace("\\", "/").strip("/")
    for prefix in (f"{GRAPH_DIR}/", f"{ESTADO_DIR}/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
    stem = rel[:-3] if rel.endswith(".md") else rel
    for name in ESTADO_DOCS:
        if _fold(stem) == _fold(name):
            return name, section
    raise GraphError(f"{path or arg} no es un documento de {ESTADO_DIR} ({', '.join(ESTADO_DOCS)})")
