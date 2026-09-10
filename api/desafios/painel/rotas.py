"""AS ROTAS DO PAINEL (T039/T040) — `/painel/desafios`.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE FORA DE `/v1`
═══════════════════════════════════════════════════════════════════════════

`/v1` e o contrato com **os aplicativos em campo**, e ele carrega uma promessa:
uma versao publicada continua funcionando ate o force-update a retirar. O painel
nao tem cliente publicado nenhum — ele e uma pagina que uma pessoa abre —, e
coloca-lo sob a mesma versao faria parecer que ele participa daquela promessa.

E o mesmo lugar em que `/legal` mora, pelo mesmo motivo: e conteudo web, e nao
API de aplicativo.

═══════════════════════════════════════════════════════════════════════════
O PADRAO POST → REDIRECT → GET, E POR QUE ELE NAO E DETALHE
═══════════════════════════════════════════════════════════════════════════

Toda acao responde `303 See Other` apontando de volta para a pagina. O motivo e
concreto: sem isso, um F5 depois de aprovar **reenvia o formulario**, e o dono
descartaria duas vezes o mesmo desafio sem perceber (o segundo descarte
sobrescreveria o motivo do primeiro).

⚠️ **`303`, e nao `302`**: o `303` obriga o navegador a trocar o metodo para
`GET` ao seguir. Com `302` alguns clientes repetem o `POST` no destino.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE O FORMULARIO E LIDO A MAO, E NAO COM `Form(...)`
═══════════════════════════════════════════════════════════════════════════

`Form(...)` do FastAPI — e ate `await request.form()` do Starlette — exigem o
pacote **`python-multipart`**, e ele **nao esta** em `requirements_api.txt`.
Acrescenta-lo poria uma dependencia nova na imagem que serve o aplicativo em
producao, por causa de uma pagina que uma pessoa abre uma vez por dia. E a mesma
conta que manteve o Jinja2 de fora (ver `pagina.py`).

O que se perde e conforto de escrita; o que se ganha e nao aumentar a superficie
de producao. E o corpo de um `<form>` sem `enctype` e
`application/x-www-form-urlencoded`, cujo formato a **biblioteca padrao** ja le
com `urllib.parse.parse_qsl` — percent-encoding, `+` como espaco e chaves
repetidas inclusos. ⛔ Isto **nao** aceita `multipart/form-data` (upload de
arquivo), e nem precisa: nao ha campo de arquivo neste painel.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.painel import pagina
from api.desafios.painel.repositorio import RepositorioPainel
from api.desafios.painel.seguranca import (
    NOME_DO_COOKIE,
    VALIDADE_DO_COOKIE_S,
    cookie_seguro,
    exigir_curador,
    segredo_configurado,
)
from api.desafios.painel.servico import ServicoCuradoria
from api.desafios.painel.vigilancia import Vigilancia
from api.nucleo.banco import obter_sessao
from api.nucleo.excecoes import ErroNegocio
from api.nucleo.log import obter_logger

log = obter_logger("api.desafios.painel")

router = APIRouter()

#: Teto do corpo de um formulario, em bytes.
#:
#: ⚠️ O maior campo e o motivo de descarte (500 caracteres). 8 KB e folga
#: generosa, e existe para que um `POST` de megabytes nao seja lido inteiro na
#: memoria antes de alguem descobrir que ele nao servia para nada.
MAX_CORPO_BYTES = 8 * 1024


def hoje_utc() -> date:
    """O dia corrente **em UTC**.

    ⚠️ Funcao propria, e nao `date.today()` espalhado pelas rotas, por dois
    motivos: `date.today()` usa o fuso do **servidor** (que no Railway e UTC, mas
    isso e configuracao, nao garantia), e uma funcao com nome e o ponto por onde
    o teste substitui o dia sem congelar o relogio do processo inteiro.
    """
    return datetime.now(timezone.utc).date()


def obter_servico(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoCuradoria:
    """Monta o servico ligado a sessao da requisicao.

    Dependencia propria para os testes a trocarem por um dube sem banco — o
    mesmo padrao de `obter_servico_preferencias` em `api/notificacoes/rotas.py`.
    """
    return ServicoCuradoria(RepositorioPainel(sessao))


async def campos_do_formulario(request: Request) -> dict[str, str]:
    """Os campos de um `<form>` urlencoded, lidos com a biblioteca padrao.

    Args:
        request: a requisicao.

    Returns:
        `{nome: valor}`. Campo repetido fica com o **ultimo** valor — nenhum
        formulario deste painel repete nome, e escolher o ultimo e o mesmo que o
        navegador faria ao reenviar.

    Raises:
        ErroNegocio: corpo grande demais.

    Ver a nota no topo do modulo sobre por que isto nao usa `Form(...)`.
    """
    corpo = await request.body()
    if len(corpo) > MAX_CORPO_BYTES:
        raise ErroNegocio(
            "Formulario grande demais.", "formulario_grande", status_http=413
        )
    # `keep_blank_values=True`: um campo enviado vazio precisa **existir** no
    # dicionario. Sem isso, "descartar sem motivo" chegaria como "campo ausente",
    # e a mensagem de erro seria sobre a coisa errada.
    return dict(parse_qsl(corpo.decode("utf-8"), keep_blank_values=True))


def _uuid_do_formulario(campos: dict[str, str]) -> UUID:
    """Le `id_desafio` do formulario.

    Raises:
        ErroNegocio: ausente ou malformado — 400, e nao 500: um `id` torto vem de
            fora, e nao e defeito do servidor.
    """
    bruto = (campos.get("id_desafio") or "").strip()
    try:
        return UUID(bruto)
    except ValueError:
        raise ErroNegocio(
            "Identificador de desafio invalido.", "id_invalido", status_http=400
        ) from None


def _data_do_formulario(campos: dict[str, str]) -> date:
    """Le `dt_dia` do formulario, no formato do `<input type=date>` (ISO).

    Raises:
        ErroNegocio: ausente ou malformado.
    """
    bruto = (campos.get("dt_dia") or "").strip()
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        raise ErroNegocio(
            f"Data invalida: {bruto!r}. Use o formato AAAA-MM-DD.",
            "data_invalida",
            status_http=400,
        ) from None


def _voltar(recado: str, *, erro: bool = False) -> RedirectResponse:
    """Redireciona para a pagina, carregando o recado do que aconteceu."""
    destino = f"{pagina.BASE}?recado={quote(recado)}"
    if erro:
        destino += "&erro=1"
    return RedirectResponse(destino, status_code=303)


@router.get("/desafios", response_class=HTMLResponse, include_in_schema=False)
async def ver_painel(
    veio_da_query: bool = Depends(exigir_curador),
    sessao: AsyncSession = Depends(obter_sessao),
    recado: Optional[str] = None,
    erro: Optional[str] = None,
) -> HTMLResponse:
    """A pagina do painel: os avisos, as divergencias e a fila.

    ⚠️ **`include_in_schema=False`**: o painel nao entra no OpenAPI publico. Ele
    nao e contrato com aplicativo nenhum, e lista-lo em `/docs` seria anunciar a
    existencia de uma pagina administrativa para quem so deveria ver `/v1`.
    """
    # Autorizou pela query string? Grava o cookie e limpa a URL — o token nao
    # fica no historico do navegador nem no `Referer` da proxima navegacao.
    if veio_da_query:
        resposta = RedirectResponse(pagina.BASE, status_code=303)
        resposta.set_cookie(
            NOME_DO_COOKIE,
            segredo_configurado(),
            max_age=VALIDADE_DO_COOKIE_S,
            httponly=True,
            samesite="strict",
            secure=cookie_seguro(),
            path="/painel",
        )
        return resposta  # type: ignore[return-value]

    dt_hoje = hoje_utc()
    repo = RepositorioPainel(sessao)
    vigia = Vigilancia(sessao)

    html = pagina.render(
        fila=await repo.fila(),
        estado_da_fila=await vigia.estado_da_fila(dt_hoje=dt_hoje),
        contagem=await vigia.contagem_de_auditoria(),
        divergencias=await vigia.divergencias(),
        dt_hoje=dt_hoje,
        recado=recado,
        recado_e_erro=bool(erro),
    )
    # `no-store`: a pagina mostra o **gabarito** dos desafios que ainda vao ao ar,
    # e um cache intermediario guardando isso seria spoiler servido a frio.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.post("/desafios/aprovar", include_in_schema=False)
async def aprovar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Aprova um desafio — e so a partir daqui ele pode ir ao ar."""
    try:
        id_desafio = _uuid_do_formulario(await campos_do_formulario(request))
        resultado = await servico.aprovar(id_desafio)
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True)
    log.info("painel: desafio aprovado", extra={"id_desafio": str(id_desafio)})
    return _voltar(resultado.mensagem)


