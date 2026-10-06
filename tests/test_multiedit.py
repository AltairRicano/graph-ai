"""`graph multiedit`, `graph update` con varias rutas, triviales y el hook Stop."""

from __future__ import annotations

import io
import json
import shutil

import pytest

from grafo_ia import templates

from conftest import assert_sano, git, load, read_twin, write, write_index

HOY = templates.today()
SRC = "src/src.md"
FEATURES = "src/features/features.md"


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
def test_llena_varios_indices_y_los_confirma(initialized, run, batch):
    code, out = batch(initialized, (
        "=== src#Propósito ===\n"
        "Punto de entrada: arranca con `$HOME` y \"comillas\".\n"
        "=== src/features#Propósito ===\n"
        "Login, usa [[src/main.go#main|main]].\n"
        "=== src/features#Relaciones ===\n"
        "- [[src/features/login.go|login.go]] → [[src/main.go|main.go]]: arranca la sesión.\n"
    ))
    assert code == 0, out
    assert "2 documentos escritos y confirmados" in out and "[AVISO]" not in out
    src = read_twin(initialized, SRC)
    assert src.startswith("---\ntipo: indice\n")
    assert f"## Propósito\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nPunto de entrada: arranca con `$HOME` y \"comillas\".\n" in src
    assert "- [[src/main.go|main.go]]" in src  # la lista de archivos sigue ahí
    g = load(initialized)
    assert g.nodes[SRC]["archivos_confirmados"] == ["main.go"]
    assert g.nodes["src/main.go"]["last_synced_hash"]
    assert g.relations(FEATURES, "src/main.go") == ["conoce"]
    status = _status(run, initialized)
    assert (status["ok"], status["faltante"], status["desactualizado"]) == ("2", "2", "0")
    assert_sano(initialized)


def test_un_archivo_de_codigo_no_es_un_blanco(initialized, batch):
    before = read_twin(initialized, SRC)
    code, out = batch(initialized, "=== src#Propósito ===\nEntrada.\n=== src/main.go ===\nNo.\n=== src/main.go#main ===\nTampoco.\n")
    assert code == 2 and "no se aplicó nada" in out
    assert out.count("es un archivo de código") == 2 and "comentario" in out
    assert read_twin(initialized, SRC) == before


def test_seccion_reemplaza_y_conserva_elaboracion(initialized, batch):
    write_index(initialized, "src", "## redondeo\n**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-01\n\nViejo.\n\n## otra\n**Elaboración:** 2026-01-02 | **Actualización:** 2026-01-02\n\nIgual.\n")
    code, out = batch(initialized, "=== src#redondeo ===\n## redondeo\nNuevo.\n")
    assert code == 0, out
    src = read_twin(initialized, SRC)
    assert f"## redondeo\n**Elaboración:** 2026-01-01 | **Actualización:** {HOY}\n\nNuevo.\n" in src
    assert "## otra\n**Elaboración:** 2026-01-02 | **Actualización:** 2026-01-02\n\nIgual.\n" in src  # la que no se tocó no se mueve
    assert "Viejo." not in src and src.count("## redondeo") == 1  # el heading repetido en el lote se descarta


def test_seccion_nueva_va_antes_de_las_listas(initialized, batch):
    code, out = batch(initialized, "=== src#Propósito ===\nEntrada.\n=== src#Redondeo de centavos ===\nUna sola vez.\n=== src ===\n## Otra regla\nAl final del reporte.\n")
    assert code == 0, out
    src = read_twin(initialized, SRC)
    order = [src.index(h) for h in ("## Propósito", "## Relaciones", "## Redondeo de centavos", "## Otra regla", "## 📁 Carpetas", "## 📄 Archivos")]
    assert order == sorted(order)
    assert f"## Otra regla\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nAl final del reporte.\n" in src
    assert "**Elaboración:**" not in src[src.index("## 📁 Carpetas"):]  # las listas no se fechan
    assert "## Relaciones\n\n## Redondeo" in src  # una sección vacía que nadie tocó no gana fecha


def test_override_conserva_las_listas_y_append_agrega(initialized, batch):
    write_index(initialized, "src", "## vieja\nSe va.\n")
    code, out = batch(initialized, "=== src [override] ===\n## Propósito\nDe cero.\n=== src#Propósito [append] ===\nSegunda línea.\n")
    assert code == 0, out
    src = read_twin(initialized, SRC)
    assert "Se va." not in src and "De cero.\n\nSegunda línea.\n" in src
    assert "## 📁 Carpetas\n- [[src/features/features.md|features]]\n" in src and "- [[src/main.go|main.go]]" in src
    assert "1 cuerpo reemplazado" in out


