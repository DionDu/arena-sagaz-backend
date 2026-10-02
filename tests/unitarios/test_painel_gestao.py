"""🔒 O PAINEL DE GESTAO do Desafio do Dia (02/10/2026).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O dono pediu, junto com a pre-aprovacao dos desafios, que a curadoria virasse
um painel de GESTAO: calendario com o status de cada dia, clique no dia para ver
o desafio, datas no formato brasileiro, o tracejado do lance e as pecas
condenadas nas damas, as estatisticas do dia jogado (engajamento, dificuldade,
tentativas), o quadro com o raio-x de cada pessoa, e mais opcoes de geracao.

`test_painel_curadoria.py` continua travando o que ja travava (seguranca,
regras da curadoria, a frase, o desenho do Pontinhos). Este arquivo trava o que
nasceu em 02/10/2026:

  1. as datas brasileiras;
  2. o calendario (cores, horizonte, quais meses aparecem);
  3. o lance das damas desenhado (trajeto, condenadas, ordem);
  4. a partida de uma pessoa (o raio-x);
  5. o dia jogado na tela;
  6. ⛔ a guarda de dia jogado (descartar, mover, tirar do calendario);
  7. as rotas novas.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.configuracao import configuracoes
from api.desafios.painel import datas, desenho, execucao_do_job, pagina
from api.desafios.painel.estatisticas import (
    FatiaDeTentativas,
    LinhaDoQuadro,
    QuemNaoResolveu,
    RaioX,
    ResumoDoDia,
    UsoDePoder,
)
from api.desafios.painel.repositorio import (
    DesafioNoPainel,
    DiaNoCalendario,
    MedicaoNoPainel,
)
from api.desafios.painel.servico import ServicoCuradoria
from api.desafios.painel.vigilancia import ContagemDeAuditoria, EstadoDaFila
from api.main import app
from api.nucleo.banco import obter_sessao
from api.nucleo.excecoes import ErroNegocio
from job.gravacao import DIAS_MAXIMOS
from tests.unitarios.fakes_desafio import FakeSessaoSQL

HOJE = date(2026, 10, 2)
SEGREDO = "segredo-de-teste-da-gestao"


def _dia_no_calendario(
    dia: date, co_curadoria: str = "aprovado", **campos
) -> DiaNoCalendario:
    """Um dia do calendario com o minimo preenchido."""
    base = dict(
        dt_dia=dia,
        id_desafio=uuid4(),
        co_curadoria=co_curadoria,
        co_jogo="damas",
        co_modalidade="anglo",
        co_personagem="tex",
        no_tipo_desafio="Coroar",
        ic_reprise=False,
    )
    base.update(campos)
    return DiaNoCalendario(**base)


def _desafio(dt_dia: date | None = HOJE, **campos) -> DesafioNoPainel:
    """Um desafio de damas com gabarito de dois lances e posicoes gravadas."""
    base = dict(
        id_desafio=uuid4(),
        co_jogo="damas",
        co_modalidade="brasileira",
        co_variante="padrao",
        co_formato_posicao="fen",
        js_posicao_inicial={"fen": "W:W22,26:B14,18", "vez_de": 1},
        co_tipo_desafio="damas_coroar",
        no_tipo_desafio="Coroar",
        co_chave_objetivo="desafioObjetivoChaveQueNaoExiste",
        js_objetivo={"n": 1},
        js_solucao={
            "lances": [{"n": 1, "jogador": 1, "lance": "22x15"}],
            "posicoes": [{"n": 1, "fen": "B:W15,26:B14"}],
            "lance_chave": 1,
        },
        nu_lances_solucao=1,
        co_personagem="pita",
        nu_semente=42,
        co_curadoria="aprovado",
        de_motivo_descarte=None,
        ic_reprise=False,
        id_desafio_origem=None,
        dh_geracao=datetime(2026, 9, 29, 15, 52, tzinfo=timezone.utc),
        dt_dia=dt_dia,
        medicoes=(MedicaoNoPainel("cacau", 20, 14, "p", "m"),),
        id_desafio_dia=uuid4() if dt_dia else None,
    )
    base.update(campos)
    return DesafioNoPainel(**base)


# ═══════════════════════════════════════════════════════════════════════════
# 1. As datas brasileiras
# ═══════════════════════════════════════════════════════════════════════════


def test_a_data_sai_no_formato_BRASILEIRO() -> None:
    """🔒 *"As datas e interessante no formato brasileiro."*"""
    assert datas.data_br(date(2026, 10, 4)) == "04/10/2026"
    assert datas.data_curta_br(date(2026, 10, 4)) == "04/10"
    assert datas.dia_por_extenso(date(2026, 10, 2)) == "sexta-feira, 02/10/2026"
    assert datas.data_br(None) == ""


def test_o_horario_sai_em_BRASILIA_e_nao_em_UTC() -> None:
    """🔒 ⚠️ 01:42 UTC do dia 1 e 22:42 do dia 30 em Brasilia - o dia muda junto."""
    momento = datetime(2026, 10, 1, 1, 42, tzinfo=timezone.utc)
    assert datas.momento_br(momento) == "30/09/2026 22:42"


def test_a_duracao_e_legivel() -> None:
    """🔒 Milissegundos crus nao sao relatorio."""
    assert datas.duracao_br(8_000) == "8s"
    assert datas.duracao_br(95_000) == "1min35s"
    assert datas.duracao_br(3_725_000) == "1h02min"
    assert datas.duracao_br(None) == ""


def test_a_URL_aceita_ISO_e_brasileiro_e_ignora_o_torto() -> None:
    """🔒 Link torto cai no dia padrao, e nao num erro."""
    assert datas.ler_data("2026-10-04") == date(2026, 10, 4)
    assert datas.ler_data("04/10/2026") == date(2026, 10, 4)
    assert datas.ler_data("ontem") is None
    assert datas.ler_data(None) is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. O calendario
# ═══════════════════════════════════════════════════════════════════════════


def test_as_cores_de_cada_dia() -> None:
    """🔒 Aprovado verde; vazio ou descartado dentro da fila, vermelho."""
    horizonte = HOJE + timedelta(days=6)
    status = lambda dia, ocupante=None: pagina.status_do_dia(  # noqa: E731
        dia, ocupante, dt_hoje=HOJE, horizonte=horizonte
    )
    assert status(HOJE, _dia_no_calendario(HOJE)) == "aprovado"
    assert status(HOJE, _dia_no_calendario(HOJE, "candidato")) == "candidato"
    assert status(HOJE, _dia_no_calendario(HOJE, "descartado")) == "descartado"
    assert status(HOJE + timedelta(days=3)) == "buraco"
    assert status(HOJE - timedelta(days=1)) == "passado"
    assert status(HOJE + timedelta(days=20)) == "livre"


def test_o_horizonte_cobre_a_semana_E_o_fim_da_fila() -> None:
    """🔒 ⚠️ Vazio no meio da fila e buraco mesmo a 20 dias; depois do fim, nao."""
    assert pagina.horizonte_da_fila(HOJE, []) == HOJE + timedelta(days=6)
    longe = HOJE + timedelta(days=20)
    assert pagina.horizonte_da_fila(HOJE, [_dia_no_calendario(longe)]) == longe


def test_o_mes_anterior_e_o_seguinte_SO_quando_tem_desafio() -> None:
    """🔒 *"Deveria mostrar o mes anterior e o proximo tambem, caso tenham algum
    desafio ja gerado."*"""
    assert pagina.meses_a_mostrar(HOJE, []) == [(2026, 10)]
    calendario = [
        _dia_no_calendario(date(2026, 9, 29)),
        _dia_no_calendario(date(2026, 11, 3)),
    ]
    assert pagina.meses_a_mostrar(HOJE, calendario) == [
        (2026, 9),
        (2026, 10),
        (2026, 11),
    ]


