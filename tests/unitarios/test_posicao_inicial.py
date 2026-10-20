"""T031 - a posicao inicial nos dois formatos, e a conferencia dos derivados.

⚠️ **O teste que mais importa e o da CONFERENCIA.** Escrever a posicao e facil; o
que o projeto precisa e que um `vez_de` errado nao chegue ao banco — porque no
Pontinhos ele nao produz erro nenhum, so faz o desafio comecar com o jogador
errado no aparelho de quem o jogar.
"""

from __future__ import annotations

import pytest

from job.posicao_inicial import (
    FORMATO_FEN,
    FORMATO_SEQUENCIA,
    PosicaoInvalida,
    conferir,
    das_damas,
    do_pontinhos,
    do_quatro,
    formato_do_jogo,
)

# A mesma "escada" dos vetores de verificacao: quatro caixas na coluna da
# esquerda, cada uma com tres lados. Nenhum destes lances fecha caixa.
ESCADA = [
    "V_1_0", "V_1_2",
    "V_3_0", "V_3_2",
    "V_5_0", "V_5_2",
    "V_7_0", "V_7_2",
    "H_0_1",
    "H_0_3",
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Escrever
# ═══════════════════════════════════════════════════════════════════════════


def test_a_sequencia_do_pontinhos_anota_o_jogador_de_cada_lance() -> None:
    """A alternancia sai da REPRODUCAO, nao de "par e impar".

    ⚠️ Quem fecha caixa joga de novo. Numa preparacao sem caixa fechada os lances
    de fato alternam — e e por isso que esta e uma boa preparacao —, mas o codigo
    nao pode DEPENDER disso.
    """
    posicao = do_pontinhos(ESCADA)
    assert posicao["versao"] == 1
    assert [l["jogador"] for l in posicao["lances"]] == [1, -1] * 5
    assert posicao["vez_de"] == 1
    assert posicao["placar"] == {"j1": 0, "j2": 0}


def test_a_sequencia_registra_o_turno_extra_de_quem_fecha_caixa() -> None:
    """🔒 O caso que separa este codigo de um `n % 2`.

    Descendo a escada, o jogador 1 fecha quatro caixas seguidas e joga cinco
    vezes em sequencia. Uma anotacao por paridade diria que os lances alternaram.
    """
    posicao = do_pontinhos(ESCADA + ["H_2_1", "H_4_1"])
    jogadores = [l["jogador"] for l in posicao["lances"]]
    # Os dois ultimos sao do MESMO jogador: o primeiro fechou caixa.
    assert jogadores[-2:] == [1, 1]
    assert posicao["placar"] == {"j1": 2, "j2": 0}
    # Ele fechou de novo no ultimo lance, entao a vez continua sendo dele.
    assert posicao["vez_de"] == 1


def test_a_fen_das_damas_e_normalizada_pelo_motor() -> None:
    """Duas escritas da mesma posicao viram uma so.

    ⚠️ Sem isso, o `UNIQUE` do banco nao significaria o que promete: a mesma
    posicao entraria duas vezes com duas grafias.
    """
    posicao = das_damas("W:W27:B23,15,4")
    assert posicao["versao"] == 1
    assert posicao["vez_de"] == 1
    # A ordem das casas pode mudar; o que importa e ser estavel.
    assert das_damas(posicao["fen"])["fen"] == posicao["fen"]


def test_fen_ilegivel_e_recusada() -> None:
    with pytest.raises(PosicaoInvalida):
        das_damas("isto nao e uma fen")


def test_sequencia_com_traco_repetido_e_recusada() -> None:
    """Traco repetido nao produz posicao — produz dado corrompido."""
    with pytest.raises(PosicaoInvalida):
        do_pontinhos(["H_0_1", "H_0_1"])


# ═══════════════════════════════════════════════════════════════════════════
# 2. Conferir — o passo que impede a publicacao de dado errado
# ═══════════════════════════════════════════════════════════════════════════


def test_a_posicao_que_o_job_escreveu_confere_consigo_mesma() -> None:
    conferir(FORMATO_SEQUENCIA, do_pontinhos(ESCADA))
    conferir(FORMATO_FEN, das_damas("W:W27:B23,15,4"))


def test_vez_de_ERRADO_e_pego_na_conferencia() -> None:
    """🔒 O defeito que nao daria erro em lugar nenhum.

    Um `vez_de` trocado faz o desafio comecar com o jogador errado — e o
    aplicativo obedeceria, porque nao tem como saber que esta errado.
    """
    posicao = dict(do_pontinhos(ESCADA))
    posicao["vez_de"] = -1
    with pytest.raises(PosicaoInvalida, match="vez_de"):
        conferir(FORMATO_SEQUENCIA, posicao)


def test_placar_ERRADO_e_pego_na_conferencia() -> None:
    """Um placar inventado daria vantagem ou desvantagem a quem jogasse."""
    posicao = dict(do_pontinhos(ESCADA))
    posicao["placar"] = {"j1": 3, "j2": 0}
    with pytest.raises(PosicaoInvalida, match="placar"):
        conferir(FORMATO_SEQUENCIA, posicao)


def test_jogador_ERRADO_num_lance_e_pego() -> None:
    """A anotacao de quem jogou cada lance tambem e derivada.

    ⚠️ E ela que o medidor por fita usa para saber onde um TURNO comeca — uma
    anotacao errada mudaria a janela do desafio sem mudar mais nada.
    """
    posicao = do_pontinhos(ESCADA)
    posicao["lances"][3]["jogador"] = 1  # era -1
    with pytest.raises(PosicaoInvalida, match="anotado"):
        conferir(FORMATO_SEQUENCIA, posicao)


def test_vez_de_ERRADO_nas_damas_e_pego() -> None:
    """Nas damas a vez esta no prefixo da FEN — duas fontes acabam discordando."""
    posicao = dict(das_damas("W:W27:B23,15,4"))
    posicao["vez_de"] = -1
    with pytest.raises(PosicaoInvalida, match="vez_de"):
        conferir(FORMATO_FEN, posicao)


def test_versao_desconhecida_e_recusada() -> None:
    """Formato futuro lido por codigo antigo daria um desafio inexplicavel."""
    posicao = dict(do_pontinhos(ESCADA))
    posicao["versao"] = 99
    with pytest.raises(PosicaoInvalida, match="versao"):
        conferir(FORMATO_SEQUENCIA, posicao)


def test_formato_inventado_e_recusado() -> None:
    with pytest.raises(PosicaoInvalida, match="co_formato_posicao"):
        conferir("matriz", do_pontinhos(ESCADA))


# ═══════════════════════════════════════════════════════════════════════════
# 3. Qual formato cada jogo usa
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "co_jogo, esperado",
    [("pontinhos", FORMATO_SEQUENCIA), ("damas", FORMATO_FEN), ("quatro", FORMATO_SEQUENCIA)],
)
def test_cada_jogo_declara_o_seu_formato(co_jogo: str, esperado: str) -> None:
    assert formato_do_jogo(co_jogo) == esperado


