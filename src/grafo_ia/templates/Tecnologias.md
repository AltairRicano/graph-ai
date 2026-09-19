---
tipo: tecnologias
fecha_elaboracion: {{fecha}}
fecha_actualizacion: {{fecha}}
---
Tecnologías actualmente en uso en el proyecto: cómo funcionan, ventajas/desventajas y por qué fueron seleccionadas. No es un historial — si una tecnología se descarta, se elimina de aquí (el porqué del cambio va en [[Estado_Proyecto/Decisiones.md|Decisiones]]).

Cada heading es `nombre_snake_case & Nombre Legible`: identificador para el parser & texto a mostrar. Formato de cada entrada:

```markdown
## base_datos_relacional & PostgreSQL
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

**Dependencias:** `vendor/postgres` (solo si existe en la raíz del proyecto; código inline, no enlace)

Qué es y cómo funciona en el proyecto.

**Ventajas:** ...
**Desventajas:** ...

**Por qué se eligió:** ... (puede enlazar a Decisiones)
```

---
