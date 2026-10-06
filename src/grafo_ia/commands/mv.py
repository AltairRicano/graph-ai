"""`graph mv <vieja> <nueva>`: renombra o mueve un nodo (solo en el grafo).

Actualiza ids en el JSON y, en cascada, reescribe toda mención `[[...]]` a esa
ruta en cualquier gemelo: solo el componente de ruta, nunca la sección ni el
texto a mostrar, conservando la forma en que estaba escrita. Si es una
carpeta, arrastra a todos sus descendientes y renombra su índice.
Todo se valida antes de escribir: o se mueve todo o nada.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from grafo_ia import graph_io
from grafo_ia.commands._common import cwd_of, plural, root_of
from grafo_ia.commands.populate import populate
from grafo_ia.edges import Resolver, TwinCache, is_structural
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import INCLUIR, Exclusion
from grafo_ia.graph_io import Graph
from grafo_ia.parser import render_link
from grafo_ia.paths import (
    GRAPH_DIR,
    ESTADO_DIR,
    code_id,
    folder_id,
    graph_dir,
    is_under,
    parent_rel,
    project_rel,
    resolve_arg,
    to_rel,
    twin_path,
)
from grafo_ia.rewrite import ensure_writable, prune_empty_dirs, retarget, rewrite_links, write_text_atomic


def build_mapping(graph: Graph, old_rel: str, new_rel: str, kind: str) -> dict[str, str]:
    if kind == "codigo":
        return {code_id(old_rel): code_id(new_rel)}
    mapping = {}
    for nid, node in graph.nodes.items():
        prel = project_rel(nid, node["tipo"])
        if prel is None or not is_under(prel, old_rel):
            continue
        new_prel = new_rel + prel[len(old_rel):]
        mapping[nid] = code_id(new_prel) if node["tipo"] == "codigo" else folder_id(new_prel)
    return mapping


def validate_mapping(root: Path, graph: Graph, mapping: dict[str, str]) -> None:
    targets = set(mapping.values())
    if len(targets) != len(mapping):
        raise GraphError("el movimiento produce ids repetidos")
    for old, new in mapping.items():
        if new in graph.nodes and new not in mapping:
            raise GraphError(f"el destino ya existe en el grafo: {new}")
        p = twin_path(root, new)
        if p.exists() and new not in mapping and os.path.normcase(str(p)) != os.path.normcase(str(twin_path(root, old))):
            raise GraphError(f"ya hay un archivo en {p} que no pertenece al grafo")


def move_nodes(root: Path, graph: Graph, mapping: dict[str, str], cache: TwinCache | None = None) -> dict[str, int]:
    """Mueve gemelos, reescribe enlaces y renombra nodos. -> gemelos tocados."""
    cache = cache or TwinCache(root)
    resolver = Resolver(graph.nodes)
    new_ids = {mapping.get(i, i) for i in graph.nodes}
    affected = set(mapping)
    for old in mapping:
        affected |= graph.adj_in.get(old, set())
    texts: dict[str, str] = {}
    touched: dict[str, int] = {}
    for s in sorted(affected):
        text, doc = cache.text(s), cache.doc(s)
        if text is None or doc is None:
            continue
        moved_source = s in mapping

        def fn(link, s=s, doc=doc, moved_source=moved_source):
            if link.target.strip() == "" or is_structural(graph, s, doc, link):
                return None
            tid, _ = resolver.resolve(link.target, s)
            if tid is None:
                return None
            if tid in mapping:
                new_target = retarget(link.target, tid, mapping[tid], new_ids, graph.tipo(tid))
            elif moved_source and link.target.strip().startswith(("./", "../")):
                new_target = tid  # su base relativa cambió: se fija al id completo
            else:
                return None
            if new_target == link.target:
                return None
            return render_link(new_target, link.section, link.alias, link.embed)

        new, n = rewrite_links(text, fn)
        if n:
            texts[mapping.get(s, s)] = new
            touched[mapping.get(s, s)] = n
    ensure_writable([twin_path(root, n) for n in texts]
                    + [twin_path(root, o) for o in mapping]
                    + [twin_path(root, n) for n in mapping.values()])
    # movimiento en dos fases (vía nombre temporal): cubre intercambios y
    # renombres que solo cambian mayúsculas en sistemas que no las distinguen
    staged = []
    token = uuid.uuid4().hex[:8]
    for old, new in mapping.items():
        p = twin_path(root, old)
        if p.is_file():
            tmp = p.with_name(f"{p.name}.mv-{token}")
            os.replace(p, tmp)
            staged.append((old, tmp, twin_path(root, new)))
    for old, tmp, dst in staged:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dst)
    for old, _, _ in staged:
        prune_empty_dirs(twin_path(root, old).parent, graph_dir(root))
    for nid, text in texts.items():
        write_text_atomic(twin_path(root, nid), text)
    graph.rename_nodes(mapping)
    for old in mapping:
        cache.forget(old)
    for nid in list(texts) + list(mapping.values()):
        cache.forget(nid)
    return touched


def ensure_index_chain(graph: Graph, rel: str) -> list[str]:
    """Crea los nodos índice de `rel` y sus ancestros que falten."""
    created = []
    cur = rel
    while cur:
        fid = folder_id(cur)
        if fid not in graph.nodes:
            graph.add_node(fid, "indice")
            created.append(fid)
        cur = parent_rel(cur)
    return created


def register(sub) -> None:
    p = sub.add_parser("mv", help="renombra o mueve un archivo o carpeta en el grafo (no toca el código real)")
    p.add_argument("vieja")
    p.add_argument("nueva")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    cwd = cwd_of(args)
    with graph_io.transaction(root) as graph:
        src = resolve_arg(root, graph.nodes, args.vieja, cwd)
        if src.kind == "estado":
            raise GraphError("los documentos de Estado_Proyecto no se mueven")
        if src.node_id is None:
            raise GraphError(f"{src.rel or '.'} no está en el grafo")
        if src.rel == "":
            raise GraphError("no se puede mover la raíz del proyecto")
        new_rel = to_rel(root, args.nueva, cwd)
        if new_rel == "" or new_rel.split("/")[0] in (GRAPH_DIR, ESTADO_DIR):
            raise GraphError(f"destino inválido: {args.nueva}")
        if is_under(new_rel, src.rel) and new_rel != src.rel:
            raise GraphError("no se puede mover una carpeta dentro de sí misma")
        verdict, reason = Exclusion(root).check(new_rel, src.kind == "indice")
        if verdict != INCLUIR:
            raise GraphError(f"el destino está excluido ({reason})")
        mapping = build_mapping(graph, src.rel, new_rel, src.kind)
        validate_mapping(root, graph, mapping)
        ensure_index_chain(graph, parent_rel(new_rel))
        touched = move_nodes(root, graph, mapping)
        populate(root, graph)
    print(f"movidos: {plural(len(mapping), 'nodo')}")
    for old, new in sorted(mapping.items()):
        print(f"  {old} -> {new}")
    if touched:
        print(f"documentos con enlaces reescritos: {len(touched)}")
        for s, n in sorted(touched.items()):
            print(f"  ~ {s} ({plural(n, 'enlace')})")
    if not (root / new_rel).exists():
        print(f"[AVISO] {new_rel} todavía no existe en el proyecto; mueve el código también "
              f"o la siguiente reconciliación lo sacará del grafo.")
    return 0
