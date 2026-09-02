"""O CONTRATO DA EXTENSAO DAS DAMAS — e o ponto cego que elas revelaram.

As damas sao o 3o jogo do hub, e o **primeiro com extensao de PARTIDA**. Ate
20/08/2026 os dois jogos publicados estendiam apenas a *jogada*; a partida so
tinha campos genericos. Isso deixou um ponto cego que este arquivo guarda.

AS QUATRO TRAVESSIAS
--------------------
- **D-1 — app ANTIGO x backend NOVO.** O app publicado nao conhece as damas e
  nunca envia `partida["damas"]` nem `jogada["damas"]`. Tem de continuar sendo
  aceito exatamente como antes, sem nenhum campo novo obrigatorio.
- **D-2 — app NOVO x backend ANTIGO.** O inverso, e o mais perigoso: um backend
  que ainda nao conhece a chave `"damas"` **ignora** a extensao. A partida entra;
  so a telemetria evapora. Rejeitar faria o app **descartar a partida inteira**
  (decisao V-5).
- **D-3 — ⚠️ o PONTO CEGO: a extensao de PARTIDA desconhecida.** Antes das damas,
  `_avisar_extensao_desconhecida` so varria a *jogada*. Uma extensao de partida
  de um jogo futuro passava em silencio **total** — nem erro, nem rastro. Nao
  era risco teorico: as damas sao justamente o primeiro caso, e se a varredura
  nao tivesse sido estendida, o 4o jogo descobriria isso em producao.
- **D-4 — os codigos desconhecidos.** Viram o sentinela `9999`. Sem ele a FK
  estoura, o app toma 500, e o evento fica **preso para sempre** na fila daquele
  aparelho — a partida daquela pessoa nunca sobe.

⚠️ **DUAS dimensoes, e elas sao das DAMAS.** Usar a dimensao de outro jogo faria
todo codigo cair no sentinela: a telemetria nasceria cega, sem erro e sem log de
falha. E o mesmo defeito que a spec 007 ja documentou para as acoes da velha.

Estes testes sao de UNIDADE: nao ha Postgres. O que se verifica e a **decisao** —
quais chaves sao reconhecidas, o que a validacao aceita, e para onde aponta cada
dimensao. O caminho ate o `INSERT` e coberto pelos testes de integracao.
"""

from __future__ import annotations

import logging
from typing import Any

from api.sincronizacao import dimensoes
from api.sincronizacao.repositorio import (
    _EXTENSOES_CONHECIDAS,
    _TETO_DE_RECUSAS_POR_PARTIDA,
    _avisar_extensao_de_partida_desconhecida,
    _avisar_extensao_desconhecida,
)
from api.sincronizacao.validacao import validar_evento

# ── Amostras fieis ao que o APP produz ──────────────────────────────────────
#
# ⚠️ Os nomes e os tipos abaixo foram conferidos contra o `paraPayload()` de
# `lib/modulos/jogos/damas/log/` em 20/08/2026. Inventar o payload aqui faria o
# teste provar que o backend concorda com o teste — nao com o app.

EXTENSAO_PARTIDA_DAMAS: dict[str, Any] = {
    "co_versao_motor": "1.0.0",
    "co_versao_contrato": "1.0.0",
    "co_fen_inicial": (
        "W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12"
    ),
    "co_cor_j1": "branca",
    "nu_semente_partida": None,
    "js_extra": None,
    # ⚠️ As recusas viajam DENTRO do objeto do jogo (decisao D-23), e nao como
    # chave de raiz do payload — a raiz nao e do jogo.
    "recusas": [],
}

EXTENSAO_JOGADA_DAMAS: dict[str, Any] = {
    "co_jogador": -1,
    "co_lance": "18x9x2",
    "co_fen_antes": "W:W21,22,K27,30:B4,K9,15",
    "qt_captura_pedra": 2,
    "qt_captura_dama": 1,
    "ic_promoveu": True,
    "co_tipo_peca_inicio": "pedra",
    "qt_nos_visitados": 94812,
    "nu_profundidade_atingida": 9,
    "co_motivo_parada_busca": "nos",
    "nu_tempo_busca_ms": 612,
    "nu_avaliacao_brancas": -40,
    "nu_semente": 873421905,
    "js_extra": None,
}


