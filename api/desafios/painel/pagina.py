"""O HTML DO PAINEL DE GESTAO DO DESAFIO DO DIA (T039/T040, refeito em 02/10/2026).

═══════════════════════════════════════════════════════════════════════════
DE CURADORIA A GESTAO — O QUE MUDOU EM 02/10/2026
═══════════════════════════════════════════════════════════════════════════

O dono pediu, ao mesmo tempo em que os desafios passaram a nascer pre-aprovados:

> *"Preciso tambem que melhore o painel de curadoria. Ele nao utiliza bem o
> espaco da tela, ha muito espaco vazio dos lados. (...) Eu queria clicar no dia
> do calendario e ver o desafio daquele dia. Ficar vendo tantos desafios na
> tela, tendo que rolar a tela e desagradavel. (...) Na verdade teriamos um
> painel de gestao dos desafios, nao so curadoria."*

Entao a pagina deixou de ser **uma fila rolavel** e virou **um calendario com um
dia aberto**:

    ┌──────────────── cabecalho ────────────────┐
    │ lateral (380px)     │ o dia escolhido      │
    │  gerar 7/14/21/28   │  tabuleiro + frase   │
    │  a fila             │  regua + acoes       │
    │  calendario (3 mes) │  como foi o dia      │
    │  pendencias         │  quadro + raio-x     │
    │  divergencias       │  a solucao, lance a  │
    │                     │  lance               │
    └─────────────────────┴──────────────────────┘

⚠️ **O painel nao passou pelo Claude Design, e isso e decisao do dono**
(02/10/2026): e ferramenta interna de uma pessoa so. Ele usa a paleta do app
(`desenho.py` espelha `app_colors.dart`) para nao parecer outro produto.

═══════════════════════════════════════════════════════════════════════════
POR QUE E STRING, E NAO UM MOTOR DE TEMPLATES
═══════════════════════════════════════════════════════════════════════════

Jinja2 nao esta em `requirements_api.txt`, e acrescenta-lo por causa de **uma**
pagina interna significaria uma dependencia nova na imagem que serve o
aplicativo em producao.

⚠️ **Escapar deixa de ser automatico, e por isso ha uma regra unica aqui:**
todo valor vindo do banco passa por `_txt()`. Nao ha excecao — nem para o que
"claramente" e um UUID, porque a proxima coluna a entrar nao sera.

═══════════════════════════════════════════════════════════════════════════
⚠️ JAVASCRIPT LEVE — E O QUE ELE NAO FAZ
═══════════════════════════════════════════════════════════════════════════

Ate 02/10/2026 o painel nao tinha JavaScript nenhum, por decisao. O dono o
liberou ("JS leve permitido") para tres coisas, e so elas:

  1. trocar o dia aberto sem recarregar a pagina (busca o HTML do dia pronto no
     servidor — `render_detalhe` — e o troca no lugar);
  2. carregar o raio-x de uma pessoa quando o dono o abre;
  3. acompanhar a geracao e **recarregar a pagina inteira** quando ela acaba.

⛔ **Nenhuma acao e feita por script.** Aprovar, descartar, agendar e gerar
continuam sendo `<form method="post">` com a pagina recarregando: o estado em
que a tela ja mudou e a gravacao falhou continua sem existir. ⚠️ E todo link
funciona sem o script — ele so poupa o recarregamento.
"""

from __future__ import annotations

import calendar as calendario_mod
from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from typing import Any, Iterable, Optional, Sequence

from api.desafios.janela_baixada import na_janela_baixada
from api.desafios.painel import desenho, execucao_do_job, frase_objetivo
from api.desafios.painel.datas import (
    INICIAIS_DA_SEMANA,
    MESES,
    data_br,
    data_curta_br,
    dia_por_extenso,
    duracao_br,
    momento_br,
)
from api.desafios.painel.estatisticas import (
    LinhaDoQuadro,
    QuemNaoResolveu,
    RaioX,
    ResumoDoDia,
)
from api.desafios.painel.repositorio import (
    DesafioNoPainel,
    DesafioSemDia,
    DiaNoCalendario,
)
from api.desafios.painel.vigilancia import (
    ContagemDeAuditoria,
    Divergencia,
    EstadoDaFila,
)

#: O caminho base do painel. Escrito uma vez para que os `action=` e os `href`
#: nao se espalhem como literais.
BASE = "/painel/desafios"

#: Como cada jogo aparece por extenso e na celula do calendario (que e estreita).
ROTULO_DO_JOGO = {"pontinhos": "Pontinhos", "damas": "Damas"}
SIGLA_DO_JOGO = {"pontinhos": "Pont", "damas": "Dama"}

#: O estado de curadoria como o dono le. ⚠️ `candidato` virou "aguardando":
#: desde 02/10/2026 so os candidatos ANTIGOS existem, e o nome tecnico fazia
#: parecer que todo desafio passava por ali.
ROTULO_DA_CURADORIA = {
    "aprovado": "aprovado",
    "candidato": "aguardando",
    "descartado": "descartado",
}

#: Quantos dias a frente o calendario pinta de vermelho quando estao vazios,
#: no minimo. ⚠️ E a folga confortavel da vigilancia (7 dias), e pelo mesmo
#: motivo: um buraco dentro dela e o que vira dia sem desafio no aplicativo.
DIAS_DE_HORIZONTE_MINIMO = 7


def _txt(valor: Any) -> str:
    """Qualquer valor → texto seguro para ir dentro do HTML.

    ⚠️ **Todo** dado do banco passa por aqui. `escape` troca `<`, `>`, `&` e (com
    `quote=True`, o padrao) as aspas pelas entidades correspondentes — sem isso,
    um motivo de descarte com `<script>` viraria script de verdade na proxima
    visita do dono.
    """
    if valor is None:
        return ""
    return escape(str(valor), quote=True)


def _rotulo_personagem(co_personagem: Optional[str]) -> str:
    """O nome do mascote com a inicial maiuscula, para leitura humana."""
    return co_personagem.capitalize() if co_personagem else "?"


def _primeira_maiuscula(texto: str) -> str:
    """`quinta-feira, 01/10/2026` → `Quinta-feira, 01/10/2026`.

    ⚠️ `str.capitalize()` nao serve: ele poe o RESTO em minuscula. E o CSS
    `text-transform: capitalize` poe maiuscula em toda palavra ("Quinta-Feira").
    """
    return texto[:1].upper() + texto[1:]


def _pct(fracao: Optional[float]) -> str:
    """`0.734` → `73%`; `None` → travessao."""
    return "&ndash;" if fracao is None else f"{fracao * 100:.0f}%"


def _nome_da_pessoa(no_exibicao: Optional[str], co_usuario: Optional[str]) -> str:
    """O apelido, e o codigo entre parenteses para o dono achar a conta no banco."""
    nome = _txt(no_exibicao) or "(sem nome)"
    codigo = f' <span class="codigo">@{_txt(co_usuario)}</span>' if co_usuario else ""
    return nome + codigo


# ═══════════════════════════════════════════════════════════════════════════
# 1. O calendario — regras puras, testaveis sem HTML
# ═══════════════════════════════════════════════════════════════════════════


def horizonte_da_fila(
    dt_hoje: date, calendario: Iterable[DiaNoCalendario]
) -> date:
    """Ate que dia um dia vazio conta como BURACO (vermelho).

    ⚠️ **O maior entre "uma semana a frente" e "o ultimo dia agendado"**: um dia
    vazio no meio da fila e buraco mesmo que esteja a vinte dias; um dia vazio
    depois do fim da fila e so o futuro ainda nao gerado, e pinta-lo de vermelho
    deixaria o mes seguinte inteiro gritando sem motivo.
    """
    ultimo = max((d.dt_dia for d in calendario), default=dt_hoje)
    return max(dt_hoje + timedelta(days=DIAS_DE_HORIZONTE_MINIMO - 1), ultimo)


def status_do_dia(
    dia: date,
    ocupante: Optional[DiaNoCalendario],
    *,
    dt_hoje: date,
    horizonte: date,
) -> str:
    """A cor de um dia do calendario.

    Returns:
        `aprovado` (verde) · `candidato` (ouro) · `descartado` (vermelho) ·
        `buraco` (vermelho: vazio, hoje ou adiante, dentro da fila) · `passado`
        (vazio e ja foi) · `livre` (vazio, depois do fim da fila).

    ⚠️ **"Descartado ou vazio = vermelho"** e o pedido do dono, e os dois sao o
    mesmo problema: um dia em que o aplicativo nao tem o que servir.
    """
    if ocupante is not None:
        return ocupante.co_curadoria
    if dia < dt_hoje:
        return "passado"
    if dia <= horizonte:
        return "buraco"
    return "livre"


