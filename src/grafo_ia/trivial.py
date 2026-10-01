"""Archivos triviales: están en el grafo, pero su gemelo no necesita contenido.

`.graph/trivial` lleva patrones con la misma sintaxis que `.graph/exclude`.
Un archivo que cae en uno y cuyo gemelo solo tiene frontmatter cuenta como
`trivial` en vez de `faltante`: nadie tiene que llenarlo para dejar el grafo
en verde. Si alguien le escribe contenido (ahí vive una decisión que vale la
pena), vuelve a las reglas normales del hash.
Sin el archivo no hay triviales: los grafos anteriores no cambian.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

from grafo_ia.exclusion import load_user_rules, match_rule

TRIVIAL_FILE = "trivial"

TRIVIAL_HEADER = (
    "# Archivos cuyo gemelo no necesita contenido, un patrón por línea (misma sintaxis que `exclude`).\n"
    "# Siguen en el grafo y se pueden enlazar; solo dejan de contar como faltantes mientras estén vacíos.\n"
    "# Se editan a mano o con `graph trivial`.\n"
)

# reglas iniciales: `graph init` las escribe al crear el archivo y cada proyecto puede quitarlas
INITIAL_TRIVIAL = {
    "estilos": ["*.css", "*.scss", "*.sass", "*.less"],
    "configuración y datos": ["*.json", "*.toml", "*.yaml", "*.yml", "*.ini", "*.cfg", "*.conf", "*.properties"],
    "archivos de herramientas": [".gitignore", ".gitattributes", ".editorconfig", ".dockerignore", ".prettierrc*", ".eslintrc*"],
}


def initial_text() -> str:
    groups = "".join(f"\n# {motivo}\n" + "".join(r + "\n" for r in rules) for motivo, rules in INITIAL_TRIVIAL.items())
    return TRIVIAL_HEADER + groups


def load_rules(root: Path) -> list[str]:
    return load_user_rules(root, TRIVIAL_FILE)


def is_trivial(rules: list[str], rel: str) -> bool:
    return bool(rules) and match_rule(rules, rel, posixpath.basename(rel)) is not None
