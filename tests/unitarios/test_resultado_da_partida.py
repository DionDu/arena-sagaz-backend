"""O resultado explícito da partida no servidor e na migração 0038 (T168, spec 010).

═══════════════════════════════════════════════════════════════════════════
O DEFEITO QUE ESTE ARQUIVO VIGIA (30/10/2026)
═══════════════════════════════════════════════════════════════════════════

Nas damas o placar (`nu_placar_j1`, `nu_placar_j2`) guarda a quantidade de PEÇAS
RESTANTES ao fim da partida. Um empate com 5×3 peças era contado como `empate`
no aparelho e como vitória no servidor (que deduzia tudo do placar). Na junção
campo a campo por `GREATEST`, `V + D + E` passava de `nu_partidas` e a
reconciliação da conta passava a ser recusada com 422 para sempre.

Regra da T168 (`docs/DECISOES-do-dono.md` §8zzzz10 do app;
`specs/010-jogo-quatro-em-linha/PASSAGEM-correcao-progressao-30-10.md` §4):

1. `co_resultado` (`'venceu_j1'` | `'venceu_j2'` | `'empate'`, ponto de vista do
   J1) é campo aditivo opcional em `payload.partida` e coluna anulável em
   `partida.tb001_partida`;
2. quando vem válido, `_incrementar_progressao` e `partida.vw001_partida` usam
   ele; quando não vem (app 1.3.1 das lojas, que não pode sofrer regressão
   nenhuma), caem na comparação do placar e produzem os mesmos números de hoje;
3. valor fora dos três (ou de outro tipo) vira `NULL` antes do SQL, com aviso no
   log — nunca estoura o `CHECK` (viraria `falha_processamento` e o app apagaria
   a partida da fila) e nunca recusa o evento.
"""

from __future__ import annotations

import ast
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.sincronizacao import dimensoes, repositorio as mod_repo
from api.sincronizacao.repositorio import (
    RESULTADOS_VALIDOS_PARTIDA,
    RepositorioSincronizacao,
    _CAMPOS_GENERICOS_DA_PARTIDA,
    _avisar_extensao_de_partida_desconhecida,
    desfecho_da_partida,
    normalizar_resultado_partida,
)
from api.sincronizacao.rotas import obter_servico_sync
from api.sincronizacao.servico import ServicoSincronizacao
from api.sincronizacao.validacao import validar_evento
from tests.contratos.fakes_sync import FakeRepoSincronizacao
from tests.unitarios.fakes_conta import FakeSession
from tests.unitarios.leitura_de_migracao import sem_comentarios_sql, sql_do_upgrade

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
MIGRACAO_0038 = (
    RAIZ_BACKEND / "migrations" / "versions" / "0038_resultado_da_partida.py"
)
DONO = "3fc7be86-c396-4167-ad30-8d7048521ad9"

#: As 20 colunas que `partida.vw001_partida` já tinha na revisão 0037 (conferidas
#: por leitura direta no `des` e no `prd` em 30/10/2026), mais a 21ª coluna nova
#: `ic_resultado_informado` obrigatoriamente ao fim.
COLUNAS_ESPERADAS_VW001 = [
    "id_partida",
    "co_evento",
    "co_jogo",
    "co_variante",
    "co_modo",
    "id_usuario",
    "id_usuario_j2",
    "co_dificuldade",
    "nu_placar_j1",
    "nu_placar_j2",
    "ic_pontua",
    "co_status",
    "co_lote_migracao",
    "dh_inicio",
    "dh_fim",
    "nu_offset_minuto_j1",
    "nu_offset_minuto_j2",
    "qt_usos_poder",
    "co_resultado",
    "ic_com_poder",
    "ic_resultado_informado",
]


# ═══════════════════════════════════════════════════════════════════════════
# Construtores de payload (molde exato da 1.3.1 vs 1.4.0)
# ═══════════════════════════════════════════════════════════════════════════


