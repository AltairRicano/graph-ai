"""`graph multiedit`, `graph update` con varias rutas, triviales y el hook Stop."""

from __future__ import annotations

import io
import json
import shutil

import pytest

from grafo_ia import templates

from conftest import git, load, read_twin, write, write_twin

HOY = templates.today()


@pytest.fixture
def batch(run, monkeypatch):
    """Corre `graph multiedit` con el lote por stdin."""

    def _batch(root, text: str, *args: str):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
        return run(root, "multiedit", *args)

    return _batch


def _status(run, root):
    out = run(root, "status")[1]
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line and not line.startswith("["))


# ---- multiedit ---------------------------------------------------------------------
def test_llena_varios_gemelos_y_los_sincroniza(initialized, run, batch):
    code, out = batch(initialized, (
        "=== src/main.go ===\n"
        "Punto de entrada.\n\n## Funciones\n\n### main\n**Qué hace:** arranca con `$HOME` y \"comillas\".\n"
        "=== src/features/login.go ===\n"
        "Login, usa [[src/main.go.md#main|main]].\n"
    ))
    assert code == 0, out
    assert out.splitlines()[0] == "multiedit: 2 gemelos escritos y sincronizados"
    main = read_twin(initialized, "src/main.go.md")
    assert main.startswith("---\ntipo: codigo\n")  # el frontmatter se conserva
    assert f"### main\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\n**Qué hace:** arranca con `$HOME`" in main
    s = _status(run, initialized)
    assert s["ok"] == "2" and s["faltante"] == "2"
    assert load(initialized).relations("src/features/login.go.md", "src/main.go.md") == ["conoce"]


def test_seccion_reemplaza_y_conserva_elaboracion(initialized, batch):
    write_twin(initialized, "src/main.go.md", (
        "Entrada.\n\n## Funciones\n\n### main\n**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-02\n\nViejo.\n\n"
        "### otra\n**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-02\n\nIntacta.\n"
    ))
    code, out = batch(initialized, "=== src/main.go#main ===\n### main\nNuevo.\n")
    assert code == 0, out
    twin = read_twin(initialized, "src/main.go.md")
    assert f"### main\n**Elaboración:** 2026-01-01 | **Actualización:** {HOY}\n\nNuevo.\n\n### otra" in twin
    assert "Viejo" not in twin
    # la sección que no se tocó conserva sus dos fechas
    assert "### otra\n**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-02\n\nIntacta.\n" in twin
    assert f"fecha_actualizacion: {HOY}" in twin


def test_seccion_nueva_va_a_funciones(initialized, batch):
    write_twin(initialized, "src/main.go.md", "Entrada.\n\n## Funciones\n\n### main\nA.\n\n## Notas\nFin.\n")
    code, out = batch(initialized, "=== src/main.go#helper ===\nAyuda a main.\n")
    assert code == 0, out
    twin = read_twin(initialized, "src/main.go.md")
    assert twin.index("### main") < twin.index("### helper") < twin.index("## Notas")
    assert f"### helper\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nAyuda a main.\n" in twin


def test_override_y_append_por_entrada(initialized, batch):
    write_twin(initialized, "src/main.go.md", "Viejo main.\n")
    write_twin(initialized, "src/features/login.go.md", "Viejo login.\n")  # escrito a mano, nunca confirmado
    code, out = batch(initialized, "=== src/main.go [override] ===\nNuevo main.\n=== src/features/login.go ===\nMás login.\n")
    assert code == 0, out
    assert "Viejo" not in read_twin(initialized, "src/main.go.md")
    assert read_twin(initialized, "src/features/login.go.md").endswith("Viejo login.\n\nMás login.\n")


