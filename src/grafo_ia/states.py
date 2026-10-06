"""Estados de sincronía de los índices de carpeta y las listas de `graph incomplete`.

El estado es de la carpeta, no de cada archivo, y nunca se guarda: se calcula al
vuelo comparando el índice con el filesystem.
- huérfano: la carpeta ya no existe (y su índice sigue en el grafo)
- faltante: el índice no existe o su `## Propósito` está vacío
- trivial: sin propósito, pero la carpeta no tiene archivos propios que lo pidan
  (ninguno, o todos caen en `.graph/trivial`)
- desactualizado: desde la última confirmación a la carpeta le entraron o salieron
  archivos, o un enlace del índice dejó de resolver
- ok: todo lo demás
Editar el cuerpo de un archivo no cambia el estado: el hash de cada archivo solo
sirve para que `graph diff` diga cuáles se modificaron.
`incomplete`, `status` y los hooks usan `report()`, así los números cuadran.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia import parser, trivial
from grafo_ia.edges import Resolver, TwinCache, scan_links
from grafo_ia.exclusion import Exclusion, Scan, walk
from grafo_ia.graph_io import Graph
from grafo_ia.hashing import hash_file
from grafo_ia.paths import ESTADO_DIR, folder_id, is_estado, is_under, parent_rel, project_rel
from grafo_ia.templates import INDEX_PURPOSE, STRUCTURAL_SECTIONS

OK = "ok"
DESACTUALIZADO = "desactualizado"
FALTANTE = "faltante"
HUERFANO = "huérfano"
TRIVIAL = "trivial"

CONFIRMED = "archivos_confirmados"  # atributo del nodo índice: archivos directos al confirmar

# un índice es "extenso" si su cuerpo pasa de este piso y además pesa más que el código de su carpeta
EXTENSO_MIN_CHARS = 4000


@dataclass
class PendingRef:
    source: str
    line: int  # 1-based
    link: str
    reason: str


@dataclass
class FolderState:
    rel: str  # carpeta ("" = raíz)
    state: str
    reasons: list[str] = field(default_factory=list)
    entered: list[str] = field(default_factory=list)  # nombres de archivo
    left: list[str] = field(default_factory=list)

    @property
    def shown(self) -> str:
        return self.rel or "."

    def describe(self) -> str:
        return f"{self.shown}: {'; '.join(self.reasons)}" if self.reasons else self.shown


@dataclass
class Report:
    ok: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    desactualizados: list[str] = field(default_factory=list)
    pendientes: list[PendingRef] = field(default_factory=list)
    huerfanos: list[str] = field(default_factory=list)
    ambiguos: list[PendingRef] = field(default_factory=list)
    sin_alias: list[PendingRef] = field(default_factory=list)
    triviales: list[str] = field(default_factory=list)
    extensos: list[tuple[str, int, int]] = field(default_factory=list)  # (carpeta, chars del índice, chars del código)
    folders: dict[str, FolderState] = field(default_factory=dict)

    def describe(self, rels: list[str]) -> list[str]:
        return [self.folders[r].describe() if r in self.folders else (r or ".") for r in rels]


def twin_has_content(cache: TwinCache, node_id: str) -> bool:
    text = cache.text(node_id)
    return text is not None and not parser.is_empty(text)


def _body_without_dates(doc: parser.Doc, lo: int, hi: int) -> str:
    return "".join(ln for ln in doc.lines[lo:hi] if not ln.lstrip().startswith("**Elaboración:**")).strip()


def has_purpose(doc: parser.Doc | None) -> bool:
    """¿El índice tiene `## Propósito` con algo escrito?"""
    if doc is None:
        return False
    for h in doc.headings:
        if h.level == 2 and parser.heading_matches(h.text, INDEX_PURPOSE):
            return bool(_body_without_dates(doc, h.line + 1, h.end))
    return False


def index_has_content(cache: TwinCache, node_id: str) -> bool:
    """¿Alguien escribió algo en el índice, fuera de las listas estructurales y los headings?"""
    doc = cache.doc(node_id)
    if doc is None:
        return False
    skip = set()
    for h in doc.headings:
        skip.add(h.line)
        if h.level == 2 and h.text in STRUCTURAL_SECTIONS:
            end = next((x.line for x in doc.headings if x.line > h.line), len(doc.lines))
            skip.update(range(h.line, end))
    return any(ln.strip() for i, ln in enumerate(doc.lines[doc.body_start:], doc.body_start) if i not in skip)


def disk_files(scan: Scan) -> dict[str, list[str]]:
    """carpeta -> nombres de sus archivos directos incluidos en el grafo."""
    out: dict[str, list[str]] = {}
    for f in scan.files:
        if f.split("/")[0] == ESTADO_DIR:
            continue
        out.setdefault(parent_rel(f), []).append(posixpath.basename(f))
    for d in scan.dirs:
        if d.split("/")[0] != ESTADO_DIR:
            out.setdefault(d, [])
    out.setdefault("", [])
    return out


def folder_files(root: Path, rel: str, exclusion: Exclusion | None = None) -> list[str]:
    """Archivos directos de una carpeta que entran al grafo (lo que se confirma)."""
    exclusion = exclusion or Exclusion(root)
    base = root / rel if rel else root
    try:
        names = sorted(p.name for p in base.iterdir() if p.is_file())
    except OSError:
        return []
    return [n for n in names if exclusion.is_included(join(rel, n), False)]


def join(rel: str, name: str) -> str:
    return f"{rel}/{name}" if rel else name


def folder_state(root: Path, graph: Graph, cache: TwinCache, rel: str, files: list[str] | None,
                 trivial_rules: list[str], broken_links: int = 0) -> FolderState:
    """Estado del índice de `rel`. `files` son sus archivos directos en disco (None = la carpeta no existe)."""
    nid = folder_id(rel)
    node = graph.nodes.get(nid)
    if files is None:
        return FolderState(rel, HUERFANO, ["la carpeta ya no existe (`graph prune`)"])
    nontrivial = [n for n in files if not trivial.is_trivial(trivial_rules, join(rel, n))]
    if not has_purpose(cache.doc(nid)):
        if not nontrivial:
            return FolderState(rel, TRIVIAL)
        why = "sin `## Propósito`" if node is not None else "aún no está en el grafo; sin `## Propósito`"
        return FolderState(rel, FALTANTE, [why])
    st = FolderState(rel, OK)
    confirmed = node.get(CONFIRMED) if node else None
    if confirmed is None:
        st.state = DESACTUALIZADO
        st.reasons.append("nunca se confirmó (`graph update`)")
    else:
        st.entered = sorted(set(nontrivial) - set(confirmed))
        st.left = sorted(n for n in set(confirmed) - set(files) if not trivial.is_trivial(trivial_rules, join(rel, n)))
        if st.entered:
            st.reasons.append("entraron: " + ", ".join(st.entered))
        if st.left:
            st.reasons.append("salieron: " + ", ".join(st.left))
        if st.entered or st.left:
            st.state = DESACTUALIZADO
    if broken_links:
        st.state = DESACTUALIZADO
        st.reasons.append("1 enlace que no resuelve" if broken_links == 1 else f"{broken_links} enlaces que no resuelven")
    return st


def modified_files(root: Path, graph: Graph, rel: str, files: list[str]) -> list[str]:
    """Archivos de la carpeta cuyo contenido cambió desde la última confirmación del índice."""
    out = []
    for n in files:
        node = graph.nodes.get(join(rel, n))
        old = node.get("last_synced_hash") if node else None
        if not old:
            continue
        try:
            if hash_file(root / join(rel, n)) != old:
                out.append(n)
        except OSError:
            continue
    return out


def index_size(root: Path, cache: TwinCache, rel: str, files: list[str]) -> tuple[int, int] | None:
    """(chars del cuerpo del índice, chars del código de la carpeta) si el índice es extenso; None si no."""
    doc = cache.doc(folder_id(rel))
    if doc is None or not files:
        return None
    body = len("".join(doc.lines[doc.body_start:]))
    if body < EXTENSO_MIN_CHARS:
        return None
    code = 0
    for n in files:
        try:
            code += (root / join(rel, n)).stat().st_size
        except OSError:
            continue
    return (body, code) if body > code else None


def scope_folders(root: Path, scopes: list[str] | None) -> tuple[set[str], list[str]] | None:
    """Rutas pedidas -> (carpetas exactas, subárboles). Un archivo pide la carpeta que lo contiene."""
    if scopes is None:
        return None
    exact, trees = set(), []
    for s in scopes:
        if s == "":
            return None
        if (root / s).is_dir():
            trees.append(s)
        else:
            exact.add(parent_rel(s))
    return exact, trees


def _in_scope(rel: str, scope: tuple[set[str], list[str]] | None) -> bool:
    if scope is None:
        return True
    exact, trees = scope
    return rel in exact or any(is_under(rel, t) for t in trees)


def report(root: Path, graph: Graph, scopes: list[str] | None = None, cache: TwinCache | None = None,
           links: bool = True, check_size: bool = False) -> Report:
    cache = cache or TwinCache(root)
    rep = Report()
    trivial_rules = trivial.load_rules(root)
    scope = scope_folders(root, scopes)
    on_disk = disk_files(walk(root, Exclusion(root), ""))

    broken: dict[str, int] = {}
    if links:
        resolver = Resolver(graph.nodes)
        for node_id in sorted(graph.nodes):
            node = graph.nodes[node_id]
            if node["tipo"] == "codigo":
                continue
            rel = project_rel(node_id, node["tipo"])
            if scope is not None and (is_estado(node_id) or rel is None or not _in_scope(rel, scope)):
                continue
            scan = scan_links(graph, resolver, cache, node_id, root=root)
            for link, reason in scan.pending:
                rep.pendientes.append(PendingRef(node_id, link.line + 1, link.raw, reason))
            for link, cands in scan.ambiguous:
                rep.ambiguos.append(PendingRef(node_id, link.line + 1, link.raw, "ambiguo: " + ", ".join(cands)))
            for link in scan.no_alias:
                rep.sin_alias.append(PendingRef(node_id, link.line + 1, link.raw, "sin texto a mostrar"))
            if node["tipo"] == "indice" and not is_estado(node_id):
                broken[node_id] = len(scan.pending) + len(scan.ambiguous)

    rels = set(on_disk)
    for node_id, node in graph.nodes.items():
        if node["tipo"] == "indice" and not is_estado(node_id):
            rels.add(project_rel(node_id, "indice"))
    for rel in sorted(rels):
        if not _in_scope(rel, scope):
            continue
        st = folder_state(root, graph, cache, rel, on_disk.get(rel), trivial_rules, broken.get(folder_id(rel), 0))
        if st.state == HUERFANO and folder_id(rel) not in graph.nodes:
            continue
        rep.folders[rel] = st
        {OK: rep.ok, FALTANTE: rep.faltantes, DESACTUALIZADO: rep.desactualizados, HUERFANO: rep.huerfanos,
         TRIVIAL: rep.triviales}[st.state].append(rel)
        if check_size and st.state in (OK, DESACTUALIZADO):
            size = index_size(root, cache, rel, on_disk.get(rel) or [])
            if size is not None:
                rep.extensos.append((rel, *size))
    return rep
