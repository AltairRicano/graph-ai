"""rename, relate, config, regeneración de aristas, consultas y doctor."""

from __future__ import annotations

import json

import pytest

from grafo_ia import graph_io
from grafo_ia.paths import twin_path

from conftest import assert_sano, load, read_twin, write, write_index

SRC = "src/src.md"
FEATURES = "src/features/features.md"
MASTER = "Index.md"

SRC_REPORT = """## main
**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-01

Arranca todo. Usa [[#helper|helper]] y [[#helper]].

## helper
Ayuda.

## framework_web & FastAPI
Algo.
"""


@pytest.fixture
def linked(initialized, run):
    root = initialized
    write_index(root, "src", SRC_REPORT)
    write_index(root, "", "Ver [[src#helper|el helper]] y [[src#helper]].\n")
    write_index(root, "src/features", "## login\nLlama a [[src#framework_web|FastAPI]] y [[src#main|main]]; vive en [[src/features/login.go|login.go]].\n")
    for rel in ("src", ".", "src/features"):
        code, out = run(root, "update", rel)
        assert code == 0, out
    return root


# ---- rename ------------------------------------------------------------------
def test_rename_alias_y_sin_alias(linked, run):
    code, out = run(linked, "rename", "src#helper", "ayudante")
    assert code == 0, out
    master = read_twin(linked, MASTER)
    assert "[[src#ayudante|el helper]]" in master  # alias conservado
    assert "[[src#ayudante]]" in master  # sin alias: el texto visible sigue al nombre nuevo
    src = read_twin(linked, SRC)
    assert "## ayudante\n" in src and "## helper\n" not in src
    assert "[[#ayudante|helper]]" in src and "[[#ayudante]]" in src  # enlaces internos
    assert MASTER in out and SRC in out


def test_rename_snake_legible_completo(linked, run):
    code, out = run(linked, "rename", "src#framework_web & FastAPI", "framework_api & Starlette")
    assert code == 0, out
    assert "## framework_api & Starlette" in read_twin(linked, SRC)
    # el enlace usaba solo el identificador: se cambia el identificador
    assert "[[src#framework_api|FastAPI]]" in read_twin(linked, FEATURES)


def test_rename_rechazos(linked, run):
    assert run(linked, "rename", "src#helper", "main")[0] == 2  # ya existe
    write_index(linked, "src/features/pagos", "## a\n## a\n")
    assert run(linked, "rename", "src/features/pagos#a", "b")[0] == 2  # ambiguo
    assert run(linked, "rename", "src#noexiste", "b")[0] == 2


def test_rename_links_only(linked, run):
    p = twin_path(linked, SRC)
    p.write_text(p.read_text().replace("## helper\n", "## ayudante\n"), encoding="utf-8")
    code, out = run(linked, "rename", "src#helper", "ayudante", "--links-only")
    assert code == 0, out
    assert "[[src#ayudante|el helper]]" in read_twin(linked, MASTER)
    # sin --links-only se rechaza porque el viejo ya no existe
    assert run(linked, "rename", "src#helper", "otro")[0] == 2


def test_rename_no_toca_aristas_ni_confirmacion(linked, run):
    before = (linked / ".graph/index.json").read_text()
    run(linked, "rename", "src#helper", "ayudante")
    assert (linked / ".graph/index.json").read_text() == before
    assert_sano(linked)


def test_rename_fallo_antes_de_escribir_no_deja_nada(linked, run, monkeypatch):
    from grafo_ia.commands import rename

    master_before = read_twin(linked, MASTER)
    monkeypatch.setattr(rename, "rewrite_links", lambda *a: (_ for _ in ()).throw(RuntimeError("fallo")))
    with pytest.raises(RuntimeError):
        run(linked, "rename", "src#helper", "ayudante")
    assert read_twin(linked, MASTER) == master_before
    assert "## helper" in read_twin(linked, SRC)


# ---- relate ------------------------------------------------------------------
def test_relate(linked, run):
    code, out = run(linked, "relate", ".", "src")
    assert code == 0 and "conoce" in out
    assert run(linked, "relate", ".", "src", "--add", "utiliza")[0] == 0
    assert run(linked, "relate", ".", "src", "--remove", "conoce")[0] == 0
    assert load(linked).relations(MASTER, SRC) == ["utiliza"]
    assert run(linked, "relate", ".", "src", "--remove", "utiliza")[0] == 2  # quedaría vacía
    assert run(linked, "relate", ".", "src", "--add", "inventada")[0] == 2
    assert run(linked, "relate", "src", ".")[0] == 2  # arista inexistente
    # un índice también se relaciona con un archivo de código
    assert run(linked, "relate", "src/features", "src/features/login.go", "--add", "implementa")[0] == 0
    # sobreviven a una regeneración
    run(linked, "update", ".")
    assert load(linked).relations(MASTER, SRC) == ["utiliza"]
    assert_sano(linked)


