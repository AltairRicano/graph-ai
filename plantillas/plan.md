# Plantilla: `Estado_Proyecto/Plan.md`

Léela al agregar, avanzar o cerrar trabajo planeado.

## Reglas

- Jerarquía: **Sección** `## nombre_snake & Nombre Legible` → **Bloque** `###` → **Tareas** como
  checklist `- [ ]` (nunca headings).
- Una tarea puede enlazar a código que todavía no existe: el enlace queda como *pendiente por
  crear* y `graph incomplete` lo lista hasta que el archivo exista.
- Al completar un bloque, **se corta entero** y se pega al final bajo `## Completado`, con
  `**Sección de origen:**` y `**Cerrado:** AAAA-MM-DD`. Así un `tail` muestra el cierre más reciente.
- Al terminar: `graph update Estado_Proyecto/Plan.md`.

## Formato

```markdown
## pagos & Pagos

### cobro_con_tarjeta
- [ ] Validar el token en [[src/pagos/cobro.go.md#validar_token|validar_token]]
- [x] Tabla de transacciones

---

## Completado

### reembolsos
**Sección de origen:** [[#pagos|Pagos]]
**Cerrado:** AAAA-MM-DD
- [x] ...
```
