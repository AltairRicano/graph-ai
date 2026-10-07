# Plantilla: `Estado_Proyecto/Estado.md`

Léela al actualizar el estado del proyecto (al cerrar una sesión o una fase).

## Reglas

- Es una **fotografía del ahora**, no una bitácora: se sobreescribe, no se acumula.
- **Sin fechas por ítem.**
- Cuatro secciones fijas: `## Hecho`, `## En curso`, `## Falta`, `## Siguientes pasos`
  (subconjunto priorizado de "Falta").
- Un requisito que el usuario pidió y todavía no se cumple va en `Falta` o `Siguientes pasos`, con sus
  palabras: la siguiente sesión no lo puede deducir del código.
- Al reescribir una sección, conserva lo que sigue vigente: `multiedit` la reemplaza entera.
- El porqué de lo hecho vive en [[Estado_Proyecto/Decisiones.md|Decisiones]]; el horizonte a futuro,
  en [[Estado_Proyecto/Plan.md|Plan]]. Enlaza en vez de repetir.
- "En curso" solo menciona tecnologías que estén en [[Estado_Proyecto/Tecnologias.md|Tecnologías]].
- Se escribe con `graph multiedit`: `=== Estado_Proyecto/Estado.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final.

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
