"""`graph init`, `graph get` y `graph status`."""

from __future__ import annotations

import os
import sys

import pytest

from grafo_ia import templates
from grafo_ia.cli import main
from grafo_ia.paths import ESTADO_DOCS, doc_path

from conftest import read_doc

HOY = templates.today()


def test_init_crea_solo_estado_proyecto(project, run):
    code, out = run(project, "init")
    assert code == 0, out
    assert "5 documentos creados: Estado, Plan, Decisiones, Tecnologias, Arquitectura" in out
    creados = sorted(p.relative_to(project).as_posix() for p in (project / ".graph").rglob("*") if p.is_file())
    assert creados == sorted(f".graph/Estado_Proyecto/{n}.md" for n in ESTADO_DOCS)  # nada del código entra
    assert f"fecha_elaboracion: {HOY}" in read_doc(project, "Estado")


def test_init_no_sobreescribe_y_repone_lo_que_falte(initialized, run):
    doc_path(initialized, "Estado").write_text("mío\n", encoding="utf-8")
    doc_path(initialized, "Plan").unlink()
    code, out = run(initialized, "init", "--yes")  # --yes se sigue aceptando
    assert code == 0 and "1 documento creado: Plan" in out
    assert read_doc(initialized, "Estado") == "mío\n"
    assert "ya existían" in run(initialized, "init")[1]


def test_init_dentro_de_un_proyecto_con_estado_se_rechaza(initialized, run):
    code, out = run(initialized / "src", "init")
    assert code == 2 and "ya hay un .graph" in out


def test_sin_graph_lo_dice(project, run):
    for cmd in (["get", "Estado"], ["status"]):
        code, out = run(project, *cmd)
        assert code == 2 and "no hay .graph" in out and "graph init" in out


def test_get_documento_seccion_y_varios(initialized, run):
    code, out = run(initialized, "get", "Estado_Proyecto/Estado.md")
    assert code == 0 and out.startswith("==> Estado_Proyecto/Estado.md <==\n---\ntipo: estado") and "## Falta" in out
    code, out = run(initialized, "get", "Estado#Falta")
    assert code == 0 and out.startswith("==> Estado_Proyecto/Estado.md#Falta <==\n## Falta") and "## Hecho" not in out
    code, out = run(initialized / "src", "get", "tecnologías", ".graph/Estado_Proyecto/Plan.md")  # desde una subcarpeta
    assert code == 0 and "==> Estado_Proyecto/Tecnologias.md <==" in out and "\n\n==> Estado_Proyecto/Plan.md <==" in out


def test_get_errores(initialized, run):
    code, out = run(initialized, "get", "Estado", "src/main.go")
    assert code == 2 and "src/main.go no es un documento de Estado_Proyecto" in out and "==>" not in out
    code, out = run(initialized, "get", "Estado#Nada")
    assert code == 2 and "no existe la sección 'Nada'" in out
    doc_path(initialized, "Plan").unlink()
    code, out = run(initialized, "get", "Plan")
    assert code == 2 and "graph init" in out


def test_status_fecha_y_sin_escribir(initialized, run):
    p = doc_path(initialized, "Estado")
    p.write_text(p.read_text(encoding="utf-8").replace(HOY, "2026-01-01") + "- algo\n", encoding="utf-8")
    doc_path(initialized, "Plan").unlink()
    code, out = run(initialized, "status")
    assert code == 0, out
    lines = {ln.split()[0]: ln for ln in out.splitlines()[1:]}
    assert "2026-01-01" in lines["Estado.md"] and "sin escribir" not in lines["Estado.md"]
    assert HOY in lines["Decisiones.md"] and "sin escribir" in lines["Decisiones.md"]
    assert "falta" in lines["Plan.md"]


@pytest.mark.skipif(sys.platform == "win32", reason="el CLI anterior falso es un script de shell")
def test_un_graph_de_gemelos_se_delega_al_cli_anterior(project, tmp_path, monkeypatch, capfd):
    (project / ".graph").mkdir()
    (project / ".graph" / "index.json").write_text("{}", encoding="utf-8")
    fake = tmp_path / "bin" / "graph-gemelos"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\necho "gemelos: $*"\nexit 7\n', encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    assert main(["-C", str(project / "src"), "incomplete", "src"]) == 7  # un comando que aquí ya no existe
    assert f"gemelos: -C {project / 'src'} incomplete src" in capfd.readouterr().out
    monkeypatch.setenv("PATH", str(tmp_path / "vacio"))
    assert main(["-C", str(project), "status"]) == 2
    assert "graph-gemelos" in capfd.readouterr().err
