"""`POST /v1/aparelhos/detalhes` - o envio diário dos detalhes do aparelho (T118).

O prefixo `/v1/aparelhos` é aplicado no `main.py`.

═══════════════════════════════════════════════════════════════════════════
AS CINCO REGRAS DO DIAGNÓSTICO DA 0016, E ONDE CADA UMA MORA
═══════════════════════════════════════════════════════════════════════════

O `data-model.md` §4.3 da spec 010 manda esta rota seguir as cinco regras do
`POST /v1/diagnosticos/motor-nativo` (cabeçalho da migração `0016`):

1. **o app deduplica** - ele manda uma vez por dia (T118a). É economia; a
   **garantia** de uma linha por aparelho por dia é a chave primária da
   `tb004`, e não o app;
2. **funciona sem login** - `usuario_atual_opcional`: o convidado tem
   aparelho, e os detalhes dele valem igual;
3. **nunca bloqueia** - `202 Accepted`, que é literalmente "recebi, não
   prometo mais nada", e o app não trata a resposta;
4. **servidor antigo é silêncio** - do lado do app: `404`/`501` não muda nada
   na tela;
5. **nada aqui é obrigatório para o resto funcionar** - a versão do dia já é
   gravada pela leitura do desafio (`api/desafios/rotas.py`); esta rota só
   acrescenta o que o app 1.4 sabe contar.

⚠️ **Por que esta rota recusa com 400 quando falta o aparelho**, se a regra 3
diz "nunca bloquear": sem o `X-Install-Id` os detalhes não têm onde morar (a
`tb003` é chaveada por ele), e só um app 1.4 com defeito chega aqui sem ele. O
400 é para esse defeito aparecer no log, e o app o trata como qualquer outra
falha: em silêncio.

⚠️ **Rate limit já cobre esta rota** sem uma linha a mais: o
`RateLimitMiddleware` é global e conta `POST` como escrita.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Response, status

from api.aparelhos.dependencias import (
    ler_cabecalhos_do_aparelho,
    obter_servico_aparelho,
)
from api.aparelhos.modelos import DetalhesDoAparelho, DetalhesRegistrados
from api.aparelhos.regras import chave_da_versao
from api.aparelhos.servico import CabecalhosDoAparelho, ServicoAparelho
from api.configuracao import configuracoes
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual_opcional,
)
from api.nucleo.excecoes import ErroNegocio
from api.nucleo.log import obter_logger
from api.nucleo.seguranca_firebase import IdentidadeFirebase

router = APIRouter()
log = obter_logger("api.aparelhos")


def agora_utc() -> datetime:
    """O instante do servidor, em UTC.

    ⚠️ Função com nome - e não `datetime.now(timezone.utc)` solto - para que o
    teste possa fixá-la: o dia local depende do instante, e um teste que use o
    relógio de verdade passa num horário e falha em outro.
    """
    return datetime.now(timezone.utc)


def limites_do_espaco_mb() -> dict[str, int]:
    """O limite de cada plataforma acima do qual o detalhe do espaço é guardado.

    ⚠️ **Lido a cada pedido**, e não guardado na importação do módulo: é uma
    variável do Railway (`ESPACO_APP_DETALHE_MB_ANDROID` e `_IOS`, padrão 150),
    e o teste a troca para provar que cada plataforma lê a sua.

    Dois limites porque a diferença que sobra entre as plataformas vem do cache
    dos SDKs, que no iOS chegou a 509 MB em 02/09/2026 (`data-model.md` §4.2).
    O `web` do desenvolvimento não tem limite, e nunca guarda o detalhe.
    """
    return {
        "android": configuracoes.ESPACO_APP_DETALHE_MB_ANDROID,
        "ios": configuracoes.ESPACO_APP_DETALHE_MB_IOS,
    }


@router.post(
    "/detalhes",
    response_model=DetalhesRegistrados,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Os detalhes do aparelho, uma vez por dia (app 1.4 em diante)",
)
async def registrar_detalhes(
    corpo: DetalhesDoAparelho,
    resposta: Response,
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    cabecalhos: CabecalhosDoAparelho = Depends(ler_cabecalhos_do_aparelho),
    identidade: Optional[IdentidadeFirebase] = Depends(usuario_atual_opcional),
    servico: ServicoAparelho = Depends(obter_servico_aparelho),
) -> DetalhesRegistrados:
    """Grava os detalhes do aparelho e a linha do dia, e devolve `202`.

    `202 Accepted` e não `201 Created` de propósito: `201` promete um recurso
    que o cliente pode ir buscar, e não há `GET` nenhum aqui.

    Raises:
        ErroNegocio: 400 sem um `X-Install-Id` legível, ou com uma
            `X-App-Version` que não se lê (ver o cabeçalho do módulo).
    """
    if cabecalhos.id_aparelho is None:
        raise ErroNegocio(
            "Cabeçalho X-Install-Id ausente ou inválido (UUID v4).",
            "aparelho_invalido",
            status_http=400,
        )
    if chave_da_versao(contexto.versao_app) is None:
        raise ErroNegocio(
            "X-App-Version fora da forma 1.2.3 ou 1.2.3+4.",
            "versao_invalida",
            status_http=400,
        )

    registro, guardou_detalhe = await servico.registrar_detalhes(
        versao_app=contexto.versao_app,
        plataforma=contexto.plataforma,
        idioma=contexto.idioma,
        cabecalhos=cabecalhos,
        uid=identidade.uid if identidade is not None else None,
        agora=agora_utc(),
        detalhes=corpo.colunas_do_aparelho(),
        versao_so=corpo.versao_so,
        espaco_app_kb=corpo.espaco_app_kb,
        espaco_app=corpo.espaco_app,
        limites_mb=limites_do_espaco_mb(),
    )

    # INFO, e não WARNING: é o app funcionando como desenhado.
    log.info(
        "detalhes do aparelho: plataforma=%s app=%s dia=%s espaco_kb=%s detalhe=%s",
        contexto.plataforma,
        registro.co_versao_app,
        registro.dt_dia_local,
        corpo.espaco_app_kb,
        guardou_detalhe,
    )

    # ⚠️ `no-store`: nada aqui é cacheável, e um proxy que guardasse o `202`
    # faria os envios seguintes nunca chegarem.
    resposta.headers["Cache-Control"] = "no-store"
    return DetalhesRegistrados(
        dia_local=registro.dt_dia_local,
        detalhe_do_espaco_guardado=guardou_detalhe,
    )
