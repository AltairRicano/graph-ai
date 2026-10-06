"""Estados y comandos de escritura."""

from __future__ import annotations

import json
import shutil

from grafo_ia.paths import twin_path

from conftest import assert_sano, load, read_twin, write, write_index

SRC = "src/src.md"
MASTER = "Index.md"


def _states(run, root):
    code, out = run(root, "status")
    assert code == 0, out
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line and not line.startswith("["))


# ---- estados ----------------------------------------------------------------------
def test_estados(initialized, run):
    root = initialized
    s = _states(run, root)
    assert s["faltante"] == "4" and s["ok"] == "0"  # raíz (Makefile), src, features y pagos
    # índice sin propósito sigue faltante y no se puede confirmar
    assert run(root, "update", "src")[0] == 2
    write_index(root, "src", "", purpose="Punto de entrada.")
    assert _states(run, root)["desactualizado"] == "1"  # escrito a mano, sin confirmar
    code, out = run(root, "update", "src")
    assert code == 0, out
    s = _states(run, root)
    assert s["ok"] == "1" and s["faltante"] == "3" and s["desactualizado"] == "0"
    write(root, "src/main.go", "package main\n// cambio\n")
    assert _states(run, root)["ok"] == "1"  # editar un archivo no cambia el estado de su carpeta
    write(root, "src/otro.go", "package main\n")
    assert _states(run, root)["desactualizado"] == "1"
    run(root, "update", "src")
    assert _states(run, root)["ok"] == "1"
    (root / "src/otro.go").unlink()
    assert _states(run, root)["desactualizado"] == "1"  # también cuando sale uno
    run(root, "update", "src")
    shutil.rmtree(root / "src")
    s = _states(run, root)
    assert s["huérfano"] == "3" and s["faltante"] == "1"  # src, features y pagos ya no existen
    assert_sano(root)


def test_update_sin_proposito_falla_y_no_cambia(initialized, run):
    before = (initialized / ".graph/index.json").read_text()
    code, out = run(initialized, "update", "src")
    assert code == 2 and "escríbelo primero" in out
    assert (initialized / ".graph/index.json").read_text() == before


def test_update_estado_proyecto_regenera_sin_hash(initialized, run):
    p = twin_path(initialized, "Estado_Proyecto/Plan.md")
    p.write_text(p.read_text() + "\n## pagos & Pagos\n### cobro\n- [ ] ver [[src/features/pagos/cobro.go|cobro]]\n", encoding="utf-8")
    code, out = run(initialized, "update", "Estado_Proyecto/Plan.md")
    assert code == 0, out
    g = load(initialized)
    assert g.relations("Estado_Proyecto/Plan.md", "src/features/pagos/cobro.go") == ["conoce"]
    assert "last_synced_hash" not in g.nodes["Estado_Proyecto/Plan.md"]


def test_update_rechaza_archivo_de_codigo(initialized, run):
    code, out = run(initialized, "update", "src/main.go")
    assert code == 2 and "es un archivo de código" in out


# ---- init / add / populate ------------------------------------------------------
def test_init_idempotente(initialized, run):
    before = (initialized / ".graph/index.json").read_text()
    docs = sorted(p.relative_to(initialized) for p in (initialized / ".graph").rglob("*.md"))
    code, out = run(initialized, "init", "--yes", "--no-git")
    assert code == 0, out
    assert (initialized / ".graph/index.json").read_text() == before
    assert sorted(p.relative_to(initialized) for p in (initialized / ".graph").rglob("*.md")) == docs


def test_init_reconstruye_tras_borrar_json(initialized, run):
    write_index(initialized, "src", "contenido\n")
    (initialized / ".graph/index.json").unlink()
    code, out = run(initialized, "init", "--yes", "--no-git")
    assert code == 0, out
    assert "src/main.go" in load(initialized).nodes
    assert "contenido\n" in read_twin(initialized, SRC)  # no se pierde contenido
    assert_sano(initialized)


def test_init_excluye_y_estructura(initialized):
    g = load(initialized)
    assert "Index.md" in g.nodes and "Estado_Proyecto/Plan.md" in g.nodes
    assert "src/features/features.md" in g.nodes
    assert g.tipo("src/main.go") == "codigo" and g.nodes["src/main.go"]["nombre"] == "main.go"
    assert not any("node_modules" in n or ".env" in n for n in g.nodes)
    assert "[[src/features/features.md|features]]" in read_twin(initialized, SRC)
    assert "[[src/main.go|main.go]]" in read_twin(initialized, SRC)
    assert not g.adj_out["Index.md"]  # enlaces estructurales no son aristas
    assert_sano(initialized)


