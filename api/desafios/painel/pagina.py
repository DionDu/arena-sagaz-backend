"""O HTML DO PAINEL (T039/T040).

═══════════════════════════════════════════════════════════════════════════
POR QUE E STRING, E NAO UM MOTOR DE TEMPLATES
═══════════════════════════════════════════════════════════════════════════

Jinja2 nao esta em `requirements_api.txt`, e acrescenta-lo por causa de **uma**
pagina interna significaria uma dependencia nova na imagem que serve o
aplicativo em producao. O ganho seria conforto de escrita; o preco, superficie.

⚠️ **Escapar deixa de ser automatico, e por isso ha uma regra unica aqui:**
todo valor vindo do banco passa por `_txt()`. Nao ha excecao — nem para o que
"claramente" e um UUID, porque a proxima coluna a entrar nao sera.

═══════════════════════════════════════════════════════════════════════════
⚠️ SEM JAVASCRIPT, E ISSO E DECISAO
═══════════════════════════════════════════════════════════════════════════

Toda acao e um `<form method="post">`. Nao ha `fetch`, nao ha estado no
navegador, e a pagina inteira recarrega a cada clique.

Para uma ferramenta que uma pessoa abre uma vez por dia, isso e uma vantagem, e
nao um atraso: o que esta na tela e o que esta no banco, sempre — nao existe o
estado intermediario em que a interface ja mudou e a gravacao falhou. E foi
exatamente esse estado que produziu, no aplicativo, o defeito de *"a tela diz
uma coisa e o dado diz outra"* mais de uma vez.

═══════════════════════════════════════════════════════════════════════════
A ORDEM DA PAGINA E A ORDEM DA VISITA
═══════════════════════════════════════════════════════════════════════════

    1. os avisos      → o que pode estragar o dia de amanha
    2. as divergencias → o que ja estragou e ninguem viu
    3. a fila          → o trabalho de hoje

⚠️ **Os avisos vem primeiro de proposito** (RF-DES-012f): eles sao a razao de a
visita existir num dia em que a fila esta vazia, e um aviso no rodape de uma
pagina longa e um aviso que nao existe.
"""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Iterable, Optional

from api.desafios.painel import desenho
from api.desafios.painel.repositorio import DesafioNoPainel
from api.desafios.painel.vigilancia import (
    ContagemDeAuditoria,
    Divergencia,
    EstadoDaFila,
)

#: O caminho base do painel. Escrito uma vez para que os `action=` dos
#: formularios nao se espalhem como literais.
BASE = "/painel/desafios"


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


def _rotulo_personagem(co_personagem: str) -> str:
    """O nome do mascote com a inicial maiuscula, para leitura humana."""
    return co_personagem.capitalize() if co_personagem else "?"


