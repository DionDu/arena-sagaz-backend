"""⛔ O desafio nao pode depender de o adversario jogar mal (regra do dono, 11/09/2026).

═══════════════════════════════════════════════════════════════════════════
⚠️ A DISTINCAO QUE ESTE MODULO FAZ
═══════════════════════════════════════════════════════════════════════════

O dono curou a primeira fila de verdade e escreveu:

> *"O problema nao e o adversario abrir a cadeia, o problema e quando ele abre a
> cadeia sendo que ha diversos outros tracos que nem entregariam caixa de graca.
> O 'entregar' cadeia em um desafio deveria ser meio que forcado: eu humano cedo
> 2 caixas para a CPU e o obrigo a abrir a cadeia. Quando ele abre a cadeia eu
> capturo tudo. E a jogada double dealing."*

⚠️ Ele esta certo, e a distincao e a que faltava. **Abrir cadeia nao e erro** — e
como o Jogo dos Pontinhos termina: chega um momento em que todo traco livre
entrega alguma coisa, e alguem tem de abrir. Medido nas partidas reais do `prd`
(120 partidas), das 195 cadeias de 3+ caixas abertas, **146 eram forcadas** e so
49 tinham alternativa segura.

**Sao duas situacoes diferentes, e so uma delas da um desafio honesto:**

  · ⛔ **ERRO** — ele abriu **existindo** traco que entregava zero. O desafio
    nasce de burrice, e some no dia em que o motor melhorar;
  · ✅ **FORCADO** (*zugzwang*) — nao havia traco seguro. Quem o colocou ali foi
    quem resolve o desafio, cedendo caixas de proposito para devolver a vez. Essa
    e a habilidade de verdade, e e o que se quer premiar.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ISTO NAO PRECISA DE BUSCA
═══════════════════════════════════════════════════════════════════════════

Nao se pergunta *"qual era o melhor lance?"* — isso exigiria o motor e seria caro
e discutivel. Pergunta-se **"existia algum lance que entregava zero?"**, que e
uma contagem: aplica o traco e ve se o outro lado tem caixa para fechar.

⚠️ E a busca pelo lance seguro **para no primeiro que achar**: a pergunta e se
*existia* alternativa, nao quantas.
"""

from __future__ import annotations

from typing import Any, Protocol

#: A partir de quantas caixas entregues a recusa vale.
#:
#: ⚠️ **1 e a regra como o dono a escreveu** — *"se ele entregou caixas e existia
#: um traco livre que entregaria zero"*. Fica nomeado, e nao escrito no meio do
#: codigo, porque e o unico botao deste modulo: se a fila secar, e aqui que se
#: afrouxa, e qualquer numero maior que 1 e uma decisao de produto.
MINIMO_DE_CAIXAS_ENTREGUES = 1


class Arbitro(Protocol):
    """O que este modulo precisa de um motor: as regras, e nada de busca.

    ⚠️ **Nao ha `escolher_lance` aqui de proposito.** Este modulo julga uma fita
    que ja existe; se ele pudesse escolher lances, alguem acabaria usando-o para
    decidir a jogada, e a fronteira "validar nao e jogar" iria junto.
    """

    def lances_legais(self, estado: Any) -> list[str]: ...
    def aplicar(self, estado: Any, lance: str) -> Any: ...


def _caixas_no_tabuleiro(estado: Any) -> int:
    """Quantas caixas ja foram fechadas, somando os dois lados."""
    placar = estado.placar
    return placar[1] + placar[-1]


