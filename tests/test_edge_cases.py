"""Casos límite de la nota de Pruebas."""

from __future__ import annotations

import os
import sys

import pytest

from grafo_ia.paths import to_rel, twin_path

from conftest import assert_sano, load, read_twin, write, write_twin


def test_rutas_con_espacios_y_acentos(project, run):
    write(project, "módulo de pagos/cálculo final.py", "x = 1\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    g = load(project)
    assert "módulo de pagos/cálculo final.py.md" in g.nodes
    write_twin(project, "módulo de pagos/cálculo final.py.md", "calcula\n")
    assert run(project, "update", "módulo de pagos/cálculo final.py")[0] == 0
    assert_sano(project)


def test_ids_siempre_con_slash(tmp_path):
    assert to_rel(tmp_path, str(tmp_path / "a" / "b.py")) == "a/b.py"
    assert "\\" not in to_rel(tmp_path, "a\\b.py", tmp_path)


def test_nombres_con_numeral_o_barra_se_excluyen(project, run):
    write(project, "src/c#.go")
    code, out = run(project, "init", "--yes", "--no-git")
    assert "rompen la sintaxis" in out
    assert not any("c#" in n for n in load(project).nodes)


def test_carpeta_con_archivo_homonimo(project, run):
    write(project, "src/features/features.md", "# real\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    g = load(project)
    assert g.tipo("src/features/features.md") == "indice"
    assert g.tipo("src/features/features.md.md") == "codigo"
    assert run(project, "doctor")[0] == 0


def test_archivo_sin_extension_que_choca_con_indice(project, run):
    write(project, "src/src", "choca\n")
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0 and "choca" in out
    assert load(project).tipo("src/src.md") == "indice"
    assert_sano(project)


def test_remove_y_mv_de_carpeta_arrastran_indice(initialized, run):
    run(initialized, "mv", "src/features/pagos", "src/cobros")
    assert twin_path(initialized, "src/cobros/cobros.md").exists()
    assert not twin_path(initialized, "src/features/pagos/pagos.md").exists()
    run(initialized, "remove", "src/cobros")
    assert not twin_path(initialized, "src/cobros/cobros.md").exists()
    assert_sano(initialized)


def test_archivo_vacio(project, run):
    write(project, "vacio.py", "")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    write_twin(project, "vacio.py.md", "vacío a propósito\n")
    assert run(project, "update", "vacio.py")[0] == 0


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permisos POSIX")
def test_gemelo_sin_permisos_de_escritura(initialized, run):
    write_twin(initialized, "src/main.go.md", "## helper\nx\n")
    write_twin(initialized, "src/features/login.go.md", "[[src/main.go.md#helper|h]]\n")
    run(initialized, "update", "src/features/login.go")
    d = twin_path(initialized, "src/features/login.go.md").parent
    os.chmod(d, 0o555)
    try:
        code, out = run(initialized, "rename", "src/main.go#helper", "ayuda")
        assert code == 2 and "permisos" in out
        assert "## helper" in read_twin(initialized, "src/main.go.md")  # nada a medias
    finally:
        os.chmod(d, 0o755)


def test_fuera_de_proyecto_codigo_2(tmp_path, run):
    code, out = run(tmp_path, "status")
    assert code == 2 and "graph init" in out


def test_desde_subcarpeta_encuentra_graph(initialized, run):
    code, out = run(initialized / "src/features", "status")
    assert code == 0 and "faltante" in out
    code, out = run(initialized / "src/features", "get", "login.go")
    assert code == 0 and "src/features/login.go.md" in out


def test_estado_proyecto_reservado(project, run):
    write(project, "Estado_Proyecto/x.py")
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0 and "reservado" in out
    assert "Estado_Proyecto/x.py.md" not in load(project).nodes
    assert_sano(project)


def test_enlaces_ambiguos_se_reportan(initialized, run):
    write(initialized, "a/util.py")
    write(initialized, "b/util.py")
    run(initialized, "add")
    write_twin(initialized, "README.md.md", "[[util.py.md|util]]\n")
    out = run(initialized, "incomplete")[1]
    assert "ambiguo" in out