_ESTILO = f"""
:root {{
  --papel: {desenho.PAPEL};
  --papel-2: {desenho.PAPEL_2};
  --creme: #FBF8F1;
  --madeira: {desenho.MADEIRA};
  --madeira-esc: {desenho.MADEIRA_ESC};
  --tinta: {desenho.TINTA};
  --tinta-suave: {desenho.TINTA_SUAVE};
  --ouro: {desenho.OURO};
  --terracota: #B85C38;
  --salvia: #7A9E7E;
  --azul: {desenho.AZUL_J1};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0 0 48px;
  background: var(--papel); color: var(--tinta);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px; line-height: 1.5;
}}
header {{
  background: var(--madeira-esc); color: var(--papel);
  padding: 16px 20px; margin-bottom: 20px;
}}
header h1 {{ margin: 0; font-size: 20px; letter-spacing: .02em; }}
header p {{ margin: 4px 0 0; opacity: .8; font-size: 13px; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 0 16px; }}
section {{ margin-bottom: 28px; }}
h2 {{
  font-size: 15px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--tinta-suave); border-bottom: 1px solid rgba(94,61,34,.22);
  padding-bottom: 6px;
}}
.aviso {{
  border-radius: 10px; padding: 12px 16px; margin-bottom: 12px;
  border-left: 6px solid var(--salvia); background: var(--creme);
}}
.aviso.atencao {{ border-left-color: var(--ouro); }}
.aviso.critico {{ border-left-color: var(--terracota); }}
.aviso strong {{ display: block; margin-bottom: 2px; }}
.aviso small {{ color: var(--tinta-suave); }}
.contadores {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0; }}
.contador {{
  background: var(--creme); border: 1px solid rgba(94,61,34,.22);
  border-radius: 10px; padding: 8px 14px; min-width: 92px;
}}
.contador b {{ display: block; font-size: 20px; }}
.contador span {{ font-size: 11px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--tinta-suave); }}
.card {{
  background: var(--creme); border: 1px solid rgba(94,61,34,.22);
  border-radius: 14px; padding: 16px; margin-bottom: 14px;
  display: flex; gap: 18px; flex-wrap: wrap;
}}
.card .desenho {{ flex: 0 0 auto; }}
.card .corpo {{ flex: 1 1 340px; min-width: 300px; }}
.card h3 {{ margin: 0 0 6px; font-size: 16px; }}
.etiqueta {{
  display: inline-block; font-size: 11px; text-transform: uppercase;
  letter-spacing: .08em; padding: 2px 8px; border-radius: 999px;
  background: var(--papel-2); color: var(--tinta-suave); margin-right: 6px;
}}
.etiqueta.candidato {{ background: var(--ouro); color: var(--madeira-esc); }}
.etiqueta.aprovado {{ background: var(--salvia); color: #fff; }}
.etiqueta.descartado {{ background: var(--terracota); color: #fff; }}
.etiqueta.reprise {{ background: var(--azul); color: #fff; }}
dl.dados {{ display: grid; grid-template-columns: auto 1fr; gap: 2px 12px;
  margin: 8px 0; font-size: 13px; }}
dl.dados dt {{ color: var(--tinta-suave); }}
dl.dados dd {{ margin: 0; font-family: ui-monospace, monospace; }}
table.regua {{ border-collapse: collapse; font-size: 13px; margin: 8px 0; }}
table.regua th, table.regua td {{
  padding: 3px 10px 3px 0; text-align: left; }}
table.regua th {{ color: var(--tinta-suave); font-weight: 600; }}
.barra {{ display: inline-block; height: 8px; border-radius: 4px;
  background: var(--azul); vertical-align: middle; }}
form.acoes {{ display: flex; gap: 8px; flex-wrap: wrap;
  align-items: center; margin-top: 10px; }}
button, input[type=date], input[type=text] {{
  font: inherit; border-radius: 8px; padding: 6px 12px;
  border: 1px solid rgba(94,61,34,.3); background: var(--papel);
  color: var(--tinta);
}}
button {{ cursor: pointer; border-bottom-width: 3px; }}
button.principal {{ background: var(--ouro); border-color: #A87A24;
  font-weight: 700; }}
button.perigo {{ background: var(--terracota); border-color: #8C4226;
  color: #fff; }}
.vazio {{ color: var(--tinta-suave); font-style: italic; padding: 8px 0; }}
.recado {{ background: var(--salvia); color: #fff; padding: 10px 16px;
  border-radius: 10px; margin-bottom: 16px; }}
.recado.erro {{ background: var(--terracota); }}
details summary {{ cursor: pointer; color: var(--tinta-suave);
  font-size: 13px; }}
pre {{ background: var(--papel-2); padding: 8px; border-radius: 8px;
  overflow-x: auto; font-size: 12px; }}

/* A solucao desenhada: uma tira de quadros que quebra em varias linhas.
   ⚠️ `flex-wrap` e nao `overflow-x`: numa solucao de 19 lances (elas existem,
   no Pontinhos) uma tira rolavel esconderia o fim da solucao atras de um gesto
   que ninguem adivinha - e e justamente o fim que decide o desafio. */
.fita {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }}
.quadro {{ border: 1px solid var(--borda); border-radius: 10px; padding: 6px;
  background: var(--papel); }}
.quadro figcaption {{ font-size: 11px; color: var(--tinta-suave);
  text-align: center; margin-top: 4px; }}
/* O lance que CUMPRE o objetivo - e o unico que a curadoria precisa julgar. */
.quadro.chave {{ border-color: var(--ouro); border-width: 2px; padding: 5px; }}
.quadro.chave figcaption {{ color: var(--tinta); font-weight: 700; }}
.quadro .vez {{ font-size: 10px; }}
"""