def _evento_1_3_1(
    *,
    co_evento: str = "11111111-1111-1111-1111-111111111111",
    id_partida: str = "22222222-2222-2222-2222-222222222222",
    co_jogo: str = "pontinhos",
    co_variante: str = "pequeno",
    co_modo: str = "vs_cpu",
    placar: tuple[int, int] = (3, 2),
    ic_pontua: bool = True,
    co_status: str = "concluida",
    xp: int = 25,
) -> dict[str, Any]:
    """Corpo EXATO que `ServicoLogPartida._montarPayload` da 1.3.1 envia.

    Repare que a chave `co_resultado` NÃO existe no dicionário (não é nem
    `None`: o app 1.3.1 não conhece o campo). Inclui `co_anonimo` como os apps
    antigos faziam, para provar retrocompatibilidade completa.
    """
    parcelas = (
        [{"co_tipo_xp": "resultado", "nu_xp": xp, "co_referencia": None}]
        if xp > 0
        else []
    )
    return {
        "co_evento": co_evento,
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "id_partida": id_partida,
                "co_jogo": co_jogo,
                "co_variante": co_variante,
                "co_modo": co_modo,
                "co_dificuldade": "normal" if co_modo == "vs_cpu" else None,
                "nu_placar_j1": placar[0],
                "nu_placar_j2": placar[1],
                "ic_pontua": ic_pontua,
                "co_status": co_status,
                "co_lote_migracao": None,
                "dh_inicio": "2026-10-30T14:00:00.000Z",
                "dh_fim": (
                    "2026-10-30T14:03:00.000Z"
                    if co_status != "em_andamento"
                    else None
                ),
                "nu_offset_minuto_j1": -180,
                "nu_offset_minuto_j2": None,
                "co_anonimo": "anon-legado",
            },
            "jogadas": [],
            "xp": parcelas,
        },
    }


def _evento_com_resultado(co_resultado: Any, **kwargs: Any) -> dict[str, Any]:
    """O mesmo corpo de partida acrescido da chave `co_resultado` (1.4.0+)."""
    ev = _evento_1_3_1(**kwargs)
    ev["payload"]["partida"]["co_resultado"] = co_resultado
    return ev


# ═══════════════════════════════════════════════════════════════════════════
# Sessão falsa que inspeciona os comandos enviados pelo repositório real
# ═══════════════════════════════════════════════════════════════════════════


class _ResultadoSQL:
    """Resposta mínima para os `.first()` e `.all()` que `gravar_evento` consome."""

    def __init__(
        self, linha: Any, linhas: list[Any] | None = None
    ) -> None:
        self._linha = linha
        self._linhas = list(linhas or [])

    def first(self) -> Any:
        return self._linha

    def all(self) -> list[Any]:
        return self._linhas


