# Plantilla: `Estado_Proyecto/Arquitectura.md`

Léela al documentar o cambiar la arquitectura del proyecto.

## Reglas

- Tres capas fijas: `## Hardware`, `## Tecnología`, `## Componentes`.
- Cada sub-heading lleva su línea `**Elaboración:** | **Actualización:**`.
- **Hardware:** un `###` por máquina o entorno (sistema operativo, RAM, CPU, almacenamiento, red).
- **Tecnología:** un `###` por tema; qué característica de cada tecnología se explota, con enlaces
  a [[#Hardware|Hardware]] y a [[Estado_Proyecto/Tecnologias.md|Tecnologías]].
- **Componentes:** patrones de diseño y especificación de cada componente, ramificado en `###` y
  `####` según la granularidad.
- Al terminar: `graph update Estado_Proyecto/Arquitectura.md`.

## Formato

```markdown
## Hardware
### servidor_produccion
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

## Tecnología
### persistencia
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD

## Componentes
### api_pagos
**Elaboración:** AAAA-MM-DD | **Actualización:** AAAA-MM-DD
#### validacion
```