def test_a_virada_de_ANO_no_calendario() -> None:
    """🔒 Janeiro tem dezembro do ano anterior como vizinho."""
    calendario = [_dia_no_calendario(date(2025, 12, 31))]
    assert pagina.meses_a_mostrar(date(2026, 1, 5), calendario) == [
        (2025, 12),
        (2026, 1),
    ]


def test_cada_dia_e_um_LINK_que_abre_o_dia() -> None:
    """🔒 O clique funciona sem JavaScript: o dia e um link com a data ISO."""
    html = pagina.render(
        dt_hoje=HOJE,
        detalhe=pagina.DetalheDoDia(dt_dia=HOJE, desafio=None),
        calendario=[_dia_no_calendario(HOJE, qt_pessoas=3, qt_resolveram=2)],
        estado_da_fila=EstadoDaFila(1, 0, ()),
        contagem=ContagemDeAuditoria(),
        divergencias=[],
    )
    assert f'href="{pagina.BASE}?dia=2026-10-02"' in html
    assert 'data-dia="2026-10-02"' in html
    # O dia mostra o jogo, o adversario e o "resolveram/tentaram".
    celula = re.search(r'<a class="dia aprovado hoje[^"]*"[^>]*>(.*?)</a>', html)
    assert celula is not None
    assert "Dama" in celula.group(1) and "Tex" in celula.group(1)
    assert "2/3" in celula.group(1)
    # O mes por extenso, com maiuscula SO na primeira letra.
    assert "Outubro de 2026" in html


