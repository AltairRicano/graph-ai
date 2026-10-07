"""CLI `graph`: despachador de subcomandos y códigos de salida.

0 = bien, 2 = error de uso o de precondición.
"""

from __future__ import annotations

import argparse
import sys

from grafo_ia import __version__, legacy
from grafo_ia.commands import init, multiedit, query
from grafo_ia.errors import EXIT_USAGE, GraphError

MODULES = (init, query, multiedit)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="graph", description="Estado de un proyecto de código para contexto de IA: cinco documentos en .graph/Estado_Proyecto.")
    p.add_argument("-C", metavar="DIR", help="correr como si se invocara desde DIR")
    p.add_argument("--version", action="version", version=f"grafo_ia {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<comando>")
    sub.required = True
    for m in MODULES:
        m.register(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    argv = sys.argv[1:] if argv is None else list(argv)
    code = legacy.dispatch(argv)  # un `.graph` de la versión de gemelos lo atiende el CLI anterior
    if code is not None:
        return code
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except GraphError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
