"""🔒 A JANELA BAIXADA: o que ja esta nos aparelhos nao sai do dia dele (07/10/2026).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O app guarda hoje e os proximos `DIAS_DE_CACHE` dias para jogar sem rede. Quem
resolve sem rede um desafio que o dono descartou depois tem o envio recusado
(`vinculo_invalido`), e quem resolve um que mudou de data entra no quadro de um
dia que nao jogou. Nos dois casos, sem nada avisar. O porque inteiro esta em
`api/desafios/janela_baixada.py`.

Os quatro lados que mexem num dia sao conferidos aqui: a regra pura, a consulta
que a alimenta, o servico do painel (que recusa) e a pagina (que espelha), mais a
compactacao do job (que nao doa de dentro da janela).
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest

from api.desafios import janela_baixada
from api.desafios.janela_baixada import (
    DIAS_DE_CACHE,
    SQL_FIM_DOS_PROXIMOS,
    fim_da_janela_baixada,
    ler_fim_da_janela_baixada,
)
from api.desafios.painel import pagina
from api.desafios.painel.servico import ServicoCuradoria
from api.desafios.repositorio import SQL_PROXIMOS
from api.nucleo.excecoes import ErroNegocio
from job.compactar_fila import LinhaDaFila, remanejar
from job.repositorio import SQL_MOVER_O_DIA
from tests.unitarios.fakes_desafio import FakeSessaoSQL
from tests.unitarios.test_painel_gestao import _desafio

HOJE = date(2026, 10, 20)


def _d(quantos: int) -> date:
    """`_d(1)` e amanha."""
    return HOJE + timedelta(days=quantos)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Onde a janela termina
# ═══════════════════════════════════════════════════════════════════════════


def test_o_cache_do_app_e_de_TRES_dias() -> None:
    """🔒 O numero com que a janela foi pensada. ⚠️ Mudou? A trava muda junto -
    e a resposta ao dono ("a curadoria vale de D+4 em diante") tambem."""
    assert DIAS_DE_CACHE == 3


def test_sem_nada_publicado_a_frente_a_janela_e_hoje_mais_3() -> None:
    """🔒 Fila vazia: vale a conta simples."""
    assert fim_da_janela_baixada(HOJE, []) == _d(3)


def test_fila_sem_buraco_a_janela_e_hoje_mais_3() -> None:
    """🔒 O caso comum: os proximos sao amanha, D+2 e D+3."""
    assert fim_da_janela_baixada(HOJE, [_d(1), _d(2), _d(3)]) == _d(3)


def test_com_BURACO_a_janela_vai_ate_o_ultimo_dia_ENTREGUE() -> None:
    """🔒 ⚠️ Amanha vazio: o `/proximos` entrega D+2, D+3 e D+4 - e o D+4 esta no
    aparelho de alguem. A conta simples o deixaria destravado."""
    assert fim_da_janela_baixada(HOJE, [_d(4)]) == _d(4)


def test_a_consulta_da_janela_tem_o_MESMO_filtro_do_proximos() -> None:
    """🔒 ⛔ A janela e, por definicao, o que o `/proximos` entrega. Se aquela
    consulta mudar de filtro ou de ordem e esta nao, a trava passa a proteger
    outros dias que nao os que estao nos aparelhos - sem nada falhar."""
    for trecho in (
        "d.co_curadoria = 'aprovado'",
        "dia.dt_dia > :dt_hoje",
        "ORDER BY dia.dt_dia ASC",
        "LIMIT :limite",
    ):
        assert trecho in SQL_PROXIMOS, f"o /proximos mudou: {trecho}"
        assert trecho in SQL_FIM_DOS_PROXIMOS, f"a janela nao acompanhou: {trecho}"


@pytest.mark.asyncio
async def test_a_leitura_do_banco_usa_o_LIMITE_do_cache_e_le_o_MAX() -> None:
    """🔒 O ultimo dia entregue vem do banco, e o limite e o do `/proximos`."""
    sessao = FakeSessaoSQL(respostas={"MAX(proximo.dt_dia)": [{"dt_fim": _d(5)}]})
    assert await ler_fim_da_janela_baixada(sessao, HOJE) == _d(5)
    _, parametros = sessao.executadas[0]
    assert parametros == {"dt_hoje": HOJE, "limite": DIAS_DE_CACHE}


@pytest.mark.asyncio
async def test_MAX_de_nada_e_NULL_e_vira_a_conta_simples() -> None:
    """🔒 ⚠️ `MAX` de nenhuma linha devolve UMA linha com `NULL`, e nao zero
    linhas. Tratar so o segundo caso derrubaria o painel com a fila vazia."""
    sessao = FakeSessaoSQL(respostas={"MAX(proximo.dt_dia)": [{"dt_fim": None}]})
    assert await ler_fim_da_janela_baixada(sessao, HOJE) == _d(3)
    assert await ler_fim_da_janela_baixada(FakeSessaoSQL(), HOJE) == _d(3)


# ═══════════════════════════════════════════════════════════════════════════
# 2. O servico do painel RECUSA
# ═══════════════════════════════════════════════════════════════════════════


class RepoDaJanela:
    """Um repositorio de mentira com UM desafio aprovado, num dia, sem tentativa.

    ⚠️ Guarda o que foi escrito: a recusa tem de vir ANTES de qualquer escrita.
    """

    def __init__(self, dt_dia: date | None, *, dt_fim: date = _d(3)) -> None:
        self.dt_dia = dt_dia
        self.dt_fim = dt_fim
        self.alvo = _desafio(dt_dia, co_curadoria="aprovado")
        self.mexeu: list[str] = []

    async def situacao_no_calendario(self, id_desafio: UUID):
        return None if self.dt_dia is None else (self.dt_dia, 0)

    async def fim_da_janela_baixada(self, dt_hoje: date) -> date:
        return self.dt_fim

    async def fila(self, *, estados=(), limite=60):
        return [self.alvo]

    async def descartar(self, id_desafio, *, de_motivo):
        self.mexeu.append("descartar")
        return True

    async def desagendar(self, id_desafio):
        self.mexeu.append("desagendar")
        return True

    async def agendar(self, id_desafio, *, dt_dia):
        self.mexeu.append(f"agendar {dt_dia}")
        return True

    async def confirmar(self):
        self.mexeu.append("commit")


@pytest.mark.parametrize("quantos", [0, 1, 2, 3], ids=["hoje", "D+1", "D+2", "D+3"])
@pytest.mark.asyncio
async def test_dia_da_janela_recusa_DESCARTAR_MOVER_e_TIRAR(quantos: int) -> None:
    """🔒 ⛔ A pergunta do dono, item por item: na janela, nada sai do dia."""
    repo = RepoDaJanela(_d(quantos))
    servico = ServicoCuradoria(repo)  # type: ignore[arg-type]
    id_desafio = repo.alvo.id_desafio

    with pytest.raises(ErroNegocio) as erro:
        await servico.descartar(id_desafio, motivo="ruim", dt_hoje=HOJE)
    assert erro.value.codigo == "dia_ja_baixado"
    # A mensagem diz de onde a curadoria volta a valer.
    assert "24/10/2026" in erro.value.detalhe
    with pytest.raises(ErroNegocio) as erro:
        await servico.agendar(id_desafio, dt_dia=_d(10), dt_hoje=HOJE)
    assert erro.value.codigo == "dia_ja_baixado"
    with pytest.raises(ErroNegocio) as erro:
        await servico.desagendar(id_desafio, dt_hoje=HOJE)
    assert erro.value.codigo == "dia_ja_baixado"

    assert repo.mexeu == [], "a recusa tem de vir ANTES de qualquer escrita"


@pytest.mark.asyncio
async def test_o_PRIMEIRO_dia_depois_da_janela_se_cura_normalmente() -> None:
    """🔒 A trava nao pode alcancar o D+4: e ali que a curadoria comeca."""
    repo = RepoDaJanela(_d(4))
    resultado = await ServicoCuradoria(repo).descartar(  # type: ignore[arg-type]
        repo.alvo.id_desafio, motivo="facil demais", dt_hoje=HOJE
    )
    assert resultado.mudou
    assert repo.mexeu == ["descartar", "desagendar", "commit"]


@pytest.mark.asyncio
async def test_com_BURACO_na_fila_o_D4_tambem_fica_travado() -> None:
    """🔒 ⚠️ Amanha vazio: o D+4 foi entregue pelo `/proximos`, e trava."""
    repo = RepoDaJanela(_d(4), dt_fim=_d(4))
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).descartar(  # type: ignore[arg-type]
            repo.alvo.id_desafio, motivo="ruim", dt_hoje=HOJE
        )
    assert erro.value.codigo == "dia_ja_baixado"


@pytest.mark.asyncio
async def test_TAPAR_um_dia_vazio_da_janela_com_um_de_FORA_e_permitido() -> None:
    """🔒 ⚠️ So a ORIGEM e travada. Ninguem tem o dia vazio guardado, e recusar
    deixaria um dia em branco no app - o defeito que o painel mais evita."""
    repo = RepoDaJanela(_d(8))  # o desafio mora no D+8, fora da janela
    resultado = await ServicoCuradoria(repo).agendar(  # type: ignore[arg-type]
        repo.alvo.id_desafio, dt_dia=_d(2), dt_hoje=HOJE
    )
    assert resultado.mudou
    assert repo.mexeu == [f"agendar {_d(2)}", "commit"]


@pytest.mark.asyncio
async def test_desafio_SEM_dia_nao_esta_em_aparelho_nenhum() -> None:
    """🔒 Da reserva para um dia vazio da janela: permitido."""
    repo = RepoDaJanela(None)
    resultado = await ServicoCuradoria(repo).agendar(  # type: ignore[arg-type]
        repo.alvo.id_desafio, dt_dia=HOJE, dt_hoje=HOJE
    )
    assert resultado.mudou


# ═══════════════════════════════════════════════════════════════════════════
# 3. A pagina ESPELHA
# ═══════════════════════════════════════════════════════════════════════════


def _detalhe(quantos: int) -> str:
    dia = _d(quantos)
    return pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=dia, desafio=_desafio(dia, co_curadoria="aprovado")),
        dt_hoje=HOJE,
        dt_sugerida=HOJE,
        dt_fim_janela_baixada=_d(3),
    )


@pytest.mark.parametrize("quantos", [0, 1, 3], ids=["hoje", "D+1", "D+3"])
def test_dia_da_janela_NAO_oferece_descartar_mover_nem_tirar(quantos: int) -> None:
    """🔒 ⛔ Espelho de `servico._exigir_fora_da_janela_baixada`."""
    html = _detalhe(quantos)
    assert f"{pagina.BASE}/descartar" not in html
    assert f"{pagina.BASE}/agendar" not in html
    assert f"{pagina.BASE}/desagendar" not in html
    assert "ja pode estar guardado nos aparelhos" in html
    assert "A curadoria vale de 24/10/2026 em diante" in html


def test_o_D4_oferece_as_tres_acoes() -> None:
    """🔒 O primeiro dia depois da janela tem os botoes de sempre."""
    html = _detalhe(4)
    assert f"{pagina.BASE}/descartar" in html
    assert f"{pagina.BASE}/agendar" in html
    assert f"{pagina.BASE}/desagendar" in html
    assert "ja pode estar guardado nos aparelhos" not in html


# ═══════════════════════════════════════════════════════════════════════════
# 4. O job nao DOA de dentro da janela
# ═══════════════════════════════════════════════════════════════════════════


def _linha(quantos: int, tipo: str) -> LinhaDaFila:
    return LinhaDaFila(
        dt_dia=_d(quantos),
        id_desafio_dia=f"id-{quantos}",
        co_tipo_desafio=tipo,
        co_curadoria="aprovado",
    )


def _plano() -> list[date]:
    return [_d(n) for n in range(7)]


def test_doador_DENTRO_da_janela_nao_desce() -> None:
    """🔒 ⛔ Amanha vazio, D+3 aprovado: sem a trava, o D+3 desceria para amanha,
    e quem o tem guardado entraria no quadro do dia errado."""
    fila = [_linha(0, "a"), _linha(2, "b"), _linha(3, "c")]
    mudancas = remanejar(
        fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=_d(3)
    )
    assert mudancas == []


def test_doador_de_FORA_tapa_o_buraco_de_DENTRO() -> None:
    """🔒 ⚠️ O buraco da janela continua podendo ser tapado - com quem ninguem tem."""
    fila = [_linha(0, "a"), _linha(2, "b"), _linha(3, "c"), _linha(6, "d")]
    mudancas = remanejar(
        fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=_d(3)
    )
    assert [(m.dt_de, m.dt_para) for m in mudancas] == [(_d(6), _d(1))]


def test_o_UPDATE_do_job_tem_a_REDE_do_banco() -> None:
    """🔒 ⛔ A regra vale mesmo que alguem chame o `UPDATE` de outro lugar."""
    assert "dt_dia          > :dt_fim_janela_baixada" in SQL_MOVER_O_DIA


def test_a_regra_mora_num_lugar_so() -> None:
    """🔒 Painel e job leem a janela do mesmo modulo - os dois lados que mexem na
    fila nao podem discordar sobre onde a trava termina."""
    import inspect

    from api.desafios.painel import repositorio as repo_painel
    from job import repositorio as repo_job

    for modulo in (repo_painel, repo_job):
        assert "ler_fim_da_janela_baixada" in inspect.getsource(modulo)
    assert janela_baixada.ler_fim_da_janela_baixada is ler_fim_da_janela_baixada


# ═══════════════════════════════════════════════════════════════════════════
# 5. As duas rotas que desenham o dia LEEM a janela
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "caminho",
    ["/painel/desafios", "/painel/desafios/fragmento?dia=2026-10-21"],
    ids=["pagina inteira", "fragmento do clique"],
)
def test_as_rotas_do_painel_consultam_a_janela(monkeypatch, caminho: str) -> None:
    """🔒 ⚠️ A pagina inteira e o fragmento (o dia aberto por clique no
    calendario) desenham o mesmo dia. Uma das duas sem a janela ofereceria, por
    um dos caminhos, os botoes que o servico recusa."""
    from fastapi.testclient import TestClient

    from api.configuracao import configuracoes
    from api.main import app
    from api.nucleo.banco import obter_sessao

    segredo = "segredo-de-teste-da-janela"
    sessao = FakeSessaoSQL(
        respostas={
            # A contagem da reserva precisa de uma linha (ver
            # `test_painel_curadoria._sessao_de_pagina`).
            "WHERE d.co_curadoria = 'aprovado'": [{"qt": 0}],
            "MAX(proximo.dt_dia)": [{"dt_fim": None}],
        }
    )
    monkeypatch.setattr(configuracoes, "PAINEL_CURADORIA_TOKEN", segredo)
    app.dependency_overrides[obter_sessao] = lambda: sessao
    try:
        resposta = TestClient(app, follow_redirects=False).get(
            caminho, headers={"X-Admin-Token": segredo}
        )
    finally:
        app.dependency_overrides.clear()

    assert resposta.status_code == 200
    assert sessao.sql_executado("MAX(proximo.dt_dia)"), "a rota nao leu a janela"
