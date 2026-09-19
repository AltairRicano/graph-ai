"""Estados y comandos de escritura."""

from __future__ import annotations

import json

from grafo_ia.paths import twin_path

from conftest import assert_sano, load, read_twin, write, write_twin


def _states(run, root):
    code, out = run(root, "status")
    assert code == 0, out
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line and not line.startswith("["))


# ---- estados ----------------------------------------------------------------------
def test_estados(initialized, run):
    root = initialized
    s = _states(run, root)
    assert s["faltante"] == "4" and s["ok"] == "0"  # README, main.go, login.go, cobro.go
    # gemelo con solo frontmatter sigue faltante
    assert run(root, "update", "src/main.go")[0] == 2
    write_twin(root, "src/main.go.md", "Punto de entrada.\n")
    code, out = run(root, "update", "src/main.go")
    assert code == 0, out
    s = _states(run, root)
    assert s["ok"] == "1" and s["faltante"] == "3"
    write(root, "src/main.go", "package main\n// cambio\n")
    assert _states(run, root)["desactualizado"] == "1"
    run(root, "update", "src/main.go")
    assert _states(run, root)["ok"] == "1"
    (root / "src/main.go").unlink()
    assert _states(run, root)["huérfano"] == "1"
    assert_sano(root)


def test_update_sin_gemelo_falla_y_no_cambia(initialized, run):
    twin_path(initialized, "src/main.go.md").unlink()
    before = (initialized / ".graph/index.json").read_text()
    code, out = run(initialized, "update", "src/main.go")
    assert code == 2 and "créalo primero" in out
    assert (initialized / ".graph/index.json").read_text() == before


def test_update_estado_proyecto_regenera_sin_hash(initialized, run):
    p = twin_path(initialized, "Estado_Proyecto/Plan.md")
    p.write_text(p.read_text() + "\n## pagos & Pagos\n### cobro\n- [ ] ver [[src/features/pagos/cobro.go.md|cobro]]\n", encoding="utf-8")
    code, out = run(initialized, "update", "Estado_Proyecto/Plan.md")
    assert code == 0, out
    g = load(initialized)
    assert g.relations("Estado_Proyecto/Plan.md", "src/features/pagos/cobro.go.md") == ["conoce"]
    assert "last_synced_hash" not in g.nodes["Estado_Proyecto/Plan.md"]


def test_update_rechaza_carpeta(initialized, run):
    assert run(initialized, "update", "src")[0] == 2


# ---- init / add / populate ------------------------------------------------------
def test_init_idempotente(initialized, run):
    before = (initialized / ".graph/index.json").read_text()
    twins = sorted(p.relative_to(initialized) for p in (initialized / ".graph").rglob("*.md"))
    code, out = run(initialized, "init", "--yes", "--no-git")
    assert code == 0, out
    assert (initialized / ".graph/index.json").read_text() == before
    assert sorted(p.relative_to(initialized) for p in (initialized / ".graph").rglob("*.md")) == twins


def test_init_reconstruye_tras_borrar_json(initialized, run):
    write_twin(initialized, "src/main.go.md", "contenido\n")
    (initialized / ".graph/index.json").unlink()
    code, out = run(initialized, "init", "--yes", "--no-git")
    assert code == 0, out
    assert "src/main.go.md" in load(initialized).nodes
    assert read_twin(initialized, "src/main.go.md").endswith("contenido\n")  # no se pierde contenido
    assert_sano(initialized)


def test_init_excluye_y_estructura(initialized):
    g = load(initialized)
    assert "Index.md" in g.nodes and "Estado_Proyecto/Plan.md" in g.nodes
    assert "src/features/features.md" in g.nodes
    assert not any("node_modules" in n or ".env" in n for n in g.nodes)
    assert "src/features/features.md" in read_twin(initialized, "src/src.md")
    assert "src/main.go.md" in read_twin(initialized, "src/src.md")
    assert not g.adj_out["Index.md"]  # enlaces estructurales no son aristas
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
    assert {"src/nuevo/nuevo.md", "src/nuevo/uno.py.md", "src/nuevo/sub/sub.md", "src/nuevo/sub/dos.py.md"} <= set(g.nodes)
    assert twin_path(initialized, "src/nuevo/sub/dos.py.md").exists()
    assert "src/nuevo/nuevo.md" in read_twin(initialized, "src/src.md")
    assert_sano(initialized)


def test_add_en_raiz_equivale_a_init(initialized, run):
    write(initialized, "otro/x.py")
    run(initialized, "add")
    via_add = json.loads((initialized / ".graph/index.json").read_text())
    run(initialized, "init", "--yes", "--no-git")
    via_init = json.loads((initialized / ".graph/index.json").read_text())
    assert via_add["nodes"] == via_init["nodes"]


