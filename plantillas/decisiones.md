# Plantilla: `Estado_Proyecto/Decisiones.md`

Léela al registrar una decisión que no es obvia solo con leer el código.

## Reglas

- Un `## titulo_en_snake_case` por decisión, con su línea de fechas.
- **`**Carpetas que afecta:**`** obligatorio: el índice de la carpeta si la toca completa, archivos o
  secciones puntuales si toca partes de varias, o nada si afecta a todo el proyecto por igual.
- Descripción tan extensa como haga falta: el porqué, las alternativas descartadas y sus costos.
- Al terminar: `graph update Estado_Proyecto/Decisiones.md`.

## Formato

```markdown
## uso_de_hash_en_lugar_de_mtime
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

**Carpetas que afecta:** [[src/sync/sync.md|sync]]

Descripción tan extensa como haga falta.
```
