# Plantilla: `Estado_Proyecto/Arquitectura.md`

Léela al documentar o cambiar la arquitectura del proyecto.

## Reglas

- Tres capas fijas: `## Hardware`, `## Tecnología`, `## Componentes`.
- **Hardware:** un `###` por máquina o entorno (sistema operativo, RAM, CPU, almacenamiento, red).
- **Tecnología:** un `###` por tema; qué característica de cada tecnología se explota, con enlaces
  a [[#Hardware|Hardware]] y a [[Estado_Proyecto/Tecnologias.md|Tecnologías]].
- **Componentes:** patrones de diseño y especificación de cada componente, ramificado en `###` y
  `####` según la granularidad.
- Se escribe con `graph multiedit` (`=== Estado_Proyecto/Arquitectura.md#Sección ===` reemplaza una sección;
  sin `#Sección` agrega al final), que confirma él mismo. Solo si lo editas a mano:
  `graph update Estado_Proyecto/Arquitectura.md`.
- La línea `**Elaboración:** | **Actualización:**` de cada `###` la pone `multiedit`: no la escribas.

## Formato

```markdown
## Hardware
### servidor_produccion
## Tecnología
### persistencia
## Componentes
### api_pagos
#### validacion
```
