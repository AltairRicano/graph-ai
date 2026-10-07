"""Apoyo de pruebas: proyecto falso y CLI en proceso."""

from __future__ import annotations

from pathlib import Path

import pytest

from grafo_ia.cli import main
from grafo_ia.paths import doc_path


def write(root: Path, rel: str, content: str = "x\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def read_doc(root: Path, name: str) -> str:
    return doc_path(root, name).read_text(encoding="utf-8")


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
    """Proyecto falso con algo de código."""
    root = tmp_path / "proyecto"
    write(root, "src/main.go", "package main\n\nfunc main() {}\n")
    write(root, "src/pagos/cobro.go", "package pagos\n")
    return root


@pytest.fixture
def initialized(project: Path, run) -> Path:
    code, out = run(project, "init")
    assert code == 0, out
    return project