def test_las_listas_no_se_escriben(initialized, batch):
    code, out = batch(initialized, "=== src#📄 Archivos ===\n- inventado\n")
    assert code == 2 and "las mantiene el CLI" in out


def test_ruta_inexistente_aborta_todo(initialized, batch):
    before = read_twin(initialized, SRC)
    code, out = batch(initialized, "=== src#Propósito ===\nEntrada.\n=== src/no_existe ===\nNada.\n=== node_modules ===\nExcluida.\n")
    assert code == 2 and "no se aplicó nada" in out
    assert "no existe en el proyecto ni en el grafo" in out and "está excluido del grafo" in out
    assert read_twin(initialized, SRC) == before


def test_carpeta_y_archivos_nuevos_entran_solos(initialized, run, batch):
    write(initialized, "src/nuevo/uno.py", "def uno():\n    pass\n")
    write(initialized, "src/otro.go", "package main\n")
    code, out = batch(initialized, "=== src/nuevo#Propósito ===\nMódulo nuevo.\n=== src#Propósito ===\nEntrada.\n")
    assert code == 0, out
    assert "nodos nuevos en el grafo" in out
    g = load(initialized)
    assert g.tipo("src/nuevo/nuevo.md") == "indice" and g.tipo("src/nuevo/uno.py") == "codigo"
    assert g.nodes[SRC]["archivos_confirmados"] == ["main.go", "otro.go"]
    src = read_twin(initialized, SRC)
    assert "- [[src/nuevo/nuevo.md|nuevo]]" in src and "- [[src/otro.go|otro.go]]" in src  # listas al día
    assert "src/nuevo" not in run(initialized, "incomplete", "src/nuevo")[1].split("faltantes")[1]
    assert_sano(initialized)


def test_lote_por_archivo_se_borra(initialized, run):
    lote = write(initialized, "lote.txt", "=== src#Propósito ===\nEntrada.\n")
    assert run(initialized, "multiedit", "-f", "lote.txt")[0] == 0
    assert not lote.exists()
    lote = write(initialized, "lote.txt", "=== src#Propósito ===\nOtra.\n")
    assert run(initialized, "multiedit", "-f", "lote.txt", "--keep")[0] == 0
    assert lote.exists() and "Otra." in read_twin(initialized, SRC)


def test_estado_proyecto_por_seccion(initialized, batch):
    code, out = batch(initialized, "=== Estado_Proyecto/Estado.md#Hecho ===\n- Login con [[src/features/login.go|login]].\n")
    assert code == 0, out
    estado = read_twin(initialized, "Estado_Proyecto/Estado.md")
    assert "## Hecho\n- Login con" in estado and "## En curso" in estado
    assert "Lo que ya está completo" not in estado  # el texto guía de la sección se reemplazó
    assert "**Elaboración:**" not in estado  # Estado no lleva fechas por sección
    assert load(initialized).relations("Estado_Proyecto/Estado.md", "src/features/login.go") == ["conoce"]
    assert batch(initialized, "=== Estado_Proyecto ===\nNo.\n")[0] == 2  # su índice solo lleva listas


def test_decisiones_fecha_cada_decision(initialized, batch):
    code, out = batch(initialized, "=== Estado_Proyecto/Decisiones.md ===\n## usar_hash\nPorque sí.\n")
    assert code == 0, out
    assert f"## usar_hash\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nPorque sí.\n" in read_twin(initialized, "Estado_Proyecto/Decisiones.md")


def test_reporta_enlaces_rotos_y_lo_que_sigue_incompleto(initialized, batch):
    write(initialized, "src/main.go", "package main\n\nfunc main() {}\n\nfunc arrancar() {}\n")
    code, out = batch(initialized, (
        "=== src#Propósito ===\nVer [[src/nada.go|nada]], [[src/main.go#arrancar|arrancar]], "
        "[[src/main.go#ya_no_esta|vieja]] y [[src/features]].\n"
        "=== src/features#Relaciones ===\n- [[src/features/login.go|login.go]] → [[src/main.go|main.go]]: algo.\n"
    ))
    assert code == 0, out
    assert "enlaces por corregir (3)" in out
    assert "[[src/nada.go|nada]] (no existe el destino)" in out
    assert "'ya_no_esta' ya no aparece en src/main.go" in out and "arrancar]]" not in out.split("corregir")[1]
    assert "(sin texto a mostrar)" in out
    # un enlace a algo que nunca existió se avisa, pero no desactualiza el índice
    assert "índices que siguen incompletos (1)" in out and "src/features: sin `## Propósito`" in out
    assert "enlaces que" not in out.split("incompletos")[1]