# ═══════════════════════════════════════════════════════════════════════════
# 3. O lance das damas desenhado
# ═══════════════════════════════════════════════════════════════════════════

#: O lance real do `des` em 01/10/2026: uma captura tripla em linha reta.
FEN_ANTES = "W:W21,25,26,27,28,29,30,31,32:B1,2,4,5,6,8,10,11,16,23"
FEN_DEPOIS = "B:WK3,21,25,27,28,29,30,31,32:B1,2,4,5,6,10,11"


def test_as_condenadas_saem_da_DIFERENCA_entre_as_FENs() -> None:
    """🔒 ⛔ Nenhuma regra de damas: duas fotografias comparadas."""
    assert desenho.capturadas_no_lance(FEN_ANTES, FEN_DEPOIS) == [8, 16, 23]


def test_a_ORDEM_das_capturas_segue_o_trajeto() -> None:
    """🔒 A peca do primeiro trecho e a 1, como o app numera a condenada."""
    ordem = desenho.ordem_das_capturas((26, 19, 12, 3), [8, 16, 23])
    assert ordem == {23: 1, 16: 2, 8: 3}


def test_sem_as_casas_do_meio_a_condenada_fica_SEM_numero() -> None:
    """🔒 ⚠️ Notacao so com origem e destino: marca, mas nao inventa ordem."""
    assert desenho.ordem_das_capturas((26, 3), [8, 16, 23]) == {
        8: None,
        16: None,
        23: None,
    }


def test_o_tabuleiro_desenha_o_TRACEJADO_e_os_SELOS_por_cima() -> None:
    """🔒 O caminho tracejado existe, e os numeros da ordem vem DEPOIS dele.

    ⚠️ Visto no painel em 02/10/2026: o tracejado atravessava a diagonal das
    condenadas e cobria os selos 1 e 2 do `26x19x12x3`.
    """
    svg = desenho.damas(
        {"fen": FEN_ANTES},
        trajeto=(26, 19, 12, 3),
        condenadas=desenho.ordem_das_capturas((26, 19, 12, 3), [8, 16, 23]),
    )
    assert 'stroke-dasharray="6 4"' in svg
    selos = re.findall(r'font-weight="700" fill="#FBF8F1">(\d)<', svg)
    assert sorted(selos) == ["1", "2", "3"]
    ultimo_caminho = svg.rfind("<polyline")
    assert all(
        svg.find(f'fill="#FBF8F1">{n}<') > ultimo_caminho for n in ("1", "2", "3")
    ), "um selo foi desenhado por baixo do tracejado"


def test_a_fita_do_gabarito_desenha_o_lance_sobre_a_posicao_de_ANTES() -> None:
    """🔒 O quadro do lance 1 e a posicao publicada com o trajeto por cima."""
    quadros = desenho.fita_da_solucao(
        "fen",
        {"fen": FEN_ANTES, "vez_de": 1},
        {
            "lances": [{"n": 1, "jogador": 1, "lance": "26x19x12x3"}],
            "posicoes": [{"n": 1, "fen": FEN_DEPOIS}],
            "lance_chave": 1,
        },
    )
    assert [q["tipo"] for q in quadros] == ["lance", "final"]
    assert "stroke-dasharray" in quadros[0]["svg"]
    assert quadros[0]["chave"] and quadros[0]["de_quem"] == "voce"


