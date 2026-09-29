"""rename, relate, config, regeneración de aristas, consultas y doctor."""

from __future__ import annotations

import json

import pytest

from grafo_ia import graph_io
from grafo_ia.paths import twin_path

from conftest import assert_sano, load, read_twin, write_twin

MAIN_TWIN = """Punto de entrada.

## Funciones
### main
**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-01

Arranca todo. Usa [[#helper|helper]] y [[#helper]].

### helper
Ayuda.

### framework_web & FastAPI
Algo.
"""


@pytest.fixture
def linked(initialized, run):
    root = initialized
    write_twin(root, "src/main.go.md", MAIN_TWIN)
    write_twin(root, "README.md.md", "Ver [[src/main.go.md#helper|el helper]] y [[src/main.go.md#helper]].\n")
    write_twin(root, "src/features/login.go.md", "## login\nLlama a [[src/main.go.md#framework_web|FastAPI]] y [[src/main.go.md#main|main]].\n")
    for rel in ("src/main.go", "README.md", "src/features/login.go"):
        code, out = run(root, "update", rel)
        assert code == 0, out
    return root


# ---- rename ------------------------------------------------------------------
def test_rename_alias_y_sin_alias(linked, run):
    code, out = run(linked, "rename", "src/main.go#helper", "ayudante")
    assert code == 0, out
    readme = read_twin(linked, "README.md.md")
    assert "[[src/main.go.md#ayudante|el helper]]" in readme  # alias conservado
    assert "[[src/main.go.md#ayudante]]" in readme  # sin alias: el texto visible sigue al nombre nuevo
    main = read_twin(linked, "src/main.go.md")
    assert "### ayudante\n" in main and "### helper\n" not in main
    assert "[[#ayudante|helper]]" in main and "[[#ayudante]]" in main  # enlaces internos
    assert "README.md.md" in out and "src/main.go.md" in out


def test_rename_snake_legible_completo(linked, run):
    code, out = run(linked, "rename", "src/main.go#framework_web & FastAPI", "framework_api & Starlette")
    assert code == 0, out
    assert "### framework_api & Starlette" in read_twin(linked, "src/main.go.md")
    # el enlace usaba solo el identificador: se cambia el identificador
    assert "[[src/main.go.md#framework_api|FastAPI]]" in read_twin(linked, "src/features/login.go.md")


def test_rename_rechazos(linked, run):
    assert run(linked, "rename", "src/main.go#helper", "main")[0] == 2  # ya existe
    write_twin(linked, "src/features/pagos/cobro.go.md", "## a\n## a\n")
    assert run(linked, "rename", "src/features/pagos/cobro.go#a", "b")[0] == 2  # ambiguo
    assert run(linked, "rename", "src/main.go#noexiste", "b")[0] == 2


def test_rename_links_only(linked, run):
    p = twin_path(linked, "src/main.go.md")
    p.write_text(p.read_text().replace("### helper\n", "### ayudante\n"), encoding="utf-8")
    code, out = run(linked, "rename", "src/main.go#helper", "ayudante", "--links-only")
    assert code == 0, out
    assert "[[src/main.go.md#ayudante|el helper]]" in read_twin(linked, "README.md.md")
    # sin --links-only se rechaza porque el viejo ya no existe
    assert run(linked, "rename", "src/main.go#helper", "otro")[0] == 2


def test_rename_no_toca_aristas_ni_hash(linked, run):
    before = (linked / ".graph/index.json").read_text()
    run(linked, "rename", "src/main.go#helper", "ayudante")
    assert (linked / ".graph/index.json").read_text() == before
    assert_sano(linked)


def test_rename_fallo_antes_de_escribir_no_deja_nada(linked, run, monkeypatch):
    from grafo_ia.commands import rename

    readme_before = read_twin(linked, "README.md.md")
    monkeypatch.setattr(rename, "rewrite_links", lambda *a: (_ for _ in ()).throw(RuntimeError("fallo")))
    with pytest.raises(RuntimeError):
        run(linked, "rename", "src/main.go#helper", "ayudante")
    assert read_twin(linked, "README.md.md") == readme_before
    assert "### helper" in read_twin(linked, "src/main.go.md")


