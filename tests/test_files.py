"""Permisos de los documentos escritos: un .graph compartido lo debe poder leer y editar todo el equipo."""

from __future__ import annotations

import os
import stat
import sys

import pytest

from grafo_ia.files import write_text_atomic
from grafo_ia.paths import doc_path

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")


def mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def umask():
    """Fija el umask durante la prueba y lo restaura al terminar."""
    previo = os.umask(0o022)

    def _set(valor: int) -> None:
        os.umask(valor)

    yield _set
    os.umask(previo)


@pytest.mark.parametrize("mascara, esperado", [(0o022, 0o644), (0o002, 0o664), (0o077, 0o600)])
def test_archivo_nuevo_respeta_el_umask(tmp_path, umask, mascara, esperado):
    umask(mascara)
    destino = tmp_path / "doc.md"
    write_text_atomic(destino, "hola\n")
    assert mode(destino) == esperado


def test_reemplazo_conserva_los_permisos_del_archivo(tmp_path, umask):
    destino = tmp_path / "doc.md"
    destino.write_text("viejo\n", encoding="utf-8")
    destino.chmod(0o664)
    write_text_atomic(destino, "nuevo\n")
    assert destino.read_text(encoding="utf-8") == "nuevo\n"
    assert mode(destino) == 0o664


def test_no_deja_temporales(tmp_path):
    write_text_atomic(tmp_path / "doc.md", "hola\n")
    assert [p.name for p in tmp_path.iterdir()] == ["doc.md"]


def test_init_crea_documentos_legibles_por_el_grupo(project, run, umask):
    umask(0o002)
    code, out = run(project, "init")
    assert code == 0, out
    assert mode(doc_path(project, "Estado")) == 0o664
