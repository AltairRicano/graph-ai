"""Instalador de grafo_ia: `./graph install` / `./graph uninstall`.

Pensado para clonar el repo donde uno guarda sus repos (por ejemplo
`~/repos/graph`) e instalar desde ahí:

1. Crea un entorno virtual propio en `<repo>/.venv` (con `uv` si está, si no con
   `venv` + `pip`) e instala el paquete en modo editable. No tiene dependencias.
   Editable: un `git pull` basta para actualizar.
2. Pone el comando `graph` en el PATH del usuario: un symlink en `~/.local/bin`
   (POSIX) o un `graph.cmd` en `%USERPROFILE%\\.local\\bin` (Windows). Nunca pisa
   un `graph` ajeno sin `--force`.
3. La Skill no se instala por defecto: cada agente tiene su forma. Con
   `--skill-dir <carpeta de skills>` se enlaza el repo ahí como `grafo-ia`; sin
   la bandera se imprime la ruta de `SKILL.md` y cómo hacerlo en Claude Code.

Solo biblioteca estándar: corre con el Python del sistema, antes de que exista
el entorno virtual.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENV = REPO / ".venv"
SKILL_NAME = "grafo-ia"
MIN_PY = (3, 10)
WINDOWS = sys.platform == "win32"


class InstallError(Exception):
    pass


def say(msg: str) -> None:
    print(msg, flush=True)


# ---- rutas -------------------------------------------------------------------
def default_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def venv_python(venv: Path = VENV) -> Path:
    return venv / ("Scripts/python.exe" if WINDOWS else "bin/python")


def venv_entry(venv: Path = VENV) -> Path:
    return venv / ("Scripts/graph.exe" if WINDOWS else "bin/graph")


def launcher_path(bin_dir: Path) -> Path:
    return bin_dir / ("graph.cmd" if WINDOWS else "graph")


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


# ---- 1. entorno virtual ------------------------------------------------------
def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise InstallError(f"falló: {' '.join(cmd)}\n{r.stdout}{r.stderr}")


def ensure_venv(python: str) -> None:
    target = str(REPO)
    uv = shutil.which("uv")
    if uv:
        if not venv_python().exists():
            say(f"· creando entorno virtual con uv en {VENV}")
            run([uv, "venv", "-q", "--python", python, str(VENV)])
        say("· instalando grafo_ia (editable) con uv")
        run([uv, "pip", "install", "-q", "--python", str(venv_python()), "-e", target])
        return
    if not venv_python().exists():
        say(f"· creando entorno virtual en {VENV}")
        r = subprocess.run([python, "-m", "venv", str(VENV)], capture_output=True, text=True)
        if r.returncode != 0:
            raise InstallError(
                "no se pudo crear el entorno virtual. En Debian/Ubuntu instala `python3-venv`, "
                f"o instala `uv` (https://docs.astral.sh/uv/).\n{r.stderr}"
            )
    vpy = str(venv_python())
    if subprocess.run([vpy, "-m", "pip", "--version"], capture_output=True).returncode != 0:
        run([vpy, "-m", "ensurepip", "--upgrade"])
    say("· instalando grafo_ia (editable) con pip")
    run([vpy, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-e", target])


# ---- 2. comando en el PATH ---------------------------------------------------
def _is_ours(launcher: Path, entry: Path) -> bool:
    if launcher.is_symlink():
        return _same(launcher, entry)
    if WINDOWS and launcher.is_file():
        return str(entry) in launcher.read_text(encoding="utf-8", errors="replace")
    return False


def check_launcher_free(bin_dir: Path, entry: Path, force: bool = False) -> None:
    """Falla antes de instalar nada si hay un `graph` ajeno en `bin_dir`."""
    launcher = launcher_path(bin_dir)
    if (launcher.exists() or launcher.is_symlink()) and not _is_ours(launcher, entry) and not force:
        raise InstallError(f"ya existe {launcher} y no es de grafo_ia; usa --force para reemplazarlo o --bin-dir para otra carpeta")


def install_launcher(bin_dir: Path, entry: Path, force: bool = False) -> Path:
    check_launcher_free(bin_dir, entry, force)
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = launcher_path(bin_dir)
    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()
    if WINDOWS:
        launcher.write_text(f'@"{entry}" %*\r\n', encoding="utf-8")
    else:
        launcher.symlink_to(entry)
    return launcher


def path_warnings(bin_dir: Path, launcher: Path) -> list[str]:
    out = []
    dirs = [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if not any(_same(d, bin_dir) for d in dirs):
        if WINDOWS:
            out.append(f"{bin_dir} no está en tu PATH. Agrégalo en Variables de entorno del usuario.")
        else:
            out.append(f"{bin_dir} no está en tu PATH. Agrega a tu ~/.bashrc o ~/.zshrc:\n    export PATH=\"{bin_dir}:$PATH\"")
    else:
        found = shutil.which("graph")
        if found and not _same(Path(found), launcher) and not _same(Path(found), venv_entry()):
            out.append(f"`graph` en tu PATH resuelve a {found}, que no es grafo_ia (¿GNU plotutils?). "
                       f"Pon {bin_dir} antes en el PATH.")
    return out


# ---- 3. skill ----------------------------------------------------------------
def install_skill(skill_dir: Path, force: bool = False) -> Path:
    skill_dir.mkdir(parents=True, exist_ok=True)
    link = skill_dir / SKILL_NAME
    if link.is_symlink() or link.exists():
        if _same(link, REPO):
            return link
        if not force:
            raise InstallError(f"ya existe {link}; usa --force para reemplazarlo")
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            shutil.rmtree(link)
    try:
        link.symlink_to(REPO, target_is_directory=True)
    except OSError:  # Windows sin permiso de symlinks: copia solo el manual
        link.mkdir()
        shutil.copy2(REPO / "SKILL.md", link / "SKILL.md")
        say("  (sin permiso para symlinks: se copió SKILL.md; tras un `git pull`, vuelve a correr install)")
    return link


def skill_hint() -> str:
    return (
        f"Skill: el manual está en {REPO / 'SKILL.md'}. Instálala según tu agente, por ejemplo:\n"
        f"    ./graph install --skill-dir ~/.claude/skills      # Claude Code (enlaza el repo como '{SKILL_NAME}')\n"
        f"    ln -s {REPO} <carpeta-de-skills-de-tu-agente>/{SKILL_NAME}"
    )


# ---- comandos ----------------------------------------------------------------
def cmd_install(args) -> int:
    if not args.python and sys.version_info < MIN_PY:
        raise InstallError(f"se necesita Python {'.'.join(map(str, MIN_PY))}+ (este es {sys.version.split()[0]}); usa --python")
    check_launcher_free(args.bin_dir, venv_entry(), args.force)
    ensure_venv(args.python or sys.executable)
    entry = venv_entry()
    if not entry.exists():
        raise InstallError(f"no apareció {entry} tras instalar")
    launcher = install_launcher(args.bin_dir, entry, args.force)
    version = subprocess.run([str(entry), "--version"], capture_output=True, text=True).stdout.strip()
    say(f"✓ {version} instalado; comando: {launcher}")
    if args.skill_dir:
        link = install_skill(args.skill_dir, args.force)
        say(f"✓ skill enlazada: {link}")
    else:
        say(skill_hint())
    for w in path_warnings(args.bin_dir, launcher):
        say(f"[AVISO] {w}")
    say("Para actualizar: `git pull` en el repo.")
    return 0


def cmd_uninstall(args) -> int:
    launcher = launcher_path(args.bin_dir)
    if launcher.exists() or launcher.is_symlink():
        if _is_ours(launcher, venv_entry()) or args.force:
            launcher.unlink()
            say(f"✓ quitado {launcher}")
        else:
            say(f"[AVISO] {launcher} no es de grafo_ia; no se toca")
    if args.skill_dir:
        link = args.skill_dir / SKILL_NAME
        if link.is_symlink() and _same(link, REPO):
            link.unlink()
            say(f"✓ quitada la skill {link}")
        elif link.is_dir() and (link / "SKILL.md").exists() and not link.is_symlink():
            shutil.rmtree(link)
            say(f"✓ quitada la skill {link}")
    if args.purge and VENV.exists():
        shutil.rmtree(VENV)
        say(f"✓ borrado {VENV}")
    say("Los `.graph` de tus proyectos no se tocan.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="./graph", description="Instala o desinstala grafo_ia desde este repo.")
    sub = p.add_subparsers(dest="accion", required=True)
    for name in ("install", "uninstall"):
        s = sub.add_parser(name)
        s.add_argument("--bin-dir", type=lambda x: Path(x).expanduser(), default=default_bin_dir(),
                       help=f"dónde poner el comando `graph` (por defecto {default_bin_dir()})")
        s.add_argument("--skill-dir", type=lambda x: Path(x).expanduser(),
                       help="carpeta de skills de tu agente (ej. ~/.claude/skills); se enlaza el repo como grafo-ia")
        s.add_argument("--force", action="store_true", help="reemplazar un `graph` o una skill que ya existan")
        if name == "install":
            s.add_argument("--python", help="intérprete para el entorno virtual (por defecto, el que corre esto)")
        else:
            s.add_argument("--purge", action="store_true", help="borrar también el entorno virtual del repo")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return cmd_install(args) if args.accion == "install" else cmd_uninstall(args)
    except InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
