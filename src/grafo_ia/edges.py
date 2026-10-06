"""Resolución de enlaces `[[...]]` a nodos y regeneración de aristas.

Reglas (Schema, "Aristas" y "Regeneración de aristas"):
- Una sola arista por par (source, target); la sección no viaja en el JSON.
- Destino nuevo -> arista con ["conoce"]; destino que ya no aparece -> fuera;
  destino que sigue -> conserva sus `relaciones`.
- Enlaces estructurales (listas de un índice) y enlaces a sí mismo no son aristas.
- Un enlace que no resuelve no es arista: es "pendiente por crear".
- Nunca se toca `last_synced_hash` aquí.

Los documentos (índices y Estado_Proyecto) son el origen de toda arista; un
archivo de código solo es destino. Las líneas `[[origen]] → [[destino]]: por qué`
de un índice se leen aparte con `relations()`: son lo que `graph neighbors`
muestra de un archivo, y no cambian el JSON.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import parser
from grafo_ia.graph_io import Graph
from grafo_ia.paths import twin_path
from grafo_ia.templates import STRUCTURAL_SECTIONS

_ARROW = re.compile(r"\s*(?:→|->|=>)\s*")


class TwinCache:
    """Lee y parsea gemelos bajo demanda, una sola vez por corrida."""

    def __init__(self, root: Path):
        self.root = root
        self._text: dict[str, str | None] = {}
        self._doc: dict[str, parser.Doc | None] = {}

    def text(self, node_id: str) -> str | None:
        if node_id not in self._text:
            p = twin_path(self.root, node_id)
            try:
                self._text[node_id] = p.read_text(encoding="utf-8")
            except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
                self._text[node_id] = None
            except UnicodeDecodeError:
                self._text[node_id] = p.read_bytes().decode("utf-8", errors="replace")
        return self._text[node_id]

    def doc(self, node_id: str) -> parser.Doc | None:
        if node_id not in self._doc:
            t = self.text(node_id)
            self._doc[node_id] = parser.parse(t) if t is not None else None
        return self._doc[node_id]

    def forget(self, node_id: str) -> None:
        self._text.pop(node_id, None)
        self._doc.pop(node_id, None)

    def put(self, node_id: str, text: str) -> None:
        self._text[node_id] = text
        self._doc.pop(node_id, None)


class Resolver:
    """Traduce el destino escrito en un enlace a un id de nodo."""

    def __init__(self, ids):
        self.ids = set(ids)
        self._by_base: dict[str, list[str]] = {}
        for i in self.ids:
            self._by_base.setdefault(posixpath.basename(i), []).append(i)

    def forms(self, target: str, source_id: str) -> list[str] | None:
        t = target.replace("\\", "/").strip()
        if t.startswith("./") or t.startswith("../"):
            t = posixpath.normpath(posixpath.join(posixpath.dirname(source_id), t))
            if t.startswith(".."):
                return None
        t = t.lstrip("/")
        if not t:
            return None
        base = posixpath.basename(t)
        # exacto, con .md, y como carpeta (su índice)
        return [t, t + ".md", f"{t}/{base}.md"]

    def resolve(self, target: str, source_id: str) -> tuple[str | None, list[str]]:
        """-> (id, candidatos). id None y sin candidatos = pendiente; con varios = ambiguo."""
        if target.strip() == "":
            return source_id, [source_id]
        forms = self.forms(target, source_id)
        if not forms:
            return None, []
        for f in forms:
            if f in self.ids:
                return f, [f]
        if target.startswith("./") or target.startswith("../"):
            return None, []
        cands = set()
        for f in forms:
            for i in self._by_base.get(posixpath.basename(f), ()):
                if i.endswith("/" + f):
                    cands.add(i)
        cands_l = sorted(cands)
        if len(cands_l) == 1:
            return cands_l[0], cands_l
        return None, cands_l


@dataclass
class LinkScan:
    resolved: list[tuple[parser.Link, str]] = field(default_factory=list)
    pending: list[tuple[parser.Link, str]] = field(default_factory=list)  # (enlace, razón)
    ambiguous: list[tuple[parser.Link, list[str]]] = field(default_factory=list)
    no_alias: list[parser.Link] = field(default_factory=list)
    structural: list[tuple[parser.Link, str | None]] = field(default_factory=list)

    def targets(self, source_id: str) -> set[str]:
        return {t for _, t in self.resolved if t != source_id}


def is_structural(graph: Graph, source_id: str, doc: parser.Doc, link: parser.Link) -> bool:
    if graph.tipo(source_id) != "indice" or link.heading is None:
        return False
    # la sección de nivel <= 2 que contiene el enlace
    top = None
    for h in doc.headings:
        if h.line > link.line:
            break
        if h.level <= 2 and h.end > link.line:
            top = h
    return top is not None and top.level == 2 and top.text in STRUCTURAL_SECTIONS


def code_has_name(root: Path, rel: str, name: str) -> bool:
    """¿El nombre de un enlace `archivo#función` sigue apareciendo en el archivo? Vale para cualquier lenguaje."""
    last = name.replace("`", "").strip().split("(")[0].split(".")[-1].strip()
    if not last:
        return True
    try:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return re.search(rf"(?<!\w){re.escape(last)}(?!\w)", text) is not None


def scan_links(graph: Graph, resolver: Resolver, cache: TwinCache, source_id: str, check_sections: bool = True,
               root: Path | None = None) -> LinkScan:
    """`root` hace falta para comprobar las secciones de enlaces a código (`archivo#función`)."""
    out = LinkScan()
    doc = cache.doc(source_id)
    if doc is None:
        return out
    for link in parser.links(doc):
        target_id, cands = resolver.resolve(link.target, source_id)
        if is_structural(graph, source_id, doc, link):
            out.structural.append((link, target_id))
            continue
        if link.alias is None:
            out.no_alias.append(link)
        if target_id is None:
            if cands:
                out.ambiguous.append((link, cands))
            else:
                out.pending.append((link, "no existe el destino"))
            continue
        if root is not None and graph.tipo(target_id) == "codigo" and not (root / target_id).is_file():
            # el nodo sigue en el grafo hasta la próxima reconciliación, pero el archivo ya no está
            out.pending.append((link, f"{target_id} ya no existe"))
        elif check_sections and link.section:
            if graph.tipo(target_id) == "codigo":
                if root is not None and not code_has_name(root, target_id, link.section):
                    out.pending.append((link, f"'{link.section}' ya no aparece en {target_id}"))
            else:
                tdoc = cache.doc(target_id)
                if tdoc is None or not parser.has_section(tdoc, link.section):
                    out.pending.append((link, f"no existe la sección '{link.section}'"))
        out.resolved.append((link, target_id))
    return out


@dataclass
class Relation:
    """Una línea `[[origen]] → [[destino]]: por qué` de un índice."""

    source: str  # id del nodo origen
    target: str
    why: str
    declared_in: str  # id del índice
    heading: str | None
    line: int  # 0-based


def relations(graph: Graph, resolver: Resolver, cache: TwinCache, index_id: str) -> list[Relation]:
    """Relaciones declaradas en un documento: líneas con dos enlaces unidos por una flecha."""
    doc = cache.doc(index_id)
    if doc is None:
        return []
    by_line: dict[int, list[parser.Link]] = {}
    for link in parser.links(doc):
        if not is_structural(graph, index_id, doc, link):
            by_line.setdefault(link.line, []).append(link)
    out = []
    for line, found in sorted(by_line.items()):
        if len(found) < 2:
            continue
        a, b = found[0], found[1]
        text = doc.lines[line]
        if not _ARROW.fullmatch(text[a.end:b.start]):
            continue
        src, _ = resolver.resolve(a.target, index_id)
        dst, _ = resolver.resolve(b.target, index_id)
        if src is None or dst is None:
            continue
        why = text[b.end:].strip().lstrip(":").strip()
        heading = doc.headings[a.heading].text if a.heading is not None else None
        out.append(Relation(src, dst, why, index_id, heading, line))
    return out


def regenerate(graph: Graph, cache: TwinCache, node_id: str, resolver: Resolver | None = None) -> tuple[set[str], set[str]]:
    """Recalcula las aristas salientes de un nodo desde su gemelo. -> (agregadas, quitadas)."""
    resolver = resolver or Resolver(graph.nodes)
    new = scan_links(graph, resolver, cache, node_id, check_sections=False).targets(node_id)
    old = set(graph.adj_out.get(node_id, set()))
    for t in old - new:
        graph.remove_edge(node_id, t)
    for t in new - old:
        graph.set_edge(node_id, t, None)
    return new - old, old - new


def resolve_pending(graph: Graph, cache: TwinCache, new_ids) -> list[tuple[str, str]]:
    """Agrega aristas desde gemelos cuyos enlaces pendientes ahora resuelven a un nodo nuevo."""
    new_ids = set(new_ids)
    if not new_ids:
        return []
    resolver = Resolver(graph.nodes)
    added = []
    for source_id in sorted(graph.nodes):
        if source_id in new_ids:
            continue
        doc = cache.doc(source_id)
        if doc is None or "[[" not in doc.text:
            continue
        for t in scan_links(graph, resolver, cache, source_id, check_sections=False).targets(source_id):
            if t in new_ids and graph.relations(source_id, t) is None:
                graph.set_edge(source_id, t, None)
                added.append((source_id, t))
    return added
