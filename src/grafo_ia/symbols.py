"""Nombre canónico de un heading, para comparar secciones sin importar cómo se escribieron."""

from __future__ import annotations

import re

from grafo_ia import parser


def heading_name(text: str) -> str:
    """`calcular_total`, `` `calcular_total()` `` y `calcular_total(a, b)` valen lo mismo."""
    text = parser.heading_ident(text) or text
    text = text.replace("`", "").strip()
    return re.sub(r"\s*\(.*\)$", "", text).strip()