@router.post("/desafios/descartar", include_in_schema=False)
async def descartar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Descarta com motivo. ⛔ **Nao apaga** (RF-DES-012c)."""
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        resultado = await servico.descartar(
            id_desafio, motivo=campos.get("motivo", "")
        )
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True)
    log.info("painel: desafio descartado", extra={"id_desafio": str(id_desafio)})
    return _voltar(resultado.mensagem)


@router.post("/desafios/agendar", include_in_schema=False)
async def agendar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Poe o desafio num dia, ou o move para outro."""
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        dt_dia = _data_do_formulario(campos)
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True)

    try:
        resultado = await servico.agendar(
            id_desafio, dt_dia=dt_dia, dt_hoje=hoje_utc()
        )
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True)
    except Exception as erro:  # noqa: BLE001
        # ⚠️ O caso concreto: `un001_dia` recusando um dia que ja tem dono. Ele
        # chega como `IntegrityError` do driver, e deixa-lo subir daria 500 numa
        # situacao rotineira de operacao — o dono precisa ler *"esse dia ja esta
        # ocupado"*, e nao um traceback.
        log.warning(
            "painel: agendamento recusado pelo banco",
            extra={"id_desafio": str(id_desafio), "detalhe": type(erro).__name__},
        )
        return _voltar(
            f"Nao deu para agendar em {dt_dia.isoformat()}: aquele dia ja tem "
            "desafio. Tire o de la primeiro — um dia serve um desafio so.",
            erro=True,
        )
    return _voltar(resultado.mensagem)


@router.post("/desafios/desagendar", include_in_schema=False)
async def desagendar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Tira o desafio do calendario, mantendo a aprovacao."""
    try:
        id_desafio = _uuid_do_formulario(await campos_do_formulario(request))
        resultado = await servico.desagendar(id_desafio)
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True)
    return _voltar(resultado.mensagem)