# ═══════════════════════════════════════════════════════════════════════════
# 4. A partida de uma pessoa (o raio-x)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_partida_traduz_o_LOG_para_o_vocabulario_do_gabarito() -> None:
    """🔒 O log grava o jogador como 1/2 e a FEN de ANTES de cada lance.

    ⚠️ O "depois" do lance k e o "antes" do k+1; o ultimo lance nao tem, e por
    isso sai sem condenadas e sem quadro final - o que nao se sabe nao se desenha.
    """
    log = [
        {"nu_ordem": 1, "nu_jogador": 1, "co_lance": "26x19x12x3", "co_fen_antes": FEN_ANTES},
        {"nu_ordem": 2, "nu_jogador": 2, "co_lance": "2-7", "co_fen_antes": FEN_DEPOIS},
    ]
    quadros = desenho.fita_da_partida(
        "fen", {"fen": FEN_ANTES, "vez_de": 1}, log, nu_lance_cumpre_desafio=1
    )
    assert [q["tipo"] for q in quadros] == ["lance", "lance"]
    assert [q["de_quem"] for q in quadros] == ["jogador", "CPU"]
    assert [q["chave"] for q in quadros] == [True, False]
    assert 'fill="#FBF8F1">1<' in quadros[0]["svg"]  # as condenadas do 1o lance
    assert 'fill="#FBF8F1">1<' not in quadros[1]["svg"]  # o ultimo, sem "depois"


def test_a_partida_do_PONTINHOS_parte_da_posicao_publicada() -> None:
    """🔒 O lance 1 do log e o primeiro DEPOIS da posicao publicada."""
    posicao = {"lances": [{"n": 1, "lance": "H_0_1", "jogador": 1}], "vez_de": 1}
    log = [{"nu_ordem": 1, "nu_jogador": 1, "co_lance": "V_1_0", "co_fen_antes": None}]
    quadros = desenho.fita_da_partida("sequencia_lances", posicao, log)
    assert [q["tipo"] for q in quadros] == ["inicio", "lance"]
    assert quadros[1]["jogador"] == 1


def test_o_raio_x_mostra_o_XP_GRAVADO_e_a_partida() -> None:
    """🔒 ⚠️ O extrato e o da tabela: o painel nao recalcula XP."""
    raio = RaioX(
        id_tentativa=uuid4(),
        id_usuario=uuid4(),
        co_usuario="abc123",
        no_exibicao="<b>Fulana</b>",
        nu_sequencia=2,
        ic_resolveu=True,
        nu_tempo_ms=31_000,
        dh_inicio=datetime(2026, 10, 2, 12, 45, tzinfo=timezone.utc),
        co_formato_posicao="sequencia_lances",
        js_posicao_inicial={"lances": [{"n": 1, "lance": "H_0_1", "jogador": 1}], "vez_de": 1},
        id_resolucao=uuid4(),
        nu_xp=29,
        nu_lance_cumpre_desafio=1,
        co_auditoria="pendente",
        lances=({"nu_ordem": 1, "nu_jogador": 1, "co_lance": "V_1_0"},),
        extrato=({"co_tipo_xp": "base", "vr_xp": 18},),
        poderes=({"co_tipo_poder": "dica", "nu_grau": 1, "dh_consumo": None},),
    )
    html = pagina.render_raio_x(raio)
    assert "&lt;b&gt;Fulana&lt;/b&gt;" in html, "nome de pessoa e texto livre: escapa"
    assert "2&ordf; tentativa" in html and "29 XP" in html
    assert "De onde veio o XP" in html and "<b>18</b>" in html
    assert "dica (grau 1" in html
    assert "<svg" in html
    assert "Tentativa nao encontrada" in pagina.render_raio_x(None)


# ═══════════════════════════════════════════════════════════════════════════
# 5. O dia jogado na tela
# ═══════════════════════════════════════════════════════════════════════════


