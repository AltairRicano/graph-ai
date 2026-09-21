---
name: grafo-ia
description: Grafo bidireccional de gemelos markdown (.graph/) que guarda el contexto de un proyecto de código fuera del código. Úsalo cuando el proyecto tenga una carpeta .graph (o el usuario pida crearla) para leer contexto antes de tocar código (graph get / neighbors / search), para documentar lo que cambiaste en el gemelo y confirmarlo con graph update, y para revisar sincronía con graph status / incomplete. Ojo: para listar el contenido de una carpeta usa siempre `graph get <carpeta>`, nunca `graph neighbors <carpeta>` — los enlaces de un índice son estructurales por diseño y jamás generan arista, así que `neighbors`/`subgraph` sobre una carpeta devuelven 0 aunque el índice tenga archivos.
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

## Flujo de trabajo del agente

1. **Antes de tocar código**, lee el contexto:
   - `graph get src/pagos/cobro.go` (gemelo completo) o `graph get src/pagos/cobro.go#calcular_total` (una sección).
   - `graph get <ruta> --expand` trae inline el contenido de los vecinos: un solo viaje.
   - `graph neighbors <ruta>[#sección]` para saber quién depende de qué — **solo sirve sobre
     archivos de código o documentos, nunca sobre una carpeta**: el índice de una carpeta
     (`tipo: indice`) lista sus archivos como enlaces estructurales, que por diseño nunca son
     arista (ver "Qué no hace"), así que `neighbors`/`subgraph` sobre una carpeta siempre
     devuelven 0 aunque el índice tenga contenido. Para listar lo que hay en una carpeta usa
     `graph get <carpeta>` en su lugar.
   - `graph search "texto"` o `graph search --filter tipo=decisiones` si no sabes dónde está algo.
   - `graph get Estado_Proyecto/Estado.md` para saber dónde está parado el proyecto.
2. **Después de cambiar código**, actualiza el gemelo de cada archivo tocado (formato abajo) y confirma:
   `graph update <ruta>`. Es el único mecanismo para marcar un gemelo como al día; falla si el gemelo está vacío.
   `update` mueve solo la `fecha_actualizacion` del frontmatter; las fechas `**Actualización:**` de cada
   sección son independientes y las actualizas tú cuando cambias esa sección.
3. **Antes de terminar**, `graph status` (resumen) o `graph incomplete` (listas). Resuelve los
   `faltante` y `desactualizado` de lo que tocaste.
4. Si agregaste archivos o carpetas y el Watcher no corre: `graph add <carpeta>` (crea nodos y cáscaras vacías).
5. Si moviste o renombraste código: `graph mv <vieja> <nueva>` (reescribe los enlaces). Si borraste código:
   `graph remove <ruta>` o `graph prune`. Estos comandos **solo tocan el grafo**, nunca el código real.

## Catálogo de comandos

| Comando | Qué hace |
| :--- | :--- |
| `graph init [--yes] [--exclude P] [--no-git]` | Crea o reconcilia `.graph` completo en la carpeta actual. Muestra una vista previa de exclusiones; `--yes` para no preguntar. |
| `graph add [ruta]` | Reconcilia una carpeta (por defecto, la actual) y crea sus cáscaras. |
| `graph populate [ruta]` | Materializa lo que dice el JSON (índices, gemelos vacíos). No sobreescribe contenido. |
| `graph update <ruta>` | Confirma sincronía: guarda el hash del código, regenera las aristas del gemelo y pone `fecha_actualizacion` del header en hoy. Con `Estado_Proyecto/X.md`, regenera aristas y mueve la fecha (no hay hash). |
| `graph remove <ruta>` | Saca del grafo un archivo o carpeta; los enlaces que lo apuntaban se quedan como texto plano. |
| `graph prune [ruta]` | Borra los gemelos huérfanos (código que ya no existe). |
| `graph mv <vieja> <nueva>` | Mueve/renombra en el grafo y reescribe todas las menciones (solo la ruta). |
| `graph rename <ruta>#<sección> <nuevo> [--links-only]` | Renombra un heading y reescribe los enlaces que lo apuntan. `--links-only` si ya lo renombraste a mano. |
| `graph relate <origen> <destino> [--add R] [--remove R]` | Muestra o edita el tipo de relación de una arista existente. |
| `graph get <ruta>[#sección] [--expand]` | Contenido del gemelo o de una sección. |
| `graph neighbors <ruta>[#sección] [--in\|--out]` | Vecinos entrantes y salientes. |
| `graph subgraph <ruta> [--depth N] [--json]` | Todo lo que hay a N saltos. |
| `graph search [texto] [--filter campo=valor] [--regex]` | Búsqueda en gemelos; cada resultado dice su sección. |
| `graph status` | Conteo por estado, chequeo grafo↔HEAD y estado del Watcher. |
| `graph incomplete [rutas]` | Listas: faltantes, desactualizados, pendientes por crear, huérfanos. |
| `graph doctor` | Integridad estructural del JSON (sale con 1 si hay daño). |
| `graph config strict [on\|off]` | Modo estricto: `pre-commit` bloquea en vez de avisar. |
| `graph watch start\|stop\|status` | Watcher en tiempo real (extra `watch`). |
| `graph hook install` | Reinstala los hooks de git. |

Códigos de salida: `0` bien, `1` hallazgos que bloquean (pre-commit estricto, doctor), `2` error de uso o precondición.

