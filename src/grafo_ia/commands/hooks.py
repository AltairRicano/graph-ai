"""Hooks de git y repo anidado de `.graph`.

`.graph` es un repo git propio, sin remoto nunca, ignorado por el repo
principal. Los hooks del repo principal son shims de shell que llaman a
`graph hook <nombre>`; si ya había un hook, se encadena (corre primero).
Todos avisan y ninguno bloquea, salvo `pre-commit` en modo estricto.
"""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from grafo_ia import graph_io, settings, states
from grafo_ia.commands._common import cwd_of
from grafo_ia.edges import TwinCache
from grafo_ia.errors import GraphError, NoGraphError
from grafo_ia.exclusion import Exclusion
from grafo_ia.hashing import hash_bytes
from grafo_ia.paths import GRAPH_DIR, code_id, find_root, graph_dir, to_rel

HOOKS = ("pre-commit", "post-commit", "post-checkout", "post-merge", "post-rewrite")
MARKER = "# grafo_ia: hook instalado por `graph init`"
CHAINED_SUFFIX = ".pre-grafo"
TRAILER = "Code-commit"
NESTED_GITIGNORE = "index.lock\nwatcher.pid\nwatcher.log\nindex.json.*.tmp\nindex.json.corrupt-*\n*.mv-*\n.grafo-*.tmp\n"


# ---- git ---------------------------------------------------------------------
def git_available() -> bool:
    return shutil.which("git") is not None


def git(cwd: Path, *args: str, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if Path(cwd).name == GRAPH_DIR:
        # los hooks corren con GIT_DIR/GIT_INDEX_FILE del repo principal: no deben
        # filtrarse al anidado. En el principal sí se respetan (commit parcial usa
        # un índice temporal).
        for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY"):
            env.pop(var, None)
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=check, input=input, text=True,
        capture_output=True, env=env, encoding="utf-8", errors="replace",
    )