def test_separador_dentro_de_bloque_de_codigo_no_corta(initialized, batch):
    code, out = batch(initialized, "=== src#Propósito ===\nEjemplo:\n```\n=== src/features ===\n```\nFin.\n")
    assert code == 0, out
    assert "=== src/features ===" in read_twin(initialized, SRC)
    assert "1 documento escrito y confirmado" in out


def test_lote_invalido(initialized, batch):
    assert batch(initialized, "")[0] == 2
    code, out = batch(initialized, "texto suelto\n=== src ===\nx\n")
    assert code == 2 and "antes del primer separador" in out
    code, out = batch(initialized, "=== src#Propósito ===\n\n")
    assert code == 2 and "entrada sin contenido" in out
    code, out = batch(initialized, "=== src#Propósito ===\n## Propósito\n")
    assert code == 2 and "solo trae el heading" in out


# ---- estados por carpeta --------------------------------------------------------------
def test_entrar_o_salir_archivos_desactualiza_y_editar_no(initialized, run, batch):
    assert batch(initialized, "=== src/features#Propósito ===\nLogin.\n")[0] == 0
    write(initialized, "src/features/login.go", "package features\n// otro cuerpo\n")
    assert _status(run, initialized)["desactualizado"] == "0"  # editar el cuerpo no desactualiza
    assert "~ login.go" in run(initialized, "diff", "src/features")[1]  # pero diff sí lo dice
    write(initialized, "src/features/logout.go", "package features\n")
    inc = run(initialized, "incomplete", "src/features/login.go")[1]  # un archivo pide su carpeta
    assert "desactualizados (1)" in inc and "src/features: entraron: logout.go" in inc
    assert "pagos" not in inc  # y solo esa carpeta, no las de adentro
    out = run(initialized, "diff")[1]
    assert "src/features (desactualizado)" in out and "+ logout.go" in out
    (initialized / "src/features/login.go").unlink()
    assert "entraron: logout.go; salieron: login.go" in run(initialized, "incomplete")[1]
    assert batch(initialized, "=== src/features#Propósito [append] ===\nY logout.\n")[0] == 0  # escribir confirma
    assert _status(run, initialized)["desactualizado"] == "0"
    assert load(initialized).nodes[FEATURES]["archivos_confirmados"] == ["logout.go"]
    assert "src/features/login.go" not in load(initialized).nodes
    assert_sano(initialized)


def test_indice_escrito_a_mano_pide_confirmarse(initialized, run):
    write_index(initialized, "src", "## regla\nAlgo.\n")
    assert "src: nunca se confirmó" in run(initialized, "incomplete")[1]
    assert run(initialized, "update", "src")[0] == 0
    assert _status(run, initialized)["desactualizado"] == "0"


# ---- update ---------------------------------------------------------------------------
def test_update_varias_rutas(initialized, run):
    write_index(initialized, "src", "Ver [[src/features|features]].\n")
    write_index(initialized, "src/features", "## login\nAlgo.\n")
    code, out = run(initialized, "update", "src", "src/features", "Estado_Proyecto/Plan.md")
    assert code == 0, out
    assert "src: índice confirmado (1 archivo)" in out and "src/features: índice confirmado" in out
    assert "+ src/features/features.md" in out and "Estado_Proyecto/Plan.md: aristas regeneradas" in out


def test_update_valida_todo_antes_de_confirmar(initialized, run):
    write_index(initialized, "src", "Algo.\n")
    code, out = run(initialized, "update", "src", "src/features")
    assert code == 2 and "no tiene `## Propósito`" in out
    assert "archivos_confirmados" not in load(initialized).nodes[SRC]  # no confirmó nada
    code, out = run(initialized, "update", "src/main.go")
    assert code == 2 and "es un archivo de código" in out and "graph update <carpeta>" in out


# ---- triviales ------------------------------------------------------------------------
def test_trivial_no_cuenta_como_faltante(project, run):
    write(project, "web/estilos/base.css", "body {}\n")
    write(project, "web/estilos/tema.css", "a {}\n")
    write(project, "web/app.js", "let a = 1\n")
    assert run(project, "init", "--yes", "--no-git")[0] == 0
    status = _status(run, project)
    assert status["faltante"] == "5"  # raíz, src, features, pagos y web
    assert status["trivial"] == "1"  # web/estilos solo tiene estilos
    inc = run(project, "incomplete")[1]
    assert "web: sin `## Propósito`" in inc and "web/estilos" not in inc
    write(project, "web/estilos/calculo.js", "let b = 2\n")  # ya tiene algo que contar
    assert "web/estilos: sin `## Propósito`" in run(project, "incomplete")[1]


