---
name: grafo-ia
description: Estado de un proyecto de código guardado en `.graph/Estado_Proyecto/` (Estado, Plan, Decisiones, Tecnologías, Arquitectura), que se lee y se escribe con el CLI `graph`. Cárgala solo en tres casos: (1) al iniciar sesión si el proyecto ya tiene .graph, junto con `graph get Estado_Proyecto/Estado.md`; (2) al terminar una iteración completa, justo antes de escribir el estado y antes de responder, salvo que ya la hayas leído en la sesión; (3) cuando el usuario lo pide. En un proyecto sin .graph no la cargues al empezar: haz el trabajo y cárgala al cerrar esa primera iteración. Si su contenido sigue en tu contexto, no la releas.
---

# Estado del proyecto (`graph`)

Lo que el código no puede decir vive en `.graph/Estado_Proyecto/`, en cinco documentos. No hay un
documento por archivo ni por carpeta: qué hace cada función y por qué se escribe en un comentario del
propio código, al programarla. El código se lee directo.

| Documento | Secciones | Qué va |
| :--- | :--- | :--- |
| `Estado.md` | `Hecho`, `En curso`, `Falta`, `Siguientes pasos` | Fotografía del ahora: se sobreescribe, no se acumula. |
| `Plan.md` | Una `## nombre_snake & Nombre Legible` por frente de trabajo, con bloques `###` y tareas `- [ ]`; `Completado` | Cola de trabajo. Un bloque cerrado se mueve entero a `Completado`. |
| `Decisiones.md` | Una `## titulo_en_snake_case` por decisión | `**Carpetas que afecta:**` y el porqué, con las alternativas descartadas. |
| `Tecnologias.md` | Una `## nombre_snake & Nombre Legible` por tecnología en uso | Cómo se usa en el proyecto, ventajas, desventajas y por qué se eligió. |
| `Arquitectura.md` | `Hardware`, `Tecnología`, `Componentes`, cada una con sus `###` | Dónde corre, qué se explota de cada tecnología y cómo se arma el software. |

El CLI busca el `.graph` más cercano subiendo por los padres (como git). Si `graph` no está en el PATH:
clonar https://github.com/AltairRicano/graph-ai y correr `./graph install` desde ahí.

## Al iniciar una sesión

1. `graph get Estado_Proyecto/Estado.md`. Si responde `no hay .graph`, no hay nada que leer: haz el
   trabajo que te pidieron; el estado se crea al cerrar esa primera iteración. Si el usuario no pidió
   usar `graph` en este proyecto, **pregúntale** antes de crearlo.
2. Lee otro documento solo cuando la tarea lo pida. Varios en una llamada:
   `graph get Decisiones Tecnologias`. Una sola sección: `graph get Estado#Falta`.
3. Después lee el código directamente.

## Al cerrar una iteración (antes de responder y antes de cada commit)

Escribe **todo en un solo `graph multiedit`**. Si el proyecto aún no tiene `.graph`, créalo en la misma
llamada: `graph init && graph multiedit <<'LOTE' ...`. No hace falta leer los documentos ni las
plantillas antes de escribirlos, ni releer el código que acabas de escribir.

Qué documentos tocar:

- **`Estado.md`, siempre.** Un requisito del usuario que todavía no se cumple (por ejemplo, «el
  frontend será en TypeScript») va en `Falta` o en `Siguientes pasos`: la siguiente sesión no lo puede
  deducir del código. Al reescribir una sección, conserva lo que sigue pendiente.
- **`Decisiones.md`** si elegiste entre alternativas, fijaste un valor por defecto sin preguntar o
  hiciste algo que no es obvio leyendo el código.
- **`Tecnologias.md`** si entró o salió un lenguaje, framework, base de datos o herramienta de despliegue.
- **`Arquitectura.md`** si cambió dónde corre el proyecto o cómo se arma: un servicio, un contenedor,
  un puerto o una carpeta principal nueva.
- **`Plan.md`** si se abrió o se cerró un bloque de trabajo.

## `graph multiedit`