def meses_a_mostrar(
    dt_hoje: date, calendario: Iterable[DiaNoCalendario]
) -> list[tuple[int, int]]:
    """O mes corrente, mais o anterior e o seguinte QUANDO tem desafio.

    ⚠️ E o pedido do dono ao pe da letra: *"Deveria mostrar o mes anterior e o
    proximo tambem, caso tenham algum desafio ja gerado."* Mes sem desafio nao
    entra — ele so empurraria o que importa para baixo.
    """
    def deslocar(ano: int, mes: int, passo: int) -> tuple[int, int]:
        # `mes - 1 + passo` vai de 0 a 11 dentro do ano; `divmod` devolve
        # quantos anos andou e o mes resultante.
        anos, resto = divmod(mes - 1 + passo, 12)
        return ano + anos, resto + 1

    atual = (dt_hoje.year, dt_hoje.month)
    com_desafio = {(d.dt_dia.year, d.dt_dia.month) for d in calendario}
    anterior = deslocar(*atual, -1)
    seguinte = deslocar(*atual, 1)
    return (
        ([anterior] if anterior in com_desafio else [])
        + [atual]
        + ([seguinte] if seguinte in com_desafio else [])
    )


def _href_do_dia(dia: date) -> str:
    """O endereco que abre um dia. A URL fica em ISO; a tela, em `dd/mm/aaaa`."""
    return f"{BASE}?dia={dia.isoformat()}"


def _mes(
    ano: int,
    mes: int,
    *,
    por_dia: dict[date, DiaNoCalendario],
    dt_hoje: date,
    horizonte: date,
    dt_selecionado: Optional[date],
) -> str:
    """Um mes do calendario, comecando no DOMINGO."""
    partes = [
        f'<div class="mes"><h3>{MESES[mes - 1].capitalize()} de {ano}</h3>'
        '<div class="grade-mes">'
    ]
    partes += [f'<span class="dsem">{i}</span>' for i in INICIAIS_DA_SEMANA]
    primeiro = date(ano, mes, 1)
    # `weekday()` da segunda = 0 ... domingo = 6; com o domingo na 1a coluna, o
    # deslocamento e `(weekday + 1) % 7`.
    partes += ['<span class="fora"></span>'] * ((primeiro.weekday() + 1) % 7)
    for numero in range(1, calendario_mod.monthrange(ano, mes)[1] + 1):
        dia = date(ano, mes, numero)
        ocupante = por_dia.get(dia)
        status = status_do_dia(dia, ocupante, dt_hoje=dt_hoje, horizonte=horizonte)
        classes = ["dia", status]
        if dia == dt_hoje:
            classes.append("hoje")
        if dia == dt_selecionado:
            classes.append("selecionado")
        if ocupante is not None:
            # A marca de alternancia: jogo e personagem, para o dono ver de
            # relance se dois dias seguidos ficaram parecidos.
            # Duas linhas, e nao uma: numa celula de ~48 px "Dama · Magno"
            # saia cortado em "Dama · M" (visto no painel em 02/10/2026).
            marca = (
                f"<small>{_txt(SIGLA_DO_JOGO.get(ocupante.co_jogo, ocupante.co_jogo))}</small>"
                f"<small>{_txt(_rotulo_personagem(ocupante.co_personagem))}</small>"
            )
            jogado = (
                f'<i title="resolveram / tentaram">{ocupante.qt_resolveram}/'
                f"{ocupante.qt_pessoas}</i>"
                if ocupante.qt_pessoas
                else ""
            )
            titulo = (
                f"{data_br(dia)} · {ROTULO_DA_CURADORIA.get(ocupante.co_curadoria, ocupante.co_curadoria)}"
                f" · {ROTULO_DO_JOGO.get(ocupante.co_jogo, ocupante.co_jogo)}"
                + (f" ({ocupante.co_modalidade})" if ocupante.co_modalidade else "")
                + f" · {ocupante.no_tipo_desafio} · contra "
                + _rotulo_personagem(ocupante.co_personagem)
            )
        else:
            marca, jogado = "", ""
            titulo = f"{data_br(dia)} · " + {
                "buraco": "sem desafio (buraco na fila)",
                "passado": "sem desafio",
                "livre": "ainda nao gerado",
            }[status]
        partes.append(
            f'<a class="{" ".join(classes)}" href="{_href_do_dia(dia)}" '
            f'data-navegar="1" data-dia="{dia.isoformat()}" title="{_txt(titulo)}">'
            f"<b>{numero}</b>{marca}{jogado}</a>"
        )
    partes.append("</div></div>")
    return "".join(partes)


def _calendario(
    calendario: Sequence[DiaNoCalendario],
    *,
    dt_hoje: date,
    dt_selecionado: Optional[date],
) -> str:
    """Os meses do calendario, com a legenda das cores."""
    por_dia = {d.dt_dia: d for d in calendario}
    horizonte = horizonte_da_fila(dt_hoje, calendario)
    meses = "".join(
        _mes(
            ano,
            mes,
            por_dia=por_dia,
            dt_hoje=dt_hoje,
            horizonte=horizonte,
            dt_selecionado=dt_selecionado,
        )
        for ano, mes in meses_a_mostrar(dt_hoje, calendario)
    )
    legenda = (
        '<p class="legenda">'
        '<span class="pino aprovado"></span>aprovado '
        '<span class="pino candidato"></span>aguardando '
        '<span class="pino buraco"></span>vazio ou descartado '
        '<span class="pino hoje"></span>hoje'
        "<br>Em cada dia: o jogo, o adversario e, se ja foi jogado, "
        "resolveram/tentaram.</p>"
    )
    return meses + legenda


# ═══════════════════════════════════════════════════════════════════════════
# 2. A lateral: gerar, a fila, pendencias, divergencias
# ═══════════════════════════════════════════════════════════════════════════


def _secao_gerar() -> str:
    """Os botoes que rodam o job, quando este processo pode (T040c).

    ⛔ **Devolve vazio quando `PAINEL_PODE_GERAR` esta desligada** — e e assim que
    ele nao existe no Railway. ⚠️ A rota recusa pelo mesmo motivo, independente
    daqui: esconder o botao sem fechar a rota e seguranca de fachada.
    """
    if not execucao_do_job.pode_gerar():
        return ""
    botoes = "".join(
        f'<button type="submit" name="dias" value="{dias}">{dias} dias</button>'
        for dias in execucao_do_job.DIAS_OFERECIDOS
    )
    estado = execucao_do_job.ESTADO
    return f"""
  <section class="bloco">
    <h2>Gerar desafios</h2>
    <form class="gerar" method="post" action="{BASE}/gerar">{botoes}</form>
    <p class="nota">Roda o job <strong>neste computador</strong>. Os dias vazios
    mais proximos sao tapados primeiro; dia que ja tem desafio e pulado. Tudo
    nasce <strong>aprovado</strong> &mdash; descarte o que nao servir.</p>
    <p class="nota" id="estado-geracao" data-rodando="{"1" if estado.rodando else "0"}">
    Ultima execucao: {_txt(estado.resumo)}</p>
  </section>"""


def _secao_fila(estado: EstadoDaFila) -> str:
    """O aviso de fila curta (RF-DES-012f), em forma compacta.

    ⚠️ **Ele aparece mesmo quando esta tudo bem** — em verde, dizendo quantos
    dias ha. Um aviso que so existe no dia ruim nao ensina o dono a le-lo.
    """
    classe = {"ok": "", "atencao": "atencao", "critico": "critico"}[estado.gravidade]
    if estado.gravidade == "ok":
        titulo = f"Fila coberta por {estado.dias_cobertos} dias seguidos."
    elif estado.gravidade == "atencao":
        titulo = (
            f"A fila cobre so {estado.dias_cobertos} dias seguidos — abaixo dos 7 "
            "que uma execucao do job repoe."
        )
    else:
        titulo = (
            f"Fila critica: {estado.dias_cobertos} dia(s) seguidos cobertos."
            if estado.dias_cobertos
            else "Fila vazia: nao ha desafio aprovado para hoje."
        )
    buracos = (
        "Vazios nos proximos 7 dias: "
        + ", ".join(data_curta_br(d) for d in estado.buracos)
        if estado.buracos
        else "Nenhum dia vazio nos proximos 7."
    )
    reserva = (
        f" {estado.reserva} aprovado(s) sem data em reserva."
        if estado.reserva
        else ""
    )
    return (
        f'<div class="aviso {classe}"><strong>{_txt(titulo)}</strong>'
        f"<small>{_txt(buracos)}{_txt(reserva)}</small></div>"
    )


