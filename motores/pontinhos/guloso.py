"""O JOGADOR GULOSO do Pontinhos: nunca recusa uma caixa.

═══════════════════════════════════════════════════════════════════════════
⚠️ PARA QUE ELE EXISTE — A IDEIA E DO DONO, 11/09/2026
═══════════════════════════════════════════════════════════════════════════

> *"1. Entregamos um estado para o usuario com caixas a capturar. Se ele capturar
> de forma gulosa ele fecha o jogo com 5 caixas. 2. Se capturar usando double
> dealing ele fecha o jogo com 7 caixas. 3. Neste exemplo o desafio seria:
> capture 7 ou mais caixas."*

⚠️ **E o desenho que dispensa o filtro de erro do adversario.** Ate aqui a
pergunta era *"o adversario errou?"*; agora ela nao precisa ser feita, porque a
dificuldade deixa de depender dele — ela vem da escolha de **quem resolve**. O
objetivo exclui a solucao ingenua **por construcao**: quem so captura nao chega
la, por mais que tente.

⚠️ **E o desafio fica auto-verificavel:** uma posicao em que o guloso ja consegue
o numero simplesmente **nao vira desafio**, e ninguem precisa opinar sobre
dificuldade. Medido em 60 posicoes reais do `prd`: 16 (27%) rendem `D > G`, com
diferencas de +1 a +5 — e um dos exemplos saiu exatamente `(guloso 5, magno 7)`,
os numeros que o dono usou sem ter visto o dado.

═══════════════════════════════════════════════════════════════════════════
⛔ O GULOSO E O PROPRIO MAGNO, COM UMA UNICA DIFERENCA
═══════════════════════════════════════════════════════════════════════════

Quando ha caixa para fechar, ele fecha. Em todo o resto, joga igual.

⚠️ **Isso e essencial para a comparacao significar alguma coisa.** Um "jogador
ruim" generico jogaria pior em tudo, e a diferenca `D - G` misturaria *"nao sabe
fazer double dealing"* com *"nao sabe jogar"*. Isolando so a decisao de recusar,
`D - G` mede exatamente a habilidade que o desafio quer cobrar.

⚠️ **E o ADVERSARIO e o mesmo nos dois casos** — o personagem do dia. Se ele
mudasse junto, a diferenca nao seria atribuivel a nada.

⛔ **E tem de ser o personagem do DIA, e nao o Magno.** O adversario publicado
pode ser a Cacau, que erra de proposito em 80% dos lances; um numero medido
contra o Magno descreveria uma partida diferente da que vai ao ar, e o enunciado
prometeria algo que nao vale para aquele desafio.
"""

from __future__ import annotations

from typing import Any, Protocol

from motores.nucleo.papeis import NivelDeMotor


class JogadorComNivel(Protocol):
    """Quem escolhe lance num nivel — a politica do Pontinhos."""

    def escolher_lance(
        self, estado: Any, nivel: NivelDeMotor, limite: Any = None, semente: int | None = None
    ) -> str: ...


class ArbitroComRegras(Protocol):
    """Quem sabe as regras: quais lances valem e o que cada um faz."""

    def lances_legais(self, estado: Any) -> list[str]: ...
    def aplicar(self, estado: Any, lance: str) -> Any: ...


def _caixas_no_tabuleiro(estado: Any) -> int:
    """Quantas caixas ja foram fechadas, somando os dois lados."""
    placar = estado.placar
    return placar[1] + placar[-1]


def lance_que_mais_fecha(arbitro: ArbitroComRegras, estado: Any) -> str | None:
    """O lance que fecha MAIS caixas agora, ou `None` se nenhum fecha.

    ⚠️ **Prefere o que fecha duas**, e nao o primeiro que fecha uma: um traco
    entre duas caixas com tres lados fecha as duas de uma vez, e um guloso que
    nao visse isso seria burro de um jeito diferente do que se quer medir — a
    comparacao mediria desatencao, e nao a recusa do double dealing.
    """
    antes = _caixas_no_tabuleiro(estado)
    melhor, ganho_do_melhor = None, 0
    for lance in arbitro.lances_legais(estado):
        ganho = _caixas_no_tabuleiro(arbitro.aplicar(estado, lance)) - antes
        if ganho > ganho_do_melhor:
            melhor, ganho_do_melhor = lance, ganho
    return melhor


def caixas_do_guloso(
    jogador_politica: JogadorComNivel,
    arbitro: ArbitroComRegras,
    inicial: Any,
    jogador: int,
    *,
    nivel: NivelDeMotor,
    nivel_do_adversario: NivelDeMotor,
    semente_do_lance,
    nu_semente: int,
) -> int:
    """Quantas caixas `jogador` fecha se NUNCA recusar uma caixa.

    Args:
        jogador_politica: quem escolhe lance quando nao ha caixa para fechar.
        arbitro: o motor, para as regras.
        inicial: a posicao de partida do desafio.
        jogador: quem resolve o desafio (`+1` ou `-1`).
        nivel: o nivel com que **ele** joga o resto dos lances.
        nivel_do_adversario: o nivel do personagem do dia.
        semente_do_lance: `(nu_semente, numero) -> int`, a mesma de `job.semente`.
        nu_semente: a semente do candidato.

    Returns:
        As caixas de `jogador` no fim da partida.

    ⚠️ **A semente segue o mesmo esquema do gerador** (uma por numero de lance),
    e nao e detalhe: sem ela, dois calculos da mesma posicao dariam numeros
    diferentes, e ⛔ **o enunciado publicado (`capture N ou mais`) deixaria de ser
    reproduzivel** — o job recalcularia `G` amanha e acharia outro `N` para o
    mesmo desafio.

    ⚠️ **A partida SEMPRE termina**: cada lance ocupa um traco, os tracos sao
    finitos, e nenhum lance os devolve. Por isso o laco nao tem teto de seguranca
    — um teto aqui esconderia um defeito no motor em vez de o denunciar.
    """
    atual = inicial
    numero = 1
    while arbitro.lances_legais(atual):
        if atual.vez_de == jogador:
            lance = lance_que_mais_fecha(arbitro, atual)
        else:
            lance = None

        if lance is None:
            lance = jogador_politica.escolher_lance(
                atual,
                nivel if atual.vez_de == jogador else nivel_do_adversario,
                semente=semente_do_lance(nu_semente, numero),
            )

        atual = arbitro.aplicar(atual, lance)
        numero += 1

    return atual.placar[jogador]
