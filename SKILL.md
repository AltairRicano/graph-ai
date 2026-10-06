---
name: grafo-ia
description: Contexto de un proyecto de código guardado en un grafo (.graph/) que se consulta y mantiene con el CLI `graph`. Los nodos son los propios archivos de código (no hay un markdown por archivo); lo que el código no dice vive en un índice por carpeta (para qué sirve el módulo, cómo se relacionan sus archivos, reglas que cruzan archivos) y en Estado_Proyecto/. Al iniciar sesión en un workspace con código basta `graph get Estado_Proyecto/Estado.md` (si responde que no hay .graph, pregunta al usuario si quiere `graph init`) y antes de tocar código `graph get <carpeta>`: para eso no hace falta cargar esta skill. Cárgala (1) justo antes de escribir o actualizar índices por primera vez en la sesión, que suele ser al terminar el código de la primera iteración y antes de responder al usuario; (2) al retomar tras un /compact si ya se escribió código; (3) al crear el grafo de un proyecto o sacar archivos de él. Si su contenido ya está en tu contexto, no la releas.
---

# Grafo para IA (`graph`)

Los **nodos** del grafo son los archivos de código reales, con su ruta como id (`src/pagos/cobro.go`).
No tienen gemelo markdown: qué hace cada función y por qué lo dice el propio código, en sus comentarios.

Lo que el código no puede decir vive en `.graph/`:

- Un **índice** por carpeta, con su mismo nombre (`src/pagos` → `.graph/src/pagos/pagos.md`): un solo
  documento por carpeta, tenga 3 archivos o 30. El de la raíz del proyecto (`.`) es `.graph/Index.md`.
- `.graph/Estado_Proyecto/`: `Estado.md`, `Plan.md`, `Decisiones.md`, `Tecnologias.md` y `Arquitectura.md`.

Los `[[enlaces]]` de índices y documentos forman un grafo dirigido (`.graph/index.json`) que se consulta
con el CLI. El CLI busca el `.graph` más cercano subiendo por los padres (como git). Todos los comandos
reciben **rutas del proyecto** (`src/pagos`, `src/pagos/cobro.go`), nunca rutas dentro de `.graph`. Los
documentos de Estado_Proyecto se nombran con su ruta virtual: `Estado_Proyecto/Plan.md`.

## Dónde va cada cosa

| Lo que hay que dejar escrito | Dónde |
| :--- | :--- |
| Qué hace una función y por qué (la regla, el caso límite, por qué no la forma obvia) | Comentario en el código, junto a la función, al escribirla |
| Para qué sirve un módulo, quién depende de él y cómo se relacionan sus archivos | Índice de la carpeta: `## Propósito` y `## Relaciones` |
| Una regla o flujo que cruza varios archivos de la carpeta | Sección propia (`## nombre`) en el índice de la carpeta |
| Una decisión que cruza carpetas, o con alternativas descartadas | `Estado_Proyecto/Decisiones.md` |
| Qué está hecho, en curso y pendiente | `Estado_Proyecto/Estado.md` |

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
   `init` deja todo armado: un índice por carpeta con sus listas y sus secciones vacías, y los cinco
   documentos de `Estado_Proyecto/` con sus secciones listas para llenar.

### 2. Durante el trabajo: leer y comentar

- **Antes de tocar código en una carpeta**, lee su índice: `graph get src/pagos`, o una sola sección
  con `graph get src/pagos#Relaciones`. Después lee los archivos de código directamente: el índice no
  los resume ni los sustituye.
  - `graph get <carpeta> --expand` trae inline los índices vecinos (un salto);
    `--depth N` sigue hasta N saltos sin repetir lo ya leído.
  - `graph neighbors <archivo o carpeta>` lista las relaciones declaradas en las que aparece, entrantes
    y salientes.
  - `graph search "texto"` o `graph search --filter tipo=decisiones` si no sabes dónde está algo.
- **El porqué de una función se escribe en el código, mientras programas**: un comentario junto a ella
  con la regla o el caso que resuelve. No hay otro lugar para eso ni una pasada posterior para documentar.
- Si moviste o renombraste código: `graph mv <vieja> <nueva>`. Si lo borraste: `graph remove <ruta>`
  o `graph prune`. Estos comandos **solo tocan el grafo**, nunca el código real.
- Si algo no debe estar en el grafo (generado, datos, vendor propio): `graph ignore <patrón>`.

### 3. Al cerrar una iteración: escribir (antes de responder y antes de cada commit)

1. `graph incomplete <rutas tocadas>`: lista los índices por escribir, cada uno con su motivo
   (sin `## Propósito`; archivos que entraron o salieron; enlaces que ya no resuelven). Un archivo como
   ruta pide la carpeta que lo contiene. Con eso basta para saber qué cambió: no hace falta otro comando.
