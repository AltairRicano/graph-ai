"""Render de cáscaras: gemelos de código, índices y documentos de Estado_Proyecto.

Las plantillas del vault (Templater) son el diseño; aquí viven las versiones
empaquetadas con nombre final y sin sintaxis de Templater.
"""

from __future__ import annotations

import datetime as _dt
import re
from importlib import resources

from grafo_ia import parser

INDEX_FOLDERS = "📁 Carpetas"
INDEX_FILES = "📄 Archivos"
STRUCTURAL_SECTIONS = (INDEX_FOLDERS, INDEX_FILES)

_FECHA_ACT = re.compile(r"^(fecha_actualizacion:[ \t]*)[^\r\n]*(\r?\n)?$")


def today() -> str:
    return _dt.date.today().isoformat()


def frontmatter(tipo: str, fecha: str) -> str:
    return f"---\ntipo: {tipo}\nfecha_elaboracion: {fecha}\nfecha_actualizacion: {fecha}\n---\n"


def render_code_shell(fecha: str | None = None) -> str:
    """Solo frontmatter: el gemelo nace `faltante` hasta que alguien escriba contenido real."""
    return frontmatter("codigo", fecha or today())


def render_estado(name: str, fecha: str | None = None) -> str:
    text = resources.files("grafo_ia").joinpath("templates", f"{name}.md").read_text(encoding="utf-8")
    return text.replace("{{fecha}}", fecha or today())


def index_item(node_id: str, label: str) -> str:
    return f"- [[{node_id}|{label}]]"


def _index_sections(folders: list[tuple[str, str]], files: list[tuple[str, str]]) -> dict[str, list[str]]:
    return {
        INDEX_FOLDERS: [index_item(i, lbl) for i, lbl in folders],
        INDEX_FILES: [index_item(i, lbl) for i, lbl in files],
    }


def render_index(folders: list[tuple[str, str]], files: list[tuple[str, str]], fecha: str | None = None) -> str:
    out = frontmatter("indice", fecha or today())
    sections = _index_sections(folders, files)
    for i, (title, items) in enumerate(sections.items()):
        out += f"## {title}\n"
        out += "".join(item + "\n" for item in items)
        if i == 0:
            out += "\n"
    return out


def update_index(text: str, folders: list[tuple[str, str]], files: list[tuple[str, str]], fecha: str | None = None) -> str | None:
    """Reescribe solo las listas estructurales, conservando cualquier otra prosa.

    Devuelve el texto nuevo, o None si las listas ya estaban al día.
    `fecha_actualizacion` solo se mueve cuando la lista cambió.
    """
    doc = parser.parse(text)
    lines = list(doc.lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    wanted = _index_sections(folders, files)
    changed = False
    # de abajo hacia arriba para no mover los índices de línea pendientes
    found = {h.text: h for h in doc.headings if h.level == 2 and h.text in STRUCTURAL_SECTIONS}
    for title in sorted(found, key=lambda t: -found[t].line):
        h = found[title]
        # la lista termina en el siguiente heading de cualquier nivel
        end = next((x.line for x in doc.headings if x.line > h.line), len(lines))
        body = lines[h.line + 1 : end]
        current = [ln.rstrip("\r\n") for ln in body if ln.strip()]
        items = wanted[title]
        if current != items:
            trailing_blank = end < len(lines)
            new_body = [item + "\n" for item in items] + (["\n"] if trailing_blank else [])
            lines[h.line + 1 : end] = new_body
            changed = True
    for title in STRUCTURAL_SECTIONS:
        if title not in found:
            if lines and lines[-1].strip():
                lines.append("\n")
            lines.append(f"## {title}\n")
            lines.extend(item + "\n" for item in wanted[title])
            changed = True
    if not changed:
        return None
    return touch_updated("".join(lines), fecha)


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