def _out(cwd: Path, *args: str) -> str | None:
    r = git(cwd, *args, check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def main_toplevel(root: Path) -> Path | None:
    top = _out(root, "rev-parse", "--show-toplevel")
    if not top:
        return None
    top_p = Path(top)
    # si el toplevel resulta ser el repo anidado, no hay repo principal
    if top_p.resolve() == graph_dir(root).resolve():
        return None
    return top_p


def main_head(root: Path) -> str | None:
    if main_toplevel(root) is None:
        return None
    return _out(root, "rev-parse", "--verify", "-q", "HEAD")


def nested_ok(root: Path) -> bool:
    return (graph_dir(root) / ".git").exists()


def init_nested(root: Path) -> None:
    g = graph_dir(root)
    if not nested_ok(root):
        git(g, "init", "-q")
        # nace en la misma rama que el código, para que post-checkout los mantenga alineados
        branch = _out(root, "symbolic-ref", "-q", "--short", "HEAD") if main_toplevel(root) else None
        if branch:
            git(g, "symbolic-ref", "HEAD", f"refs/heads/{branch}", check=False)
    gi = g / ".gitignore"
    if not gi.exists():
        gi.write_text(NESTED_GITIGNORE, encoding="utf-8")


def ensure_main_gitignore(root: Path) -> None:
    gi = root / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    if any(line.strip() in (GRAPH_DIR, GRAPH_DIR + "/", "/" + GRAPH_DIR, "/" + GRAPH_DIR + "/") for line in lines):
        return
    with open(gi, "a", encoding="utf-8") as f:
        if lines and lines[-1].strip():
            f.write("\n")
        f.write(f"# grafo de contexto para IA (repo anidado, personal por máquina)\n{GRAPH_DIR}/\n")


def nested_has_commits(root: Path) -> bool:
    return nested_ok(root) and _out(graph_dir(root), "rev-parse", "--verify", "-q", "HEAD") is not None


def mirror_commit(root: Path, message: str, sha: str | None) -> bool:
    """Commit en `.graph` con el mismo mensaje + trailer; vacío si no hay cambios."""
    if not nested_ok(root):
        return False
    g = graph_dir(root)
    git(g, "add", "-A", check=False)
    body = message.rstrip() or "graph"
    if sha:
        body += f"\n\n{TRAILER}: {sha}"
    r = git(g, "commit", "-q", "--allow-empty", "--no-verify", "-F", "-", input=body + "\n", check=False)
    if r.returncode != 0:
        print(f"[AVISO] no se pudo commitear en .graph: {r.stderr.strip() or r.stdout.strip()}")
        return False
    return True


def last_code_commit(root: Path) -> str | None:
    if not nested_has_commits(root):
        return None
    msg = _out(graph_dir(root), "log", "-1", "--format=%B")
    found = None
    for line in (msg or "").splitlines():
        if line.startswith(f"{TRAILER}:"):
            found = line.split(":", 1)[1].strip()
    return found


def find_mirror(root: Path, sha: str) -> str | None:
    """Commit más reciente de `.graph` cuyo trailer apunta a `sha`."""
    if not nested_has_commits(root):
        return None
    out = _out(graph_dir(root), "log", "--all", "--format=%H", f"--grep=^{TRAILER}: {sha}$")
    return out.splitlines()[0] if out else None


def head_mismatch(root: Path) -> str | None:
    """Chequeo perezoso: HEAD del código contra el último Code-commit de `.graph`."""
    if not git_available() or not nested_has_commits(root):
        return None
    head = main_head(root)
    if head is None:
        return None
    mirrored = last_code_commit(root)
    if mirrored == head:
        return None
    return (f"el grafo está en {mirrored[:10] if mirrored else '(sin commit espejo)'} y el código en {head[:10]}; "
            f"revisa `graph incomplete` y confirma con `graph update`")


# ---- instalación -------------------------------------------------------------
def _shim(name: str) -> str:
    py = shlex.quote(Path(sys.executable).as_posix())
    run = (
        f'if [ -x {py} ] && {py} -c "import grafo_ia" >/dev/null 2>&1; then set -- {py} -m grafo_ia hook {name} "$@"\n'
        f'elif command -v graph >/dev/null 2>&1; then set -- graph hook {name} "$@"\n'
        f"else exit 0\nfi\n"
    )
    chained = f'"$HOOK_DIR/{name}{CHAINED_SUFFIX}"'
    if name == "post-rewrite":  # stdin se lee una vez y se pasa a los dos
        return (
            f"#!/bin/sh\n{MARKER}\nHOOK_DIR=$(dirname \"$0\")\ninput=$(cat)\n"
            f"if [ -x {chained} ]; then printf '%s\\n' \"$input\" | {chained} \"$@\" || exit $?; fi\n"
            f"{run}printf '%s\\n' \"$input\" | \"$@\"\n"
        )
    return (
        f"#!/bin/sh\n{MARKER}\nHOOK_DIR=$(dirname \"$0\")\n"
        f"if [ -x {chained} ]; then {chained} \"$@\" || exit $?; fi\n"
        f"{run}exec \"$@\"\n"
    )


def hooks_dir(root: Path) -> Path | None:
    p = _out(root, "rev-parse", "--git-path", "hooks")
    if not p:
        return None
    path = Path(p)
    return path if path.is_absolute() else (root / path)


def install(root: Path) -> list[str]:
    d = hooks_dir(root)
    if d is None:
        return []
    d.mkdir(parents=True, exist_ok=True)
    done = []
    for name in HOOKS:
        target = d / name
        if target.exists():
            current = target.read_text(encoding="utf-8", errors="replace")
            if MARKER not in current:
                chained = d / (name + CHAINED_SUFFIX)
                if not chained.exists():
                    target.replace(chained)
        target.write_text(_shim(name), encoding="utf-8", newline="\n")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        done.append(name)
    return done


# ---- hooks -------------------------------------------------------------------
def _staged(root: Path, top: Path) -> list[tuple[str, str]]:
    """(ruta de proyecto, ruta desde el toplevel) de los archivos staged."""
    out = git(top, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").stdout
    result = []
    for p in filter(None, out.split("\0")):
        try:
            rel = to_rel(root, top / p)
        except GraphError:
            continue
        if rel and not rel.startswith(GRAPH_DIR + "/"):
            result.append((rel, p))
    return result


def pre_commit(root: Path, argv: list[str]) -> int:
    top = main_toplevel(root)
    if top is None:
        return 0
    staged = _staged(root, top)
    excl = Exclusion(root)
    staged = [(rel, p) for rel, p in staged if excl.is_included(rel, False)]
    graph = graph_io.load(root)
    cache = TwinCache(root)
    top_path = {rel: p for rel, p in staged}

    def staged_hash(rel: str) -> str | None:
        r = subprocess.run(["git", "show", f":{top_path[rel]}"], cwd=str(top), capture_output=True)
        return hash_bytes(r.stdout) if r.returncode == 0 else None

    grave: list[str] = []
    for rel, _ in staged:
        node = graph.nodes.get(code_id(rel))
        if node is None:
            grave.append(f"faltante: {rel} (ni siquiera está en el grafo; corre `graph add`)")
            continue
        state = states.code_state(root, node, cache, staged_hash)
        if state in (states.FALTANTE, states.DESACTUALIZADO):
            grave.append(f"{state}: {rel}")
    rep = states.report(root, graph, [rel for rel, _ in staged], cache) if staged else states.Report()
    strict = settings.get_flag(root, "strict")
    if grave:
        print("[WARNING] grafo: gemelos que no están al día en lo que vas a commitear:")
        for g in grave:
            print(f"  - {g}")
        print("  Escribe/actualiza el gemelo y confírmalo con `graph update <ruta>`.")
    if rep.pendientes:
        print("grafo (informativo): pendientes por crear en lo staged:")
        for p in rep.pendientes:
            print(f"  · {p.source}:{p.line} {p.link}")
    if rep.huerfanos:
        print("grafo (informativo): huérfanos dentro de lo staged (revisa el alcance):")
        for h in rep.huerfanos:
            print(f"  · {h}")
    msg = head_mismatch(root)
    if msg:
        print(f"[AVISO] {msg}")
    if grave and strict:
        print("[grafo] modo estricto: commit bloqueado (sáltalo con --no-verify)")
        return 1
    return 0


def post_commit(root: Path, argv: list[str]) -> int:
    sha = main_head(root)
    msg = _out(root, "log", "-1", "--pretty=%B") or ""
    mirror_commit(root, msg, sha)
    return 0


def post_checkout(root: Path, argv: list[str]) -> int:
    if len(argv) < 3 or argv[2] != "1":
        return 0  # checkout de archivo: nada que hacer
    new = argv[1]
    if not nested_has_commits(root):
        return 0
    g = graph_dir(root)
    if _out(g, "status", "--porcelain"):
        print("[AVISO] .graph tiene cambios sin commitear: no se mueve de rama/commit")
        return 0
    branch = _out(root, "symbolic-ref", "-q", "--short", "HEAD")
    if branch:
        if _out(g, "rev-parse", "--verify", "-q", f"refs/heads/{branch}"):
            r = git(g, "checkout", "-q", branch, check=False)
        else:
            r = git(g, "checkout", "-q", "-b", branch, check=False)
        if r.returncode != 0:
            print(f"[AVISO] .graph no pudo cambiar a la rama {branch}: {r.stderr.strip()}")
        return 0
    mirror = find_mirror(root, new)
    if mirror is None:
        print(f"[AVISO] .graph no tiene un commit espejo de {new[:10]}; se queda donde está")
        return 0
    r = git(g, "checkout", "-q", "--detach", mirror, check=False)
    if r.returncode != 0:
        print(f"[AVISO] .graph no pudo moverse a {mirror[:10]}: {r.stderr.strip()}")
    return 0


def post_merge(root: Path, argv: list[str]) -> int:
    from grafo_ia.commands.populate import populate
    from grafo_ia.reconciliation import reconcile

    with graph_io.transaction(root) as graph:
        reconcile(root, graph, "")
        populate(root, graph)
    changed = _out(root, "diff", "--name-only", "ORIG_HEAD", "HEAD")
    top = main_toplevel(root)
    rels = []
    for p in (changed or "").splitlines():
        try:
            rel = to_rel(root, (top or root) / p)
        except GraphError:
            continue
        if rel and not rel.startswith(GRAPH_DIR):
            rels.append(rel)
    if not rels:
        return 0
    rep = states.report(root, graph_io.load(root), rels, links=False)
    if rep.faltantes or rep.desactualizados:
        print("[WARNING] grafo: el merge trajo código sin gemelo al día:")
        for r in rep.faltantes:
            print(f"  - faltante: {r}")
        for r in rep.desactualizados:
            print(f"  - desactualizado: {r}")
    return 0


def post_rewrite(root: Path, argv: list[str], stdin: str | None = None) -> int:
    kind = argv[0] if argv else "rewrite"
    data = stdin if stdin is not None else sys.stdin.read()
    for line in data.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        old, new = parts[0], parts[1]
        if find_mirror(root, new) is not None or find_mirror(root, old) is None:
            continue
        mirror_commit(root, f"Reescritura ({kind}): {old[:10]} -> {new[:10]}", new)
    return 0


HANDLERS = {
    "pre-commit": pre_commit,
    "post-commit": post_commit,
    "post-checkout": post_checkout,
    "post-merge": post_merge,
    "post-rewrite": post_rewrite,
}


def register(sub) -> None:
    p = sub.add_parser("hook", help="uso interno de los hooks de git; `graph hook install` los reinstala")
    p.add_argument("nombre", choices=["install", *HOOKS])
    p.add_argument("args", nargs="*")
    p.set_defaults(func=run)


def run(args) -> int:
    try:
        root = find_root(cwd_of(args))
    except NoGraphError:
        if args.nombre == "install":
            raise
        return 0  # repo sin grafo: el hook no hace nada
    if args.nombre == "install":
        if main_toplevel(root) is None:
            raise GraphError("el proyecto no es un repo git")
        print("hooks instalados: " + ", ".join(install(root)))
        return 0
    if not graph_io.index_path(root).exists():
        return 0
    try:
        return HANDLERS[args.nombre](root, list(args.args))
    except GraphError as e:
        print(f"[AVISO] grafo ({args.nombre}): {e}")
        return 0
