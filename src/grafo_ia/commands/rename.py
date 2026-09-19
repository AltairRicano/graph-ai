"""`graph rename <ruta>#<sección> <nuevo> [--links-only]`: `mv` a nivel de sección.

1. Cambia el texto del heading (mismos gatos).
2. Reescribe los `[[ruta#vieja|texto]]` de los vecinos entrantes (vía `adj_in`)
   y los `[[#vieja]]` internos del propio gemelo.
Todo o nada: calcula todo antes de escribir. No cambia aristas ni hashes, así
que no toma el lock. No cubre subsecciones encadenadas (`[[a#Sec#Sub]]`).
`--links-only`: el heading ya se renombró a mano; solo arregla los enlaces.
"""

from __future__ import annotations

import re

from grafo_ia import graph_io, parser
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.edges import Resolver, TwinCache
from grafo_ia.errors import GraphError
from grafo_ia.paths import resolve_arg, twin_path
from grafo_ia.rewrite import ensure_writable, rewrite_links, write_text_atomic

_HEADING_PREFIX = re.compile(r"^( {0,3}#{1,6})[ \t]+")


def _section_matcher(old_full: str):
    """¿El texto de sección de un enlace apunta al heading viejo?"""
    old_ident = parser.heading_ident(old_full)

    def match(section: str) -> bool:
        if section == old_full:
            return True
        if old_ident is not None and section == old_ident:
            return True
        # se pasó solo el identificador viejo y el enlace usa el texto completo
        return old_ident is None and parser.heading_ident(section) == old_full

    return match


def _new_section(link_section: str, new_full: str) -> str:
    """Conserva la forma: si el enlace usaba solo el identificador, se cambia el identificador."""
    if parser.ID_SEPARATOR in link_section:
        return new_full
    return parser.heading_ident(new_full) or new_full


def register(sub) -> None:
    p = sub.add_parser("rename", help="renombra una sección sin romper los enlaces que la apuntan")
    p.add_argument("seccion", metavar="ruta#sección")
    p.add_argument("nuevo", help="texto completo del heading nuevo")
    p.add_argument("--links-only", action="store_true", help="el heading ya se renombró; solo arreglar enlaces")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    graph = graph_io.load(root)
    t = resolve_arg(root, graph.nodes, args.seccion, cwd_of(args), allow_section=True)
    if t.node_id is None:
        raise GraphError(f"{t.rel or '.'} no está en el grafo")
    if not t.section:
        raise GraphError("falta la sección: usa <ruta>#<sección>")
    if "#" in t.section:
        raise GraphError("rename no cubre subsecciones encadenadas (a#Sec#Sub)")
    new_full = args.nuevo.strip()
    if not new_full or "#" in new_full or "|" in new_full or "]]" in new_full:
        raise GraphError("el nombre nuevo no puede estar vacío ni tener # | ]]")
    cache = TwinCache(root)
    node_id = t.node_id
    text = cache.text(node_id)
    if text is None:
        raise GraphError(f"no existe el gemelo de {t.rel}")
    doc = cache.doc(node_id)

    old_matches = parser.find_headings(doc, t.section)
    new_matches = parser.find_headings(doc, new_full)
    if args.links_only:
        if old_matches:
            raise GraphError(f"el heading '{t.section}' sigue existiendo; quita --links-only")
        if len(new_matches) != 1:
            raise GraphError(f"el heading nuevo '{new_full}' no existe una sola vez en el gemelo")
        old_full = t.section
    else:
        if not old_matches:
            raise GraphError(f"no existe la sección '{t.section}'")
        if len(old_matches) > 1:
            raise GraphError(f"la sección '{t.section}' aparece más de una vez: ambigua")
        h = doc.headings[old_matches[0]]
        if h.text == new_full:
            raise GraphError("el nombre nuevo es igual al viejo")
        new_key = parser.heading_ident(new_full) or new_full
        if new_matches or any(parser.heading_matches(x.text, new_key) for x in doc.headings if x is not h):
            raise GraphError(f"ya existe una sección '{new_full}' en el gemelo")
        old_full = h.text
        line = doc.lines[h.line]
        m = _HEADING_PREFIX.match(line)
        ending = line[len(line.rstrip("\r\n")):]
        lines = list(doc.lines)
        lines[h.line] = f"{m.group(1)} {new_full}{ending}"
        text = "".join(lines)

    matches = _section_matcher(old_full)
    resolver = Resolver(graph.nodes)
    new_texts: dict[str, str] = {}
    touched: dict[str, int] = {}
    sources = sorted(graph.adj_in.get(node_id, set()) | {node_id})
    for s in sources:
        src_text = text if s == node_id else cache.text(s)
        if src_text is None:
            continue

        def fn(link, s=s):
            if not link.section or "#" in link.section or not matches(link.section):
                return None
            target, _ = resolver.resolve(link.target, s)
            if target != node_id:
                return None
            return parser.render_link(link.target, _new_section(link.section, new_full), link.alias, link.embed)

        out, n = rewrite_links(src_text, fn)
        if n:
            touched[s] = n
        if n or (s == node_id and not args.links_only):
            new_texts[s] = out
    ensure_writable(twin_path(root, s) for s in new_texts)
    for s, out in new_texts.items():
        write_text_atomic(twin_path(root, s), out)
    if not args.links_only:
        print(f"{node_id}: '{old_full}' -> '{new_full}'")
    print(f"gemelos tocados: {len(touched)}")
    for s, n in sorted(touched.items()):
        print(f"  ~ {s} ({plural(n, 'enlace')})")
    return 0