# ---- config ------------------------------------------------------------------
def test_config_strict(initialized, run):
    cfg = initialized / ".graph/config"
    assert run(initialized, "config", "strict")[1].strip() == "strict: off"
    run(initialized, "config", "strict", "on")
    run(initialized, "config", "strict", "on")
    assert cfg.read_text().count("strict") == 1
    assert "strict: on" in run(initialized, "config", "strict")[1]
    run(initialized, "config", "strict", "off")
    run(initialized, "config", "strict", "off")
    assert "strict" not in cfg.read_text().split()
    assert run(initialized, "config", "strict", "tal vez")[0] == 2
    cfg.unlink()
    assert "off" in run(initialized, "config", "strict")[1]
    run(initialized, "config", "strict", "on")
    assert "strict" in cfg.read_text()


# ---- regeneración de aristas ---------------------------------------------------
def test_regeneracion(linked, run):
    g = load(linked)
    assert g.relations(MASTER, SRC) == ["conoce"]
    assert g.relations(FEATURES, "src/features/login.go") == ["conoce"]  # el destino es el archivo de código
    run(linked, "relate", ".", "src", "--add", "utiliza")
    confirmed = g.nodes[MASTER]["archivos_confirmados"]
    write_index(linked, "", "Ver [[src#helper|el helper]] y [[src#helper]].\nY [[src/features|features]]\n")
    from grafo_ia.edges import TwinCache, regenerate

    with graph_io.transaction(linked) as g2:
        added, removed = regenerate(g2, TwinCache(linked), MASTER)
    assert added == {FEATURES} and not removed
    g3 = load(linked)
    assert g3.relations(MASTER, FEATURES) == ["conoce"]
    assert g3.relations(MASTER, SRC) == ["conoce", "utiliza"]
    assert g3.nodes[MASTER]["archivos_confirmados"] == confirmed  # regenerar no toca la confirmación
    write_index(linked, "", "nada\n")
    run(linked, "update", ".")
    assert not load(linked).adj_out[MASTER]


# ---- consultas ---------------------------------------------------------------
def test_get_seccion_y_expand(linked, run):
    code, out = run(linked, "get", "src#helper")
    assert code == 0 and out.startswith("==> src/src.md#helper <==") and "Ayuda." in out
    assert "Arranca todo" not in out
    code, out = run(linked, "get", ".", "--expand")
    assert "==> src/src.md#helper (saliente: conoce) <==" in out and "Ayuda." in out


def test_get_de_un_archivo_de_codigo_manda_a_leerlo(linked, run):
    code, out = run(linked, "get", "src/main.go")
    assert code == 0 and "léelo directo" in out and "graph get src" in out and "graph neighbors src/main.go" in out


def test_neighbors(linked, run):
    code, out = run(linked, "neighbors", "src")
    assert "<- Index.md" in out and "<- src/features/features.md" in out
    code, out = run(linked, "neighbors", "src#helper", "--in")
    assert "Index.md" in out and "features.md" not in out  # solo lo que apunta a esa sección
    code, out = run(linked, "neighbors", "src/features#login", "--out")
    assert "-> src/src.md" in out and "-> src/features/login.go" in out


def test_neighbors_de_un_archivo_muestra_sus_relaciones(linked, run):
    write(linked, "web/api.ts", "export const cobrar = 1\n")
    code, out = run(linked, "multiedit", "-f", str(write(linked, "lote.txt", """=== src/features#Relaciones ===
- [[src/features/login.go|login.go]] → [[src/main.go#main|main]]: arranca la sesión.
- [[web/api.ts|api.ts]] -> [[src/features/login.go|login.go]]: el frontend llama `POST /login`.
- [[src/features/login.go|login.go]] → [[src/features/pagos|pagos]]: cobra al entrar.
""")))
    assert code == 0, out
    code, out = run(linked, "neighbors", "src/features/login.go")
    assert code == 0, out
    assert "relaciones (3)" in out
    assert "src/features/login.go -> src/main.go: arranca la sesión. (en src/features#Relaciones)" in out
    assert "web/api.ts -> src/features/login.go: el frontend llama `POST /login`." in out
    assert "src/features/login.go -> src/features/pagos: cobra al entrar." in out
    assert "mencionado en (1)" in out and "<- src/features/features.md" in out
    out_in = run(linked, "neighbors", "src/features/login.go", "--in")[1]
    assert "relaciones (1)" in out_in and "web/api.ts" in out_in
    # la relación también se ve desde el otro extremo, aunque viva en otro índice
    assert "web/api.ts -> src/features/login.go" in run(linked, "neighbors", "web/api.ts")[1]
    assert "src/features/login.go -> src/features/pagos" in run(linked, "neighbors", "src/features/pagos")[1]
    assert_sano(linked)


