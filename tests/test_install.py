"""Instalador (`./graph install`): partes que no requieren crear un entorno virtual."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("grafo_install", REPO / "scripts" / "install.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")


@posix_only
def test_launcher_es_symlink_e_idempotente(tmp_path):
    entry = tmp_path / "venv-graph"
    entry.write_text("#!/bin/sh\n")
    launcher = inst.install_launcher(tmp_path / "bin", entry)
    assert launcher.is_symlink() and launcher.resolve() == entry.resolve()
    assert inst.install_launcher(tmp_path / "bin", entry) == launcher  # reinstalar no falla


@posix_only
def test_no_pisa_un_graph_ajeno(tmp_path):
    entry = tmp_path / "venv-graph"
    entry.write_text("")
    ajeno = tmp_path / "bin" / "graph"
    ajeno.parent.mkdir()
    ajeno.write_text("#!/bin/sh\necho plotutils\n")
    with pytest.raises(inst.InstallError):
        inst.check_launcher_free(tmp_path / "bin", entry)
    assert ajeno.read_text().endswith("plotutils\n")
    inst.install_launcher(tmp_path / "bin", entry, force=True)
    assert ajeno.is_symlink()


@posix_only
def test_skill_enlaza_el_repo(tmp_path):
    link = inst.install_skill(tmp_path / "skills")
    assert link.name == "grafo-ia" and (link / "SKILL.md").exists()
    assert inst.install_skill(tmp_path / "skills") == link  # idempotente
    otra = tmp_path / "skills2" / "grafo-ia"
    otra.mkdir(parents=True)
    with pytest.raises(inst.InstallError):
        inst.install_skill(tmp_path / "skills2")


def test_aviso_de_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    warnings = inst.path_warnings(tmp_path, tmp_path / "graph")
    assert warnings and "no está en tu PATH" in warnings[0]


@posix_only
def test_lanzador_sin_instalar_avisa(tmp_path):
    copia = tmp_path / "graph"
    copia.mkdir()
    (copia / "graph").write_bytes((REPO / "graph").read_bytes())
    (copia / "graph").chmod(0o755)
    r = subprocess.run([str(copia / "graph"), "status"], capture_output=True, text=True)
    assert r.returncode == 2 and "./graph install" in r.stderr
