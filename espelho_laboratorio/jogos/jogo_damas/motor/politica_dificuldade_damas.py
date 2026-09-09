"""O que cada nível de dificuldade das damas significa **para quem joga**.

Por que este módulo existe separado de `busca_damas.py`
=======================================================
`Nivel`, lá, é o orçamento de **busca**: profundidade, quiescência, teto de nós.
São parâmetros do motor, e o motor não deve saber nada de apresentação.

Aqui ficam as decisões que o jogador percebe e que **não mudam a força**: quanto
tempo o personagem parece pensar, e quantos segundos o humano tem para jogar.
Misturar as duas coisas num objeto só faria mexer no relógio da tela parecer
mexer na dificuldade da IA.

O espelho deste arquivo no app é `politica_dificuldade_velha.dart` (o relógio) e
`core/jogos/tempo_de_pensar.dart` (a espera do personagem).

⚠️ Os números daqui são **estimativa declarada**, decidida com o dono em
2026-08-14, e não medição. A calibração de verdade vem das partidas reais depois
da publicação. Só a Cacau tem número vindo de partida jogada.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# A espera do personagem — o padrão do hub, com a chave do Remote Config
# ---------------------------------------------------------------------------

CHAVE_REMOTE_CONFIG = "delay_ms_personagem_pensando_damas"
"""A chave que o app consulta para saber a base da espera.

Descrição cadastrada no console, palavra por palavra:

    Damas - delay e milisegundos para o personagem jogar. Este valor é
    multiplicado pelo parâmetro de cada personagem nos jogos e define após
    quanto tempo o personagem efetuará sua jogada após todos os cálculos
    (Minimax, busca CNN etc serem realizados).

O nome segue `delay_ms_personagem_pensando_<jogoId>`, como as chaves do
Pontinhos e da velha. Mudar o padrão aqui faria o Hub, que percorre a lista de
jogos montando as chaves, procurar uma que ninguém criou — e cair no *fallback*
para sempre, em silêncio.
"""

BASE_FALLBACK_MS = 400
"""A base usada quando o Remote Config não responde, ou responde com lixo.

⚠️ **Não é um número livre: existe um piso aritmético.** A espera do Magno é
`2,0 × base`, e ela precisa ser maior que o tempo que a busca dele realmente
leva, senão a pausa zera e o Magno passa a ser o personagem mais LENTO da tela —
exatamente o oposto do que o dono pediu.

⚠️ **Estes 400 ms estão ABAIXO do piso no celular de entrada.** Medido em
21/08/2026, em aparelhos reais, com a `bancada_aparelho`:

| aparelho | nós/s | 96.000 nós custam | piso que a base precisaria ter |
|---|---|---|---|
| Galaxy A06 | 71.614 | **1,34 s** | **671 ms** |
| iPhone 15 Pro Max | 536.263 | 0,18 s | 90 ms |

O "Galaxy A35, 160.593 nós/s" que era o aparelho de referência declarado, e de
onde saiu o piso de 299 ms, é **2,2× mais rápido** que o A06 — não serve de
referência para o compromisso do produto, que é com o `minSdk 24`.

A conta completa, com esta base, e as duas colunas de busca que a medição
separou:

| nível | multiplicador | espera-alvo | busca (iPhone 15 Pro Max) | busca (Galaxy A06) | pausa que sobra no A06 |
|---|---|---|---|---|---|
| Cacau | 5,0× | 2,00 s | ~0,00 s | ~0,00 s | 2,00 s |
| Pita | 4,0× | 1,60 s | ~0,00 s | ~0,00 s | 1,60 s |
| Tex | 3,0× | 1,20 s | ~0,00 s | ~0,01 s | 1,19 s |
| Magno | 2,0× | 0,80 s | 0,18 s | **1,34 s** | **0 — e estoura em 0,54 s** |

