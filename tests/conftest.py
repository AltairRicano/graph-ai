"""Apoyo de pruebas: proyecto falso, CLI en proceso y `assert_sano()`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from grafo_ia import graph_io
from grafo_ia.cli import main
from grafo_ia.commands.doctor import diagnose
from grafo_ia.paths import twin_path

FM = "---\ntipo: codigo\nfecha_elaboracion: 2026-01-01\nfecha_actualizacion: 2026-01-01\n---\n"


def write(root: Path, rel: str, content: str = "x\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def write_twin(root: Path, node_id: str, body: str, fm: str = FM) -> Path:
    p = twin_path(root, node_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm + body, encoding="utf-8")
    return p


def read_twin(root: Path, node_id: str) -> str:
    return twin_path(root, node_id).read_text(encoding="utf-8")


def assert_sano(root: Path) -> None:
    problems = diagnose(root)
    assert problems == [], "\n".join(problems)


def load(root: Path) -> graph_io.Graph:
    return graph_io.load(root)


@pytest.fixture
def run(capsys):
    """Corre `graph ...` en proceso. -> (código, salida)."""

    def _run(root: Path, *args: str) -> tuple[int, str]:
        try:
            code = main(["-C", str(root), *args])
        except SystemExit as e:  # argparse
            code = e.code if isinstance(e.code, int) else 2
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    return _run


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Proyecto falso: código, subcarpetas anidadas y una carpeta excluida."""
    root = tmp_path / "proyecto"
    write(root, "README.md", "# Proyecto\n")
    write(root, "src/main.go", "package main\n\nfunc main() {}\n")
    write(root, "src/features/login.go", "package features\n")
    write(root, "src/features/pagos/cobro.go", "package pagos\n")
    write(root, "node_modules/lib/index.js", "module.exports = 1\n")
    write(root, ".env", "SECRET=1\n")
    return root


@pytest.fixture
def initialized(project: Path, run) -> Path:
    code, out = run(project, "init", "--yes", "--no-git")
    assert code == 0, out
    return project


def git(cwd: Path, *args: str, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@t",
    })
    return subprocess.run(["git", *args], cwd=str(cwd), check=check, text=True, capture_output=True, env=env, input=input)
