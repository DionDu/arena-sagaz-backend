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

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qsl, quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.painel import execucao_do_job, pagina
from api.desafios.painel.datas import data_br, ler_data
from api.desafios.painel.estatisticas import EstatisticasDoDia
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


def _voltar(
    recado: str,
    *,
    erro: bool = False,
    campos: Optional[dict[str, str]] = None,
) -> RedirectResponse:
    """Redireciona para a pagina, no MESMO dia (ou desafio) de onde a acao veio.

    ⚠️ **Voltar para o dia e o que torna o calendario usavel** (02/10/2026):
    sem isso, cada descarte jogaria o dono de volta a "hoje", e ele teria de
    achar de novo no calendario o dia em que estava trabalhando.

    ⚠️ Os dois campos de volta sao conferidos antes de entrar na URL — uma data
    ISO valida e um UUID valido —, porque vem do formulario, isto e, de fora.
    """
    destino = f"{pagina.BASE}?recado={quote(recado)}"
    campos = campos or {}
    dia = ler_data(campos.get("voltar"))
    if dia is not None:
        destino += f"&dia={dia.isoformat()}"
    else:
        try:
            destino += f"&desafio={UUID((campos.get('voltar_desafio') or '').strip())}"
        except ValueError:
            pass
    if erro:
        destino += "&erro=1"
    return RedirectResponse(destino, status_code=303)


def _janela_do_calendario(dt_hoje: date) -> tuple[date, date]:
    """Do 1o dia do mes anterior ao ultimo dia do mes seguinte.

    ⚠️ Le os tres meses sempre; quem decide se o anterior e o seguinte APARECEM
    e `pagina.meses_a_mostrar` (so quando tem desafio neles).
    """

    def primeiro_dia(passo: int) -> date:
        """O dia 1 do mes `passo` meses distante do corrente."""
        # `mes - 1 + passo` vai de 0 a 11 dentro do ano; `divmod` devolve quantos
        # anos andou e o mes resultante (dezembro + 1 = janeiro do ano seguinte).
        anos, resto = divmod(dt_hoje.month - 1 + passo, 12)
        return date(dt_hoje.year + anos, resto + 1, 1)

    # O ultimo dia do mes seguinte e o dia 1 do mes depois dele, menos um dia.
    return primeiro_dia(-1), primeiro_dia(2) - timedelta(days=1)


async def _montar_detalhe(
    sessao: AsyncSession,
    *,
    dt_hoje: date,
    dia: Optional[str],
    desafio: Optional[str],
) -> pagina.DetalheDoDia:
    """Le do banco tudo o que a area principal mostra.

    Args:
        dia: `?dia=` da URL (ISO ou `dd/mm/aaaa`); ausente = hoje.
        desafio: `?desafio=` da URL — abre um desafio pelo id (o que esta sem
            data). Tem precedencia sobre `dia`.

    ⚠️ **As estatisticas so sao lidas para dia que JA COMECOU** (hoje ou antes):
    um dia agendado nao tem tentativa, e sete consultas para responder "zero"
    custariam a troca de dia sem mostrar nada.
    """
    repo = RepositorioPainel(sessao)
    item = None
    dt_dia: Optional[date] = None

    id_desafio: Optional[UUID] = None
    if desafio:
        try:
            id_desafio = UUID(desafio.strip())
        except ValueError:
            id_desafio = None
    if id_desafio is not None:
        item = await repo.desafio_por_id(id_desafio)
        dt_dia = item.dt_dia if item else None
    else:
        dt_dia = ler_data(dia) or dt_hoje
        item = await repo.desafio_do_dia(dt_dia)

    detalhe = pagina.DetalheDoDia(dt_dia=dt_dia, desafio=item)
    if (
        item is not None
        and item.id_desafio_dia is not None
        and item.dt_dia is not None
        and item.dt_dia <= dt_hoje
    ):
        est = EstatisticasDoDia(sessao)
        detalhe = replace(
            detalhe,
            resumo=await est.resumo(id_desafio_dia=item.id_desafio_dia, dt_dia=item.dt_dia),
            quadro=tuple(await est.quadro(item.id_desafio_dia)),
            nao_resolveram=tuple(await est.nao_resolveram(item.id_desafio_dia)),
        )
    elif item is None and dt_dia is not None and dt_dia >= dt_hoje:
        # Dia vazio daqui para a frente: oferece os aprovados da reserva.
        detalhe = replace(detalhe, reserva=tuple(await repo.sem_dia("aprovado")))
    return detalhe


