"""Modelo en memoria del grafo y persistencia de `index.json`.

- Formato node-link de networkx (`nodes` + `links`), dirigido, sin multigrafo.
- `adj_out`/`adj_in` se derivan al cargar y se mantienen en cada operación;
  nunca se persisten (la fuente de verdad son las aristas).
- Toda escritura pasa por `transaction()`: lock de archivo del SO sobre
  `.graph/index.lock` durante leer-modificar-escribir, y reemplazo atómico.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator

from grafo_ia.errors import CorruptGraphError, GraphError
from grafo_ia.paths import NODE_TIPOS, graph_dir, node_name

SCHEMA_VERSION = 1
INDEX_FILE = "index.json"
LOCK_FILE = "index.lock"

TAXONOMY = (
    "importa",
    "utiliza",
    "implementa",
    "hereda_de",
    "extiende",
    "sobreescribe",
    "compone",
    "conoce",
    "informativa",
)
DEFAULT_RELATION = "conoce"


class Graph:
    def __init__(self, meta: dict | None = None):
        self.meta: dict = dict(meta or {})
        self.meta.setdefault("schema_version", SCHEMA_VERSION)
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple[str, str], list[str]] = {}
        self.adj_out: dict[str, set[str]] = {}
        self.adj_in: dict[str, set[str]] = {}
        self.dirty = False

    # ---- nodos -------------------------------------------------------------
    def add_node(self, node_id: str, tipo: str, **attrs) -> dict:
        if tipo not in NODE_TIPOS:
            raise ValueError(f"tipo de nodo inválido: {tipo}")
        node = {"id": node_id, "nombre": node_name(node_id), "tipo": tipo}
        if tipo == "codigo":
            node["last_synced_hash"] = attrs.pop("last_synced_hash", None)
        node.update(attrs)
        self.nodes[node_id] = node
        self.adj_out.setdefault(node_id, set())
        self.adj_in.setdefault(node_id, set())
        self.dirty = True
        return node

    def remove_node(self, node_id: str) -> None:
        for t in list(self.adj_out.get(node_id, ())):
            self.remove_edge(node_id, t)
        for s in list(self.adj_in.get(node_id, ())):
            self.remove_edge(s, node_id)
        self.nodes.pop(node_id, None)
        self.adj_out.pop(node_id, None)
        self.adj_in.pop(node_id, None)
        self.dirty = True

    def rename_nodes(self, mapping: dict[str, str]) -> None:
        """Renombra ids en lote conservando atributos y aristas."""
        if not mapping:
            return
        old_edges = dict(self.edges)
        old_nodes = dict(self.nodes)
        self.nodes = {}
        for nid, node in old_nodes.items():
            new = mapping.get(nid, nid)
            node = dict(node)
            node["id"] = new
            node["nombre"] = node_name(new)
            self.nodes[new] = node
        self.edges = {}
        self.adj_out = {n: set() for n in self.nodes}
        self.adj_in = {n: set() for n in self.nodes}
        for (s, t), rels in old_edges.items():
            self.set_edge(mapping.get(s, s), mapping.get(t, t), rels)
        self.dirty = True

    def get(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def tipo(self, node_id: str) -> str | None:
        n = self.nodes.get(node_id)
        return n["tipo"] if n else None

    # ---- aristas -----------------------------------------------------------
    def set_edge(self, source: str, target: str, relaciones: list[str] | None = None) -> None:
        rels = list(relaciones) if relaciones else [DEFAULT_RELATION]
        if self.edges.get((source, target)) != rels:
            self.edges[(source, target)] = rels
            self.dirty = True
        self.adj_out.setdefault(source, set()).add(target)
        self.adj_in.setdefault(target, set()).add(source)

    def remove_edge(self, source: str, target: str) -> None:
        if self.edges.pop((source, target), None) is not None:
            self.dirty = True
        self.adj_out.get(source, set()).discard(target)
        self.adj_in.get(target, set()).discard(source)

    def relations(self, source: str, target: str) -> list[str] | None:
        return self.edges.get((source, target))

    # ---- serialización -----------------------------------------------------
    def to_json(self) -> dict:
        return {
            "directed": True,
            "multigraph": False,
            "graph": self.meta,
            "nodes": [self.nodes[k] for k in sorted(self.nodes)],
            "links": [
                {"source": s, "target": t, "relaciones": self.edges[(s, t)]}
                for (s, t) in sorted(self.edges)
            ],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Graph":
        if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(data.get("links"), list):
            raise CorruptGraphError("index.json no tiene la forma node-link esperada (nodes/links)")
        g = cls(data.get("graph") or {})
        for node in data["nodes"]:
            if not isinstance(node, dict) or "id" not in node:
                raise CorruptGraphError("index.json tiene un nodo sin id")
            g.nodes[node["id"]] = dict(node)
            g.adj_out.setdefault(node["id"], set())
            g.adj_in.setdefault(node["id"], set())
        for link in data["links"]:
            try:
                s, t = link["source"], link["target"]
            except (TypeError, KeyError):
                raise CorruptGraphError("index.json tiene una arista sin source/target")
            g.edges[(s, t)] = list(link.get("relaciones") or [])
            g.adj_out.setdefault(s, set()).add(t)
            g.adj_in.setdefault(t, set()).add(s)
        g.dirty = False
        return g


# ---- disco ------------------------------------------------------------------
def index_path(root: Path) -> Path:
    return graph_dir(root) / INDEX_FILE


def load_raw(root: Path) -> dict:
    p = index_path(root)
    if not p.exists():
        raise CorruptGraphError(f"no existe {p} (usa `graph init` para reconstruirlo)")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CorruptGraphError(f"index.json corrupto ({e}); `graph init` lo reconstruye")


def load(root: Path) -> Graph:
    """Lectura pura, sin lock: la escritura es atómica, nunca se ve a medias."""
    return Graph.from_json(load_raw(root))


def save(root: Path, graph: Graph) -> None:
    """Escribe a un temporal en la misma carpeta y lo reemplaza con os.replace."""
    target = index_path(root)
    data = json.dumps(graph.to_json(), ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="index.json.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    graph.dirty = False


@contextlib.contextmanager
def lock(root: Path) -> Iterator[None]:
    """Lock exclusivo del SO sobre `.graph/index.lock`.

    Si el proceso muere con el lock tomado, el SO lo libera. Sin prioridades:
    quien llega primero escribe primero.
    """
    path = graph_dir(root) / LOCK_FILE
    f = open(path, "a+b")
    try:
        if sys.platform == "win32":
            import msvcrt

            f.seek(0)
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:  # LK_LOCK se rinde tras ~10 s; seguimos esperando
                    time.sleep(0.05)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


@contextlib.contextmanager
def transaction(root: Path, create: bool = False) -> Iterator[Graph]:
    """Lock + carga + (yield) + guardado si hubo cambios y no hubo excepción."""
    if not graph_dir(root).is_dir():
        raise GraphError(f"no existe {graph_dir(root)}")
    with lock(root):
        if create and not index_path(root).exists():
            graph = Graph()
            graph.dirty = True
        else:
            graph = load(root)
        yield graph
        if graph.dirty:
            save(root, graph)


def to_networkx(graph: Graph):
    """Exporta a networkx (extra `nx`)."""
    import networkx as nx

    data = graph.to_json()
    try:
        return nx.node_link_graph(data, directed=True, multigraph=False, edges="links")
    except TypeError:  # networkx < 3.4
        return nx.node_link_graph(data, directed=True, multigraph=False, link="links")