Un lote de texto plano por stdin, sin escapar nada. Cada entrada es una línea separadora y debajo el
contenido tal cual:

```bash
graph multiedit <<'LOTE'
=== Estado_Proyecto/Estado.md#Hecho ===
- Backend desplegado con Docker Compose: API en 127.0.0.1:8080.
=== Estado_Proyecto/Estado.md#Falta ===
- Frontend en TypeScript (lo pidió el usuario para el sprint 2).
=== Estado_Proyecto/Decisiones.md ===
## dinero_en_centavos
**Carpetas que afecta:** `src/pagos`, `src/db`

El dinero se guarda en centavos enteros: con flotantes los totales no cuadran. Se descartó DECIMAL
porque el driver lo devuelve como texto.
=== Estado_Proyecto/Tecnologias.md ===
## base_datos & MySQL 8.4
Ajustado para caber en 300 MB.

**Por qué se eligió:** lo pidió el usuario.
LOTE
```

| Separador | Efecto |
| :--- | :--- |
| `=== documento#sección ===` | Reemplaza esa sección (el contenido va **sin** repetir el heading). En `Decisiones` y `Tecnologias`, si no existe se crea como `##`. |
| `=== documento#sección [append] ===` | Agrega al final de esa sección. |
| `=== documento ===` | Agrega al final del documento (una sección nueva lleva su `## nombre`). |
| `=== documento [override] ===` | Reemplaza todo lo escrito. |

- El documento se nombra `Estado_Proyecto/Estado.md` o solo `Estado`.
- **No escribas frontmatter ni líneas `**Elaboración:** | **Actualización:**`**: las pone el comando
  (conserva la elaboración y mueve la actualización solo si el texto cambió).
- Se valida todo antes de escribir: con un error no se aplica nada y dice qué entrada falló.
- El heredoc con comillas (`<<'LOTE'`) evita que el shell interprete `$`, comillas o backticks. Un lote
  muy grande se pasa con `graph multiedit -f lote.txt` (lo borra al aplicarlo).

## Comandos

| Comando | Qué hace |
| :--- | :--- |
| `graph init` | Crea `.graph/Estado_Proyecto/` con los cinco documentos. Correrlo de nuevo no sobreescribe nada. |
| `graph get <documento>[#sección]...` | Imprime uno o varios documentos, o una sección. |
| `graph status` | Lista los cinco documentos con su última actualización y cuáles siguen sin escribir. |
| `graph multiedit [-f lote] [--keep]` | Escribe secciones de varios documentos de un lote y pone las fechas. |

Códigos de salida: `0` bien, `2` error de uso o de precondición (por ejemplo, no hay `.graph`).

## Subagentes: `agentes/`

- Un subagente que **audita, investiga o reporta hallazgos sin editar código** escribe su reporte
  completo en `agentes/<fecha>_<nombre-agente>_<id-agente>.md`, en la raíz del proyecto. Nunca un agente
  consolidador que resuma a los demás: las respuestas largas se cortan y en el resumen se pierde contexto.
- Un subagente de **corrección** no escribe reporte: edita el archivo y deja el porqué en un comentario.
- `Estado_Proyecto/` lo escribe el agente principal, que es quien sabe qué se pidió y qué quedó pendiente.
- `agentes/` es operativo, no producto: va en el `.gitignore` del proyecto.

Formato del reporte en `plantillas/reporte_agente.md` (junto a este archivo).

## Plantillas

Para escribir basta esta página. Las plantillas de `plantillas/` traen las reglas finas de cada
documento (`estado.md`, `plan.md`, `decisiones.md`, `tecnologias.md`, `arquitectura.md`): lee una solo
si dudas, y no la releas si ya está en tu contexto.

## Qué no hace

- No lee el código ni sabe qué cambió: qué documento tocar lo decides tú con la lista de arriba.
- No avisa si un documento quedó viejo; `graph status` solo muestra la fecha de su última actualización.
- `.graph/` no se sube al repositorio: va en el `.gitignore` del proyecto.