def test_append_a_desactualizado_se_rechaza_y_no_aplica_nada(initialized, run, batch):
    write_twin(initialized, "src/main.go.md", "Entrada.\n")
    run(initialized, "update", "src/main.go")
    write(initialized, "src/main.go", "package main\n// cambio\n")
    before = read_twin(initialized, "src/features/login.go.md")
    code, out = batch(initialized, "=== src/features/login.go ===\nLogin.\n=== src/main.go ===\nParche.\n")
    assert code == 2 and "desactualizado" in out and "no se aplicó nada" in out
    assert read_twin(initialized, "src/features/login.go.md") == before
    # con sección sí pasa, y queda al día
    code, out = batch(initialized, "=== src/main.go#main ===\nArranca.\n")
    assert code == 0, out
    assert _status(run, initialized)["desactualizado"] == "0"


def test_ruta_inexistente_aborta_todo(initialized, batch):
    before = read_twin(initialized, "src/main.go.md")
    code, out = batch(initialized, "=== src/main.go ===\nEntrada.\n=== src/no_existe.go ===\nNada.\n")
    assert code == 2 and "src/no_existe.go" in out
    assert read_twin(initialized, "src/main.go.md") == before


def test_archivo_nuevo_se_agrega_solo(initialized, run, batch):
    write(initialized, "src/nuevo/util.go", "package nuevo\n")
    code, out = batch(initialized, "=== src/nuevo/util.go ===\nUtilidades.\n")
    assert code == 0, out
    assert "1 archivo agregado al grafo" in out
    g = load(initialized)
    assert g.nodes["src/nuevo/util.go.md"].get("last_synced_hash")
    assert "src/nuevo/nuevo.md" in g.nodes
    assert "util.go" in read_twin(initialized, "src/nuevo/nuevo.md")
    assert run(initialized, "doctor")[0] == 0


def test_lote_por_archivo_se_borra(initialized, run):
    lote = initialized / "lote.txt"
    lote.write_text("=== src/main.go ===\nEntrada.\n", encoding="utf-8")
    code, out = run(initialized, "multiedit", "-f", "lote.txt")
    assert code == 0, out
    assert not lote.exists()
    assert read_twin(initialized, "src/main.go.md").endswith("Entrada.\n")


def test_estado_proyecto_por_seccion(initialized, batch):
    code, out = batch(initialized, "=== Estado_Proyecto/Estado.md#Hecho ===\n- Login con [[src/features/login.go.md|login]].\n")
    assert code == 0, out
    estado = read_twin(initialized, "Estado_Proyecto/Estado.md")
    assert "## Hecho\n- Login con" in estado and "## En curso" in estado
    assert "Lo que ya está completo" not in estado  # el texto guía de la sección se reemplazó
    assert "**Elaboración:**" not in estado  # Estado no lleva fechas por sección
    assert load(initialized).relations("Estado_Proyecto/Estado.md", "src/features/login.go.md") == ["conoce"]


def test_decisiones_fecha_cada_decision(initialized, batch):
    code, out = batch(initialized, "=== Estado_Proyecto/Decisiones.md ===\n## usar_hash\nPorque sí.\n")
    assert code == 0, out
    assert f"## usar_hash\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nPorque sí.\n" in read_twin(initialized, "Estado_Proyecto/Decisiones.md")


def test_reporta_enlaces_rotos(initialized, batch):
    code, out = batch(initialized, "=== src/main.go ===\nUsa [[src/features/login.go.md#no_hay|x]] y [[src/main.go.md]].\n")
    assert code == 0, out
    assert "enlaces por corregir (2)" in out and "no existe la sección 'no_hay'" in out and "sin texto a mostrar" in out


def test_separador_dentro_de_bloque_de_codigo_no_corta(initialized, batch):
    code, out = batch(initialized, "=== src/main.go ===\nEjemplo:\n```\n=== src/features/login.go ===\n```\nFin.\n")
    assert code == 0, out
    assert "1 gemelo escrito" in out
    assert "=== src/features/login.go ===" in read_twin(initialized, "src/main.go.md")


def test_lote_invalido(initialized, batch):
    assert batch(initialized, "texto suelto\n=== src/main.go ===\nx\n")[0] == 2
    assert batch(initialized, "")[0] == 2
    code, out = batch(initialized, "=== src ===\nUna carpeta.\n")
    assert code == 2 and "carpeta" in out
    code, out = batch(initialized, "=== src/main.go ===\n\n")
    assert code == 2 and "sin contenido" in out


