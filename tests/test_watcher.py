"""Watcher: lógica por lotes con eventos simulados, ciclo de vida y una prueba de humo real."""

from __future__ import annotations

import time

import pytest

from grafo_ia.commands import watcher
from grafo_ia.commands.watcher import Event, WatchProcessor
from grafo_ia.paths import twin_path

from conftest import assert_sano, load, read_twin, write, write_index


def ev(root, kind, rel, dest=None, is_dir=False):
    return Event(kind, str(root / rel), str(root / dest) if dest else None, is_dir)


def test_crear_y_borrar(initialized):
    root = initialized
    proc = WatchProcessor(root)
    write(root, "src/nuevo.go")
    proc.process([ev(root, "created", "src/nuevo.go")])
    assert "src/nuevo.go" in load(root).nodes
    assert "[[src/nuevo.go|nuevo.go]]" in read_twin(root, "src/src.md")  # entra a la lista de su carpeta
    (root / "src/nuevo.go").unlink()
    proc.process([ev(root, "deleted", "src/nuevo.go")])
    assert "src/nuevo.go" not in load(root).nodes
    assert "nuevo.go" not in read_twin(root, "src/src.md")
    assert_sano(root)


def test_mover_archivo_y_carpeta(initialized):
    root = initialized
    write_index(root, "", "[[src/main.go|main]] [[src/features/login.go|login]]\n")
    proc = WatchProcessor(root)
    proc.process([ev(root, "modified", ".graph/Index.md")])
    (root / "src/main.go").rename(root / "src/app.go")
    proc.process([ev(root, "moved", "src/main.go", "src/app.go")])
    assert "[[src/app.go|main]]" in read_twin(root, "Index.md")
    (root / "src/features").rename(root / "src/mods")
    proc.process([ev(root, "moved", "src/features", "src/mods", is_dir=True)])
    g = load(root)
    assert "src/mods/login.go" in g.nodes and "src/mods/mods.md" in g.nodes
    assert "[[src/mods/login.go|login]]" in read_twin(root, "Index.md")
    assert_sano(root)


def test_rafaga_se_procesa_una_vez(initialized, monkeypatch):
    root = initialized
    from grafo_ia import reconciliation

    calls = []
    real = reconciliation.reconcile

    def spy(*a, **k):
        calls.append(a[2] if len(a) > 2 else k.get("scope"))
        return real(*a, **k)

    monkeypatch.setattr(reconciliation, "reconcile", spy)
    for i in range(20):
        write(root, f"src/r{i}.go")
    WatchProcessor(root).process([ev(root, "created", f"src/r{i}.go") for i in range(20)])
    assert calls == ["src"]
    assert all(f"src/r{i}.go" in load(root).nodes for i in range(20))


def test_ignora_git_temporales_y_propias(initialized):
    root = initialized
    before = (root / ".graph/index.json").read_text()
    res = WatchProcessor(root).process([
        ev(root, "created", ".git/objects/ab"),
        ev(root, "created", "src/.main.go.swp"),
        ev(root, "created", "src/main.go~"),
        ev(root, "modified", ".graph/index.json"),
        ev(root, "created", ".graph/index.lock"),
        ev(root, "modified", "src/main.go"),  # modificar código: nada
        ev(root, "created", "node_modules/x.js"),
    ])
    assert res == {"moved": {}, "reconciled": [], "regenerated": []}
    assert (root / ".graph/index.json").read_text() == before


def test_indice_modificado_regenera(initialized):
    root = initialized
    write_index(root, "src", "usa [[src/features/login.go|login]]\n")
    res = WatchProcessor(root).process([ev(root, "modified", ".graph/src/src.md")])
    assert res["regenerated"] == ["src/src.md"]
    assert load(root).relations("src/src.md", "src/features/login.go") == ["conoce"]


def test_arranque_recoge_lo_perdido(initialized):
    write(initialized, "src/mientras.go")
    import threading

    stop = threading.Event()
    stop.set()  # arranca, reconcilia y sale
    pytest.importorskip("watchdog")
    watcher.run_forever(initialized, stop)
    assert "src/mientras.go" in load(initialized).nodes
    assert not (initialized / ".graph/watcher.pid").exists()


# ---- ciclo de vida y humo ------------------------------------------------------
@pytest.fixture
def live(initialized):
    pytest.importorskip("watchdog")
    pytest.importorskip("psutil")
    yield initialized
    watcher.stop(initialized)


def test_pid_muerto_es_detenido(initialized):
    pytest.importorskip("psutil")
    (initialized / ".graph/watcher.pid").write_text("999999 1.0\n")
    assert watcher.describe(initialized) == "detenido"
    assert watcher.stop(initialized) is False  # stop sin Watcher no falla


def test_humo_watchdog_real(live, run):
    root = live
    code, out = run(root, "watch", "start")
    assert code == 0, out
    pid1 = watcher.running(root)[0]
    run(root, "watch", "start")
    assert watcher.running(root)[0] == pid1  # start doble no lanza otro
    assert "corriendo" in run(root, "watch", "status")[1]
    write(root, "src/humo.go", "package humo\n")
    deadline = time.time() + 15
    while time.time() < deadline and "src/humo.go" not in load(root).nodes:
        time.sleep(0.2)
    assert "src/humo.go" in load(root).nodes
    assert run(root, "watch", "stop")[1].strip() == "watcher: detenido"
    assert "detenido" in run(root, "watch", "status")[1]
