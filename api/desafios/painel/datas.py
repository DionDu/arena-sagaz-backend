"""AS DATAS DO PAINEL, NO FORMATO BRASILEIRO (pedido do dono, 02/10/2026).

> *"As datas e interessante no formato brasileiro."*

⚠️ **Um lugar so para formatar**, e todo o painel passa por aqui. Data escrita
com `isoformat()` no meio do HTML e o defeito que a pagina antiga tinha em sete
lugares, e cada um teria de ser lembrado a parte.

⚠️ **O banco e a URL continuam em ISO** (`2026-10-04`): e o formato que o
`<input type=date>` e o Postgres entendem, e trocar ali so criaria conversao.
O formato brasileiro e so de LEITURA.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE O FUSO E UM DESLOCAMENTO FIXO, E NAO `zoneinfo`
═══════════════════════════════════════════════════════════════════════════

`zoneinfo.ZoneInfo("America/Sao_Paulo")` precisa da base de fusos do sistema, e
no Windows ela nao vem instalada (exige o pacote `tzdata`, que nao esta em
`requirements_api.txt`). O painel roda na maquina do dono, que e Windows.

O Brasil nao tem horario de verao desde 2019, entao Brasilia e UTC-3 o ano
inteiro, e um `timezone(timedelta(hours=-3))` diz a mesma coisa sem dependencia.
⚠️ Se o horario de verao voltar, e AQUI que se troca.

⚠️ **O dia do desafio continua sendo o dia UTC** (`dt_dia`, RF-DES do dia
global): o fuso de Brasilia so serve para mostrar HORARIOS de geracao e de
resolucao, nunca para decidir de que dia um desafio e.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

#: Brasilia, sem horario de verao (ver o topo do modulo).
BRASILIA = timezone(timedelta(hours=-3), name="Brasilia")

#: Os meses por extenso, para o titulo de cada calendario.
MESES = (
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

#: Os dias da semana, na ordem de `date.weekday()` (segunda = 0).
DIAS_DA_SEMANA = (
    "segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sabado", "domingo",
)

#: As iniciais do cabecalho do calendario, comecando no DOMINGO — que e como o
#: calendario se le no Brasil.
INICIAIS_DA_SEMANA = ("D", "S", "T", "Q", "Q", "S", "S")


def data_br(dia: Optional[date]) -> str:
    """`2026-10-04` → `04/10/2026`. Vazio para `None`."""
    if dia is None:
        return ""
    return dia.strftime("%d/%m/%Y")


def data_curta_br(dia: date) -> str:
    """`2026-10-04` → `04/10` — para listas em que o ano e obvio."""
    return dia.strftime("%d/%m")


def dia_por_extenso(dia: date) -> str:
    """`2026-10-04` → `sabado, 04/10/2026`."""
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {data_br(dia)}"


def momento_br(momento: Optional[datetime]) -> str:
    """Um instante do banco → `29/09/2026 17:47` em Brasilia.

    ⚠️ Instante sem fuso e tratado como UTC: e assim que o Postgres os entrega
    para colunas `TIMESTAMPTZ` pelo driver, e um `naive` aqui so pode ter vindo
    de um teste.
    """
    if momento is None:
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(BRASILIA).strftime("%d/%m/%Y %H:%M")


def duracao_br(milissegundos: Optional[float]) -> str:
    """`95000` → `1min35s`; `8000` → `8s`. Vazio para `None`."""
    if milissegundos is None:
        return ""
    segundos = int(round(milissegundos / 1000))
    minutos, resto = divmod(segundos, 60)
    if minutos == 0:
        return f"{resto}s"
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas}h{minutos:02d}min"
    return f"{minutos}min{resto:02d}s"


def ler_data(texto: Optional[str]) -> Optional[date]:
    """Le uma data vinda da URL: aceita `2026-10-04` e `04/10/2026`.

    Returns:
        A data, ou `None` quando o texto nao e data nenhuma — quem chama cai no
        dia padrao, em vez de responder erro por um link torto.
    """
    if not texto:
        return None
    texto = texto.strip()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        pass
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None
