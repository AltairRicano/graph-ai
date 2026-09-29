# Plantilla: `Estado_Proyecto/Tecnologias.md`

Léela al agregar, cambiar o descartar una tecnología del proyecto.

## Reglas

- Solo tecnologías **en uso**. No es un historial: lo descartado se **borra** de aquí y el porqué del
  cambio va en [[Estado_Proyecto/Decisiones.md|Decisiones]].
- Un `## nombre_snake & Nombre Legible` por tecnología: identificador para el parser & texto a mostrar.
- `**Dependencias:**` solo si la tecnología vive en una carpeta de la raíz del proyecto (código
  inline, no enlace).
- Al terminar: `graph update Estado_Proyecto/Tecnologias.md`.

## Formato

```markdown
## base_datos_relacional & PostgreSQL
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

**Dependencias:** `vendor/postgres`

Qué es y cómo funciona en el proyecto.

**Ventajas:** ...
**Desventajas:** ...

**Por qué se eligió:** ... (puede enlazar a Decisiones)
```
