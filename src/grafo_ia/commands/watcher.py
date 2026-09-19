"""Watcher: el único componente que corre de forma continua (uno por proyecto).

`graph watch start|stop|status`. El proceso de fondo (`graph watch run`) guarda
`pid` + hora de arranque en `.graph/watcher.pid`; comparar la hora evita
confundirlo con otro proceso que reutilizó el pid.

Eventos (agrupados en ráfagas de ~0.75 s):
- movido: `mv` directo, sin heurística;
- creado/borrado: reconcilia la carpeta padre y `populate`;
- gemelo modificado: regenera sus aristas;
- código modificado: nada (el estado se calcula por hash).
`WatchProcessor.process()` es puro respecto a watchdog: se prueba con eventos simulados.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from grafo_ia import graph_io
from grafo_ia.commands._common import root_of
from grafo_ia.edges import TwinCache, regenerate
from grafo_ia.errors import GraphError
from grafo_ia.exclusion import EXCLUIR, Exclusion
from grafo_ia.paths import GRAPH_DIR, code_id, folder_id, graph_dir, is_under, parent_rel, to_rel

PID_FILE = "watcher.pid"
LOG_FILE = "watcher.log"
DEBOUNCE = 0.75
GRAPH_INTERNAL = {"index.json", "index.lock", PID_FILE, LOG_FILE, "config", "exclude", ".gitignore"}


@dataclass
class Event:
    kind: str  # created | deleted | moved | modified
    src: str  # ruta absoluta
    dest: str | None = None
    is_dir: bool = False


def _is_editor_temp(name: str) -> bool:
    return (
        name.endswith("~") or name.startswith(".#") or name.startswith(".grafo-")
        or name.endswith((".swp", ".swx", ".swo", ".tmp")) or ".mv-" in name or name == "4913"
    )


class WatchProcessor:
    def __init__(self, root: Path):
        self.root = Path(root)

    def classify(self, path: str, is_dir: bool) -> tuple[str, str]:
        """-> ("ignore" | "code" | "twin", ruta relativa o id)."""
        try:
            rel = to_rel(self.root, path, self.root)
        except GraphError:
            return "ignore", ""
        if not rel:
            return "ignore", ""
        parts = rel.split("/")
        if parts[0] == ".git" or _is_editor_temp(parts[-1]):
            return "ignore", rel
        if parts[0] == GRAPH_DIR:
            sub = rel[len(GRAPH_DIR) + 1:]
            if not sub or sub.split("/")[0] == ".git" or sub in GRAPH_INTERNAL or sub.startswith("index.json") or not sub.endswith(".md") or is_dir:
                return "ignore", sub
            return "twin", sub
        verdict, _ = Exclusion(self.root, sniff_binary=False).check(rel, is_dir)
        if verdict == EXCLUIR:
            return "ignore", rel
        return "code", rel

    def process(self, events: list[Event]) -> dict:
        moves: list[tuple[str, str, bool]] = []
        scopes: set[str] = set()
        twins: set[str] = set()
        for ev in events:
            if ev.kind == "moved" and ev.dest:
                s_kind, s_rel = self.classify(ev.src, ev.is_dir)
                d_kind, d_rel = self.classify(ev.dest, ev.is_dir)
                if s_kind == "code" and d_kind == "code":
                    moves.append((s_rel, d_rel, ev.is_dir))
                elif s_kind == "code":
                    scopes.add(parent_rel(s_rel))
                elif d_kind == "code":
                    scopes.add(parent_rel(d_rel))
                if d_kind == "twin":  # guardado atómico de un editor: tmp -> gemelo
                    twins.add(d_rel)
            elif ev.kind in ("created", "deleted"):
                kind, rel = self.classify(ev.src, ev.is_dir)
                if kind == "code":
                    scopes.add(parent_rel(rel))
                elif kind == "twin" and ev.kind == "created":
                    twins.add(rel)
            elif ev.kind == "modified":
                kind, rel = self.classify(ev.src, ev.is_dir)
                if kind == "twin":
                    twins.add(rel)
        result = {"moved": {}, "reconciled": [], "regenerated": []}
        if not (moves or scopes or twins):
            return result
        from grafo_ia.commands.mv import build_mapping, ensure_index_chain, move_nodes, validate_mapping
        from grafo_ia.commands.populate import populate
        from grafo_ia.reconciliation import reconcile

        cache = TwinCache(self.root)
        structural = False
        with graph_io.transaction(self.root) as graph:
            for old, new, is_dir in moves:
                kind = None
                if code_id(old) in graph.nodes and graph.tipo(code_id(old)) == "codigo":
                    kind = "codigo"
                elif folder_id(old) in graph.nodes:
                    kind = "indice"
                if kind is None:
                    scopes.add(parent_rel(new))
                    continue
                mapping = build_mapping(graph, old, new, kind)
                try:
                    validate_mapping(self.root, graph, mapping)
                except GraphError:
                    scopes.update({parent_rel(old), parent_rel(new)})
                    continue
                ensure_index_chain(graph, parent_rel(new))
                move_nodes(self.root, graph, mapping, cache)
                result["moved"].update(mapping)
                structural = True
            # alcances anidados: basta con el más externo
            ordered = sorted(scopes, key=len)
            final: list[str] = []
            for s in ordered:
                if not any(is_under(s, f) for f in final):
                    final.append(s)
            for s in final:
                changes = reconcile(self.root, graph, s, cache=cache)
                if not changes.empty:
                    structural = True
                result["reconciled"].append(s)
            for t in sorted(twins):
                if t in graph.nodes:
                    cache.forget(t)
                    added, removed = regenerate(graph, cache, t)
                    if added or removed:
                        result["regenerated"].append(t)
            if structural:
                populate(self.root, graph)
        return result


# ---- ciclo de vida -----------------------------------------------------------
def _pid_path(root: Path) -> Path:
    return graph_dir(root) / PID_FILE


def _need_psutil():
    try:
        import psutil
    except ImportError:
        raise GraphError("el Watcher necesita el extra `watch`: pip install 'grafo-ia[watch]'")
    return psutil


def read_pid(root: Path) -> tuple[int, float] | None:
    p = _pid_path(root)
    try:
        pid_s, started_s = p.read_text(encoding="utf-8").split()[:2]
        return int(pid_s), float(started_s)
    except (OSError, ValueError):
        return None


def running(root: Path) -> tuple[int, float] | None:
    """(pid, hora de arranque) si el Watcher de este proyecto está vivo."""
    info = read_pid(root)
    if info is None:
        return None
    try:
        psutil = _need_psutil()
    except GraphError:
        return None
    pid, started = info
    try:
        proc = psutil.Process(pid)
        if abs(proc.create_time() - started) > 1.0 or not proc.is_running():
            return None
        if proc.status() == psutil.STATUS_ZOMBIE:
            return None
    except psutil.Error:
        return None
    return info


def describe(root: Path) -> str:
    info = running(root)
    if info is None:
        return "detenido"
    return f"corriendo desde {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info[1]))} (pid {info[0]})"


def start(root: Path, timeout: float = 10.0) -> tuple[int, float]:
    _need_psutil()
    info = running(root)
    if info:
        return info
    cmd = [sys.executable, "-m", "grafo_ia", "-C", str(root), "watch", "run"]
    log = open(graph_dir(root) / LOG_FILE, "ab")
    kwargs: dict = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL, "cwd": str(root)}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)
    log.close()
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = running(root)
        if info:
            return info
        time.sleep(0.1)
    raise GraphError(f"el Watcher no arrancó; revisa {GRAPH_DIR}/{LOG_FILE}")


def stop(root: Path, timeout: float = 10.0) -> bool:
    psutil = _need_psutil()
    info = running(root)
    if info is None:
        _pid_path(root).unlink(missing_ok=True)
        return False
    try:
        proc = psutil.Process(info[0])
        proc.terminate()
        try:
            proc.wait(timeout)
        except psutil.TimeoutExpired:
            proc.kill()
    except psutil.Error:
        pass
    _pid_path(root).unlink(missing_ok=True)
    return True


def run_forever(root: Path, stop_event: threading.Event | None = None) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        raise GraphError("el Watcher necesita el extra `watch`: pip install 'grafo-ia[watch]'")
    psutil = _need_psutil()
    me = psutil.Process(os.getpid())
    _pid_path(root).write_text(f"{os.getpid()} {me.create_time()}\n", encoding="utf-8")
    stop_event = stop_event or threading.Event()

    def _bye(*_):
        stop_event.set()

    signal.signal(signal.SIGTERM, _bye)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _bye)

    from grafo_ia.commands.populate import populate
    from grafo_ia.reconciliation import reconcile, summary

    # al arrancar: recoger lo que cambió mientras estuvo apagado
    with graph_io.transaction(root) as graph:
        changes = reconcile(root, graph, "")
        populate(root, graph)
    print(f"[watcher] {summary(changes)}", flush=True)

    events: "queue.Queue[Event]" = queue.Queue()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: D401
            kind = event.event_type
            if kind not in ("created", "deleted", "moved", "modified"):
                return
            events.put(Event(kind, os.fsdecode(event.src_path), os.fsdecode(getattr(event, "dest_path", "") or "") or None, event.is_directory))

    observer = Observer()
    observer.schedule(Handler(), str(root), recursive=True)
    observer.start()
    processor = WatchProcessor(root)
    try:
        while not stop_event.is_set():
            try:
                first = events.get(timeout=0.5)
            except queue.Empty:
                continue
            batch = [first]
            while True:
                try:
                    batch.append(events.get(timeout=DEBOUNCE))
                except queue.Empty:
                    break
            try:
                res = processor.process(batch)
                if res["moved"] or res["reconciled"] or res["regenerated"]:
                    print(f"[watcher] {res}", flush=True)
            except Exception as e:  # noqa: BLE001 - el Watcher no debe morir por un lote
                print(f"[watcher] error procesando lote: {e!r}", flush=True)
    finally:
        observer.stop()
        observer.join(timeout=5)
        info = read_pid(root)
        if info and info[0] == os.getpid():
            _pid_path(root).unlink(missing_ok=True)


def register(sub) -> None:
    p = sub.add_parser("watch", help="Watcher en tiempo real: start | stop | status")
    p.add_argument("accion", choices=["start", "stop", "status", "run"])
    p.set_defaults(func=run)


def run(args) -> int:
    root = root_of(args)
    if args.accion == "start":
        pid, started = start(root)
        print(f"watcher: corriendo (pid {pid})")
    elif args.accion == "stop":
        print("watcher: detenido" if stop(root) else "watcher: no estaba corriendo")
    elif args.accion == "status":
        print(f"watcher: {describe(root)}")
    else:
        run_forever(root)
    return 0
