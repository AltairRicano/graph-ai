---
name: grafo-ia
description: Contexto de un proyecto de código guardado fuera del código, en un grafo de gemelos markdown (.graph/) que se consulta y mantiene con el CLI `graph`. Dispárala (1) al iniciar una sesión nueva en un workspace que no esté vacío - si hay .graph, lee solo Estado_Proyecto/Estado.md y Tecnologias.md; si no hay, pregunta al usuario si quiere crearlo con `graph init`; (2) antes de cada commit, para poner al día los gemelos de lo que se commitea (`graph incomplete`, `graph diff`, `graph update`); (3) al terminar cada sesión o fase de trabajo, para verificar el estado (`graph status`, `graph incomplete`) y actualizar Estado_Proyecto; (4) antes de tocar código en un proyecto con .graph, para leer el gemelo y sus vecinos (`graph get`, `graph neighbors`); (5) cuando haya que sacar archivos o carpetas del grafo (`graph ignore`).
---

# Grafo para IA (`graph`)

Cada archivo del proyecto tiene un **gemelo** markdown dentro de `.graph/`, en la misma ruta más `.md`
(`src/main.go` → `.graph/src/main.go.md`). Cada carpeta tiene un **índice** con su mismo nombre
(`src/features` → `.graph/src/features/features.md`); el maestro es `.graph/Index.md`.
`.graph/Estado_Proyecto/` guarda `Estado.md`, `Plan.md`, `Decisiones.md`, `Tecnologias.md` y `Arquitectura.md`.
Los `[[enlaces]]` entre gemelos forman un grafo dirigido (`.graph/index.json`) que se consulta con el CLI.

El CLI busca el `.graph` más cercano subiendo por los padres (como git). Todos los comandos reciben
**rutas del proyecto** (`src/main.go`, `src/features`), nunca rutas dentro de `.graph`. Los documentos de
Estado_Proyecto se nombran con su ruta virtual: `Estado_Proyecto/Plan.md`.

## Instalación

Si `graph` no está en el PATH: clonar https://github.com/AltairRicano/graph-ai (por ejemplo en `~/repos/graph`) y correr `./graph install`
desde ahí (`graph.cmd install` en Windows). Detalles en el README.

## Disparadores

### 1. Al iniciar una sesión nueva

1. Si el workspace está vacío (sin archivos, o solo `.git`), no hay nada que hacer.
2. Si no lo está, `graph get Estado_Proyecto/Estado.md`: además de leer el estado, confirma que existe
   el grafo. Después, `graph get Estado_Proyecto/Tecnologias.md`. **Nada más**: el resto se lee bajo
   demanda, cuando la tarea lo pida.
3. Si responde `no hay .graph`, **pregunta al usuario** si quiere crearlo. Si acepta:
   `graph init --dry-run` (vista previa de lo que entra y lo que se excluye) y luego `graph init --yes`.

### 2. Antes de cada commit

1. `graph incomplete <rutas que vas a commitear>`. Sale en orden de prioridad: primero
   **desactualizados**, después **faltantes**.
2. Por cada desactualizado: `graph diff <ruta> --symbols` dice qué funciones cambiaron; actualiza esas
   secciones del gemelo y confirma con `graph update <ruta>`.
