# Plantilla: índice de carpeta

Léela la primera vez que escribas el índice de una carpeta, o si dudas de qué va en él. El índice de
`src/pagos` vive en `.graph/src/pagos/pagos.md`; si la carpeta ya está en el grafo, la cáscara
(cabecera, `## Propósito` y `## Relaciones` vacías, y las listas de carpetas y archivos) ya existe.
El índice de la raíz del proyecto (`.`) es `.graph/Index.md` y sigue las mismas reglas.

## Reglas

- **Es el único documento de la carpeta**: uno por los 10, 20 o 30 archivos que tenga. Los archivos de
  código son los nodos del grafo y no tienen gemelo: qué hace cada función y por qué lo dice el propio
  código, en sus comentarios.
- **El índice cuenta lo que no se ve leyendo un solo archivo.** No resume archivo por archivo ni
  parafrasea el código, y no lleva el avance del trabajo (eso es `Estado_Proyecto/Estado.md`).
- **`## Propósito`** (obligatoria; sin ella el índice es un faltante): para qué existe el módulo y cómo
  impacta al proyecto. Qué resuelve, quién depende de él y qué se rompe si falla o cambia.
- **`## Relaciones`**: una línea por relación, `- [[origen]] → [[destino]]: por qué`. El origen y el
  destino son archivos de código reales (`[[src/pagos/cobro.go|cobro.go]]`), una función de un archivo
  (`[[src/pagos/cobro.go#calcular_total|calcular_total]]`) o el índice de otra carpeta
  (`[[src/db|db]]`, `[[src/db#Transacciones|transacciones]]`). Van solo las que explican el módulo:
  - de qué depende fuera de la carpeta y quién lo usa desde fuera;
  - las que un import no muestra: una llamada HTTP, una tabla o un evento compartido, un orden obligado.

  Los imports evidentes entre archivos de la misma carpeta no se listan.
- **Secciones temáticas** (`## nombre`), las que hagan falta: una por regla de negocio, flujo o
  restricción que cruza varios archivos de la carpeta, con enlaces a los archivos donde vive.
  - Si la regla vive en un solo archivo, no va aquí: va en un comentario junto al código.
  - Si cruza carpetas o hubo alternativas descartadas, va en
    [[Estado_Proyecto/Decisiones.md|Decisiones]] y aquí solo se enlaza.
- **Nunca edites las listas `📁 Carpetas` / `📄 Archivos`**: las mantiene el CLI.
- **No escribas el frontmatter ni la línea `**Elaboración:** | **Actualización:**`** de cada `##`: las
  pone `graph multiedit` (conserva la elaboración y mueve la actualización solo si el texto cambió).
- Una carpeta sin archivos propios (solo subcarpetas) o que solo tiene archivos triviales (estilos,
  configuración) no pide `## Propósito`.
- Largo: el que se lee de una pasada. Un índice demasiado largo se avisa: suele repetir lo que el
  código ya dice.
- Se escribe con `graph multiedit`, que confirma el índice él mismo: `=== carpeta#Sección ===`
  reemplaza una sección (o la crea), `=== carpeta ===` agrega al final. Solo si lo editas a mano hace
  falta `graph update <carpeta>`.

## Formato

Lo que mandas en el lote (sin cabecera, fechas ni listas):

```markdown
=== src/pagos#Propósito ===
Cobra los pedidos y deja el asiento que después usa facturación. Todo lo que mueve dinero pasa por
aquí: si falla, los pedidos se quedan sin cobrar y la factura no se puede emitir.
=== src/pagos#Relaciones ===
- [[src/pagos/cobro.go#calcular_total|calcular_total]] → [[src/pagos/descuentos.go|descuentos.go]]: el descuento se aplica antes del impuesto.
- [[src/pagos/cobro.go|cobro.go]] → [[src/db#Transacciones|db]]: cada cobro corre en una sola transacción.
- [[web/src/api.ts|api.ts]] → [[src/pagos/rutas.go|rutas.go]]: el frontend cobra con `POST /pagos`.
=== src/pagos ===
## Redondeo de centavos
El total se redondea una sola vez, al final de [[src/pagos/cobro.go#calcular_total|calcular_total]].
[[src/pagos/descuentos.go|descuentos.go]] y [[src/pagos/impuestos.go|impuestos.go]] trabajan con el
monto sin redondear: redondear en cada paso deja diferencias que la factura rechaza.
```

Cómo queda en `.graph/src/pagos/pagos.md`:

```markdown
---
tipo: indice
fecha_elaboracion: AAAA-MM-DD
fecha_actualizacion: AAAA-MM-DD
---
## Propósito
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

Cobra los pedidos y deja el asiento que después usa facturación. ...

## Relaciones
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

- [[src/pagos/cobro.go#calcular_total|calcular_total]] → [[src/pagos/descuentos.go|descuentos.go]]: ...

## Redondeo de centavos
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

El total se redondea una sola vez, ...

## 📁 Carpetas
- [[src/pagos/proveedores/proveedores.md|proveedores]]

## 📄 Archivos
- [[src/pagos/cobro.go|cobro.go]]
- [[src/pagos/descuentos.go|descuentos.go]]
```

Las listas van siempre al final: lo que agregas queda antes de ellas.