def test_populate_no_sobreescribe(initialized, run):
    write_twin(initialized, "src/main.go.md", "a mano\n")
    run(initialized, "populate")
    assert read_twin(initialized, "src/main.go.md").endswith("a mano\n")


def test_borrar_codigo_vacio_quita_nodo_con_contenido_huerfano(initialized, run):
    write_twin(initialized, "src/main.go.md", "tiene contenido\n")
    (initialized / "src/main.go").unlink()
    (initialized / "src/features/login.go").unlink()
    run(initialized, "add")
    g = load(initialized)
    assert "src/features/login.go.md" not in g.nodes  # vacío: se va solo
    assert "src/main.go.md" in g.nodes  # con contenido: huérfano
    assert not twin_path(initialized, "src/features/login.go.md").exists()
    assert_sano(initialized)


def test_movimiento_escapado_por_hash(initialized, run):
    write_twin(initialized, "src/main.go.md", "principal\n")
    write_twin(initialized, "README.md.md", "ver [[src/main.go.md|main]]\n")
    run(initialized, "update", "src/main.go")
    run(initialized, "update", "README.md")
    (initialized / "src/main.go").rename(initialized / "src/app.go")
    code, out = run(initialized, "add")
    assert code == 0, out
    g = load(initialized)
    assert "src/app.go.md" in g.nodes and "src/main.go.md" not in g.nodes
    assert "[[src/app.go.md|main]]" in read_twin(initialized, "README.md.md")
    assert g.nodes["src/app.go.md"]["last_synced_hash"]
    assert_sano(initialized)


def test_movimiento_no_uno_a_uno_no_adivina(initialized, run):
    for rel in ("src/main.go", "src/features/login.go"):
        write(initialized, rel, "igual\n")
        write_twin(initialized, rel + ".md", "c\n")
        run(initialized, "update", rel)
    (initialized / "src/main.go").rename(initialized / "src/a.go")
    (initialized / "src/features/login.go").rename(initialized / "src/b.go")
    run(initialized, "add")
    g = load(initialized)
    assert "src/main.go.md" in g.nodes and "src/a.go.md" in g.nodes  # huérfano + faltante


def test_pendiente_se_vuelve_arista_al_nacer(initialized, run):
    write_twin(initialized, "README.md.md", "futuro: [[src/pago.go.md|pago]]\n")
    run(initialized, "update", "README.md")
    code, out = run(initialized, "incomplete")
    assert "src/pago.go.md" in out
    write(initialized, "src/pago.go", "package x\n")
    run(initialized, "add", "src")
    assert load(initialized).relations("README.md.md", "src/pago.go.md") == ["conoce"]


# ---- remove / prune ---------------------------------------------------------------
def test_remove_archivo_limpia_enlaces_y_aristas(initialized, run):
    write_twin(initialized, "README.md.md", "usa [[src/main.go.md#main|la entrada]] y `[[src/main.go.md|x]]`\n")
    run(initialized, "update", "README.md")
    code, out = run(initialized, "remove", "src/main.go")
    assert code == 0, out
    assert "README.md.md" in out and "sigue existiendo" in out
    text = read_twin(initialized, "README.md.md")
    assert "usa la entrada y `[[src/main.go.md|x]]`" in text  # el código inline no se toca
    g = load(initialized)
    assert "src/main.go.md" not in g.nodes
    assert not any("src/main.go.md" in e for e in g.edges)
    assert (initialized / "src/main.go").exists()  # nunca borra código real
    assert "src/main.go.md" not in read_twin(initialized, "src/src.md")
    assert_sano(initialized)


def test_remove_carpeta_completa(initialized, run):
    code, out = run(initialized, "remove", "src/features")
    assert code == 0, out
    g = load(initialized)
    assert not any(n.startswith("src/features") for n in g.nodes)
    assert not (initialized / ".graph/src/features").exists()
    assert_sano(initialized)


def test_remove_rechaza_gemelo_e_indice(initialized, run):
    assert run(initialized, "remove", ".graph/src/src.md")[0] == 2
    assert run(initialized, "remove", "Estado_Proyecto/Plan.md")[0] == 2
    assert run(initialized, "remove", ".")[0] == 2


def test_prune_solo_huerfanos_y_acotado(initialized, run):
    write_twin(initialized, "src/main.go.md", "a\n")
    write_twin(initialized, "src/features/login.go.md", "b [[src/futuro.go.md|futuro]]\n")
    write_twin(initialized, "README.md.md", "ver [[src/main.go.md|main]]\n")
    run(initialized, "update", "README.md")
    (initialized / "src/main.go").unlink()
    (initialized / "src/features/login.go").unlink()
    code, out = run(initialized, "prune", "src/features")
    assert code == 0, out
    g = load(initialized)
    assert "src/features/login.go.md" not in g.nodes
    assert "src/main.go.md" in g.nodes  # fuera del alcance
    run(initialized, "prune")
    g = load(initialized)
    assert "src/main.go.md" not in g.nodes
    assert "ver main" in read_twin(initialized, "README.md.md")
    assert "src/features/pagos/cobro.go.md" in g.nodes  # no huérfano
    assert_sano(initialized)


