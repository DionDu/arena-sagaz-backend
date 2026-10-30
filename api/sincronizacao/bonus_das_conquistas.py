"""O BÔNUS DE XP de cada conquista - creditado pelo SERVIDOR ao recebê-la.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA TABELA EXISTE
═══════════════════════════════════════════════════════════════════════════

Toda conquista do app paga um bônus de XP, uma vez, ao ser desbloqueada: o app
o soma no total local na hora da celebração, fora do teto diário.

Até 30/10/2026 o servidor só creditava o bônus das conquistas **do Desafio do
Dia** (decisão do dono de 05/10/2026: não há partida que as carregue). O das
conquistas **dos jogos** só chegava ao servidor pela reconciliação
(``GREATEST`` do total do aparelho) - ⚠️ e não "como parcela da partida", como
este cabeçalho dizia: o evento de partida nunca levou parcela de conquista
(``partida.tb003_xp_partida`` com ``nu_tipo_xp = 5`` nunca teve uma linha no
``prd``). Quando a reconciliação era recusada (422 ``progressao_inconsistente``,
em 9 contas do ``prd``), o bônus nunca chegava ao ranking - o 2º defeito de
progressão da 1.4.0 (``arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/
RETOMADA-progressao-1.4.0.md`` §2).

Desde a T167 da spec 010 a tabela tem **todas** as conquistas, e o servidor
credita o bônus de qualquer uma ao INSERI-LA (o evento ``conquista`` e o merge
do convidado - ``repositorio.py``, ``_creditar_bonus_da_conquista``).

⚠️ **O valor mora AQUI, e não no evento.** O app manda só o código da conquista;
quanto ela vale é o servidor quem diz. Aceitar o número vindo do aparelho seria
abrir uma porta de XP para quem forjar o evento. (Forjando todos os códigos, o
máximo é a soma desta tabela, uma vez por conta - menos do que a reconciliação
aceita já permitia.)

⚠️ **E o crédito acontece uma vez só**, quando a linha da conquista é INSERIDA
(``xmax = 0`` no evento; ``RETURNING`` no merge). Reenviar o evento - o mesmo
aparelho, ou a mesma conquista desbloqueada em dois aparelhos - encontra a
linha e não credita de novo.

⛔ **A reconciliação NUNCA credita.** Ela aplica ``GREATEST`` com o total do
aparelho, que já inclui o bônus; somar depois disso pagaria duas vezes.

═══════════════════════════════════════════════════════════════════════════
⚠️ A MESMA TABELA EXISTE NO APP - E O APP ANTIGO TAMBÉM PAGA ESTES NÚMEROS
═══════════════════════════════════════════════════════════════════════════

Se os valores divergirem, o número do aparelho e o do ranking param de bater em
silêncio. O cadeado é um arquivo comum,
``arena-sagaz-frontend/test/core/progressao/bonus_das_conquistas.json``: o app o
compara com o catálogo dele (``bonus_das_conquistas_test.dart``), e
``tests/unitarios/test_bonus_das_conquistas.py`` o compara com esta tabela.

⚠️ **Os apps em campo (1.3.1 e anteriores) também falam com este servidor**, e
cada um soma o bônus que o catálogo DELE diz. Nenhum valor mudou no histórico do
catálogo (conferido em 30/10/2026: desde a 1.3.1 só entraram as conquistas do
Quatro). ⛔ **Por isso o valor de uma conquista publicada não muda mais**: mudar
aqui faria o servidor creditar um número e o app antigo mostrar outro. Conquista
nova entra com valor novo; conquista velha fica como está.

⚠️ **Os códigos são chave de persistência**: nunca renomear depois de publicado
(o app guarda o código, e o servidor também, em
``progressao.tb002_conquista_usuario.co_conquista VARCHAR(40)``).
"""

from __future__ import annotations

