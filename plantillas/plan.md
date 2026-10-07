# Plantilla: `Estado_Proyecto/Plan.md`

Léela al agregar, avanzar o cerrar trabajo planeado.

## Reglas

- Jerarquía: **Sección** `## nombre_snake & Nombre Legible` → **Bloque** `###` → **Tareas** como
  checklist `- [ ]` (nunca headings).
- Una tarea nombra el código que toca con su ruta (`src/pagos/cobro.go`), exista ya o no.
- Al completar un bloque, **se corta entero** y se pega al final bajo `## Completado`, con
  `**Sección de origen:**` y `**Cerrado:** AAAA-MM-DD`. Así un `tail` muestra el cierre más reciente.
- Se escribe con `graph multiedit`: `=== Estado_Proyecto/Plan.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final.

## Formato

```markdown
## pagos & Pagos

### cobro_con_tarjeta
- [ ] Validar el token en `validar_token` (`src/pagos/cobro.go`)
- [x] Tabla de transacciones

---

## Completado

### reembolsos
**Sección de origen:** pagos
**Cerrado:** AAAA-MM-DD
- [x] ...
```