def test_trivial_agregar_y_quitar(initialized, run):
    assert _status(run, initialized)["faltante"] == "4"
    assert run(initialized, "trivial", "Makefile")[0] == 0
    assert _status(run, initialized)["faltante"] == "3"
    assert "Makefile" in run(initialized, "trivial")[1]
    assert run(initialized, "trivial", "--remove", "Makefile")[0] == 0
    assert _status(run, initialized)["faltante"] == "4"


def test_indice_extenso_se_avisa(initialized, run, batch):
    code, out = batch(initialized, "=== src#Propósito ===\n" + "Relleno que repite el código. " * 200 + "\n")
    assert code == 0, out
    assert "índices más largos que el código de su carpeta" in out and "src:" in out
    assert "índices más largos que el código de su carpeta" in run(initialized, "incomplete")[1]


# ---- hook Stop ------------------------------------------------------------------------
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
    write(project, "lib/nuevo.go", "package lib\n")
    code, out = stop({})
    assert code == 2 and "faltante: src: sin `## Propósito`" in out and "faltante: lib: aún no está en el grafo" in out
    assert "features" not in out  # solo las carpetas tocadas
    assert stop({"stop_hook_active": True})[0] == 0  # no encierra al agente en un bucle
    monkeypatch.setattr("sys.stdin", io.StringIO("=== src#Propósito ===\nEntrada.\n=== lib#Propósito ===\nNuevo.\n"))
    assert run(project, "multiedit")[0] == 0
    assert stop({})[0] == 0


def test_no_inventa_fechas_en_secciones_que_no_toco(initialized, batch):
    write_index(initialized, "src", "## sin_fecha\nNadie la fechó.\n")
    assert batch(initialized, "=== src#otra ===\nNueva.\n")[0] == 0
    src = read_twin(initialized, SRC)
    assert "## sin_fecha\nNadie la fechó.\n" in src
    assert f"## otra\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nNueva.\n" in src


def test_carpeta_borrada_queda_huerfana_si_tenia_contenido(initialized, run, batch):
    assert batch(initialized, "=== src/features/pagos#Propósito ===\nCobros.\n")[0] == 0
    shutil.rmtree(initialized / "src/features/pagos")
    assert run(initialized, "add")[0] == 0
    g = load(initialized)
    assert "src/features/pagos/pagos.md" in g.nodes and "src/features/pagos/cobro.go" not in g.nodes
    assert "huérfanos (1)" in run(initialized, "incomplete")[1]
    assert batch(initialized, "=== src/features/pagos#Propósito ===\nYa no.\n")[0] == 2
    assert run(initialized, "prune")[0] == 0
    assert "src/features/pagos/pagos.md" not in load(initialized).nodes
    assert_sano(initialized)


def test_enlace_que_deja_de_resolver_desactualiza_y_el_pendiente_no(initialized, run, batch):
    write(initialized, "src/main.go", "package main\n\nfunc main() {}\n\nfunc arrancar() {}\n")
    code, out = batch(initialized, (
        "=== src#Propósito ===\nArranca con [[src/main.go#arrancar|arrancar]] y usa [[src/features/login.go|login]]. "
        "El frontend irá en [[web|web]].\n"
    ))
    assert code == 0, out
    assert "[[web|web]] (no existe el destino)" in out  # se avisa al escribir...
    assert "siguen incompletos" not in out  # ...pero el índice queda al día
    assert _status(run, initialized)["desactualizado"] == "0"
    assert "pendientes por crear (1)" in run(initialized, "incomplete")[1]
    write(initialized, "src/main.go", "package main\n\nfunc main() {}\n")  # la función enlazada desaparece
    assert "src: 1 enlace que dejó de resolver" in run(initialized, "incomplete")[1]
    (initialized / "src/features/login.go").unlink()  # y un archivo enlazado de otra carpeta también
    assert "src: 2 enlaces que dejaron de resolver" in run(initialized, "incomplete")[1]


def test_init_dice_que_indices_faltan_por_escribir(project, run):
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0, out
    assert "índices por escribir (4): ., src, src/features, src/features/pagos" in out
