"""Parser de markdown: frontmatter, secciones y bloques de código."""

from __future__ import annotations

import pytest

from grafo_ia import parser
from grafo_ia.errors import AmbiguousError, NotFoundError

DOC = """---
tipo: estado
categorías:
  - proyecto
  - ia
---
Intro.

## Uno
texto uno
### Uno.a
a
### Uno.b
b
## Dos
```python
# comentario, no heading
```
# Tres
fin
"""


def test_frontmatter_y_listas():
    doc = parser.parse(DOC)
    assert doc.meta["tipo"] == "estado"
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