def _jogada(**extras: Any) -> dict[str, Any]:
    """Uma jogada generica valida, com o que os extras acrescentarem."""
    base = {
        "id_jogada": "11111111-1111-1111-1111-111111111111",
        "nu_ordem": 1,
        "nu_jogador": 1,
        "dh_jogada": "2026-08-20T10:00:00.000",
        "nu_tempo_decisao_ms": 1200,
        "co_origem_decisao": "humano",
    }
    base.update(extras)
    return base


def _partida(**extras: Any) -> dict[str, Any]:
    base = {
        "co_jogo": "damas",
        "co_variante": "brasileira",
        "nu_placar_j1": 1,
        "nu_placar_j2": 0,
    }
    base.update(extras)
    return base


def _evento(
    co_evento: str,
    jogadas: list[dict[str, Any]],
    partida: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "co_evento": co_evento,
        "co_tipo": "partida",
        "payload": {
            "partida": partida if partida is not None else _partida(),
            "jogadas": jogadas,
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 60}],
        },
    }


class TestD1AppAntigoBackendNovo:
    """Quem nao atualizar o app tem de continuar sincronizando igual."""

    def test_partida_sem_extensao_nenhuma_continua_valida(self):
        """O payload do app publicado, byte a byte como ele e hoje.

        Se este caso falhar, a migracao 0012 quebrou quem esta em campo — que e
        exatamente o que a diretriz do dono proibe.
        """
        evento = _evento(
            "ev-app-antigo",
            [_jogada()],
            partida=_partida(co_jogo="pontinhos", co_variante="5x5"),
        )
        assert validar_evento(evento) is None

    def test_nenhum_campo_das_damas_virou_obrigatorio(self):
        """A extensao e OPCIONAL nos dois niveis.

        Um campo novo obrigatorio na partida generica invalidaria todo evento de
        app antigo — e o sintoma seria a fila de sincronizacao travando para
        todo mundo que nao atualizou, de uma vez.
        """
        evento = _evento("ev-sem-damas", [_jogada()])
        assert validar_evento(evento) is None


class TestD2AppNovoBackendAntigo:
    """A extensao que o backend nao conhece e IGNORADA, nunca rejeitada."""

    def test_extensao_de_jogada_desconhecida_nao_invalida_o_evento(self):
        evento = _evento("ev-futuro-j", [_jogada(xadrez={"co_casa": "e4"})])
        assert validar_evento(evento) is None, (
            "rejeitar aqui faria o app DESCARTAR a partida inteira do usuario "
            "para nao perder um detalhe que este backend nao saberia guardar"
        )

    def test_extensao_de_PARTIDA_desconhecida_nao_invalida_o_evento(self):
        """O mesmo, um nivel acima — o caso que nao existia antes das damas."""
        evento = _evento(
            "ev-futuro-p",
            [_jogada()],
            partida=_partida(xadrez={"co_abertura": "siciliana"}),
        )
        assert validar_evento(evento) is None

    def test_as_damas_sao_extensao_CONHECIDA(self):
        assert "damas" in _EXTENSOES_CONHECIDAS

    def test_as_extensoes_conhecidas_nao_geram_aviso(self, caplog):
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_desconhecida(_jogada(damas=EXTENSAO_JOGADA_DAMAS))
            _avisar_extensao_de_partida_desconhecida(
                _partida(damas=EXTENSAO_PARTIDA_DAMAS)
            )
        assert not caplog.records, (
            "as damas sao conhecidas desde a migracao 0012; avisar sobre elas "
            "encheria o log de alarme falso a cada partida"
        )


