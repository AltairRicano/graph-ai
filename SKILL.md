---
name: grafo-ia-gemelos
description: Versión anterior de grafo-ia (un gemelo markdown por archivo). Úsala solo en proyectos cuyo `.graph` contiene `index.json`; en los demás aplica la skill `grafo-ia`. Contexto de un proyecto de código guardado fuera del código, en un grafo de gemelos markdown (.graph/) que se consulta y mantiene con el CLI `graph`. Al iniciar sesión en un workspace con código basta `graph get Estado_Proyecto/Estado.md` (si responde que no hay .graph, pregunta al usuario si quiere `graph init`) y antes de tocar código `graph get <ruta>` / `graph neighbors <ruta>`: para eso no hace falta cargar esta skill. Cárgala (1) justo antes de escribir o actualizar gemelos por primera vez en la sesión, que suele ser al terminar el código de la primera iteración y antes de responder al usuario; (2) al retomar tras un /compact si ya se escribió código; (3) al crear el grafo de un proyecto o sacar archivos de él. Si su contenido ya está en tu contexto, no la releas.
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
   `init` deja todo armado: los gemelos con su cabecera, los índices completos y los cinco documentos de
   `Estado_Proyecto/` con sus secciones listas para llenar.

### 2. Durante el trabajo: leer

- **Antes de tocar código**, lee el contexto:
  - `graph get src/pagos/cobro.go` (gemelo completo) o `graph get src/pagos/cobro.go#calcular_total` (una sección).
  - `graph get <ruta> --expand` trae inline el contenido de los vecinos (un salto);
    `graph get <ruta> --depth N` sigue hasta N saltos por secciones sin repetir lo ya leído.
  - `graph neighbors <ruta>[#sección]` para saber quién depende de qué. Solo sobre archivos y
    documentos: sobre una carpeta responde que es una carpeta. Para ver lo que contiene una carpeta,
    `graph get <carpeta>` (su índice).
  - `graph search "texto"` o `graph search --filter tipo=decisiones` si no sabes dónde está algo.
- **Si acabas de escribir el código, no lo releas** para documentarlo: ya lo tienes en contexto. Reléelo
  solo ante una duda puntual.
- Si moviste o renombraste código: `graph mv <vieja> <nueva>`. Si lo borraste: `graph remove <ruta>`
  o `graph prune`. Estos comandos **solo tocan el grafo**, nunca el código real.
- Si algo no debe estar en el grafo (generado, datos, vendor propio): `graph ignore <patrón>`.

### 3. Al cerrar una iteración: escribir (antes de responder y antes de cada commit)

No documentes archivo por archivo mientras programas. Al terminar el código de la iteración:

