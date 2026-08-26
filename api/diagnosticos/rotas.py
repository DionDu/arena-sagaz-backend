"""`POST /v1/diagnosticos/motor-nativo` — o app avisando que o binário não subiu.

O prefixo `/v1/diagnosticos` é aplicado no `main.py`.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ENDPOINT PRECISA SER, E POR QUÊ
═══════════════════════════════════════════════════════════════════════════

Ele existe porque a trava da T199 esconde o nível Sagaz quando o motor nativo
não carrega — e, sem isto, escondia **em silêncio**. Foi assim que o Release do
iOS jogou semanas em Dart sem que nada denunciasse.

As cinco regras do desenho estão no cabeçalho da migração
`0016_diagnostico_motor_nativo`. Três delas moram **aqui**:

* **funcionar sem login** (regra 2) — `usuario_atual_opcional`, e nenhum ponto
  do fluxo pede identidade;
* **nunca bloquear** (regra 3) — responde `202 Accepted`, que é literalmente
  "recebi, não prometo mais nada", e o app não trata a resposta;
* **tolerar servidor antigo** (regra 4) — do lado do app: `404`/`501` é
  silêncio. A consequência aqui é que nada nesta rota pode ser pré-requisito de
  outra coisa.

A regra 1 (**deduplicar**) mora no **app**, e é deliberado: deduplicar no
servidor exigiria um identificador estável de aparelho, que a regra 5 proíbe.

⚠️ **Rate limit já cobre esta rota** sem uma linha a mais: o
`RateLimitMiddleware` é global e conta `POST` como escrita, com o teto mais
apertado. Um aparelho em laço não derruba nada — leva `429`, que para o app é
silêncio como qualquer outra falha.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.diagnosticos.modelos import (
    DiagnosticoMotorNativoRequest,
    DiagnosticoResposta,
)
from api.diagnosticos.repositorio import RepositorioDiagnostico
from api.diagnosticos.servico import ServicoDiagnostico
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual_opcional,
)
from api.nucleo.log import obter_logger
from api.nucleo.seguranca_firebase import IdentidadeFirebase

router = APIRouter()
log = obter_logger("api.diagnosticos")

# ⚠️ `X-Platform` aceita `web` (é o ambiente de desenvolvimento), mas a coluna
# `co_plataforma` só conhece android/ios/outra — porque um relato de "web" não
# corresponde a nenhum aparelho que se possa consertar. O mapa abaixo é a
# tradução, e o `outra` existe para o valor não virar `NULL` e sumir da contagem.
_PLATAFORMA_NA_COLUNA = {"android": "android", "ios": "ios"}


def obter_servico_diagnostico(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoDiagnostico:
    """Monta o serviço ligado à sessão da requisição.

    Dependência própria (e não construção dentro da rota) para os testes a
    trocarem por um fake — é assim que a suíte roda sem Postgres.
    """
    return ServicoDiagnostico(repo=RepositorioDiagnostico(sessao), sessao=sessao)


@router.post(
    "/motor-nativo",
    response_model=DiagnosticoResposta,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Relata que um motor nativo não carregou neste aparelho",
)
async def relatar_motor_nativo(
    corpo: DiagnosticoMotorNativoRequest,
    resposta: Response,
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    identidade: Optional[IdentidadeFirebase] = Depends(usuario_atual_opcional),
    servico: ServicoDiagnostico = Depends(obter_servico_diagnostico),
) -> DiagnosticoResposta:
    """Registra um relato e devolve `202` com o id gerado.

    `202 Accepted` e não `201 Created` de propósito: `201` promete um recurso
    que o cliente pode ir buscar, e não há `GET` nenhum aqui — isto é uma caixa
    de entrada de diagnóstico, não um recurso do app.
    """
    # ── Onde, a partir do cabeçalho obrigatório ─────────────────────────────
    #
    # A plataforma e a versão do app NÃO vêm do corpo: elas já viajam em todo
    # pedido do app, e pedi-las duas vezes criaria duas fontes para o mesmo
    # dado — e a segunda é a que fica errada quando as duas discordam.
    plataforma = _PLATAFORMA_NA_COLUNA.get(contexto.plataforma, "outra")

    id_diagnostico = await servico.registrar_motor_nativo(
        uid=identidade.uid if identidade is not None else None,
        dados={
            "co_jogo": corpo.jogo,
            "co_motor": corpo.motor,
            "co_motivo": corpo.motivo,
            "de_motivo": corpo.detalhe,
            "co_versao_binario_esperada": corpo.versao_binario_esperada,
            "co_versao_binario_encontrada": corpo.versao_binario_encontrada,
            "co_plataforma": plataforma,
            "co_versao_so": corpo.versao_so,
            "no_modelo_aparelho": corpo.modelo_aparelho,
            "co_abi": corpo.abi,
            "co_versao_app": contexto.versao_app,
            "co_flavor": corpo.flavor,
            "co_modo_build": corpo.modo_build,
        },
    )

    # ⚠️ Log de servidor em nível INFO, e não WARNING. Isto **não é um erro do
    # servidor**: é o app funcionando como desenhado (caiu para o motor Dart e
    # avisou). Marcá-lo como WARNING encheria o painel de alertas de uma coisa
    # que ninguém precisa acordar para ver — e alerta que sempre toca é alerta
    # que se aprende a ignorar.
    log.info(
        "motor nativo indisponivel: jogo=%s motor=%s motivo=%s plataforma=%s "
        "abi=%s app=%s",
        corpo.jogo,
        corpo.motor,
        corpo.motivo,
        plataforma,
        corpo.abi,
        contexto.versao_app,
    )

    # ⚠️ `no-store`: nada aqui é cacheável, e um proxy que guardasse o `202`
    # faria os relatos seguintes nunca chegarem.
    resposta.headers["Cache-Control"] = "no-store"
    return DiagnosticoResposta(id_diagnostico=id_diagnostico)
