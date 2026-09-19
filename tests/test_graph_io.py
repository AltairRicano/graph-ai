"""graph_io: node-link, adyacencias derivadas, escritura atómica, corrupción, lock."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import pytest

from grafo_ia import graph_io
from grafo_ia.graph_io import Graph

from conftest import assert_sano, write_twin


def _graph_dir(tmp_path):
    (tmp_path / ".graph").mkdir(exist_ok=True)
    return tmp_path


def test_roundtrip_y_links(tmp_path):
    root = _graph_dir(tmp_path)
    g = Graph({"nombre": "x"})
    g.add_node("a.py.md", "codigo", last_synced_hash="h")
    g.add_node("b.py.md", "codigo")
    g.set_edge("a.py.md", "b.py.md", ["utiliza"])
    graph_io.save(root, g)
    raw = json.loads((root / ".graph/index.json").read_text())
    assert "links" in raw and "edges" not in raw
    assert raw["directed"] is True and raw["multigraph"] is False
    g2 = graph_io.load(root)
    assert g2.to_json() == g.to_json()


def test_adj_in_derivado(tmp_path):
    g = Graph()
    for n in "abc":
        g.add_node(f"{n}.md", "codigo")
    g.set_edge("a.md", "b.md")
    g.set_edge("c.md", "b.md")
    g2 = Graph.from_json(g.to_json())
    recomputed = {}
    for (s, t) in g2.edges:
        recomputed.setdefault(t, set()).add(s)
    assert {k: v for k, v in g2.adj_in.items() if v} == recomputed


def test_escritura_fallida_deja_el_anterior(tmp_path, monkeypatch):
    root = _graph_dir(tmp_path)
    g = Graph()
    g.add_node("a.md", "codigo")
    graph_io.save(root, g)
    before = (root / ".graph/index.json").read_text()
    g.add_node("b.md", "codigo")

    def boom(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(graph_io.os, "replace", boom)
    with pytest.raises(OSError):
        graph_io.save(root, g)
    assert (root / ".graph/index.json").read_text() == before
    assert not [p for p in (root / ".graph").iterdir() if p.name.endswith(".tmp")]


def test_json_corrupto_error_claro_e_init_reconstruye(initialized, run):
    (initialized / ".graph/index.json").write_text("{ roto", encoding="utf-8")
    code, out = run(initialized, "status")
    assert code == 2 and "corrupto" in out
    hash_before = (initialized / ".graph/config").read_text()
    code, out = run(initialized, "init", "--yes", "--no-git")
    assert code == 0, out
    assert "respaldado" in out
    assert (initialized / ".graph/config").read_text() == hash_before
    assert graph_io.load(initialized).meta["hash"] in hash_before  # el identificador sobrevive
    assert_sano(initialized)


def _writer(root, prefix, m):
    for i in range(m):
        with graph_io.transaction(root) as g:
            g.add_node(f"{prefix}-{i}.md", "codigo")


def test_concurrencia_n_por_m(tmp_path):
    root = _graph_dir(tmp_path)
    graph_io.save(root, Graph())
    n, m = 4, 15
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_writer, args=(root, f"p{k}", m)) for k in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0
    g = graph_io.load(root)
    assert len(g.nodes) == n * m


def _hold_lock_and_die(root, ready):
    with graph_io.lock(root):
        ready.set()
        time.sleep(0.2)
        os._exit(1)  # muere con el lock tomado


def test_lock_de_proceso_muerto_se_libera(tmp_path):
    root = _graph_dir(tmp_path)
    graph_io.save(root, Graph())
    ctx = mp.get_context("spawn")
    ready = ctx.Event()
    p = ctx.Process(target=_hold_lock_and_die, args=(root, ready))
    p.start()
    assert ready.wait(30)
    p.join(30)
    start = time.time()
    with graph_io.transaction(root) as g:
        g.add_node("x.md", "codigo")
    assert time.time() - start < 5


def test_dos_enlaces_misma_arista(initialized, run):
    write_twin(initialized, "src/main.go.md", "## a\n[[src/features/login.go.md|l]]\n## b\n[[src/features/login.go.md#x|l]]\n")
    run(initialized, "update", "src/main.go")
    g = graph_io.load(initialized)
    assert [e for e in g.edges if e[0] == "src/main.go.md"] == [("src/main.go.md", "src/features/login.go.md")]


@pytest.mark.skipif(pytest.importorskip("networkx") is None, reason="sin networkx")
def test_to_networkx(initialized):
    nxg = graph_io.to_networkx(graph_io.load(initialized))
    assert nxg.is_directed() and "src/main.go.md" in nxg
