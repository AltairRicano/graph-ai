"""`graph config strict [on|off]`: modo estricto de `pre-commit`.

Solo toca `.graph/config`, no el grafo, así que no toma el lock del index.json.
Idempotente.
"""

from __future__ import annotations

from grafo_ia import settings
from grafo_ia.commands._common import root_of
from grafo_ia.errors import GraphError

STRICT = "strict"


def register(sub) -> None:
    p = sub.add_parser("config", help="opciones del proyecto (hoy: strict)")
    p.add_argument("opcion", choices=[STRICT])
    p.add_argument("valor", nargs="?", help="on | off (sin valor: muestra el estado)")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    if args.valor is None:
        print(f"{STRICT}: {'on' if settings.get_flag(root, STRICT) else 'off'}")
        return 0
    if args.valor not in ("on", "off"):
        raise GraphError(f"valor inválido '{args.valor}': usa on u off")
    changed = settings.set_flag(root, STRICT, args.valor == "on")
    print(f"{STRICT}: {args.valor}" + ("" if changed else " (sin cambios)"))
    return 0
