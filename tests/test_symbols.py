"""Cruce funciones del código <-> secciones del gemelo."""

from __future__ import annotations

from grafo_ia import parser, symbols

from conftest import write, write_twin

PY = '''import functools


def calcular_total(items):
    return sum(items)


@functools.cache
def _ayuda():
    pass


class Carrito:
    def agregar(self, x):
        pass

    @property
    def total(self):
        return 0

    @total.setter
    def total(self, v):
        pass

    class Linea:
        async def guardar(self):
            pass
'''

GO = '''package pagos

func Cobrar(m int) error {
	return nil
}

func (c *Carrito) Agregar(x int) {
}

func (s Pila[T]) Push(v T) {}
'''


def test_extrae_python():
    syms = symbols.extract("a.py", PY)
    assert [s.name for s in syms] == [
        "calcular_total", "_ayuda", "Carrito.agregar", "Carrito.total", "Carrito.total", "Carrito.Linea.guardar",
    ]
    ayuda = syms[1]
    assert (ayuda.start, ayuda.end) == (8, 10)  # el decorador cuenta
    assert symbols.extract("a.py", "def roto(:\n") is None


def test_extrae_go():
    syms = symbols.extract("a.go", GO)
    assert [(s.name, s.start, s.end) for s in syms] == [("Cobrar", 3, 5), ("Carrito.Agregar", 7, 8), ("Pila.Push", 10, 10)]


def test_lenguaje_sin_soporte():
    assert symbols.extract("a.rs", "fn main() {}") is None
    assert symbols.align("a.rs", "fn main() {}", parser.parse("x")) is None


def test_align_normaliza_headings():
    doc = parser.parse("Algo.\n\n## Funciones\n### `calcular_total()`\n### _ayuda(a, b)\n### viejo\n#### nivel4\n## Otra\n### Carrito.agregar\n")
    a = symbols.align("a.py", PY, doc)
    assert a.sin_seccion == ["Carrito.agregar", "Carrito.total", "Carrito.Linea.guardar"]  # fuera de ## Funciones no cuenta
    assert a.sin_funcion == ["viejo"]


def test_touched():
    old = "def a():\n    return 1\n\n\ndef b():\n    return 2\n\n\ndef c():\n    pass\n"
    new = "X = 1\n\n\ndef a():\n    return 1\n\n\ndef b():\n    return 3\n\n\ndef d():\n    pass\n"
    t = symbols.touched("m.py", old, new)
    assert t.modificadas == ["b"] and t.nuevas == ["d"] and t.eliminadas == ["c"] and t.fuera
    # agregar una función al final con su separación en blanco no es un cambio "fuera de funciones"
    t = symbols.touched("m.py", "def a():\n    pass\n", "def a():\n    pass\n\n\ndef b():\n    pass\n")
    assert t.nuevas == ["b"] and not t.fuera


def test_incomplete_status_y_update_avisan(initialized, run):
    root = initialized
    write(root, "src/pagos.py", "def cobrar():\n    pass\n\n\ndef reembolsar():\n    pass\n")
    run(root, "add")
    write_twin(root, "src/pagos.py.md", "Pagos.\n\n## Funciones\n### cobrar\nCobra.\n\n### anular\nYa no existe.\n")
    code, out = run(root, "update", "src/pagos.py")
    assert code == 0 and "[AVISO] el gemelo no cuadra" in out and "sin sección: reembolsar" in out and "sin función: anular" in out
    out = run(root, "incomplete")[1]
    assert "secciones desalineadas con el código (1)" in out and "src/pagos.py: sin sección: reembolsar; sin función: anular" in out
    assert "desalineado: 1" in run(root, "status")[1]
    write_twin(root, "src/pagos.py.md", "Pagos.\n\n## Funciones\n### cobrar\nCobra.\n\n### reembolsar\nDevuelve.\n")
    code, out = run(root, "update", "src/pagos.py")
    assert code == 0 and "AVISO" not in out
    assert "desalineado: 0" in run(root, "status")[1]
