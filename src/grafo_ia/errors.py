"""Errores que el CLI traduce a mensaje + código de salida."""

EXIT_OK = 0
EXIT_USAGE = 2


class GraphError(Exception):
    """Error esperado: argumentos malos, precondición rota, `.graph` ausente.

    El CLI imprime el mensaje sin traceback y sale con `code`.
    """

    code = EXIT_USAGE

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


class NoGraphError(GraphError):
    """No hay `.graph` en la carpeta actual ni en sus padres."""


class AmbiguousError(GraphError):
    """Una sección coincide con más de un heading."""


class NotFoundError(GraphError):
    """Documento o sección inexistente."""