def _secao_fila(estado: EstadoDaFila) -> str:
    """O aviso de fila curta (RF-DES-012f).

    ⚠️ **Ele aparece mesmo quando esta tudo bem** — em verde, dizendo quantos
    dias ha. Um aviso que so existe no dia ruim nao ensina o dono a le-lo, e no
    dia em que aparecer ele sera uma novidade a interpretar sob pressao.
    """
    classe = {"ok": "", "atencao": "atencao", "critico": "critico"}[
        estado.gravidade
    ]
    if estado.gravidade == "ok":
        titulo = f"Fila coberta por {estado.dias_cobertos} dias."
    elif estado.gravidade == "atencao":
        titulo = (
            f"A fila cobre so {estado.dias_cobertos} dias — abaixo dos 7 que uma "
            "execucao do job repoe."
        )
    else:
        titulo = (
            f"FILA CRITICA: {estado.dias_cobertos} dia(s) cobertos."
            if estado.dias_cobertos
            else "FILA VAZIA: nao ha desafio aprovado para hoje."
        )

    detalhe = (
        f"{estado.reserva} desafio(s) aprovado(s) esperando data. "
        "Aprovado sem data nao vai ao ar: agende."
        if estado.reserva
        else "Nenhum desafio aprovado em reserva — so ha o que o job gerar."
    )
    buracos = (
        "Dias descobertos nos proximos 7: "
        + ", ".join(d.isoformat() for d in estado.buracos)
        if estado.buracos
        else ""
    )
    return (
        f'<div class="aviso {classe}"><strong>{_txt(titulo)}</strong>'
        f"<small>{_txt(detalhe)}"
        + (f"<br>{_txt(buracos)}" if buracos else "")
        + "</small></div>"
    )


def _secao_divergencias(
    contagem: ContagemDeAuditoria, divergencias: Iterable[Divergencia]
) -> str:
    """A secao de divergencias de julgamento (RF-DES-034a).

    ⚠️ **Os tres contadores aparecem sempre**, e o texto explica o que
    `pendente` alto significa: sem o avaliador (T043a) rodando, `divergente = 0`
    nao quer dizer "esta tudo certo" — quer dizer "ninguem conferiu".
    """
    partes = [
        '<div class="contadores">',
        f'<div class="contador"><b>{contagem.pendente}</b>'
        "<span>pendentes</span></div>",
        f'<div class="contador"><b>{contagem.confere}</b>'
        "<span>conferem</span></div>",
        f'<div class="contador"><b>{contagem.divergente}</b>'
        "<span>divergentes</span></div>",
        "</div>",
    ]

    if contagem.avaliador_nunca_rodou:
        partes.append(
            '<div class="aviso critico"><strong>O avaliador de resolucoes '
            "nao rodou ainda.</strong><small>Ha resolucoes recebidas e nenhuma "
            "conferida. Enquanto isso, <code>divergente = 0</code> significa "
            "&quot;ninguem olhou&quot;, e nao &quot;esta tudo certo&quot;."
            "</small></div>"
        )

    linhas = list(divergencias)
    if not linhas:
        partes.append(
            '<p class="vazio">Nenhuma divergencia de julgamento registrada.</p>'
        )
        return "".join(partes)

    partes.append(
        '<div class="aviso critico"><strong>Divergencia nao corrige nada.'
        "</strong><small>Vale o aplicativo (RF-DES-032): a pessoa continua no "
        "quadro e o XP dela nao muda. Estas linhas existem para serem "
        "investigadas.</small></div>"
        '<table class="regua"><tr><th>dia</th><th>jogo</th><th>tipo</th>'
        "<th>XP</th><th>o que o arbitro achou</th></tr>"
    )
    for linha in linhas:
        partes.append(
            "<tr>"
            f"<td>{_txt(linha.dt_dia)}</td>"
            f"<td>{_txt(linha.co_jogo)}</td>"
            f"<td>{_txt(linha.co_tipo_desafio)}</td>"
            f"<td>{_txt(linha.nu_xp)}</td>"
            f"<td>{_txt(linha.de_auditoria) or '&mdash;'}</td>"
            "</tr>"
        )
    partes.append("</table>")
    return "".join(partes)


