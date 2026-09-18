"""O RESUMO DO MES — T072a (`contracts/resumo-do-mes.md`).

O que estes casos protegem:

  · ⚠️ **o mes ZERA** (RF-DES-067) — o recorte e do dia 1 ao dia de hoje, e nao
    "os ultimos 30 dias": trocar um pelo outro e outro produto, em que ninguem
    mais recomeca junto;
  · ⛔ **nada de amanha** (RF-DES-009) — a fila tem dias futuros publicados na
    mesma tabela, e eles nao saem daqui;
  · ⚠️ **zero e resposta valida**, ao contrario do zero do quadro;
  · ⛔ **a ordem das rotas** — `/meu-mes` antes de `/{id_desafio}`, senao o
    caminho vira um `422` mudo.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

from api.desafios.mes import SQL_DIAS_DO_MES, ServicoMes, primeiro_dia_do_mes

HOJE = date(2026, 9, 18)
EU = "uid-eu"
ID_DIA = uuid4()
ID_DESAFIO = UUID("9f1c0000-0000-4000-8000-000000000001")


class RepoFalso:
    """Um `RepositorioMes` de mentira — ele anota o que lhe perguntaram."""

    def __init__(self, linhas=None) -> None:
        self._linhas = linhas or []
        self.pedido: dict = {}

    async def dias(self, *, id_usuario, primeiro_dia, dt_hoje):
        self.pedido = {
            "id_usuario": id_usuario,
            "primeiro_dia": primeiro_dia,
            "dt_hoje": dt_hoje,
        }
        return self._linhas


def linha(
    *,
    dia: date,
    resolvido: bool = True,
    jogo: str = "damas",
    modalidade: str | None = "brasileira",
    reprise: bool = False,
) -> dict:
    """Uma linha como o `SELECT` a devolve."""
    return {
        "dt_dia": dia,
        "id_desafio_dia": ID_DIA,
        "id_desafio": ID_DESAFIO,
        "co_jogo": jogo,
        "co_modalidade": modalidade,
        "ic_reprise": reprise,
        "ic_resolvido": resolvido,
    }


class TestOMesZera:
    """⚠️ RF-DES-067: o recorte e o **mes corrente**."""

    def test_o_primeiro_dia_e_o_dia_1(self):
        assert primeiro_dia_do_mes(HOJE) == date(2026, 9, 1)

    def test_no_dia_1_o_recorte_e_um_dia_so(self):
        # ⚠️ E isso e correto, e nao um caso degenerado: no dia 1 o mes tem um
        # dia. O calendario mostra o mes inteiro com os outros por chegar.
        assert primeiro_dia_do_mes(date(2026, 1, 1)) == date(2026, 1, 1)

    def test_a_virada_do_ano_nao_e_especial(self):
        assert primeiro_dia_do_mes(date(2026, 12, 31)) == date(2026, 12, 1)

    @pytest.mark.asyncio
    async def test_a_consulta_recebe_o_dia_1_e_HOJE(self):
        # ⛔ **Nada de amanha**: o corte superior e hoje, e nao o fim do mes. A
        # fila de aprovados tem dias futuros publicados **nesta mesma tabela**.
        repo = RepoFalso()
        await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert repo.pedido["primeiro_dia"] == date(2026, 9, 1)
        assert repo.pedido["dt_hoje"] == HOJE

    @pytest.mark.asyncio
    async def test_o_mes_sai_como_ano_e_mes(self):
        # ⛔ **E nunca o NOME do mes**: nome e i18n, e o servidor nao sabe o
        # idioma do aparelho que perguntou.
        corpo = await ServicoMes(RepoFalso()).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["mes"] == "2026-09"

    @pytest.mark.asyncio
    async def test_mes_de_um_digito_vai_com_zero_a_esquerda(self):
        corpo = await ServicoMes(RepoFalso()).montar(
            id_usuario=EU, dt_hoje=date(2026, 3, 4)
        )

        assert corpo["mes"] == "2026-03"


class TestOQueCadaDiaTraz:
    """O que o calendario e o card de um dia passado precisam."""

    @pytest.mark.asyncio
    async def test_traz_o_dia_o_jogo_e_se_resolveu(self):
        repo = RepoFalso([linha(dia=date(2026, 9, 17))])
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        (dia,) = corpo["dias"]
        assert dia["dia"] == date(2026, 9, 17)
        assert dia["jogo"] == "damas"
        assert dia["modalidade"] == "brasileira"
        assert dia["resolvido"] is True
        assert dia["reprise"] is False

    @pytest.mark.asyncio
    async def test_o_identificador_do_desafio_vem_junto(self):
        # ⚠️ E ele que abre os replays e o gabarito daquele dia: sem ele o card
        # seria um retangulo que nao leva a lugar nenhum.
        repo = RepoFalso([linha(dia=date(2026, 9, 17))])
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["dias"][0]["id_desafio"] == ID_DESAFIO

    @pytest.mark.asyncio
    async def test_modalidade_nula_do_pontinhos_continua_nula(self):
        # ⛔ **Nao vira string vazia.** A ausencia e a verdade: o Pontinhos nao
        # tem modalidade, e a tela decide nao desenhar a pilula.
        repo = RepoFalso(
            [linha(dia=HOJE, jogo="pontinhos", modalidade=None)]
        )
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["dias"][0]["modalidade"] is None

    @pytest.mark.asyncio
    async def test_a_reprise_e_declarada(self):
        repo = RepoFalso([linha(dia=HOJE, reprise=True)])
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["dias"][0]["reprise"] is True

    @pytest.mark.asyncio
    async def test_o_dia_NAO_resolvido_vem_na_lista(self):
        # ⚠️ **E o que o `LEFT JOIN` garante.** Um `JOIN` devolveria so os dias
        # bons, e o calendario nasceria sem os outros — sem erro nenhum, e com a
        # aparencia de quem nunca perdeu um dia.
        repo = RepoFalso([linha(dia=date(2026, 9, 16), resolvido=False)])
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert len(corpo["dias"]) == 1
        assert corpo["dias"][0]["resolvido"] is False


class TestATotalizacao:
    """*"17 desafios resolvidos"* — e o zero, que aqui aparece."""

    @pytest.mark.asyncio
    async def test_conta_so_os_resolvidos(self):
        repo = RepoFalso(
            [
                linha(dia=date(2026, 9, 18), resolvido=True),
                linha(dia=date(2026, 9, 17), resolvido=False),
                linha(dia=date(2026, 9, 16), resolvido=True),
            ]
        )
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["resolvidos"] == 2
        assert len(corpo["dias"]) == 3

    @pytest.mark.asyncio
    async def test_zero_e_resposta_valida(self):
        # ⚠️ **Ao contrario do zero do quadro** (RF-DES-064): la o numero conta
        # sobre o tamanho da base; aqui e sobre a propria pessoa, e a tela o
        # traduz em convite — *"todo mundo recomeca junto no dia 1"*.
        repo = RepoFalso([linha(dia=HOJE, resolvido=False)])
        corpo = await ServicoMes(repo).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["resolvidos"] == 0

    @pytest.mark.asyncio
    async def test_mes_sem_dia_nenhum_nao_e_erro(self):
        # Acontece no dia 1, antes de o job publicar: lista vazia e o estado
        # normal, e um 404 faria a tela tratar rotina como falha.
        corpo = await ServicoMes(RepoFalso()).montar(id_usuario=EU, dt_hoje=HOJE)

        assert corpo["dias"] == []
        assert corpo["resolvidos"] == 0


class TestOSqlENaoMente:
    """🔒 Dois defeitos silenciosos que so se pegam lendo o SQL."""

    def test_a_resolucao_e_filtrada_no_ON_e_nao_no_WHERE(self):
        # ⚠️ **O defeito classico do `LEFT JOIN`**: com `r.id_usuario` no
        # `WHERE`, ele vira um `JOIN` disfarcado e descarta justamente os dias
        # sem resolucao **dela** — o calendario ficaria so com os dias bons, sem
        # erro nenhum.
        antes_do_where, _, depois = SQL_DIAS_DO_MES.partition("WHERE")

        assert "AND r.id_usuario = :id_usuario" in antes_do_where
        assert "r.id_usuario" not in depois

    def test_so_desafio_aprovado_entra_no_calendario(self):
        # E a mesma regra das outras rotas: aprovar e agendar sao duas acoes, e
        # so o aprovado e publicado.
        assert "co_curadoria = 'aprovado'" in SQL_DIAS_DO_MES


class TestAOrdemDasRotas:
    """🔒 `/meu-mes` antes de `/{id_desafio}` — senao o caminho vira `422`."""

    def test_meu_mes_vem_antes_do_id(self):
        # ⚠️ O FastAPI casa a **primeira** rota que serve. Com `/{id_desafio}` na
        # frente, `meu-mes` seria lido como UUID e responderia `422` — um erro de
        # validacao onde existe uma rota perfeitamente valida, e o aplicativo
        # traduziria isso como "o historico nao carregou".
        from api.desafios.rotas import router

        caminhos = [r.path for r in router.routes]

        assert caminhos.index("/meu-mes") < caminhos.index("/{id_desafio}")