class TestD3OPontoCegoDaExtensaoDePartida:
    """⚠️ A varredura da PARTIDA — que nao existia antes das damas."""

    def test_extensao_de_partida_desconhecida_gera_AVISO(self, caplog):
        """Ignorar nao pode ser SILENCIOSO — e aqui era silencio total.

        Antes de 20/08/2026 nao havia varredura nenhuma no nivel da partida.
        Um app que mandasse `partida["xadrez"]` nao dava erro **e nao deixava
        rastro**: nada indicava que havia um app em campo mais novo que o
        backend, nem que faltava um ingestor.

        ⚠️ O jogo usado aqui e `xadrez` porque ele **nao existe**. No dia em que
        existir, este caso falha e o exemplo tera de ser trocado — e isso e o
        preco, ja pago duas vezes neste projeto, de guardar a tolerancia ao
        desconhecido com um exemplo concreto.
        """
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(
                _partida(xadrez={"co_abertura": "siciliana"})
            )
        # `getMessage()` aplica os args ao formato; `r.message % r.args` faria a
        # interpolacao duas vezes e estouraria.
        mensagens = [r.getMessage() for r in caplog.records]
        assert any("xadrez" in m for m in mensagens)
        assert any("partida" in m for m in mensagens), (
            "o aviso precisa dizer em que NIVEL a extensao apareceu; sem isso, "
            "quem le o log nao sabe onde procurar o ingestor que falta"
        )

    def test_campo_generico_solto_da_partida_nao_e_confundido_com_extensao(
        self, caplog
    ):
        """Um campo novo que NAO e dicionario nao e extensao de jogo.

        Sem esta distincao, qualquer campo escalar acrescentado a partida no
        futuro encheria o log de avisos falsos — e log cheio de alarme falso e
        log que ninguem le. E exatamente a tolerancia a mudancas ADITIVAS que o
        contrato de versionamento da API exige.
        """
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(_partida(nu_campo_futuro=7))
        assert not caplog.records

    def test_o_campo_co_anonimo_do_app_antigo_nao_gera_aviso(self, caplog):
        """A coluna sumiu na migracao 0007, mas o campo ainda chega.

        Ele e ignorado de proposito. Avisar sobre ele encheria o log uma vez por
        partida de todo mundo que nao atualizou — que e a maioria.
        """
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(_partida(co_anonimo="abc"))
        assert not caplog.records


class TestD4AsDimensoesDasDamas:
    """Duas dimensoes, e as duas apontam para o schema das DAMAS."""

    def test_a_dimensao_de_regra_de_recusa_aponta_para_o_schema_certo(self):
        view, col_codigo, col_chave = dimensoes._DIMENSOES["regra_recusa_damas"]
        assert view == "jogo_damas.vw901_regra_recusa"
        assert (col_codigo, col_chave) == ("co_regra", "nu_regra")

    def test_a_dimensao_de_motivo_de_parada_aponta_para_o_schema_certo(self):
        view, col_codigo, col_chave = dimensoes._DIMENSOES["motivo_parada_damas"]
        assert view == "jogo_damas.vw902_motivo_parada_busca"
        assert (col_codigo, col_chave) == (
            "co_motivo_parada_busca",
            "nu_motivo_parada_busca",
        )

    def test_as_dimensoes_das_damas_NAO_colidem_com_as_dos_outros_jogos(self):
        """O erro que este teste existe para pegar.

        Se as damas usassem a dimensao de outro jogo, TODO codigo delas cairia no
        sentinela 9999 — sem erro, sem excecao e sem log de falha. A telemetria
        do jogo novo nasceria cega, e uma coluna inteira de "desconhecido" e
        muito facil de nao notar.
        """
        das_damas = {
            dimensoes._DIMENSOES[k][0]
            for k in ("regra_recusa_damas", "motivo_parada_damas")
        }
        dos_outros = {
            dimensoes._DIMENSOES[k][0]
            for k in ("acao", "acao_pontinhos", "situacao_pontinhos", "acao_velha")
        }
        assert das_damas.isdisjoint(dos_outros)

    def test_toda_dimensao_das_damas_le_por_VIEW(self):
        """Regra do ecossistema: le-se na `vw`, escreve-se na `tb`."""
        for chave in ("regra_recusa_damas", "motivo_parada_damas"):
            view = dimensoes._DIMENSOES[chave][0]
            assert ".vw" in view, f"{chave} le direto da tabela: {view}"


class TestD5OTetoDeRecusas:
    """O servidor nao confia na contagem do cliente."""

    def test_o_teto_do_servidor_bate_com_o_do_app(self):
        """São 50 nos dois lados (RF-DAM-115k).

        ⚠️ **Sao dois tetos, nao um.** O app conta e para de gravar; o servidor
        conta de novo e descarta o excedente. O segundo existe porque um defeito
        em laco num app em campo mandaria milhares de linhas, e quem paga a conta
        do banco e este lado.

        Divergir os numeros nao quebraria nada visivelmente — so faria o log
        parecer truncado sem motivo aparente, o que e pior de diagnosticar.
        """
        assert _TETO_DE_RECUSAS_POR_PARTIDA == 50
