# Plantilla: `Estado_Proyecto/Decisiones.md`

Léela al registrar una decisión que no es obvia solo con leer el código.

## Reglas

- Un `## titulo_en_snake_case` por decisión.
- **`**Carpetas que afecta:**`** obligatorio, con rutas del proyecto en código: la carpeta si la toca
  completa (`src/sync`), archivos puntuales si toca partes de varias (`src/sync/hash.go`), o nada si
  afecta a todo el proyecto por igual.
- Descripción tan extensa como haga falta: el porqué, las alternativas descartadas y sus costos. También
  van aquí los valores por defecto que elegiste sin preguntar.
- Se escribe con `graph multiedit`: `=== Estado_Proyecto/Decisiones.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final.
- La línea `**Elaboración:** | **Actualización:**` de cada `##` la pone `multiedit`: no la escribas.

## Formato

```markdown
## uso_de_hash_en_lugar_de_mtime
**Carpetas que afecta:** `src/sync`

Descripción tan extensa como haga falta.
```
