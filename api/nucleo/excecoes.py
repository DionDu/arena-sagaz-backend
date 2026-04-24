from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErroNegocio(Exception):
    def __init__(self, detalhe: str, codigo: str, status_http: int = 400):
        self.detalhe = detalhe
        self.codigo = codigo
        self.status_http = status_http
        super().__init__(detalhe)


class ErroConflito(ErroNegocio):
    def __init__(self, detalhe: str, codigo: str):
        super().__init__(detalhe, codigo, status_http=409)


class ErroNaoAutorizado(ErroNegocio):
    def __init__(self, detalhe: str, codigo: str):
        super().__init__(detalhe, codigo, status_http=401)


class ErroNaoEncontrado(ErroNegocio):
    def __init__(self, detalhe: str, codigo: str):
        super().__init__(detalhe, codigo, status_http=404)


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroNegocio)
    async def handler_erro_negocio(request: Request, exc: ErroNegocio) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_http,
            content={"detalhe": exc.detalhe, "codigo": exc.codigo},
        )
