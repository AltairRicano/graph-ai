"""`graph diff`: instantáneas de `graph update` en el repo anidado de `.graph`."""

from __future__ import annotations

import shutil

import pytest

from grafo_ia import snapshots

from conftest import git, load, write, write_twin

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="sin git")

V1 = "def cobrar(m):\n    return m\n\n\ndef anular(m):\n    pass\n"
V2 = "def cobrar(m):\n    return m * 2\n\n\ndef reembolsar(m):\n    pass\n"


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def synced(project, run):
    write(project, "src/pagos.py", V1)
    git(project, "init", "-q", "-b", "main")
    code, out = run(project, "init", "--yes")
    assert code == 0, out
    write_twin(project, "src/pagos.py.md", "Pagos.\n\n## Funciones\n### cobrar\nx\n\n### anular\ny\n")
    code, out = run(project, "update", "src/pagos.py")
    assert code == 0, out
    return project


def refs(root):
    return git(root / ".graph", "for-each-ref", "--format=%(refname)", snapshots.REF_PREFIX).stdout.split()


def test_update_guarda_instantanea_anclada(synced):
    blob = load(synced).nodes["src/pagos.py.md"][snapshots.ATTR]
    assert refs(synced) == [snapshots.REF_PREFIX + blob]
    assert snapshots.load(synced, blob) == V1.encode()


def test_diff_muestra_cambios_y_secciones(synced, run):
    write(synced, "src/pagos.py", V2)
    code, out = run(synced, "diff")
    assert code == 0, out
    assert "==> src/pagos.py (desactualizado) <==" in out
    assert "secciones a revisar: cobrar (modificada), reembolsar (nueva), anular (eliminada)" in out
    assert "-    return m\n" in out and "+    return m * 2\n" in out
    code, out = run(synced, "diff", "src/pagos.py", "--symbols")
    assert "secciones a revisar" in out and "@@" not in out


def test_diff_sin_cambios_y_carpetas(synced, run):
    assert run(synced, "diff")[1].strip() == "nada desactualizado"
    assert "sin cambios desde el último" in run(synced, "diff", "src/pagos.py")[1]
    write(synced, "src/pagos.py", V2)
    assert "src/pagos.py (desactualizado)" in run(synced, "diff", "src")[1]
    assert run(synced, "diff", "Estado_Proyecto/Plan.md")[0] == 2


def test_update_nuevo_suelta_la_instantanea_vieja(synced, run):
    old = load(synced).nodes["src/pagos.py.md"][snapshots.ATTR]
    write(synced, "src/pagos.py", V2)
    run(synced, "update", "src/pagos.py")
    new = load(synced).nodes["src/pagos.py.md"][snapshots.ATTR]
    assert new != old and refs(synced) == [snapshots.REF_PREFIX + new]
    run(synced, "remove", "src/pagos.py")
    assert refs(synced) == []


def test_sin_instantanea_lo_dice(initialized, run):
    write_twin(initialized, "src/main.go.md", "Main.\n")
    run(initialized, "update", "src/main.go")  # --no-git: no hay dónde guardar
    assert snapshots.ATTR not in load(initialized).nodes["src/main.go.md"]
    write(initialized, "src/main.go", "package main\n// cambio\n")
    out = run(initialized, "diff")[1]
    assert "sin instantánea" in out and "git diff" in out
