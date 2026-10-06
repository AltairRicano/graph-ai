# Plantilla: reporte de agente (`agentes/`)

Léela al lanzar una flota de subagentes en paralelo, o si eres uno de ellos.

## Reglas

- Cada agente que **audite, investigue o reporte hallazgos sin editar código** escribe su propio
  archivo en `agentes/` (carpeta real en la raíz del proyecto, fuera de `.graph`). Nunca un agente
  consolidador que resuma a los demás: se pierde contexto en ese resumen.
- El cuerpo es el contenido **completo** de la tarea (el hallazgo, la auditoría, el análisis), no un
  resumen: la razón de escribirlo en disco es que las respuestas largas se cortan por límite de contexto.
- `agentes/` en la raíz está **excluida del grafo por defecto**: el reporte no entra a ningún índice, no
  se corre `graph add` ni `graph update` sobre él. Es markdown y se lee directo.
- Un agente de **corrección** (que edita un archivo real) no escribe reporte: edita el archivo, deja
  el porqué en un comentario del código y, si el cambio altera lo que dice el índice de la carpeta, lo
  pone al día con `graph multiedit`.
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