# ---- update con varias rutas -----------------------------------------------------
def test_update_varias_rutas(initialized, run):
    write_twin(initialized, "src/main.go.md", "A.\n")
    write_twin(initialized, "src/features/login.go.md", "B.\n")
    code, out = run(initialized, "update", "src/main.go", "src/features/login.go")
    assert code == 0, out
    assert _status(run, initialized)["ok"] == "2"


def test_update_varias_rutas_valida_antes_de_confirmar(initialized, run):
    write_twin(initialized, "src/main.go.md", "A.\n")
    code, _ = run(initialized, "update", "src/main.go", "src/features/login.go")  # el segundo está vacío
    assert code == 2
    assert not load(initialized).nodes["src/main.go.md"].get("last_synced_hash")


# ---- triviales ------------------------------------------------------------------
def test_trivial_no_cuenta_como_faltante(project, run):
    write(project, "web/estilos.css", "a { color: red }\n")
    write(project, "web/app.js", "console.log(1)\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    s = _status(run, project)
    assert s["trivial"] == "1" and s["faltante"] == "5"
    assert "web/estilos.css" not in run(project, "incomplete")[1]
    code, out = run(project, "update", "web/estilos.css")
    assert code == 0 and "trivial" in out
    # con contenido vuelve a las reglas normales
    write_twin(project, "web/estilos.css.md", "Tokens de color del tema.\n")
    assert _status(run, project)["desactualizado"] == "1"


def test_trivial_agregar_y_quitar(initialized, run):
    assert _status(run, initialized)["faltante"] == "4"
    assert run(initialized, "trivial", "Makefile")[0] == 0
    assert _status(run, initialized)["faltante"] == "3"
    assert "Makefile" in run(initialized, "trivial")[1]
    assert run(initialized, "trivial", "--remove", "Makefile")[0] == 0
    assert _status(run, initialized)["faltante"] == "4"


def test_gemelo_extenso_se_avisa(initialized, run):
    write_twin(initialized, "src/main.go.md", "x" * 3000 + "\n")
    run(initialized, "update", "src/main.go")
    assert "más largos que su código" in run(initialized, "incomplete")[1]


# ---- hook Stop de Claude Code --------------------------------------------------
@pytest.mark.skipif(shutil.which("git") is None, reason="sin git")
def test_claude_stop(project, run, monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)
    git(project, "init", "-q", "-b", "main")
    assert run(project, "init", "--yes")[0] == 0
    git(project, "add", "-A")
    git(project, "commit", "-qm", "inicial", "--no-verify")

    def stop(payload: dict):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        return run(project, "hook", "claude-stop")

    assert stop({})[0] == 0  # nada sin commitear: los faltantes viejos no bloquean
    write(project, "src/main.go", "package main\n// cambio\n")
    write(project, "src/nuevo.go", "package main\n")
    code, out = stop({})
    assert code == 2 and "faltante: src/main.go" in out and "src/nuevo.go (aún no está en el grafo)" in out
    assert stop({"stop_hook_active": True})[0] == 0  # no encierra al agente en un bucle
    monkeypatch.setattr("sys.stdin", io.StringIO("=== src/main.go ===\nEntrada.\n=== src/nuevo.go ===\nNuevo.\n"))
    assert run(project, "multiedit")[0] == 0
    assert stop({})[0] == 0


def test_no_inventa_fechas_en_secciones_que_no_toco(initialized, batch):
    write_twin(initialized, "src/main.go.md", "Entrada.\n\n## Funciones\n\n### vieja\nSin fechas.\n")
    assert batch(initialized, "=== src/main.go#nueva ===\nReciente.\n")[0] == 0
    twin = read_twin(initialized, "src/main.go.md")
    assert "### vieja\nSin fechas.\n" in twin and f"### nueva\n**Elaboración:** {HOY}" in twin
