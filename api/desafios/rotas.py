"""AS TRES LEITURAS DO APLICATIVO — `/v1/desafios/*` (T042).

Conforme `specs/009-desafio-do-dia/contracts/desafio-publicado.md`.

    GET /v1/desafios/hoje       → o desafio de hoje
    GET /v1/desafios/proximos   → o cache invisivel (RF-DES-120)
    GET /v1/desafios/{id}       → o historico

═══════════════════════════════════════════════════════════════════════════
⚠️ CONVIDADO LE, E ISSO E DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

As tres aceitam `usuario_atual_opcional`: o desafio publicado e o **mesmo** para
todo mundo, e nada na resposta depende de quem pergunta. Exigir login aqui
transformaria "ver o desafio de hoje" num muro antes do primeiro contato — e o
aplicativo tem modo convidado justamente para nao ter esse muro.

⚠️ **Resolver e outra coisa**: enviar resolucao exige conta (T043), porque ai a
resposta passa a ser sobre uma pessoa.

═══════════════════════════════════════════════════════════════════════════
⚠️ "NAO HA DESAFIO HOJE" E 404 COM CODIGO PROPRIO, E NAO 200 COM `null`
═══════════════════════════════════════════════════════════════════════════

E o pior caso operacional da spec (fila vazia **e** sem reprise), e o aplicativo
precisa distinguir tres situacoes que a tela trata de formas diferentes:

    sem rede            → erro de transporte, e o cache entra
    404 sem_desafio_hoje → **ha servidor, e nao ha desafio**: texto honesto
    200                 → joga

Um `200` com corpo vazio confundiria a segunda com a terceira, e a tela mostraria
o esqueleto de um desafio que nao existe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_envio import (
    EnvioDeDica,
    EnvioDeResolucao,
    RespostaDeResolucao,
)
from api.desafios.modelos_resposta import DesafioPublicado, ProximosPublicados
from api.desafios.publicacao import para_resposta
from api.desafios.repositorio import DIAS_DE_CACHE, RepositorioDesafio
from api.desafios.quadro import RepositorioQuadro
from api.desafios.repositorio_envio import RepositorioEnvio
from api.desafios.servico_envio import ServicoEnvio
from api.desafios.servico_quadro import ServicoQuadro
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
    usuario_atual_opcional,
)
from api.nucleo.excecoes import ErroNaoEncontrado
from api.nucleo.log import obter_logger
from api.nucleo.seguranca_firebase import IdentidadeFirebase

log = obter_logger("api.desafios")

router = APIRouter()

#: Quanto tempo uma resposta pode ficar guardada por um intermediario.
#:
#: ⚠️ **Curto de proposito.** O desafio nao muda dentro do dia, mas
#: `agora_no_servidor` sim — e e a **diferenca** entre ele e `encerra_em` que
#: calibra a contagem regressiva no aparelho (RF-DES-008). Uma resposta guardada
#: por meia hora entregaria um `agora` de meia hora atras, e a contagem nasceria
#: adiantada.
CACHE_SEGUNDOS = 30


def obter_repositorio(
    sessao: AsyncSession = Depends(obter_sessao),
) -> RepositorioDesafio:
    """Monta o repositorio ligado a sessao da requisicao.

    Dependencia propria para os testes a trocarem por um duble sem banco.
    """
    return RepositorioDesafio(sessao)


def agora_utc() -> datetime:
    """O instante do servidor, em UTC.

    ⚠️ Funcao com nome — e nao `datetime.now(timezone.utc)` espalhado — para que
    o teste possa fixa-la e para que **um** instante sirva a resposta inteira.
    """
    return datetime.now(timezone.utc)


@router.get("/hoje", response_model=DesafioPublicado)
async def desafio_de_hoje(
    resposta: Response,
    repo: RepositorioDesafio = Depends(obter_repositorio),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    _identidade=Depends(usuario_atual_opcional),
) -> DesafioPublicado:
    """O desafio de hoje — a porta principal do laco diario.

    Raises:
        ErroNaoEncontrado: nao ha desafio aprovado no ar. Ver a nota no topo
            sobre por que isto e 404 e nao 200 com corpo vazio.
    """
    agora = agora_utc()
    linha = await repo.de_hoje(agora=agora)
    if linha is None:
        raise ErroNaoEncontrado(
            "Nao ha desafio publicado para hoje.", "sem_desafio_hoje"
        )
    resposta.headers["Cache-Control"] = f"public, max-age={CACHE_SEGUNDOS}"
    return para_resposta(linha, agora=agora)


@router.get("/proximos", response_model=ProximosPublicados)
async def proximos_desafios(
    resposta: Response,
    repo: RepositorioDesafio = Depends(obter_repositorio),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    _identidade=Depends(usuario_atual_opcional),
) -> ProximosPublicados:
    """O cache invisivel: os proximos dias, para jogar sem rede (RF-DES-120).

    ⚠️ **"Invisivel" e sobre EXIBIR, e nao sobre ter** (RF-DES-009): o aplicativo
    guarda e nao mostra. ⛔ O servidor nao consegue impedir a tela de exibir o que
    ja baixou — a garantia mora la —, mas nao entrega mais do que o necessario
    para atravessar um fim de semana sem rede.

    ⚠️ **Lista vazia e resposta valida**, e nao 404: nao ter proximos e o estado
    normal de uma fila que acabou de ser consumida, e um erro ai faria o
    aplicativo tratar operacao rotineira como falha.
    """
    agora = agora_utc()
    linhas = await repo.proximos(dt_hoje=agora.date(), limite=DIAS_DE_CACHE)
    resposta.headers["Cache-Control"] = f"public, max-age={CACHE_SEGUNDOS}"
    return ProximosPublicados(
        agora_no_servidor=agora,
        desafios=[para_resposta(linha, agora=agora) for linha in linhas],
    )


@router.get("/{id_desafio}", response_model=DesafioPublicado)
async def desafio_por_id(
    id_desafio: UUID,
    resposta: Response,
    repo: RepositorioDesafio = Depends(obter_repositorio),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    _identidade=Depends(usuario_atual_opcional),
) -> DesafioPublicado:
    """Um desafio publicado, pelo identificador — o caminho do historico.

    ⚠️ **Declarada por ULTIMO de proposito.** O FastAPI casa as rotas na ordem em
    que foram registradas, e `/{id_desafio}` casa com qualquer coisa: declarada
    antes, ela engoliria `/hoje` e `/proximos` — que chegariam aqui como um UUID
    invalido, virando 422 numa rota que existe.

    Raises:
        ErroNaoEncontrado: o desafio nao existe **ou** nao esta aprovado. ⚠️ A
            mesma resposta para os dois casos, de proposito: distinguir "nao
            existe" de "existe e nao foi aprovado" contaria a quem perguntou que
            ha um candidato com aquele identificador.
    """
    agora = agora_utc()
    linha = await repo.por_id(id_desafio)
    if linha is None:
        raise ErroNaoEncontrado("Desafio nao encontrado.", "desafio_inexistente")
    resposta.headers["Cache-Control"] = f"public, max-age={CACHE_SEGUNDOS}"
    return para_resposta(linha, agora=agora)


# ═══════════════════════════════════════════════════════════════════════════
# O ENVIO (T043) — e aqui a conta deixa de ser opcional
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Ler o desafio de hoje aceita convidado; **resolver, nao**. A partir daqui a
# resposta e sobre uma pessoa: a resolucao aponta para `conta.tb001_usuario`, a
# chave natural da idempotencia e `(desafio, pessoa)`, e o quadro do dia so faz
# sentido com identidade.
#
# ⚠️ **O aplicativo nao espera esta resposta** (RF-DES-030): o veredito ja
# apareceu na tela, e o envio sobe pelo outbox. Por isso o codigo HTTP importa
# mais que o corpo — e o `409` de "a partida ainda nao chegou" e o unico que pede
# reenvio.


def obter_servico_envio(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoEnvio:
    """Monta o servico de escrita ligado a sessao da requisicao."""
    return ServicoEnvio(RepositorioEnvio(sessao))


@router.post("/{id_desafio}/resolucao", response_model=RespostaDeResolucao)
async def enviar_resolucao(
    id_desafio: UUID,
    envio: EnvioDeResolucao,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    servico: ServicoEnvio = Depends(obter_servico_envio),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
) -> RespostaDeResolucao:
    """Registra a resolucao (ou a tentativa que falhou) e o extrato de XP.

    ⚠️ **`aceita: true` significa "recebi e gravei", nunca "conferi"**
    (RF-DES-036). A validacao roda fora do caminho da requisicao, em lote e com
    atraso: e **auditoria**, nao liberacao. E se ela discordar, ⛔ **vale o
    aplicativo** (RF-DES-032) — a pessoa continua no quadro e a divergencia vira
    linha no painel de curadoria.

    Raises:
        PartidaAindaNaoChegou: 409. ⚠️ **Reenvie**, nao descarte.
        ErroNegocio: 400, dado impossivel (RF-DES-033).
    """
    resultado = await servico.registrar_resolucao(
        id_desafio=id_desafio, id_usuario=identidade.uid, envio=envio
    )
    log.info(
        "desafio: resolucao registrada",
        extra={
            "id_desafio": str(id_desafio),
            "veredito": envio.veredito,
            "ja_existia": resultado.resposta.ja_existia,
            "parcelas": resultado.parcelas_gravadas,
        },
    )
    return resultado.resposta


@router.post("/{id_desafio}/dica", status_code=204)
async def registrar_dica(
    id_desafio: UUID,
    envio: EnvioDeDica,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    servico: ServicoEnvio = Depends(obter_servico_envio),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
) -> None:
    """Registra que a 1a ou a 2a dica foi gasta.

    ⚠️ **Chamada no instante em que o premiado se COMPLETA** — a rede ja esta la
    naquele momento, e e o unico instante em que se sabe que a recompensa foi
    concedida. ⛔ Premiado interrompido **nao consome** (RF-DES-056): quem chama
    esta rota e o callback de recompensa, e nunca a abertura do anuncio.

    ⚠️ **O contador vive no servidor** porque o teto de duas dicas e **por
    desafio** (RF-DES-057), e tentar e ilimitado no dia: fechar o aplicativo
    encerra a tentativa, nao o dia, e um contador local daria dicas infinitas a
    quem reabrisse.

    Responde `204` — nao ha corpo a devolver, e o aplicativo nao espera nada.
    """
    nova = await servico.registrar_dica(
        id_desafio=id_desafio, id_usuario=identidade.uid, envio=envio
    )
    log.info(
        "desafio: dica registrada",
        extra={
            "id_desafio": str(id_desafio),
            "grau": envio.grau,
            "nova": nova,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# O QUADRO E O REPLAY (T044)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Exigem rede** (RF-DES-123) — sao dados de outras pessoas. Isso **nao
# impede jogar**: o botao de jogar continua funcionando sem rede, porque o
# desafio ja foi baixado.
#
# ⚠️ **Convidado VE o quadro** e nao tem linha propria nem replays. Ver e social;
# ter linha exige identidade, e reagir tambem (RF-DES-084).


def obter_servico_quadro(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoQuadro:
    """Monta o servico do quadro ligado a sessao da requisicao."""
    return ServicoQuadro(RepositorioQuadro(sessao))


@router.get("/{id_desafio}/quadro")
async def quadro_do_dia(
    id_desafio: UUID,
    servico: ServicoQuadro = Depends(obter_servico_quadro),
    identidade=Depends(usuario_atual_opcional),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
) -> dict:
    """O quadro do dia: os quatro mascotes e quem resolveu.

    ⛔ As quatro regras que a tela nao pode contornar moram no servidor: zero
    nunca aparece, fracao abaixo de 20 tentativas nao e servida, so quem resolveu
    aparece, e `ic_publico` desligado some — inclusive no meio do dia.
    """
    return await servico.montar(
        id_desafio=id_desafio,
        id_usuario=identidade.uid if identidade else None,
        agora=agora_utc(),
    )


@router.get("/{id_desafio}/replay/{sujeito:path}")
async def replay_do_sujeito(
    id_desafio: UUID,
    sujeito: str,
    servico: ServicoQuadro = Depends(obter_servico_quadro),
    identidade=Depends(usuario_atual_opcional),
    _contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
) -> dict:
    """O Raio-X de um sujeito — `eu` · `jogador/{id}` · `desafio`.

    ⚠️ **`{sujeito:path}` porque `jogador/{id}` tem barra dentro.** O contrato
    escreve o sujeito assim, e um parametro comum pararia na primeira `/` — a
    rota nem casaria, e o erro seria um 404 sem explicacao.

    ⚠️ **A trava de spoiler e resolvida AQUI** (403), e nao na tela: esconder so
    na interface deixaria o dado a um `curl` de distancia, e o quadro viraria
    gabarito.
    """
    # `jogador/<id>` chega inteiro; o que o servico quer e o identificador.
    if sujeito.startswith("jogador/"):
        sujeito = sujeito[len("jogador/") :]

    return await servico.replay(
        id_desafio=id_desafio,
        sujeito=sujeito,
        id_usuario=identidade.uid if identidade else None,
        agora=agora_utc(),
    )