# ---- relate ------------------------------------------------------------------
def test_relate(linked, run):
    code, out = run(linked, "relate", "README.md", "src/main.go")
    assert code == 0 and "conoce" in out
    assert run(linked, "relate", "README.md", "src/main.go", "--add", "utiliza")[0] == 0
    assert run(linked, "relate", "README.md", "src/main.go", "--remove", "conoce")[0] == 0
    assert load(linked).relations("README.md.md", "src/main.go.md") == ["utiliza"]
    assert run(linked, "relate", "README.md", "src/main.go", "--remove", "utiliza")[0] == 2  # quedaría vacía
    assert run(linked, "relate", "README.md", "src/main.go", "--add", "inventada")[0] == 2
    assert run(linked, "relate", "src/main.go", "README.md")[0] == 2  # arista inexistente
    # sobreviven a una regeneración
    run(linked, "update", "README.md")
    assert load(linked).relations("README.md.md", "src/main.go.md") == ["utiliza"]
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
    assert g.relations("README.md.md", "src/main.go.md") == ["conoce"]
    run(linked, "relate", "README.md", "src/main.go", "--add", "utiliza")
    h = g.nodes["README.md.md"]["last_synced_hash"]
    p = twin_path(linked, "README.md.md")
    p.write_text(p.read_text() + "Y [[src/features/login.go.md|login]]\n", encoding="utf-8")
    from grafo_ia.edges import TwinCache, regenerate

    with graph_io.transaction(linked) as g2:
        added, removed = regenerate(g2, TwinCache(linked), "README.md.md")
    assert added == {"src/features/login.go.md"} and not removed
    g3 = load(linked)
    assert g3.relations("README.md.md", "src/features/login.go.md") == ["conoce"]
    assert g3.relations("README.md.md", "src/main.go.md") == ["conoce", "utiliza"]
    assert g3.nodes["README.md.md"]["last_synced_hash"] == h  # regenerar no toca el hash
    p.write_text("---\ntipo: codigo\n---\nnada\n", encoding="utf-8")
    run(linked, "update", "README.md")
    assert not load(linked).adj_out["README.md.md"]


# ---- consultas ---------------------------------------------------------------
def test_get_seccion_y_expand(linked, run):
    code, out = run(linked, "get", "src/main.go#helper")
    assert code == 0 and out.startswith("==> src/main.go.md#helper <==") and "Ayuda." in out
    assert "Arranca todo" not in out
    code, out = run(linked, "get", "README.md", "--expand")
    assert "==> src/main.go.md#helper (saliente: conoce) <==" in out and "Ayuda." in out


def test_neighbors(linked, run):
    code, out = run(linked, "neighbors", "src/main.go")
    assert "<- README.md.md" in out and "<- src/features/login.go.md" in out
    code, out = run(linked, "neighbors", "src/main.go#helper", "--in")
    assert "README.md.md" in out and "login.go.md" not in out  # solo lo que apunta a esa sección
    code, out = run(linked, "neighbors", "src/features/login.go#login", "--out")
    assert "-> src/main.go.md" in out


def test_subgraph_profundidad_y_ciclos(linked, run):
    write_twin(linked, "src/features/pagos/cobro.go.md", "[[README.md.md|r]]\n")
    write_twin(linked, "src/main.go.md", MAIN_TWIN + "\n[[src/features/pagos/cobro.go.md|c]]\n")
    run(linked, "update", "src/features/pagos/cobro.go")
    run(linked, "update", "src/main.go")
    out0 = run(linked, "subgraph", "README.md", "--depth", "0")[1]
    assert "nodos (1)" in out0
    out1 = run(linked, "subgraph", "README.md", "--depth", "1")[1]
    assert "src/main.go.md" in out1
    code, outn = run(linked, "subgraph", "README.md", "--depth", "10", "--json")
    data = json.loads(outn)
    assert {n["id"] for n in data["nodes"]} >= {"README.md.md", "src/main.go.md", "src/features/pagos/cobro.go.md"}


