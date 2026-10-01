"""`graph trivial`: administra `.graph/trivial` desde el CLI.

- Sin argumentos: lista los patrones.
- `graph trivial <patrón>...`: los agrega.
- `graph trivial --remove <patrón>...`: los quita.
No toca el grafo ni los gemelos: el estado se calcula al vuelo, así que un
archivo trivial con gemelo vacío deja de salir como faltante en cuanto entra
la regla, y vuelve a salir en cuanto se quita.
"""

from __future__ import annotations

from grafo_ia import trivial as rules
from grafo_ia.commands._common import root_of
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import norm_rule
from grafo_ia.paths import graph_dir


def register(sub) -> None:
    p = sub.add_parser("trivial", help="patrones de archivos cuyo gemelo no necesita contenido (.graph/trivial)")
    p.add_argument("patrones", nargs="*", metavar="patrón",
                   help="nombre suelto = en cualquier nivel (admite comodines); con '/' = desde la raíz")
    p.add_argument("--remove", action="store_true", help="quita los patrones en vez de agregarlos")
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    path = graph_dir(root) / rules.TRIVIAL_FILE
    current = rules.load_rules(root)
    patterns = [r for r in map(norm_rule, args.patrones) if r]
    if not patterns:
        if args.patrones:
            raise GraphError("patrón vacío")
        if args.remove:
            raise GraphError("--remove necesita al menos un patrón")
        print(f"patrones en .graph/trivial ({len(current)})")
        for r in current:
            print(f"  {r}")
        return 0
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else rules.TRIVIAL_HEADER.splitlines()
    if args.remove:
        gone = [p for p in patterns if p in current]
        lines = [ln for ln in lines if not ln.strip() or ln.strip().startswith("#") or norm_rule(ln) not in gone]
        for p in patterns:
            print(f"patrón quitado: {p}" if p in gone else f"no estaba: {p}")
    else:
        new = [p for p in dict.fromkeys(patterns) if p not in current]
        lines += new
        for p in patterns:
            print(f"patrón agregado: {p}" if p in new else f"ya estaba: {p}")
    path.write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")
    return 0
