"""Cáscaras de los documentos de Estado_Proyecto y fechas del frontmatter.

Las plantillas del vault (Templater) son el diseño; aquí viven las versiones
empaquetadas con nombre final y sin sintaxis de Templater.
"""

from __future__ import annotations

import datetime as _dt
import re
from importlib import resources

from grafo_ia import parser

_FECHA_ACT = re.compile(r"^(fecha_actualizacion:[ \t]*)[^\r\n]*(\r?\n)?$")


def today() -> str:
    return _dt.date.today().isoformat()


def render_estado(name: str, fecha: str | None = None) -> str:
    text = resources.files("grafo_ia").joinpath("templates", f"{name}.md").read_text(encoding="utf-8")
    return text.replace("{{fecha}}", fecha or today())


def _body(text: str) -> str:
    doc = parser.parse(text)
    return "".join(doc.lines[doc.body_start:]).strip()


def is_shell(name: str, text: str) -> bool:
    """¿El documento sigue como nació? Solo cuenta el cuerpo: las fechas del frontmatter no."""
    return _body(text) == _body(render_estado(name))


def touch_updated(text: str, fecha: str | None = None) -> str:
    """Pone `fecha_actualizacion` del header (frontmatter) en `fecha`.

    Solo toca el frontmatter: las fechas `**Actualización:**` de cada sección
    son independientes y no se mueven. Sin frontmatter no se inventa uno.
    """
    doc = parser.parse(text)
    if doc.body_start == 0:
        return text
    fecha = fecha or today()
    lines = list(doc.lines)
    closing = doc.body_start - 1  # línea del `---` de cierre
    for i in range(1, closing):
        m = _FECHA_ACT.match(lines[i])
        if m:
            lines[i] = f"{m.group(1)}{fecha}{m.group(2) or ''}"
            return "".join(lines)
    eol = "\r\n" if lines[0].endswith("\r\n") else "\n"
    lines.insert(closing, f"fecha_actualizacion: {fecha}{eol}")
    return "".join(lines)