def test_get_depth_ida_y_vuelta_por_secciones_distintas(initialized, run):
    root = initialized
    write_twin(root, "src/main.go.md", "## uno\nver [[src/features/login.go.md#dos|dos]]\n\n## cuatro\nvuelve a [[src/features/login.go.md#dos|dos]]\n")
    write_twin(root, "src/features/login.go.md", "## dos\nsigue en [[src/main.go.md#cuatro|cuatro]]\n\n## tres\nnada\n")
    for rel in ("src/main.go", "src/features/login.go"):
        assert run(root, "update", rel)[0] == 0
    code, out = run(root, "get", "src/main.go#uno", "--depth", "5")
    assert code == 0, out
    assert "==> src/features/login.go.md#dos (saliente: conoce, salto 1) <==" in out
    assert "==> src/main.go.md#cuatro (saliente: conoce, salto 2) <==" in out  # vuelve, pero a otra sección
    assert out.count("==> src/features/login.go.md#dos") == 1  # la sección ya leída corta esa rama
    assert "saltos omitidos" in out
    # con un salto es lo mismo que --expand
    assert run(root, "get", "src/main.go#uno", "--depth", "1")[1] == run(root, "get", "src/main.go#uno", "--expand")[1]


def test_get_depth_corta_archivo_completo_ya_visitado(initialized, run):
    root = initialized
    write_twin(root, "src/main.go.md", "## uno\nver [[src/features/login.go.md|login]]\n")
    write_twin(root, "src/features/login.go.md", "## dos\nvuelve a [[src/main.go.md|main]]\n")
    for rel in ("src/main.go", "src/features/login.go"):
        assert run(root, "update", rel)[0] == 0
    code, out = run(root, "get", "src/main.go", "--depth", "4")
    assert code == 0, out
    assert out.count("==> src/main.go.md") == 1 and out.count("==> src/features/login.go.md") == 1


def test_neighbors_y_subgraph_rechazan_carpetas(linked, run):
    for cmd in ("neighbors", "subgraph"):
        code, out = run(linked, cmd, "src/features")
        assert code == 2 and "este elemento es una carpeta" in out and "graph get src/features" in out
    assert run(linked, "get", "src/features")[0] == 0


def test_search(linked, run):
    out = run(linked, "search", "ayuda")[1]
    assert "src/main.go.md:" in out and "[#helper]" in out
    out = run(linked, "search", "--filter", "tipo=plan")[1]
    assert out.strip() == "Estado_Proyecto/Plan.md"
    assert run(linked, "search")[0] == 2


def test_status_cuadra_con_incomplete(linked, run):
    write_twin(linked, "README.md.md", "futuro [[src/nada.go.md|nada]]\n")
    (linked / "src/features/login.go").unlink()
    status = dict(l.split(": ", 1) for l in run(linked, "status")[1].splitlines() if ": " in l and not l.startswith("["))
    inc = run(linked, "incomplete")[1]
    counts = {line.rsplit(" (", 1)[0]: int(line.rsplit("(", 1)[1].rstrip(")")) for line in inc.splitlines() if not line.startswith(" ")}
    assert int(status["faltante"]) == counts["faltantes"]
    assert int(status["desactualizado"]) == counts["desactualizados"]
    assert int(status["pendiente por crear"]) == counts["pendientes por crear"] >= 1
    assert int(status["huérfano"]) == counts["huérfanos"] == 1


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
    (lambda d: d["nodes"].append({"id": "src/extra.go.md", "nombre": "extra.go", "tipo": "codigo", "last_synced_hash": None}), "no referencia a su hijo"),
    (lambda d: d["links"].append({"source": "Index.md", "target": "src/src.md", "relaciones": []}), "relaciones vacías"),
    (lambda d: d["links"].append({"source": "Index.md", "target": "src/src.md", "relaciones": ["amistad"]}), "fuera de la taxonomía"),
])
def test_doctor_detecta_danos(initialized, run, mutate, needle):
    _seed(initialized, mutate)
    code, out = run(initialized, "doctor")
    assert code == 1 and needle in out


def test_doctor_sano(initialized, run):
    assert run(initialized, "doctor") == (0, "grafo sano\n")