def test_subgraph_profundidad_y_ciclos(linked, run):
    write_index(linked, "src/features/pagos", "[[Index.md|r]]\n")
    write_index(linked, "src", SRC_REPORT + "\n[[src/features/pagos|c]]\n")
    run(linked, "update", "src/features/pagos")
    run(linked, "update", "src")
    out0 = run(linked, "subgraph", ".", "--depth", "0")[1]
    assert "nodos (1)" in out0
    out1 = run(linked, "subgraph", ".", "--depth", "1")[1]
    assert "src/src.md" in out1
    code, outn = run(linked, "subgraph", ".", "--depth", "10", "--json")
    data = json.loads(outn)
    assert {n["id"] for n in data["nodes"]} >= {MASTER, SRC, "src/features/pagos/pagos.md", "src/features/login.go"}
    assert run(linked, "subgraph", "src/features/login.go")[0] == 0


def test_get_depth_ida_y_vuelta_por_secciones_distintas(initialized, run):
    root = initialized
    write_index(root, "src", "## uno\nver [[src/features#dos|dos]]\n\n## cuatro\nvuelve a [[src/features#dos|dos]]\n")
    write_index(root, "src/features", "## dos\nsigue en [[src#cuatro|cuatro]]\n\n## tres\nnada\n")
    for rel in ("src", "src/features"):
        assert run(root, "update", rel)[0] == 0
    code, out = run(root, "get", "src#uno", "--depth", "5")
    assert code == 0, out
    assert "==> src/features/features.md#dos (saliente: conoce, salto 1) <==" in out
    assert "==> src/src.md#cuatro (saliente: conoce, salto 2) <==" in out  # vuelve, pero a otra sección
    assert out.count("==> src/features/features.md#dos") == 1  # la sección ya leída corta esa rama
    assert "saltos omitidos" in out
    # con un salto es lo mismo que --expand
    assert run(root, "get", "src#uno", "--depth", "1")[1] == run(root, "get", "src#uno", "--expand")[1]


def test_get_depth_corta_indice_completo_ya_visitado(initialized, run):
    root = initialized
    write_index(root, "src", "## uno\nver [[src/features|features]]\n")
    write_index(root, "src/features", "## dos\nvuelve a [[src|src]]\n")
    for rel in ("src", "src/features"):
        assert run(root, "update", rel)[0] == 0
    code, out = run(root, "get", "src", "--depth", "4")
    assert code == 0, out
    assert out.count("==> src/src.md") == 1 and out.count("==> src/features/features.md") == 1


def test_search(linked, run):
    out = run(linked, "search", "ayuda")[1]
    assert "src/src.md:" in out and "[#helper]" in out
    out = run(linked, "search", "--filter", "tipo=plan")[1]
    assert out.strip() == "Estado_Proyecto/Plan.md"
    assert run(linked, "search")[0] == 2


def test_status_cuadra_con_incomplete(linked, run):
    write_index(linked, "", "futuro [[src/nada.go|nada]]\n")
    write(linked, "src/features/nuevo.go", "package features\n")
    import shutil

    write_index(linked, "src/features/pagos", "algo\n")
    shutil.rmtree(linked / "src/features/pagos")
    status = dict(l.split(": ", 1) for l in run(linked, "status")[1].splitlines() if ": " in l and not l.startswith("["))
    inc = run(linked, "incomplete")[1]
    counts = {line.rsplit(" (", 1)[0]: int(line.rsplit("(", 1)[1].rstrip(")")) for line in inc.splitlines() if not line.startswith(" ")}
    assert int(status["faltante"]) == counts["faltantes"]
    assert int(status["desactualizado"]) == counts["desactualizados"] == 2  # la raíz (enlace roto) y features (entró un archivo)
    assert int(status["pendiente por crear"]) == counts["pendientes por crear"] >= 1
    assert int(status["huérfano"]) == counts["huérfanos"] == 1
    assert "src/features: entraron: nuevo.go" in inc and ".: 1 enlace que no resuelve" in inc


def test_incomplete_reporta_sin_alias(linked, run):
    assert "enlaces sin texto a mostrar" in run(linked, "incomplete")[1]


# ---- doctor ------------------------------------------------------------------
def _seed(root, mutate):
    p = root / ".graph/index.json"
    data = json.loads(p.read_text())
    mutate(data)
    p.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["nodes"].append(dict(d["nodes"][0])), "id duplicado"),
    (lambda d: d["links"].append({"source": "Index.md", "target": "no/existe.md", "relaciones": ["conoce"]}), "colgante"),
    (lambda d: d["nodes"].append({"id": "x/huerfano/huerfano.md", "nombre": "huerfano", "tipo": "indice"}), "no tiene índice padre"),
    (lambda d: d["nodes"].append({"id": "src/extra.go", "nombre": "extra.go", "tipo": "codigo", "last_synced_hash": None}), "no referencia a su hijo"),
    (lambda d: d["links"].append({"source": "Index.md", "target": "src/src.md", "relaciones": []}), "relaciones vacías"),
    (lambda d: d["links"].append({"source": "Index.md", "target": "src/src.md", "relaciones": ["amistad"]}), "fuera de la taxonomía"),
])
def test_doctor_detecta_danos(initialized, run, mutate, needle):
    _seed(initialized, mutate)
    code, out = run(initialized, "doctor")
    assert code == 1 and needle in out


def test_doctor_sano(initialized, run):
    assert run(initialized, "doctor") == (0, "grafo sano\n")