class _SessaoGravacao:
    """Anota cada comando SQL e simula o `RETURNING` da partida e de `_ja_tem_xp`.

    * `ic_inserida=True` simula o `INSERT` novo (`xmax = 0`);
    * `ic_inserida=False` simula o `DO UPDATE` da 2ª leva (`em_andamento` →
      `concluida`);
    * `ja_tem_xp` controla a sentinela de `_ja_tem_xp` na completação.
    """

    def __init__(
        self, *, ic_inserida: bool = True, ja_tem_xp: bool = False
    ) -> None:
        self.ic_inserida = ic_inserida
        self.ja_tem_xp = ja_tem_xp
        self.comandos: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self, comando: Any, parametros: dict[str, Any] | None = None
    ) -> _ResultadoSQL:
        sql = str(comando)
        params = dict(parametros or {})
        self.comandos.append((sql, params))

        if "INSERT INTO partida.tb001_partida" in sql:
            return _ResultadoSQL((params.get("id_partida"), self.ic_inserida))
        if "FROM partida.tb003_xp_partida" in sql:
            return _ResultadoSQL((1,) if self.ja_tem_xp else None)
        if "FROM partida.vw902_tipo_xp" in sql:
            return _ResultadoSQL(
                None,
                [
                    ("resultado", 1),
                    ("sequencia", 2),
                    ("vitoria", 3),
                    ("derrota", 4),
                    ("empate", 5),
                    ("participacao", 6),
                    ("bonus", 7),
                ],
            )
        return _ResultadoSQL(None)

    def parametros_de(self, trecho_sql: str) -> list[dict[str, Any]]:
        """Devolve a lista de dicionários de parâmetros cujo SQL contém [trecho_sql]."""
        return [p for sql, p in self.comandos if trecho_sql in sql]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Funções puras e validação (sem tocar em validacao.py)
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizacaoEDesfechoPuro:
    """A regra de sanitização e contagem isolada de qualquer banco."""

    def test_os_tres_valores_validos_passam_intactos(self):
        assert RESULTADOS_VALIDOS_PARTIDA == frozenset(
            {"venceu_j1", "venceu_j2", "empate"}
        )
        for codigo in ("venceu_j1", "venceu_j2", "empate"):
            assert normalizar_resultado_partida(codigo) == codigo

    @pytest.mark.parametrize(
        "invalido",
        [
            None,
            "",
            "EMPATE",
            " empate",
            "empate ",
            "VENCEU_J1",
            "vitoria",
            "derrota",
            0,
            1,
            -1,
            True,
            False,
            1.5,
            ["empate"],
            {"resultado": "empate"},
        ],
    )
    def test_qualquer_outro_valor_vira_None(self, invalido: Any):
        assert normalizar_resultado_partida(invalido) is None

    @pytest.mark.parametrize(
        "placar, esperado",
        [
            ((3, 2), (1, 0, 0)),
            ((2, 3), (0, 1, 0)),
            ((2, 2), (0, 0, 1)),
            # Damas na 1.3.1 (sem co_resultado): 5×3 peças restantes dá vitória
            # pelo placar — comportamento atual preservado para quem não atualizar.
            ((5, 3), (1, 0, 0)),
        ],
    )
    def test_sem_co_resultado_deduz_do_placar_como_na_1_3_1(
        self, placar: tuple[int, int], esperado: tuple[int, int, int]
    ):
        partida = {"nu_placar_j1": placar[0], "nu_placar_j2": placar[1]}
        assert desfecho_da_partida(partida) == esperado
        assert sum(desfecho_da_partida(partida)) == 1

    def test_empate_de_damas_5x3_com_controle_da_1_3_1(self):
        """O caso central do defeito 2, com seu controle lado a lado."""
        sem_campo = {"nu_placar_j1": 5, "nu_placar_j2": 3}
        com_empate = {"nu_placar_j1": 5, "nu_placar_j2": 3, "co_resultado": "empate"}

        # Controle: sem o campo dá vitória do J1 (regra antiga).
        assert desfecho_da_partida(sem_campo) == (1, 0, 0)
        # Com o campo explícito dá empate, igual ao que o app contou.
        assert desfecho_da_partida(com_empate) == (0, 0, 1)

    @pytest.mark.parametrize(
        "co_resultado, placar, esperado",
        [
            ("venceu_j1", (2, 4), (1, 0, 0)),
            ("venceu_j2", (5, 1), (0, 1, 0)),
            ("empate", (0, 3), (0, 0, 1)),
        ],
    )
    def test_resultado_valido_vence_qualquer_placar(
        self,
        co_resultado: str,
        placar: tuple[int, int],
        esperado: tuple[int, int, int],
    ):
        partida = {
            "nu_placar_j1": placar[0],
            "nu_placar_j2": placar[1],
            "co_resultado": co_resultado,
        }
        assert desfecho_da_partida(partida) == esperado

    def test_validacao_aceita_sem_campo_com_campo_e_com_lixo(self):
        """⛔ `validacao.py` não mudou e nunca recusa partida por `co_resultado`."""
        assert validar_evento(_evento_1_3_1()) is None
        assert validar_evento(_evento_com_resultado("empate")) is None
        assert validar_evento(_evento_com_resultado("LIXO_DO_CLIENTE")) is None
        assert validar_evento(_evento_com_resultado(999)) is None

    def test_co_resultado_esta_nos_campos_genericos_da_partida(self, caplog):
        """Mesmo que um cliente quebrado mande um dicionário em `co_resultado`,
        ele não pode ser confundido com extensão de um jogo desconhecido."""
        assert "co_resultado" in _CAMPOS_GENERICOS_DA_PARTIDA
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(
                {"co_jogo": "damas", "co_resultado": {"invalido": 1}}
            )
        assert caplog.records == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Repositório real (`gravar_evento` e `_incrementar_progressao`)
# ═══════════════════════════════════════════════════════════════════════════


