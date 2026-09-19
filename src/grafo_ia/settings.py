"""`.graph/config`: banderas sueltas (`strict`) y `clave=valor` (`nombre`, `hash`)."""

from __future__ import annotations

from pathlib import Path

from grafo_ia.paths import graph_dir

CONFIG_FILE = "config"


def _path(root: Path) -> Path:
    return graph_dir(root) / CONFIG_FILE


def _lines(root: Path) -> list[str]:
    p = _path(root)
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8").splitlines()


def _write(root: Path, lines: list[str]) -> None:
    _path(root).write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def get_flag(root: Path, flag: str) -> bool:
    return any(line.strip() == flag for line in _lines(root))


def set_flag(root: Path, flag: str, on: bool) -> bool:
    """Activa o desactiva una bandera. Devuelve True si el archivo cambió."""
    lines = _lines(root)
    present = any(line.strip() == flag for line in lines)
    if on == present:
        return False
    if on:
        lines.append(flag)
    else:
        lines = [line for line in lines if line.strip() != flag]
    _write(root, lines)
    return True


def get_value(root: Path, key: str) -> str | None:
    for line in _lines(root):
        k, sep, v = line.partition("=")
        if sep and k.strip() == key:
            return v.strip()
    return None


def set_value(root: Path, key: str, value: str) -> None:
    lines = _lines(root)
    for i, line in enumerate(lines):
        k, sep, _ = line.partition("=")
        if sep and k.strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    _write(root, lines)