def _secao_divergencias(
    contagem: ContagemDeAuditoria, divergencias: Iterable[Divergencia]
) -> str:
    """As divergencias de julgamento (RF-DES-034a), compactas.

    ⚠️ **Os tres contadores aparecem sempre**: sem o avaliador rodando,
    `divergente = 0` nao quer dizer "esta tudo certo" — quer dizer "ninguem
    conferiu".
    """
    partes = [
        '<div class="contadores">',
        f'<div class="contador"><b>{contagem.pendente}</b><span>pendentes</span></div>',
        f'<div class="contador"><b>{contagem.confere}</b><span>conferem</span></div>',
        f'<div class="contador"><b>{contagem.divergente}</b><span>divergentes</span></div>',
        "</div>",
    ]
    if contagem.avaliador_nunca_rodou:
        partes.append(
            '<div class="aviso critico"><strong>O avaliador de resolucoes nao '
            "rodou ainda.</strong><small>Ha resolucoes recebidas e nenhuma "
            "conferida: <code>divergente = 0</code> significa &quot;ninguem "
            "olhou&quot;.</small></div>"
        )
    linhas = list(divergencias)
    if not linhas:
        partes.append('<p class="vazio">Nenhuma divergencia registrada.</p>')
        return "".join(partes)
    partes.append(
        '<p class="nota">Divergencia nao corrige nada: vale o aplicativo '
        "(RF-DES-032). Estas linhas existem para investigar.</p>"
        '<table class="tabela"><tr><th>dia</th><th>jogo</th><th>XP</th>'
        "<th>o que o arbitro achou</th></tr>"
    )
    for linha in linhas:
        dia = (
            f'<a href="{_href_do_dia(linha.dt_dia)}" data-navegar="1">'
            f"{data_curta_br(linha.dt_dia)}</a>"
            if linha.dt_dia
            else ""
        )
        partes.append(
            f"<tr><td>{dia}</td><td>{_txt(linha.co_jogo)}</td>"
            f"<td>{_txt(linha.nu_xp)}</td>"
            f"<td>{_txt(linha.de_auditoria) or '&mdash;'}</td></tr>"
        )
    partes.append("</table>")
    return "".join(partes)


def _lista_sem_dia(itens: Sequence[DesafioSemDia], *, mostrar_motivo: bool) -> str:
    """Uma lista curta de desafios sem data; cada um abre no detalhe."""
    if not itens:
        return '<p class="vazio">Nenhum.</p>'
    partes = ['<ul class="lista">']
    for item in itens:
        motivo = (
            f'<span class="motivo">{_txt(item.de_motivo_descarte)}</span>'
            if mostrar_motivo and item.de_motivo_descarte
            else ""
        )
        partes.append(
            f'<li><a href="{BASE}?desafio={_txt(item.id_desafio)}" data-navegar="1">'
            f"{_txt(item.no_tipo_desafio)}</a> "
            f'<span class="meta">{_txt(ROTULO_DO_JOGO.get(item.co_jogo, item.co_jogo))}'
            f" &middot; {_txt(_rotulo_personagem(item.co_personagem))}"
            f" &middot; {_txt(momento_br(item.dh_geracao))}</span>{motivo}</li>"
        )
    partes.append("</ul>")
    return "".join(partes)