def _detalhe_jogado() -> pagina.DetalheDoDia:
    """Hoje, com tres pessoas: duas resolveram (uma oculta), uma nao."""
    item = _desafio()
    linha = LinhaDoQuadro(
        posicao=1,
        id_resolucao=uuid4(),
        id_tentativa=uuid4(),
        id_usuario=uuid4(),
        co_usuario="u1",
        no_exibicao="Ana",
        nu_xp=30,
        nu_tempo_ms=70_000,
        dh_resolucao=datetime(2026, 10, 2, 1, 0, tzinfo=timezone.utc),
        co_auditoria="confere",
        nu_sequencia=1,
        qt_tentativas=1,
        qt_dicas=0,
        qt_reacoes=2,
        ic_publico=True,
    )
    return pagina.DetalheDoDia(
        dt_dia=HOJE,
        desafio=item,
        resumo=ResumoDoDia(
            qt_tentativas=5,
            qt_pessoas=3,
            qt_resolveram=2,
            md_tempo_resolucao_ms=70_000,
            md_tentativa_que_resolveu=1.5,
            xp_medio=25.0,
            xp_maximo=30,
            xp_minimo=20,
            qt_ativos_no_dia=12,
            distribuicao=(
                FatiaDeTentativas(1, True, 1),
                FatiaDeTentativas(3, False, 1),
            ),
            poderes=(UsoDePoder("dica", 2, 1),),
            auditoria={"confere": 2},
        ),
        quadro=(linha, replace(linha, posicao=2, no_exibicao="Bia", ic_publico=False)),
        nao_resolveram=(
            QuemNaoResolveu(uuid4(), "u3", "Caio", 3, 90_000, 2, uuid4()),
        ),
    )


def test_o_dia_jogado_mostra_ENGAJAMENTO_com_o_denominador() -> None:
    """🔒 ⚠️ Taxa sem denominador nao e relatorio: 3 de 12, 2 de 3."""
    html = pagina.render_detalhe(_detalhe_jogado(), dt_hoje=HOJE, dt_sugerida=HOJE)
    assert "Como foi o dia" in html
    assert "25% de 12 que jogaram algo no dia" in html
    assert "2 de 3" in html
    # A regua previa 70% (14/20 da Cacau): a comparacao com a gente esta ali.
    assert "a regua previa 70%" in html
    assert "1min10s" in html


def test_o_quadro_tem_TODO_mundo_e_marca_quem_esta_oculto_no_app() -> None:
    """🔒 O painel ve todos; o app nao. A marca evita confundir os dois."""
    html = pagina.render_detalhe(_detalhe_jogado(), dt_hoje=HOJE, dt_sugerida=HOJE)
    assert "Ana" in html and "Bia" in html
    assert html.count("oculto no app") == 1
    assert "Tentaram e nao resolveram" in html and "Caio" in html
    # Tres gavetas de raio-x: duas do quadro e a do Caio.
    assert html.count('class="raio-x"') == 3


def test_dia_JOGADO_nao_oferece_descartar_nem_mover() -> None:
    """🔒 ⛔ Espelho de `_exigir_dia_nao_jogado`: hoje com tentativa conta."""
    html = pagina.render_detalhe(_detalhe_jogado(), dt_hoje=HOJE, dt_sugerida=HOJE)
    assert f"{pagina.BASE}/descartar" not in html
    assert f"{pagina.BASE}/agendar" not in html
    assert "Dia ja jogado nao se descarta" in html


def test_dia_AGENDADO_oferece_descartar_e_volta_para_o_mesmo_dia() -> None:
    """🔒 A acao leva o dia junto, para a pagina voltar a ele (`voltar`)."""
    amanha = HOJE + timedelta(days=1)
    html = pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=amanha, desafio=_desafio(amanha)),
        dt_hoje=HOJE,
        dt_sugerida=HOJE,
    )
    assert f"{pagina.BASE}/descartar" in html
    assert 'name="voltar" value="2026-10-03"' in html


def test_dia_VAZIO_oferece_a_reserva_para_agendar_ali() -> None:
    """🔒 O buraco diz que a geracao o tapa - ou deixa agendar agora."""
    from api.desafios.painel.repositorio import DesafioSemDia

    reserva = DesafioSemDia(
        id_desafio=uuid4(),
        co_jogo="pontinhos",
        co_modalidade=None,
        co_personagem="cacau",
        no_tipo_desafio="Paciencia",
        co_curadoria="aprovado",
        de_motivo_descarte=None,
        dh_geracao=datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    html = pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=HOJE, desafio=None, reserva=(reserva,)),
        dt_hoje=HOJE,
        dt_sugerida=HOJE,
    )
    assert "Dia vazio" in html
    assert "Agendar em 02/10" in html


