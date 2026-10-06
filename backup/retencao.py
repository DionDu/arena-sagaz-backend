"""Quanto tempo cada backup fica no Drive - a regra das três camadas.

═══════════════════════════════════════════════════════════════════════════
A DECISÃO DO DONO (06/10/2026, DECISOES §8zv): 7 diários, 4 semanais, 3 mensais
═══════════════════════════════════════════════════════════════════════════

O backup não existe para voltar o banco inteiro: existe para guardar **cópias do
passado que se abrem e se comparam** com o banco atual, e consertar pontualmente
o que uma falha estragou. Uma falha leve pode levar semanas para ser notada, então
as cópias vão espaçando conforme envelhecem.

Cada backup recebe uma **etiqueta no dia em que nasce**, e a etiqueta decide o
prazo:

    | etiqueta | qual backup (data UTC)   | fica por |
    |----------|--------------------------|----------|
    | mensal   | o do dia 1º do mês       | 92 dias  |
    | semanal  | o de domingo             | 35 dias  |
    | diario   | todos os outros          |  7 dias  |

⚠️ **A etiqueta vai escrita no NOME do arquivo**, e a faxina a lê de lá, em vez de
recalculá-la pela data. Parece redundante (a data está no nome também), mas é o
que torna a regra estável: se um dia o prazo ou a regra da etiqueta mudarem, os
arquivos que já estão no Drive continuam sendo julgados pelo que eram quando
nasceram.

⚠️ **Por que não "6 arquivos: D-1, D-2, D-3, D-7, D-15, D-30".** Foi a proposta
inicial do dono, e ela não fecha: para existir um backup de exatamente 7 dias
amanhã, o backup que hoje tem 6 dias não pode ter sido apagado - e assim por
diante, até todos sobreviverem 30 dias. As camadas resolvem com ~15 arquivos.

⛔ **Nome que este módulo não reconhece NUNCA é apagado.** A pasta só deveria ter
backups, mas um arquivo posto à mão, ou de um formato antigo, fica - apagar o que
não se entende é como um conserto vira perda de dado.
"""

from __future__ import annotations

# `from __future__ import annotations` faz o Python tratar as anotações de tipo
# como texto, sem avaliá-las. Permite escrever `tuple[date, str] | None` mesmo em
# versões mais antigas do Python - e a imagem usa o Python que o Debian trouxer.

import re
from datetime import date

# ─── As três etiquetas e os prazos ─────────────────────────────────────────

MENSAL = "mensal"
SEMANAL = "semanal"
DIARIO = "diario"

#: Quantos dias cada etiqueta fica no Drive. Um arquivo com **idade** (dias desde
#: que nasceu) **maior** que o prazo é apagado; idade igual ao prazo ainda fica.
#: Assim o diário de 7 dias atrás ainda está lá - é o D-7 que o dono pediu.
PRAZO_EM_DIAS: dict[str, int] = {
    MENSAL: 92,
    SEMANAL: 35,
    DIARIO: 7,
}

# ─── O nome do arquivo ─────────────────────────────────────────────────────

#: O começo de todo nome. Diz de que banco é a cópia: se um dia houver backup do
#: `des` na mesma conta, os dois não se confundem.
PREFIXO = "arena-sagaz-prd"

#: `.dump` é o formato `custom` do `pg_dump` (o que o `pg_restore` lê), e `.gpg`
#: diz que ele está criptografado - quem abrir a pasta sabe o que fazer com ele.
EXTENSAO = ".dump.gpg"

# Expressão regular que reconhece um nome nosso. Lendo por partes:
#   ^arena-sagaz-prd_            o prefixo, no começo exato do nome (`^`)
#   (\d{4}-\d{2}-\d{2})          grupo 1: a data, AAAA-MM-DD (`\d` = um dígito)
#   _(mensal|semanal|diario)     grupo 2: a etiqueta, uma das três e só elas
#   \.dump\.gpg$                 a extensão, no fim exato (`$`); o `\.` é o ponto
#                                literal, porque `.` sozinho casaria qualquer letra
_PADRAO_DO_NOME = re.compile(
    r"^" + re.escape(PREFIXO) + r"_(\d{4}-\d{2}-\d{2})_(mensal|semanal|diario)"
    + re.escape(EXTENSAO) + r"$"
)


def etiqueta_do_dia(dia: date) -> str:
    """A etiqueta de um backup nascido em `dia` (data UTC).

    O dia 1º vence o domingo: quando o 1º cai num domingo, o backup é **mensal**,
    porque o prazo mais longo é o que protege mais. `weekday()` conta a semana a
    partir da segunda-feira (0) - o domingo é o 6.
    """
    if dia.day == 1:
        return MENSAL
    if dia.weekday() == 6:
        return SEMANAL
    return DIARIO


def nome_do_arquivo(dia: date) -> str:
    """O nome do backup nascido em `dia`, com a etiqueta embutida.

    Exemplo: `arena-sagaz-prd_2026-10-11_semanal.dump.gpg`. A data no formato
    ISO (AAAA-MM-DD) faz a ordem alfabética da pasta ser a ordem do calendário.
    """
    return f"{PREFIXO}_{dia.isoformat()}_{etiqueta_do_dia(dia)}{EXTENSAO}"


def ler_nome(nome: str) -> tuple[date, str] | None:
    """Devolve `(dia, etiqueta)` de um nome nosso, ou `None` se não for nosso.

    `None` também sai para um nome com o formato certo e uma data impossível
    (`2026-02-30`): `date.fromisoformat` recusa, e um nome que não se entende
    não se apaga.
    """
    casou = _PADRAO_DO_NOME.match(nome)
    if casou is None:
        return None
    try:
        dia = date.fromisoformat(casou.group(1))
    except ValueError:
        return None
    return dia, casou.group(2)


def deve_apagar(nome: str, hoje: date) -> bool:
    """`True` quando o backup `nome` passou do prazo da sua etiqueta.

    - nome que não é nosso → `False` (nunca se apaga o que não se entende);
    - data no futuro (idade negativa) → `False`: só acontece com relógio errado,
      e nesse caso o mais seguro é guardar.
    """
    lido = ler_nome(nome)
    if lido is None:
        return False
    dia, etiqueta = lido
    # Subtrair duas datas dá um `timedelta`; `.days` é o número de dias inteiros.
    idade = (hoje - dia).days
    return idade > PRAZO_EM_DIAS[etiqueta]


def nomes_a_apagar(nomes: list[str], hoje: date) -> list[str]:
    """Filtra, de uma lista de nomes da pasta, os que a faxina de hoje apaga."""
    return [nome for nome in nomes if deve_apagar(nome, hoje)]
