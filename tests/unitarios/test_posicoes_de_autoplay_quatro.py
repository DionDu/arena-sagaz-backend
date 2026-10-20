"""O acervo de partidas Magno × Tex do Quatro em Linha (T117 da spec 010).

Três partes:

  1. **o arquivo que viaja no repositório**: cada partida é legal do primeiro
     ao último lance, termina, o vencedor gravado é o do árbitro, o Magno troca
     de cor, e não há partida repetida;
  2. **o sorteio**, com um acervo pequeno montado à mão: a posição fica na
     faixa pedida, nunca é a partida inteira, e posição mais continuação é a
     partida; a mesma semente dá a mesma posição;
  3. **o script de extração**: o arquivo que ele escreve volta pelo leitor, e
     a mesma partida jogada duas vezes sai igual (com o executável).
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

from job import posicoes_de_autoplay_quatro as acervo_mod
from motores.quatro import contrato_quatro
from motores.quatro import jogador_dart_quatro as jdq
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, ler_sequencia

MODALIDADE = "tradicional"


def _carregar_o_script():
    """Importa o script de extração como módulo (`scripts/` não é pacote).

    ⚠️ `sys.modules[nome]` antes do `exec_module`: o `@dataclass(slots=True)`
    dos módulos que ele importa procura a classe lá enquanto carrega.
    """
    caminho = Path(__file__).parents[2] / "scripts" / "extrair_posicoes_de_autoplay_quatro.py"
    spec = importlib.util.spec_from_file_location("extrair_quatro", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["extrair_quatro"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


EXTRATOR = _carregar_o_script()


def _partida(sequencia: str, magno: int = 1, vencedor: int = 1) -> acervo_mod.PartidaDeAutoplay:
    return acervo_mod.PartidaDeAutoplay(ler_sequencia(sequencia), magno, vencedor)


#: Um acervo de três partidas, montado à mão (conferidas pelo árbitro no caso
#: abaixo). A 1ª (o J1 fecha a linha de baixo, 7 lances) e a 2ª (o J2 fecha a
#: coluna 1, 10 lances) dividem a abertura `s4s4`; a 3ª é o J1 na coluna 1.
PEQUENO = acervo_mod.AcervoQuatro(
    co_modalidade=MODALIDADE,
    co_versao_motor="teste",
    partidas=(
        _partida("s4s4s3s5s2s6s1"),
        _partida("s4s4s5s1s7s1s7s1s2s1", magno=-1, vencedor=-1),
        _partida("s1s2s1s2s1s2s1"),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O arquivo que viaja no repositório
# ═══════════════════════════════════════════════════════════════════════════


def test_o_acervo_de_mao_e_legal() -> None:
    """O controle do resto: as partidas de mão terminam com o vencedor anotado."""
    arbitro = MotorQuatro(MODALIDADE)
    for partida in PEQUENO.partidas:
        veredito = arbitro.veredito(EstadoQuatro(MODALIDADE, partida.lances))
        assert veredito.acabou and veredito.vencedor == partida.vencedor


def test_o_acervo_tradicional_existe_e_e_da_modalidade() -> None:
    acervo = acervo_mod.carregar(MODALIDADE)
    assert acervo.co_modalidade == MODALIDADE
    # 400 partidas pedidas, 396 distintas em 20/10/2026: abaixo de 300 alguém
    # gravou um acervo de ensaio por cima do de verdade.
    assert len(acervo.partidas) >= 300


def test_cada_partida_e_legal_termina_e_tem_o_vencedor_do_arbitro() -> None:
    arbitro = MotorQuatro(MODALIDADE)
    for partida in acervo_mod.carregar(MODALIDADE).partidas:
        # `tabuleiro` reproduz lance a lance e recusa lance ilegal ou depois do fim.
        estado = EstadoQuatro(MODALIDADE, partida.lances)
        veredito = arbitro.veredito(estado)
        assert veredito.acabou, "".join(partida.lances)
        assert veredito.vencedor == partida.vencedor, "".join(partida.lances)


def test_o_magno_troca_de_cor_e_nao_ha_partida_repetida() -> None:
    partidas = acervo_mod.carregar(MODALIDADE).partidas
    assert {p.magno for p in partidas} == {1, -1}
    # As duas cores com quantidades parecidas (a troca é a cada partida; só as
    # repetidas, que saem, desequilibram).
    abrindo = sum(1 for p in partidas if p.magno == 1)
    assert abs(2 * abrindo - len(partidas)) <= len(partidas) // 10
    assert len({p.lances for p in partidas}) == len(partidas)


def test_o_acervo_carimba_o_motor_que_jogou() -> None:
    assert acervo_mod.carregar(MODALIDADE).co_versao_motor.startswith("quatro-dart-")


# ═══════════════════════════════════════════════════════════════════════════
# 2. O sorteio
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("semente", range(40))
def test_a_posicao_fica_na_faixa_e_continua_a_partida(semente: int) -> None:
    posicao = acervo_mod.sortear(
        random.Random(semente), co_modalidade=MODALIDADE, minimo=2, maximo=5, acervo=PEQUENO
    )
    assert 2 <= len(posicao.lances) <= 5
    # Prefixo mais continuação é uma partida do acervo, e a continuação nunca
    # é vazia: a posição tem sempre um lance a jogar.
    assert posicao.lances + posicao.continuacao in {p.lances for p in PEQUENO.partidas}
    assert posicao.continuacao


def test_o_teto_da_faixa_respeita_o_fim_da_partida() -> None:
    """Pedindo até 20 lances, a posição para um lance antes do fim de cada partida."""
    vistos = set()
    for semente in range(200):
        posicao = acervo_mod.sortear(
            random.Random(semente), co_modalidade=MODALIDADE, minimo=6, maximo=20,
            acervo=PEQUENO,
        )
        assert len(posicao.continuacao) >= 1
        vistos.add(len(posicao.lances))
    # A 1ª e a 3ª partidas têm 7 lances (só o 6 serve); a 2ª tem 10 (de 6 a 9).
    assert vistos == {6, 7, 8, 9}


def test_a_mesma_semente_da_a_mesma_posicao() -> None:
    a = acervo_mod.sortear(random.Random(7), co_modalidade=MODALIDADE, minimo=1, maximo=6,
                           acervo=PEQUENO)
    b = acervo_mod.sortear(random.Random(7), co_modalidade=MODALIDADE, minimo=1, maximo=6,
                           acervo=PEQUENO)
    assert a == b


def test_nenhuma_partida_alem_do_minimo_falha_alto() -> None:
    with pytest.raises(acervo_mod.SemPosicaoDeAutoplay, match="a mais longa tem 10"):
        acervo_mod.sortear(random.Random(1), co_modalidade=MODALIDADE, minimo=10, maximo=12,
                           acervo=PEQUENO)


@pytest.mark.parametrize("minimo, maximo", [(0, 4), (5, 4)])
def test_faixa_invalida_e_recusada(minimo: int, maximo: int) -> None:
    with pytest.raises(ValueError, match="faixa"):
        acervo_mod.sortear(random.Random(1), co_modalidade=MODALIDADE, minimo=minimo,
                           maximo=maximo, acervo=PEQUENO)


def test_as_posicoes_distintas_contam_a_abertura_comum_uma_vez() -> None:
    distintas = acervo_mod.posicoes_distintas_por_comprimento(PEQUENO)
    # `s4` (1ª e 2ª) e `s1` (3ª): duas posições de 1 lance; `s4s4` e `s1s2`: duas
    # de 2; daí em diante as três divergem.
    assert distintas[1] == 2
    assert distintas[2] == 2
    assert distintas[3] == 3
    # Do 7º lance em diante só a 2ª partida tem posição (as outras acabam nele).
    assert distintas[7] == 1
    assert distintas[9] == 1
    assert 10 not in distintas


# ═══════════════════════════════════════════════════════════════════════════
# 3. O leitor recusa o arquivo errado, e o script escreve o que ele lê
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def pasta_temporaria(tmp_path, monkeypatch):
    """Aponta o acervo para uma pasta temporária e esquece o que já foi lido."""
    monkeypatch.setattr(acervo_mod, "PASTA_DO_ACERVO", tmp_path)
    acervo_mod.carregar.cache_clear()
    yield tmp_path
    acervo_mod.carregar.cache_clear()


def test_o_que_o_script_escreve_volta_pelo_leitor(pasta_temporaria) -> None:
    partidas = list(PEQUENO.partidas)
    texto = EXTRATOR.para_json(MODALIDADE, partidas)
    acervo_mod.caminho_do_acervo(MODALIDADE).write_text(texto, encoding="utf-8")
    lido = acervo_mod.carregar(MODALIDADE)
    assert lido.partidas == PEQUENO.partidas
    assert lido.co_versao_motor == contrato_quatro.versao_do_motor()
    # Uma partida por linha: é o que deixa o diff do acervo legível.
    assert texto.count("\n") == len(partidas) + 4


def test_o_leitor_recusa_arquivo_de_outra_modalidade(pasta_temporaria) -> None:
    dado = json.loads(EXTRATOR.para_json("outra", list(PEQUENO.partidas)))
    acervo_mod.caminho_do_acervo(MODALIDADE).write_text(json.dumps(dado), encoding="utf-8")
    with pytest.raises(ValueError, match="'outra'"):
        acervo_mod.carregar(MODALIDADE)


def test_o_leitor_recusa_outro_formato(pasta_temporaria) -> None:
    dado = json.loads(EXTRATOR.para_json(MODALIDADE, list(PEQUENO.partidas)))
    dado["versao"] = acervo_mod.VERSAO_DO_ACERVO + 1
    acervo_mod.caminho_do_acervo(MODALIDADE).write_text(json.dumps(dado), encoding="utf-8")
    with pytest.raises(ValueError, match="formato"):
        acervo_mod.carregar(MODALIDADE)


def test_sem_o_arquivo_a_mensagem_diz_como_reconstruir(pasta_temporaria) -> None:
    with pytest.raises(FileNotFoundError, match="extrair_posicoes_de_autoplay_quatro"):
        acervo_mod.carregar(MODALIDADE)


def test_as_repetidas_saem_e_a_primeira_fica() -> None:
    a, b, c = PEQUENO.partidas
    repetida = acervo_mod.PartidaDeAutoplay(a.lances, -1, a.vencedor)
    assert EXTRATOR.sem_repetidas([a, b, repetida, c]) == [a, b, c]


@pytest.fixture(scope="module")
def jogador():
    try:
        jdq.caminho_do_executavel()
    except jdq.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do Quatro não está compilado: {erro}")
    from motores.quatro.jogador_quatro import JogadorQuatro

    with jdq.JogadorDartQuatro() as motor:
        yield JogadorQuatro(MODALIDADE, motor_dart=motor)


def test_a_mesma_partida_jogada_duas_vezes_sai_igual(jogador) -> None:
    """A semente é o índice: é o que torna o arquivo reproduzível."""
    primeira = EXTRATOR.jogar_partida(jogador, MODALIDADE, 3)
    segunda = EXTRATOR.jogar_partida(jogador, MODALIDADE, 3)
    assert primeira == segunda
    # Índice ímpar: o Magno responde.
    assert primeira.magno == -1


def test_a_partida_jogada_e_a_que_esta_no_acervo(jogador) -> None:
    """O acervo do repositório saiu deste motor e desta semente: a partida 0
    jogada agora é a primeira dele (a 0 nunca é repetida de outra)."""
    acervo = acervo_mod.carregar(MODALIDADE)
    if acervo.co_versao_motor != contrato_quatro.versao_do_motor():
        pytest.skip("o motor mudou desde a extração; o acervo continua legal")
    assert EXTRATOR.jogar_partida(jogador, MODALIDADE, 0) == acervo.partidas[0]