def test_o_script_NAO_faz_acao_de_escrita() -> None:
    """🔒 ⛔ JS leve: so le. Escrita continua sendo formulario (ver o topo de
    `pagina.py`) - o estado "a tela mudou e o banco nao" continua sem existir."""
    assert "POST" not in pagina._SCRIPT.upper().replace("POSTURA", "")
    assert "method" not in pagina._SCRIPT


# ═══════════════════════════════════════════════════════════════════════════
# 6. ⛔ A guarda de dia jogado
# ═══════════════════════════════════════════════════════════════════════════


class RepoDaGuarda:
    """Um repositorio de mentira com UM desafio, num dia e com N tentativas."""

    def __init__(self, dt_dia: date | None, qt_tentativas: int = 0) -> None:
        self.dt_dia = dt_dia
        self.qt_tentativas = qt_tentativas
        self.mexeu: list[str] = []
        self.alvo = _desafio(dt_dia)

    async def situacao_no_calendario(self, id_desafio: UUID):
        return None if self.dt_dia is None else (self.dt_dia, self.qt_tentativas)

    async def fila(self, *, estados=(), limite=60):
        return [self.alvo]

    async def descartar(self, id_desafio, *, de_motivo):
        self.mexeu.append("descartar")
        return True

    async def desagendar(self, id_desafio):
        self.mexeu.append("desagendar")
        return True

    async def agendar(self, id_desafio, *, dt_dia):
        self.mexeu.append("agendar")
        return True

    async def aprovar_candidatos(self):
        return 5

    async def confirmar(self):
        self.mexeu.append("commit")


@pytest.mark.parametrize(
    "dt_dia, qt_tentativas",
    [(HOJE - timedelta(days=1), 0), (HOJE, 1)],
    ids=["dia que passou", "hoje com tentativa"],
)
@pytest.mark.asyncio
async def test_dia_JOGADO_recusa_as_tres_acoes(dt_dia: date, qt_tentativas: int) -> None:
    """🔒 ⛔ Descartar e tirar do calendario apagariam o vinculo (o banco recusaria
    com 500); TROCAR A DATA e pior - o banco aceita, e as tentativas de quem
    jogou mudariam de dia sem nada acusar."""
    repo = RepoDaGuarda(dt_dia, qt_tentativas)
    servico = ServicoCuradoria(repo)  # type: ignore[arg-type]
    id_desafio = repo.alvo.id_desafio

    with pytest.raises(ErroNegocio) as erro:
        await servico.descartar(id_desafio, motivo="ruim", dt_hoje=HOJE)
    assert erro.value.codigo == "dia_ja_jogado"
    with pytest.raises(ErroNegocio):
        await servico.agendar(id_desafio, dt_dia=HOJE + timedelta(days=3), dt_hoje=HOJE)
    with pytest.raises(ErroNegocio):
        await servico.desagendar(id_desafio, dt_hoje=HOJE)

    assert repo.mexeu == [], "a recusa tem de vir ANTES de qualquer escrita"


@pytest.mark.asyncio
async def test_dia_AGENDADO_sem_tentativa_descarta_normalmente() -> None:
    """🔒 A guarda nao pode travar o ato de curadoria do dia a dia."""
    repo = RepoDaGuarda(HOJE + timedelta(days=2))
    servico = ServicoCuradoria(repo)  # type: ignore[arg-type]
    resultado = await servico.descartar(repo.alvo.id_desafio, motivo="facil", dt_hoje=HOJE)
    assert resultado.mudou
    assert repo.mexeu == ["descartar", "desagendar", "commit"]


@pytest.mark.asyncio
async def test_aprovar_os_candidatos_ANTIGOS_de_uma_vez() -> None:
    """🔒 A ponte da transicao: os candidatos de antes de 02/10/2026."""
    repo = RepoDaGuarda(None)
    resultado = await ServicoCuradoria(repo).aprovar_candidatos()  # type: ignore[arg-type]
    assert resultado.mensagem == "5 candidato(s) aprovado(s)."
    assert repo.mexeu == ["commit"]


