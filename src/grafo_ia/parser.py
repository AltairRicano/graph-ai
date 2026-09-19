"""Parser de markdown de gemelos: frontmatter, headings ("gatos"), secciones y enlaces.

Reglas:
- Nada dentro de un bloque de código (``` o ~~~) cuenta: ni headings ni enlaces.
  El código inline (`...`) tampoco cuenta para enlaces.
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
_LINK = re.compile(r"(!?)\[\[([^\[\]\n]*?)\]\]")
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
class Link:
    line: int
    start: int  # columna del `[[` (o del `!` si es embed)
    end: int  # columna después de `]]`
    target: str  # parte de ruta, "" para `[[#Sección]]`
    section: str | None  # todo lo que va después del primer `#`
    alias: str | None
    embed: bool = False
    heading: int | None = None  # índice en Doc.headings de la sección que lo contiene

    @property
    def raw(self) -> str:
        return render_link(self.target, self.section, self.alias, self.embed)


@dataclass
class Doc:
    text: str
    lines: list[str]  # con sus saltos de línea
    body_start: int  # primera línea después del frontmatter
    code: list[bool]  # línea dentro de un bloque de código
    headings: list[Heading] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def heading_for_line(self, line: int) -> int | None:
        """Índice del heading cuya sección (la más interna) contiene la línea."""
        best = None
        for i, h in enumerate(self.headings):
            if h.line <= line < h.end:
                best = i
            elif h.line > line:
                break
        return best


def heading_ident(text: str) -> str | None:
    if ID_SEPARATOR in text:
        return text.split(ID_SEPARATOR, 1)[0].strip()
    return None


def heading_matches(text: str, name: str) -> bool:
    return text == name or heading_ident(text) == name


def render_link(target: str, section: str | None, alias: str | None, embed: bool = False) -> str:
    out = "!" if embed else ""
    out += "[[" + target
    if section is not None:
        out += "#" + section
    if alias is not None:
        out += "|" + alias
    return out + "]]"


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


def parse(text: str) -> Doc:
    lines = text.splitlines(keepends=True)
    meta, body_start = _parse_frontmatter(lines)
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
        code[i] = True  # el frontmatter tampoco aporta headings ni enlaces
    return Doc(text, lines, body_start, code, headings, meta)


def is_empty(text: str) -> bool:
    """Vacío = sin nada después del frontmatter. Es la definición de `faltante`."""
    doc = parse(text)
    return "".join(doc.lines[doc.body_start :]).strip() == ""


def _mask_inline_code(line: str) -> str:
    """Reemplaza el contenido de spans de código inline por espacios."""
    out = list(line)
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "`":
            j = i
            while j < n and line[j] == "`":
                j += 1
            ticks = line[i:j]
            close = line.find(ticks, j)
            while close != -1 and close + len(ticks) < n and line[close + len(ticks)] == "`":
                close = line.find(ticks, close + len(ticks) + 1)
            if close == -1:
                i = j
                continue
            for k in range(i, close + len(ticks)):
                out[k] = " "
            i = close + len(ticks)
        else:
            i += 1
    return "".join(out)


def links(doc: Doc) -> list[Link]:
    result: list[Link] = []
    for i, line in enumerate(doc.lines):
        if doc.code[i] or "[[" not in line:
            continue
        masked = _mask_inline_code(line)
        for m in _LINK.finditer(masked):
            inner = line[m.start(2) : m.end(2)]
            alias = None
            if "|" in inner:
                inner, alias = inner.split("|", 1)
                if inner.endswith("\\"):  # `[[a\|b]]` dentro de tablas
                    inner = inner[:-1]
            section = None
            if "#" in inner:
                inner, section = inner.split("#", 1)
            result.append(
                Link(
                    line=i,
                    start=m.start(),
                    end=m.end(),
                    target=inner.strip(),
                    section=section.strip() if section is not None else None,
                    alias=alias,
                    embed=bool(m.group(1)),
                    heading=doc.heading_for_line(i),
                )
            )
    return result


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


def has_section(doc: Doc, name: str) -> bool:
    try:
        find_section(doc, name)
        return True
    except AmbiguousError:
        return True  # existe, aunque repetida
    except NotFoundError:
        return False


def section_range(doc: Doc, name: str) -> tuple[int, int]:
    h = find_section(doc, name)
    return h.line, h.end