def caixas_entregues(arbitro: Arbitro, estado: Any, lance: str) -> int:
    """Quantas caixas o ADVERSARIO leva de graca logo depois deste lance.

    Args:
        arbitro: o motor, so para as regras.
        estado: a posicao **antes** do lance.
        lance: o rotulo do traco (`H_0_1`).

    Returns:
        O tamanho da cadeia entregue. `0` quando o lance nao entrega nada.

    ⚠️ **Fechar caixa nao entrega nada**: quem fecha joga de novo, entao a vez nem
    chega ao outro lado. E o primeiro caso tratado, e sem ele todo lance que
    fecha caixa seria contado como entrega.

    ⚠️ **A conta e gulosa: o outro lado leva tudo o que puder.** Nao e o que um
    especialista faz (ele as vezes recusa as duas ultimas, para manter a vez —
    e o proprio double-cross), mas e o teto do que aquele lance oferece, e e o
    numero certo para a pergunta *"isso entregou alguma coisa?"*.
    """
    depois = arbitro.aplicar(estado, lance)
    if depois.vez_de == estado.vez_de:
        return 0  # fechou caixa: a vez nem passou

    levadas = 0
    atual = depois
    while True:
        antes = _caixas_no_tabuleiro(atual)
        seguinte = next(
            (
                candidato
                for lance_do_outro in arbitro.lances_legais(atual)
                if _caixas_no_tabuleiro(candidato := arbitro.aplicar(atual, lance_do_outro))
                > antes
            ),
            None,
        )
        if seguinte is None:
            return levadas
        levadas += _caixas_no_tabuleiro(seguinte) - antes
        atual = seguinte


def lance_seguro(arbitro: Arbitro, estado: Any) -> str | None:
    """Um traco que nao entrega caixa nenhuma, se existir.

    Returns:
        O rotulo do primeiro traco seguro encontrado, ou `None` se **todos**
        entregam — que e a definicao operacional de zugzwang aqui.

    ⚠️ Devolve o rotulo, e nao um booleano, porque quem recusa um desafio precisa
    poder dizer **qual** era a alternativa. Sem isso a recusa vira um "nao" sem
    argumento, e a curadoria nao tem como conferir se a regra esta certa.
    """
    return next(
        (
            lance
            for lance in arbitro.lances_legais(estado)
            if caixas_entregues(arbitro, estado, lance) == 0
        ),
        None,
    )


def dependeu_de_erro(
    arbitro: Arbitro,
    inicial: Any,
    fita: list[dict[str, Any]],
    jogador: int,
) -> str | None:
    """A fita tem algum lance do ADVERSARIO que entregou caixas tendo saida?

    Args:
        arbitro: o motor, so para as regras.
        inicial: a posicao de partida do desafio.
        fita: os passos do gabarito, cada um com `n`, `jogador` e `lance`.
        jogador: quem resolve o desafio (`+1` ou `-1`).

    Returns:
        Uma frase dizendo qual lance e qual era a alternativa — ⚠️ pronta para ir
        ao diagnostico do candidato —, ou `None` quando nenhum lance do
        adversario foi erro.

    ⚠️ **Percorre a fita inteira, e nao so ate o objetivo cair.** Um erro depois
    do objetivo nao afeta a solucao, mas afeta o **replay**, que e o que a pessoa
    ve; e a fita so vai ate o objetivo de qualquer forma.

    ⛔ **A ordem das duas perguntas importa para o custo.** Primeiro *"este lance
    entregou alguma coisa?"* (uma conta); so entao *"existia alternativa?"* (ate
    31 contas). Invertida, a funcao ficaria trinta vezes mais cara para dizer a
    mesma coisa na esmagadora maioria dos passos.
    """
    atual = inicial
    for passo in fita:
        lance = passo["lance"]
        de_quem = passo.get("jogador", atual.vez_de)

        if de_quem != jogador:
            entregou = caixas_entregues(arbitro, atual, lance)
            if entregou >= MINIMO_DE_CAIXAS_ENTREGUES:
                alternativa = lance_seguro(arbitro, atual)
                if alternativa is not None:
                    return (
                        f"lance {passo.get('n', '?')} do adversario ({lance}) "
                        f"entregou {entregou} caixa(s), e {alternativa} "
                        f"entregava zero"
                    )

        atual = arbitro.aplicar(atual, lance)

    return None
