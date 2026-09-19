# grafo_ia — Grafo para IA

Grafo bidireccional de gemelos markdown para dar contexto a agentes de IA sobre un proyecto de código,
sin ensuciar el código con comentarios extensos. Inspirado en el grafo de Obsidian, pensado para el modo headless.

- Cada archivo tiene un gemelo `.md` en `.graph/` y cada carpeta un índice.
- Los `[[enlaces]]` entre gemelos forman un grafo dirigido en `.graph/index.json` (formato node-link de networkx).
- La sincronía se detecta por hash del contenido (no por fecha), con cuatro estados: ok, desactualizado, faltante y huérfano.
- `.graph` es un repo git anidado sin remoto, alineado con el repo de código mediante hooks.

El manual de uso (catálogo de comandos y formatos) está en [SKILL.md](SKILL.md).

## Instalación

Requiere Python 3.10+ y git. Clona el repo donde guardas tus repos y corre el instalador:

```bash
git clone https://github.com/AltairRicano/graph-ai.git ~/repos/graph
cd ~/repos/graph
./graph install                    # Windows: graph.cmd install
```

`./graph install` hace tres cosas:

1. Crea un entorno virtual propio en `.venv/` dentro del repo (con `uv` si lo tienes, si no con `venv` + `pip`)
   e instala `grafo_ia` en modo editable con el extra `watch` (`watchdog`, `psutil`).
2. Pone el comando `graph` en tu PATH: un symlink en `~/.local/bin/graph` (Windows: `graph.cmd` en
   `%USERPROFILE%\.local\bin`). Si ahí ya hay un `graph` que no es este, no lo pisa sin `--force`.
   Te avisa si la carpeta no está en tu PATH, o si otro `graph` (por ejemplo el de GNU plotutils) le gana.
3. **No instala la Skill por defecto**, porque cada agente tiene su propia forma de instalarlas. Te imprime la ruta
   de `SKILL.md`. Si quieres enlazarla, pasa la carpeta de skills de tu agente:

```bash
./graph install --skill-dir ~/.claude/skills      # Claude Code: enlaza el repo como ~/.claude/skills/grafo-ia
```

Opciones: `--bin-dir DIR` (otra carpeta para el comando), `--python RUTA` (otro intérprete), `--no-watch`
(sin Watcher), `--force`.

**Actualizar:** `git pull` en el repo. Al ser editable, no hace falta reinstalar salvo que cambien las dependencias
(correr `./graph install` otra vez es seguro).

**Desinstalar:** `./graph uninstall [--skill-dir DIR] [--purge]`. `--purge` borra también el `.venv/` del repo.
Los `.graph` de tus proyectos no se tocan.

Desde el repo, `./graph <comando>` también funciona sin tener nada en el PATH: delega al CLI del `.venv/`.

Para desarrollo: `uv venv && uv pip install -e '.[test]'`.

## Uso rápido

```bash
cd mi-proyecto
graph init            # vista previa de exclusiones y confirmación
graph status
graph get src/main.go --expand
# ... escribir el gemelo .graph/src/main.go.md ...
graph update src/main.go
```

## Pruebas

```bash
.venv/bin/python -m pytest
```

El CI corre la matriz de Linux, macOS y Windows (`.github/workflows/tests.yml`).

## Licencia

Apache 2.0. Ver [LICENSE](LICENSE).