Repare que **só o Magno gasta busca de verdade**: os três primeiros param na
profundidade (1, 2 e 3) e visitam dezenas de nós, não milhares. É por isso que o
piso da base depende só dele — e por isso a inversão pedida pelo dono ("o Magno
não pode ser o mais lento") se mantém no iPhone e **se perde** no A06.

⚠️ **O que NÃO se perde no A06 é a força.** A rede de segurança do `sagaz` é de
3 s, e 1,34 s não a dispara: o A06 completa os 96.000 nós e enfrenta exatamente o
mesmo Magno que o iPhone. É para isso que o orçamento é em nós. O defeito medido
aqui é de **ritmo**, e só.

⚠️ **Para desligar a espera pelo console, ponha `1`, não `0`** — zero é
indistinguível de "chave ausente" e cai no fallback, o oposto do pretendido.
Mesma armadilha documentada em `tempo_de_pensar.dart`.
"""

MULTIPLICADOR_DO_DELAY: dict[str, float] = {
    "cacau": 5.0,
    "pita": 4.0,
    "tex": 3.0,
    "sagaz": 2.0,
}
"""Quantas vezes a base cada personagem espera — **decrescente com a força**.

Decisão do dono em 2026-08-14: *"quero que o usuário tenha a percepção de que os
personagens mais burros ficam mais tempo pensando numa jogada melhor, enquanto o
Magno joga mais rápido. Não quero que o Magno seja mais lento que os demais."*

⚠️ **São diferentes dos multiplicadores dos outros dois jogos** (2,0 · 1,7 · 1,4
· 1,0, em `tempo_de_pensar.dart`), e a diferença é deliberada: lá a razão entre o
mais lento e o mais rápido é 2,0×; aqui é **2,5×**, para a inversão continuar
visível apesar de o Magno gastar 0,6 s de busca real. Nos outros jogos o motor
decide em microssegundos e a espera é inteiramente encenação — em damas, metade
da espera do Magno é trabalho de verdade.
"""


def espera_alvo_ms(identificador_do_nivel: str, base_ms: int = BASE_FALLBACK_MS) -> int:
    """Quanto deve durar o intervalo **inteiro** entre o lance do humano e o da CPU.

    É `multiplicador × base`, na forma do hub. Note que é o intervalo TOTAL —
    busca mais encenação —, e não a pausa: quem calcula a pausa é
    `pausa_de_encenacao`.
    """
    return round(MULTIPLICADOR_DO_DELAY[identificador_do_nivel] * base_ms)


def pausa_de_encenacao_ms(
    identificador_do_nivel: str,
    ms_da_busca: float,
    base_ms: int = BASE_FALLBACK_MS,
) -> int:
    """Quanto a tela deve esperar **depois** de a busca terminar.

    Args:
        identificador_do_nivel: `"cacau"`, `"pita"`, `"tex"` ou `"sagaz"`.
        ms_da_busca: quanto a busca realmente levou, **neste** aparelho.
        base_ms: o valor vindo do Remote Config, já interpretado.

    Returns:
        Os milissegundos de pausa. **Nunca negativo**: quando a busca já passou
        do alvo — celular lento, ou posição cara —, a resposta é zero e o jogador
        simplesmente esperou mais. Somar uma pausa por cima aí seria castigar
        duas vezes quem tem o aparelho pior.

    Por que subtrair a busca, em vez de somar a espera ao que ela levou
    -------------------------------------------------------------------
    Porque somar inverteria a ordem que o dono pediu. A busca do Magno custa
    0,60 s e a da Cacau custa ~0,00 s: com espera somada, o Magno seria sempre o
    mais lento da tela. Subtraindo, o intervalo total é o que o multiplicador
    manda, **independentemente do aparelho** — num celular lento a busca come
    mais e a pausa encolhe sozinha.
    """
    restante = espera_alvo_ms(identificador_do_nivel, base_ms) - ms_da_busca
    return int(restante) if restante > 0 else 0


def interpretar_base_do_remote_config(bruto: int) -> int:
    """Traduz o valor **bruto** da chave na base a usar.

    Chave ausente devolve `0` no SDK do Firebase, e negativo não faz sentido para
    uma espera — os dois casos caem no fallback. Espelha
    `interpretarBaseDePensar` do app, de propósito: é a mesma regra, e ela
    precisa dar o mesmo resultado dos dois lados.
    """
    return bruto if bruto > 0 else BASE_FALLBACK_MS


# ---------------------------------------------------------------------------
# O relógio do humano
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApresentacaoDoNivel:
    """As decisões de ritmo de um nível que não são a espera do personagem.

    Attributes:
        timer_do_humano_segundos: quantos segundos o jogador tem por lance.
            `None` = sem relógio.
    """

    timer_do_humano_segundos: int | None


APRESENTACAO: dict[str, ApresentacaoDoNivel] = {
    "cacau": ApresentacaoDoNivel(None),
    "pita": ApresentacaoDoNivel(30),
    "tex": ApresentacaoDoNivel(25),
    "sagaz": ApresentacaoDoNivel(20),
}
"""⚠️ **A Cacau não tem relógio**, e isso é regra do hub, não esquecimento
(RF-VLH-012): quem está aprendendo não deve jogar contra o tempo.

Os segundos do humano são **mais generosos que nos outros dois jogos** — 30/25/20
aqui contra 15/10/7 na velha e 20/15/10 no Pontinhos. O motivo está no tabuleiro:
o 3×3 tem no máximo 9 casas e a decisão é quase imediata; em damas 8×8 há até
20 lances legais e é preciso varrer quatro diagonais para não deixar peça
pendurada. O comentário de `politica_dificuldade_velha.dart` já registra o
princípio — lá ele autoriza apertar; aqui ele obriga a afrouxar."""
