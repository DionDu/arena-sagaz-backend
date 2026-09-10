"""DA LINHA DO BANCO PARA A RESPOSTA — a traducao, num lugar so (T042).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO NAO MORA DENTRO DA ROTA
═══════════════════════════════════════════════════════════════════════════

As **tres** leituras (`/hoje`, `/proximos`, `/{id}`) devolvem a mesma coisa, e
uma traducao escrita tres vezes divergiria — a que divergisse serviria um campo
a menos para uma das rotas, e o aplicativo veria o mesmo desafio diferente
conforme a porta por onde entrou.

⚠️ **E aqui que a ausencia do gabarito e garantida**: esta funcao nunca recebe
`js_solucao`, porque as consultas de `repositorio.py` nao o selecionam. Duas
barreiras para a mesma coisa, de proposito — a segunda existe para o dia em que
alguem acrescentar a coluna a consulta sem perceber.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from api.desafios.modelos_resposta import (
    COLECAO_DESAFIO_DO_DIA,
    FORMA_VERIFICACAO_V1,
    DesafioPublicado,
    ObjetivoPublicado,
)

#: Os jogos em que `co_variante` significa **tamanho de tabuleiro**.
#:
#: ⚠️ E um conjunto, e nao um `if co_jogo == "pontinhos"`, porque o proximo jogo
#: com tabuleiros de tamanhos diferentes entra aqui numa linha. ⛔ O campo
#: `variante` continua vindo **sempre**, generico: `tamanho` e um apelido que o
#: contrato deu, e nao uma segunda informacao.
JOGOS_COM_TAMANHO = frozenset({"pontinhos"})


def para_resposta(
    linha: Mapping[str, Any], *, agora: datetime
) -> DesafioPublicado:
    """Converte uma linha das consultas publicas na resposta do aplicativo.

    Args:
        linha: o que `repositorio.py` devolveu.
        agora: o instante do servidor — **o mesmo** para todos os itens de uma
            resposta. ⚠️ Ler o relogio por item faria dois desafios da mesma
            resposta trazerem `agora_no_servidor` diferentes, e o aplicativo, que
            calibra a contagem regressiva pela **diferenca** entre os dois
            instantes, calibraria cada um com uma base ligeiramente distinta.

    Returns:
        A resposta, sem gabarito.

    ⚠️ **`tabuleiro` e `posicao` sao excludentes**, e `formato_posicao` diz qual
    veio. A FEN cabe numa string; a posicao do Pontinhos, nao — a posse de uma
    caixa e historico, e so a sequencia a descreve.
    """
    co_formato = linha["co_formato_posicao"]
    js_posicao = linha["js_posicao_inicial"] or {}

    if co_formato == "fen":
        tabuleiro = js_posicao.get("fen")
        posicao = None
    else:
        tabuleiro = None
        posicao = js_posicao

    co_jogo = linha["co_jogo"]
    co_variante = linha["co_variante"]

    return DesafioPublicado(
        id_desafio=linha["id_desafio"],
        jogo=co_jogo,
        modalidade=linha["co_modalidade"],
        tipo=linha["co_tipo_desafio"],
        forma_verificacao=FORMA_VERIFICACAO_V1,
        parametros=linha["js_chegada"],
        formato_posicao=co_formato,
        tabuleiro=tabuleiro,
        posicao=posicao,
        tamanho=co_variante if co_jogo in JOGOS_COM_TAMANHO else None,
        variante=co_variante,
        objetivo=ObjetivoPublicado(
            chave=linha["co_chave_objetivo"],
            valores=linha["js_objetivo"] or {},
        ),
        personagem=linha["co_personagem"],
        semente=linha["nu_semente"],
        versao_minima_app=linha["co_versao_minima"],
        versao_perfil=linha["co_versao_perfil"],
        teto_log_meios_lances=linha["nu_teto_log"],
        encerra_em=linha["dh_encerramento"],
        agora_no_servidor=agora,
        reprise=linha["ic_reprise"],
        colecao=COLECAO_DESAFIO_DO_DIA,
        id_desafio_dia=linha["id_desafio_dia"],
    )
