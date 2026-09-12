"""A CADEIA LONGA: montar o tabuleiro para capturar muitas caixas de uma vez.

═══════════════════════════════════════════════════════════════════════════
⚠️ A IDEIA E DO DONO, 12/09/2026
═══════════════════════════════════════════════════════════════════════════

> *"Capturar uma sequencia longa de cadeias. Deixa o usuario conectar tracos de
> tal forma que consiga montar uma cadeia extremamente longa, e depois captura-la,
> ao inves do adversario. Ao inves de quebrar o tabuleiro em varias cadeias
> pequenas, formar cadeias longas (ex: 5 ou mais caixas)."*

E, sobre como medir:

> *"Talvez voce possa ate avaliar o cumprimento do desafio pela quantidade de
> lances seguidos, ja que ao capturar caixa o humano/cpu continuam jogando ate
> nao capturar mais nenhuma."*

⚠️ **Essa observacao e a chave da medida, e ela dispensa geometria.** Quem fecha
caixa joga de novo; entao uma **corrida de lances consecutivos do mesmo jogador**
e, literalmente, uma cadeia sendo capturada. Nao e preciso reconhecer a forma da
cadeia no tabuleiro para julgar o desafio — basta olhar a fita.

⛔ **Mas a medida conta CAIXAS, e nao lances.** Um unico traco pode fechar **duas**
caixas de uma vez (o que separa duas caixas com tres lados), e a frase publicada
promete caixas: *"capture N ou mais caixas em sequencia"*. Contar lances daria um
numero menor que o placar mostra, e a pessoa veria o desafio recusado com o
numero certo na tela.

═══════════════════════════════════════════════════════════════════════════
O ARQUITETO: quem resolve este desafio, e por que ele nao e o Magno
═══════════════════════════════════════════════════════════════════════════

⛔ **O Magno NAO serve de gabarito aqui.** Ele joga para vencer, e vencer no
Pontinhos e frequentemente o contrario do que este desafio pede: ele parte o
tabuleiro em cadeias curtas e controla a paridade. O desafio pede o oposto —
**construir** uma cadeia grande e ficar com ela.

O arquiteto joga com tres regras, nesta ordem:

    1. ha caixa para fechar?     → fecha (e a captura da cadeia)
    2. ha traco que nao entrega? → joga um deles, o que menos parte o tabuleiro
    3. nenhum e seguro?          → abre a MENOR cadeia disponivel

⚠️ **A regra 2 e o que constroi a cadeia**, e ela ja existe no projeto:
`abertura_forcada.lance_seguro` responde *"este traco entrega caixa?"*. Marcar so
tracos seguros e, por definicao, nunca levar uma caixa ao terceiro lado — e o
tabuleiro vai naturalmente ficando com caixas de grau 2 ligadas umas as outras,
que e a cadeia.

⚠️ **A regra 3 e o sacrificio minimo**, e ela existe porque o zugzwang chega: uma
hora *todo* traco entrega. Abrir a menor cadeia e o que preserva a maior para
depois — e e exatamente o que o dono descreveu ao falar de ceder duas caixas para
o adversario ser obrigado a abrir a cadeia longa.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from . import abertura_forcada
from .motor_pontinhos import partida_para_dataset

#: O tamanho a partir do qual o analisador do laboratorio chama de "cadeia longa".
#:
#: ⚠️ **Nao e escolha deste arquivo** — e a definicao que a CNN ja usa no canal de
#: broadcast de cadeias (`analisador_estrutural_pontinhos`). Repeti-la com outro
#: numero faria o desafio falar de uma coisa e a rede de outra.
CADEIA_LONGA = 3


class Arbitro(Protocol):
    """Quem sabe as regras: quais tracos valem e o que cada um faz."""

    def lances_legais(self, estado: Any) -> list[str]: ...
    def aplicar(self, estado: Any, lance: str) -> Any: ...


def _caixas_no_tabuleiro(estado: Any) -> int:
    """Quantas caixas ja foram fechadas, somando os dois lados."""
    placar = estado.placar
    return placar[1] + placar[-1]


# ═══════════════════════════════════════════════════════════════════════════
# 1. A MEDIDA — quantas caixas em sequencia
# ═══════════════════════════════════════════════════════════════════════════


def maior_captura_em_sequencia(
    inicial: Any,
    fita: Sequence[Mapping[str, Any]],
    jogador: int,
) -> int:
    """A maior cadeia que `jogador` capturou de uma vez, em caixas.

    Args:
        inicial: a posicao de partida do desafio. ⚠️ **Sem arbitro**, de
            proposito: no Pontinhos a posicao E a sequencia de lances, e o
            proprio estado sabe seguir com `com_lance`. Pedir o motor aqui
            obrigaria quem mede — o juiz, que nao instancia motor — a carregar
            um so para aplicar lances que o estado ja aplica.
        fita: os lances, cada um `{"n", "jogador", "lance"}` — o vocabulario do
            log de partidas.
        jogador: de quem e o desafio (`+1` ou `-1`).

    Returns:
        Quantas caixas ele fechou na melhor **corrida** — lances consecutivos
        sem a vez passar. `0` se ele nunca fechou nada.

    ⚠️ **A corrida sai da FITA, e nao de uma regra escrita aqui.** Quem decide se
    houve lance extra e o motor; a fita e o registro do que ele decidiu. Reimplementar
    a alternancia neste arquivo seria uma segunda fonte da verdade sobre ela — e
    as duas discordariam no primeiro caso de borda. E o mesmo raciocinio de
    `medidor_por_fita.turnos_da_fita`.

    ⚠️ **Reproduz a partida para contar**, porque a fita diz *quem* jogou e *qual*
    traco, mas nao quantas caixas aquele traco fechou.
    """
    maior = 0
    corrida = 0
    atual = inicial
    jogador_anterior: int | None = None

    for passo in fita:
        de_quem = passo["jogador"]
        # Trocou a vez? A corrida anterior acabou.
        if de_quem != jogador_anterior:
            corrida = 0
            jogador_anterior = de_quem

        antes = _caixas_no_tabuleiro(atual)
        atual = atual.com_lance(passo["lance"])
        fechadas = _caixas_no_tabuleiro(atual) - antes

        if de_quem == jogador:
            corrida += fechadas
            maior = max(maior, corrida)

    return maior


# ═══════════════════════════════════════════════════════════════════════════
# 2. A FORMA DO TABULEIRO — quanto ha de cadeia agora
# ═══════════════════════════════════════════════════════════════════════════


def stats_de_cadeias(estado: Any) -> tuple[int, int, int]:
    """`(quantas cadeias longas, caixas nelas, maior cadeia)` na posicao atual.

    ⛔ **A conversao de formato NAO e detalhe.** O analisador espera a matriz no
    formato do DATASET (`{0, 1, 8, 9}`); passar a matriz crua devolve **zero
    cadeias em toda posicao, sem erro nenhum** — uma medicao inteira ja "provou"
    assim que nao havia cadeia longa em lugar algum (11/09/2026).

    ⚠️ O import e local de proposito: `motor_pontinhos` poe o espelho do
    laboratorio no `sys.path` ao ser importado, entao `jogos.jogo_pontinhos.*` so
    existe **depois** dele.
    """
    from jogos.jogo_pontinhos.motor.analisador_estrutural_pontinhos import (  # noqa: E402
        extrair_stats_cadeias,
    )

    return extrair_stats_cadeias(partida_para_dataset(estado.tabuleiro.matriz))


# ═══════════════════════════════════════════════════════════════════════════
# 3. O ARQUITETO — quem monta a cadeia e depois a captura
# ═══════════════════════════════════════════════════════════════════════════


def _lance_que_mais_fecha(arbitro: Arbitro, estado: Any) -> str | None:
    """O traco que fecha MAIS caixas agora, ou `None` se nenhum fecha.

    ⚠️ Prefere o que fecha duas — o traco entre duas caixas que ja tem tres lados
    fecha as duas de uma vez, e deixar isso passar encurtaria a corrida por
    desatencao.
    """
    antes = _caixas_no_tabuleiro(estado)
    melhor, ganho_do_melhor = None, 0
    for lance in arbitro.lances_legais(estado):
        ganho = _caixas_no_tabuleiro(arbitro.aplicar(estado, lance)) - antes
        if ganho > ganho_do_melhor:
            melhor, ganho_do_melhor = lance, ganho
    return melhor


def _melhor_seguro(arbitro: Arbitro, estado: Any) -> str | None:
    """Entre os tracos que nao entregam nada, o que deixa a maior cadeia.

    ⚠️ **Nao basta ser seguro.** Todo traco seguro serve para nao dar caixa; mas
    entre eles ha os que **partem** o tabuleiro em pedacos pequenos e os que
    mantem as caixas de grau 2 ligadas. O desafio e sobre a segunda coisa, e por
    isso a escolha olha a forma resultante — `stats_de_cadeias` responde qual
    ficou com a maior cadeia.

    ⚠️ **Desempate pela soma das cadeias longas**, e nao pelo primeiro da lista:
    duas posicoes com a mesma maior cadeia nao sao equivalentes se uma tem outra
    cadeia longa guardada atras dela.
    """
    melhor: str | None = None
    nota_do_melhor: tuple[int, int] | None = None

    for lance in arbitro.lances_legais(estado):
        if abertura_forcada.caixas_entregues(arbitro, estado, lance) != 0:
            continue
        _quantas, total, maior = stats_de_cadeias(arbitro.aplicar(estado, lance))
        nota = (maior, total)
        if nota_do_melhor is None or nota > nota_do_melhor:
            melhor, nota_do_melhor = lance, nota

    return melhor


def _menor_sacrificio(arbitro: Arbitro, estado: Any) -> str:
    """Em zugzwang, o traco que entrega a MENOR cadeia.

    ⚠️ **Chamado so quando todo traco entrega alguma coisa** — e ai a pergunta
    deixa de ser *"como nao dar?"* e passa a ser *"qual dar?"*. Entregar a menor
    e o que guarda a maior para a vez seguinte, que e o proprio enredo do desafio:
    o adversario leva duas caixas e fica obrigado a abrir a cadeia grande.
    """
    legais = arbitro.lances_legais(estado)
    return min(
        legais, key=lambda lance: abertura_forcada.caixas_entregues(arbitro, estado, lance)
    )


def lance_do_arquiteto(arbitro: Arbitro, estado: Any) -> str:
    """O lance de quem esta construindo uma cadeia longa para capturar depois.

    ⚠️ **Nao e "jogar bem", e jogar PARA ESTE OBJETIVO.** Um Magno no lugar dele
    partiria o tabuleiro em cadeias curtas e controlaria a paridade — que e como
    se vence, e o oposto do que o desafio pede.
    """
    fecha = _lance_que_mais_fecha(arbitro, estado)
    if fecha is not None:
        return fecha

    seguro = _melhor_seguro(arbitro, estado)
    if seguro is not None:
        return seguro

    return _menor_sacrificio(arbitro, estado)
