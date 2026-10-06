"""Archivos triviales: están en el grafo, pero no le piden contenido al índice de su carpeta.

`.graph/trivial` lleva patrones con la misma sintaxis que `.graph/exclude`.
Una carpeta cuyos archivos propios caen todos en uno (o que no tiene archivos
propios) cuenta como `trivial` en vez de `faltante` mientras su índice no tenga
propósito: nadie tiene que llenarlo para dejar el grafo en verde. Tampoco
desactualizan el índice al entrar o salir.
Sin el archivo no hay triviales.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

from grafo_ia.exclusion import load_user_rules, match_rule

TRIVIAL_FILE = "trivial"

TRIVIAL_HEADER = (
    "# Archivos que no le piden contenido al índice de su carpeta, un patrón por línea (misma sintaxis que `exclude`).\n"
    "# Siguen en el grafo y se pueden enlazar; una carpeta que solo tiene de estos no cuenta como faltante.\n"
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
