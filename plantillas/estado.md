# Plantilla: `Estado_Proyecto/Estado.md`

Léela al actualizar el estado del proyecto (al cerrar una sesión o una fase).

## Reglas

- Es una **fotografía del ahora**, no una bitácora: se sobreescribe, no se acumula.
- **Sin fechas por ítem.**
- Cuatro secciones fijas: `## Hecho`, `## En curso`, `## Falta`, `## Siguientes pasos`
  (subconjunto priorizado de "Falta").
- El porqué de lo hecho vive en [[Estado_Proyecto/Decisiones.md|Decisiones]]; el horizonte a futuro,
  en [[Estado_Proyecto/Plan.md|Plan]]. Enlaza en vez de repetir.
- "En curso" solo menciona tecnologías que estén en [[Estado_Proyecto/Tecnologias.md|Tecnologías]].
- Al terminar: `graph update Estado_Proyecto/Estado.md`.

## Formato

```markdown
## Hecho
- Lo que ya está completo y funcionando.

## En curso
- En qué se trabaja ahora mismo.

## Falta
- Backlog general, sin priorizar.

## Siguientes pasos
- Lo siguiente, en orden.
```
