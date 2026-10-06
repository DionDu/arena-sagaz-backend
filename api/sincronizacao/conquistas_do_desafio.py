"""O BÔNUS DE XP das conquistas do Desafio do Dia — creditado pelo SERVIDOR.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA TABELA EXISTE (05/10/2026)
═══════════════════════════════════════════════════════════════════════════

Toda conquista do app paga um bônus de XP, uma vez, ao ser desbloqueada. Nas
conquistas **dos jogos** esse bônus sobe ao servidor como uma parcela da
partida (``co_tipo_xp = 'conquista'`` em ``partida.tb003_xp_partida``) — é por
isso que ``gravar_conquista`` diz que "o XP da conquista não entra aqui".

As conquistas **do Desafio do Dia** não têm partida que as carregue: elas nascem
da resolução do desafio, e a partida de desafio sobe com ``ic_pontua = FALSE``
(o anti-farm do XP de partida — ``docs/DECISOES-do-dono.md`` §8k-9). O dono
decidiu em 05/10/2026 que elas pagam bônus **creditado pelo servidor**, ao
receber o evento da conquista.

⚠️ **O valor mora AQUI, e não no evento.** O app manda só o código da conquista;
quanto ela vale é o servidor quem diz. Aceitar o número vindo do aparelho seria
abrir uma porta de XP para quem forjar o evento.

⚠️ **E o crédito acontece uma vez só**, quando a linha da conquista é INSERIDA
(``xmax = 0``). Reenviar o evento — o mesmo aparelho, ou a mesma conquista
desbloqueada em dois aparelhos — encontra a linha e não credita de novo.

═══════════════════════════════════════════════════════════════════════════
⚠️ A MESMA TABELA EXISTE NO APP
═══════════════════════════════════════════════════════════════════════════

O app mostra o "+N XP" na celebração e soma o bônus no total local na hora; o
servidor soma o mesmo número quando o evento chega, e a reconciliação por
``GREATEST`` encontra os dois iguais. Se os valores divergirem, o número do
aparelho e o do ranking param de bater em silêncio. Quem vigia é
``tests/unitarios/test_conquistas_do_desafio.py``, que lê o catálogo do app
(``arena-sagaz-frontend/lib/core/progressao/conquistas.dart``) e compara código
a código.

⚠️ **Os códigos são chave de persistência**: nunca renomear depois de publicado
(o app guarda o código, e o servidor também, em
``progressao.tb002_conquista_usuario.co_conquista VARCHAR(40)``).
"""

from __future__ import annotations

#: Código da conquista → XP de bônus. Só as conquistas do Desafio do Dia estão
#: aqui: as dos jogos têm o bônus na partida, e creditá-las de novo neste caminho
#: pagaria duas vezes.
BONUS_DAS_CONQUISTAS_DO_DESAFIO: dict[str, int] = {
    "desafio_primeiro": 40,
    "desafio_resolvidos_10": 100,
    "desafio_resolvidos_50": 200,
    "desafio_resolvidos_100": 350,
    "desafio_semana_completa": 120,
    "desafio_mes_completo": 400,
}


def bonus_da_conquista_do_desafio(co_conquista: object) -> int:
    """Quanto o servidor credita ao INSERIR a conquista [co_conquista].

    Devolve ``0`` para qualquer código que não seja de desafio — inclusive os
    dos jogos, cujo bônus já veio na partida. ``object`` e não ``str`` porque o
    código sai de um payload JSON, e um valor que não seja texto também tem de
    dar zero, e não estourar.
    """
    if not isinstance(co_conquista, str):
        return 0
    return BONUS_DAS_CONQUISTAS_DO_DESAFIO.get(co_conquista, 0)