1. `graph incomplete <rutas tocadas>`: sale por prioridad, primero **desactualizados**, después
   **faltantes**. Los archivos triviales (ver [Triviales](#triviales)) no aparecen: no los llenes.
2. Por cada desactualizado, `graph diff <ruta> --symbols` dice qué funciones cambiaron: son las
   secciones a reescribir.
3. Escribe **todo en un solo `graph multiedit`** (ver abajo): gemelos nuevos, secciones cambiadas y los
   documentos de `Estado_Proyecto/` que correspondan (`Estado.md` siempre; `Plan.md` / `Decisiones.md`
   si aplica). Confirma la sincronía él mismo: no hace falta `graph update` después.
4. Corrige en un segundo lote lo que `multiedit` avise (enlaces rotos, funciones sin sección).

El hook `pre-commit` avisa de lo mismo (y bloquea con `graph config strict on`), pero no escribe nada.

## `graph multiedit`

Un lote de texto plano por stdin, sin escapar nada. Cada entrada es una línea separadora y debajo el
contenido tal cual, con las rutas **desde la raíz del proyecto**:

```bash
graph multiedit <<'LOTE'
=== src/pagos/cobro.go ===
Por qué existe el archivo, en corto.

---

## Funciones

### calcular_total
**Qué hace:** suma los renglones, aplica [[src/pagos/descuentos.go.md#aplicar_descuento|aplicar_descuento]] y el impuesto.

**Por qué existe:** el descuento va antes del impuesto porque así lo exige la facturación.
=== src/pagos/descuentos.go#aplicar_descuento ===
**Qué hace:** ...

**Por qué existe:** ...
=== Estado_Proyecto/Estado.md#Hecho ===
- Cobro con descuentos.
LOTE
```

| Separador | Efecto |
| :--- | :--- |
| `=== ruta ===` | Agrega al final del cuerpo. En un gemelo vacío es escribirlo completo. |
| `=== ruta [override] ===` | Reemplaza el cuerpo completo. |
| `=== ruta#sección ===` | Reemplaza esa sección (el contenido va **sin** repetir el heading). En un gemelo de código, si la sección no existe se crea como `###` dentro de `## Funciones`. |
| `=== ruta#sección [append] ===` | Agrega al final de esa sección. |

- **No escribas frontmatter ni líneas `**Elaboración:** | **Actualización:**`**: el comando conserva la
  cabecera y pone las fechas (mantiene la elaboración, mueve la actualización solo si el texto cambió).
- Se valida todo antes de escribir: con un error no se aplica nada y dice qué entrada falló.
- Agregar (`=== ruta ===`) a un gemelo **desactualizado** se rechaza: usa `ruta#sección` u `[override]`.
- Un archivo de código nuevo que aún no está en el grafo se agrega solo (no hace falta `graph add`).
- El heredoc con comillas (`<<'LOTE'`) evita que el shell interprete `$`, comillas o backticks. Para un
  lote muy grande, escríbelo a un archivo y pásalo con `graph multiedit -f lote.txt` (lo borra al aplicarlo).
- La salida es una línea de resumen más los avisos: enlaces por corregir, secciones desalineadas con el
  código y gemelos más largos que su código (señal de que toca consolidar con `[override]`).

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
| `graph add [ruta]` | Reconcilia una carpeta o archivo (por defecto, la carpeta actual): crea solo los gemelos (con su cabecera) e índices de lo nuevo y pone al día los índices existentes. |
| `graph multiedit [-f lote] [--keep]` | Escribe el cuerpo de varios gemelos de un lote (stdin o archivo), pone las fechas y confirma la sincronía de cada uno. Ver [`graph multiedit`](#graph-multiedit). |
| `graph populate [ruta]` | Materializa lo que dice el JSON (índices, gemelos vacíos). No sobreescribe contenido. |
| `graph update <ruta>...` | Para gemelos editados a mano (`multiedit` ya lo hace). Acepta varios archivos, no carpetas. Confirma sincronía: guarda el hash y una instantánea del código (para `diff`), regenera las aristas del gemelo y pone `fecha_actualizacion` del header en hoy. Avisa si las funciones no cuadran con las secciones. Con `Estado_Proyecto/X.md`, regenera aristas y mueve la fecha. |
| `graph diff [rutas] [--symbols]` | Qué cambió en el código desde el último `update` y qué funciones tocó (modificadas, nuevas, eliminadas). Sin rutas: todos los desactualizados. `--symbols`: solo las secciones a revisar. |
| `graph ignore [patrón...] [--remove] [--force]` | Sin argumentos lista las exclusiones. Con patrones los agrega a `.graph/exclude` y saca del grafo lo excluido (sin `--force` no borra gemelos con contenido). `--remove` los quita y reconcilia. |
| `graph trivial [patrón...] [--remove]` | Sin argumentos lista los patrones de `.graph/trivial`; con patrones los agrega o quita. No toca gemelos. |
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
| `graph incomplete [rutas]` | Listas por prioridad: desactualizados, faltantes, secciones desalineadas, pendientes por crear, huérfanos, y gemelos más largos que su código. Los triviales vacíos no salen. |
| `graph doctor` | Integridad estructural del JSON (sale con 1 si hay daño). |
| `graph config strict [on\|off]` | Modo estricto: `pre-commit` bloquea en vez de avisar. |
| `graph watch start\|stop\|status` | Watcher en tiempo real (extra `watch`). |
| `graph hook install` | Reinstala los hooks de git. |
| `graph hook claude-stop` | Hook `Stop` para Claude Code: bloquea el cierre del turno si el código sin commitear tiene gemelos faltantes o desactualizados (una sola vez por cierre). Se declara a mano en `settings.json`. |

Códigos de salida: `0` bien, `1` hallazgos que bloquean (pre-commit estricto, doctor), `2` error de uso o precondición.

Patrones de `ignore` / `.graph/exclude`: nombre suelto = en cualquier nivel (admite comodines,
`*.csv`); con `/` = desde la raíz (`/generado` es solo la `generado` de la raíz, `src/generado` esa ruta).
Siempre excluidos: carpetas ocultas (salvo `.github`), dependencias/build, `agentes/` en la raíz,
archivos sensibles, lockfiles y binarios. Además, `graph init` escribe en `.graph/exclude` unas reglas
iniciales que cada proyecto puede quitar (a mano o con `graph ignore --remove <patrón>`):
documentación (`*.md`, `*.markdown`, `*.rst`, `docs`, `doc`), licencias (`LICENSE*`, `COPYING*`,
`NOTICE*`), pruebas (`tests`, `test`, `__tests__`, `test_*.py`, `*_test.py`, `*_test.go`, `*.test.*`,
`*.spec.*`) y plantillas (`plantillas`, `templates`). Distinguen mayúsculas, como toda regla propia.

## Estados de un archivo de código

- **ok**: el gemelo tiene contenido y el hash del código coincide con el confirmado.
- **desactualizado**: el código cambió desde el último `graph update` (`graph diff` dice qué).
- **faltante**: el gemelo no existe o solo tiene frontmatter.
- **trivial**: gemelo vacío de un archivo que cae en `.graph/trivial`. Cuenta como completo.
- **huérfano**: el gemelo sigue, pero el código ya no existe (`graph prune`).
- **pendiente por crear** (en enlaces): un `[[...]]` apunta a algo que todavía no existe (típico desde Plan).

Aparte de los estados, **desalineado** es un aviso: en Python y Go, una función del código sin `###`
en `## Funciones`, o un `###` cuya función ya no existe. Otros lenguajes no se chequean.

### Triviales

Hay archivos que no tienen un porqué que contar (estilos, configuración, archivos de herramientas).
`graph init` deja en `.graph/trivial` unos patrones iniciales (`*.css`, `*.json`, `*.toml`, `*.yaml`,
`.gitignore`, ...) con la misma sintaxis que `exclude`. Un archivo que cae en uno sigue en el grafo y se
puede enlazar, pero su gemelo vacío **no es un faltante: no lo llenes**. Escríbele contenido solo si ahí
vive una decisión que alguien necesitará; desde entonces sigue las reglas normales del hash.
Para todo lo demás, el largo del gemelo va con el del código: uno más largo que su archivo se avisa.

## Convenciones de escritura (obligatorias)

- **Cada función (`###`) dice qué hace y por qué existe** a nivel de lógica de negocio: el porqué es
  lo que el código no dice y lo que más vale del gemelo (detalle en `plantillas/gemelo_codigo.md`).
- **Todo enlace lleva texto a mostrar:** `[[src/db.go.md#conectar|conectar]]`. La forma canónica es el id
  completo (ruta dentro de `.graph`, con `.md`). También se acepta sin `.md` o solo el final de la ruta si es único.
- **Nunca edites las listas `📁 Carpetas` / `📄 Archivos` de un índice**: las mantiene `populate`.
- **No declares el tipo de relación en la prosa**; se asigna con `graph relate` (taxonomía: `importa`,
  `utiliza`, `implementa`, `hereda_de`, `extiende`, `sobreescribe`, `compone`, `conoce`, `informativa`).
  Toda arista nueva nace como `conoce`.
- Los headings son direccionables con `ruta#heading`: evita headings repetidos dentro de un mismo gemelo.
- Una sección abarca hasta el siguiente heading de igual o mayor nivel.

### Plantillas

El formato del gemelo de código es el del ejemplo de [`graph multiedit`](#graph-multiedit): descripción,
`---`, `## Funciones` y un `###` por función (los métodos como `Clase.metodo`) con **Qué hace** y
**Por qué existe**. Los documentos de `Estado_Proyecto/` ya nacen con sus secciones y una línea que dice
qué va en cada una: se llenan por sección (`=== Estado_Proyecto/Estado.md#Hecho ===`).

Las plantillas de `plantillas/` (junto a este archivo) traen las reglas finas de cada formato. **Lee solo
la que vas a usar, la primera vez que la uses; si ya está en tu contexto, no la releas**:

| Vas a escribir | Plantilla |
| :--- | :--- |
| El gemelo de un archivo de código | `plantillas/gemelo_codigo.md` |
| `Estado_Proyecto/Estado.md` | `plantillas/estado.md` |
| `Estado_Proyecto/Plan.md` | `plantillas/plan.md` |
| `Estado_Proyecto/Decisiones.md` | `plantillas/decisiones.md` |
| `Estado_Proyecto/Tecnologias.md` | `plantillas/tecnologias.md` |
| `Estado_Proyecto/Arquitectura.md` | `plantillas/arquitectura.md` |
| Un reporte de subagente en `agentes/` | `plantillas/reporte_agente.md` |

## Qué no hace

- No redacta gemelos: las cáscaras nacen vacías y el contenido lo escribe el agente o una persona. Lo mecánico
  sí es suyo: la cabecera, los índices y las fechas (del header y de cada sección) las ponen `init`, `add`,
  `multiedit` y `update`.
- `remove`, `mv`, `prune` e `ignore` no tocan el código real.
- No convierte en arista los enlaces `📁 Carpetas`/`📄 Archivos` de un índice: son estructurales por diseño
  (la pertenencia a una carpeta ya se lee en la ruta). Por eso `neighbors`/`subgraph` no aplican a carpetas.
- No chequea funciones fuera de Python y Go.
- `.graph` es un repo git anidado **sin remoto**: personal por máquina, nunca se sube. Ahí viven
  también las instantáneas de `graph diff`; sin git no hay instantáneas.
