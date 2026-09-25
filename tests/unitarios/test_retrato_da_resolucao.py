"""🔒 O retrato da resolucao: TODAS as medidas do tabuleiro e a janela gasta (T085za).

O cartao de quem resolveu (*"4 caixas em 2 turnos"*) sai de
`tb003_resolucao.js_feito`, em qualquer aparelho em que a pessoa entrar
(`DECISOES-do-dono.md` §8z item 13). Ate a `0027` o servidor guardava so as
medidas que PESAM no desafio (as linhas de `tb004`), e a janela em lugar nenhum.

Os ajudantes (o envio valido, o repositorio falso, a partida) sao os de
`test_envio_de_resolucao.py` - ⛔ copiados: dois envios "validos" escritos em dois
lugares divergem, e o caso daqui passaria contra um envio que a rota recusa.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.desafios.modelos_envio import FeitoMedido
from api.desafios.repositorio_envio import SQL_GRAVAR_RESOLUCAO
from api.desafios.retrato import FORA_DO_RETRATO, retrato_da_resolucao
from api.desafios.servico_envio import ServicoEnvio
from tests.unitarios.test_envio_de_resolucao import (
    ID_DESAFIO,
    ID_USUARIO,
    RepoFalso,
    _envio,
    _partida,
)


def test_o_retrato_tem_as_medidas_do_TABULEIRO_e_a_janela() -> None:
    """As de sessao e o veredito ficam de fora - cada um ja tem casa propria."""
    retrato = retrato_da_resolucao(
        [
            FeitoMedido(chave="caixas_fechadas", valor=4),
            FeitoMedido(chave="caixas_do_adversario", valor=1),
            FeitoMedido(chave="tentativas", valor=2),
            FeitoMedido(chave="tempo_ate_resolver", valor=48210),
            FeitoMedido(chave="dicas_usadas", valor=0),
            FeitoMedido(chave="desafio_concluido", valor=1),
        ],
        2,
    )
    assert retrato == {
        "medidas": {"caixas_do_adversario": 1, "caixas_fechadas": 4},
        "janela_gasta": 2,
    }


def test_contagem_vira_INTEIRO_e_fracao_passa_como_veio() -> None:
    """`4.0` e `4` para a frase; uma medida fracionaria futura ⛔ e truncada."""
    retrato = retrato_da_resolucao(
        [
            FeitoMedido(chave="caixas_fechadas", valor=4.0),
            FeitoMedido(chave="medida_futura", valor=0.5),
        ],
        None,
    )
    assert retrato["medidas"] == {"caixas_fechadas": 4, "medida_futura": 0.5}
    assert isinstance(retrato["medidas"]["caixas_fechadas"], int)
    # A janela que ⛔ se conta (a partida inteira) sai nula, e ⛔ zero.
    assert retrato["janela_gasta"] is None


def test_as_tres_de_sessao_e_o_veredito_sao_o_que_fica_de_fora() -> None:
    """Uma chave a mais aqui tiraria do retrato uma medida que alguma frase le."""
    assert FORA_DO_RETRATO == {
        "tentativas",
        "tempo_ate_resolver",
        "dicas_usadas",
        "desafio_concluido",
    }


@pytest.mark.asyncio
async def test_a_resolucao_grava_o_retrato_com_a_medida_que_NAO_pesa() -> None:
    """🔒 O caso que motivou a `0027`: `capturas_extras` ⛔ pesa neste desafio
    (⛔ vai para a `tb004`), e o retrato a guarda mesmo assim - a frase de outro
    tipo pode le-la.
    """
    # O catalogo do repositorio falso ganha `capturas_extras`: ela EXISTE (⛔ e
    # chave inventada, que a rota recusa) e ⛔ pesa (`_pesos` so tem
    # `damas_coroadas` e `material_do_adversario`).
    repo = RepoFalso(
        partida=_partida(),
        catalogo=(
            "damas_coroadas",
            "material_do_adversario",
            "capturas_extras",
            "tentativas",
            "tempo_ate_resolver",
            "dicas_usadas",
        ),
    )
    envio = _envio(
        feitos=[
            FeitoMedido(chave="damas_coroadas", valor=1),
            FeitoMedido(chave="capturas_extras", valor=2),
            FeitoMedido(chave="tempo_ate_resolver", valor=48210),
            FeitoMedido(chave="tentativas", valor=3),
        ],
        janela_gasta=3,
    )

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=envio
    )

    assert repo.resolucoes[0]["js_feito"] == {
        "medidas": {"capturas_extras": 2, "damas_coroadas": 1},
        "janela_gasta": 3,
    }


def test_o_INSERT_grava_o_retrato_como_JSONB() -> None:
    """O driver ⛔ converte `dict`: o texto entra e o `CAST` o faz JSONB."""
    assert "js_feito" in SQL_GRAVAR_RESOLUCAO
    assert "CAST(:js_feito AS JSONB)" in SQL_GRAVAR_RESOLUCAO


def test_a_janela_gasta_e_OPCIONAL_na_resolucao() -> None:
    """⚠️ O app anterior a T085za ⛔ a manda - e recusar faria o outbox descartar
    a resolucao (422 e "dado impossivel" la), levando o XP junto.
    """
    assert _envio().janela_gasta is None


def test_janela_gasta_negativa_e_dado_invalido() -> None:
    with pytest.raises(ValidationError):
        _envio(janela_gasta=-1)