def test_los_archivos_de_codigo_no_tienen_documento(initialized):
    docs = sorted(str(p.relative_to(initialized / ".graph")) for p in (initialized / ".graph").rglob("*.md"))
    assert docs == sorted([
        "Index.md", "src/src.md", "src/features/features.md", "src/features/pagos/pagos.md",
        "Estado_Proyecto/Estado_Proyecto.md", "Estado_Proyecto/Arquitectura.md", "Estado_Proyecto/Decisiones.md",
        "Estado_Proyecto/Estado.md", "Estado_Proyecto/Plan.md", "Estado_Proyecto/Tecnologias.md",
    ])


def test_indice_de_carpeta_nace_como_reporte(initialized, run):
    for index in (SRC, MASTER):
        text = read_twin(initialized, index)
        assert text.index("## Propósito") < text.index("## Relaciones") < text.index("## 📁 Carpetas") < text.index("## 📄 Archivos")
    assert "## Propósito" not in read_twin(initialized, "Estado_Proyecto/Estado_Proyecto.md")  # solo estructura
    # reconciliar no toca lo que el agente escribió en el reporte
    write_index(initialized, "src", "", purpose="Cobra los pedidos.")
    write(initialized, "src/nuevo.go", "package main\n")
    run(initialized, "add")
    after = read_twin(initialized, SRC)
    assert "Cobra los pedidos.\n" in after and "[[src/nuevo.go|nuevo.go]]" in after
    assert_sano(initialized)


def test_init_sin_terminal_pide_yes(project, run):
    code, out = run(project, "init")
    assert code == 2 and "--yes" in out


def test_add_sin_argumento_en_subcarpeta_recursivo(initialized, run):
    write(initialized, "src/nuevo/uno.py")
    write(initialized, "src/nuevo/sub/dos.py")
    code, out = run(initialized / "src/nuevo", "add")
    assert code == 0, out
    g = load(initialized)
    assert {"src/nuevo/nuevo.md", "src/nuevo/uno.py", "src/nuevo/sub/sub.md", "src/nuevo/sub/dos.py"} <= set(g.nodes)
    assert twin_path(initialized, "src/nuevo/sub/sub.md").exists()
    assert not (initialized / ".graph/src/nuevo/sub/dos.py.md").exists()
    assert "src/nuevo/nuevo.md" in read_twin(initialized, SRC)
    assert_sano(initialized)


def test_add_en_raiz_equivale_a_init(initialized, run):
    write(initialized, "otro/x.py")
    run(initialized, "add")
    via_add = json.loads((initialized / ".graph/index.json").read_text())
    run(initialized, "init", "--yes", "--no-git")
    via_init = json.loads((initialized / ".graph/index.json").read_text())
    assert via_add["nodes"] == via_init["nodes"]


def test_populate_no_sobreescribe(initialized, run):
    write_index(initialized, "src", "a mano\n")
    run(initialized, "populate")
    assert "a mano\n" in read_twin(initialized, SRC)


def test_borrar_codigo_quita_su_nodo(initialized, run):
    write_index(initialized, "src", "ver [[src/main.go|main]]\n")
    run(initialized, "update", "src")
    (initialized / "src/main.go").unlink()
    (initialized / "src/features/login.go").unlink()
    run(initialized, "add")
    g = load(initialized)
    assert "src/features/login.go" not in g.nodes and "src/main.go" not in g.nodes
    assert "src/features/features.md" in g.nodes  # la carpeta sigue (tiene a pagos)
    assert "[[src/main.go|main.go]]" not in read_twin(initialized, SRC)  # sale de la lista
    assert "src: salieron: main.go; 1 enlace que no resuelve" in run(initialized, "incomplete")[1]
    assert_sano(initialized)


def test_movimiento_escapado_por_hash(initialized, run):
    write_index(initialized, "src", "principal: [[src/main.go|main]]\n")
    write_index(initialized, "", "ver [[src/main.go|main]]\n")
    run(initialized, "update", "src")
    run(initialized, "update", ".")
    (initialized / "src/main.go").rename(initialized / "src/app.go")
    code, out = run(initialized, "add")
    assert code == 0, out
    g = load(initialized)
    assert "src/app.go" in g.nodes and "src/main.go" not in g.nodes
    assert "[[src/app.go|main]]" in read_twin(initialized, MASTER) and "[[src/app.go|main]]" in read_twin(initialized, SRC)
    assert g.nodes["src/app.go"]["last_synced_hash"]
    assert g.relations(MASTER, "src/app.go") == ["conoce"]
    assert_sano(initialized)