def _secao_pendencias(
    *,
    candidatos: Sequence[DesafioSemDia],
    candidatos_agendados: int,
    reserva: Sequence[DesafioSemDia],
    descartados: Sequence[DesafioSemDia],
) -> str:
    """O que nao mora no calendario: candidatos antigos, reserva e descartados."""
    total_candidatos = len(candidatos) + candidatos_agendados
    aprovar_todos = (
        f'<form method="post" action="{BASE}/aprovar-candidatos">'
        f'<button class="principal" type="submit">Aprovar os {total_candidatos} '
        "candidato(s) que aguardam</button></form>"
        '<p class="nota">Desde 02/10/2026 tudo nasce aprovado; estes sao de antes. '
        "Os que ja tem dia aparecem em ouro no calendario.</p>"
        if total_candidatos
        else ""
    )
    return f"""
  <section class="bloco">
    <h2>Pendencias</h2>
    {aprovar_todos}
    <details{" open" if candidatos else ""}><summary>Aguardando, sem data ({len(candidatos)})</summary>
      {_lista_sem_dia(candidatos, mostrar_motivo=False)}</details>
    <details{" open" if reserva else ""}><summary>Aprovados sem data &mdash; reserva ({len(reserva)})</summary>
      {_lista_sem_dia(reserva, mostrar_motivo=False)}</details>
    <details><summary>Descartados recentes ({len(descartados)})</summary>
      {_lista_sem_dia(descartados, mostrar_motivo=True)}</details>
  </section>"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. O detalhe de um dia
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DetalheDoDia:
    """Tudo o que a area principal mostra sobre um dia (ou um desafio sem dia).

    Atributos:
        dt_dia: o dia aberto. `None` quando o que se abriu foi um desafio sem
            data (reserva, candidato antigo, descartado).
        desafio: o desafio daquele dia; `None` = dia vazio.
        resumo, quadro, nao_resolveram: so existem para dia que ja foi jogado.
        reserva: os aprovados sem data — num dia vazio, o painel oferece
            agenda-los ali.
    """

    dt_dia: Optional[date]
    desafio: Optional[DesafioNoPainel]
    resumo: Optional[ResumoDoDia] = None
    quadro: tuple[LinhaDoQuadro, ...] = ()
    nao_resolveram: tuple[QuemNaoResolveu, ...] = ()
    reserva: tuple[DesafioSemDia, ...] = ()


def _frase_do_desafio(item: DesafioNoPainel) -> str:
    """A frase em portugues, como a pessoa a le no aplicativo (T040b).

    ⚠️ **Devolve vazio quando nao da para montar**, e o card segue com a chave
    crua logo abaixo — uma chave nova no aplicativo nao pode derrubar o painel.
    """
    frase = frase_objetivo.frase_do_desafio(item.co_chave_objetivo, item.js_objetivo)
    if not frase:
        return ""
    return f'<p class="frase">{_txt(frase)}</p>'


def _regua(item: DesafioNoPainel) -> str:
    """A medicao da regua por mascote (RF-DES-012b): uma linha por mascote.

    ⚠️ E a taxa por nivel que separa *"duro demais"* de *"banal"* — dois motivos
    de descarte diferentes, que um numero unico esconderia.
    """
    if not item.medicoes:
        return (
            '<p class="vazio">Sem medicao da regua: o job nao mediu este '
            "desafio.</p>"
        )
    partes = [
        '<table class="tabela regua"><tr><th>mascote</th><th>resolveu</th>'
        "<th>taxa</th><th></th></tr>"
    ]
    for m in item.medicoes:
        largura = int(round(m.taxa * 120))
        partes.append(
            "<tr>"
            f"<td>{_txt(_rotulo_personagem(m.co_personagem))}</td>"
            f"<td>{m.nu_resolveu}/{m.nu_execucoes}</td>"
            f"<td>{m.taxa * 100:.0f}%</td>"
            f'<td><span class="barra" style="width:{largura}px"></span></td>'
            "</tr>"
        )
    partes.append("</table>")
    return "".join(partes)


def _quadros_html(quadros: Sequence[dict[str, Any]]) -> str:
    """Uma tira de quadros (`desenho._quadros`), que quebra em varias linhas.

    ⚠️ `flex-wrap` e nao rolagem lateral: numa solucao de 19 lances uma tira
    rolavel esconderia o fim atras de um gesto que ninguem adivinha — e e o fim
    que decide o desafio.
    """
    partes = ['<div class="fita">']
    passou_da_chave = False
    for quadro in quadros:
        classes = ["quadro"]
        if quadro["chave"]:
            classes.append("chave")
        elif passou_da_chave and quadro["tipo"] == "lance":
            # ⚠️ Depois do objetivo a partida pode continuar (RF-DES-213): os
            # lances seguem desenhados, apagados, para nao competir com o que
            # decidiu o desafio. ⚠️ So os LANCES: a posicao final nao e "depois",
            # e o resultado de tudo, e apagada parecia descartada.
            classes.append("depois")
        if quadro["tipo"] == "inicio":
            legenda = "inicio"
        elif quadro["tipo"] == "final":
            legenda = "posicao final"
        else:
            legenda = f"{quadro['n']}. {quadro['titulo']} ({quadro['de_quem']})"
            if quadro.get("chave"):
                legenda += " ✓ objetivo"
            if quadro.get("errou_de_proposito"):
                # A CPU jogou fora do melhor lance de proposito: um desafio que so
                # se resolve por causa disto e fragil.
                legenda += " ⚠ erro de proposito"
        classe_legenda = (
            ' class="erro-de-proposito"' if quadro.get("errou_de_proposito") else ""
        )
        partes.append(
            f'<figure class="{" ".join(classes)}">{quadro["svg"]}'
            f"<figcaption{classe_legenda}>{_txt(legenda)}</figcaption></figure>"
        )
        if quadro["chave"]:
            passou_da_chave = True
    partes.append("</div>")
    return "".join(partes)


def _fita_da_solucao(item: DesafioNoPainel) -> str:
    """A solucao de referencia DESENHADA, um quadro por lance.

    ⛔ **Quando nao da para montar a sequencia, diz-se isso** — nada de mostrar
    meia solucao.
    """
    quadros = desenho.fita_da_solucao(
        item.co_formato_posicao,
        item.js_posicao_inicial,
        item.js_solucao,
        co_variante=item.co_variante,
    )
    if not quadros:
        return (
            '<p class="vazio">Sem sequencia desenhavel. Desafios gerados antes de '
            "11/09/2026 nao trazem a posicao de cada lance.</p>"
        )
    nota = (
        '<p class="nota">Cada tabuleiro e a posicao ANTES do lance: o tracejado e '
        "o caminho da peca, e o &times; marca as pecas que ele come, na ordem."
        "</p>"
        if item.co_formato_posicao == "fen"
        else ""
    )
    return nota + _quadros_html(quadros)


def _acoes(
    item: DesafioNoPainel,
    *,
    dt_hoje: date,
    dt_sugerida: date,
    dt_fim_janela_baixada: date,
    qt_tentativas: int = 0,
) -> str:
    """Os formularios de acao do desafio aberto.

    ⚠️ **Espelham as regras de `servico.py`, e nao as substituem**: um formulario
    ausente nao impede um `curl`. O que a tela esconde, o servico tambem recusa.
    """
    id_txt = _txt(item.id_desafio)
    # Para onde a pagina volta depois da acao: o mesmo dia, ou o mesmo desafio.
    voltar = (
        f'<input type="hidden" name="voltar" value="{_txt(item.dt_dia.isoformat())}">'
        if item.dt_dia
        else f'<input type="hidden" name="voltar_desafio" value="{id_txt}">'
    )
    oculto = f'<input type="hidden" name="id_desafio" value="{id_txt}">{voltar}'
    # ⛔ Dia jogado (passado, ou hoje com tentativa) nao se descarta nem se move:
    # espelho de `servico._exigir_dia_nao_jogado`, que e quem recusa de fato.
    ja_jogado = item.dt_dia is not None and (
        item.dt_dia < dt_hoje or (item.dt_dia == dt_hoje and qt_tentativas > 0)
    )
    if ja_jogado:
        return (
            '<p class="nota">Dia ja jogado nao se descarta nem se move: ele e a '
            "historia de quem jogou.</p>"
        )

    # ⛔ O que ja esta nos aparelhos nao sai do dia dele (07/10/2026): espelho de
    # `servico._exigir_fora_da_janela_baixada`, que e quem recusa de fato.
    baixado = item.dt_dia is not None and na_janela_baixada(
        item.dt_dia, dt_hoje=dt_hoje, dt_fim=dt_fim_janela_baixada
    )
    if baixado:
        nota_baixado = (
            '<p class="nota">&#128274; Este dia ja pode estar guardado nos aparelhos '
            "(o app baixa hoje e os proximos dias para jogar sem rede): nao se "
            "descarta, nao se move e nao sai do calendario. A curadoria vale de "
            f"{_txt(data_br(dt_fim_janela_baixada + timedelta(days=1)))} em diante.</p>"
        )
        # ⚠️ Aprovar um CANDIDATO continua possivel: o `/proximos` nao o entrega,
        # entao ele nao esta em aparelho nenhum, e aprova-lo so evita um dia em
        # branco. (Desde 02/10/2026 nada nasce candidato; e o caso raro.)
        if item.co_curadoria == "candidato":
            return (
                '<div class="caixa-acoes">'
                f'<form class="acoes" method="post" action="{BASE}/aprovar">{oculto}'
                '<button class="principal" type="submit">Aprovar</button></form>'
                + nota_baixado
                + "</div>"
            )
        return nota_baixado

    partes: list[str] = []
    if item.co_curadoria != "aprovado":
        rotulo = "Aprovar" if item.co_curadoria == "candidato" else "Reconsiderar e aprovar"
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/aprovar">{oculto}'
            f'<button class="principal" type="submit">{rotulo}</button></form>'
        )
    else:
        valor_dia = (item.dt_dia or dt_sugerida).isoformat()
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/agendar">{oculto}'
            f'<input type="date" name="dt_dia" value="{_txt(valor_dia)}" required>'
            '<button type="submit">'
            + ("Trocar a data" if item.dt_dia else "Agendar")
            + "</button></form>"
        )
        if item.dt_dia:
            partes.append(
                f'<form class="acoes" method="post" action="{BASE}/desagendar">'
                f'{oculto}<button type="submit">Tirar do calendario</button></form>'
            )
    if item.co_curadoria != "descartado":
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/descartar">{oculto}'
            '<input type="text" name="motivo" required maxlength="500" '
            'placeholder="por que este nao serve (obrigatorio)">'
            '<button class="perigo" type="submit">Descartar</button></form>'
            '<p class="nota">Descartar tira o desafio do dia; a proxima geracao '
            "tapa primeiro o buraco mais proximo.</p>"
        )
    return '<div class="caixa-acoes">' + "".join(partes) + "</div>"


def _momento_do_dia(dt_dia: Optional[date], dt_hoje: date) -> str:
    """`no ar hoje` · `encerrado` · `agendado` · `sem data`."""
    if dt_dia is None:
        return "sem data"
    if dt_dia == dt_hoje:
        return "no ar hoje"
    return "encerrado" if dt_dia < dt_hoje else "agendado"


def _cartao_do_desafio(
    item: DesafioNoPainel,
    *,
    dt_hoje: date,
    dt_sugerida: date,
    dt_fim_janela_baixada: date,
    qt_tentativas: int = 0,
) -> str:
    """O desafio aberto: o tabuleiro grande ao lado do que se decide sobre ele."""
    etiquetas = [
        f'<span class="etiqueta {_txt(item.co_curadoria)}">'
        f"{_txt(ROTULO_DA_CURADORIA.get(item.co_curadoria, item.co_curadoria))}</span>",
        f'<span class="etiqueta">{_txt(_momento_do_dia(item.dt_dia, dt_hoje))}</span>',
        f'<span class="etiqueta jogo">{_txt(ROTULO_DO_JOGO.get(item.co_jogo, item.co_jogo))}'
        + (f" &middot; {_txt(item.co_modalidade)}" if item.co_modalidade else "")
        + "</span>",
        f'<span class="etiqueta">contra {_txt(_rotulo_personagem(item.co_personagem))}</span>',
    ]
    if item.ic_reprise:
        etiquetas.append('<span class="etiqueta reprise">reprise</span>')

    return (
        '<article class="cartao">'
        f'<div class="tabuleiro">'
        f"{desenho.posicao(item.co_formato_posicao, item.js_posicao_inicial, numerar=True, maior=True, co_variante=item.co_variante)}"
        "</div>"
        '<div class="corpo">'
        f"<h2 class=\"titulo-desafio\">{_txt(item.no_tipo_desafio)}</h2>"
        f"<div>{''.join(etiquetas)}</div>"
        # ⛔ A FRASE, antes de qualquer dado tecnico (T040b): e o que se cura.
        + _frase_do_desafio(item)
        + '<dl class="dados">'
        f"<dt>chave</dt><dd>{_txt(item.co_chave_objetivo)} {_txt(item.js_objetivo)}</dd>"
        f"<dt>adversario</dt><dd>{_txt(_rotulo_personagem(item.co_personagem))} "
        f"&middot; semente {_txt(item.nu_semente)}</dd>"
        f"<dt>solucao</dt><dd>{item.nu_lances_solucao} lance(s)</dd>"
        f"<dt>gerado em</dt><dd>{_txt(momento_br(item.dh_geracao))} (Brasilia)</dd>"
        # ⚠️ O id inteiro, e nao encurtado (pedido do dono, 11/09/2026): e com ele
        # que se discute um desafio sem precisar de captura de tela.
        f'<dt>id</dt><dd><code class="id">{_txt(item.id_desafio)}</code></dd>'
        + (
            f"<dt>descarte</dt><dd>{_txt(item.de_motivo_descarte)}</dd>"
            if item.de_motivo_descarte
            else ""
        )
        + "</dl>"
        + "<h3>A regua (os mascotes, antes de ir ao ar)</h3>"
        + _regua(item)
        + _acoes(
            item,
            dt_hoje=dt_hoje,
            dt_sugerida=dt_sugerida,
            dt_fim_janela_baixada=dt_fim_janela_baixada,
            qt_tentativas=qt_tentativas,
        )
        + "</div></article>"
    )


def _kpi(valor: str, rotulo: str, detalhe: str = "") -> str:
    """Um numero grande com o rotulo — e, embaixo, o denominador ou o contexto.

    ⚠️ `valor` e `detalhe` ja chegam montados (podem ter `&ndash;`); quem chama
    garante que nao ha dado livre neles sem `_txt`.
    """
    sub = f"<small>{detalhe}</small>" if detalhe else ""
    return f'<div class="kpi"><b>{valor}</b><span>{_txt(rotulo)}</span>{sub}</div>'


def _como_foi_o_dia(
    item: DesafioNoPainel,
    resumo: ResumoDoDia,
    quadro: Sequence[LinhaDoQuadro],
    nao_resolveram: Sequence[QuemNaoResolveu],
) -> str:
    """O dia jogado: engajamento, dificuldade real, o quadro e quem nao resolveu."""
    if resumo.qt_pessoas == 0:
        return (
            '<section class="bloco"><h2>Como foi o dia</h2>'
            '<p class="vazio">Ninguem tentou este desafio ainda.</p></section>'
        )

    # A regua previu X (media dos mascotes); a gente resolveu Y.
    previsto = (
        sum(m.taxa for m in item.medicoes) / len(item.medicoes)
        if item.medicoes
        else None
    )
    kpis = "".join(
        [
            _kpi(
                str(resumo.qt_pessoas),
                "pessoas tentaram",
                f"{_pct(resumo.engajamento)} de {resumo.qt_ativos_no_dia} que jogaram algo no dia",
            ),
            _kpi(
                _pct(resumo.taxa_de_resolucao),
                "resolveram",
                f"{resumo.qt_resolveram} de {resumo.qt_pessoas}"
                + (f" &middot; a regua previa {_pct(previsto)}" if previsto is not None else ""),
            ),
            _kpi(
                str(resumo.qt_tentativas),
                "tentativas",
                (
                    f"{resumo.tentativas_por_pessoa:.1f} por pessoa"
                    if resumo.tentativas_por_pessoa is not None
                    else ""
                ),
            ),
            _kpi(
                (
                    f"{resumo.md_tentativa_que_resolveu:.1f}&ordf;"
                    if resumo.md_tentativa_que_resolveu is not None
                    else "&ndash;"
                ),
                "tentativa que resolveu",
                "em media (1&ordf; = de primeira)",
            ),
            _kpi(
                _txt(duracao_br(resumo.md_tempo_resolucao_ms)) or "&ndash;",
                "tempo para resolver",
                "mediana de quem resolveu",
            ),
            _kpi(
                f"{resumo.xp_medio:.0f}" if resumo.xp_medio is not None else "&ndash;",
                "XP medio",
                (
                    f"de {resumo.xp_minimo} a {resumo.xp_maximo}"
                    if resumo.xp_maximo is not None
                    else ""
                ),
            ),
            _kpi(
                str(sum(p.qt_usos for p in resumo.poderes)),
                "dicas usadas",
                (
                    f"por {sum(p.qt_pessoas for p in resumo.poderes)} pessoa(s)"
                    if resumo.poderes
                    else "ninguem pediu dica"
                ),
            ),
            _kpi(
                str(sum(r.qt for r in resumo.reacoes)),
                "reacoes no quadro",
                " ".join(f"{_txt(r.co_emoji)}&nbsp;{r.qt}" for r in resumo.reacoes),
            ),
        ]
    )

    # A distribuicao: quantas pessoas fizeram 1, 2, 3... tentativas.
    maior = max((f.qt_pessoas for f in resumo.distribuicao), default=1) or 1
    linhas_dist = []
    for fatia in resumo.distribuicao:
        largura = int(round(fatia.qt_pessoas / maior * 160))
        classe = "barra" if fatia.resolveu else "barra falhou"
        linhas_dist.append(
            f"<tr><td>{fatia.qt_tentativas} tentativa(s)</td>"
            f"<td>{'resolveu' if fatia.resolveu else 'nao resolveu'}</td>"
            f"<td>{fatia.qt_pessoas}</td>"
            f'<td><span class="{classe}" style="width:{largura}px"></span></td></tr>'
        )
    distribuicao = (
        '<table class="tabela"><tr><th>quantas vezes tentou</th><th></th>'
        "<th>pessoas</th><th></th></tr>" + "".join(linhas_dist) + "</table>"
    )

    auditoria = ", ".join(
        f"{qt} {_txt(estado)}" for estado, qt in sorted(resumo.auditoria.items())
    )

    return (
        '<section class="bloco"><h2>Como foi o dia</h2>'
        f'<div class="kpis">{kpis}</div>'
        '<div class="duas-colunas">'
        f"<div><h3>Tentativas por pessoa</h3>{distribuicao}</div>"
        f'<div><h3>Auditoria das resolucoes</h3><p class="nota">{auditoria or "nenhuma"}</p>'
        "</div></div>"
        + _quadro(quadro)
        + _nao_resolveram(nao_resolveram)
        + "</section>"
    )


def _gaveta_do_raio_x(id_tentativa: Any) -> str:
    """O raio-x de uma tentativa, carregado so quando o dono o abre.

    ⚠️ Sem JavaScript o `<details>` abre vazio, e o link de dentro leva a pagina
    do raio-x — o mesmo HTML, servido inteiro.
    """
    id_txt = _txt(id_tentativa)
    return (
        f'<details class="raio-x" data-tentativa="{id_txt}"><summary>raio-x</summary>'
        f'<div class="conteudo"><a href="{BASE}/raio-x/{id_txt}">abrir o raio-x</a>'
        "</div></details>"
    )


def _quadro(quadro: Sequence[LinhaDoQuadro]) -> str:
    """O quadro do dia, com todo mundo, na ordem do aplicativo."""
    if not quadro:
        return '<h3>O quadro</h3><p class="vazio">Ninguem resolveu ainda.</p>'
    partes = [
        "<h3>O quadro (quem resolveu)</h3>"
        '<table class="tabela ranking"><tr><th>#</th><th>pessoa</th><th>XP</th>'
        "<th>tempo</th><th>tentativas</th><th>dicas</th><th>reacoes</th>"
        "<th>auditoria</th><th>resolveu em</th><th></th></tr>"
    ]
    for linha in quadro:
        oculto = (
            ' <span class="etiqueta">oculto no app</span>' if not linha.ic_publico else ""
        )
        partes.append(
            "<tr>"
            f"<td>{linha.posicao}</td>"
            f"<td>{_nome_da_pessoa(linha.no_exibicao, linha.co_usuario)}{oculto}</td>"
            f"<td><b>{linha.nu_xp}</b></td>"
            f"<td>{_txt(duracao_br(linha.nu_tempo_ms))}</td>"
            f"<td>{linha.qt_tentativas} (resolveu na {linha.nu_sequencia}&ordf;)</td>"
            f"<td>{linha.qt_dicas}</td>"
            f"<td>{linha.qt_reacoes}</td>"
            f"<td>{_txt(linha.co_auditoria)}</td>"
            f"<td>{_txt(momento_br(linha.dh_resolucao))}</td>"
            f"<td>{_gaveta_do_raio_x(linha.id_tentativa)}</td>"
            "</tr>"
        )
    partes.append("</table>")
    return "".join(partes)


def _nao_resolveram(pessoas: Sequence[QuemNaoResolveu]) -> str:
    """Quem tentou e nao resolveu — e onde se ve se o desafio confunde."""
    if not pessoas:
        return ""
    partes = [
        "<h3>Tentaram e nao resolveram</h3>"
        '<table class="tabela"><tr><th>pessoa</th><th>tentativas</th>'
        "<th>tempo somado</th><th>dicas</th><th>a ultima tentativa</th></tr>"
    ]
    for p in pessoas:
        partes.append(
            "<tr>"
            f"<td>{_nome_da_pessoa(p.no_exibicao, p.co_usuario)}</td>"
            f"<td>{p.qt_tentativas}</td>"
            f"<td>{_txt(duracao_br(p.nu_tempo_total_ms))}</td>"
            f"<td>{p.qt_dicas}</td>"
            f"<td>{_gaveta_do_raio_x(p.id_ultima_tentativa)}</td>"
            "</tr>"
        )
    partes.append("</table>")
    return "".join(partes)


def _dia_vazio(detalhe: DetalheDoDia, *, dt_hoje: date) -> str:
    """O que mostrar num dia sem desafio — com o que fazer a respeito."""
    dia = detalhe.dt_dia
    assert dia is not None
    if dia < dt_hoje:
        texto = "Este dia passou sem desafio."
    else:
        texto = (
            "Dia vazio. A proxima geracao tapa os dias vazios mais proximos "
            "primeiro, com jogo, modalidade e adversario diferentes dos vizinhos."
        )
    partes = [f'<div class="aviso critico"><strong>{_txt(texto)}</strong></div>']
    if dia >= dt_hoje and detalhe.reserva:
        partes.append(
            "<h3>Ou agende agora um aprovado da reserva</h3><ul class=\"lista\">"
        )
        for item in detalhe.reserva:
            partes.append(
                f'<li><form class="acoes" method="post" action="{BASE}/agendar">'
                f'<input type="hidden" name="id_desafio" value="{_txt(item.id_desafio)}">'
                f'<input type="hidden" name="dt_dia" value="{dia.isoformat()}">'
                f'<input type="hidden" name="voltar" value="{dia.isoformat()}">'
                f"<span>{_txt(item.no_tipo_desafio)} "
                f'<span class="meta">{_txt(ROTULO_DO_JOGO.get(item.co_jogo, item.co_jogo))}'
                f" &middot; {_txt(_rotulo_personagem(item.co_personagem))}</span></span>"
                f'<button type="submit">Agendar em {data_curta_br(dia)}</button>'
                "</form></li>"
            )
        partes.append("</ul>")
    return "".join(partes)


def render_detalhe(
    detalhe: DetalheDoDia,
    *,
    dt_hoje: date,
    dt_sugerida: date,
    dt_fim_janela_baixada: date,
) -> str:
    """A area principal: o dia (ou o desafio) aberto.

    ⚠️ **E o mesmo HTML na pagina inteira e no fragmento** que o script busca ao
    trocar de dia: uma funcao so, para as duas nunca divergirem.

    Args:
        dt_fim_janela_baixada: o ultimo dia que pode estar num aparelho
            (`api/desafios/janela_baixada.py`). ⚠️ Sem valor padrao: esquecido,
            o painel ofereceria botoes que o servico recusaria.
    """
    item = detalhe.desafio
    dia = detalhe.dt_dia or (item.dt_dia if item else None)

    if dia is not None:
        anterior, seguinte = dia - timedelta(days=1), dia + timedelta(days=1)
        titulo = (
            f'<a class="seta" href="{_href_do_dia(anterior)}" data-navegar="1" '
            f'title="{data_br(anterior)}">&lsaquo;</a>'
            f"<h1>{_txt(_primeira_maiuscula(dia_por_extenso(dia)))}</h1>"
            f'<a class="seta" href="{_href_do_dia(seguinte)}" data-navegar="1" '
            f'title="{data_br(seguinte)}">&rsaquo;</a>'
            + (
                f'<a class="botao-hoje" href="{_href_do_dia(dt_hoje)}" '
                'data-navegar="1">hoje</a>'
                if dia != dt_hoje
                else ""
            )
        )
    else:
        titulo = "<h1>Desafio sem data</h1>"

    partes = [f'<div class="cabeca-do-dia" data-dia="{dia.isoformat() if dia else ""}">{titulo}</div>']

    if item is None:
        partes.append(_dia_vazio(detalhe, dt_hoje=dt_hoje))
        return "".join(partes)

    partes.append(
        _cartao_do_desafio(
            item,
            dt_hoje=dt_hoje,
            dt_sugerida=dt_sugerida,
            dt_fim_janela_baixada=dt_fim_janela_baixada,
            qt_tentativas=detalhe.resumo.qt_tentativas if detalhe.resumo else 0,
        )
    )
    if detalhe.resumo is not None:
        partes.append(
            _como_foi_o_dia(item, detalhe.resumo, detalhe.quadro, detalhe.nao_resolveram)
        )
    partes.append(
        '<section class="bloco"><h2>A solucao de referencia, lance a lance</h2>'
        + _fita_da_solucao(item)
        + "<details><summary>o gabarito em JSON</summary>"
        f"<pre>{_txt(item.js_solucao)}</pre></details></section>"
    )
    return "".join(partes)


# ═══════════════════════════════════════════════════════════════════════════
# 4. O raio-x de uma tentativa
# ═══════════════════════════════════════════════════════════════════════════


def render_raio_x(raio: Optional[RaioX]) -> str:
    """Uma tentativa inteira: como foi, as dicas, o XP e a partida desenhada.

    ⚠️ **Le o que foi gravado**: o XP e o extrato sao os da tabela, e nao uma
    conta refeita aqui — a regra de credito mora em `credito_do_dia.py`.
    """
    if raio is None:
        return '<p class="vazio">Tentativa nao encontrada.</p>'

    situacao = (
        f"resolveu, {raio.nu_xp} XP, auditoria {_txt(raio.co_auditoria)}"
        if raio.ic_resolveu
        else "nao resolveu"
    )
    partes = [
        f'<p class="nota"><strong>{_nome_da_pessoa(raio.no_exibicao, raio.co_usuario)}</strong>'
        f" &middot; {raio.nu_sequencia}&ordf; tentativa &middot; "
        f"{_txt(duracao_br(raio.nu_tempo_ms))} &middot; {situacao}"
        + (
            f" &middot; objetivo no lance {raio.nu_lance_cumpre_desafio}"
            if raio.nu_lance_cumpre_desafio
            else ""
        )
        + (f" &middot; comecou {_txt(momento_br(raio.dh_inicio))}" if raio.dh_inicio else "")
        + "</p>"
    ]
    if raio.de_auditoria:
        partes.append(f'<p class="nota">Auditoria: {_txt(raio.de_auditoria)}</p>')

    if raio.poderes:
        dicas = ", ".join(
            f"{_txt(p.get('co_tipo_poder'))} (grau {_txt(p.get('nu_grau'))}, "
            f"{_txt(momento_br(p.get('dh_consumo')))})"
            for p in raio.poderes
        )
        partes.append(f'<p class="nota">Poderes usados: {dicas}</p>')
    else:
        partes.append('<p class="nota">Nenhuma dica usada.</p>')

    if raio.extrato:
        linhas = []
        for e in raio.extrato:
            linhas.append(
                "<tr>"
                f"<td>{_txt(e.get('co_tipo_xp'))}</td>"
                f"<td>{_txt(e.get('co_feito')) or '&mdash;'}</td>"
                f"<td>{_txt(e.get('vr_medida'))} {_txt(e.get('co_unidade'))}</td>"
                f"<td>{_txt(e.get('vr_normalizado'))}</td>"
                f"<td>{_txt(e.get('vr_peso'))}</td>"
                f"<td><b>{_txt(e.get('vr_xp'))}</b></td>"
                "</tr>"
            )
        partes.append(
            "<h4>De onde veio o XP</h4>"
            '<table class="tabela"><tr><th>parcela</th><th>feito</th><th>medida</th>'
            "<th>normalizado</th><th>peso</th><th>XP</th></tr>"
            + "".join(linhas)
            + "</table>"
        )

    quadros = desenho.fita_da_partida(
        raio.co_formato_posicao,
        raio.js_posicao_inicial,
        raio.lances,
        nu_lance_cumpre_desafio=raio.nu_lance_cumpre_desafio,
        co_variante=raio.co_variante,
    )
    if quadros:
        partes.append(
            f"<h4>A partida, lance a lance ({len(raio.lances)} lances)</h4>"
            + _quadros_html(quadros)
        )
    else:
        partes.append('<p class="vazio">Sem lances gravados para esta tentativa.</p>')
    return "".join(partes)


# ═══════════════════════════════════════════════════════════════════════════
# 5. A pagina inteira
# ═══════════════════════════════════════════════════════════════════════════

_ESTILO_TOKENS = f"""
:root {{
  --papel: {desenho.PAPEL};
  --papel-2: {desenho.PAPEL_2};
  --creme: {desenho.CREME};
  --madeira: {desenho.MADEIRA};
  --madeira-esc: {desenho.MADEIRA_ESC};
  --tinta: {desenho.TINTA};
  --tinta-suave: {desenho.TINTA_SUAVE};
  --ouro: {desenho.OURO};
  --ouro-esc: #A87A24;
  --terracota: #B85C38;
  --terracota-esc: #8C4226;
  --salvia: #7A9E7E;
  --salvia-esc: #57795C;
  --azul: {desenho.AZUL_J1};
  --borda: rgba(94,61,34,.22);
}}
"""

#: O CSS sem chaves duplicadas: string comum, e nao f-string, para ler como CSS.
_ESTILO = """
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--papel); color: var(--tinta);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 14px; line-height: 1.45;
}
header {
  background: var(--madeira-esc); color: var(--papel);
  padding: 12px 24px; display: flex; align-items: baseline; gap: 16px;
  flex-wrap: wrap;
}
header h1 { margin: 0; font-size: 19px; letter-spacing: .02em; }
header p { margin: 0; opacity: .8; font-size: 13px; }
a { color: var(--madeira-esc); }