def _regua(item: DesafioNoPainel) -> str:
    """A medicao da regua por mascote (RF-DES-012b).

    ⚠️ **Uma linha por mascote, com a taxa e a barra.** E a taxa por nivel que
    separa *"duro demais"* de *"banal"* — dois motivos de descarte diferentes,
    que um numero unico esconderia.
    """
    if not item.medicoes:
        return (
            '<p class="vazio">Sem medicao da regua. ⛔ Aprovar as cegas: o '
            "job nao mediu este candidato.</p>"
        )
    partes = [
        '<table class="regua"><tr><th>mascote</th><th>resolveu</th>'
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


def _fita(item: DesafioNoPainel) -> str:
    """A solucao de referencia DESENHADA, um quadro por lance.

    ⚠️ **E o que torna a curadoria possivel sem jogar** (pedido do dono,
    11/09/2026): *"olhando so o JSON dos lances fica muito dificil para mim
    visualizar isso"*. O JSON continua ali embaixo, dobrado, para quando a
    duvida for sobre o dado e nao sobre a partida.

    ⛔ **Quando nao da para montar a sequencia, diz-se isso** — nada de mostrar
    meia solucao. Desafio gerado antes de 11/09/2026 nao tem as posicoes
    gravadas, e o recado manda regerar em vez de deixar o dono concluindo que o
    painel quebrou.
    """
    quadros = desenho.fita_da_solucao(
        item.co_formato_posicao, item.js_posicao_inicial, item.js_solucao
    )
    if not quadros:
        return (
            '<p class="vazio">Sem sequencia desenhavel. ⚠️ Desafios gerados '
            "antes de 11/09/2026 nao trazem a posicao de cada lance; rode o job "
            "de novo para ve-la.</p>"
        )

    partes = ['<div class="fita">']
    for quadro in quadros:
        classe = "quadro chave" if quadro["chave"] else "quadro"
        if quadro["n"] == 0:
            legenda = "inicio"
        else:
            # ⚠️ Quem jogou aquele lance, na mesma regra de cor do aplicativo:
            # jogador 1 e azul, jogador 2 e vermelho. Aqui vai o nome, porque o
            # que o dono precisa saber e se o lance foi DELE ou do adversario.
            de_quem = "voce" if quadro["jogador"] == -1 else "adversario"
            legenda = f"{quadro['n']}. {quadro['titulo']} ({de_quem})"
        partes.append(
            f'<figure class="{classe}">{quadro["svg"]}'
            f"<figcaption>{_txt(legenda)}</figcaption></figure>"
        )
    partes.append("</div>")
    return "".join(partes)


def _acoes(item: DesafioNoPainel, *, dt_sugerida: date) -> str:
    """Os formularios de aprovar, descartar e agendar.

    ⚠️ **O formulario de agendar aparece so no aprovado**, espelhando a regra de
    `servico.py`. ⛔ Isso e espelho, e nao a regra: quem recusa um candidato
    agendado e o servico, porque um `<form>` ausente nao impede um `curl`.
    """
    id_txt = _txt(item.id_desafio)
    partes: list[str] = []

    if item.co_curadoria != "aprovado":
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/aprovar">'
            f'<input type="hidden" name="id_desafio" value="{id_txt}">'
            '<button class="principal" type="submit">Aprovar</button>'
            "</form>"
        )
    else:
        valor_dia = _txt(item.dt_dia.isoformat() if item.dt_dia else dt_sugerida)
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/agendar">'
            f'<input type="hidden" name="id_desafio" value="{id_txt}">'
            f'<input type="date" name="dt_dia" value="{valor_dia}" required>'
            "<button type=\"submit\">"
            + ("Trocar a data" if item.dt_dia else "Agendar")
            + "</button></form>"
        )
        if item.dt_dia:
            partes.append(
                f'<form class="acoes" method="post" action="{BASE}/desagendar">'
                f'<input type="hidden" name="id_desafio" value="{id_txt}">'
                '<button type="submit">Tirar do calendario</button>'
                "</form>"
            )

    if item.co_curadoria != "descartado":
        partes.append(
            f'<form class="acoes" method="post" action="{BASE}/descartar">'
            f'<input type="hidden" name="id_desafio" value="{id_txt}">'
            '<input type="text" name="motivo" required maxlength="500" '
            'placeholder="por que este nao serve (obrigatorio)" size="38">'
            '<button class="perigo" type="submit">Descartar</button>'
            "</form>"
        )
    return "".join(partes)