def test_movimiento_no_uno_a_uno_no_adivina(initialized, run):
    for rel in ("src/main.go", "src/features/login.go"):
        write(initialized, rel, "igual\n")
    write_index(initialized, "src", "c [[src/main.go|main]]\n")
    write_index(initialized, "src/features", "c\n")
    run(initialized, "update", "src", "src/features")
    (initialized / "src/main.go").rename(initialized / "src/a.go")
    (initialized / "src/features/login.go").rename(initialized / "src/b.go")
    run(initialized, "add")
    g = load(initialized)
    assert "src/main.go" not in g.nodes and {"src/a.go", "src/b.go"} <= set(g.nodes)
    assert "[[src/main.go|main]]" in read_twin(initialized, SRC)  # el enlace no se reescribe a ciegas


def test_pendiente_se_vuelve_arista_al_nacer(initialized, run):
    write_index(initialized, "", "futuro: [[src/pago.go|pago]]\n")
    run(initialized, "update", ".")
    code, out = run(initialized, "incomplete")
    assert "src/pago.go" in out
    write(initialized, "src/pago.go", "package x\n")
    run(initialized, "add", "src")
    assert load(initialized).relations(MASTER, "src/pago.go") == ["conoce"]


# ---- remove / prune ---------------------------------------------------------------
def test_remove_archivo_limpia_enlaces_y_aristas(initialized, run):
    write_index(initialized, "", "usa [[src/main.go#main|la entrada]] y `[[src/main.go|x]]`\n")
    run(initialized, "update", ".")
    code, out = run(initialized, "remove", "src/main.go")
    assert code == 0, out
    assert "Index.md" in out and "sigue existiendo" in out
    text = read_twin(initialized, MASTER)
    assert "usa la entrada y `[[src/main.go|x]]`" in text  # el código inline no se toca
    g = load(initialized)
    assert "src/main.go" not in g.nodes
    assert not any("src/main.go" in e for e in g.edges)
    assert (initialized / "src/main.go").exists()  # nunca borra código real
    assert "src/main.go" not in read_twin(initialized, SRC)
    assert_sano(initialized)


def test_remove_carpeta_completa(initialized, run):
    code, out = run(initialized, "remove", "src/features")
    assert code == 0, out
    g = load(initialized)
    assert not any(n.startswith("src/features") for n in g.nodes)
    assert not (initialized / ".graph/src/features").exists()
    assert_sano(initialized)


def test_remove_rechaza_rutas_de_graph_estado_y_raiz(initialized, run):
    assert run(initialized, "remove", ".graph/src/src.md")[0] == 2
    assert run(initialized, "remove", "Estado_Proyecto/Plan.md")[0] == 2
    assert run(initialized, "remove", ".")[0] == 2


def test_prune_solo_huerfanos_y_acotado(initialized, run):
    write_index(initialized, "src/features/pagos", "a\n")
    write_index(initialized, "", "ver [[src/main.go|main]] y [[src/features/pagos|pagos]]\n")
    run(initialized, "update", ".")
    (initialized / "src/main.go").unlink()
    shutil.rmtree(initialized / "src/features/pagos")
    code, out = run(initialized, "prune", "src/features")
    assert code == 0, out
    g = load(initialized)
    assert "src/features/pagos/pagos.md" not in g.nodes and "src/features/pagos/cobro.go" not in g.nodes
    assert not (initialized / ".graph/src/features/pagos").exists()
    assert "src/main.go" in g.nodes  # fuera del alcance
    run(initialized, "prune")
    g = load(initialized)
    assert "src/main.go" not in g.nodes
    assert "ver main y pagos" in read_twin(initialized, MASTER)
    assert "src/features/login.go" in g.nodes  # no huérfano
    assert_sano(initialized)


# ---- mv ------------------------------------------------------------------------------
def test_mv_tabla_de_reescritura(initialized, run):
    write_index(initialized, "", (
        "a [[src/main.go#main|texto]]\n"
        "b [[src/main.go|sin seccion]]\n"
        "c [[src/main.go]]\n"
        "d [[src/main.go#Otra|x]] y [[src/main.go#Otra|y]]\n"
        "e [[main.go|corta]]\n"
    ))
    run(initialized, "update", ".")
    code, out = run(initialized, "mv", "src/main.go", "src/headless.go")
    assert code == 0, out
    text = read_twin(initialized, MASTER)
    assert "[[src/headless.go#main|texto]]" in text
    assert "[[src/headless.go|sin seccion]]" in text
    assert "c [[src/headless.go]]" in text
    assert "[[src/headless.go#Otra|x]] y [[src/headless.go#Otra|y]]" in text
    assert "[[headless.go|corta]]" in text
    g = load(initialized)
    assert g.relations(MASTER, "src/headless.go") == ["conoce"]
    assert "src/main.go" not in g.nodes
    assert "[[src/headless.go|headless.go]]" in read_twin(initialized, SRC)
    assert_sano(initialized)


