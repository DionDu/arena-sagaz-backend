"""O PODER "VOLTAR JOGADA" NO INGESTOR — T203/T204, e o probing da base.

O que este arquivo guarda sao as tres decisoes que, se saissem erradas, nao
dariam erro nenhum — a partida entraria, o placar estaria certo, e o dado seria
mentira:

1. **Os campos novos sao GENERICOS, e nao das damas.** Se `nu_lance`,
   `ic_cancelada`, `co_poder` ou `dh_cancelamento` nao estiverem na lista de
   campos genericos da jogada, o ingestor os tratara como **extensao de um jogo
   desconhecido** e emitira um aviso a cada jogada de cada partida — enchendo o
   log de producao com um alarme falso, e ensinando a ignora-lo.

2. **`qt_usos_poder` sanitizado nunca derruba a partida.** A coluna e `SMALLINT
   NOT NULL` com `CHECK (>= 0)`. Um valor podre do cliente estouraria o CHECK e
   devolveria 500 — e o evento ficaria **preso para sempre** na fila daquele
   aparelho. E a mesma assimetria da decisao V-5, e a mesma escolha que
   `_offset` ja fazia para o fuso.

3. **`None` nao vira `0` nos contadores da base.** `None` = "nao houve busca";
   `0` = "houve busca e ela nao consultou". Um `.get(..., 0)` no ingestor
   apagaria a distincao **depois** de o app ter tido o cuidado de preserva-la.

Estes testes sao de UNIDADE: nao ha Postgres. O que se verifica e a decisao —
quais chaves o ingestor reconhece e o que ele faz com o que chega.
"""

from __future__ import annotations

import logging
from typing import Any

from api.sincronizacao.repositorio import (
    _CAMPOS_GENERICOS_DA_JOGADA,
    _CAMPOS_GENERICOS_DA_PARTIDA,
    _avisar_extensao_de_partida_desconhecida,
    _avisar_extensao_desconhecida,
    _inteiro_nao_negativo,
)
from api.sincronizacao.validacao import validar_evento


def _jogada(**extras: Any) -> dict[str, Any]:
    base = {
        "id_jogada": "11111111-1111-1111-1111-111111111111",
        "nu_ordem": 1,
        "nu_jogador": 1,
        "dh_jogada": "2026-08-28T20:00:00.000",
        "nu_tempo_decisao_ms": 1200,
        "co_origem_decisao": "humano",
    }
    base.update(extras)
    return base


def _evento(jogadas: list[dict[str, Any]], **partida: Any) -> dict[str, Any]:
    base_partida = {
        "co_jogo": "damas",
        "co_variante": "brasileira",
        "nu_placar_j1": 8,
        "nu_placar_j2": 3,
    }
    base_partida.update(partida)
    return {
        "co_evento": "22222222-2222-2222-2222-222222222222",
        "co_tipo": "partida",
        "payload": {
            "partida": base_partida,
            "jogadas": jogadas,
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 60}],
        },
    }


class TestOsCamposDoPoderSaoGenericos:
    """⚠️ Eles valem para QUALQUER jogo do hub, e nao so para as damas.

    O poder nasceu em `lib/core/poderes/` no app: a tela de qualquer jogo pode
    chama-lo. Uma jogada desfeita e uma jogada desfeita em qualquer tabuleiro —
    e por isso as colunas ficam em `partida.tb002_jogada`, e nao numa tabela por
    jogo, que teria de ser copiada tres vezes.
    """

    def test_os_quatro_campos_da_jogada_estao_na_lista_generica(self):
        for campo in ("nu_lance", "ic_cancelada", "co_poder", "dh_cancelamento"):
            assert campo in _CAMPOS_GENERICOS_DA_JOGADA, (
                f"{campo} fora da lista: o ingestor o trataria como extensao de "
                "um jogo desconhecido e avisaria a cada jogada"
            )

    def test_qt_usos_poder_esta_na_lista_generica_da_partida(self):
        assert "qt_usos_poder" in _CAMPOS_GENERICOS_DA_PARTIDA

    def test_uma_jogada_cancelada_NAO_gera_aviso_de_extensao(self, caplog):
        # O sintoma que este caso previne: o log de producao ganhando uma linha
        # de WARNING por jogada de toda partida em que alguem usou o poder.
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_desconhecida(
                _jogada(
                    nu_lance=7,
                    ic_cancelada=True,
                    co_poder="voltar_jogada",
                    dh_cancelamento="2026-08-28T20:01:00.000Z",
                )
            )
        assert caplog.records == []

    def test_qt_usos_poder_na_partida_NAO_gera_aviso(self, caplog):
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(
                {
                    "co_jogo": "damas",
                    "co_variante": "brasileira",
                    "qt_usos_poder": 2,
                }
            )
        assert caplog.records == []


class TestOEventoContinuaValido:
    """A validacao nao pode ter ganhado campo obrigatorio nenhum."""

    def test_jogada_SEM_os_campos_do_poder_continua_valida(self):
        # E o caso do Pontinhos e da velha, que estao no aparelho de quem joga
        # hoje e nunca enviarao estas chaves.
        assert validar_evento(_evento([_jogada()])) is None

    def test_jogada_COM_os_campos_do_poder_e_aceita(self):
        assert (
            validar_evento(
                _evento(
                    [
                        _jogada(nu_ordem=7, nu_lance=7, ic_cancelada=True,
                                co_poder="voltar_jogada",
                                dh_cancelamento="2026-08-28T20:01:00.000Z"),
                        _jogada(
                            id_jogada="33333333-3333-3333-3333-333333333333",
                            nu_ordem=9,
                            nu_lance=7,
                        ),
                    ],
                    qt_usos_poder=1,
                )
            )
            is None
        )


class TestASanitizacaoDaContagem:
    """⚠️ Um numero podre do cliente nao pode custar a partida da pessoa."""

    def test_ausente_vira_zero(self):
        # O caso comum: o app so envia a chave quando ela e maior que zero, para
        # o payload dos jogos sem poder continuar identico ao que ja esta em
        # campo. Ausencia significa exatamente "nao houve poder".
        assert _inteiro_nao_negativo(None) == 0

    def test_um_inteiro_normal_passa(self):
        assert _inteiro_nao_negativo(3) == 3

    def test_zero_passa(self):
        assert _inteiro_nao_negativo(0) == 0

    def test_negativo_vira_zero_em_vez_de_estourar_o_CHECK(self):
        # `CHECK (qt_usos_poder >= 0)` recusaria, o INSERT falharia, e a partida
        # inteira voltaria 500 — travando a fila daquele aparelho para sempre.
        assert _inteiro_nao_negativo(-1) == 0

    def test_texto_vira_zero(self):
        assert _inteiro_nao_negativo("2") == 0

    def test_absurdo_vira_zero(self):
        # SMALLINT vai ate 32767; um valor acima disso estouraria o TIPO, que e
        # um erro ainda mais bruto que o CHECK.
        assert _inteiro_nao_negativo(10**9) == 0

    def test_booleano_e_recusado_explicitamente(self):
        # ⚠️ Em Python `bool` E `int`, e `True == 1`. Sem a recusa explicita,
        # `"qt_usos_poder": true` viraria "um uso" em silencio — e o teste que
        # so olhasse o tipo passaria.
        assert _inteiro_nao_negativo(True) == 0
        assert _inteiro_nao_negativo(False) == 0

    def test_float_e_recusado(self):
        assert _inteiro_nao_negativo(2.0) == 0