def _cartao(item: DesafioNoPainel, *, dt_sugerida: date) -> str:
    """Um desafio da fila, com as cinco informacoes que RF-DES-012b exige."""
    etiquetas = [
        f'<span class="etiqueta {_txt(item.co_curadoria)}">'
        f"{_txt(item.co_curadoria)}</span>"
    ]
    if item.ic_reprise:
        etiquetas.append('<span class="etiqueta reprise">reprise</span>')
    if item.dt_dia:
        etiquetas.append(
            f'<span class="etiqueta">{_txt(item.dt_dia.isoformat())}</span>'
        )
    else:
        etiquetas.append('<span class="etiqueta">sem data</span>')

    modalidade = f" &middot; {_txt(item.co_modalidade)}" if item.co_modalidade else ""

    return (
        '<article class="card">'
        f'<div class="desenho">'
        f"{desenho.posicao(item.co_formato_posicao, item.js_posicao_inicial)}"
        "</div>"
        '<div class="corpo">'
        f"<h3>{_txt(item.no_tipo_desafio)} "
        f"<small>({_txt(item.co_jogo)}{modalidade})</small></h3>"
        f"<div>{''.join(etiquetas)}</div>"
        '<dl class="dados">'
        f"<dt>objetivo</dt><dd>{_txt(item.co_chave_objetivo)} "
        f"{_txt(item.js_objetivo)}</dd>"
        f"<dt>adversario</dt><dd>{_txt(_rotulo_personagem(item.co_personagem))} "
        f"&middot; semente {_txt(item.nu_semente)}</dd>"
        f"<dt>solucao</dt><dd>{item.nu_lances_solucao} lance(s)</dd>"
        f"<dt>gerado em</dt><dd>{_txt(item.dh_geracao)}</dd>"
        + (
            f"<dt>descarte</dt><dd>{_txt(item.de_motivo_descarte)}</dd>"
            if item.de_motivo_descarte
            else ""
        )
        + "</dl>"
        + _regua(item)
        + "<details open><summary>a solucao de referencia, lance a lance"
        "</summary>" + _fita(item) + "</details>"
        + "<details><summary>o gabarito em JSON</summary>"
        f"<pre>{_txt(item.js_solucao)}</pre></details>"
        + _acoes(item, dt_sugerida=dt_sugerida)
        + "</div></article>"
    )


def render(
    *,
    fila: Iterable[DesafioNoPainel],
    estado_da_fila: EstadoDaFila,
    contagem: ContagemDeAuditoria,
    divergencias: Iterable[Divergencia],
    dt_hoje: date,
    recado: Optional[str] = None,
    recado_e_erro: bool = False,
) -> str:
    """A pagina inteira.

    Args:
        fila: os desafios a curar.
        estado_da_fila: a folga da fila (T040).
        contagem: as resolucoes por estado de auditoria (T040).
        divergencias: as linhas divergentes (T040).
        dt_hoje: o dia corrente em UTC — vira a data sugerida nos formularios.
        recado: a mensagem do que acabou de acontecer, se houve acao.
        recado_e_erro: pinta o recado de vermelho.

    Returns:
        O HTML completo, pronto para uma `HTMLResponse`.
    """
    itens = list(fila)
    # A data sugerida e o primeiro buraco da fila, e nao "amanha": e o dia que
    # de fato precisa de dono, e digitar a data certa e o passo mais facil de
    # errar numa tela cheia de linhas parecidas.
    dt_sugerida = estado_da_fila.buracos[0] if estado_da_fila.buracos else dt_hoje

    corpo_fila = (
        "".join(_cartao(item, dt_sugerida=dt_sugerida) for item in itens)
        if itens
        else '<p class="vazio">Nenhum candidato na fila. Se a cobertura acima '
        "estiver curta, o job precisa rodar.</p>"
    )

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
<title>Curadoria do Desafio do Dia</title>
<style>{_ESTILO}</style>
</head>
<body>
<header>
  <h1>Curadoria do Desafio do Dia</h1>
  <p>Nada vai ao ar sem passar por aqui. Hoje e {_txt(dt_hoje.isoformat())} (UTC).</p>
</header>
<main>
  {bloco_recado}
  <section>
    <h2>Vigilancia &mdash; a fila</h2>
    {_secao_fila(estado_da_fila)}
  </section>
  <section>
    <h2>Vigilancia &mdash; divergencias de julgamento</h2>
    {_secao_divergencias(contagem, divergencias)}
  </section>
  <section>
    <h2>A fila de curadoria ({len(itens)})</h2>
    {corpo_fila}
  </section>
</main>
</body>
</html>"""