def test_mv_carpeta_con_descendientes(initialized, run):
    write_index(initialized, "src/features", "", purpose="Login y cobros.")
    write_index(initialized, "", "[[src/features|features]], [[src/features/features.md|largo]] y [[src/features/pagos/cobro.go#c|c]]\n")
    run(initialized, "update", ".", "src/features")
    code, out = run(initialized, "mv", "src/features", "src/modulos")
    assert code == 0, out
    g = load(initialized)
    assert {"src/modulos/modulos.md", "src/modulos/login.go", "src/modulos/pagos/pagos.md", "src/modulos/pagos/cobro.go"} <= set(g.nodes)
    assert not any(n.startswith("src/features") for n in g.nodes)
    text = read_twin(initialized, MASTER)
    assert "[[src/modulos|features]]" in text and "[[src/modulos/modulos.md|largo]]" in text
    assert "[[src/modulos/pagos/cobro.go#c|c]]" in text
    assert "Login y cobros." in read_twin(initialized, "src/modulos/modulos.md")  # el reporte viaja con la carpeta
    assert not (initialized / ".graph/src/features").exists()
    assert g.nodes["src/modulos/modulos.md"]["archivos_confirmados"] == ["login.go"]
    assert_sano(initialized)


def test_mv_rechaza_destino_existente_sin_cambios(initialized, run):
    before = (initialized / ".graph/index.json").read_text()
    code, out = run(initialized, "mv", "src/main.go", "src/features/login.go")
    assert code == 2
    assert (initialized / ".graph/index.json").read_text() == before


def test_mv_rechaza_ruta_de_graph(initialized, run):
    assert run(initialized, "mv", ".graph/src/src.md", "x")[0] == 2


def test_mv_solo_mayusculas(initialized, run):
    code, out = run(initialized, "mv", "src/main.go", "src/Main.go")
    assert code == 0, out
    assert "src/Main.go" in load(initialized).nodes
    assert_sano(initialized)


# ---- fecha del header en update ----------------------------------------------------
def test_update_mueve_solo_la_fecha_del_header(initialized, run):
    from grafo_ia.templates import today

    p = twin_path(initialized, SRC)
    p.write_text(p.read_text().replace(f"fecha_elaboracion: {today()}", "fecha_elaboracion: 2026-01-01")
                 .replace(f"fecha_actualizacion: {today()}", "fecha_actualizacion: 2026-01-01"), encoding="utf-8")
    write_index(initialized, "src", (
        "## regla\n**Elaboración:** 2025-01-01 | **Actualización:** 2025-02-02\n\n"
        "fecha_actualizacion: 1999-01-01 (texto en el cuerpo, no se toca)\n"
    ))
    code, out = run(initialized, "update", "src")
    assert code == 0, out
    header, body = read_twin(initialized, SRC).split("\n---\n", 1)
    assert f"fecha_actualizacion: {today()}" in header
    assert "fecha_elaboracion: 2026-01-01" in header  # la de elaboración no cambia
    assert "**Actualización:** 2025-02-02" in body  # fechas de sección independientes
    assert "fecha_actualizacion: 1999-01-01" in body


def test_update_estado_proyecto_mueve_fecha(initialized, run):
    from grafo_ia.templates import today

    p = twin_path(initialized, "Estado_Proyecto/Plan.md")
    p.write_text(p.read_text().replace(f"fecha_actualizacion: {today()}", "fecha_actualizacion: 2000-01-01"), encoding="utf-8")
    run(initialized, "update", "Estado_Proyecto/Plan.md")
    assert f"fecha_actualizacion: {today()}" in p.read_text()


def test_touch_updated_sin_frontmatter_o_sin_campo():
    from grafo_ia.templates import touch_updated

    assert touch_updated("sin frontmatter\nfecha_actualizacion: x\n", "2026-01-01") == "sin frontmatter\nfecha_actualizacion: x\n"
    assert touch_updated("---\ntipo: indice\n---\ncuerpo\n", "2026-01-01") == "---\ntipo: indice\nfecha_actualizacion: 2026-01-01\n---\ncuerpo\n"
    assert touch_updated("---\r\nfecha_actualizacion: a\r\n---\r\nx\r\n", "b") == "---\r\nfecha_actualizacion: b\r\n---\r\nx\r\n"


def test_update_fallido_no_toca_la_fecha(initialized, run):
    before = read_twin(initialized, SRC)
    assert run(initialized, "update", "src")[0] == 2  # sin propósito
    assert read_twin(initialized, SRC) == before


def test_incomplete_prioriza_desactualizados(initialized, run):
    write_index(initialized, "src", "", purpose="Punto de entrada.")
    run(initialized, "update", "src")
    write(initialized, "src/otro.go", "package main\n")
    code, out = run(initialized, "incomplete")
    assert code == 0
    assert out.index("desactualizados (1)") < out.index("faltantes (3)") < out.index("pendientes por crear")