/* ⚠️ A GRADE DA PAGINA: a lateral tem largura fixa e o dia ocupa TODO o resto.
   Era o pedido central: "ha muito espaco vazio dos lados". `minmax(0, 1fr)`
   deixa a coluna encolher abaixo do conteudo, para a fita quebrar em linhas em
   vez de empurrar a pagina para o lado. */
.grade {
  display: grid; grid-template-columns: 380px minmax(0, 1fr);
  gap: 20px; padding: 16px 24px 48px;
}
@media (max-width: 1000px) { .grade { grid-template-columns: minmax(0, 1fr); } }
.lateral { display: flex; flex-direction: column; gap: 14px; }
.bloco {
  background: var(--creme); border: 1px solid var(--borda);
  border-radius: 14px; padding: 12px 14px;
}
.principal-area { min-width: 0; display: flex; flex-direction: column; gap: 16px; }
h2 {
  font-size: 13px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--tinta-suave); margin: 0 0 8px;
}
h3 { font-size: 14px; margin: 14px 0 6px; }
h4 { font-size: 13px; margin: 12px 0 4px; }

/* O CALENDARIO */
/* ⚠️ Sem `text-transform: capitalize`: ele poe maiuscula em TODA palavra, e
   saia "Setembro De 2026". A maiuscula vem do Python, so na primeira letra. */
