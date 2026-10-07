# grafo_ia — Grafo para IA (versión de gemelos)

> Esta rama conserva la versión anterior, para los proyectos que ya tienen un `.graph` con gemelos. La versión
> vigente está en `main`: guarda solo el estado del proyecto y, cuando encuentra un `.graph` de este formato,
> le pasa cada comando a `graph-gemelos`, que es el `graph` de esta rama puesto en el PATH con ese nombre.

Grafo bidireccional de gemelos markdown para dar contexto a agentes de IA sobre un proyecto de código,
sin ensuciar el código con comentarios extensos. Inspirado en el grafo de Obsidian, pensado para el modo headless.

- Cada archivo tiene un gemelo `.md` en `.graph/` y cada carpeta un índice.
- Los `[[enlaces]]` entre gemelos forman un grafo dirigido en `.graph/index.json` (formato node-link de networkx).
- La sincronía se detecta por hash del contenido (no por fecha), con cinco estados: ok, desactualizado, faltante,
  trivial y huérfano.
- `graph multiedit` escribe el cuerpo de muchos gemelos en una sola llamada a partir de un lote de texto plano,
  pone las fechas y confirma la sincronía de cada uno.
- Los archivos triviales (estilos, configuración) siguen en el grafo pero no piden contenido: `.graph/trivial`.
- `.graph` es un repo git anidado sin remoto, alineado con el repo de código mediante hooks.
- Al confirmar un gemelo se guarda una instantánea del código: `graph diff` muestra qué cambió desde
  entonces y qué funciones tocó, y en Python y Go se avisa cuando las secciones del gemelo ya no cuadran
  con las funciones del código.

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
graph multiedit <<'LOTE'          # escribe varios gemelos y los confirma
=== src/main.go ===
Punto de entrada del servicio.
=== src/pagos/cobro.go#calcular_total ===
**Qué hace:** ... **Por qué existe:** ...
LOTE
# ... más tarde, tras cambiar el código ...
graph incomplete                  # desactualizados primero, luego faltantes
graph diff src/main.go --symbols  # qué funciones cambiaron desde la última confirmación
graph update src/a.go src/b.go    # confirmar gemelos editados a mano
graph ignore '*.csv'              # sacar del grafo lo que no aporta contexto
graph trivial '*.sql'             # dejarlo en el grafo, pero sin pedirle contenido
```

### Lotes de `graph multiedit`

Cada entrada empieza con una línea separadora y sigue con el contenido tal cual, sin escapar nada.
Las rutas van desde la raíz del proyecto.

| Separador | Efecto |
| :--- | :--- |
| `=== ruta ===` | Agrega al final del cuerpo (en un gemelo vacío, lo escribe completo). |
| `=== ruta [override] ===` | Reemplaza el cuerpo completo. |
| `=== ruta#sección ===` | Reemplaza esa sección; en un gemelo de código la crea bajo `## Funciones` si no existe. |
| `=== ruta#sección [append] ===` | Agrega al final de esa sección. |

El frontmatter y las líneas `**Elaboración:** | **Actualización:**` los mantiene el comando. El lote se valida
entero antes de escribir (un error no deja nada a medias), agrega al grafo los archivos nuevos que mencione y
al final reporta enlaces rotos, funciones sin sección y gemelos más largos que su código. Agregar a un gemelo
desactualizado se rechaza: hay que reescribir la sección que cambió o usar `[override]`. Con `-f lote.txt` lee
el lote de un archivo y lo borra al aplicarlo (`--keep` lo conserva).

### Cierre de turno en Claude Code

`graph hook claude-stop` es un hook `Stop`: si el código con cambios sin commitear tiene gemelos faltantes o
desactualizados, bloquea el cierre del turno una vez y le dice al agente cuáles son. Es opcional y se declara
en `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "graph hook claude-stop" }] }]
  }
}
```

## Estructura del repositorio

```
graph-ai/
├── .github/workflows/   CI: pruebas e instalador en Linux, macOS y Windows
├── plantillas/          formatos de escritura: gemelo de código, cada documento de
│                        Estado_Proyecto y reportes de agentes (un archivo por formato)
├── scripts/             instalador multiplataforma (install.py)
├── src/grafo_ia/        paquete Python del CLI: parser, grafo, exclusiones, estados,
│   │                    instantáneas y cruce de funciones con secciones
│   ├── commands/        un módulo por subcomando (init, multiedit, update, diff, ignore, ...)
│   └── templates/       cáscaras de Estado_Proyecto que crea `graph init`
├── tests/               pruebas con pytest
├── graph, graph.cmd     lanzadores del repo (POSIX y Windows)
├── SKILL.md             manual de uso: flujo, catálogo de comandos y convenciones
└── pyproject.toml       metadatos del paquete y extras (watch, nx, test)
```

## Pruebas

```bash
.venv/bin/python -m pytest
```

El CI corre la matriz de Linux, macOS y Windows (`.github/workflows/tests.yml`).

## Licencia

Apache 2.0. Ver [LICENSE](LICENSE).
