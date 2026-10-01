"""`graph multiedit`: escribe el cuerpo de varios gemelos en una sola llamada.

El lote llega por stdin (`graph multiedit <<'EOF'`) o por archivo (`-f lote.txt`)
y es texto plano, sin escapar nada. Cada entrada empieza con una línea
separadora y sigue con el contenido tal cual:

    === src/pagos/cobro.go ===
    Descripción del archivo y sus secciones.
    === src/pagos/cobro.go#calcular_total ===
    Cuerpo nuevo de esa sección (sin repetir el heading).
    === Estado_Proyecto/Estado.md#Hecho [override] ===
    - ...

- Las rutas son del proyecto y **desde la raíz**, igual que en el resto del CLI.
- `ruta` sola agrega el contenido al final del cuerpo (en un gemelo vacío es
  lo mismo que escribirlo). `ruta [override]` reemplaza el cuerpo completo.
- `ruta#sección` reemplaza solo esa sección; `ruta#sección [append]` agrega al
  final de ella. En un gemelo de código, una sección que no existe se crea como
  `###` dentro de `## Funciones`.
- El frontmatter nunca viaja en el lote: el comando lo conserva y mueve
  `fecha_actualizacion`. También pone él la línea `**Elaboración:** |
  **Actualización:**` de cada sección fechada (conserva la elaboración, mueve
  la actualización solo si el texto cambió).
- Un archivo de código que existe pero todavía no está en el grafo se agrega solo.
- Se valida todo el lote antes de escribir: con un solo error no se aplica nada.
- Al terminar confirma la sincronía de cada gemelo (lo que hace `graph update`)
  y reporta enlaces rotos, funciones sin sección y gemelos demasiado largos.

Agregar a un gemelo desactualizado se rechaza: quedaría marcado al día con las
secciones viejas intactas. Ahí toca `ruta#sección` o `[override]`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import graph_io, parser, states, symbols, templates, trivial
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.commands.update import confirm
from grafo_ia.edges import Resolver, TwinCache, scan_links
from grafo_ia.errors import GraphError, NotFoundError
from grafo_ia.exclusion import Exclusion
from grafo_ia.paths import Target, code_id, resolve_arg, twin_path
from grafo_ia.reconciliation import reconcile
from grafo_ia.rewrite import ensure_writable, write_text_atomic

APPEND = "append"
OVERRIDE = "override"

_SEPARATOR = re.compile(r"^=== (?P<target>\S.*?)(?: \[(?P<mode>append|override)\])? ===[ \t]*$")
_DATE_LINE = re.compile(r"^\*\*Elaboración:\*\*[ \t]*(?P<elab>[^|\s]*)[ \t]*\|[ \t]*\*\*Actualización:\*\*[ \t]*(?P<act>\S*)[ \t]*$")

# nivel de heading que lleva línea de fechas, por tipo de gemelo (los demás no llevan)
DATED_LEVEL = {"codigo": 3, "decisiones": 2, "tecnologias": 2, "arquitectura": 3}

MAX_LISTED = 15


@dataclass
class Entry:
    target: str
    mode: str | None  # None = por defecto según el blanco
    content: str
    line: int  # 1-based, la del separador


@dataclass
class Plan:
    """Un gemelo del lote: su texto de partida y el que se va a escribir."""

    target: Target
    tipo: str
    text: str
    new: bool = False  # el archivo existe pero aún no está en el grafo
    stale: bool = False  # desactualizado antes del lote
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
            plan.text = head + (body.rstrip("\n") + "\n\n" if body.strip() else "") + entry.content + "\n"
        return
    content = _strip_own_heading(entry.content, section)
    if not content.strip():
        raise GraphError("la entrada solo trae el heading, sin contenido")
    try:
        h = parser.find_section(doc, section)
    except NotFoundError:
        if plan.tipo != "codigo" or "#" in section:
            raise
        _new_function(plan, lines, doc, section, content)
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


def _new_function(plan: Plan, lines: list[str], doc: parser.Doc, name: str, content: str) -> None:
    """Sección nueva en un gemelo de código: `### nombre` al final de `## Funciones`."""
    block = [f"### {name}\n"] + _block(content, False)
    funcs = next((h for h in doc.headings
                  if h.level == 2 and symbols.heading_name(h.text).casefold() == symbols.FUNCTIONS_SECTION), None)
    if funcs is None:
        while lines and not lines[-1].strip() and len(lines) > doc.body_start:
            lines.pop()
        sep = ["\n"] if len(lines) > doc.body_start else []
        lines += sep + ["## Funciones\n", "\n"] + block
    else:
        end = funcs.end
        while end > funcs.line + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end : funcs.end] = ["\n"] + block + (["\n"] if funcs.end < len(lines) else [])
    plan.sections += 1
    plan.text = "".join(lines)


# ---- comando -----------------------------------------------------------------
def register(sub) -> None:
    p = sub.add_parser("multiedit", help="escribe el cuerpo de varios gemelos de un lote (stdin o -f) y los confirma")
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
    trivial_rules = trivial.load_rules(root)
    with graph_io.transaction(root) as graph:
        exclusion = Exclusion(root)
        plans: dict[str, Plan] = {}
        errors: list[str] = []
        for e in entries:
            where = f"línea {e.line} ({e.target})"
            try:
                t = resolve_arg(root, graph.nodes, e.target, root, allow_section=True)
                if not e.content.strip():
                    raise GraphError("entrada sin contenido")
                node_id = t.node_id or code_id(t.rel)
                plan = plans.get(node_id)
                if plan is None:
                    plan = _plan(root, graph, cache, exclusion, t, trivial_rules)
                    plans[node_id] = plan
                if plan.stale and t.section is None and e.mode != OVERRIDE:
                    raise GraphError("el gemelo está desactualizado: agregar al final lo dejaría marcado al día con "
                                     "secciones viejas. Usa `ruta#sección` para lo que cambió (`graph diff --symbols`) "
                                     "o `[override]` para reescribirlo")
                apply_entry(plan, e, t.section)
            except GraphError as err:
                errors.append(f"{where}: {err}")
        if errors:
            raise GraphError("multiedit: no se aplicó nada\n" + "\n".join(f"  - {x}" for x in errors))

        for plan in plans.values():
            level = DATED_LEVEL.get(plan.tipo)
            plan.text = templates.touch_updated(restamp(plan.text, level, today, plan.old_dates), today)
        ensure_writable(twin_path(root, nid) for nid in plans)
        for rel in sorted({p.target.rel for p in plans.values() if p.new}):
            reconcile(root, graph, rel, exclusion)
            populate(root, graph, rel)
        for node_id, plan in plans.items():
            if node_id not in graph.nodes:
                raise GraphError(f"{plan.target.rel} no entró al grafo; revisa `graph add {plan.target.rel}`")
            write_text_atomic(twin_path(root, node_id), plan.text)
            cache.put(node_id, plan.text)
        resolver = Resolver(graph.nodes)
        for node_id, plan in plans.items():
            t = plan.target
            confirm(root, graph, cache, Target(t.rel, node_id, "codigo" if plan.tipo == "codigo" else "estado"), resolver)

        broken, misaligned, long = [], [], []
        for node_id, plan in plans.items():
            scan = scan_links(graph, resolver, cache, node_id)
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} ({reason})" for ln, reason in scan.pending]
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} (ambiguo: {', '.join(c)})" for ln, c in scan.ambiguous]
            broken += [f"{node_id}:{ln.line + 1} {ln.raw} (sin texto a mostrar)" for ln in scan.no_alias]
            if plan.tipo == "codigo":
                a = states.alignment(root, plan.target.rel, cache)
                if a is not None:
                    misaligned.append(f"{a.rel}: {a.describe()}")
                size = states.twin_size(root, plan.target.rel, cache)
                if size is not None:
                    long.append(f"{plan.target.rel}: {size[0]} caracteres de gemelo, {size[1]} de código")

    if args.file and not args.keep:
        try:
            _batch_path(args).unlink()
        except OSError:
            pass
    sections = sum(p.sections for p in plans.values())
    overrides = sum(p.overrides for p in plans.values())
    extra = [x for x in (plural(sections, "sección escrita", "secciones escritas") if sections else "",
                         plural(overrides, "cuerpo reemplazado", "cuerpos reemplazados") if overrides else "",
                         plural(sum(p.new for p in plans.values()), "archivo agregado al grafo", "archivos agregados al grafo")
                         if any(p.new for p in plans.values()) else "") if x]
    print(f"multiedit: {plural(len(plans), 'gemelo escrito y sincronizado', 'gemelos escritos y sincronizados')}"
          + (f" ({', '.join(extra)})" if extra else ""))
    for w in warnings:
        print(f"[AVISO] {w}")
    if broken:
        _listed("enlaces por corregir", broken)
    if misaligned:
        _listed("secciones desalineadas con el código", misaligned)
    if long:
        _listed("gemelos más largos que su código (toca consolidar)", long)
    return 0


def _plan(root: Path, graph, cache: TwinCache, exclusion: Exclusion, t: Target, trivial_rules: list[str]) -> Plan:
    """Punto de partida de un gemelo del lote; valida que se pueda escribir."""
    if t.kind == "indice":
        raise GraphError("es una carpeta: los índices los mantiene `populate`, no se escriben con multiedit")
    if t.node_id is None:
        if not (root / t.rel).is_file():
            raise GraphError("no existe en el proyecto ni en el grafo")
        if not exclusion.is_included(t.rel, False):
            raise GraphError(f"está excluido del grafo ({exclusion.check(t.rel, False)[1]})")
        return Plan(t, "codigo", templates.render_code_shell(), new=True)
    tipo = graph.nodes[t.node_id]["tipo"]
    text = cache.text(t.node_id)
    if tipo == "codigo":
        if not (root / t.rel).is_file():
            raise GraphError("el código ya no existe: su gemelo es huérfano (`graph prune` o `graph remove`)")
        if text is None:
            text = templates.render_code_shell()
        # un gemelo escrito a mano y nunca confirmado no "miente" todavía: solo cuenta el que ya se confirmó
        node = graph.nodes[t.node_id]
        stale = bool(node.get("last_synced_hash")) and (
            states.code_state(root, node, cache, trivial_rules=trivial_rules) == states.DESACTUALIZADO)
    else:
        if text is None:
            raise GraphError("el documento todavía no existe (usa `graph populate`)")
        stale = False
    return Plan(t, tipo, text, stale=stale, old_dates=collect_dates(text, DATED_LEVEL.get(tipo)))
