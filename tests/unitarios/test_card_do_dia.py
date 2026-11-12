"""O card do dia (`/v1/card-do-dia`): a agenda, os números do Magno e a rota.

O que estes casos protegem:

- o **dia de publicação** é o dia de Brasília em que o desafio começou (o
  desafio de quinta UTC é o post de quarta às 21h);
- os **quatro dias** do dono (quarta, sexta, sábado, domingo), o pedido de ajuda
  como 2º story do domingo e o Magno numa quarta a cada duas semanas;
- a **rotação** nunca repete layout nem papel em dois posts seguidos;
- os **números do Magno** contam só o que conta (vs CPU, sagaz, concluída) e
  em dias de Brasília; e o card dele **não sai** quando os números não impressionam;
- a **rota** não entrega gabarito, não aceita cache e não depende de login.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.card_do_dia import agenda as regras
from api.card_do_dia import magno
from api.card_do_dia import rotas as rotas_card
from api.card_do_dia.agenda import NumerosDoMagno
from api.main import app

# A linha de desafio de exemplo dos testes do `/hoje` (sem `js_solucao`, como
# as consultas de verdade a devolvem). Importada para não haver duas cópias.
from tests.unitarios.test_rotas_desafio_publicado import _linha

QUARTA = date(2026, 11, 18)  # a primeira quarta do Magno
QUINTA, SEXTA, SABADO, DOMINGO = (QUARTA + timedelta(days=i) for i in (1, 2, 3, 4))


# ── O calendário ─────────────────────────────────────────────────────────────


def test_o_desafio_de_quinta_utc_e_o_post_de_quarta():
    """O desafio de quinta (UTC) começa quarta às 21h de Brasília."""
    assert regras.dia_de_publicacao(QUINTA) == QUARTA


@pytest.mark.parametrize(
    "dia, publica",
    [(QUARTA, True), (QUINTA, False), (SEXTA, True), (SABADO, True), (DOMINGO, True),
     (QUARTA - timedelta(days=1), False), (QUARTA - timedelta(days=2), False)],
    ids=["quarta", "quinta", "sexta", "sabado", "domingo", "terca", "segunda"],
)
def test_os_quatro_dias_do_dono(dia: date, publica: bool):
    assert regras.publica_em(dia) is publica


def test_proxima_publicacao():
    """Nunca o próprio dia; de domingo pula para a quarta seguinte."""
    assert regras.proxima_publicacao(QUARTA) == SEXTA
    assert regras.proxima_publicacao(QUINTA) == SEXTA
    assert regras.proxima_publicacao(DOMINGO) == QUARTA + timedelta(days=7)


def test_o_magno_e_uma_quarta_sim_outra_nao():
    assert regras.e_quarta_do_magno(QUARTA)
    assert not regras.e_quarta_do_magno(QUARTA + timedelta(days=7))
    assert regras.e_quarta_do_magno(QUARTA + timedelta(days=14))
    assert not regras.e_quarta_do_magno(SEXTA)


def test_a_rotacao_nunca_repete_layout_nem_papel_em_posts_seguidos():
    """Dois meses de posts: cada um difere do anterior no layout E no papel."""
    dias = [QUARTA + timedelta(days=i) for i in range(60)]
    posts = [regras.montar_agenda(d).stories[0] for d in dias if regras.publica_em(d)]
    for anterior, atual in zip(posts, posts[1:]):
        assert anterior.layout != atual.layout
        assert anterior.papel != atual.papel


def test_domingo_tem_dois_stories_e_o_segundo_e_o_pedido_de_ajuda():
    plano = regras.montar_agenda(DOMINGO)
    assert [s.card for s in plano.stories] == ["convite", "ajuda"]
    # Os dois stories do domingo em papéis diferentes.
    assert plano.stories[0].papel != plano.stories[1].papel
    assert len(regras.montar_agenda(SABADO).stories) == 1


def test_dia_de_folga_traz_os_stories_mesmo_assim():
    """O botão "ver o card de hoje mesmo assim" precisa de algo para mostrar."""
    plano = regras.montar_agenda(QUINTA)
    assert plano.publica_hoje is False
    assert plano.stories and plano.stories[0].card == "convite"


# ── A escolha do card do Magno ───────────────────────────────────────────────


def _n(jogo=None, dias=0, recorde=0, partidas=0, derrotas=0) -> NumerosDoMagno:
    return NumerosDoMagno(jogo, dias, recorde, partidas, derrotas)


def test_quarta_do_magno_sem_numeros_que_impressionem_vira_convite():
    fracos = [_n(dias=3, partidas=10), _n("damas", dias=5, partidas=20, derrotas=1)]
    plano = regras.montar_agenda(QUARTA, escopos_do_magno=fracos)
    assert plano.magno is None
    assert plano.stories[0].card == "convite"


def test_quarta_do_magno_com_numeros_bons_traz_o_card_d():
    bons = [_n(dias=regras.LIMITE_DIAS_SEM_PERDER, recorde=40)]
    plano = regras.montar_agenda(QUARTA, escopos_do_magno=bons)
    assert plano.stories[0].card == "magno"
    assert plano.magno.variante == "placa"


def test_os_quatro_jogos_juntos_vencem_um_jogo_so():
    """Um jogo pode ter mais dias, mas "nos quatro jogos" é o feito maior."""
    L = regras.LIMITE_DIAS_SEM_PERDER
    escolha = regras.escolher_magno([_n("velha", dias=L + 90), _n(None, dias=L)], ocorrencia=0)
    assert escolha.numeros.jogo is None


def test_entre_jogos_vence_o_maior_numero():
    L = regras.LIMITE_DIAS_SEM_PERDER
    escolha = regras.escolher_magno([_n("velha", dias=L), _n("damas", dias=L + 9)], ocorrencia=0)
    assert escolha.numeros.jogo == "damas"


def test_o_placar_so_vale_sem_nenhuma_derrota():
    P = regras.LIMITE_PARTIDAS_NO_PERIODO
    assert regras.escolher_magno([_n(partidas=P * 10, derrotas=1)], ocorrencia=1) is None
    escolha = regras.escolher_magno([_n(partidas=P, derrotas=0)], ocorrencia=1)
    assert escolha.variante == "placar"


def test_as_variantes_se_alternam_quando_as_duas_valem():
    ambos = [_n(dias=regras.LIMITE_DIAS_SEM_PERDER, partidas=regras.LIMITE_PARTIDAS_NO_PERIODO)]
    assert regras.escolher_magno(ambos, ocorrencia=0).variante == "placa"
    assert regras.escolher_magno(ambos, ocorrencia=1).variante == "placar"


# ── As legendas ──────────────────────────────────────────────────────────────


def test_legendas_seguem_as_regras_do_dono():
    """Sem travessão longo e sem "o app que eu criei" (decisões de 11 e 12/11)."""
    todas = [*regras.LEGENDAS_CONVITE, regras.LEGENDA_AJUDA, *regras.LEGENDAS_MAGNO]
    for legenda in todas:
        assert "—" not in legenda
        assert "que eu criei" not in legenda.lower()
    # As do convite têm as duas lacunas que a página preenche.
    for legenda in regras.LEGENDAS_CONVITE:
        assert "{objetivo}" in legenda and "{jogo}" in legenda


def test_o_link_dos_stories_leva_a_origem_que_o_baixar_aceita():
    from api.site import baixar

    assert regras.LINK_DOS_STORIES.endswith("/baixar?o=story")
    assert "story" in baixar.ORIGENS


# ── Os números do Magno ──────────────────────────────────────────────────────


def _p(jogo: str, dia: date, derrota: bool = False, inicio: date | None = None):
    return magno.PartidaDoMagno(jogo, inicio or dia, dia, derrota)


def test_dias_sem_perder_e_recorde():
    """Primeira partida em 01/09; derrotas em 11/09 e 01/11; publicação em 18/11.

    Intervalos: 10 dias, 51 dias (o recorde) e 17 dias (o atual)."""
    partidas = [
        _p("damas", date(2026, 9, 1)),
        _p("damas", date(2026, 9, 11), derrota=True),
        _p("damas", date(2026, 11, 1), derrota=True),
        _p("damas", date(2026, 11, 10)),
    ]
    escopos, _ = magno.calcular_escopos(partidas, QUARTA)
    damas = next(n for n in escopos if n.jogo == "damas")
    assert damas.dias_sem_perder == 17
    assert damas.recorde_dias == 51


def test_sem_nenhuma_derrota_conta_desde_a_primeira_partida():
    escopos, _ = magno.calcular_escopos([_p("velha", date(2026, 10, 1))], QUARTA)
    velha = next(n for n in escopos if n.jogo == "velha")
    assert velha.dias_sem_perder == (QUARTA - date(2026, 10, 1)).days
    assert velha.recorde_dias == velha.dias_sem_perder


def test_os_quatro_juntos_contam_a_derrota_de_qualquer_jogo():
    partidas = [_p("velha", date(2026, 9, 1)), _p("quatro", date(2026, 11, 15), derrota=True)]
    escopos, _ = magno.calcular_escopos(partidas, QUARTA)
    juntos = next(n for n in escopos if n.jogo is None)
    assert juntos.dias_sem_perder == 3
    # A velha, sozinha, segue sem derrota; jogo sem partida nenhuma fica de fora.
    assert {n.jogo for n in escopos} == {None, "velha", "quatro"}


def test_partida_depois_do_dia_de_publicacao_nao_entra():
    """O card de um dia não pode mudar por uma derrota que veio depois dele."""
    partidas = [_p("damas", date(2026, 9, 1)), _p("damas", QUARTA + timedelta(days=1), derrota=True)]
    escopos, _ = magno.calcular_escopos(partidas, QUARTA)
    assert escopos[0].dias_sem_perder == (QUARTA - date(2026, 9, 1)).days


def test_placar_do_periodo():
    partidas = [_p("damas", date(2026, 11, d)) for d in (1, 5, 16)] + [
        _p("damas", date(2026, 10, 30), derrota=True)
    ]
    escopos, rotulo = magno.calcular_escopos(partidas, QUARTA)
    assert rotulo == "Em novembro"
    assert escopos[0].partidas_no_periodo == 3
    assert escopos[0].derrotas_no_periodo == 0


@pytest.mark.parametrize(
    "dia, esperado",
    [
        (date(2026, 11, 18), (date(2026, 11, 1), date(2026, 11, 18), "Em novembro")),
        (date(2026, 11, 4), (date(2026, 10, 1), date(2026, 10, 31), "Em outubro")),
        (date(2027, 1, 6), (date(2026, 12, 1), date(2026, 12, 31), "Em dezembro")),
    ],
    ids=["segunda_quinzena", "primeira_quinzena", "virada_do_ano"],
)
def test_periodo_do_placar(dia: date, esperado):
    """Na primeira quinzena vale o mês anterior inteiro (o atual ainda é pouco)."""
    assert magno.periodo_do_placar(dia) == esperado


def test_dia_de_brasilia():
    """02:00 UTC de quinta ainda é quarta às 23h em Brasília."""
    instante = datetime(2026, 11, 19, 2, 0, tzinfo=timezone.utc)
    assert magno.para_dia_de_brasilia(instante) == QUARTA
    # Sem fuso (como pode vir do banco) é tratado como UTC.
    assert magno.para_dia_de_brasilia(instante.replace(tzinfo=None)) == QUARTA


def test_a_consulta_so_conta_o_que_conta():
    """O cadeado lê o texto da consulta: os quatro filtros e nenhum usuário."""
    sql = magno.SQL_PARTIDAS_DO_MAGNO
    for filtro in ("co_modo = 'vs_cpu'", "co_dificuldade = 'sagaz'", "co_status = 'concluida'", "'venceu_j1'"):
        assert filtro in sql
    assert "id_usuario" not in sql


# ── A rota ───────────────────────────────────────────────────────────────────


@pytest.fixture
def cliente(monkeypatch):
    """Cliente com o relógio fixo numa quinta 00:30 UTC (quarta 21h30 em Brasília).

    `dependency_overrides` troca as dependências do FastAPI por dublês sem banco;
    o `yield` entrega o cliente ao teste e, depois dele, limpa as trocas.
    """
    agora = datetime(2026, 11, 19, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(rotas_card, "agora_utc", lambda: agora)
    app.dependency_overrides[rotas_card.ler_partidas_do_magno] = lambda: []
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_rota_com_desafio(cliente: TestClient):
    linha = _linha(co_jogo="damas", dt_dia=QUINTA)
    app.dependency_overrides[rotas_card.ler_desafio_vigente] = lambda: linha
    r = cliente.get("/v1/card-do-dia")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["dia_publicacao"] == "2026-11-18"
    assert corpo["publica_hoje"] is True
    assert corpo["desafio"]["jogo"] == "damas"
    assert corpo["link"].endswith("/baixar?o=story")
    # ⛔ O gabarito nunca viaja.
    assert "solucao" not in r.text
    # Quarta do Magno, mas sem partidas: o card dele não sai, vira convite.
    assert corpo["magno"] is None
    assert corpo["stories"][0]["card"] == "convite"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-robots-tag"] == "noindex"


def test_rota_sem_desafio_aprovado(cliente: TestClient):
    """Sem desafio, a página ainda sabe o dia (pelo relógio) e diz "não aprovado"."""
    app.dependency_overrides[rotas_card.ler_desafio_vigente] = lambda: None
    r = cliente.get("/v1/card-do-dia")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["desafio"] is None
    assert corpo["dia_publicacao"] == "2026-11-18"


def test_rota_na_quarta_do_magno_com_numeros(cliente: TestClient):
    linha = _linha(co_jogo="velha", dt_dia=QUINTA)
    longe = QUARTA - timedelta(days=100)
    partidas = [_p("velha", longe), *[_p("velha", date(2026, 11, d)) for d in range(1, 18)]]
    app.dependency_overrides[rotas_card.ler_desafio_vigente] = lambda: linha
    app.dependency_overrides[rotas_card.ler_partidas_do_magno] = lambda: partidas
    corpo = cliente.get("/v1/card-do-dia").json()
    assert corpo["stories"][0]["card"] == "magno"
    assert corpo["magno"]["dias_sem_perder"] == 100
    assert corpo["magno"]["periodo"] == "Em novembro"