#: `no-store`: a pagina mostra o **gabarito** dos desafios que ainda vao ao ar,
#: e um cache intermediario guardando isso seria spoiler servido a frio.
SEM_CACHE = {"Cache-Control": "no-store"}


@router.get("/desafios", response_class=HTMLResponse, include_in_schema=False)
async def ver_painel(
    veio_da_query: bool = Depends(exigir_curador),
    sessao: AsyncSession = Depends(obter_sessao),
    recado: Optional[str] = None,
    erro: Optional[str] = None,
    dia: Optional[str] = None,
    desafio: Optional[str] = None,
) -> HTMLResponse:
    """A pagina do painel de gestao: a lateral e o dia aberto.

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
    de, ate = _janela_do_calendario(dt_hoje)

    html = pagina.render(
        dt_hoje=dt_hoje,
        detalhe=await _montar_detalhe(sessao, dt_hoje=dt_hoje, dia=dia, desafio=desafio),
        calendario=await repo.calendario(dt_de=de, dt_ate=ate),
        estado_da_fila=await vigia.estado_da_fila(dt_hoje=dt_hoje),
        contagem=await vigia.contagem_de_auditoria(),
        divergencias=await vigia.divergencias(),
        candidatos=await repo.sem_dia("candidato"),
        reserva=await repo.sem_dia("aprovado"),
        descartados=await repo.sem_dia("descartado", limite=20),
        recado=recado,
        recado_e_erro=bool(erro),
    )
    return HTMLResponse(html, headers=SEM_CACHE)


@router.get("/desafios/fragmento", response_class=HTMLResponse, include_in_schema=False)
async def ver_fragmento(
    _: bool = Depends(exigir_curador),
    sessao: AsyncSession = Depends(obter_sessao),
    dia: Optional[str] = None,
    desafio: Optional[str] = None,
) -> HTMLResponse:
    """So a area principal de um dia — o que o script troca ao clicar no calendario.

    ⚠️ E `pagina.render_detalhe`, a MESMA funcao da pagina inteira: o dia aberto
    por clique e o dia aberto por link nao podem divergir.
    """
    dt_hoje = hoje_utc()
    vigia = Vigilancia(sessao)
    estado = await vigia.estado_da_fila(dt_hoje=dt_hoje)
    dt_sugerida = estado.buracos[0] if estado.buracos else dt_hoje
    detalhe = await _montar_detalhe(sessao, dt_hoje=dt_hoje, dia=dia, desafio=desafio)
    return HTMLResponse(
        pagina.render_detalhe(detalhe, dt_hoje=dt_hoje, dt_sugerida=dt_sugerida),
        headers=SEM_CACHE,
    )


@router.get(
    "/desafios/raio-x/{id_tentativa}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def ver_raio_x(
    id_tentativa: str,
    _: bool = Depends(exigir_curador),
    sessao: AsyncSession = Depends(obter_sessao),
    fragmento: Optional[str] = None,
) -> HTMLResponse:
    """O raio-x de uma tentativa: so o pedaco (para o script) ou a pagina inteira.

    ⚠️ Id torto responde a pagina com "nao encontrada", e nao 500: o id vem da
    URL, isto e, de fora.
    """
    try:
        raio = await EstatisticasDoDia(sessao).raio_x(UUID(id_tentativa.strip()))
    except ValueError:
        raio = None
    corpo = pagina.render_raio_x(raio)
    if fragmento:
        return HTMLResponse(corpo, headers=SEM_CACHE)
    return HTMLResponse(pagina.pagina_avulsa("Raio-x da tentativa", corpo), headers=SEM_CACHE)


@router.get("/desafios/geracao", include_in_schema=False)
async def ver_geracao(_: bool = Depends(exigir_curador)) -> JSONResponse:
    """O estado da geracao em JSON — o script pergunta enquanto ela roda."""
    return JSONResponse(execucao_do_job.ESTADO.como_dicionario(), headers=SEM_CACHE)


@router.post("/desafios/aprovar", include_in_schema=False)
async def aprovar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Aprova um desafio (um candidato antigo, ou um descartado reconsiderado)."""
    campos: dict[str, str] = {}
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        resultado = await servico.aprovar(id_desafio)
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True, campos=campos)
    log.info("painel: desafio aprovado", extra={"id_desafio": str(id_desafio)})
    return _voltar(resultado.mensagem, campos=campos)


