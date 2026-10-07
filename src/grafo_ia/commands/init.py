"""`graph init`: crea `.graph/Estado_Proyecto/` con sus cinco documentos.

Correrlo de nuevo no sobreescribe nada: solo repone el documento que falte.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from grafo_ia import templates
from grafo_ia.commands._common import cwd_of, plural
from grafo_ia.errors import GraphError, NoGraphError
from grafo_ia.files import write_text_atomic
from grafo_ia.paths import ESTADO_DIR, ESTADO_DOCS, GRAPH_DIR, doc_path, find_root


def ensure_docs(root: Path) -> list[str]:
    """Crea los documentos que falten. -> nombres de los creados."""
    created = []
    fecha = templates.today()
    for name in ESTADO_DOCS:
        path = doc_path(root, name)
        if not path.exists():
            write_text_atomic(path, templates.render_estado(name, fecha))
            created.append(name)
    return created


def register(sub) -> None:
    p = sub.add_parser("init", help="crea .graph/Estado_Proyecto en la carpeta actual")
    # ya no pregunta nada; se acepta para no romper a quien lo siga escribiendo
    p.add_argument("-y", "--yes", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=run)


def run(args) -> int:
    root = cwd_of(args)
    try:
        existing = find_root(root)
    except NoGraphError:
        existing = None
    if existing is not None and existing != root:
        raise GraphError(f"ya hay un {GRAPH_DIR} en {existing}; corre `graph init` ahí")
    created = ensure_docs(root)
    print(f"estado: {root / GRAPH_DIR / ESTADO_DIR}")
    if created:
        print(f"{plural(len(created), 'documento creado', 'documentos creados')}: {', '.join(created)} (se escriben con `graph multiedit`)")
    else:
        print("los cinco documentos ya existían: no se cambió nada")
    return 0
