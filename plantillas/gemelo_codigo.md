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
- **Cada `###` responde dos preguntas, siempre las dos:**
  - **Qué hace:** el comportamiento en una o dos frases, sin parafrasear el código línea por línea
    (eso el agente ya lo lee en el archivo).
  - **Por qué existe:** la razón de negocio o del dominio que la hace necesaria: qué regla, caso o
    restricción resuelve, qué pasaría sin ella, y por qué funciona así y no de la forma obvia. Es lo
    que el código no dice y lo más valioso del gemelo. Si la función es pura plomería (un getter, un
    adaptador), dilo en una línea y enlaza a la función de negocio a la que sirve.
- Largo según la función: mínima si es trivial; específica y con enlaces a las funciones relacionadas
  si es lógica de negocio.
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

**Qué hace:** suma los renglones del carrito, aplica
[[src/pagos/descuentos.go.md#aplicar_descuento|aplicar_descuento]] y después el impuesto.

**Por qué existe:** el total que ve el cliente tiene que coincidir con el de la factura, y el
descuento va antes del impuesto porque así lo exige la facturación; hacerlo al revés deja
diferencias de centavos que la factura rechaza.

### Carrito.agregar
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

**Qué hace:** agrega un producto o suma la cantidad si ya estaba.

**Por qué existe:** plomería de [[#calcular_total|calcular_total]]: evita
renglones repetidos del mismo producto. Los métodos van como `Clase.metodo`, todos al mismo nivel.
```
