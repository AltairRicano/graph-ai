"""Consultas de solo lectura: `graph get` y `graph status`."""

from __future__ import annotations

from pathlib import Path

from grafo_ia import parser, templates
from grafo_ia.commands._common import root_of
from grafo_ia.errors import GraphError
from grafo_ia.paths import ESTADO_DIR, ESTADO_DOCS, doc_id, doc_path, graph_dir, resolve_doc


def read_doc(root: Path, name: str) -> str:
    try:
        return doc_path(root, name).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GraphError(f"{doc_id(name)} no existe (`graph init` lo vuelve a crear)")


# ---- get ---------------------------------------------------------------------
def run_get(args) -> int:
    root = root_of(args)
    targets = [resolve_doc(a) for a in args.rutas]  # un nombre mal escrito falla antes de imprimir nada
    for i, (name, section) in enumerate(targets):
        doc = parser.parse(read_doc(root, name))
        content = parser.section_text(doc, section) if section else doc.text
        if i:
            print()
        print(f"==> {doc_id(name)}{'#' + section if section else ''} <==")
        print(content.rstrip("\n"))
    return 0


# ---- status ------------------------------------------------------------------
def run_status(args) -> int:
    root = root_of(args)
    print(f"{ESTADO_DIR}: {graph_dir(root) / ESTADO_DIR}")
    width = max(len(n) for n in ESTADO_DOCS) + 3
    for name in ESTADO_DOCS:
        label = f"{name}.md".ljust(width)
        path = doc_path(root, name)
        if not path.exists():
            print(f"  {label}  falta (`graph init` lo crea)")
            continue
        text = path.read_text(encoding="utf-8")
        fecha = parser.parse(text).meta.get("fecha_actualizacion") or "sin fecha"
        print(f"  {label}  {fecha}" + ("  sin escribir" if templates.is_shell(name, text) else ""))
    return 0


def register(sub) -> None:
    p = sub.add_parser("get", help="imprime uno o varios documentos de Estado_Proyecto, o una sección")
    p.add_argument("rutas", nargs="+", metavar="documento[#sección]")
    p.set_defaults(func=run_get)

    p = sub.add_parser("status", help="los cinco documentos con su última actualización")
    p.set_defaults(func=run_status)