2. Por cada carpeta que tocaste, decide si el cambio altera lo que su índice dice: el propósito, una
   relación o una regla. Si solo cambió el cuerpo de funciones, el índice no se toca.
3. Escribe **todo en un solo `graph multiedit`** (ver abajo): las secciones de índice que cambian y los
   documentos de `Estado_Proyecto/` que correspondan (`Estado.md` siempre; `Plan.md` / `Decisiones.md`
   si aplica). Confirma la sincronía él mismo: no hace falta `graph update` después.
4. Corrige en un segundo lote solo lo que `multiedit` avise (enlaces por corregir, índices que siguen
   incompletos).

**El índice que leíste antes de tocar el código es el mismo que editas al cerrar: no lo releas.** Si no
lo habías leído, pídelo en la misma llamada que el paso 1 (`graph incomplete src/pagos; graph get src/pagos`).

El hook `pre-commit` avisa de lo mismo (y bloquea con `graph config strict on`), pero no escribe nada.

## `graph multiedit`

Un lote de texto plano por stdin, sin escapar nada. Cada entrada es una línea separadora y debajo el
contenido tal cual. El blanco es una **carpeta** (su índice) o un documento de `Estado_Proyecto/`, con
la ruta **desde la raíz del proyecto**:

```bash
graph multiedit <<'LOTE'
=== src/pagos#Propósito ===
Cobra los pedidos y deja el asiento que después usa facturación. Todo lo que mueve dinero pasa por
aquí: si falla, los pedidos se quedan sin cobrar y la factura no se puede emitir.
=== src/pagos#Relaciones ===
- [[src/pagos/cobro.go#calcular_total|calcular_total]] → [[src/pagos/descuentos.go|descuentos.go]]: el descuento se aplica antes del impuesto.
- [[src/pagos/cobro.go|cobro.go]] → [[src/db#Transacciones|db]]: cada cobro corre en una sola transacción.
- [[web/src/api.ts|api.ts]] → [[src/pagos/rutas.go|rutas.go]]: el frontend cobra con `POST /pagos`.
=== src/pagos ===
## Redondeo de centavos
El total se redondea una sola vez, al final de [[src/pagos/cobro.go#calcular_total|calcular_total]];
redondear en cada paso deja diferencias que la factura rechaza.
=== Estado_Proyecto/Estado.md#Hecho ===
- Cobro con descuentos.
LOTE
```

| Separador | Efecto |
| :--- | :--- |
| `=== ruta#sección ===` | Reemplaza esa sección (el contenido va **sin** repetir el heading). En un índice, si no existe se crea como `##`. |
| `=== ruta#sección [append] ===` | Agrega al final de esa sección. |
| `=== ruta ===` | Agrega al final de lo escrito: en un índice, una sección nueva con su `## nombre`, antes de las listas. |
| `=== ruta [override] ===` | Reemplaza todo lo escrito. En un índice se conservan las listas de carpetas y archivos. |

- **Un archivo de código no es un blanco**: se rechaza. Su porqué va en un comentario del propio archivo.
- **No escribas frontmatter ni líneas `**Elaboración:** | **Actualización:**`**: el comando conserva la
  cabecera y pone las fechas de cada sección (mantiene la elaboración, mueve la actualización solo si el
  texto cambió).
- Se valida todo antes de escribir: con un error no se aplica nada y dice qué entrada falló.
- Antes de leer el lote reconcilia el proyecto: las carpetas y archivos nuevos entran solos al grafo y
  las listas quedan al día. No hace falta `graph add`.
- El heredoc con comillas (`<<'LOTE'`) evita que el shell interprete `$`, comillas o backticks. Para un
  lote muy grande, escríbelo a un archivo y pásalo con `graph multiedit -f lote.txt` (lo borra al aplicarlo).
- La salida es una línea de resumen más los avisos: enlaces por corregir, índices del lote que siguen
  incompletos (con su motivo) e índices más largos que el código de su carpeta.

## Catálogo de comandos

