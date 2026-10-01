# Plantilla: `Estado_Proyecto/Tecnologias.md`

Léela al agregar, cambiar o descartar una tecnología del proyecto.

## Reglas

- Solo tecnologías **en uso**. No es un historial: lo descartado se **borra** de aquí y el porqué del
  cambio va en [[Estado_Proyecto/Decisiones.md|Decisiones]].
- Un `## nombre_snake & Nombre Legible` por tecnología: identificador para el parser & texto a mostrar.
- `**Dependencias:**` solo si la tecnología vive en una carpeta de la raíz del proyecto (código
  inline, no enlace).
- Se escribe con `graph multiedit` (`=== Estado_Proyecto/Tecnologias.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final), que confirma él mismo. Solo si lo editas a mano:
  `graph update Estado_Proyecto/Tecnologias.md`.
- La línea `**Elaboración:** | **Actualización:**` de cada `##` la pone `multiedit`: no la escribas.

## Formato

```markdown
## base_datos_relacional & PostgreSQL
**Dependencias:** `vendor/postgres`

Qué es y cómo funciona en el proyecto.

**Ventajas:** ...
**Desventajas:** ...

**Por qué se eligió:** ... (puede enlazar a Decisiones)
```
