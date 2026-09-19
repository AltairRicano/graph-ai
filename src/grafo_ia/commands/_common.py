"""Utilidades compartidas por los subcomandos."""

from __future__ import annotations

import os
from pathlib import Path

from grafo_ia.paths import find_root


def cwd_of(args) -> Path:
    return Path(getattr(args, "C", None) or os.getcwd()).absolute()


def root_of(args) -> Path:
    return find_root(cwd_of(args))


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def print_list(title: str, items, empty: str | None = None) -> None:
    items = list(items)
    print(f"{title} ({len(items)})")
    if not items and empty:
        print(f"  {empty}")
    for item in items:
        print(f"  {item}")
