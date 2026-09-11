"""🔒 A pesca de posições do Pontinhos em partidas reais.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO GUARDA
═══════════════════════════════════════════════════════════════════════════

A posição do Jogo dos Pontinhos **é o conjunto de traços marcados**, e marcar um
traço nunca desmarca outro. Logo **todo prefixo de uma partida real é uma posição
real** — e pescar, aqui, é conversão, não busca.

⛔ **O risco não está na conversão: está no BITMASK.** A posição viaja como um
inteiro em que o bit `i` é o traço `co_rotulo[i]`. Uma ordem de rótulos diferente
produz máscaras que **carregam sem erro** e significam outro tabuleiro. Nada
denunciaria: seria um NPZ bem formado, com números plausíveis dentro. É por isso
que a ordem é lida do acervo que já existe, e o primeiro teste daqui é sobre ela.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from job.posicoes_de_autoplay_pontinhos import TRACOS_DO_TABULEIRO  # noqa: E402
from scripts.pescar_posicoes_pontinhos import (  # noqa: E402
    gravar,
    ler_partidas,
    mascaras_dos_prefixos,
    ordem_canonica_dos_rotulos,
)

#: Uma partida curta e uma de um lance, para os prefixos serem conferíveis a olho.
LINHAS = [
    {"id_partida": "p1", "nu_ordem": "1", "co_aresta": "H_0_1", "co_variante": "pequeno"},
    {"id_partida": "p1", "nu_ordem": "2", "co_aresta": "V_1_0", "co_variante": "pequeno"},
    {"id_partida": "p1", "nu_ordem": "3", "co_aresta": "H_2_1", "co_variante": "pequeno"},
    {"id_partida": "p2", "nu_ordem": "1", "co_aresta": "H_0_1", "co_variante": "pequeno"},
]


@pytest.fixture
def csv_de_lances(tmp_path: Path) -> Path:
    """Escreve as linhas acima num CSV, como o export do banco faria."""
    caminho = tmp_path / "lances.csv"
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(LINHAS[0]))
        escritor.writeheader()
        escritor.writerows(LINHAS)
    return caminho


class TestOrdemDosRotulos:
    """⛔ O contrato silencioso do bitmask."""

    def test_sao_os_31_do_tabuleiro_pequeno(self) -> None:
        """🔒 O tabuleiro 4x3 tem 31 traços — nem 30, nem 32."""
        assert len(ordem_canonica_dos_rotulos()) == TRACOS_DO_TABULEIRO

    def test_nao_ha_rotulo_repetido(self) -> None:
        """🔒 ⚠️ Dois bits com o mesmo nome fariam duas posições virarem uma.

        E o sintoma seria mudo: o acervo teria menos posições do que deveria, e
        ninguém saberia dizer quantas se perderam.
        """
        rotulos = ordem_canonica_dos_rotulos()
        assert len(set(rotulos)) == len(rotulos)


class TestLerPartidas:
    """A leitura do CSV — onde a ORDEM é a única coisa irrecuperável."""

    def test_agrupa_por_partida_e_ordena(self, csv_de_lances: Path) -> None:
        """🔒 Cada partida vira a sua lista de rótulos, na ordem jogada."""
        partidas = ler_partidas(csv_de_lances)
        assert partidas == {"p1": ["H_0_1", "V_1_0", "H_2_1"], "p2": ["H_0_1"]}

    def test_a_ordem_e_REIMPOSTA_e_nao_herdada_do_arquivo(self, tmp_path: Path) -> None:
        """🔒 ⚠️ O CSV pode chegar embaralhado, e o script não pode acreditar nele.

        Um arquivo aberto no Excel e salvo de volta perde o `ORDER BY`. ⛔ E aqui
        a ordem errada não dá erro: dá prefixos que nunca existiram, com aparência
        perfeita.
        """
        caminho = tmp_path / "fora_de_ordem.csv"
        with caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(LINHAS[0]))
            escritor.writeheader()
            escritor.writerows(reversed(LINHAS[:3]))  # 3, 2, 1
        assert ler_partidas(caminho)["p1"] == ["H_0_1", "V_1_0", "H_2_1"]

    def test_o_BOM_do_Excel_nao_quebra_o_cabecalho(self, tmp_path: Path) -> None:
        """🔒 ⚠️ `utf-8-sig`: sem ele a 1ª coluna se chamaria `﻿id_partida`.

        O cabeçalho parece certo na tela, e só o `linha["id_partida"]` falha.
        """
        caminho = tmp_path / "com_bom.csv"
        caminho.write_text(
            "id_partida,nu_ordem,co_aresta,co_variante\np1,1,H_0_1,pequeno\n",
            encoding="utf-8-sig",
        )
        assert ler_partidas(caminho) == {"p1": ["H_0_1"]}

    def test_so_o_tabuleiro_pequeno_entra(self, tmp_path: Path) -> None:
        """🔒 ⛔ Outro tamanho tem outra quantidade de traços — e outro bitmask."""
        caminho = tmp_path / "misto.csv"
        with caminho.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(LINHAS[0]))
            escritor.writeheader()
            escritor.writerows(
                [*LINHAS[:1], {**LINHAS[0], "id_partida": "grande", "co_variante": "medio"}]
            )
        assert list(ler_partidas(caminho)) == ["p1"]


class TestPrefixos:
    """Os prefixos, que são as posições."""

    def test_uma_partida_de_N_lances_da_N_posicoes(self, csv_de_lances: Path) -> None:
        """🔒 E a de `p2` cai junto com o 1º prefixo de `p1`: as duas marcam `H_0_1`."""
        mascaras, _motivos = mascaras_dos_prefixos(
            ler_partidas(csv_de_lances), ordem_canonica_dos_rotulos()
        )
        assert len(mascaras) == 3  # 3 de p1; a de p2 é a mesma do 1º prefixo

    def test_a_posicao_VAZIA_fica_de_fora(self, csv_de_lances: Path) -> None:
        """🔒 ⚠️ O tabuleiro inicial é igual para todo mundo.

        Incluí-lo faria o acervo prometer variedade que não tem na fase 0.
        """
        mascaras, _motivos = mascaras_dos_prefixos(
            ler_partidas(csv_de_lances), ordem_canonica_dos_rotulos()
        )
        assert 0 not in mascaras

    def test_o_bit_certo_acende(self) -> None:
        """🔒 A conferência direta do contrato: bit `i` ↔ `co_rotulo[i]`."""
        rotulos = ordem_canonica_dos_rotulos()
        mascaras, _ = mascaras_dos_prefixos({"p": [rotulos[5]]}, rotulos)
        assert mascaras == {1 << 5}

    def test_traco_REPETIDO_interrompe_a_partida(self) -> None:
        """🔒 ⛔ E interrompe de propósito, em vez de ignorar o lance.

        ⚠️ Marcar duas vezes o mesmo traço é impossível no jogo. Se aparecer, a
        linha está corrompida ou a ordem veio errada — e daí para a frente
        **todos** os prefixos daquela partida estariam errados, não só aquele.
        Ignorar o lance produziria posições plausíveis e falsas.
        """
        rotulos = ordem_canonica_dos_rotulos()
        mascaras, motivos = mascaras_dos_prefixos(
            {"p": [rotulos[0], rotulos[1], rotulos[0], rotulos[2]]}, rotulos
        )
        assert motivos["traco_repetido"] == 1
        assert motivos["partida_interrompida"] == 1
        # Só os dois prefixos anteriores ao defeito sobreviveram.
        assert mascaras == {1, 0b11}

    def test_rotulo_DESCONHECIDO_tambem_interrompe(self) -> None:
        """🔒 Um nome que não existe no tabuleiro é dado corrompido, não ruído."""
        rotulos = ordem_canonica_dos_rotulos()
        _mascaras, motivos = mascaras_dos_prefixos({"p": ["H_99_99"]}, rotulos)
        assert motivos["rotulo_fora_do_tabuleiro:H_99_99"] == 1


class TestGravar:
    """⚠️ A ordenação do arquivo é parte do contrato, não enfeite."""

    def test_sai_ordenado_por_quantidade_de_tracos(self, tmp_path: Path) -> None:
        """🔒 ⛔ `Acervo.com_tracos` assume FATIA CONTÍGUA por quantidade.

        Um arquivo desordenado carregaria sem erro e devolveria posições da fase
        errada — o gerador pediria "20 traços" e receberia outra coisa.
        """
        saida = tmp_path / "acervo.npz"
        rotulos = ordem_canonica_dos_rotulos()
        gravar({0b111, 0b1, 0b11, 0b1000}, rotulos, saida)

        mascaras = np.load(saida)["nu_mascara"]
        contagens = [int(m).bit_count() for m in mascaras]
        assert contagens == sorted(contagens)

    def test_o_arquivo_e_lido_pelo_ACERVO_de_verdade(self, tmp_path: Path) -> None:
        """🔒 ⚠️ O teste que prova que a pesca serve para alguma coisa.

        Não basta gravar um NPZ: ele tem de ser aceito por
        `posicoes_de_autoplay_pontinhos.carregar`, que é quem o gerador usa. Aqui
        se monta o `Acervo` com o mesmo código de produção e se pede uma fase.
        """
        from job.posicoes_de_autoplay_pontinhos import Acervo, _inicio_de_cada_fase

        saida = tmp_path / "acervo.npz"
        rotulos = ordem_canonica_dos_rotulos()
        gravar({0b1, 0b11, 0b101, 0b111}, rotulos, saida)

        arquivo = np.load(saida)
        acervo = Acervo(
            nu_mascara=arquivo["nu_mascara"],
            co_rotulo=tuple(str(x) for x in arquivo["co_rotulo"]),
            nu_inicio=_inicio_de_cada_fase(arquivo["nu_mascara"]),
        )
        assert sorted(acervo.com_tracos(2)) == [0b11, 0b101]
        assert sorted(acervo.com_tracos(3)) == [0b111]
        # ⚠️ Fase sem posição devolve fatia VAZIA, e não IndexError.
        assert len(acervo.com_tracos(31)) == 0
