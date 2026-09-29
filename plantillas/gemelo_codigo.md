# Plantilla: gemelo de código

Léela al escribir o actualizar el gemelo de un archivo de código. El gemelo vive en la misma ruta
más `.md` dentro de `.graph/` (`src/pagos/cobro.go` → `.graph/src/pagos/cobro.go.md`); si el
archivo ya está en el grafo, la cáscara (solo frontmatter) ya existe.

## Reglas

- **Descripción inicial:** por qué existe el archivo. Corta pero detallada; se alarga solo si hay
  mucha lógica de negocio.
- **`## Funciones`** con un `###` por función o método. Los métodos van como `Clase.metodo`, todos
  al mismo nivel (sin `####` por clase).
- En Python y Go, `graph update`, `graph status` e `graph incomplete` cruzan esos `###` con las
  funciones reales y reportan **funciones sin sección** y **secciones sin función**. El heading
  puede llevar backticks o paréntesis (`` `calcular_total()` ``): se compara solo el nombre.
- Cada `###` lleva su línea `**Elaboración:** | **Actualización:**`. La de Actualización la mueves
  tú cuando cambias esa sección; `graph update` solo mueve la `fecha_actualizacion` del frontmatter.
- Mínima si la función es trivial; específica y con enlaces a las funciones relacionadas si es
  lógica de negocio.
- Al poner al día un gemelo desactualizado, `graph diff <ruta> --symbols` dice qué funciones
  cambiaron (modificadas, nuevas, eliminadas): son las secciones a revisar.
- Al terminar: `graph update <ruta>`.

## Formato

```markdown
---
tipo: codigo
fecha_elaboracion: AAAA-MM-DD
fecha_actualizacion: AAAA-MM-DD
---
Descripción corta pero detallada de por qué existe el archivo.

---

## Funciones

### calcular_total
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

Mínima si es trivial; específica y con enlaces a las funciones relacionadas si es lógica de negocio,
por ejemplo [[src/pagos/descuentos.go.md#aplicar_descuento|aplicar_descuento]].

### Carrito.agregar
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

Los métodos van como `Clase.metodo`, todos al mismo nivel.
```
