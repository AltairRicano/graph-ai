# Plantilla: reporte de agente (`agentes/`)

Léela al lanzar una flota de subagentes en paralelo, o si eres uno de ellos.

## Reglas

- Cada agente que **audite, investigue o reporte hallazgos sin editar código** escribe su propio
  archivo en `agentes/` (carpeta en la raíz del proyecto, fuera de `.graph`). Nunca un agente
  consolidador que resuma a los demás: se pierde contexto en ese resumen.
- El cuerpo es el contenido **completo** de la tarea (el hallazgo, la auditoría, el análisis), no un
  resumen: la razón de escribirlo en disco es que las respuestas largas se cortan por límite de contexto.
- El reporte es markdown suelto: se lee directo y `graph` no lo toca.
- Un agente de **corrección** (que edita un archivo real) no escribe reporte: edita el archivo y deja
  el porqué en un comentario del código.
- `Estado_Proyecto/` lo actualiza el agente principal al cerrar, no los subagentes: es quien sabe qué se
  pidió y qué quedó pendiente.
- `agentes/` es operativo, no producto: el proyecto debe tenerla en su `.gitignore`.

## Nombre de archivo

`agentes/<fecha>_<nombre-agente>_<id-agente>.md`, por ejemplo `agentes/2026-09-21_code-reviewer_a3f91c.md`.

## Formato

```markdown
---
agente: code-reviewer
id: a3f91c
fecha: AAAA-MM-DD
tarea: auditoria
---
Contenido completo de la tarea.
```
