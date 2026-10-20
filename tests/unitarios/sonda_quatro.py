"""A modalidade-SONDA do Quatro em Linha, do lado Python (spec 010, T108).

Só de teste: nunca vai para `motores/`. É o espelho da sonda do laboratório
(`ia/jogos/jogo_quatro/motor_dart/test/sonda/modalidade_sonda_quatro.dart`),
uma modalidade de mentira diferente da de verdade em tudo o que pode diferir:

  - o tabuleiro 6 × 5 (largura PAR: não há coluna do meio);
  - um 2º tipo de lance, `tirar` (letra `t`): quem tem a vez tira a peça de
    BAIXO de uma coluna, se ela for dele, e a coluna inteira desce uma casa (a
    regra do "Pop Out");
  - se um lance forma linha para os DOIS jogadores (só um `tirar` faz isso),
    vence quem NÃO jogou; empate só com o tabuleiro cheio.

Ela entra no árbitro pela mesma porta que uma modalidade nova de verdade
entraria: o contrato (`tests/dados/contrato_sonda_quatro.json`) e uma família de
regras registrada pelos tipos de lance. ⚠️ Se fazê-la atravessar o árbitro
exigir mudança em `motores/quatro/` que cite a sonda, é o defeito que ela
existe para achar: corrige-se a produção, sem nome de modalidade escrito.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from motores.quatro import contrato_quatro
from motores.quatro.motor_quatro import (
    TIPO_SOLTAR,
    DesfechoQuatro,
    RegrasDeGravidadeQuatro,
    TabuleiroQuatro,
    linhas_alinhadas,
)

#: O nome do 2º tipo de lance da sonda.
TIPO_TIRAR = "tirar"

#: O contrato de teste com a sonda.
CAMINHO_DO_CONTRATO_DA_SONDA = (
    Path(__file__).resolve().parents[1] / "dados" / "contrato_sonda_quatro.json"
)


class RegrasSondaQuatro:
    """Soltar e tirar, 6 × 5 (as dimensões vêm do contrato de teste)."""

    def __init__(
        self,
        dimensoes: contrato_quatro.DimensoesQuatro,
        tipos_de_lance: Mapping[str, str],
    ) -> None:
        self.dimensoes = dimensoes
        self.tipos_de_lance = tipos_de_lance
        # O soltar é o da gravidade: reaproveitado, e não reescrito.
        self._gravidade = RegrasDeGravidadeQuatro(dimensoes, tipos_de_lance)

    def inicial(self) -> TabuleiroQuatro:
        return self._gravidade.inicial()

    def lances_legais(self, tabuleiro: TabuleiroQuatro) -> list[tuple[str, int]]:
        # Por coluna, o soltar e depois o tirar: a ordem da sonda do Dart.
        lances = []
        for coluna in range(1, self.dimensoes.largura + 1):
            pilha = tabuleiro.colunas[coluna - 1]
            if len(pilha) < self.dimensoes.altura:
                lances.append((TIPO_SOLTAR, coluna))
            if pilha and pilha[0] == tabuleiro.vez:
                lances.append((TIPO_TIRAR, coluna))
        return lances

    def aplicar(self, tabuleiro: TabuleiroQuatro, lance: tuple[str, int]) -> TabuleiroQuatro:
        if lance not in self.lances_legais(tabuleiro):
            raise ValueError(f"a sonda não aceita {lance} aqui")
        tipo, coluna = lance
        if tipo == TIPO_SOLTAR:
            return self._gravidade.aplicar(tabuleiro, lance)
        colunas = list(tabuleiro.colunas)
        # Tirar: some a peça de baixo, e as de cima descem uma casa.
        colunas[coluna - 1] = colunas[coluna - 1][1:]
        return TabuleiroQuatro(
            colunas=tuple(colunas),
            vez=-tabuleiro.vez,
            lances_jogados=tabuleiro.lances_jogados + 1,
        )

    def desfecho(self, tabuleiro: TabuleiroQuatro) -> DesfechoQuatro | None:
        quem_jogou = -tabuleiro.vez
        do_outro = linhas_alinhadas(self.dimensoes, tabuleiro, -quem_jogou)
        de_quem_jogou = linhas_alinhadas(self.dimensoes, tabuleiro, quem_jogou)
        # Linha do outro (com ou sem linha de quem jogou): vence o outro.
        if do_outro:
            return DesfechoQuatro(vencedor=-quem_jogou, linhas=tuple(do_outro))
        if de_quem_jogou:
            return DesfechoQuatro(vencedor=quem_jogou, linhas=tuple(de_quem_jogou))
        if all(len(p) == self.dimensoes.altura for p in tabuleiro.colunas):
            return DesfechoQuatro(vencedor=None)
        return None


def usar_a_sonda(monkeypatch) -> None:
    """Aponta o contrato para o da sonda e registra a família de regras dela.

    `monkeypatch` desfaz as duas trocas no fim do teste; o cache do contrato é
    limpo agora e precisa ser limpo de novo no fim (ver `limpar_o_cache`).
    """
    from motores.quatro import motor_quatro

    monkeypatch.setattr(
        contrato_quatro, "CAMINHO_DO_CONTRATO", CAMINHO_DO_CONTRATO_DA_SONDA
    )
    familias = dict(motor_quatro.FAMILIAS_DE_REGRAS)
    familias[frozenset({TIPO_SOLTAR, TIPO_TIRAR})] = RegrasSondaQuatro
    monkeypatch.setattr(motor_quatro, "FAMILIAS_DE_REGRAS", familias)
    contrato_quatro._bytes_do_contrato.cache_clear()


def limpar_o_cache() -> None:
    """Depois do teste, o próximo volta a ler o contrato do espelho."""
    contrato_quatro._bytes_do_contrato.cache_clear()