class TestRepositorioGravarEvento:
    """Prova os parâmetros SQL gerados pelo repositório real em cada cenário."""

    @pytest.fixture(autouse=True)
    def _isolar_cache_dimensoes(self):
        """Não deixa o mapa simulado de `vw902_tipo_xp` vazar para outros testes."""
        dimensoes.limpar_cache()
        yield
        dimensoes.limpar_cache()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "co_jogo, placar, vde_esperado",
        [
            ("pontinhos", (3, 2), (1, 0, 0)),
            ("pontinhos", (2, 3), (0, 1, 0)),
            ("pontinhos", (2, 2), (0, 0, 1)),
            ("damas", (5, 3), (1, 0, 0)),
        ],
    )
    async def test_corpo_da_1_3_1_grava_NULL_e_conta_pelo_placar_sem_aviso(
        self,
        caplog,
        co_jogo: str,
        placar: tuple[int, int],
        vde_esperado: tuple[int, int, int],
    ):
        sessao = _SessaoGravacao()
        repo = RepositorioSincronizacao(sessao)
        ev = _evento_1_3_1(co_jogo=co_jogo, placar=placar, xp=30)

        with caplog.at_level(logging.WARNING):
            gravou = await repo.gravar_evento(
                id_usuario=DONO, co_evento=ev["co_evento"], payload=ev["payload"]
            )

        assert gravou is True
        assert caplog.records == []

        [p_partida] = sessao.parametros_de("INSERT INTO partida.tb001_partida")
        assert p_partida["co_resultado"] is None

        [p_prog] = sessao.parametros_de(
            "INSERT INTO progressao.tb001_progressao_usuario"
        )
        assert (p_prog["vit"], p_prog["der"], p_prog["emp"]) == vde_esperado
        assert p_prog["xp"] == 30

    @pytest.mark.asyncio
    async def test_corpo_novo_empate_de_damas_5x3_grava_e_conta_empate(self):
        sessao = _SessaoGravacao()
        repo = RepositorioSincronizacao(sessao)
        ev = _evento_com_resultado("empate", co_jogo="damas", placar=(5, 3), xp=18)

        gravou = await repo.gravar_evento(
            id_usuario=DONO, co_evento=ev["co_evento"], payload=ev["payload"]
        )

        assert gravou is True
        [p_partida] = sessao.parametros_de("INSERT INTO partida.tb001_partida")
        assert p_partida["co_resultado"] == "empate"

        [p_prog] = sessao.parametros_de(
            "INSERT INTO progressao.tb001_progressao_usuario"
        )
        assert (p_prog["vit"], p_prog["der"], p_prog["emp"]) == (0, 0, 1)

    @pytest.mark.asyncio
    async def test_corpo_novo_derrota_informada_com_placar_maior_conta_derrota(self):
        sessao = _SessaoGravacao()
        repo = RepositorioSincronizacao(sessao)
        ev = _evento_com_resultado(
            "venceu_j2", co_jogo="damas", placar=(4, 2), xp=10
        )

        await repo.gravar_evento(
            id_usuario=DONO, co_evento=ev["co_evento"], payload=ev["payload"]
        )

        [p_partida] = sessao.parametros_de("INSERT INTO partida.tb001_partida")
        assert p_partida["co_resultado"] == "venceu_j2"
        [p_prog] = sessao.parametros_de(
            "INSERT INTO progressao.tb001_progressao_usuario"
        )
        assert (p_prog["vit"], p_prog["der"], p_prog["emp"]) == (0, 1, 0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "valor_ruim",
        [
            "EMPATE",
            " empate",
            "vitoria",
            "",
            1,
            True,
            ["empate"],
            {"x": 1},
        ],
    )
    async def test_valor_invalido_vira_NULL_avisa_e_cai_no_placar(
        self, caplog, valor_ruim: Any
    ):
        """⛔ Se o valor ruim chegasse ao SQL, o CHECK explodiria e o app
        apagaria a partida da outbox como `falha_processamento`."""
        sessao = _SessaoGravacao()
        repo = RepositorioSincronizacao(sessao)
        ev = _evento_com_resultado(valor_ruim, placar=(2, 5), xp=12)

        with caplog.at_level(logging.WARNING):
            gravou = await repo.gravar_evento(
                id_usuario=DONO, co_evento=ev["co_evento"], payload=ev["payload"]
            )

        assert gravou is True
        [p_partida] = sessao.parametros_de("INSERT INTO partida.tb001_partida")
        assert p_partida["co_resultado"] is None

        # Caiu no placar 2×5 → derrota do J1.
        [p_prog] = sessao.parametros_de(
            "INSERT INTO progressao.tb001_progressao_usuario"
        )
        assert (p_prog["vit"], p_prog["der"], p_prog["emp"]) == (0, 1, 0)
        assert len(caplog.records) == 1
        assert "co_resultado invalido" in caplog.records[0].getMessage()

    @pytest.mark.asyncio
    async def test_pvp_local_grava_co_resultado_mas_nao_incrementa_progressao(self):
        sessao = _SessaoGravacao()
        repo = RepositorioSincronizacao(sessao)
        ev = _evento_com_resultado(
            "venceu_j1", co_modo="pvp_local", ic_pontua=False, placar=(3, 1), xp=0
        )

        gravou = await repo.gravar_evento(
            id_usuario=DONO, co_evento=ev["co_evento"], payload=ev["payload"]
        )

        assert gravou is True
        [p_partida] = sessao.parametros_de("INSERT INTO partida.tb001_partida")
        assert p_partida["co_resultado"] == "venceu_j1"
        assert (
            sessao.parametros_de("INSERT INTO progressao.tb001_progressao_usuario")
            == []
        )

    @pytest.mark.asyncio
    async def test_duas_levas_primeira_aberta_e_segunda_fecha_com_resultado(self):
        """Na 1ª leva (`em_andamento`) ainda não há vencedor (`None`). Na 2ª
        leva (`concluida`), o `DO UPDATE` grava o `co_resultado` final."""
        # 1ª leva: INSERT novo, em andamento, sem resultado.
        sessao_1 = _SessaoGravacao(ic_inserida=True)
        repo_1 = RepositorioSincronizacao(sessao_1)
        leva_1 = _evento_1_3_1(
            co_modo="desafio",
            ic_pontua=False,
            co_status="em_andamento",
            placar=(2, 1),
            xp=0,
        )
        assert await repo_1.gravar_evento(
            id_usuario=DONO,
            co_evento=leva_1["co_evento"],
            payload=leva_1["payload"],
        )
        [p1] = sessao_1.parametros_de("INSERT INTO partida.tb001_partida")
        assert p1["co_status"] == "em_andamento"
        assert p1["co_resultado"] is None

        # 2ª leva: completação (`ic_inserida=False`) fechando em empate 5×3.
        sessao_2 = _SessaoGravacao(ic_inserida=False, ja_tem_xp=False)
        repo_2 = RepositorioSincronizacao(sessao_2)
        leva_2 = _evento_com_resultado(
            "empate",
            co_jogo="damas",
            co_status="concluida",
            placar=(5, 3),
            xp=20,
        )
        assert await repo_2.gravar_evento(
            id_usuario=DONO,
            co_evento=leva_2["co_evento"],
            payload=leva_2["payload"],
        )
        [p2] = sessao_2.parametros_de("INSERT INTO partida.tb001_partida")
        assert p2["co_status"] == "concluida"
        assert p2["co_resultado"] == "empate"

        # Como `ja_tem_xp` era False, incrementou uma vez com empate; se já
        # tivesse XP (`ja_tem_xp=True`), não incrementaria de novo (controle).
        [p_prog] = sessao_2.parametros_de(
            "INSERT INTO progressao.tb001_progressao_usuario"
        )
        assert (p_prog["vit"], p_prog["der"], p_prog["emp"]) == (0, 0, 1)

        sessao_2_repetida = _SessaoGravacao(ic_inserida=False, ja_tem_xp=True)
        await RepositorioSincronizacao(sessao_2_repetida).gravar_evento(
            id_usuario=DONO,
            co_evento=leva_2["co_evento"],
            payload=leva_2["payload"],
        )
        assert (
            sessao_2_repetida.parametros_de(
                "INSERT INTO progressao.tb001_progressao_usuario"
            )
            == []
        )

    def test_sql_da_partida_inclui_co_resultado_no_INSERT_e_no_DO_UPDATE(self):
        """Cadeado estrutural no SQL de `gravar_evento`: mata a remoção da
        coluna tanto na inserção quanto na completação em duas levas."""
        fonte = Path(mod_repo.__file__).read_text(encoding="utf-8")
        sql = fonte.split("INSERT INTO partida.tb001_partida", 1)[1].split(
            '"""', 1
        )[0]
        cabecalho_insert, resto = sql.split("VALUES", 1)
        valores_insert, bloco_conflito = resto.split(
            "ON CONFLICT (co_evento) DO UPDATE", 1
        )
        bloco_set = bloco_conflito.split("WHERE", 1)[0]

        assert re.search(r"\bco_resultado\b", cabecalho_insert) is not None
        assert ":co_resultado" in valores_insert
        assert (
            re.search(
                r"\bco_resultado\s*=\s*EXCLUDED\.co_resultado\b", bloco_set
            )
            is not None
        )
        assert (
            "WHERE partida.tb001_partida.co_status = 'em_andamento'"
            in bloco_conflito
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Migração 0038 (DDL, lista de colunas, execução real da VIEW no SQLite e downgrade)
# ═══════════════════════════════════════════════════════════════════════════


def _sql_do_downgrade(arquivo: Path) -> str:
    """Extrai os textos SQL executados por `downgrade()` via AST."""
    fonte = arquivo.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    pedacos: list[str] = []
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "downgrade":
            for filho in ast.walk(no):
                if (
                    isinstance(filho, ast.Call)
                    and isinstance(filho.func, ast.Attribute)
                    and filho.func.attr == "execute"
                    and filho.args
                    and isinstance(filho.args[0], ast.Constant)
                    and isinstance(filho.args[0].value, str)
                ):
                    pedacos.append(filho.args[0].value)
    return "\n".join(pedacos)


def _select_da_view_na_0038() -> str:
    """Extrai o `SELECT ... FROM partida.tb001_partida p` da migração 0038."""
    sql = sem_comentarios_sql(sql_do_upgrade(MIGRACAO_0038))
    m = re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+partida\.vw001_partida\s+AS\s+"
        r"(SELECT\s+.*?FROM\s+partida\.tb001_partida\s+p\b)",
        sql,
        re.I | re.S,
    )
    assert m is not None, "CREATE OR REPLACE VIEW partida.vw001_partida não achado na 0038"
    return m.group(1)


