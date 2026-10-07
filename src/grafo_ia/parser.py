"""Parser de markdown de los documentos: frontmatter, headings ("gatos") y secciones.

Reglas:
- Nada dentro de un bloque de código (``` o ~~~) cuenta como heading.
- Una sección va desde su heading hasta el siguiente de igual o mayor jerarquía
  (menos o igual cantidad de `#`), o hasta el final del documento.
- Un heading `nombre_snake_case & Nombre Legible` se puede direccionar por el
  texto completo o solo por el identificador antes de ` & `.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from grafo_ia.errors import AmbiguousError, NotFoundError

_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_CLOSING_HASHES = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FM_KEY = re.compile(r"^([^\s:#-][^:]*):[ \t]*(.*)$")
_FM_ITEM = re.compile(r"^[ \t]*-[ \t]*(.*)$")

ID_SEPARATOR = " & "


@dataclass
class Heading:
    level: int
    text: str
    line: int  # índice 0-based en `Doc.lines`
    end: int = 0  # línea (exclusiva) donde termina su sección

    @property
    def ident(self) -> str | None:
        """Identificador de un heading `snake & Legible`, o None."""
        return heading_ident(self.text)


@dataclass
class Doc:
    text: str
    lines: list[str]  # con sus saltos de línea
    body_start: int  # primera línea después del frontmatter
    code: list[bool]  # línea dentro de un bloque de código
    headings: list[Heading] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def heading_ident(text: str) -> str | None:
    if ID_SEPARATOR in text:
        return text.split(ID_SEPARATOR, 1)[0].strip()
    return None


def heading_matches(text: str, name: str) -> bool:
    return text == name or heading_ident(text) == name


def _parse_frontmatter(lines: list[str]) -> tuple[dict, int]:
    if not lines or lines[0].lstrip("﻿").rstrip("\r\n").strip() != "---":
        return {}, 0
    meta: dict = {}
    current: str | None = None
    for i in range(1, len(lines)):
        raw = lines[i].rstrip("\r\n")
        if raw.strip() in ("---", "..."):
            for k, v in meta.items():
                if v == []:
                    meta[k] = ""
            return meta, i + 1
        m = _FM_KEY.match(raw)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            if value == "":
                meta[key] = []
                current = key
            elif value.startswith("[") and value.endswith("]"):
                meta[key] = [_unquote(v) for v in value[1:-1].split(",") if v.strip()]
                current = None
            else:
                meta[key] = _unquote(value)
                current = None
            continue
        m = _FM_ITEM.match(raw)
        if m and current is not None and isinstance(meta.get(current), list):
            meta[current].append(_unquote(m.group(1)))
    # frontmatter sin cierre: no es frontmatter
    return {}, 0


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(text: str, frontmatter: bool = True) -> Doc:
    """`frontmatter=False` para un fragmento de cuerpo: un `---` inicial es un separador, no un header."""
    lines = text.splitlines(keepends=True)
    meta, body_start = _parse_frontmatter(lines) if frontmatter else ({}, 0)
    code = [False] * len(lines)
    headings: list[Heading] = []
    fence: str | None = None
    for i in range(body_start, len(lines)):
        raw = lines[i].rstrip("\r\n")
        if fence is not None:
            code[i] = True
            stripped = raw.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        m = _FENCE.match(raw)
        if m:
            fence = m.group(1)
            code[i] = True
            continue
        m = _HEADING.match(raw)
        if m:
            text_ = m.group(2) or ""
            text_ = _CLOSING_HASHES.sub("", text_).strip() if text_.rstrip().endswith("#") else text_.strip()
            headings.append(Heading(len(m.group(1)), text_, i))
    for idx, h in enumerate(headings):
        h.end = len(lines)
        for nxt in headings[idx + 1 :]:
            if nxt.level <= h.level:
                h.end = nxt.line
                break
    for i in range(body_start):
        code[i] = True  # el frontmatter tampoco aporta headings
    return Doc(text, lines, body_start, code, headings, meta)


def find_headings(doc: Doc, name: str, within: tuple[int, int] | None = None) -> list[int]:
    lo, hi = within if within else (0, len(doc.lines))
    return [i for i, h in enumerate(doc.headings) if lo <= h.line < hi and heading_matches(h.text, name)]


def find_section(doc: Doc, name: str) -> Heading:
    """Resuelve `A` o `A#B` (B dentro de la sección A). Error si no existe o es ambiguo."""
    parts = [p for p in name.split("#") if p != ""]
    if not parts:
        raise NotFoundError("sección vacía")
    within: tuple[int, int] | None = None
    heading: Heading | None = None
    for part in parts:
        found = find_headings(doc, part, within)
        if within is not None and heading is not None:
            found = [i for i in found if doc.headings[i].line != heading.line]
        if not found:
            raise NotFoundError(f"no existe la sección '{part}'")
        if len(found) > 1:
            lines = ", ".join(str(doc.headings[i].line + 1) for i in found)
            raise AmbiguousError(f"la sección '{part}' aparece más de una vez (líneas {lines})")
        heading = doc.headings[found[0]]
        within = (heading.line, heading.end)
    assert heading is not None
    return heading


def section_text(doc: Doc, name: str) -> str:
    h = find_section(doc, name)
    return "".join(doc.lines[h.line : h.end])
