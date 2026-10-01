# Plantilla: `Estado_Proyecto/Decisiones.md`

Léela al registrar una decisión que no es obvia solo con leer el código.

## Reglas

- Un `## titulo_en_snake_case` por decisión.
- **`**Carpetas que afecta:**`** obligatorio: el índice de la carpeta si la toca completa, archivos o
  secciones puntuales si toca partes de varias, o nada si afecta a todo el proyecto por igual.
- Descripción tan extensa como haga falta: el porqué, las alternativas descartadas y sus costos.
- Se escribe con `graph multiedit` (`=== Estado_Proyecto/Decisiones.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final), que confirma él mismo. Solo si lo editas a mano:
  `graph update Estado_Proyecto/Decisiones.md`.
- La línea `**Elaboración:** | **Actualización:**` de cada `##` la pone `multiedit`: no la escribas.

## Formato

```markdown
## uso_de_hash_en_lugar_de_mtime
**Carpetas que afecta:** [[src/sync/sync.md|sync]]

Descripción tan extensa como haga falta.
```
