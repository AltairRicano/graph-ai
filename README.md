# grafo_ia — Grafo para IA

Contexto de un proyecto de código para agentes de IA, sin duplicar el código en documentación. Los nodos del
grafo son los propios archivos de código; lo que el código no dice vive en un índice markdown por carpeta y
en el estado del proyecto. Pensado para el modo headless.

- Los archivos de código no tienen un documento gemelo: qué hace cada función y por qué va en sus comentarios.
- Cada carpeta tiene un índice en `.graph/` con su propósito, las relaciones entre sus archivos y con otras
  carpetas, y las reglas que cruzan archivos. Un documento por carpeta, tenga 3 archivos o 30.
- `.graph/Estado_Proyecto/` guarda el estado, el plan, las decisiones, las tecnologías y la arquitectura.
- Los `[[enlaces]]` de índices y documentos apuntan a archivos de código reales, a funciones o a otras
  carpetas, y forman un grafo dirigido en `.graph/index.json` (formato node-link de networkx).
- El estado es de la carpeta: un índice queda desactualizado cuando a su carpeta le entran o salen archivos
  o cuando uno de sus enlaces deja de resolver, no cada vez que alguien edita un archivo.
- `graph multiedit` escribe secciones de muchos índices y documentos en una sola llamada a partir de un lote
  de texto plano, pone las fechas y confirma cada uno.
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
graph init                        # vista previa de exclusiones y confirmación
graph status                      # índices por estado
graph get src/pagos --expand      # el índice de una carpeta y los de sus vecinos
graph neighbors src/pagos/cobro.go  # relaciones declaradas de un archivo
graph multiedit <<'LOTE'          # escribe varios índices y los confirma
=== src/pagos#Propósito ===
Cobra los pedidos y deja el asiento que usa facturación.
=== src/pagos#Relaciones ===
- [[src/pagos/cobro.go|cobro.go]] → [[src/db|db]]: cada cobro corre en una sola transacción.
=== Estado_Proyecto/Estado.md#Hecho ===
- Cobro con descuentos.
LOTE
# ... más tarde, tras cambiar el código ...
graph incomplete                  # índices por escribir, cada uno con su motivo
graph diff src/pagos              # archivos que entraron, salieron o cambiaron desde la última confirmación
graph update src/pagos            # confirmar un índice editado a mano
graph ignore '*.csv'              # sacar del grafo lo que no aporta contexto
graph trivial '*.sql'             # dejarlo en el grafo, pero sin pedirle contenido a su carpeta
```

### Lotes de `graph multiedit`

Cada entrada empieza con una línea separadora y sigue con el contenido tal cual, sin escapar nada. El blanco es
una carpeta (su índice) o un documento de `Estado_Proyecto/`, con la ruta desde la raíz del proyecto.

| Separador | Efecto |
| :--- | :--- |
| `=== ruta#sección ===` | Reemplaza esa sección; en un índice la crea si no existe. |
| `=== ruta#sección [append] ===` | Agrega al final de esa sección. |
| `=== ruta ===` | Agrega al final de lo escrito (en un índice, antes de sus listas). |
| `=== ruta [override] ===` | Reemplaza todo lo escrito; en un índice conserva las listas de carpetas y archivos. |

El frontmatter, las listas de carpetas y archivos y las líneas `**Elaboración:** | **Actualización:**` los
mantiene el comando. Antes de leer el lote reconcilia el proyecto, así que las carpetas y archivos nuevos entran
solos al grafo. El lote se valida entero antes de escribir (un error no deja nada a medias) y al final reporta
enlaces por corregir, índices que siguen incompletos e índices más largos que el código de su carpeta. Un archivo
de código no es un blanco válido. Con `-f lote.txt` lee el lote de un archivo y lo borra al aplicarlo (`--keep`
lo conserva).

### Cierre de turno en Claude Code

`graph hook claude-stop` es un hook `Stop`: si una carpeta con código sin commitear tiene su índice faltante o
desactualizado, bloquea el cierre del turno una vez y le dice al agente cuáles son. Es opcional y se declara
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
├── plantillas/          formatos de escritura: índice de carpeta, cada documento de
│                        Estado_Proyecto y reportes de agentes (un archivo por formato)
├── scripts/             instalador multiplataforma (install.py)
├── src/grafo_ia/        paquete Python del CLI: parser, grafo, exclusiones, reconciliación
│   │                    y estados por carpeta
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