.mes h3 { margin: 4px 0 6px; }
.grade-mes { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
.dsem { text-align: center; font-size: 11px; color: var(--tinta-suave); }
.dia {
  display: flex; flex-direction: column; min-height: 54px; padding: 2px 4px;
  border-radius: 7px; text-decoration: none; color: var(--tinta);
  background: var(--papel); border: 2px solid transparent; position: relative;
  overflow: hidden;
}
.dia b { font-size: 12px; }
.dia small { font-size: 9px; line-height: 1.1; white-space: nowrap; }
.dia i { font-style: normal; font-size: 9px; position: absolute; right: 3px; top: 2px; }
.dia.aprovado { background: #D6E4D3; }
.dia.candidato { background: #F1DDB0; }
.dia.descartado, .dia.buraco { background: #F0CDC2; }
.dia.passado { opacity: .45; }
.dia.livre { opacity: .7; }
.dia.hoje { border-color: var(--azul); }
.dia.selecionado { border-color: var(--madeira-esc); box-shadow: 0 0 0 2px var(--ouro); }
.dia:hover { filter: brightness(.95); }
.legenda { font-size: 11px; color: var(--tinta-suave); margin: 8px 0 0; }
.pino { display: inline-block; width: 10px; height: 10px; border-radius: 3px;
  margin: 0 3px 0 8px; vertical-align: middle; }
.pino.aprovado { background: #D6E4D3; } .pino.candidato { background: #F1DDB0; }
.pino.buraco { background: #F0CDC2; }
.pino.hoje { border: 2px solid var(--azul); }

/* OS AVISOS E CONTADORES */
.aviso { border-radius: 10px; padding: 8px 12px; margin: 6px 0;
  border-left: 6px solid var(--salvia); background: var(--papel); }
.aviso.atencao { border-left-color: var(--ouro); }
.aviso.critico { border-left-color: var(--terracota); }
.aviso strong { display: block; }
.aviso small { color: var(--tinta-suave); }
.contadores { display: flex; gap: 8px; flex-wrap: wrap; }
.contador { background: var(--papel); border: 1px solid var(--borda);
  border-radius: 10px; padding: 4px 10px; min-width: 80px; }
.contador b { display: block; font-size: 18px; }
.contador span { font-size: 10px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--tinta-suave); }

/* AS LISTAS DA LATERAL */
.lista { list-style: none; padding: 0; margin: 4px 0; }
.lista li { padding: 4px 0; border-bottom: 1px dashed var(--borda); }
.meta { color: var(--tinta-suave); font-size: 12px; }
.motivo { display: block; font-size: 12px; font-style: italic; color: var(--terracota-esc); }
details summary { cursor: pointer; color: var(--tinta-suave); font-size: 13px; padding: 3px 0; }

/* O DIA ABERTO */
.cabeca-do-dia { display: flex; align-items: center; gap: 10px; }
.cabeca-do-dia h1 { margin: 0; font-size: 22px; }
.seta { font-size: 26px; text-decoration: none; padding: 0 8px; border-radius: 8px;
  background: var(--creme); border: 1px solid var(--borda); line-height: 1.2; }
.botao-hoje { font-size: 12px; padding: 3px 10px; border-radius: 999px;
  background: var(--azul); color: #fff; text-decoration: none; }
.cartao { display: flex; gap: 24px; flex-wrap: wrap; background: var(--creme);
  border: 1px solid var(--borda); border-radius: 14px; padding: 16px; }
.cartao .tabuleiro { flex: 0 0 auto; }
.cartao .corpo { flex: 1 1 420px; min-width: 300px; }
.titulo-desafio { font-size: 20px; text-transform: none; letter-spacing: 0;
  color: var(--tinta); margin: 0 0 6px; }
.etiqueta { display: inline-block; font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; padding: 2px 8px; border-radius: 999px;
  background: var(--papel-2); color: var(--tinta-suave); margin: 0 4px 4px 0; }
.etiqueta.candidato { background: var(--ouro); color: var(--madeira-esc); }
.etiqueta.aprovado { background: var(--salvia); color: #fff; }
.etiqueta.descartado { background: var(--terracota); color: #fff; }
.etiqueta.reprise { background: var(--azul); color: #fff; }
/* ⛔ A FRASE DO DESAFIO (T040b): o texto mais importante do cartao, e por isso
   maior que os dados e sem a fonte monoespacada. */
p.frase { margin: 8px 0 10px; font-size: 16px; line-height: 1.4;
  padding: 8px 12px; border-left: 3px solid var(--ouro);
  background: var(--papel-2); border-radius: 0 8px 8px 0; }
p.nota { font-size: 13px; color: var(--tinta-suave); margin: 4px 0; }
.vazio { color: var(--tinta-suave); font-style: italic; }
dl.dados { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px;
  margin: 8px 0; font-size: 13px; }
dl.dados dt { color: var(--tinta-suave); }
dl.dados dd { margin: 0; font-family: ui-monospace, Consolas, monospace;
  overflow-wrap: anywhere; }
code.id { font-family: ui-monospace, Consolas, monospace; font-size: 12px;
  background: var(--papel-2); padding: 1px 5px; border-radius: 5px;
  user-select: all; }
.codigo { font-family: ui-monospace, Consolas, monospace; font-size: 11px;
  color: var(--tinta-suave); }

/* AS TABELAS E AS BARRAS */
table.tabela { border-collapse: collapse; font-size: 13px; margin: 6px 0; width: auto; }
table.tabela th, table.tabela td { padding: 4px 12px 4px 0; text-align: left;
  vertical-align: top; border-bottom: 1px solid var(--borda); }
table.tabela th { color: var(--tinta-suave); font-weight: 600; }
table.ranking { width: 100%; }
.barra { display: inline-block; height: 9px; border-radius: 4px;
  background: var(--salvia); vertical-align: middle; }
.regua .barra { background: var(--azul); }
.barra.falhou { background: var(--terracota); }

/* OS NUMEROS DO DIA */
.kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 10px; }
.kpi { background: var(--papel); border: 1px solid var(--borda);
  border-radius: 12px; padding: 8px 12px; }
.kpi b { display: block; font-size: 24px; }
.kpi span { font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--tinta-suave); }
.kpi small { display: block; font-size: 12px; color: var(--tinta-suave); }
.duas-colunas { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px; }

/* OS FORMULARIOS */
.caixa-acoes { margin-top: 12px; padding-top: 8px; border-top: 1px dashed var(--borda); }
form.acoes, form.gerar { display: flex; gap: 8px; flex-wrap: wrap;
  align-items: center; margin: 6px 0; }
form.acoes input[type=text] { flex: 1 1 260px; }
button, input[type=date], input[type=text] {
  font: inherit; border-radius: 8px; padding: 6px 12px;
  border: 1px solid rgba(94,61,34,.3); background: var(--papel); color: var(--tinta);
}
button { cursor: pointer; border-bottom-width: 3px; }
button.principal { background: var(--ouro); border-color: var(--ouro-esc); font-weight: 700; }
button.perigo { background: var(--terracota); border-color: var(--terracota-esc); color: #fff; }
.recado { background: var(--salvia); color: #fff; padding: 10px 16px;
  border-radius: 10px; margin: 12px 24px 0; }
.recado.erro { background: var(--terracota); }
pre { background: var(--papel-2); padding: 8px; border-radius: 8px;
  overflow-x: auto; font-size: 12px; }

/* A FITA DE LANCES */
.fita { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.quadro { border: 1px solid var(--borda); border-radius: 10px; padding: 6px;
  background: var(--papel); margin: 0; }
.quadro figcaption { font-size: 11px; color: var(--tinta-suave);
  text-align: center; margin-top: 4px; max-width: 280px; }
/* O lance que CUMPRE o objetivo - o unico que a curadoria precisa julgar. */
.quadro.chave { border-color: var(--ouro); border-width: 3px; padding: 4px; }
.quadro.chave figcaption { color: var(--tinta); font-weight: 700; }
.quadro.depois { opacity: .55; }
.quadro .erro-de-proposito { color: var(--terracota); font-weight: 700; }
.raio-x .conteudo { padding: 8px 0; }
.carregando { opacity: .5; transition: opacity .15s; }
"""

#: O script leve (ver o topo do modulo): trocar de dia, abrir o raio-x e
#: acompanhar a geracao. ⚠️ Nenhuma acao de escrita passa por aqui.
_SCRIPT = """
(function () {
  var BASE = document.body.getAttribute('data-base');
  var area = document.getElementById('detalhe');

  // Marca no calendario o dia que esta aberto.
  function marcar(dia) {
    document.querySelectorAll('.dia.selecionado').forEach(function (a) {
      a.classList.remove('selecionado');
    });
    if (!dia) return;
    var alvo = document.querySelector('.dia[data-dia="' + dia + '"]');
    if (alvo) alvo.classList.add('selecionado');
  }

  // Busca o HTML do dia pronto no servidor e o poe no lugar. Se algo falhar,
  // navega do jeito normal: o link funciona sem este script.
  function abrir(endereco, empilhar) {
    var url = new URL(endereco, location.href);
    area.classList.add('carregando');
    fetch(BASE + '/fragmento' + url.search, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        area.innerHTML = html;
        area.classList.remove('carregando');
        var cabeca = area.querySelector('.cabeca-do-dia');
        marcar(cabeca ? cabeca.getAttribute('data-dia') : null);
        var recado = document.querySelector('.recado');
        if (recado) recado.remove();
        if (empilhar) history.pushState({}, '', url.pathname + url.search);
        if (area.getBoundingClientRect().top < 0) area.scrollIntoView();
      })
      .catch(function () { location.href = endereco; });
  }

  document.addEventListener('click', function (ev) {
    var a = ev.target.closest('a[data-navegar]');
    // Ctrl/Cmd/Shift ou botao do meio: o dono quer abrir noutra aba.
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) return;
    ev.preventDefault();
    abrir(a.href, true);
  });
  window.addEventListener('popstate', function () { abrir(location.href, false); });

  // O raio-x: carrega na primeira vez que a gaveta abre. `toggle` nao borbulha,
  // por isso a escuta e na fase de captura (o `true` no fim).
  document.addEventListener('toggle', function (ev) {
    var gaveta = ev.target;
    if (!gaveta.matches || !gaveta.matches('details[data-tentativa]')) return;
    if (!gaveta.open || gaveta.getAttribute('data-carregado')) return;
    gaveta.setAttribute('data-carregado', '1');
    var conteudo = gaveta.querySelector('.conteudo');
    conteudo.textContent = 'carregando...';
    fetch(BASE + '/raio-x/' + gaveta.getAttribute('data-tentativa') + '?fragmento=1',
          { credentials: 'same-origin' })
      .then(function (r) { return r.text(); })
      .then(function (html) { conteudo.innerHTML = html; })
      .catch(function () { conteudo.textContent = 'nao deu para carregar.'; });
  }, true);

  // A geracao: enquanto roda, pergunta de 15 em 15 s; ao terminar, recarrega a
  // pagina INTEIRA, para a tela mostrar o banco, e nao um remendo.
  var estado = document.getElementById('estado-geracao');
  if (estado && estado.getAttribute('data-rodando') === '1') {
    var relogio = setInterval(function () {
      fetch(BASE + '/geracao', { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          estado.textContent = 'Ultima execucao: ' + j.resumo;
          if (!j.rodando) { clearInterval(relogio); location.reload(); }
        })
        .catch(function () {});
    }, 15000);
  }
})();
"""


def render(
    *,
    dt_hoje: date,
    dt_fim_janela_baixada: date,
    detalhe: DetalheDoDia,
    calendario: Sequence[DiaNoCalendario],
    estado_da_fila: EstadoDaFila,
    contagem: ContagemDeAuditoria,
    divergencias: Iterable[Divergencia],
    candidatos: Sequence[DesafioSemDia] = (),
    reserva: Sequence[DesafioSemDia] = (),
    descartados: Sequence[DesafioSemDia] = (),
    recado: Optional[str] = None,
    recado_e_erro: bool = False,
) -> str:
    """A pagina inteira do painel de gestao.

    Args:
        dt_hoje: o dia corrente em UTC.
        dt_fim_janela_baixada: o ultimo dia que pode estar num aparelho - os
            dias ate ele nao oferecem descartar nem mover (07/10/2026).
        detalhe: o dia (ou desafio) aberto na area principal.
        calendario: os dias com desafio nos meses mostrados.
        estado_da_fila: a folga da fila (T040).
        contagem, divergencias: a auditoria das resolucoes (T040).
        candidatos, reserva, descartados: o que nao mora no calendario.
        recado: a mensagem do que acabou de acontecer, se houve acao.
        recado_e_erro: pinta o recado de vermelho.

    Returns:
        O HTML completo, pronto para uma `HTMLResponse`.
    """
    # A data sugerida para agendar e o primeiro buraco da fila, e nao "amanha":
    # e o dia que de fato precisa de dono.
    dt_sugerida = estado_da_fila.buracos[0] if estado_da_fila.buracos else dt_hoje
    dt_selecionado = detalhe.dt_dia or (detalhe.desafio.dt_dia if detalhe.desafio else None)
    candidatos_agendados = sum(1 for d in calendario if d.co_curadoria == "candidato")

    bloco_recado = (
        f'<div class="recado{" erro" if recado_e_erro else ""}">{_txt(recado)}</div>'
        if recado
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Gestao do Desafio do Dia</title>
<style>{_ESTILO_TOKENS}{_ESTILO}</style>
</head>
<body data-base="{BASE}">
<header>
  <h1>Gestao do Desafio do Dia</h1>
  <p>Hoje e {_txt(dia_por_extenso(dt_hoje))} (o dia do desafio e o dia UTC).</p>
</header>
{bloco_recado}
<div class="grade">
  <aside class="lateral">
    {_secao_gerar()}
    <section class="bloco"><h2>A fila</h2>{_secao_fila(estado_da_fila)}</section>
    <section class="bloco"><h2>Calendario</h2>
      {_calendario(calendario, dt_hoje=dt_hoje, dt_selecionado=dt_selecionado)}
    </section>
    {_secao_pendencias(candidatos=candidatos, candidatos_agendados=candidatos_agendados, reserva=reserva, descartados=descartados)}
    <section class="bloco"><h2>Divergencias de julgamento</h2>
      {_secao_divergencias(contagem, divergencias)}
    </section>
  </aside>
  <main class="principal-area" id="detalhe">
    {render_detalhe(detalhe, dt_hoje=dt_hoje, dt_sugerida=dt_sugerida, dt_fim_janela_baixada=dt_fim_janela_baixada)}
  </main>
</div>
<script>{_SCRIPT}</script>
</body>
</html>"""


def pagina_avulsa(titulo: str, corpo: str) -> str:
    """Um fragmento servido sozinho, com o estilo do painel.

    ⚠️ E o caminho de quem abre o raio-x sem JavaScript (ou numa aba nova): o
    mesmo HTML do fragmento, dentro de uma pagina com o CSS.
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{_txt(titulo)}</title><style>{_ESTILO_TOKENS}{_ESTILO}</style></head>
<body><header><h1>{_txt(titulo)}</h1><p><a style="color:inherit" href="{BASE}">voltar ao painel</a></p></header>
<main style="padding:16px 24px">{corpo}</main></body></html>"""