# ---- mv ------------------------------------------------------------------------------
def test_mv_tabla_de_reescritura(initialized, run):
    write_twin(initialized, "README.md.md", (
        "a [[src/main.go.md#Function|texto]]\n"
        "b [[src/main.go.md|sin seccion]]\n"
        "c [[src/main.go]]\n"
        "d [[src/main.go.md#Otra|x]] y [[src/main.go.md#Otra|y]]\n"
        "e [[main.go.md|corta]]\n"
    ))
    run(initialized, "update", "README.md")
    code, out = run(initialized, "mv", "src/main.go", "src/headless.go")
    assert code == 0, out
    text = read_twin(initialized, "README.md.md")
    assert "[[src/headless.go.md#Function|texto]]" in text
    assert "[[src/headless.go.md|sin seccion]]" in text
    assert "c [[src/headless.go]]" in text
    assert "[[src/headless.go.md#Otra|x]] y [[src/headless.go.md#Otra|y]]" in text
    assert "[[headless.go.md|corta]]" in text
    g = load(initialized)
    assert g.relations("README.md.md", "src/headless.go.md") == ["conoce"]
    assert twin_path(initialized, "src/headless.go.md").exists()
    assert not twin_path(initialized, "src/main.go.md").exists()
    assert_sano(initialized)


def test_mv_carpeta_con_descendientes(initialized, run):
    write_twin(initialized, "README.md.md", "[[src/features/features.md|features]] [[src/features/pagos/cobro.go.md#c|c]]\n")
    run(initialized, "update", "README.md")
    code, out = run(initialized, "mv", "src/features", "src/modulos")
    assert code == 0, out
    g = load(initialized)
    assert {"src/modulos/modulos.md", "src/modulos/login.go.md", "src/modulos/pagos/pagos.md", "src/modulos/pagos/cobro.go.md"} <= set(g.nodes)
    assert not any(n.startswith("src/features") for n in g.nodes)
    text = read_twin(initialized, "README.md.md")
    assert "[[src/modulos/modulos.md|features]]" in text and "[[src/modulos/pagos/cobro.go.md#c|c]]" in text
    assert twin_path(initialized, "src/modulos/modulos.md").exists()
    assert_sano(initialized)


def test_mv_rechaza_destino_existente_sin_cambios(initialized, run):
    before = (initialized / ".graph/index.json").read_text()
    code, out = run(initialized, "mv", "src/main.go", "src/features/login.go")
    assert code == 2
    assert (initialized / ".graph/index.json").read_text() == before
    assert twin_path(initialized, "src/main.go.md").exists()


def test_mv_rechaza_gemelo(initialized, run):
    assert run(initialized, "mv", ".graph/src/src.md", "x")[0] == 2


def test_mv_solo_mayusculas(initialized, run):
    code, out = run(initialized, "mv", "src/main.go", "src/Main.go")
    assert code == 0, out
    assert "src/Main.go.md" in load(initialized).nodes
    assert_sano(initialized)


# ---- fecha del header en update ----------------------------------------------------
def test_update_mueve_solo_la_fecha_del_header(initialized, run):
    from grafo_ia.templates import today

    write_twin(initialized, "src/main.go.md", (
        "Entrada.\n\n## Funciones\n### main\n"
        "**Elaboración:** 2025-01-01 | **Actualización:** 2025-02-02\n\n"
        "fecha_actualizacion: 1999-01-01 (texto en el cuerpo, no se toca)\n"
    ))
    code, out = run(initialized, "update", "src/main.go")
    assert code == 0, out
    text = read_twin(initialized, "src/main.go.md")
    header, body = text.split("\n---\n", 1)
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
    assert touch_updated("---\ntipo: codigo\n---\ncuerpo\n", "2026-01-01") == "---\ntipo: codigo\nfecha_actualizacion: 2026-01-01\n---\ncuerpo\n"
    assert touch_updated("---\r\nfecha_actualizacion: a\r\n---\r\nx\r\n", "b") == "---\r\nfecha_actualizacion: b\r\n---\r\nx\r\n"


def test_update_fallido_no_toca_la_fecha(initialized, run):
    write_twin(initialized, "src/main.go.md", "")  # vacío: faltante
    before = read_twin(initialized, "src/main.go.md")
    assert run(initialized, "update", "src/main.go")[0] == 2
    assert read_twin(initialized, "src/main.go.md") == before
