"""`graph multiedit`: escribe secciones de varios índices y documentos en una sola llamada.

El lote llega por stdin (`graph multiedit <<'EOF'`) o por archivo (`-f lote.txt`)
y es texto plano, sin escapar nada. Cada entrada empieza con una línea
separadora y sigue con el contenido tal cual:

    === src/pagos#Propósito ===
    Para qué existe el módulo y cómo impacta al proyecto.
    === src/pagos ===
    ## Redondeo de centavos
    Una regla que cruza varios archivos de la carpeta.
    === Estado_Proyecto/Estado.md#Hecho [append] ===
    - ...

- El blanco es una carpeta (su índice) o un documento de Estado_Proyecto, con la
  ruta **desde la raíz**. Un archivo de código no es un blanco: no tiene
  documento, su porqué va en un comentario del propio código.
- `ruta#sección` reemplaza solo esa sección; `ruta#sección [append]` agrega al
  final de ella. En un índice, una sección que no existe se crea como `##`.
- `ruta` sola agrega el contenido al final del cuerpo. `ruta [override]`
  reemplaza todo lo escrito; en un índice se conservan las listas de carpetas
  y archivos, que nunca viajan en el lote.
- El frontmatter tampoco viaja: el comando lo conserva y mueve
  `fecha_actualizacion`. También pone él la línea `**Elaboración:** |
  **Actualización:**` de cada sección fechada (conserva la elaboración, mueve
  la actualización solo si el texto cambió).
- Antes de leer el lote reconcilia el proyecto: las carpetas y archivos nuevos
  entran solos al grafo y las listas de los índices quedan al día.
- Se valida todo el lote antes de escribir: con un solo error no se aplica nada.
- Al terminar confirma cada índice (lo que hace `graph update`) y reporta
  enlaces por corregir, índices demasiado largos y los que siguen incompletos.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import graph_io, parser, states, symbols, templates
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.commands.update import confirm
from grafo_ia.edges import Resolver, TwinCache, scan_links
from grafo_ia.errors import GraphError, NotFoundError
from grafo_ia.exclusion import Exclusion
from grafo_ia.paths import ESTADO_INDEX_ID, Target, resolve_arg, twin_path
from grafo_ia.reconciliation import reconcile
from grafo_ia.rewrite import ensure_writable, write_text_atomic

APPEND = "append"
OVERRIDE = "override"

_SEPARATOR = re.compile(r"^=== (?P<target>\S.*?)(?: \[(?P<mode>append|override)\])? ===[ \t]*$")
_DATE_LINE = re.compile(r"^\*\*Elaboración:\*\*[ \t]*(?P<elab>[^|\s]*)[ \t]*\|[ \t]*\*\*Actualización:\*\*[ \t]*(?P<act>\S*)[ \t]*$")

# nivel de heading que lleva línea de fechas, por tipo de documento (los demás no llevan)
DATED_LEVEL = {"indice": 2, "decisiones": 2, "tecnologias": 2, "arquitectura": 3}

MAX_LISTED = 15


@dataclass
class Entry:
    target: str
    mode: str | None  # None = por defecto según el blanco
    content: str
    line: int  # 1-based, la del separador


@dataclass
class Plan:
    """Un documento del lote: su texto de partida y el que se va a escribir."""

    target: Target
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
                raise GraphError(f"línea {i}: hay contenido antes del primer separador `=== ruta ===`")
            continue
        fm = parser._FENCE.match(raw)
        if fm:
            fence = fm.group(1)
        buf.append(line)
    close()
    if not entries:
        raise GraphError("lote vacío: cada entrada empieza con una línea `=== ruta[#sección] ===`")
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
        if h.level != level or h.text in templates.STRUCTURAL_SECTIONS:
            continue  # las listas de un índice no son contenido: no se fechan
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
            plan.text = head + entry.content + "\n" + (_structural_tail(doc) if plan.tipo == "indice" else "")
            plan.overrides += 1
        elif plan.tipo == "indice":
            _insert_before_lists(plan, lines, doc, [entry.content + "\n"])
        else:
            plan.text = head + (body.rstrip("\n") + "\n\n" if body.strip() else "") + entry.content + "\n"
        return
    if plan.tipo == "indice" and section.strip() in templates.STRUCTURAL_SECTIONS:
        raise GraphError("las listas de carpetas y archivos las mantiene el CLI: no se escriben")
    content = _strip_own_heading(entry.content, section)
    if not content.strip():
        raise GraphError("la entrada solo trae el heading, sin contenido")
    try:
        h = parser.find_section(doc, section)
    except NotFoundError:
        if plan.tipo != "indice" or "#" in section:
            raise
        _new_section(plan, lines, doc, section, content)
        return
    if entry.mode == APPEND:
        end = h.end
        while end > h.line + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end : h.end] = ["\n"] + _block(content, h.end < len(lines))
    else:
        lines[h.line + 1 : h.end] = _block(content, h.end < len(lines))
    plan.sections += 1
    plan.text = "".join(lines)


def _structural_tail(doc: parser.Doc) -> str:
    """Las listas `📁 Carpetas` / `📄 Archivos` tal como están, para conservarlas en un `[override]`."""
    out = ""
    for h in doc.headings:
        if h.level == 2 and h.text in templates.STRUCTURAL_SECTIONS:
            end = next((x.line for x in doc.headings if x.line > h.line), len(doc.lines))
            out += "\n" + "".join(doc.lines[h.line:end]).rstrip("\n") + "\n"
    return out


def _insert_before_lists(plan: Plan, lines: list[str], doc: parser.Doc, block: list[str]) -> None:
    """Agrega al reporte de un índice sin caer dentro de sus listas, que van siempre al final.

    Lo que quedara debajo de `📄 Archivos` sería parte de esa lista y `populate` lo borraría.
    """
    at = min((h.line for h in doc.headings if h.level == 2 and h.text in templates.STRUCTURAL_SECTIONS), default=len(lines))
    start = at
    while start > doc.body_start and not lines[start - 1].strip():
        start -= 1
    before = ["\n"] if start > doc.body_start else []
    lines[start:at] = before + block + (["\n"] if at < len(lines) else [])
    plan.text = "".join(lines)


def _new_section(plan: Plan, lines: list[str], doc: parser.Doc, name: str, content: str) -> None:
    """Sección nueva en un índice: `## nombre` antes de las listas, o arriba de todo si es el propósito."""
    block = [f"## {name}\n"] + _block(content, False)
    if parser.heading_matches(name, templates.INDEX_PURPOSE):
        more = any(ln.strip() for ln in lines[doc.body_start:])
        lines[doc.body_start:doc.body_start] = block + (["\n"] if more else [])
        plan.text = "".join(lines)
    else:
        _insert_before_lists(plan, lines, doc, block)
    plan.sections += 1


# ---- comando -----------------------------------------------------------------
def register(sub) -> None:
    p = sub.add_parser("multiedit", help="escribe secciones de varios índices y documentos de un lote (stdin o -f) y los confirma")
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


def _listed(title: str, items: list[str]) -> None:
    print(f"[AVISO] {title} ({len(items)})")
    for item in items[:MAX_LISTED]:
        print(f"  {item}")
    if len(items) > MAX_LISTED:
        print(f"  ... y {len(items) - MAX_LISTED} más (`graph incomplete`)")


def run(args) -> int:
    root = root_of(args)
    entries, warnings = parse_batch(_read_batch(args))
    cache = TwinCache(root)
    today = templates.today()
    with graph_io.transaction(root) as graph:
        exclusion = Exclusion(root)
        # lo nuevo entra solo y las listas quedan al día antes de tocar ningún índice
        changes = reconcile(root, graph, "", exclusion, cache)
        populate(root, graph)
        cache = TwinCache(root)  # populate reescribió listas en disco: lo leído antes ya no vale
        plans: dict[str, Plan] = {}
        errors: list[str] = []
        for e in entries:
            where = f"línea {e.line} ({e.target})"
            try:
                t = resolve_arg(root, graph.nodes, e.target, root, allow_section=True)
                if not e.content.strip():
                    raise GraphError("entrada sin contenido")
                plan = plans.get(t.node_id) if t.node_id else None
                if plan is None:
                    plan = _plan(root, graph, cache, exclusion, t)
                    plans[t.node_id] = plan
                apply_entry(plan, e, t.section)
            except GraphError as err:
                errors.append(f"{where}: {err}")
        if errors:
            raise GraphError("multiedit: no se aplicó nada\n" + "\n".join(f"  - {x}" for x in errors))

        for plan in plans.values():
            level = DATED_LEVEL.get(plan.tipo)
            plan.text = templates.touch_updated(restamp(plan.text, level, today, plan.old_dates), today)
        ensure_writable(twin_path(root, nid) for nid in plans)
        for node_id, plan in plans.items():
            write_text_atomic(twin_path(root, node_id), plan.text)
            cache.put(node_id, plan.text)
        resolver = Resolver(graph.nodes)
        for node_id, plan in plans.items():
            confirm(root, graph, cache, Target(plan.target.rel, node_id, plan.target.kind), resolver, exclusion)

        broken = []
        for node_id in plans:
            scan = scan_links(graph, resolver, cache, node_id, root=root)
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} ({reason})" for ln, reason in scan.pending]
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} (ambiguo: {', '.join(c)})" for ln, c in scan.ambiguous]
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} (sin texto a mostrar)" for ln in scan.no_alias]
        folders = [p.target.rel for p in plans.values() if p.tipo == "indice"]
        rep = states.report(root, graph, None, cache, links=True, check_size=True) if folders else states.Report()
        pending = rep.describe([r for r in rep.faltantes + rep.desactualizados if r in folders])
        long = [f"{rel or '.'}: {size} caracteres de índice, {code} de código" for rel, size, code in rep.extensos if rel in folders]

    if args.file and not args.keep:
        try:
            _batch_path(args).unlink()
        except OSError:
            pass
    sections = sum(p.sections for p in plans.values())
    overrides = sum(p.overrides for p in plans.values())
    added = [n for n in changes.added if graph.tipo(n) in ("codigo", "indice")]
    extra = [x for x in (plural(sections, "sección escrita", "secciones escritas") if sections else "",
                         plural(overrides, "cuerpo reemplazado", "cuerpos reemplazados") if overrides else "",
                         plural(len(added), "nodo nuevo en el grafo", "nodos nuevos en el grafo") if added else "") if x]
    print(f"multiedit: {plural(len(plans), 'documento escrito y confirmado', 'documentos escritos y confirmados')}"
          + (f" ({', '.join(extra)})" if extra else ""))
    for w in warnings:
        print(f"[AVISO] {w}")
    if broken:
        _listed("enlaces por corregir", broken)
    if pending:
        _listed("índices que siguen incompletos", pending)
    if long:
        _listed("índices más largos que el código de su carpeta (repiten lo que el código ya dice)", long)
    return 0


def _plan(root: Path, graph, cache: TwinCache, exclusion: Exclusion, t: Target) -> Plan:
    """Punto de partida de un documento del lote; valida que se pueda escribir."""
    if t.kind == "codigo":
        raise GraphError("es un archivo de código: no tiene documento. Su porqué va en un comentario del propio "
                         "archivo; lo que cruza archivos, en el índice de su carpeta (`=== carpeta#Sección ===`)")
    if t.node_id is None:
        if not (root / t.rel).exists():
            raise GraphError("no existe en el proyecto ni en el grafo")
        raise GraphError(f"está excluido del grafo ({exclusion.check(t.rel, (root / t.rel).is_dir())[1]})")
    if t.node_id == ESTADO_INDEX_ID:
        raise GraphError("el índice de Estado_Proyecto solo lleva listas: escribe en uno de sus documentos")
    tipo = graph.nodes[t.node_id]["tipo"]
    if tipo == "indice" and not (root / t.rel).is_dir():
        raise GraphError("la carpeta ya no existe: su índice es huérfano (`graph prune` o `graph remove`)")
    text = cache.text(t.node_id)
    if text is None:
        raise GraphError("el documento todavía no existe (usa `graph populate`)")
    return Plan(t, tipo, text, old_dates=collect_dates(text, DATED_LEVEL.get(tipo)))
