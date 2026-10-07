"""Proyectos con un `.graph` de la versión de gemelos: los atiende el CLI anterior.

Ese formato se reconoce por su `index.json`. Si el `.graph` más cercano lo trae,
`graph` le pasa el comando tal cual a `graph-gemelos` (la versión anterior,
instalada aparte), para que esos proyectos sigan funcionando sin cambiar nada.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from grafo_ia.errors import EXIT_USAGE, NoGraphError
from grafo_ia.paths import find_root, graph_dir

LEGACY_COMMAND = "graph-gemelos"
LEGACY_MARKER = "index.json"


def _cwd(argv: list[str]) -> Path:
    """El `-C DIR` de la línea de comandos; lo demás no se valida, porque el comando puede no existir aquí."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("-C")
    known, _ = pre.parse_known_args(argv)
    return Path(known.C or ".").absolute()


def is_legacy(cwd: Path) -> bool:
    try:
        root = find_root(cwd)
    except NoGraphError:
        return False
    return (graph_dir(root) / LEGACY_MARKER).is_file()


def dispatch(argv: list[str]) -> int | None:
    """Corre el comando con el CLI anterior si el proyecto es de ese formato. None = no lo es."""
    if not is_legacy(_cwd(argv)):
        return None
    exe = shutil.which(LEGACY_COMMAND)
    if exe is None:
        print(f"error: este .graph es de la versión de gemelos (trae {LEGACY_MARKER}) y `{LEGACY_COMMAND}` no está en el PATH", file=sys.stderr)
        return EXIT_USAGE
    return subprocess.call([exe, *argv])
