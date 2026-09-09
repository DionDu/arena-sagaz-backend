"""Os empates que as Regras Oficiais **declaram**, e que a matemática não vê.

O problema, em uma frase
------------------------
A análise retrógrada resolve o jogo e diz quem ganha. Mas as Regras Oficiais
brasileiras declaram **empatados** certos finais em que um lado ganharia se
jogasse à vontade — porque o regulamento lhe dá um número limitado de lances
para concluir. Três damas contra uma dama na grande diagonal é o caso famoso:
ganha em jogo irrestrito, e é empate pela regra.

> **Uma base sem estas regras mente.** Ela reprovaria lances corretos do motor na
> medição do §7.1 da proposta, e faria o app perder finais que o jogador
> brasileiro sabe de cor que são empate. Era o "achado mais caro de ignorar" do
> §6.4, e é o que este módulo resolve.

O que muda na natureza do cálculo
---------------------------------
Estas regras **não perguntam "quem ganha?"** — perguntam **"ganha em quantos
lances?"**. Por isso a análise retrógrada precisou passar a medir a *distância*
até o fim, e não só o resultado. Uma base WLD pura não tem como aplicá-las.

⚠️ Duas ambiguidades que eu NÃO resolvi sozinho
-----------------------------------------------
O texto normativo é econômico, e há dois pontos em que ele admite mais de uma
leitura. Registro a minha e o que ela custa se estiver errada — chutar em
silêncio seria pior:

1. **"após executados 5 lances" — 5 de cada lado, ou 5 no total?** O RESUMO das
   regras (item 18) diz "5 lances **de cada jogador**", e é essa a leitura
   adotada: o lado forte tem 5 lances *seus*. Se a leitura certa for 5 no total,
   a base declara empate tarde demais e algumas vitórias sobram indevidamente.
2. **Art. 100 — a dama solitária tem de estar na grande diagonal quando?** No
   começo da contagem, o tempo todo, ou no fim? Adotei "na posição avaliada" —
   se ela está lá, a regra vale. Se a leitura certa for "o tempo todo", a base
   declara empate em posições demais.

**Como confirmar:** as duas se resolvem contra o Aurora Borealis, que tem base de
finais para as brasileiras (§3 da proposta). Basta comparar algumas centenas de
posições dessas fatias. Está registrado como pendência da etapa 6.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass, field

from jogos.jogo_damas.motor.tabuleiro_damas import GRANDE_DIAGONAL, Cor, Peca
from jogos.jogo_damas.tablebase.indice_damas import (
    DERROTA,
    EMPATE,
    VITORIA,
    Fatia,
)


@dataclass(frozen=True)
class RegraDeEmpate:
    """Um empate declarado pelo regulamento, como dado conferível.

    Mesmo padrão das cláusulas de captura: o texto oficial **copiado**, onde
    achá-lo, e o efeito expresso em número. Parafrasear regra é como o erro entra.

    Attributes:
        materiais: as combinações `(pedras brancas, damas brancas, pedras pretas,
            damas pretas)` a que a regra se aplica. Vazio quando a regra vale por
            um critério e não por uma lista — ver `vale_para_fatia`.
        so_damas: se verdadeiro, a regra vale para **qualquer** fatia sem pedras.
        limite_em_lances: quantos lances o lado forte tem para concluir.
        exige_dama_solitaria_na_grande_diagonal: condição extra do art. 100,
            conferida posição a posição e não por fatia.
    """

    identificador: str
    onde_no_documento: str
    texto_oficial: str
    limite_em_lances: int
    materiais: frozenset[tuple[int, int, int, int]] = field(default_factory=frozenset)
    so_damas: bool = False
    exige_dama_solitaria_na_grande_diagonal: bool = False

    def vale_para_fatia(self, fatia: Fatia) -> bool:
        if self.so_damas:
            return fatia.total_de_pedras == 0
        return fatia.contagens in self.materiais

    def limite_em_meios_lances(self, quem_tem_a_vez_esta_ganhando: bool) -> int:
        """Quantos meios-lances o lado forte tem, contados desta posição.

        Se o **forte** é quem joga, ele gasta 5 lances seus intercalados por 4
        do adversário — 9 meios-lances. Se quem joga é o **fraco**, entram 5 do
        forte intercalados por 5 do fraco — 10.
        """
        return (2 * self.limite_em_lances - 1 if quem_tem_a_vez_esta_ganhando
                else 2 * self.limite_em_lances)


# ---------------------------------------------------------------------------
# As regras, do texto normativo
# ---------------------------------------------------------------------------

_TRINTA_E_DOIS_MENOS = lambda *c: c  # noqa: E731  (só para alinhar a leitura)


def _nos_dois_sentidos(
    combinacoes: list[tuple[int, int, int, int]]
) -> frozenset[tuple[int, int, int, int]]:
    """Acrescenta o espelho de cada combinação.

    O regulamento descreve os finais de um lado só ("duas damas contra dama"),
    mas eles valem com as cores trocadas. Esquecer o espelho faria a regra valer
    só quando as brancas fossem o lado forte — viés silencioso e absurdo.
    """
    com_espelho = set()
    for pb, db, pp, dp in combinacoes:
        com_espelho.add((pb, db, pp, dp))
        com_espelho.add((pp, dp, pb, db))
    return frozenset(com_espelho)


VINTE_LANCES_SO_DE_DAMAS = RegraDeEmpate(
    identificador="art_97b_vinte_lances",
    onde_no_documento="Art. 97b; RESUMO DAS REGRAS, item 16",
    texto_oficial=(
        "for verificado no tabuleiro de 64 casas, que durante 20 (vinte) lances "
        "sucessivos foram feitos apenas movimentos de damas, sem qualquer tipo "
        "de captura ou deslocamento de pedras"
    ),
    limite_em_lances=20,
    so_damas=True,
)
"""A regra geral dos finais só de damas.

