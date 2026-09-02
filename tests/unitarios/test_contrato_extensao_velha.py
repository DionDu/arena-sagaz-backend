"""O CONTRATO DA EXTENSAO DE JOGADA — e a promessa de nao quebrar quem esta em campo.

⚠️ **A diretriz que este arquivo guarda** (dono, 2026-08-06):

    "Todas as alteracoes que estamos fazendo com este novo jogo nao devem
     quebrar o app das pessoas que estao jogando versao mais antiga e nao vao
     atualizar o App."

Isso se traduz em tres travessias, e as tres estao aqui:

- **C-1/C-2 — app ANTIGO x backend NOVO.** O app publicado nao conhece a velha e
  nunca envia `jogada["velha"]`. Ele tem de continuar sendo aceito exatamente
  como antes, sem nenhum campo novo obrigatorio.
- **C-3 — app NOVO x backend ANTIGO.** E o inverso, e o mais perigoso: um
  backend que ainda nao conhece a chave `"velha"` **ignora** a extensao. A
  partida entra; so o `ic_otimo` evapora. Rejeitar faria o app **descartar a
  partida inteira** — e e por isso que ignorar e a decisao (V-5).
- **C-4 — codigo de acao desconhecido.** Vira o sentinela `9999`, e a string
  crua fica em `js_extra`. Sem o sentinela, a FK estoura, o app toma 500 e o
  evento fica **preso para sempre** na fila daquele aparelho.

Estes testes sao de UNIDADE: nao ha Postgres. O que se verifica e a decisao —
quais chaves sao reconhecidas, o que a validacao aceita e rejeita, e para onde
vai um codigo que ninguem cadastrou. O caminho ate o `INSERT` e coberto pelos
testes de integracao.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from api.sincronizacao import dimensoes
from api.sincronizacao.repositorio import (
    _EXTENSOES_CONHECIDAS,
    _avisar_extensao_desconhecida,
)
from api.sincronizacao.validacao import validar_evento


def _jogada(**extras: Any) -> dict[str, Any]:
    """Uma jogada generica valida, com o que os extras acrescentarem."""
    base = {
        "id_jogada": "11111111-1111-1111-1111-111111111111",
        "nu_ordem": 1,
        "nu_jogador": 1,
        "dh_jogada": "2026-08-06T10:00:00.000",
        "nu_tempo_decisao_ms": 1200,
        "co_origem_decisao": "humano",
    }
    base.update(extras)
    return base


def _evento(co_evento: str, jogadas: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "co_evento": co_evento,
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "co_jogo": "velha",
                "nu_placar_j1": 1,
                "nu_placar_j2": 0,
            },
            "jogadas": jogadas,
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 12}],
        },
    }


EXTENSAO_VELHA = {
    "co_jogador": 1,
    "co_celula": "C_2_2",
    "ic_otimo": True,
    "co_acao": None,
    "js_extra": None,
}

EXTENSAO_PONTINHOS = {
    "co_jogador": -1,
    "co_aresta": "H_0_1",
    "nu_caixas_fechadas": 1,
}


class TestSC017LoteMisto:
    """SC-017 — quatro eventos, tres entram, so o quarto e rejeitado."""

    def test_o_lote_de_quatro(self):
        lote = [
            # 1) velha, com extensao
            _evento("ev-velha", [_jogada(velha=EXTENSAO_VELHA)]),
            # 2) pontinhos, com extensao — o app publicado, que nao mudou
            _evento("ev-pontinhos", [_jogada(pontinhos=EXTENSAO_PONTINHOS)]),
            # 3) sem extensao nenhuma — perfeitamente valido
            _evento("ev-sem-ext", [_jogada()]),
            # 4) malformado: sem `co_evento`, o unico campo sem o qual nao ha
            #    idempotencia possivel
            {"co_tipo": "partida", "payload": {}},
        ]

        resultados = [validar_evento(e) for e in lote]

        assert resultados[0] is None, "a velha com extensao tem de ser aceita"
        assert resultados[1] is None, "o Pontinhos continua igual"
        assert resultados[2] is None, "jogada sem extensao e valida"
        assert resultados[3] is not None, "o malformado tem de ser rejeitado"
        # E o quarto e rejeitado por um motivo NOMEADO — nao por acidente.
        assert resultados[3] == "evento_sem_id"


class TestC1C2AppAntigoContinuaAceito:
    """O app publicado em 04/08/2026 nao pode notar diferenca nenhuma."""

    def test_evento_sem_a_chave_velha_e_aceito(self):
        # E o payload que o app em campo monta hoje: jogada generica + a
        # extensao do Pontinhos, e nada da velha.
        evento = _evento("ev-antigo", [_jogada(pontinhos=EXTENSAO_PONTINHOS)])
        assert validar_evento(evento) is None

    def test_evento_sem_co_tipo_continua_valendo_como_partida(self):
        """Apps bem antigos nem mandavam `co_tipo`.

        A ausencia do campo significa "partida". Este teste existe porque e o
        tipo de retrocompatibilidade que se perde numa refatoracao distraida —
        e o sintoma seria o app antigo parando de sincronizar, em silencio.
        """
        evento = _evento("ev-muito-antigo", [_jogada()])
        del evento["co_tipo"]
        assert validar_evento(evento) is None

    def test_nenhum_campo_novo_virou_obrigatorio(self):
        """A jogada MINIMA continua passando.

        Se algum campo da velha tivesse virado obrigatorio na validacao
        generica, o app antigo — que nunca o envia — seria rejeitado inteiro.
        """
        minima = {
            "id_jogada": "22222222-2222-2222-2222-222222222222",
            "nu_ordem": 1,
            "nu_jogador": 1,
            "dh_jogada": "2026-08-06T10:00:00.000",
        }
        assert validar_evento(_evento("ev-minima", [minima])) is None


class TestC3AppNovoBackendAntigo:
    """A extensao que este backend nao conhece e IGNORADA, nunca rejeitada."""

    def test_chave_desconhecida_nao_invalida_o_evento(self):
        # Simula o app do 3o jogo do hub falando com este backend.
        evento = _evento("ev-futuro", [_jogada(damas={"co_casa": "D_3_4"})])
        assert validar_evento(evento) is None, (
            "rejeitar aqui faria o app DESCARTAR a partida inteira do usuario "
            "para nao perder um detalhe que este backend nao saberia guardar"
        )

    def test_a_chave_desconhecida_gera_AVISO(self, caplog):
        """Ignorar nao pode ser silencioso.

        O `warning` e o unico sinal de que ha um app em campo mais novo que este
        backend, e de que falta o ingestor daquele jogo.

        ⚠️ **O CANARIO MORREU EM 20/08/2026, E FOI TROCADO — 2a vez do projeto.**
        Este caso usava `damas` como o jogo desconhecido. No dia em que a
        migracao 0012 entrou, as damas viraram extensao CONHECIDA, e o caso
        passou a falhar — corretamente, porque ele deixara de testar o que dizia
        testar.

        O jogo desconhecido agora e `xadrez`, que nao existe em lugar nenhum. **E
        ele tera de ser trocado de novo** no dia em que o xadrez entrar. Isso nao
        e defeito do teste: e o preco de guardar a tolerancia ao DESCONHECIDO
        usando um exemplo concreto — e o preco vale, porque a alternativa (nao
        testar) e o modo de falha que este backend nao pode ter.

        A mesma armadilha ja tinha custado caro no frontend, em
        `conquista_desconhecida_app_antigo_test.dart`, e la o canario tambem
        morreu duas vezes.
        """
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_desconhecida(_jogada(xadrez={"co_casa": "e4"}))
        # `getMessage()` aplica os args ao formato; `r.message % r.args` faria
        # a interpolacao duas vezes e estouraria.
        assert any("xadrez" in r.getMessage() for r in caplog.records)

    def test_as_extensoes_CONHECIDAS_nao_geram_aviso(self, caplog):
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_desconhecida(_jogada(velha=EXTENSAO_VELHA))
            _avisar_extensao_desconhecida(_jogada(pontinhos=EXTENSAO_PONTINHOS))
        assert not caplog.records

    def test_campo_generico_solto_nao_e_confundido_com_extensao(self, caplog):
        """Um campo novo que NAO e dicionario nao e extensao de jogo.

        Sem esta distincao, qualquer campo escalar acrescentado a jogada no
        futuro encheria o log de avisos falsos — e log cheio de alarme falso e
        log que ninguem le.
        """
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_desconhecida(_jogada(nu_campo_futuro=7))
        assert not caplog.records

    def test_as_extensoes_conhecidas_estao_declaradas(self):
        """As tres que este backend sabe gravar hoje.

        ⚠️ Chamava-se `test_as_DUAS_extensoes...` ate 20/08/2026. O numero saiu
        do nome de proposito: um nome que conta itens envelhece a cada jogo novo,
        e renomear um teste a cada release perde o historico dele no CI.
        """
        assert _EXTENSOES_CONHECIDAS == {"pontinhos", "velha", "damas"}


class TestC4CodigoDeAcaoDesconhecido:
    """A dimensao da velha existe, e e SEPARADA da do Pontinhos."""

    def test_a_dimensao_acao_velha_aponta_para_o_schema_da_velha(self):
        view, col_codigo, col_chave = dimensoes._DIMENSOES["acao_velha"]
        assert view == "jogo_velha.vw901_jogada_acao"
        assert (col_codigo, col_chave) == ("co_acao", "nu_acao")

    def test_a_dimensao_do_pontinhos_NAO_foi_desviada(self):
        """O apelido antigo continua apontando para o Pontinhos.

        E o que impede o deploy de quebrar a ingestao do jogo publicado: o
        codigo que ainda chama `resolver(..., "acao", ...)` tem de continuar
        achando a tabela de sempre.
        """
        for chave in ("acao", "acao_pontinhos"):
            view, _, _ = dimensoes._DIMENSOES[chave]
            assert view == "jogo_pontinhos.vw901_jogada_acao"

    def test_as_duas_dimensoes_de_acao_sao_TABELAS_DIFERENTES(self):
        """O erro que este teste existe para pegar.

        Se a velha usasse a dimensao do Pontinhos, TODA acao dela cairia no
        sentinela 9999 — e a telemetria do jogo novo nasceria cega, sem erro
        nenhum, sem log de falha, so uma coluna inteira de "desconhecido".
        """
        velha, _, _ = dimensoes._DIMENSOES["acao_velha"]
        pontinhos, _, _ = dimensoes._DIMENSOES["acao"]
        assert velha != pontinhos

    def test_o_sentinela_e_o_mesmo_valor_da_migracao(self):
        assert dimensoes.NU_DESCONHECIDO == 9999


class TestOsSeisCodigosDaVelha:
    """A lista do app e a da migracao tem de ser a mesma."""

    CODIGOS = (
        "minimax_otimo",
        "minimax_deslize",
        "epsilon_aleatorio",
        "abertura_sorteada",
        "bloqueio_forcado",
        "timeout_auto",
    )

    @pytest.mark.parametrize("codigo", CODIGOS)
    def test_o_codigo_esta_na_migracao(self, codigo: str):
        from pathlib import Path

        migracao = (
            Path(__file__).resolve().parents[2]
            / "migrations"
            / "versions"
            / "0011_schema_jogo_velha.py"
        )
        assert f"'{codigo}'" in migracao.read_text(encoding="utf-8")