| Comando | Qué hace |
| :--- | :--- |
| `graph init [--yes] [--dry-run] [--exclude P] [--no-git]` | Crea o reconcilia `.graph` completo en la carpeta actual. Muestra una vista previa de exclusiones; `--yes` para no preguntar. |
| `graph add [ruta]` | Reconcilia una carpeta (por defecto, la actual): registra los archivos nuevos, crea los índices de las carpetas nuevas y pone al día las listas de los existentes. |
| `graph multiedit [-f lote] [--keep]` | Escribe secciones de varios índices y documentos de un lote (stdin o archivo), pone las fechas y confirma cada uno. Ver [`graph multiedit`](#graph-multiedit). |
| `graph populate [ruta]` | Materializa lo que dice el JSON (índices y sus listas). No sobreescribe contenido. |
| `graph update <ruta>...` | Confirma índices y documentos editados a mano (`multiedit` ya lo hace): guarda qué archivos tiene la carpeta, regenera las aristas y mueve `fecha_actualizacion`. No acepta archivos de código. |
| `graph diff [carpetas]` | Qué cambió en la carpeta desde la última confirmación de su índice: archivos que entraron (`+`), salieron (`-`) y se modificaron (`~`). Sin rutas: todas las que tienen cambios. |
| `graph ignore [patrón...] [--remove] [--force]` | Sin argumentos lista las exclusiones. Con patrones los agrega a `.graph/exclude` y saca del grafo lo excluido. `--remove` los quita y reconcilia. |
| `graph trivial [patrón...] [--remove]` | Sin argumentos lista los patrones de `.graph/trivial`; con patrones los agrega o quita. |
| `graph remove <ruta>` | Saca del grafo un archivo o carpeta; los enlaces que lo apuntaban se quedan como texto plano. |
| `graph prune [ruta]` | Borra los índices huérfanos (carpetas que ya no existen) y los nodos de archivos borrados. |
| `graph mv <vieja> <nueva>` | Mueve/renombra en el grafo y reescribe todas las menciones (solo la ruta). |
| `graph rename <carpeta>#<sección> <nuevo> [--links-only]` | Renombra un heading y reescribe los enlaces que lo apuntan. `--links-only` si ya lo renombraste a mano. |
| `graph relate <origen> <destino> [--add R] [--remove R]` | Muestra o edita el tipo de relación de una arista existente. |
| `graph get <ruta>[#sección] [--expand] [--depth N]` | Contenido de un índice o documento, o de una sección; con `--expand`/`--depth`, también el de sus vecinos. Sobre un archivo de código responde que se lee directo. |
| `graph neighbors <ruta>[#sección] [--in\|--out]` | De un archivo: las líneas `origen → destino` en las que aparece, en cualquier índice, y qué documentos lo mencionan. De una carpeta o documento: además, sus enlaces salientes y entrantes. |
| `graph subgraph <ruta> [--depth N] [--json]` | Todo lo que hay a N saltos. |
| `graph search [texto] [--filter campo=valor] [--regex]` | Búsqueda en índices y documentos; cada resultado dice su sección. |
| `graph status` | Conteo de índices por estado, chequeo grafo↔HEAD y estado del Watcher. |
| `graph incomplete [rutas]` | Índices por escribir, por prioridad y con su motivo: desactualizados, faltantes, enlaces pendientes, huérfanos y demasiado largos. Los triviales no salen. |
| `graph doctor` | Integridad estructural del JSON (sale con 1 si hay daño). |
| `graph config strict [on\|off]` | Modo estricto: `pre-commit` bloquea en vez de avisar. |
| `graph watch start\|stop\|status` | Watcher en tiempo real (extra `watch`). |
| `graph hook install` | Reinstala los hooks de git. |
| `graph hook claude-stop` | Hook `Stop` para Claude Code: bloquea una vez el cierre del turno si una carpeta con código sin commitear tiene su índice faltante o desactualizado. Se declara a mano en `settings.json`. |

Códigos de salida: `0` bien, `1` hallazgos que bloquean (pre-commit estricto, doctor), `2` error de uso o precondición.

Patrones de `ignore` / `.graph/exclude`: nombre suelto = en cualquier nivel (admite comodines,
`*.csv`); con `/` = desde la raíz (`/generado` es solo la `generado` de la raíz, `src/generado` esa ruta).
Siempre excluidos: carpetas ocultas (salvo `.github`), dependencias/build, `agentes/` en la raíz,
archivos sensibles, lockfiles y binarios. Además, `graph init` escribe en `.graph/exclude` unas reglas
iniciales que cada proyecto puede quitar con `graph ignore --remove <patrón>`: documentación, licencias,
pruebas y plantillas (`graph ignore` las lista). Distinguen mayúsculas, como toda regla propia.

## Estados de un índice

El estado es de la carpeta, no de cada archivo.

- **ok**: tiene `## Propósito` y la carpeta tiene los mismos archivos que cuando se confirmó.
- **desactualizado**: desde la última confirmación a la carpeta le entraron o salieron archivos (un
  renombre es las dos cosas), un enlace del índice apunta a un archivo o función que ya no existe, o el
  índice se escribió a mano y nunca se confirmó.
  **Editar el cuerpo de un archivo no lo desactualiza**: decidir si ese cambio altera lo que el índice
  dice es el paso 2 del cierre. El hash de cada archivo se guarda solo para que `graph diff` diga cuáles cambiaron.
- **faltante**: el índice no existe o su `## Propósito` está vacío.
- **trivial**: sin propósito, pero la carpeta no tiene archivos propios que lo pidan: ninguno (solo
  subcarpetas) o todos caen en `.graph/trivial`. Cuenta como completa.
- **huérfano**: el índice sigue, pero la carpeta ya no existe (`graph prune`).
- **pendiente por crear** (en enlaces): un `[[...]]` apunta a algo que todavía no existe (típico desde Plan).

### Triviales

`graph init` deja en `.graph/trivial` unos patrones iniciales (`*.css`, `*.json`, `*.toml`, `*.yaml`,
`.gitignore`, ...) con la misma sintaxis que `exclude`. Un archivo que cae en uno sigue en el grafo y se
puede enlazar, pero no cuenta para pedirle contenido a su carpeta: una carpeta de puros triviales
**no es un faltante: no la llenes**, salvo que ahí viva una decisión que alguien necesitará.

## Convenciones de escritura (obligatorias)

- **El índice cuenta lo que no se ve leyendo un solo archivo.** No resume archivo por archivo, no
  parafrasea el código y no lleva el avance del trabajo.
- **`## Relaciones` lleva una línea por relación**: `- [[origen]] → [[destino]]: por qué`. Solo las que
  explican el módulo: de qué depende fuera de la carpeta, quién lo usa, y las que un import no muestra
  (una llamada HTTP, una tabla o un evento compartido, un orden obligado). Los imports evidentes dentro
  de la carpeta no se listan.
- **Todo enlace lleva texto a mostrar** y la ruta desde la raíz del proyecto:
  - a un archivo de código: `[[src/db/conexion.go|conexion.go]]`;
  - a una función de un archivo: `[[src/db/conexion.go#conectar|conectar]]` (se comprueba que el
    nombre siga apareciendo en el archivo, en cualquier lenguaje);
  - a una carpeta (su índice) o a una sección de él: `[[src/db|db]]`, `[[src/db#Transacciones|transacciones]]`;
  - a un documento: `[[Estado_Proyecto/Decisiones.md#uso_de_hash|uso_de_hash]]`.

  También se acepta solo el final de la ruta si es único.
- **Nunca edites las listas `📁 Carpetas` / `📄 Archivos` de un índice**: las mantiene el CLI.
- **No declares el tipo de relación en la prosa**; se asigna con `graph relate` (taxonomía: `importa`,
  `utiliza`, `implementa`, `hereda_de`, `extiende`, `sobreescribe`, `compone`, `conoce`, `informativa`).
  Toda arista nueva nace como `conoce`.
- Los headings son direccionables con `ruta#heading`: evita headings repetidos dentro de un mismo índice.
- Una sección abarca hasta el siguiente heading de igual o mayor nivel.

### Plantillas

Para un índice basta esta página: su formato es el del ejemplo de [`graph multiedit`](#graph-multiedit).
Los documentos de `Estado_Proyecto/` ya nacen con sus secciones y una línea que dice qué va en cada una.
Las plantillas de `plantillas/` (junto a este archivo) traen las reglas finas de cada formato. **Lee una
solo si dudas, la primera vez que la uses; si ya está en tu contexto, no la releas**:

| Vas a escribir | Plantilla |
| :--- | :--- |
| El índice de una carpeta | `plantillas/indice.md` |
| `Estado_Proyecto/Estado.md` | `plantillas/estado.md` |
| `Estado_Proyecto/Plan.md` | `plantillas/plan.md` |
| `Estado_Proyecto/Decisiones.md` | `plantillas/decisiones.md` |
| `Estado_Proyecto/Tecnologias.md` | `plantillas/tecnologias.md` |
| `Estado_Proyecto/Arquitectura.md` | `plantillas/arquitectura.md` |
| Un reporte de subagente en `agentes/` | `plantillas/reporte_agente.md` |

## Qué no hace

- No redacta índices: nacen con sus secciones vacías. Lo mecánico sí es suyo: la cabecera, las listas
  de carpetas y archivos y las fechas.
- No deduce relaciones leyendo imports: las de `## Relaciones` son las que alguien escribió.
- No detecta que un cambio dentro de un archivo dejó viejo lo que dice el índice: solo avisa por
  archivos que entran o salen y por enlaces que dejan de resolver.
- No convierte en arista los enlaces `📁 Carpetas`/`📄 Archivos` de un índice: son estructura, no relación.
- De un enlace `archivo#función` solo comprueba que el nombre aparezca en el archivo, no que sea una función.
- `.graph` es un repo git anidado **sin remoto**: personal por máquina, nunca se sube. Ahí viven
  también las instantáneas de `graph diff`; sin git no hay instantáneas.
