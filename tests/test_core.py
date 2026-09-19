"""Núcleo compartido: hashing, parser, exclusión."""

from __future__ import annotations

import os
import sys

import pytest

from grafo_ia import parser
from grafo_ia.errors import AmbiguousError, NotFoundError
from grafo_ia.exclusion import EXCLUIR, GRAFO, INCLUIR, Exclusion, walk
from grafo_ia.hashing import hash_bytes, hash_file

from conftest import write


# ---- hashing -------------------------------------------------------------------
def test_hash_crlf_igual_a_lf(tmp_path):
    a = write(tmp_path, "a", "")
    b = write(tmp_path, "b", "")
    a.write_bytes(b"uno\ndos\n")
    b.write_bytes(b"uno\r\ndos\r\n")
    assert hash_file(a) == hash_file(b) == hash_bytes(b"uno\r\ndos\r\n")


def test_hash_un_byte_distinto(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_bytes(b"hola")
    b.write_bytes(b"holb")
    assert hash_file(a) != hash_file(b)


def test_hash_crlf_partido_entre_bloques(tmp_path):
    p = tmp_path / "x"
    data = b"a" * 9 + b"\r\n" + b"b" * 20 + b"\r\n"
    p.write_bytes(data)
    # bloque de 10: el \r cae al final del primer bloque y el \n en el siguiente
    assert hash_file(p, chunk_size=10) == hash_bytes(data)


def test_hash_vacio_binario_grande(tmp_path):
    empty = tmp_path / "e"
    empty.write_bytes(b"")
    assert hash_file(empty) == hash_bytes(b"")
    binf = tmp_path / "b"
    binf.write_bytes(bytes(range(256)) * 10)
    assert hash_file(binf) == hash_bytes(bytes(range(256)) * 10)
    big = tmp_path / "g"
    big.write_bytes(b"linea\r\n" * 200_000)
    assert hash_file(big) == hash_bytes(b"linea\n" * 200_000)


# ---- parser --------------------------------------------------------------------
DOC = """---
tipo: codigo
categorías:
  - proyecto
  - ia
---
Intro con [[src/a.go.md#Sec|texto]].

## Uno
texto uno
### Uno.a
a
### Uno.b
b
## Dos
```python
# comentario, no heading
x = "[[no/es.md|enlace]]"
```
Con `[[inline.md|tampoco]]` y [[sin/alias.md]].
# Tres
fin
"""


def test_frontmatter_y_listas():
    doc = parser.parse(DOC)
    assert doc.meta["tipo"] == "codigo"
    assert doc.meta["categorías"] == ["proyecto", "ia"]


def test_seccion_hasta_igual_o_mayor_jerarquia():
    doc = parser.parse(DOC)
    text = parser.section_text(doc, "Uno")
    assert text.startswith("## Uno") and "### Uno.a" in text and "### Uno.b" in text
    assert "## Dos" not in text
    assert parser.section_text(doc, "Tres").rstrip().endswith("fin")  # hasta el final
    assert parser.section_text(doc, "Uno#Uno.b").strip() == "### Uno.b\nb"


def test_comentario_en_bloque_de_codigo_no_es_heading():
    doc = parser.parse(DOC)
    assert "comentario, no heading" not in [h.text for h in doc.headings]


def test_heading_snake_y_legible():
    doc = parser.parse("## framework_web & FastAPI\nx\n## otra & Otra\n")
    assert parser.section_text(doc, "framework_web").startswith("## framework_web & FastAPI")
    assert parser.section_text(doc, "framework_web & FastAPI").startswith("## framework_web")


def test_seccion_inexistente_y_ambigua():
    doc = parser.parse("## a\n## a\n")
    with pytest.raises(AmbiguousError):
        parser.find_section(doc, "a")
    with pytest.raises(NotFoundError):
        parser.find_section(doc, "b")


def test_enlaces():
    doc = parser.parse(DOC)
    links = parser.links(doc)
    raws = [(l.target, l.section, l.alias) for l in links]
    assert ("src/a.go.md", "Sec", "texto") in raws
    assert ("sin/alias.md", None, None) in raws
    assert all("no/es.md" != l.target for l in links)  # dentro de bloque de código
    assert all("inline.md" != l.target for l in links)  # dentro de código inline


def test_enlace_con_espacios_y_sin_seccion():
    doc = parser.parse("ver [[carpeta con espacios/archivo.py.md|archivo]] y [[#Local|local]]\n")
    links = parser.links(doc)
    assert links[0].target == "carpeta con espacios/archivo.py.md" and links[0].section is None
    assert links[1].target == "" and links[1].section == "Local"


def test_is_empty():
    assert parser.is_empty("---\ntipo: codigo\n---\n\n  \n")
    assert not parser.is_empty("---\ntipo: codigo\n---\nalgo\n")
    assert parser.is_empty("")


# ---- exclusión -----------------------------------------------------------------
@pytest.mark.parametrize("rel,is_dir,reason", [
    ("node_modules", True, "dependencias"),
    ("src/vendor", True, "dependencias"),
    ("img/logo.png", False, "extensión"),
    ("package-lock.json", False, "lockfile"),
    ("config/.env", False, "sensible"),
    ("certs/server.pem", False, "sensible"),
    (".DS_Store", False, "cruft"),
    ("notas.swp", False, "cruft"),
    (".cache", True, "oculta"),
    ("a#b.py", False, "enlace"),
])
def test_ejes_de_exclusion(tmp_path, rel, is_dir, reason):
    verdict, why = Exclusion(tmp_path).check(rel, is_dir)
    assert verdict == EXCLUIR and reason in why


def test_excepciones_graph_y_github(tmp_path):
    ex = Exclusion(tmp_path)
    assert ex.check(".github", True)[0] == INCLUIR
    assert ex.check(".github/workflows/ci.yml", False)[0] == INCLUIR
    assert ex.check(".graph", True)[0] == GRAFO
    assert ex.check(".graph/src/a.md", False)[0] == GRAFO


def test_binario_por_contenido(tmp_path):
    (tmp_path / "blob").write_bytes(b"\x00\x01\x02")
    assert Exclusion(tmp_path).check("blob", False)[0] == EXCLUIR


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks requieren privilegios en Windows")
def test_symlinks_no_se_siguen(tmp_path):
    write(tmp_path, "real/a.py")
    os.symlink(tmp_path / "real", tmp_path / "enlace")
    scan = walk(tmp_path)
    assert "real/a.py" in scan.files
    assert not any(f.startswith("enlace") for f in scan.files)


def test_exclude_de_usuario_suma_y_se_relee(tmp_path):
    write(tmp_path, "src/a.py")
    write(tmp_path, "generado/b.py")
    write(tmp_path, "node_modules/c.js")
    (tmp_path / ".graph").mkdir()
    (tmp_path / ".graph/exclude").write_text("\n# comentario\ngenerado\n\n", encoding="utf-8")
    scan = walk(tmp_path)
    assert scan.files == ["src/a.py"]  # la regla por defecto (node_modules) sigue
    (tmp_path / ".graph/exclude").write_text("", encoding="utf-8")
    assert "generado/b.py" in walk(tmp_path).files  # se relee en cada corrida


def test_env_excluido_dentro_de_carpeta_incluida(tmp_path):
    write(tmp_path, "app/.env", "X=1")
    write(tmp_path, "app/main.py")
    assert walk(tmp_path).files == ["app/main.py"]
