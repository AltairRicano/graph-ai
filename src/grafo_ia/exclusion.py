"""Motor de exclusión multi-eje y recorrido del árbol del proyecto.

Tres veredictos: INCLUIR (se espeja), EXCLUIR (no existe para el grafo) y
GRAFO (`.graph`: es el propio grafo, se maneja aparte y nunca se espeja).
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from grafo_ia.paths import GRAPH_DIR, graph_dir

INCLUIR = "incluir"
EXCLUIR = "excluir"
GRAFO = "grafo"

EXCLUDE_FILE = "exclude"

HIDDEN_DIR_EXCEPTIONS = {".github"}

DEPENDENCY_DIRS = {
    "node_modules", "vendor", "dist", "build", "target", "bin", "obj",
    "site-packages", "venv", "__pycache__", "bower_components", "jspm_packages",
}

BINARY_EXTENSIONS = {
    # compilados / objetos
    ".pyc", ".pyo", ".class", ".o", ".obj", ".so", ".dll", ".dylib", ".exe", ".a", ".lib",
    ".wasm", ".jar", ".war", ".whl", ".egg",
    # comprimidos
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".zst",
    # documentos binarios
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
    # imágenes
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff", ".psd", ".avif", ".heic",
    # audio / video
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".mkv", ".mov", ".avi", ".webm",
    # fuentes
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # datos binarios
    ".db", ".sqlite", ".sqlite3", ".bin", ".dat", ".npy", ".npz", ".pkl", ".parquet",
}

GENERATED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock",
    "go.sum", "Gemfile.lock", "composer.lock", "Pipfile.lock", "uv.lock", "bun.lockb",
}

SENSITIVE_PATTERNS = [
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks",
    "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*", "credentials", "credentials.*",
    ".netrc", ".pgpass", "*.secret", "secrets.*",
]

CRUFT_PATTERNS = [".DS_Store", "Thumbs.db", "desktop.ini", "*.swp", "*.swo", "*.tmp", "*~"]

# reglas iniciales de `.graph/exclude`: `graph init` las escribe al crearlo, así
# cada proyecto puede quitarlas (a mano o con `graph ignore --remove`). No es
# código con lógica que documentar: un gemelo solo repetiría el archivo.
# Como toda regla propia, distinguen mayúsculas (`LICENSE*` no deja fuera `license.py`).
INITIAL_RULES = {
    "documentación": ["*.md", "*.markdown", "*.rst", "docs", "doc"],
    "licencias": ["LICENSE*", "LICENCE*", "COPYING*", "NOTICE*"],
    "pruebas": ["tests", "test", "__tests__", "test_*.py", "*_test.py", "*_test.go", "*.test.*", "*.spec.*"],
    "plantillas": ["plantillas", "templates"],
}

# carpetas operativas en la raíz del proyecto: nunca se espejan
OPERATIONAL_ROOT_DIRS = {"agentes": "reportes de agentes (operativo, no producto)"}

SUGGESTED_DIRS = {"coverage", "htmlcov", "logs", "log", "tmp", "temp", "cache", "out", "__snapshots__"}
LARGE_DIR_THRESHOLD = 300
BINARY_SNIFF_BYTES = 8192


@dataclass
class Scan:
    dirs: list[str] = field(default_factory=list)  # carpetas incluidas (sin la raíz)
    files: list[str] = field(default_factory=list)  # archivos incluidos
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (ruta, razón)


def norm_rule(rule: str) -> str:
    """`\\` -> `/`, sin espacios ni `/` final. Un `/` inicial se conserva: ancla a la raíz."""
    rule = rule.strip().replace("\\", "/").rstrip("/")
    return "" if rule.strip("/") == "" else rule


def load_user_rules(root: Path, filename: str = EXCLUDE_FILE) -> list[str]:
    """Reglas de `.graph/exclude` (o de otro archivo de patrones): se releen en cada corrida."""
    p = graph_dir(root) / filename
    if not p.exists():
        return []
    rules = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rule = norm_rule(line)
            if rule:
                rules.append(rule)
    return rules


LINK_BREAKING_CHARS = set("#|[]")
LINK_BREAKING_REASON = "el nombre tiene # | [ o ], que rompen la sintaxis de enlace"


def _breaks_link(name: str) -> bool:
    return any(c in LINK_BREAKING_CHARS for c in name)


def match_rule(rules: list[str], rel: str, name: str) -> str | None:
    """Primera regla propia que cubre `rel`: nombre suelto en cualquier nivel, con `/` desde la raíz."""
    for rule in rules:
        if rule.startswith("/"):
            rule_rel = rule.lstrip("/")
            if rel == rule_rel or rel.startswith(rule_rel + "/") or fnmatch.fnmatchcase(rel, rule_rel):
                return rule
        elif "/" in rule:
            if rel == rule or rel.startswith(rule + "/") or fnmatch.fnmatchcase(rel, rule):
                return rule
        elif fnmatch.fnmatchcase(name, rule):
            return rule
    return None


def _matches_any(name: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def looks_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(BINARY_SNIFF_BYTES)
    except OSError:
        return False


class Exclusion:
    def __init__(self, root: Path, sniff_binary: bool = True):
        self.root = Path(root)
        self.user_rules = load_user_rules(self.root)
        self.sniff_binary = sniff_binary

    def check(self, rel: str, is_dir: bool, is_symlink: bool = False) -> tuple[str, str]:
        """Veredicto para una ruta relativa, evaluando cada componente."""
        parts = rel.split("/") if rel else []
        if not parts:
            return INCLUIR, ""
        if parts[0] == GRAPH_DIR:
            return GRAFO, "es el propio grafo"
        # carpetas ancestro: si una está excluida, todo lo de abajo también
        for i, part in enumerate(parts[:-1]):
            verdict, reason = self._check_dir("/".join(parts[: i + 1]), part)
            if verdict != INCLUIR:
                return verdict, reason
        name = parts[-1]
        if is_symlink:
            return EXCLUIR, "symlink (no se sigue)"
        if is_dir:
            return self._check_dir(rel, name)
        return self._check_file(rel, name)

    def _user_rule(self, rel: str, name: str) -> str | None:
        return match_rule(self.user_rules, rel, name)

    def _check_dir(self, rel: str, name: str) -> tuple[str, str]:
        if _breaks_link(name):
            return EXCLUIR, LINK_BREAKING_REASON
        if name.startswith(".") and name not in HIDDEN_DIR_EXCEPTIONS:
            return EXCLUIR, "carpeta oculta"
        if name in DEPENDENCY_DIRS or name.endswith(".egg-info"):
            return EXCLUIR, "carpeta de dependencias/build"
        if rel in OPERATIONAL_ROOT_DIRS:
            return EXCLUIR, OPERATIONAL_ROOT_DIRS[rel]
        rule = self._user_rule(rel, name)
        if rule:
            return EXCLUIR, f".graph/exclude: {rule}"
        return INCLUIR, ""

    def _check_file(self, rel: str, name: str) -> tuple[str, str]:
        if _breaks_link(name):
            return EXCLUIR, LINK_BREAKING_REASON
        if _matches_any(name, SENSITIVE_PATTERNS):
            return EXCLUIR, "archivo sensible"
        if _matches_any(name, CRUFT_PATTERNS):
            return EXCLUIR, "cruft de sistema/editor"
        if name in GENERATED_FILES:
            return EXCLUIR, "archivo generado (lockfile)"
        if os.path.splitext(name)[1].lower() in BINARY_EXTENSIONS:
            return EXCLUIR, "binario por extensión"
        rule = self._user_rule(rel, name)
        if rule:
            return EXCLUIR, f".graph/exclude: {rule}"
        if self.sniff_binary and looks_binary(self.root / rel):
            return EXCLUIR, "binario por contenido"
        return INCLUIR, ""

    def is_included(self, rel: str, is_dir: bool | None = None) -> bool:
        p = self.root / rel
        if is_dir is None:
            is_dir = p.is_dir() and not p.is_symlink()
        verdict, _ = self.check(rel, is_dir, p.is_symlink())
        return verdict == INCLUIR


def walk(root: Path, exclusion: Exclusion | None = None, scope: str = "") -> Scan:
    """Recorre `scope` (relativo a la raíz) sin seguir symlinks. Orden determinista."""
    exclusion = exclusion or Exclusion(root)
    scan = Scan()
    start = root / scope if scope else root
    if scope:
        if not start.exists() and not start.is_symlink():
            return scan  # desapareció: todo lo que había bajo el alcance se reconcilia como borrado
        verdict, reason = exclusion.check(scope, start.is_dir(), start.is_symlink())
        if verdict != INCLUIR:
            scan.excluded.append((scope, reason))
            return scan
        if start.is_file():
            scan.files.append(scope)
            return scan
        scan.dirs.append(scope)
    stack = [scope]
    while stack:
        rel_dir = stack.pop()
        try:
            entries = sorted(os.scandir(root / rel_dir if rel_dir else root), key=lambda e: e.name)
        except OSError:
            continue
        subdirs = []
        for entry in entries:
            rel = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
            is_link = entry.is_symlink()
            is_dir = entry.is_dir(follow_symlinks=False)
            verdict, reason = exclusion.check(rel, is_dir, is_link)
            if verdict == GRAFO:
                continue
            if verdict == EXCLUIR:
                scan.excluded.append((rel, reason))
                continue
            if is_dir:
                scan.dirs.append(rel)
                subdirs.append(rel)
            elif entry.is_file(follow_symlinks=False):
                scan.files.append(rel)
        stack.extend(reversed(subdirs))
    scan.dirs.sort()
    scan.files.sort()
    return scan


def suggest(scan: Scan) -> list[tuple[str, str]]:
    """Exclusiones extra que parecen obvias y no están cubiertas."""
    out = []
    counts: dict[str, int] = {}
    for f in scan.files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            counts[d] = counts.get(d, 0) + 1
    for d in scan.dirs:
        name = d.rsplit("/", 1)[-1]
        if name.lower() in SUGGESTED_DIRS:
            out.append((d, "suele ser generada o temporal"))
        elif counts.get(d, 0) >= LARGE_DIR_THRESHOLD:
            out.append((d, f"{counts[d]} archivos: ¿es código propio o generado?"))
    return out
