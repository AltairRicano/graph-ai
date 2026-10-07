# grafo_ia — Estado de proyecto para IA

Contexto de un proyecto de código para agentes de IA, sin duplicar el código en documentación. Lo que el
código no puede decir (qué está hecho y qué falta, por qué se decidió cada cosa, con qué se construye y
dónde corre) vive en cinco documentos markdown dentro de `.graph/Estado_Proyecto/`, que se leen y se escriben
con el comando `graph`. Pensado para el modo headless.

- `Estado.md`, `Plan.md`, `Decisiones.md`, `Tecnologias.md` y `Arquitectura.md`: nada más.
- No hay un documento por archivo ni por carpeta: qué hace cada función y por qué va en sus comentarios, y
  el código se lee directo.
- `graph multiedit` escribe secciones de varios documentos en una sola llamada a partir de un lote de texto
  plano, y pone las fechas.
- Los reportes de subagentes van en `agentes/`, en la raíz del proyecto, uno por agente.

El manual de uso (cuándo leer, cuándo escribir y formatos) está en [SKILL.md](SKILL.md).

## Instalación

Requiere Python 3.10+. No tiene dependencias. Clona el repo donde guardas tus repos y corre el instalador:

```bash
git clone https://github.com/AltairRicano/graph-ai.git ~/repos/graph
cd ~/repos/graph
./graph install                    # Windows: graph.cmd install
```

`./graph install` hace tres cosas:

1. Crea un entorno virtual propio en `.venv/` dentro del repo (con `uv` si lo tienes, si no con `venv` + `pip`)
   e instala `grafo_ia` en modo editable.
2. Pone el comando `graph` en tu PATH: un symlink en `~/.local/bin/graph` (Windows: `graph.cmd` en
   `%USERPROFILE%\.local\bin`). Si ahí ya hay un `graph` que no es este, no lo pisa sin `--force`.
   Te avisa si la carpeta no está en tu PATH, o si otro `graph` (por ejemplo el de GNU plotutils) le gana.
3. **No instala la Skill por defecto**, porque cada agente tiene su propia forma de instalarlas. Te imprime la ruta
   de `SKILL.md`. Si quieres enlazarla, pasa la carpeta de skills de tu agente:

```bash
./graph install --skill-dir ~/.claude/skills      # Claude Code: enlaza el repo como ~/.claude/skills/grafo-ia
```

Opciones: `--bin-dir DIR` (otra carpeta para el comando), `--python RUTA` (otro intérprete), `--force`.

**Actualizar:** `git pull` en el repo. Al ser editable, no hace falta reinstalar.

**Desinstalar:** `./graph uninstall [--skill-dir DIR] [--purge]`. `--purge` borra también el `.venv/` del repo.
Los `.graph` de tus proyectos no se tocan.

Desde el repo, `./graph <comando>` también funciona sin tener nada en el PATH: delega al CLI del `.venv/`.

Para desarrollo: `uv venv && uv pip install -e '.[test]'`.

## Uso

```bash
cd mi-proyecto
graph init                         # crea .graph/Estado_Proyecto con los cinco documentos
graph get Estado                   # lee un documento (o varios: graph get Estado Plan)
graph get Estado#Falta             # o una sola sección
graph status                       # los cinco documentos con su última actualización
graph multiedit <<'LOTE'           # escribe varios documentos en una llamada
=== Estado_Proyecto/Estado.md#Hecho ===
- Cobro con descuentos.
=== Estado_Proyecto/Decisiones.md ===
## dinero_en_centavos
**Carpetas que afecta:** `src/pagos`

Con flotantes los totales no cuadran.
LOTE
```

| Comando | Qué hace |
| :--- | :--- |
| `graph init` | Crea `.graph/Estado_Proyecto/` con los cinco documentos. Correrlo de nuevo no sobreescribe nada. |
| `graph get <documento>[#sección]...` | Imprime uno o varios documentos, o una sección. |
| `graph status` | Lista los cinco documentos con su última actualización y cuáles siguen sin escribir. |
| `graph multiedit [-f lote] [--keep]` | Escribe secciones de varios documentos de un lote (stdin o archivo). |

El comando busca el `.graph` más cercano subiendo por las carpetas padre, como git. Un documento se nombra
`Estado_Proyecto/Estado.md` o solo `Estado`.

### Lotes de `graph multiedit`

Cada entrada empieza con una línea separadora y sigue con el contenido tal cual, sin escapar nada.

| Separador | Efecto |
| :--- | :--- |
| `=== documento#sección ===` | Reemplaza esa sección. En `Decisiones` y `Tecnologias`, si no existe la crea. |
| `=== documento#sección [append] ===` | Agrega al final de esa sección. |
| `=== documento ===` | Agrega al final del documento. |
| `=== documento [override] ===` | Reemplaza todo lo escrito. |

El frontmatter y las líneas `**Elaboración:** | **Actualización:**` los mantiene el comando. El lote se valida
entero antes de escribir: un error no deja nada a medias. Con `-f lote.txt` lee el lote de un archivo y lo borra
al aplicarlo (`--keep` lo conserva).

`.graph/` y `agentes/` son operativos: van en el `.gitignore` de cada proyecto.

### Proyectos con un `.graph` anterior

La versión anterior guardaba un gemelo markdown por archivo de código y un `index.json`. Un proyecto que ya
tiene ese `.graph` puede seguir con ella: se instala aparte desde la rama `gemelos`, con su comando en el PATH
como `graph-gemelos`. Cuando `graph` encuentra un `.graph` con `index.json`, le pasa el comando tal cual a
`graph-gemelos`.

## Estructura del repositorio

```
graph-ai/
├── .github/workflows/   CI: pruebas e instalador en Linux, macOS y Windows
├── plantillas/          reglas de escritura de cada documento de Estado_Proyecto y de los
│                        reportes de agentes (un archivo por formato)
├── scripts/             instalador multiplataforma (install.py)
├── src/grafo_ia/        paquete Python del CLI: parser de markdown, rutas y escritura de archivos
│   ├── commands/        un módulo por grupo de subcomandos (init, get y status, multiedit)
│   └── templates/       cáscaras de los cinco documentos que crea `graph init`
├── tests/               pruebas con pytest
├── graph, graph.cmd     lanzadores del repo (POSIX y Windows)
├── SKILL.md             manual de uso: cuándo leer, cuándo escribir y formatos
└── pyproject.toml       metadatos del paquete
```

## Pruebas

```bash
.venv/bin/python -m pytest
```

El CI corre la matriz de Linux, macOS y Windows (`.github/workflows/tests.yml`).

## Licencia

Apache 2.0. Ver [LICENSE](LICENSE).