3. Por cada faltante: escribe el gemelo (ver [Plantillas](#plantillas)) y `graph update <ruta>`.

El hook `pre-commit` avisa de lo mismo (y bloquea con `graph config strict on`), pero no escribe nada.

### 3. Al terminar la sesión o una fase

1. `graph status` y `graph incomplete`: resuelve lo que tocaste (desactualizados, faltantes,
   secciones desalineadas).
2. Actualiza `Estado_Proyecto/Estado.md` (y `Plan.md` / `Decisiones.md` si aplica) y corre
   `graph update Estado_Proyecto/<Doc>.md` por cada uno.

### 4. Durante el trabajo

- **Antes de tocar código**, lee el contexto:
  - `graph get src/pagos/cobro.go` (gemelo completo) o `graph get src/pagos/cobro.go#calcular_total` (una sección).
  - `graph get <ruta> --expand` trae inline el contenido de los vecinos (un salto);
    `graph get <ruta> --depth N` sigue hasta N saltos por secciones sin repetir lo ya leído.
  - `graph neighbors <ruta>[#sección]` para saber quién depende de qué. Solo sobre archivos y
    documentos: sobre una carpeta responde que es una carpeta. Para ver lo que contiene una carpeta,
    `graph get <carpeta>` (su índice).
  - `graph search "texto"` o `graph search --filter tipo=decisiones` si no sabes dónde está algo.
- **Después de cambiar código**, actualiza el gemelo de cada archivo tocado y confirma con
  `graph update <ruta>`. Es el único mecanismo para marcar un gemelo como al día; falla si el gemelo
  está vacío y avisa si sus `###` no cuadran con las funciones del código.
- Si agregaste archivos o carpetas y el Watcher no corre: `graph add <carpeta>`.
- Si moviste o renombraste código: `graph mv <vieja> <nueva>`. Si lo borraste: `graph remove <ruta>`
  o `graph prune`. Estos comandos **solo tocan el grafo**, nunca el código real.
- Si algo no debe estar en el grafo (generado, datos, vendor propio): `graph ignore <patrón>`.

## Navegación manual: duplicados

Si encadenas consultas a mano, vas a ver lo mismo más de una vez: `graph neighbors a.go` muestra
`b.go`, y `graph neighbors b.go` te devuelve `a.go`. Eso es un **duplicado**, no contexto nuevo.
Lleva registro de lo que ya leíste por **sección** (`ruta#sección`), no solo por archivo:

- Ir y volver entre dos archivos por **secciones distintas** (`a#uno → b#dos → a#cuatro`) sí es contexto nuevo.
- Volver a una sección ya leída, o saltar al **archivo completo** de uno ya leído, es un duplicado:
  corta ahí esa rama y sigue con las demás.

`graph get <ruta> --depth N` aplica esta regla por ti y al final dice cuántos saltos omitió.

## Catálogo de comandos

| Comando | Qué hace |
| :--- | :--- |
| `graph init [--yes] [--dry-run] [--exclude P] [--no-git]` | Crea o reconcilia `.graph` completo en la carpeta actual. Muestra una vista previa de exclusiones; `--yes` para no preguntar. |
| `graph add [ruta]` | Reconcilia una carpeta (por defecto, la actual) y crea sus cáscaras. |
| `graph populate [ruta]` | Materializa lo que dice el JSON (índices, gemelos vacíos). No sobreescribe contenido. |
| `graph update <ruta>` | Confirma sincronía: guarda el hash y una instantánea del código (para `diff`), regenera las aristas del gemelo y pone `fecha_actualizacion` del header en hoy. Avisa si las funciones no cuadran con las secciones. Con `Estado_Proyecto/X.md`, regenera aristas y mueve la fecha. |
| `graph diff [rutas] [--symbols]` | Qué cambió en el código desde el último `update` y qué funciones tocó (modificadas, nuevas, eliminadas). Sin rutas: todos los desactualizados. `--symbols`: solo las secciones a revisar. |
| `graph ignore [patrón...] [--remove] [--force]` | Sin argumentos lista las exclusiones. Con patrones los agrega a `.graph/exclude` y saca del grafo lo excluido (sin `--force` no borra gemelos con contenido). `--remove` los quita y reconcilia. |
| `graph remove <ruta>` | Saca del grafo un archivo o carpeta; los enlaces que lo apuntaban se quedan como texto plano. |
| `graph prune [ruta]` | Borra los gemelos huérfanos (código que ya no existe). |
| `graph mv <vieja> <nueva>` | Mueve/renombra en el grafo y reescribe todas las menciones (solo la ruta). |
| `graph rename <ruta>#<sección> <nuevo> [--links-only]` | Renombra un heading y reescribe los enlaces que lo apuntan. `--links-only` si ya lo renombraste a mano. |
| `graph relate <origen> <destino> [--add R] [--remove R]` | Muestra o edita el tipo de relación de una arista existente. |
| `graph get <ruta>[#sección] [--expand] [--depth N]` | Contenido del gemelo o de una sección; con `--expand`/`--depth`, también el de sus vecinos. |
| `graph neighbors <ruta>[#sección] [--in\|--out]` | Vecinos entrantes y salientes (no aplica a carpetas). |
| `graph subgraph <ruta> [--depth N] [--json]` | Todo lo que hay a N saltos, por archivo (no aplica a carpetas). |
| `graph search [texto] [--filter campo=valor] [--regex]` | Búsqueda en gemelos; cada resultado dice su sección. |
| `graph status` | Conteo por estado, secciones desalineadas, chequeo grafo↔HEAD y estado del Watcher. |
| `graph incomplete [rutas]` | Listas por prioridad: desactualizados, faltantes, secciones desalineadas, pendientes por crear, huérfanos. |
| `graph doctor` | Integridad estructural del JSON (sale con 1 si hay daño). |
| `graph config strict [on\|off]` | Modo estricto: `pre-commit` bloquea en vez de avisar. |
| `graph watch start\|stop\|status` | Watcher en tiempo real (extra `watch`). |
| `graph hook install` | Reinstala los hooks de git. |

Códigos de salida: `0` bien, `1` hallazgos que bloquean (pre-commit estricto, doctor), `2` error de uso o precondición.

Patrones de `ignore` / `.graph/exclude`: nombre suelto = en cualquier nivel (admite comodines,
`*.csv`); con `/` = desde la raíz (`/generado` es solo la `generado` de la raíz, `src/generado` esa ruta).
Siempre excluidos: carpetas ocultas (salvo `.github`), dependencias/build, `agentes/` en la raíz,
archivos sensibles, lockfiles, binarios, documentación (`.md`, `.markdown`, `.rst`, `docs/`, `doc/`),
licencias (`LICENSE`, `COPYING`, `NOTICE`), pruebas (`tests/`, `test/`, `__tests__/`, `test_*.py`,
`*_test.py`, `*_test.go`, `*.test.*`, `*.spec.*`) y plantillas (`plantillas/`, `templates/`).

## Estados de un archivo de código

- **ok**: el gemelo tiene contenido y el hash del código coincide con el confirmado.
- **desactualizado**: el código cambió desde el último `graph update` (`graph diff` dice qué).
- **faltante**: el gemelo no existe o solo tiene frontmatter.
- **huérfano**: el gemelo sigue, pero el código ya no existe (`graph prune`).
- **pendiente por crear** (en enlaces): un `[[...]]` apunta a algo que todavía no existe (típico desde Plan).

Aparte de los estados, **desalineado** es un aviso: en Python y Go, una función del código sin `###`
en `## Funciones`, o un `###` cuya función ya no existe. Otros lenguajes no se chequean.

## Convenciones de escritura (obligatorias)

- **Todo enlace lleva texto a mostrar:** `[[src/db.go.md#conectar|conectar]]`. La forma canónica es el id
  completo (ruta dentro de `.graph`, con `.md`). También se acepta sin `.md` o solo el final de la ruta si es único.
- **Nunca edites las listas `📁 Carpetas` / `📄 Archivos` de un índice**: las mantiene `populate`.
- **No declares el tipo de relación en la prosa**; se asigna con `graph relate` (taxonomía: `importa`,
  `utiliza`, `implementa`, `hereda_de`, `extiende`, `sobreescribe`, `compone`, `conoce`, `informativa`).
  Toda arista nueva nace como `conoce`.
- Los headings son direccionables con `ruta#heading`: evita headings repetidos dentro de un mismo gemelo.
- Una sección abarca hasta el siguiente heading de igual o mayor nivel.

### Plantillas

Cada formato tiene su plantilla en `plantillas/` (junto a este archivo). **Lee solo la que vas a usar,
en el momento de usarla**:

| Vas a escribir | Lee |
| :--- | :--- |
| El gemelo de un archivo de código | `plantillas/gemelo_codigo.md` |
| `Estado_Proyecto/Estado.md` | `plantillas/estado.md` |
| `Estado_Proyecto/Plan.md` | `plantillas/plan.md` |
| `Estado_Proyecto/Decisiones.md` | `plantillas/decisiones.md` |
| `Estado_Proyecto/Tecnologias.md` | `plantillas/tecnologias.md` |
| `Estado_Proyecto/Arquitectura.md` | `plantillas/arquitectura.md` |
| Un reporte de subagente en `agentes/` | `plantillas/reporte_agente.md` |

## Qué no hace

- No escribe contenido de gemelos por sí solo: las cáscaras nacen vacías y el contenido lo escribe el agente o una persona
  (la única excepción es la `fecha_actualizacion` del header, que mueve `graph update`).
- `remove`, `mv`, `prune` e `ignore` no tocan el código real.
- No convierte en arista los enlaces `📁 Carpetas`/`📄 Archivos` de un índice: son estructurales por diseño
  (la pertenencia a una carpeta ya se lee en la ruta). Por eso `neighbors`/`subgraph` no aplican a carpetas.
- No chequea funciones fuera de Python y Go.
- `.graph` es un repo git anidado **sin remoto**: personal por máquina, nunca se sube. Ahí viven
  también las instantáneas de `graph diff`; sin git no hay instantáneas.
