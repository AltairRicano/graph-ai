"""`graph multiedit`: escribe secciones de varios documentos de Estado_Proyecto en una sola llamada.

El lote llega por stdin (`graph multiedit <<'EOF'`) o por archivo (`-f lote.txt`)
y es texto plano, sin escapar nada. Cada entrada empieza con una línea
separadora y sigue con el contenido tal cual:

    === Estado_Proyecto/Estado.md#Hecho ===
    - Backend desplegado.
    === Estado_Proyecto/Decisiones.md ===
    ## dinero_en_centavos
    Por qué se guarda en centavos enteros.
    === Estado_Proyecto/Estado.md#Falta [append] ===
    - ...

- El blanco es un documento de Estado_Proyecto (`Estado_Proyecto/Estado.md` o
  solo `Estado`). El código no tiene documento: su porqué va en un comentario.
- `documento#sección` reemplaza solo esa sección; `documento#sección [append]`
  agrega al final de ella. En Decisiones y Tecnologias, una sección que no
  existe se crea como `##`.
- `documento` solo agrega el contenido al final del cuerpo. `documento [override]`
  reemplaza todo lo escrito.
- El frontmatter no viaja: el comando lo conserva y mueve `fecha_actualizacion`.
  También pone él la línea `**Elaboración:** | **Actualización:**` de cada
  sección fechada (conserva la elaboración, mueve la actualización solo si el
  texto cambió).
- Se valida todo el lote antes de escribir: con un solo error no se aplica nada.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import parser, symbols, templates
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.errors import GraphError, NotFoundError
from grafo_ia.files import ensure_writable, write_text_atomic
from grafo_ia.paths import ESTADO_DOCS, doc_path, resolve_doc

APPEND = "append"
OVERRIDE = "override"

_SEPARATOR = re.compile(r"^=== (?P<target>\S.*?)(?: \[(?P<mode>append|override)\])? ===[ \t]*$")
_DATE_LINE = re.compile(r"^\*\*Elaboración:\*\*[ \t]*(?P<elab>[^|\s]*)[ \t]*\|[ \t]*\*\*Actualización:\*\*[ \t]*(?P<act>\S*)[ \t]*$")

# nivel de heading que lleva línea de fechas, por tipo de documento (los demás no llevan)
DATED_LEVEL = {"decisiones": 2, "tecnologias": 2, "arquitectura": 3}
# documentos que crecen por entradas: una sección que no existe se crea (en los demás son fijas)
CREATES_SECTIONS = {"decisiones", "tecnologias"}


@dataclass
class Entry:
    target: str
    mode: str | None  # None = por defecto según el blanco
    content: str
    line: int  # 1-based, la del separador


@dataclass
class Plan:
    """Un documento del lote: su texto de partida y el que se va a escribir."""

    name: str
    tipo: str
    text: str
    sections: int = 0
    overrides: int = 0
    old_dates: dict = field(default_factory=dict)


# ---- lote --------------------------------------------------------------------
def parse_batch(text: str) -> tuple[list[Entry], list[str]]:
    """-> (entradas, avisos). Un separador dentro de un bloque de código no corta."""
    entries: list[Entry] = []
    warnings: list[str] = []
    current: Entry | None = None
    buf: list[str] = []
    fence: str | None = None

    def close() -> None:
        if current is not None:
            current.content = "".join(buf).strip("\n")

    for i, line in enumerate(text.splitlines(keepends=True), 1):
        raw = line.rstrip("\r\n")
        m = _SEPARATOR.match(raw)
        if fence is not None:
            stripped = raw.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            elif m:
                warnings.append(f"línea {i}: `{raw}` parece un separador pero está dentro de un bloque de código sin cerrar")
            buf.append(line)
            continue
        if m:
            close()
            current = Entry(m.group("target").strip(), m.group("mode"), "", i)
            entries.append(current)
            buf = []
            continue
        if current is None:
            if raw.strip():
                raise GraphError(f"línea {i}: hay contenido antes del primer separador `=== documento ===`")
            continue
        fm = parser._FENCE.match(raw)
        if fm:
            fence = fm.group(1)
        buf.append(line)
    close()
    if not entries:
        raise GraphError("lote vacío: cada entrada empieza con una línea `=== documento[#sección] ===`")
    return entries, warnings


# ---- fechas ------------------------------------------------------------------
def _section_body(doc: parser.Doc, h: parser.Heading) -> tuple[int | None, str]:
    """(línea de la fecha o None, texto de la sección sin heading ni fecha, normalizado)."""
    date_at = None
    for i in range(h.line + 1, h.end):
        if doc.lines[i].strip():
            if not doc.code[i] and _DATE_LINE.match(doc.lines[i].strip()):
                date_at = i
            break
    body = "".join(ln for i, ln in enumerate(doc.lines[h.line + 1 : h.end], h.line + 1) if i != date_at)
    return date_at, body.strip()


def collect_dates(text: str, level: int | None) -> dict[str, tuple[str, str, str]]:
    """nombre de sección -> (elaboración, actualización, texto); fechas vacías si no tenía línea."""
    if level is None:
        return {}
    doc = parser.parse(text)
    out = {}
    for h in doc.headings:
        if h.level != level:
            continue
        date_at, body = _section_body(doc, h)
        m = _DATE_LINE.match(doc.lines[date_at].strip()) if date_at is not None else None
        out[symbols.heading_name(h.text)] = (m.group("elab") if m else "", m.group("act") if m else "", body)
    return out


def restamp(text: str, level: int | None, today: str, old: dict[str, tuple[str, str, str]]) -> str:
    """Pone la línea de fechas de cada sección fechada; el agente nunca la escribe.

    Conserva la elaboración de una sección que ya existía y solo mueve la
    actualización si su texto cambió.
    """
    if level is None:
        return text
    doc = parser.parse(text)
    lines = list(doc.lines)
    for h in reversed(doc.headings):  # de abajo hacia arriba para no mover índices pendientes
        if h.level != level:
            continue
        date_at, body = _section_body(doc, h)
        prev = old.get(symbols.heading_name(h.text))
        if prev and not prev[0] and prev[2] == body and date_at is None:
            continue  # sección sin fechas que el lote no tocó: no se le inventa una elaboración
        elab = (prev[0] if prev else "") or today
        act = prev[1] if prev and prev[1] and prev[2] == body else today
        stamp = f"**Elaboración:** {elab} | **Actualización:** {act}\n"
        if not lines[h.line].endswith("\n"):
            lines[h.line] += "\n"
        if date_at is not None:
            lines[date_at] = stamp
            continue
        rest = lines[h.line + 1 : h.end]
        lines[h.line + 1 : h.line + 1] = [stamp] + (["\n"] if rest and rest[0].strip() else [])
    return "".join(lines)


# ---- edición -----------------------------------------------------------------
def _strip_own_heading(content: str, name: str) -> str:
    """Quita el heading si el agente lo repitió al inicio del contenido de su sección."""
    first, _, rest = content.partition("\n")
    m = parser._HEADING.match(first)
    last = name.split("#")[-1]
    if m and (parser.heading_matches((m.group(2) or "").strip(), last)
              or symbols.heading_name(m.group(2) or "") == symbols.heading_name(last)):
        return rest.strip("\n")
    return content


def _block(content: str, more_after: bool) -> list[str]:
    return [content + "\n"] + (["\n"] if more_after else [])


def _appended(head: str, body: str, block: str) -> str:
    return head + (body.rstrip("\n") + "\n\n" if body.strip() else "") + block + "\n"


def apply_entry(plan: Plan, entry: Entry, section: str | None) -> None:
    """Aplica una entrada al texto en memoria de `plan`. Lanza GraphError si no se puede."""
    doc = parser.parse(plan.text)
    lines = list(doc.lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    head = "".join(lines[: doc.body_start])
    body = "".join(lines[doc.body_start :])
    if section is None:
        if entry.mode == OVERRIDE:
            plan.text = head + entry.content + "\n"
            plan.overrides += 1
        else:
            plan.text = _appended(head, body, entry.content)
        return
    content = _strip_own_heading(entry.content, section)
    if not content.strip():
        raise GraphError("la entrada solo trae el heading, sin contenido")
    try:
        h = parser.find_section(doc, section)
    except NotFoundError as err:
        if plan.tipo in CREATES_SECTIONS and "#" not in section:
            plan.text = _appended(head, body, f"## {section}\n{content}")
            plan.sections += 1
            return
        tops = ", ".join(x.text for x in doc.headings if x.level == 2)
        raise NotFoundError(f"{err}; secciones de {plan.name}: {tops}" if tops else str(err))
    if entry.mode == APPEND:
        end = h.end
        while end > h.line + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end : h.end] = ["\n"] + _block(content, h.end < len(lines))
    else:
        lines[h.line + 1 : h.end] = _block(content, h.end < len(lines))
    plan.sections += 1
    plan.text = "".join(lines)


# ---- comando -----------------------------------------------------------------
def register(sub) -> None:
    p = sub.add_parser("multiedit", help="escribe secciones de varios documentos de Estado_Proyecto de un lote (stdin o -f)")
    p.add_argument("-f", "--file", metavar="LOTE", help="archivo con el lote (por defecto, stdin); se borra al aplicarlo")
    p.add_argument("--keep", action="store_true", help="no borrar el archivo del lote")
    p.set_defaults(func=run)


def _batch_path(args) -> Path | None:
    if not args.file:
        return None
    path = Path(args.file)
    return path if path.is_absolute() else cwd_of(args) / path


def _read_batch(args) -> str:
    path = _batch_path(args)
    if path is not None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            raise GraphError(f"no se pudo leer el lote {args.file}: {e.strerror or e}")
    if sys.stdin.isatty():
        raise GraphError("multiedit lee el lote de stdin (`graph multiedit <<'EOF'`) o de un archivo (`-f lote.txt`)")
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data


def _plan(root: Path, name: str) -> Plan:
    """Punto de partida de un documento del lote; el que falte nace de su cáscara."""
    path = doc_path(root, name)
    text = path.read_text(encoding="utf-8") if path.exists() else templates.render_estado(name)
    tipo = ESTADO_DOCS[name]
    return Plan(name, tipo, text, old_dates=collect_dates(text, DATED_LEVEL.get(tipo)))


def run(args) -> int:
    root = root_of(args)
    entries, warnings = parse_batch(_read_batch(args))
    today = templates.today()
    plans: dict[str, Plan] = {}
    errors: list[str] = []
    for e in entries:
        try:
            try:
                name, section = resolve_doc(e.target)
            except GraphError as err:
                raise GraphError(f"{err}. Lo que explica el código va en un comentario del propio código")
            if not e.content.strip():
                raise GraphError("entrada sin contenido")
            if name not in plans:
                plans[name] = _plan(root, name)
            apply_entry(plans[name], e, section)
        except GraphError as err:
            errors.append(f"línea {e.line} ({e.target}): {err}")
    if errors:
        raise GraphError("multiedit: no se aplicó nada\n" + "\n".join(f"  - {x}" for x in errors))

    for plan in plans.values():
        plan.text = templates.touch_updated(restamp(plan.text, DATED_LEVEL.get(plan.tipo), today, plan.old_dates), today)
    ensure_writable(doc_path(root, name) for name in plans)
    for name, plan in plans.items():
        write_text_atomic(doc_path(root, name), plan.text)

    if args.file and not args.keep:
        try:
            _batch_path(args).unlink()
        except OSError:
            pass
    sections = sum(p.sections for p in plans.values())
    overrides = sum(p.overrides for p in plans.values())
    extra = [x for x in (plural(sections, "sección escrita", "secciones escritas") if sections else "",
                         plural(overrides, "cuerpo reemplazado", "cuerpos reemplazados") if overrides else "") if x]
    print(f"multiedit: {plural(len(plans), 'documento escrito', 'documentos escritos')}: {', '.join(plans)}"
          + (f" ({', '.join(extra)})" if extra else ""))
    for w in warnings:
        print(f"[AVISO] {w}")
    return 0