Repare por que ela cabe numa base de finais apesar de falar de *histórico*: numa
fatia sem pedras, **todo** lance é de dama, e qualquer captura muda de fatia. Ou
seja, dentro da fatia o contador nunca zera — então "ganhar em até 20 lances a
partir daqui" é exatamente o que a regra pede.
"""

FINAIS_DECLARADOS_EMPATADOS = RegraDeEmpate(
    identificador="art_99_cinco_lances",
    onde_no_documento="Art. 99; RESUMO DAS REGRAS, item 18",
    texto_oficial=(
        "Os finais de duas damas contra dama, uma dama e uma pedra contra uma "
        "dama ou uma dama contra uma dama são considerados empatados após "
        "executados 5 (cinco) lances no máximo, no tabuleiro de 64 ou 100 casas."
    ),
    limite_em_lances=5,
    materiais=_nos_dois_sentidos([
        (0, 2, 0, 2),   # 2 damas × 2 damas
        (0, 2, 0, 1),   # 2 damas × 1 dama
        (0, 2, 1, 1),   # 2 damas × 1 dama e 1 pedra
        (0, 1, 0, 1),   # 1 dama × 1 dama
        (0, 1, 1, 1),   # 1 dama × 1 dama e 1 pedra
    ]),
)
"""Os cinco finais que o art. 99 lista, com as cores nos dois sentidos.

A lista veio do RESUMO item 18 somado aos diagramas do art. 99 — os dois trechos
se completam, e nenhum deles sozinho traz as cinco combinações.
"""

TRES_DAMAS_CONTRA_UMA_NA_GRANDE_DIAGONAL = RegraDeEmpate(
    identificador="art_100_grande_diagonal",
    onde_no_documento="Art. 100 (tabuleiro de 64 casas)",
    texto_oficial=(
        "No tabuleiro de 64 casas os finais de três damas ou duas damas e uma "
        "pedra ou uma dama e duas pedras, contra uma dama localizada na grande "
        "diagonal são considerados empatados após executados 5 (cinco) lances "
        "no máximo."
    ),
    limite_em_lances=5,
    materiais=_nos_dois_sentidos([
        (0, 3, 0, 1),   # 3 damas × 1 dama
        (1, 2, 0, 1),   # 2 damas e 1 pedra × 1 dama
        (2, 1, 0, 1),   # 1 dama e 2 pedras × 1 dama
    ]),
    exige_dama_solitaria_na_grande_diagonal=True,
)
"""O caso famoso, e o que mais surpreende quem não conhece o regulamento.