# ═══════════════════════════════════════════════════════════════════════════
# 7. As rotas novas
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cliente(monkeypatch):
    """Um `TestClient` com o painel habilitado e um banco que responde vazio."""
    monkeypatch.setattr(configuracoes, "PAINEL_CURADORIA_TOKEN", SEGREDO)
    app.dependency_overrides[obter_sessao] = lambda: FakeSessaoSQL(
        respostas={"WHERE d.co_curadoria = 'aprovado'": [{"qt": 0}]}
    )
    c = TestClient(app, follow_redirects=False)
    yield c
    app.dependency_overrides.clear()


def test_o_FRAGMENTO_traz_so_a_area_do_dia(cliente) -> None:
    """🔒 O script troca so o miolo: nada de `<html>` dentro de `<main>`."""
    resposta = cliente.get(
        f"{pagina.BASE}/fragmento?dia=04/10/2026", headers={"X-Admin-Token": SEGREDO}
    )
    assert resposta.status_code == 200
    assert "<html" not in resposta.text
    assert "Domingo, 04/10/2026" in resposta.text
    assert resposta.headers["cache-control"] == "no-store"


def test_o_fragmento_exige_o_TOKEN(cliente) -> None:
    """🔒 ⛔ Rota nova, mesma porta: o gabarito nao vaza pelo fragmento."""
    assert cliente.get(f"{pagina.BASE}/fragmento").status_code == 401
    assert cliente.get(f"{pagina.BASE}/geracao").status_code == 401
    assert cliente.get(f"{pagina.BASE}/raio-x/{uuid4()}").status_code == 401


def test_raio_x_com_id_TORTO_e_pagina_e_nao_500(cliente) -> None:
    """🔒 O id vem da URL, isto e, de fora."""
    resposta = cliente.get(
        f"{pagina.BASE}/raio-x/nao-e-uuid", headers={"X-Admin-Token": SEGREDO}
    )
    assert resposta.status_code == 200
    assert "Tentativa nao encontrada" in resposta.text


def test_a_GERACAO_responde_em_JSON(cliente) -> None:
    """🔒 O script pergunta isto enquanto a geracao roda."""
    resposta = cliente.get(f"{pagina.BASE}/geracao", headers={"X-Admin-Token": SEGREDO})
    assert resposta.status_code == 200
    assert set(resposta.json()) >= {"rodando", "resumo"}


def test_a_acao_VOLTA_para_o_dia_de_onde_veio(cliente) -> None:
    """🔒 Sem isso, cada descarte jogaria o dono de volta a "hoje"."""
    resposta = cliente.post(
        f"{pagina.BASE}/descartar",
        data={"id_desafio": "torto", "motivo": "x", "voltar": "2026-10-05"},
        headers={"X-Admin-Token": SEGREDO},
    )
    assert resposta.status_code == 303
    assert "dia=2026-10-05" in resposta.headers["location"]
    assert "erro=1" in resposta.headers["location"]


def test_o_campo_de_volta_e_CONFERIDO_antes_de_entrar_na_URL(cliente) -> None:
    """🔒 ⚠️ Vem do formulario: um `voltar` torto nao vira pedaco de URL."""
    resposta = cliente.post(
        f"{pagina.BASE}/descartar",
        data={"id_desafio": "torto", "voltar": "x&token=1", "voltar_desafio": "y"},
        headers={"X-Admin-Token": SEGREDO},
    )
    assert "token" not in resposta.headers["location"]
    assert "dia=" not in resposta.headers["location"]


def test_as_opcoes_de_geracao_incluem_21_e_28_DENTRO_do_teto_do_job() -> None:
    """🔒 *"Quero mais opcoes de gerar desafios alem dos 14 dias (ex: 21, 28)."*

    ⚠️ E nenhuma passa do `DIAS_MAXIMOS` do job: uma opcao que o job recusa
    seria um botao que gasta um clique para nao fazer nada.
    """
    assert execucao_do_job.DIAS_OFERECIDOS == (7, 14, 21, 28)
    assert max(execucao_do_job.DIAS_OFERECIDOS) <= DIAS_MAXIMOS