#: Código da conquista → XP de bônus, na ordem do catálogo do app.
BONUS_DAS_CONQUISTAS: dict[str, int] = {
    # ── De conta: nível, vitórias no hub, chama e dias jogados.
    "nivel_5": 80,
    "nivel_10": 120,
    "nivel_20": 200,
    "nivel_35": 320,
    "nivel_55": 480,
    "nivel_80": 680,
    "primeira_vitoria": 40,
    "vitorias_10": 100,
    "vitorias_50": 200,
    "vitorias_100": 350,
    "vitorias_500": 800,
    "sequencia_3": 60,
    "sequencia_7": 120,
    "sequencia_14": 220,
    "sequencia_30": 400,
    "dias_10": 100,
    "dias_30": 250,
    "dias_100": 600,
    # ── Jogo dos Pontinhos.
    "pontinhos_vitorias_1": 40,
    "pontinhos_vitorias_10": 100,
    "pontinhos_vitorias_50": 200,
    "pontinhos_vitorias_100": 350,
    "pontinhos_derrotar_cacau": 80,
    "pontinhos_derrotar_pita": 140,
    "pontinhos_derrotar_tex": 180,
    "pontinhos_derrotar_magno": 220,
    "pontinhos_derrotar_cacau_com_poder": 30,
    "pontinhos_derrotar_pita_com_poder": 50,
    "pontinhos_derrotar_tex_com_poder": 70,
    "pontinhos_derrotar_magno_com_poder": 90,
    "pontinhos_lenda": 300,
    "pontinhos_lenda_com_poder": 120,
    # ── Jogo da Velha.
    "velha_vitorias_1": 30,
    "velha_vitorias_10": 70,
    "velha_vitorias_50": 140,
    "velha_vitorias_100": 240,
    "velha_derrotar_cacau": 40,
    "velha_derrotar_pita": 90,
    "velha_derrotar_tex": 200,
    "velha_derrotar_magno": 500,
    "velha_lenda": 400,
    "velha_segurou_magno": 250,
    "velha_partida_perfeita": 300,
    # ── Jogo das Damas.
    "damas_vitorias_1": 80,
    "damas_vitorias_10": 200,
    "damas_vitorias_50": 400,
    "damas_vitorias_100": 700,
    "damas_derrotar_cacau": 80,
    "damas_derrotar_pita": 140,
    "damas_derrotar_tex": 200,
    "damas_derrotar_magno": 300,
    "damas_derrotar_cacau_com_poder": 30,
    "damas_derrotar_pita_com_poder": 50,
    "damas_derrotar_tex_com_poder": 80,
    "damas_derrotar_magno_com_poder": 120,
    "damas_lenda": 350,
    "damas_lenda_com_poder": 140,
    "damas_segurou_magno": 250,
    "damas_segurou_magno_com_poder": 100,
    "damas_partida_perfeita": 250,
    "damas_primeira_dama": 40,
    "damas_captura_tripla": 120,
    "damas_captura_cinco": 220,
    # ── Desafio do Dia (desde 05/10/2026; eram as únicas creditadas aqui até a T167).
    "desafio_primeiro": 40,
    "desafio_resolvidos_10": 100,
    "desafio_resolvidos_50": 200,
    "desafio_resolvidos_100": 350,
    "desafio_semana_completa": 120,
    "desafio_mes_completo": 400,
    # ── Quatro em Linha (chega com a 1.4.0).
    "quatro_vitorias_1": 80,
    "quatro_vitorias_10": 200,
    "quatro_vitorias_50": 400,
    "quatro_vitorias_100": 700,
    "quatro_derrotar_cacau": 80,
    "quatro_derrotar_pita": 140,
    "quatro_derrotar_tex": 200,
    "quatro_derrotar_magno": 300,
    "quatro_derrotar_cacau_com_poder": 30,
    "quatro_derrotar_pita_com_poder": 50,
    "quatro_derrotar_tex_com_poder": 80,
    "quatro_derrotar_magno_com_poder": 120,
    "quatro_lenda": 350,
    "quatro_lenda_com_poder": 140,
    "quatro_segurou_magno": 250,
    "quatro_segurou_magno_com_poder": 100,
    "quatro_torre": 40,
    "quatro_diagonal": 40,
    "quatro_relampago": 120,
    "quatro_dupla": 120,
    "quatro_cinco": 220,
    "quatro_folego_longo": 120,
}


def bonus_da_conquista(co_conquista: object) -> int:
    """Quanto o servidor credita ao INSERIR a conquista [co_conquista].

    Devolve ``0`` para um código que esta tabela não conhece - uma conquista de
    um app mais novo que o servidor, por exemplo: ela fica gravada, e o bônus
    dela chega pela reconciliação, como chegava antes. ``object`` e não ``str``
    porque o código sai de um payload JSON, e um valor que não seja texto também
    tem de dar zero, e não estourar.
    """
    if not isinstance(co_conquista, str):
        return 0
    return BONUS_DAS_CONQUISTAS.get(co_conquista, 0)
