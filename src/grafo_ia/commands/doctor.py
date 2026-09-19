"""`graph doctor`: integridad estructural del JSON (no sincronía de contenido).

Sobre el JSON crudo (con un dict, los ids duplicados se perderían en silencio):
ids duplicados, tipos inválidos, aristas colgantes o repetidas, `relaciones`
vacías o fuera de la taxonomía, lazos. Jerarquía derivada de las rutas: todo
nodo tiene su índice padre en el JSON, y la lista del padre lo referencia.
Sano -> 0; con daño -> 1.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from grafo_ia import graph_io
from grafo_ia.commands._common import root_of
from grafo_ia.edges import Resolver, TwinCache, scan_links
from grafo_ia.graph_io import TAXONOMY, Graph
from grafo_ia.paths import NODE_TIPOS, parent_index_id
from grafo_ia.reconciliation import fixed_nodes


def diagnose(root: Path) -> list[str]:
    problems: list[str] = []
    try:
        raw = graph_io.load_raw(root)
    except Exception as e:  # noqa: BLE001 - se reporta cualquier forma de corrupción
        return [str(e)]
    if raw.get("directed") is not True or raw.get("multigraph") is not False:
        problems.append("index.json: se esperaba directed=true y multigraph=false")
    nodes = raw.get("nodes")
    links = raw.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        return problems + ["index.json: faltan las listas nodes/links"]

    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    for nid, c in Counter(ids).items():
        if c > 1:
            problems.append(f"id duplicado: {nid} ({c} veces)")
    idset = set(ids)
    for n in nodes:
        if not isinstance(n, dict) or "id" not in n:
            problems.append("nodo sin id")
            continue
        if n.get("tipo") not in NODE_TIPOS:
            problems.append(f"tipo inválido en {n['id']}: {n.get('tipo')!r}")
        if n.get("tipo") != "codigo" and "last_synced_hash" in n:
            problems.append(f"last_synced_hash en un nodo que no es de código: {n['id']}")
    for nid in fixed_nodes():
        if nid not in idset:
            problems.append(f"falta el nodo fijo {nid}")

    pairs = Counter()
    for link in links:
        s, t = link.get("source"), link.get("target")
        pairs[(s, t)] += 1
        if s not in idset:
            problems.append(f"arista colgante: source {s} no existe")
        if t not in idset:
            problems.append(f"arista colgante: target {t} no existe")
        if s == t:
            problems.append(f"arista de un nodo a sí mismo: {s}")
        rels = link.get("relaciones")
        if not isinstance(rels, list) or not rels:
            problems.append(f"relaciones vacías en {s} -> {t}")
        else:
            bad = [r for r in rels if r not in TAXONOMY]
            if bad:
                problems.append(f"relación fuera de la taxonomía en {s} -> {t}: {', '.join(map(str, bad))}")
    for (s, t), c in pairs.items():
        if c > 1:
            problems.append(f"arista repetida: {s} -> {t} ({c} veces)")

    # jerarquía derivada de la ruta
    try:
        graph = Graph.from_json(raw)
    except Exception as e:  # noqa: BLE001
        return problems + [str(e)]
    cache = TwinCache(root)
    resolver = Resolver(graph.nodes)
    children: dict[str, set[str]] = {}
    for nid, node in graph.nodes.items():
        parent = parent_index_id(nid, node.get("tipo", ""))
        if parent is None:
            continue
        if graph.tipo(parent) != "indice":
            problems.append(f"{nid} no tiene índice padre ({parent} no existe)")
            continue
        children.setdefault(parent, set()).add(nid)
    for idx, kids in sorted(children.items()):
        doc = cache.doc(idx)
        if doc is None:
            problems.append(f"falta el archivo del índice {idx} (usa `graph populate`)")
            continue
        listed = {t for _, t in scan_links(graph, resolver, cache, idx, check_sections=False).structural if t}
        for kid in sorted(kids - listed):
            problems.append(f"el índice {idx} no referencia a su hijo {kid}")
    return problems


def register(sub) -> None:
    p = sub.add_parser("doctor", help="chequeo de integridad estructural del grafo")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    problems = diagnose(root)
    if not problems:
        print("grafo sano")
        return 0
    print(f"problemas ({len(problems)})")
    for p in problems:
        print(f"  - {p}")
    return 1
