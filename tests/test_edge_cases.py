"""Casos límite de la nota de Pruebas."""

from __future__ import annotations

import os
import sys

import pytest

from grafo_ia.paths import to_rel, twin_path

from conftest import assert_sano, load, read_twin, write, write_index


def test_rutas_con_espacios_y_acentos(project, run):
    write(project, "módulo de pagos/cálculo final.py", "x = 1\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    g = load(project)
    assert "módulo de pagos/cálculo final.py" in g.nodes
    write_index(project, "módulo de pagos", "calcula con [[módulo de pagos/cálculo final.py|cálculo]]\n")
    assert run(project, "update", "módulo de pagos")[0] == 0
    assert load(project).relations("módulo de pagos/módulo de pagos.md", "módulo de pagos/cálculo final.py") == ["conoce"]
    assert "cálculo final.py" in run(project, "neighbors", "módulo de pagos")[1]
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
    assert "src/features/features.md.md" not in g.nodes  # documentación: no entra
    assert run(project, "doctor")[0] == 0


def test_archivo_homonimo_de_su_carpeta_no_choca_con_el_indice(project, run):
    write(project, "src/src", "sin extensión\n")
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0 and "choca" not in out
    g = load(project)
    assert g.tipo("src/src.md") == "indice" and g.tipo("src/src") == "codigo"
    assert_sano(project)


def test_md_que_choca_con_el_indice_se_omite(project, run):
    write(project, "src/src.md", "# documento real con el nombre del índice\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    assert run(project, "ignore", "--remove", "*.md")[0] == 0  # ahora los .md entran al grafo
    code, out = run(project, "add")
    assert code == 0 and "se omitió src/src.md" in out and "choca" in out
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
    write_index(project, "", "", purpose="Tiene un archivo vacío a propósito.")
    assert run(project, "update", ".")[0] == 0
    assert load(project).nodes["vacio.py"]["last_synced_hash"]


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="permisos POSIX")
def test_indice_sin_permisos_de_escritura(initialized, run):
    write_index(initialized, "src", "## helper\nx\n")
    write_index(initialized, "src/features", "[[src#helper|h]]\n")
    run(initialized, "update", "src/features")
    d = twin_path(initialized, "src/features/features.md").parent
    os.chmod(d, 0o555)
    try:
        code, out = run(initialized, "rename", "src#helper", "ayuda")
        assert code == 2 and "permisos" in out
        assert "## helper" in read_twin(initialized, "src/src.md")  # nada a medias
    finally:
        os.chmod(d, 0o755)


def test_fuera_de_proyecto_codigo_2(tmp_path, run):
    code, out = run(tmp_path, "status")
    assert code == 2 and "graph init" in out


def test_desde_subcarpeta_encuentra_graph(initialized, run):
    code, out = run(initialized / "src/features", "status")
    assert code == 0 and "faltante" in out
    code, out = run(initialized / "src/features", "get", "login.go")
    assert code == 0 and "src/features/login.go es un archivo de código" in out
    code, out = run(initialized / "src/features", "get", ".")
    assert code == 0 and out.startswith("==> src/features/features.md <==")


def test_estado_proyecto_reservado(project, run):
    write(project, "Estado_Proyecto/x.py")
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0 and "reservado" in out
    assert "Estado_Proyecto/x.py" not in load(project).nodes
    assert_sano(project)


def test_enlaces_ambiguos_se_reportan(initialized, run):
    write(initialized, "a/util.py")
    write(initialized, "b/util.py")
    run(initialized, "add")
    write_index(initialized, "", "[[util.py|util]]\n")
    out = run(initialized, "incomplete")[1]
    assert "ambiguo" in out