class TestMigracao0038:
    """Garante cada promessa da folha de aval assinada em 30/10/2026."""

    def test_coluna_e_anulavel_sem_default_e_com_CHECK_dos_tres_valores(self):
        sql = sem_comentarios_sql(sql_do_upgrade(MIGRACAO_0038))
        compacto = " ".join(sql.split())

        # Coluna VARCHAR(10), sem NOT NULL e sem DEFAULT.
        m_add = re.search(
            r"ALTER TABLE partida\.tb001_partida ADD COLUMN (?:IF NOT EXISTS )?"
            r"co_resultado VARCHAR\(10\)(.*?)(?:ALTER TABLE|COMMENT ON|CREATE )",
            compacto,
            re.I,
        )
        assert m_add is not None
        cauda_add = m_add.group(1).upper()
        assert "NOT NULL" not in cauda_add
        assert "DEFAULT" not in cauda_add

        # Constraint nomeada ck_partida_resultado com NULL + os 3 códigos.
        m_ck = re.search(
            r"ADD CONSTRAINT ck_partida_resultado CHECK\s*\((.*)\)\s*COMMENT ON",
            compacto,
            re.I,
        )
        assert m_ck is not None, "ck_partida_resultado não encontrada na 0038"
        corpo_ck = m_ck.group(1)
        assert re.search(r"co_resultado\s+IS\s+NULL", corpo_ck, re.I) is not None
        valores_ck = set(re.findall(r"'([^']+)'", corpo_ck))
        assert valores_ck == {"venceu_j1", "venceu_j2", "empate"}

    def test_view_tem_as_21_colunas_na_ordem_exata_e_coalesce_na_ordem_certa(self):
        select_view = _select_da_view_na_0038()

        # O cast `::text` é obrigatório para `CREATE OR REPLACE VIEW` no Postgres
        # não acusar troca de `text` para `character varying`.
        assert (
            re.search(
                r"COALESCE\s*\(\s*p\.co_resultado\s*,\s*CASE\b.*?END\s*\)\s*::\s*text\s+AS\s+co_resultado",
                select_view,
                re.I | re.S,
            )
            is not None
        )

        # Executa a PRÓPRIA VIEW extraída da 0038 num SQLite em memória (apenas
        # tirando `::text`, que é sintaxe do Postgres): isso confere de uma só
        # vez os nomes e a ordem das 21 colunas, a ausência de `p.co_resultado`
        # duplicado, a prioridade do `COALESCE` e o valor de `ic_resultado_informado`!
        select_sqlite = re.sub(r"::\s*text\b", "", select_view, flags=re.I)

        con = sqlite3.connect(":memory:")
        try:
            con.execute("ATTACH DATABASE ':memory:' AS partida")
            con.execute(
                """
                CREATE TABLE partida.tb001_partida (
                    id_partida TEXT,
                    co_evento TEXT,
                    co_jogo TEXT,
                    co_variante TEXT,
                    co_modo TEXT,
                    id_usuario TEXT,
                    id_usuario_j2 TEXT,
                    co_dificuldade TEXT,
                    nu_placar_j1 INTEGER,
                    nu_placar_j2 INTEGER,
                    ic_pontua INTEGER,
                    co_status TEXT,
                    co_lote_migracao TEXT,
                    dh_inicio TEXT,
                    dh_fim TEXT,
                    nu_offset_minuto_j1 INTEGER,
                    nu_offset_minuto_j2 INTEGER,
                    qt_usos_poder INTEGER,
                    co_resultado TEXT
                )
                """
            )
            con.execute(f"CREATE VIEW partida.vw001_partida AS {select_sqlite}")

            # 1) Nomes e ordem exata das 21 colunas da VIEW.
            cur = con.execute("SELECT * FROM partida.vw001_partida")
            colunas_reais = [d[0] for d in cur.description]
            assert colunas_reais == COLUNAS_ESPERADAS_VW001

            # 2) Comportamento linha a linha: 1.3.1 (NULL) vs 1.4.0 (explícito).
            casos = [
                ("p1", 3, 2, 0, None, "venceu_j1", 0),
                ("p2", 2, 3, 0, None, "venceu_j2", 0),
                ("p3", 2, 2, 0, None, "empate", 0),
                # Controle da 1.3.1 nas damas 5×3: sem co_resultado, vale o placar.
                ("p4_131", 5, 3, 0, None, "venceu_j1", 0),
                # 1.4.0 nas damas 5×3 com empate explícito: vence o placar!
                ("p5_140", 5, 3, 2, "empate", "empate", 1),
                # 1.4.0 derrota explícita com mais peças: vence o placar!
                ("p6_140", 4, 1, 0, "venceu_j2", "venceu_j2", 1),
            ]
            for id_p, j1, j2, poder, res_gravado, res_esperado, info_esp in casos:
                con.execute(
                    """
                    INSERT INTO partida.tb001_partida
                        (id_partida, nu_placar_j1, nu_placar_j2, qt_usos_poder, co_resultado)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (id_p, j1, j2, poder, res_gravado),
                )

            lidas = con.execute(
                """
                SELECT id_partida, co_resultado, ic_com_poder, ic_resultado_informado
                  FROM partida.vw001_partida
                 ORDER BY id_partida
                """
            ).fetchall()

            assert lidas == [
                ("p1", "venceu_j1", 0, 0),
                ("p2", "venceu_j2", 0, 0),
                ("p3", "empate", 0, 0),
                ("p4_131", "venceu_j1", 0, 0),
                ("p5_140", "empate", 1, 1),
                ("p6_140", "venceu_j2", 0, 1),
            ]
        finally:
            con.close()

    def test_downgrade_derruba_e_recria_a_view_sem_a_coluna_nova(self):
        down = sem_comentarios_sql(_sql_do_downgrade(MIGRACAO_0038))
        assert re.search(r"DROP\s+VIEW\s+IF\s+EXISTS\s+partida\.vw001_partida", down, re.I)
        assert re.search(r"DROP\s+CONSTRAINT\s+IF\s+EXISTS\s+ck_partida_resultado", down, re.I)
        assert re.search(r"DROP\s+COLUMN\s+IF\s+EXISTS\s+co_resultado", down, re.I)
        assert re.search(r"CREATE\s+VIEW\s+partida\.vw001_partida\s+AS", down, re.I)
        assert "ic_resultado_informado" not in down


# ═══════════════════════════════════════════════════════════════════════════
# 4. Contrato HTTP (`POST /v1/sincronizacao/eventos` com o FakeRepoSincronizacao)
# ═══════════════════════════════════════════════════════════════════════════


class TestContratoRotaEventos:
    """Garante que a rota HTTP e o `FakeRepoSincronizacao` obedecem à mesma regra."""

    @pytest.fixture
    def cliente(self):
        c = TestClient(app)
        yield c
        app.dependency_overrides.clear()

    def _ligar(self, repo: FakeRepoSincronizacao, versao: str = "1.3.1") -> None:
        app.dependency_overrides[usuario_autenticado] = lambda: UsuarioAutenticado(
            id_usuario=DONO,
            co_usuario="2smgkp2h",
            contexto=ContextoRequisicao(
                versao_app=versao, plataforma="ios", idioma="pt"
            ),
        )
        app.dependency_overrides[obter_servico_sync] = lambda: ServicoSincronizacao(
            repo, FakeSession()
        )

    def test_rota_com_corpos_da_1_3_1_da_exatamente_os_numeros_de_hoje(
        self, cliente: TestClient
    ):
        repo = FakeRepoSincronizacao()
        self._ligar(repo, versao="1.3.1")

        lote = [
            _evento_1_3_1(co_evento="ev-1", id_partida="p-1", placar=(3, 2), xp=20),
            _evento_1_3_1(co_evento="ev-2", id_partida="p-2", placar=(2, 3), xp=10),
            _evento_1_3_1(co_evento="ev-3", id_partida="p-3", placar=(2, 2), xp=15),
            _evento_1_3_1(
                co_evento="ev-4",
                id_partida="p-4",
                co_jogo="damas",
                placar=(5, 3),
                xp=25,
            ),
        ]
        r = cliente.post("/v1/sincronizacao/eventos", json={"eventos": lote})

        assert r.status_code == 200
        corpo = r.json()
        assert corpo["aceitos"] == ["ev-1", "ev-2", "ev-3", "ev-4"]
        assert corpo["rejeitados"] == []
        assert corpo["falhas"] == []
        prog = corpo["progressao"]
        assert prog["nu_xp_total"] == 70
        assert prog["nu_partidas"] == 4
        assert prog["nu_vitorias"] == 2
        assert prog["nu_derrotas"] == 1
        assert prog["nu_empates"] == 1

    def test_rota_com_corpo_novo_conta_empate_de_damas_5x3(
        self, cliente: TestClient
    ):
        repo = FakeRepoSincronizacao()
        self._ligar(repo, versao="1.4.0")

        ev_empate = _evento_com_resultado(
            "empate",
            co_evento="ev-damas-empate",
            id_partida="p-damas-empate",
            co_jogo="damas",
            placar=(5, 3),
            xp=25,
        )
        r = cliente.post("/v1/sincronizacao/eventos", json={"eventos": [ev_empate]})

        assert r.status_code == 200
        corpo = r.json()
        assert corpo["aceitos"] == ["ev-damas-empate"]
        prog = corpo["progressao"]
        assert prog["nu_partidas"] == 1
        assert prog["nu_vitorias"] == 0
        assert prog["nu_derrotas"] == 0
        assert prog["nu_empates"] == 1

    def test_rota_com_co_resultado_invalido_aceita_partida_e_cai_no_placar(
        self, cliente: TestClient
    ):
        repo = FakeRepoSincronizacao()
        self._ligar(repo, versao="1.4.0")

        ev = _evento_com_resultado(
            "FORA_DO_DOMINIO",
            co_evento="ev-ruim",
            id_partida="p-ruim",
            placar=(1, 4),
            xp=10,
        )
        r = cliente.post("/v1/sincronizacao/eventos", json={"eventos": [ev]})

        assert r.status_code == 200
        corpo = r.json()
        assert corpo["aceitos"] == ["ev-ruim"]
        assert corpo["rejeitados"] == []
        assert corpo["falhas"] == []
        assert corpo["progressao"]["nu_derrotas"] == 1