Três damas contra uma **ganham** em jogo irrestrito. Pela regra brasileira, com
a dama solitária na grande diagonal, é **empate**. Uma base que não soubesse
disso reprovaria lances corretos do motor.
"""

REGRAS: tuple[RegraDeEmpate, ...] = (
    FINAIS_DECLARADOS_EMPATADOS,
    TRES_DAMAS_CONTRA_UMA_NA_GRANDE_DIAGONAL,
    VINTE_LANCES_SO_DE_DAMAS,
)
"""Na ordem em que devem ser tentadas: **da mais apertada para a mais frouxa**.

As fatias do art. 99 também são fatias só de damas, então as duas regras se
aplicam às mesmas posições. Vale a de limite menor — cinco lances, não vinte.
"""


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------


def _dama_solitaria_esta_na_grande_diagonal(tabuleiro, fatia: Fatia) -> bool:
    """O lado fraco tem exatamente uma dama, e ela está na grande diagonal?

    "Lado fraco" aqui é o que tem **só uma dama e nenhuma pedra** — é assim que o
    art. 100 descreve o defensor.
    """
    for cor, (pedras, damas) in (
        (Cor.BRANCAS, (fatia.pedras_brancas, fatia.damas_brancas)),
        (Cor.PRETAS, (fatia.pedras_pretas, fatia.damas_pretas)),
    ):
        if pedras == 0 and damas == 1:
            peca = Peca.DAMA_BRANCA if cor is Cor.BRANCAS else Peca.DAMA_PRETA
            casa = next(c for c in range(1, 33) if tabuleiro.ler(c) is peca)
            return casa in GRANDE_DIAGONAL
    return False


def regra_aplicavel(fatia: Fatia) -> RegraDeEmpate | None:
    """A regra de empate mais apertada que vale para esta fatia, se houver."""
    candidatas = [r for r in REGRAS if r.vale_para_fatia(fatia)]
    if not candidatas:
        return None
    return min(candidatas, key=lambda r: r.limite_em_lances)


def aplicar_empates_declarados(
    fatia: Fatia, valores: bytearray, distancias: array
) -> int:
    """Converte em empate as vitórias que o regulamento não deixa concluir.

    Altera `valores` **no lugar** e devolve quantas posições mudaram.

    Precisa rodar **logo depois** de a fatia ser resolvida e **antes** de
    qualquer fatia maior consultá-la: as fatias grandes decidem olhando o
    resultado das pequenas, e se a regra chegar atrasada elas terão decidido em
    cima de vitórias que não existem.
    """
    regra = regra_aplicavel(fatia)
    if regra is None:
        return 0

    mudadas = 0
    for indice in range(fatia.tamanho):
        resultado = valores[indice]
        if resultado == EMPATE:
            continue

        distancia = distancias[indice]
        if distancia < 0:
            continue

        limite = regra.limite_em_meios_lances(resultado == VITORIA)
        if distancia <= limite:
            continue

        if regra.exige_dama_solitaria_na_grande_diagonal:
            tabuleiro = fatia.para_posicao(indice)
            if tabuleiro is None:
                continue
            if not _dama_solitaria_esta_na_grande_diagonal(tabuleiro, fatia):
                continue

        # Nem vitória nem derrota: o regulamento declarou empate antes de o
        # jogo perfeito conseguir concluir.
        valores[indice] = EMPATE
        mudadas += 1

    return mudadas
