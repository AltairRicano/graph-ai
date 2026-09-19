"""Errores que el CLI traduce a mensaje + código de salida."""

EXIT_OK = 0
EXIT_BLOCK = 1
EXIT_USAGE = 2


class GraphError(Exception):
    """Error esperado: argumentos malos, precondición rota, grafo ausente.

    El CLI imprime el mensaje sin traceback y sale con `code`.
    """

    code = EXIT_USAGE

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


class NoGraphError(GraphError):
    """No hay `.graph` en la carpeta actual ni en sus padres."""


class CorruptGraphError(GraphError):
    """`index.json` ilegible o con forma inválida."""


class AmbiguousError(GraphError):
    """Una sección o un enlace coincide con más de un destino."""


class NotFoundError(GraphError):
    """Nodo o sección inexistente."""
