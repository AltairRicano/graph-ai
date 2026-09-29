"""Funciones y métodos del código, y su cruce con las secciones del gemelo.

Chequeo barato, no un analizador completo:
- Python con `ast` (exacto): funciones de módulo y métodos de clase, anidando
  clases como `Externa.Interna.metodo`. Con un error de sintaxis no se chequea.
- Go con regex: `func Nombre` y `func (r *Tipo) Nombre` -> `Tipo.Nombre`;
  el cuerpo termina en la primera `}` de la columna 0 (lo garantiza gofmt).
- Cualquier otro lenguaje: None (no se chequea, no se inventa).
Convención del gemelo: `## Funciones` con un `###` por función y los
métodos como `Clase.metodo`, todos al mismo nivel.
"""

from __future__ import annotations

import ast
import difflib
import posixpath
import re
from dataclasses import dataclass, field

from grafo_ia import parser

FUNCTIONS_SECTION = "funciones"


@dataclass(frozen=True)
class Symbol:
    name: str
    start: int  # 1-based, incluye decoradores
    end: int  # 1-based, inclusiva


def _python(text: str) -> list[Symbol] | None:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out: list[Symbol] = []

    def visit(body, prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([d.lineno for d in node.decorator_list] + [node.lineno])
                out.append(Symbol(prefix + node.name, start, node.end_lineno or node.lineno))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".")

    visit(tree.body, "")
    return out


_GO_FUNC = re.compile(r"^func\s+(?:\(\s*(?:\w+\s+)?\*?\s*(\w+)(?:\[[^\]]*\])?\s*\)\s*)?(\w+)")


def _go(text: str) -> list[Symbol]:
    lines = text.splitlines()
    out: list[Symbol] = []
    for i, line in enumerate(lines):
        m = _GO_FUNC.match(line)
        if not m:
            continue
        recv, name = m.groups()
        end = i
        if not line.rstrip().endswith("}"):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("}")), len(lines) - 1)
        out.append(Symbol(f"{recv}.{name}" if recv else name, i + 1, end + 1))
    return out


EXTRACTORS = {".py": _python, ".go": _go}


def supported(rel: str) -> bool:
    return posixpath.splitext(rel)[1].lower() in EXTRACTORS


def extract(rel: str, text: str) -> list[Symbol] | None:
    """Símbolos del archivo, o None si el lenguaje no se chequea."""
    fn = EXTRACTORS.get(posixpath.splitext(rel)[1].lower())
    return fn(text.replace("\r\n", "\n")) if fn else None


def heading_name(text: str) -> str:
    """`calcular_total`, `` `calcular_total()` `` y `calcular_total(a, b)` valen lo mismo."""
    text = parser.heading_ident(text) or text
    text = text.replace("`", "").strip()
    return re.sub(r"\s*\(.*\)$", "", text).strip()


def documented(doc: parser.Doc) -> list[str]:
    """Nombres de los `###` dentro de `## Funciones` (vacío si no hay esa sección)."""
    names: list[str] = []
    for h in doc.headings:
        if h.level == 2 and heading_name(h.text).casefold() == FUNCTIONS_SECTION:
            names += [heading_name(x.text) for x in doc.headings if x.level == 3 and h.line < x.line < h.end]
    return names


@dataclass
class Alignment:
    rel: str
    sin_seccion: list[str] = field(default_factory=list)  # en el código, no en el gemelo
    sin_funcion: list[str] = field(default_factory=list)  # en el gemelo, ya no en el código

    def describe(self) -> str:
        parts = []
        if self.sin_seccion:
            parts.append("sin sección: " + ", ".join(self.sin_seccion))
        if self.sin_funcion:
            parts.append("sin función: " + ", ".join(self.sin_funcion))
        return "; ".join(parts)


def align(rel: str, code_text: str, doc: parser.Doc) -> Alignment | None:
    """None si cuadra o si el lenguaje no se chequea."""
    syms = extract(rel, code_text)
    if syms is None:
        return None
    in_code = list(dict.fromkeys(s.name for s in syms))  # un setter repite el nombre
    in_twin = documented(doc)
    code_set, twin_set = set(in_code), set(in_twin)
    a = Alignment(rel, [n for n in in_code if n not in twin_set], list(dict.fromkeys(n for n in in_twin if n not in code_set)))
    return a if a.sin_seccion or a.sin_funcion else None


@dataclass
class Touched:
    modificadas: list[str] = field(default_factory=list)
    nuevas: list[str] = field(default_factory=list)
    eliminadas: list[str] = field(default_factory=list)
    fuera: bool = False  # hubo cambios fuera de toda función

    def describe(self) -> str:
        parts = [f"{n} (modificada)" for n in self.modificadas]
        parts += [f"{n} (nueva)" for n in self.nuevas]
        parts += [f"{n} (eliminada)" for n in self.eliminadas]
        if self.fuera:
            parts.append("cambios fuera de funciones (revisa la descripción del archivo)")
        return ", ".join(parts) if parts else "ninguna"


def touched(rel: str, old: str, new: str) -> Touched | None:
    """Qué funciones tocó el cambio de `old` a `new`, o None si el lenguaje no se chequea."""
    old, new = old.replace("\r\n", "\n"), new.replace("\r\n", "\n")
    so, sn = extract(rel, old), extract(rel, new)
    if so is None or sn is None:
        return None
    changed_old: set[int] = set()
    changed_new: set[int] = set()
    matcher = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed_old.update(range(i1 + 1, i2 + 1))
        changed_new.update(range(j1 + 1, j2 + 1))
    names_old = {s.name for s in so}
    names_new = {s.name for s in sn}
    t = Touched()

    def hit(s: Symbol, lines: set[int]) -> bool:
        return any(s.start <= ln <= s.end for ln in lines)

    for s in sn:
        if s.name not in names_old:
            t.nuevas.append(s.name)
        elif hit(s, changed_new) and s.name not in t.modificadas:
            t.modificadas.append(s.name)
    for s in so:
        if s.name not in names_new:
            t.eliminadas.append(s.name)
        elif hit(s, changed_old) and s.name not in t.modificadas:
            t.modificadas.append(s.name)
    t.fuera = any(not any(s.start <= ln <= s.end for s in sn) for ln in changed_new) or any(
        not any(s.start <= ln <= s.end for s in so) for ln in changed_old
    )
    return t