## Estados de un archivo de código

- **ok**: el gemelo tiene contenido y el hash del código coincide con el confirmado.
- **desactualizado**: el código cambió desde el último `graph update`.
- **faltante**: el gemelo no existe o solo tiene frontmatter.
- **huérfano**: el gemelo sigue, pero el código ya no existe (`graph prune`).
- **pendiente por crear** (en enlaces): un `[[...]]` apunta a algo que todavía no existe (típico desde Plan).

## Convenciones de escritura (obligatorias)

- **Todo enlace lleva texto a mostrar:** `[[src/db.go.md#conectar|conectar]]`. La forma canónica es el id
  completo (ruta dentro de `.graph`, con `.md`). También se acepta sin `.md` o solo el final de la ruta si es único.
- **Nunca edites las listas `📁 Carpetas` / `📄 Archivos` de un índice**: las mantiene `populate`.
- **No declares el tipo de relación en la prosa**; se asigna con `graph relate` (taxonomía: `importa`,
  `utiliza`, `implementa`, `hereda_de`, `extiende`, `sobreescribe`, `compone`, `conoce`, `informativa`).
  Toda arista nueva nace como `conoce`.
- Los headings son direccionables con `ruta#heading`: evita headings repetidos dentro de un mismo gemelo.
- Una sección abarca hasta el siguiente heading de igual o mayor nivel.

### Gemelo de código (`<archivo>.md`)

```markdown
---
tipo: codigo
fecha_elaboracion: AAAA-MM-DD
fecha_actualizacion: AAAA-MM-DD
---
Descripción corta pero detallada de por qué existe el archivo (se alarga solo si hay mucha lógica de negocio).

---

## Funciones

### calcular_total
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

Mínima si es trivial; específica y con enlaces a las funciones relacionadas si es lógica de negocio,
por ejemplo [[src/pagos/descuentos.go.md#aplicar_descuento|aplicar_descuento]].

### Carrito.agregar
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

Los métodos van como `Clase.metodo`, todos al mismo nivel.
```

### Documentos de Estado_Proyecto

- **Estado.md**: fotografía del ahora, se sobreescribe (Hecho / En curso / Falta / Siguientes pasos). Sin fechas por ítem.
- **Plan.md**: `## seccion_snake & Nombre Legible` → `### bloque` → `- [ ] tarea`. Al completar un bloque, se mueve
  entero al final bajo `## Completado` con `**Sección de origen:**` y `**Cerrado:** AAAA-MM-DD`.
- **Decisiones.md**: `## titulo_en_snake_case`, fechas, `**Carpetas que afecta:**` (índices o archivos, o nada si es global).
- **Tecnologias.md**: `## nombre_snake & Nombre Legible` por tecnología en uso; lo descartado se borra.
- **Arquitectura.md**: `## Hardware`, `## Tecnología`, `## Componentes` con sub-headings fechados.

Tras editar uno de ellos, `graph update Estado_Proyecto/<Doc>.md` regenera sus aristas.

### Reportes de agentes (carpeta `agentes/`)

Cuando se lanza una flota de subagentes (Agent tool) en paralelo, cada agente que **audite,
investigue o reporte hallazgos sin editar código directamente** escribe su propio archivo en
`agentes/` (carpeta real en la raíz del proyecto, fuera de `.graph`) — nunca un agente
consolidador que resuma a los demás: se pierde contexto en ese resumen.

Convención de archivo: `agentes/<fecha>_<nombre-agente>_<id-agente>.md`, por ejemplo
`agentes/2026-09-21_code-reviewer_a3f91c.md`. Frontmatter:

```markdown
---
agente: code-reviewer
id: a3f91c
fecha: AAAA-MM-DD
tarea: auditoria
---
```

El cuerpo es el contenido pertinente de esa tarea completo (el hallazgo, la auditoría, el
análisis), no un resumen truncado — la razón de escribirlo en disco en vez de solo devolverlo en
la respuesta es la misma que para `Estado_Proyecto/`: reportes que se cortan a medias por límite
de contexto.

Al terminar: `graph add agentes/` (primera vez) y `graph update agentes/<archivo>.md`, como
cualquier gemelo de código (`tipo: codigo` normal — `agentes/` no usa un tipo especial).

Un agente de **corrección** (que edita un archivo real del proyecto) no necesita este archivo
extra: le basta con editar el archivo y correr `graph update <ruta>` sobre su propio gemelo — el
diff y el gemelo actualizado ya documentan el cambio.

`agentes/` es operativo, no producto: cada proyecto que lo use debe agregarlo a su
`.gitignore`, igual que `.graph/`.

## Qué no hace

- No escribe contenido de gemelos por sí solo: las cáscaras nacen vacías y el contenido lo escribe el agente o una persona
  (la única excepción es la `fecha_actualizacion` del header, que mueve `graph update`).
- `remove`, `mv` y `prune` no tocan el código real.
- No convierte en arista los enlaces `📁 Carpetas`/`📄 Archivos` de un índice: son estructurales
  por diseño (evita ensuciar `neighbors`/`subgraph` con la obviedad de "este archivo vive en esta
  carpeta", que ya se lee en la ruta). `graph neighbors`/`graph subgraph` sobre una carpeta
  devuelven siempre 0 vecinos — usa `graph get <carpeta>` para ver su listado real.
- `.graph` es un repo git anidado **sin remoto**: personal por máquina, nunca se sube.
