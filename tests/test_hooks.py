"""Hooks de git en repos temporales, con `.graph` anidado."""

from __future__ import annotations

import shutil

import pytest

from conftest import git, write, write_twin

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="sin git")


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t"}.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def repo(project, run):
    git(project, "init", "-q", "-b", "main")
    git(project, "add", "-A")
    git(project, "commit", "-qm", "inicial")
    code, out = run(project, "init", "--yes")
    assert code == 0, out
    git(project, "add", "-A")
    git(project, "commit", "-qm", "gitignore")
    return project


def nested(root, *args):
    return git(root / ".graph", *args, check=False).stdout.strip()


def head(root):
    return git(root, "rev-parse", "HEAD").stdout.strip()


def test_init_crea_repo_anidado_sin_remoto(repo):
    assert (repo / ".graph/.git").is_dir()
    assert nested(repo, "remote") == ""
    assert ".graph/" in (repo / ".gitignore").read_text()
    assert git(repo, "status", "--porcelain").stdout.strip() == ""  # .graph ignorado


def test_pre_commit_avisa_y_deja_pasar(repo):
    write(repo, "src/main.go", "package main\n// cambio\n")
    git(repo, "add", "src/main.go")
    r = git(repo, "commit", "-m", "cambio", check=False)
    assert r.returncode == 0
    assert "[WARNING]" in r.stdout + r.stderr and "src/main.go" in r.stdout + r.stderr


def test_pre_commit_estricto_bloquea(repo, run):
    run(repo, "config", "strict", "on")
    write(repo, "src/main.go", "package main\n// cambio\n")
    git(repo, "add", "src/main.go")
    r = git(repo, "commit", "-m", "cambio", check=False)
    assert r.returncode != 0
    assert git(repo, "commit", "-qm", "sin verificar", "--no-verify", check=False).returncode == 0


def test_pre_commit_usa_lo_staged(repo, run):
    write_twin(repo, "src/main.go.md", "principal\n")
    run(repo, "update", "src/main.go")
    run(repo, "config", "strict", "on")
    write(repo, "src/main.go", "package main\n// en disco, sin stagear\n")
    write(repo, "Makefile", "# otro\n")
    write_twin(repo, "Makefile.md", "readme\n")
    run(repo, "update", "Makefile")
    git(repo, "add", "Makefile")
    # main.go cambió en disco pero no está staged: no cuenta
    assert git(repo, "commit", "-qm", "readme", check=False).returncode == 0


def test_post_commit_espejo_con_trailer(repo):
    before = int(nested(repo, "rev-list", "--count", "HEAD"))
    write(repo, "src/main.go", "package main\n// x\n")
    git(repo, "commit", "-qam", "mensaje de prueba")
    assert int(nested(repo, "rev-list", "--count", "HEAD")) == before + 1  # vacío si no hubo cambios
    msg = nested(repo, "log", "-1", "--format=%B")
    assert msg.startswith("mensaje de prueba")
    assert f"Code-commit: {head(repo)}" in msg


def test_post_checkout_rama_y_commit_viejo(repo):
    old = head(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    assert nested(repo, "rev-parse", "--abbrev-ref", "HEAD") == "feature"
    write(repo, "src/nuevo.go", "package x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "nuevo")
    git(repo, "checkout", "-q", "main")
    assert nested(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    git(repo, "checkout", "-q", "--detach", old)
    mirror = nested(repo, "rev-parse", "HEAD")
    assert f"Code-commit: {old}" in nested(repo, "log", "-1", "--format=%B", mirror)
    assert nested(repo, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"  # desacoplado


def test_post_checkout_archivo_no_hace_nada(repo):
    before = nested(repo, "rev-parse", "HEAD")
    write(repo, "src/main.go", "basura\n")
    git(repo, "checkout", "--", "src/main.go")
    assert nested(repo, "rev-parse", "HEAD") == before


def test_post_checkout_graph_sucio_no_se_mueve(repo):
    before = nested(repo, "rev-parse", "--abbrev-ref", "HEAD")
    write_twin(repo, "src/main.go.md", "sin commitear\n")
    r = git(repo, "checkout", "-b", "otra")
    assert "cambios sin commitear" in r.stdout + r.stderr
    assert nested(repo, "rev-parse", "--abbrev-ref", "HEAD") == before


def test_repo_anidado_nace_en_la_rama_del_codigo(repo):
    assert nested(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_post_checkout_sin_espejo_avisa(repo):
    git(repo, "commit", "-q", "--allow-empty", "-m", "sin espejo", "--no-verify")
    # simulamos un commit sin espejo quitando el último commit de .graph
    nested(repo, "reset", "-q", "--hard", "HEAD~1")
    target = head(repo)
    git(repo, "checkout", "-q", "main~1")
    r = git(repo, "checkout", "--detach", target, check=False)
    assert "no tiene un commit espejo" in r.stdout + r.stderr


def test_post_merge_avisa_faltantes(repo):
    git(repo, "checkout", "-q", "-b", "feature")
    write(repo, "src/merge.go", "package x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "desde feature", "--no-verify")
    git(repo, "checkout", "-q", "main")
    r = git(repo, "merge", "--ff-only", "feature")
    assert "faltante: src/merge.go" in r.stdout + r.stderr


def test_post_rewrite_amend_y_rebase(repo):
    write(repo, "src/main.go", "package main\n// a\n")
    git(repo, "commit", "-qam", "a")
    git(repo, "commit", "-q", "--amend", "-m", "a enmendado")
    new = head(repo)
    assert nested(repo, "log", "--all", "--format=%H", f"--grep=^Code-commit: {new}$")
    # rebase: main avanza, feature se rebasa encima
    git(repo, "checkout", "-q", "-b", "feature", "HEAD~1")
    write(repo, "src/f.go", "package f\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "f")
    git(repo, "rebase", "-q", "main")
    rebased = head(repo)
    assert nested(repo, "log", "--all", "--format=%H", f"--grep=^Code-commit: {rebased}$")


def test_chequeo_perezoso_tras_reset(repo, run):
    write(repo, "src/main.go", "package main\n// b\n")
    git(repo, "commit", "-qam", "b")
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    code, out = run(repo, "status")
    assert "el grafo está en" in out


def test_hooks_existentes_se_encadenan(project, run, tmp_path):
    git(project, "init", "-q", "-b", "main")
    hook = project / ".git/hooks/pre-commit"
    marker = tmp_path / "corrio"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    run(project, "init", "--yes")
    assert (project / ".git/hooks/pre-commit.pre-grafo").exists()
    git(project, "add", "-A")
    git(project, "commit", "-qm", "x")
    assert marker.exists()