@router.post("/desafios/aprovar-candidatos", include_in_schema=False)
async def aprovar_candidatos(
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Aprova de uma vez os candidatos de antes da pre-aprovacao (02/10/2026)."""
    resultado = await servico.aprovar_candidatos()
    log.info("painel: candidatos aprovados em lote")
    return _voltar(resultado.mensagem)


@router.post("/desafios/descartar", include_in_schema=False)
async def descartar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Descarta com motivo. ⛔ **Nao apaga** (RF-DES-012c).

    ⚠️ Desde 02/10/2026 e ESTE o ato de curadoria: o desafio nasce aprovado, e o
    descarte abre o buraco que a proxima geracao tapa primeiro.
    """
    campos: dict[str, str] = {}
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        resultado = await servico.descartar(
            id_desafio, motivo=campos.get("motivo", ""), dt_hoje=hoje_utc()
        )
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True, campos=campos)
    log.info("painel: desafio descartado", extra={"id_desafio": str(id_desafio)})
    return _voltar(resultado.mensagem, campos=campos)


@router.post("/desafios/agendar", include_in_schema=False)
async def agendar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Poe o desafio num dia, ou o move para outro."""
    campos: dict[str, str] = {}
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        dt_dia = _data_do_formulario(campos)
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True, campos=campos)

    # ⚠️ Depois de agendar, a pagina abre o dia de DESTINO — e la que o dono quer
    # conferir o resultado.
    destino = {**campos, "voltar": dt_dia.isoformat()}
    try:
        resultado = await servico.agendar(
            id_desafio, dt_dia=dt_dia, dt_hoje=hoje_utc()
        )
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True, campos=campos)
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
            f"Nao deu para agendar em {data_br(dt_dia)}: aquele dia ja tem "
            "desafio. Tire o de la primeiro — um dia serve um desafio so.",
            erro=True,
            campos=campos,
        )
    return _voltar(resultado.mensagem, campos=destino)


@router.post("/desafios/desagendar", include_in_schema=False)
async def desagendar(
    request: Request,
    _autorizado: bool = Depends(exigir_curador),
    servico: ServicoCuradoria = Depends(obter_servico),
) -> RedirectResponse:
    """Tira o desafio do calendario, mantendo a aprovacao."""
    campos: dict[str, str] = {}
    try:
        campos = await campos_do_formulario(request)
        id_desafio = _uuid_do_formulario(campos)
        resultado = await servico.desagendar(id_desafio, dt_hoje=hoje_utc())
    except ErroNegocio as erro:
        return _voltar(erro.detalhe, erro=True, campos=campos)
    return _voltar(resultado.mensagem, campos=campos)


@router.post("/desafios/gerar", include_in_schema=False)
async def gerar(
    _: bool = Depends(exigir_curador),
    campos: dict[str, str] = Depends(campos_do_formulario),
) -> RedirectResponse:
    """Dispara o job de geracao em segundo plano (T040c).

    ⚠️ **Pedido do dono em 16/09/2026**: *"O comando `rodar_job_local.py --dias
    14` eu nao vou conseguir memorizar. Ele precisava estar dentro do painel de
    curadoria."* E em 02/10/2026 as opcoes cresceram para 7, 14, 21 e 28 dias.

    ⛔ **A rota recusa quando `PAINEL_PODE_GERAR` esta desligada** — e nao apenas
    o botao some da tela. Esconder o botao sem fechar a rota e seguranca de
    fachada, e esta rota dispara minutos de CPU no processo que atende o
    aplicativo.

    ⚠️ **Volta na hora.** Quem espera e a thread; a pagina acompanha pelo
    `/geracao` e recarrega sozinha quando a execucao termina.
    """
    bruto = (campos.get("dias") or "").strip()
    try:
        nu_dias = int(bruto)
    except ValueError:
        return _voltar(f"`{bruto}` nao e um numero de dias.", erro=True)
    if nu_dias not in execucao_do_job.DIAS_OFERECIDOS:
        # ⚠️ Recusa o que o botao nao oferece: um `dias=300` digitado na mao
        # gastaria horas de CPU por um formulario que ninguem revisou.
        return _voltar(
            f"{nu_dias} dia(s) nao e uma opcao "
            f"({', '.join(str(d) for d in execucao_do_job.DIAS_OFERECIDOS)}).",
            erro=True,
        )

    try:
        execucao_do_job.disparar(nu_dias)
    except execucao_do_job.GeracaoDesligada as erro:
        return _voltar(str(erro), erro=True)
    except execucao_do_job.JaEstaRodando as erro:
        return _voltar(f"ja ha uma execucao em andamento — {erro}", erro=True)

    return _voltar(
        f"Geracao de {nu_dias} dia(s) comecou. A pagina se atualiza sozinha "
        "quando terminar."
    )