def test_jogo_sem_formato_declarado_falha_ALTO() -> None:
    """⚠️ Gravar no formato errado faria o aplicativo ler uma FEN como sequencia.

    E o erro so apareceria no aparelho de alguem, sem que nada no servidor
    tivesse reclamado.
    """
    with pytest.raises(PosicaoInvalida, match="formato de posicao"):
        formato_do_jogo("velha")


# ═══════════════════════════════════════════════════════════════════════════
# 4. O Quatro em Linha (T116 da spec 010): o mesmo formato do Pontinhos, e a
#    conferencia separada pelo `co_jogo` de dentro da posicao
# ═══════════════════════════════════════════════════════════════════════════

ABERTURA_QUATRO = ["s4", "s4", "s3", "s5", "s3"]


def test_quatro_monta_a_forma_do_arbitro_com_a_versao() -> None:
    posicao = do_quatro(ABERTURA_QUATRO, co_modalidade="tradicional")
    assert posicao == {
        "versao": 1,
        "co_jogo": "quatro",
        "co_modalidade": "tradicional",
        "co_formato_posicao": FORMATO_SEQUENCIA,
        "sequencia_lances": ABERTURA_QUATRO,
        "co_lances": "s4s4s3s5s3",
        # Cinco lances jogados: a vez e do jogador 2.
        "vez_de": -1,
    }
    conferir(FORMATO_SEQUENCIA, posicao, co_modalidade="tradicional")


@pytest.mark.parametrize(
    "campo, valor",
    [("vez_de", 1), ("co_lances", "s4s4s3s5"), ("co_formato_posicao", "fen")],
)
def test_quatro_derivado_ERRADO_e_pego(campo: str, valor: object) -> None:
    """Cada derivado se refaz: o `co_lances` e o que o app le como posicao."""
    posicao = {**do_quatro(ABERTURA_QUATRO, co_modalidade="tradicional"), campo: valor}
    with pytest.raises(PosicaoInvalida, match=campo):
        conferir(FORMATO_SEQUENCIA, posicao, co_modalidade="tradicional")


def test_quatro_com_modalidade_de_outro_desafio_e_pego() -> None:
    posicao = do_quatro(ABERTURA_QUATRO, co_modalidade="tradicional")
    with pytest.raises(PosicaoInvalida, match="modalidade"):
        conferir(FORMATO_SEQUENCIA, posicao, co_modalidade="pop_out")


def test_quatro_sem_co_jogo_NAO_passa_como_pontinhos() -> None:
    """⚠️ Os dois jogos usam o mesmo formato. Sem o `co_jogo`, a posicao cai na
    conferencia do Pontinhos - e ela tem de falhar alto, e nao aceitar."""
    posicao = do_quatro(ABERTURA_QUATRO, co_modalidade="tradicional")
    del posicao["co_jogo"]
    with pytest.raises(PosicaoInvalida):
        conferir(FORMATO_SEQUENCIA, posicao, co_modalidade="tradicional")


def test_quatro_lance_ilegal_e_partida_acabada_sao_recusados() -> None:
    # A coluna 4 tem seis casas: o setimo `s4` e ilegal.
    with pytest.raises(PosicaoInvalida, match="invalida"):
        do_quatro(["s4"] * 7, co_modalidade="tradicional")
    # O jogador 1 empilha quatro na coluna 1: a partida acabou, nao ha desafio.
    with pytest.raises(PosicaoInvalida, match="acabou"):
        do_quatro(["s1", "s2", "s1", "s2", "s1", "s2", "s1"], co_modalidade="tradicional")
