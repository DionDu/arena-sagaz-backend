"""O retrato da resolucao - o que a pessoa FEZ no instante do objetivo (T085za).

═══════════════════════════════════════════════════════════════════════════
O QUE ELE E
═══════════════════════════════════════════════════════════════════════════

O JSON que vai para `desafio_dia.tb003_resolucao.js_feito` (a `0027`):

    {"medidas": {"caixas_fechadas": 4, "caixas_do_adversario": 1, ...},
     "janela_gasta": 2}

E dele que o aplicativo escreve o cartao de quem resolveu (*"4 caixas em 2
turnos"*), em qualquer aparelho em que a pessoa entrar - o dono, em 24/09/2026:
*"Quando o usuario se loga em outro aparelho precisa visualizar no outro
aparelho o mesmo que via no primeiro"*.

⚠️ **Retrato, ⛔ conta.** O XP continua linha a linha em `tb004_xp_desafio`, que
guarda so as medidas que PESAM no desafio. O retrato guarda **todas** as de
tabuleiro - quem escolhe o que a frase le e o manifesto
`contratos/medidas_do_feito.json`, e ⛔ este modulo.

⚠️ **Montado aqui, a partir do proprio envio**, e ⛔ mandado pronto pelo
aplicativo: o `feitos` do envio JA traz todas as medidas do tabuleiro (o
extrato da resolucao, no app, junta tudo o que o medidor contou). Um segundo
campo com as mesmas medidas seria a segunda copia da verdade - e as duas
poderiam discordar.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from api.desafios.extrato_xp import FEITO_DICAS, FEITO_TEMPO, FEITO_TENTATIVAS
from api.desafios.modelos_envio import FeitoMedido

#: O que ⛔ entra no retrato, e por que:
#:
#:   · as tres de SESSAO (tentativas, tempo, dicas) - ⛔ sao do tabuleiro, e ja
#:     tem casa propria (`tb002_tentativa`, as dicas, e as parcelas da `tb004`);
#:   · `desafio_concluido` - ⛔ e medida, e o veredito, e ele ja e a propria
#:     linha de `tb003_resolucao`.
FORA_DO_RETRATO = frozenset(
    {FEITO_TENTATIVAS, FEITO_TEMPO, FEITO_DICAS, "desafio_concluido"}
)


def _numero(valor: float) -> int | float:
    """`4.0` vira `4`: as medidas de tabuleiro sao contagens, e o JSON do
    retrato e lido por gente (o painel) e pela frase, que espera inteiro.
    Valor fracionario - uma medida futura que o seja - passa como veio.
    """
    return int(valor) if float(valor).is_integer() else valor


def retrato_da_resolucao(
    feitos: Iterable[FeitoMedido], janela_gasta: Optional[int]
) -> dict[str, Any]:
    """O `js_feito` de uma resolucao.

    Args:
        feitos: o `feitos` do envio - as medidas do instante do objetivo.
        janela_gasta: quanto da janela foi gasto ate o objetivo (os *"2
            turnos"*), ou `None` quando a janela e a partida inteira.

    Returns:
        `{"medidas": {...}, "janela_gasta": n | None}` - as medidas em ordem
        alfabetica, para duas resolucoes iguais darem o mesmo texto.
    """
    medidas = {
        f.chave: _numero(f.valor)
        for f in sorted(feitos, key=lambda f: f.chave)
        if f.chave not in FORA_DO_RETRATO
    }
    return {"medidas": medidas, "janela_gasta": janela_gasta}
