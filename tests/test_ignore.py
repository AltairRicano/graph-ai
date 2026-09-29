"""`graph ignore` y exclusiones por defecto (agentes/, reglas ancladas a la raíz)."""

from __future__ import annotations

from conftest import assert_sano, load, write, write_twin


def test_agentes_en_la_raiz_nunca_se_espeja(project, run):
    write(project, "agentes/2026-09-21_code-reviewer_a3f91c.md", "---\nagente: code-reviewer\n---\nhallazgos\n")
    write(project, "src/agentes/bot.go", "package agentes\n")
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0, out
    nodes = load(project).nodes
    assert not any(n.startswith("agentes/") for n in nodes)
    assert "src/agentes/bot.go.md" in nodes  # solo la de la raíz es operativa
    assert_sano(project)


def test_ignore_agrega_regla_y_saca_del_grafo(initialized, run):
    code, out = run(initialized, "ignore", "features")
    assert code == 0, out
    assert "regla agregada: features" in out
    nodes = load(initialized).nodes
    assert not any(n.startswith("src/features/") for n in nodes)
    assert "features" in (initialized / ".graph/exclude").read_text()
    assert "features" not in (initialized / ".graph/src/src.md").read_text()  # el índice padre se regenera
    assert_sano(initialized)
    # idempotente
    code, out = run(initialized, "ignore", "features")
    assert code == 0 and "ya estaba: features" in out
    # y una reconciliación no lo regresa
    run(initialized, "add")
    assert "src/features/login.go.md" not in load(initialized).nodes


def test_ignore_no_borra_contenido_sin_force(initialized, run):
    write_twin(initialized, "src/features/login.go.md", "Login.\n")
    before = (initialized / ".graph/exclude").read_text()
    code, out = run(initialized, "ignore", "login.go")
    assert code == 2 and "src/features/login.go.md" in out and "--force" in out
    assert (initialized / ".graph/exclude").read_text() == before
    assert "src/features/login.go.md" in load(initialized).nodes
    code, out = run(initialized, "ignore", "login.go", "--force")
    assert code == 0, out
    assert "src/features/login.go.md" not in load(initialized).nodes
    assert_sano(initialized)


def test_ignore_remove_regresa_lo_excluido(initialized, run):
    run(initialized, "ignore", "features")
    code, out = run(initialized, "ignore", "--remove", "features")
    assert code == 0, out
    assert "regla quitada: features" in out
    assert "src/features/pagos/cobro.go.md" in load(initialized).nodes
    assert "features" not in [ln.strip() for ln in (initialized / ".graph/exclude").read_text().splitlines()]
    assert_sano(initialized)


def test_ignore_anclado_a_la_raiz(initialized, run):
    write(initialized, "generado/a.py", "a\n")
    write(initialized, "src/generado/b.py", "b\n")
    run(initialized, "add")
    code, out = run(initialized, "ignore", "/generado")
    assert code == 0, out
    nodes = load(initialized).nodes
    assert "generado/a.py.md" not in nodes and "src/generado/b.py.md" in nodes
    assert_sano(initialized)


def test_ignore_lista(initialized, run):
    run(initialized, "ignore", "features")
    code, out = run(initialized, "ignore")
    assert code == 0 and "features" in out and "agentes/" in out
    assert run(initialized, "ignore", "--remove")[0] == 2
