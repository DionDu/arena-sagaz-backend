"""O CONTRATO DA EXTENSAO DO XADREZ, do lado do servidor (T109 da spec 012).

O app manda a partida pela sincronizacao de sempre, e o jogo entra como a chave
`xadrez`, na partida (com as recusas dentro) e em cada jogada
(`arena-sagaz-frontend/specs/012-jogo-xadrez/contracts/extensao-log-xadrez.md`).
Este arquivo confere o que o SERVIDOR faz com ela. O lado do app (os mapeadores
e o replay pelo motor, I-7) e testado no proprio app (T107).

AS TRAVESSIAS
-------------
- **X-1, app ANTIGO x backend NOVO.** A 1.5.0 nunca manda `xadrez`: o evento
  dela continua valendo como antes (SC-015).
- **X-2, a chave e CONHECIDA**: `xadrez` nao gera o aviso de "extensao
  desconhecida", nem na partida nem na jogada.
- **X-3, as dimensoes sao DO XADREZ** (procurar a acao dele na tabela do Quatro
  mandaria tudo ao sentinela).
- **X-4, o que o ingestor grava**, com uma sessao que anota cada comando: as
  invariantes do contrato do lado do servidor (I-1 a I-10), as recusas com e
  sem destino, o teto de 50 e as casas fora da forma.
- **X-5, o payload cabe**: cada texto que o app manda cabe na coluna (o
  `VARCHAR(n)` lido da 0039), e cada jogada que o app pode mandar passa nos
  `CHECK` da 0039, escritos aqui como predicados.
- **X-6, os codigos do MOTOR cabem nas dimensoes**: toda acao, motivo de
  parada e motivo de fim que o motor Rust (o fonte espelhado) emite tem linha
  na 0039. Um codigo que faltasse iria ao 9999 em toda partida, calado.

Estes testes sao de UNIDADE: nao ha Postgres. O banco de verdade e conferido
com uma partida jogada no `des`, depois da T068 (a 0039 aplicada).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest

from api.sincronizacao import dimensoes
from api.sincronizacao import repositorio as modulo_repositorio
from api.sincronizacao.repositorio import (
    _EXTENSOES_CONHECIDAS,
    RepositorioSincronizacao,
    _avisar_extensao_de_partida_desconhecida,
    _avisar_extensao_desconhecida,
)
from api.sincronizacao.validacao import validar_evento
from motores.xadrez import jogador_xadrez as jx
from tests.unitarios.leitura_de_migracao import sql_do_upgrade, tabelas_do_sql

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0039_schema_jogo_xadrez.py"
#: O `InicioXadrez` do app, no repositorio irmao (o Quatro le o motor de la do
#: mesmo jeito). Fora desta maquina, o caso que o le e pulado.
INICIO_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "lib"
    / "modulos"
    / "jogos"
    / "xadrez"
    / "logica"
    / "inicio_xadrez.dart"
)

# ── Amostras fieis ao contrato do log (extensao-log-xadrez.md §1-§2) ───────

FEN_INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#: Uma recusa com destino e uma sem (o toque numa peca sem lance, §8zzzz41).
RECUSAS = [
    {
        "nu_ordem": 7,
        "nu_sequencia": 1,
        "co_casa_origem": "e1",
        "co_casa_destino": "g1",
        "co_regra": "roque_atravessa_casa_atacada",
        "dh_recusa": "2026-11-19T12:00:00.000Z",
    },
    {
        "nu_ordem": 9,
        "nu_sequencia": 1,
        "co_casa_origem": "c8",
        "co_casa_destino": None,
        "co_regra": "peca_sem_lance",
        "dh_recusa": "2026-11-19T12:01:00.000Z",
    },
]

EXTENSAO_PARTIDA_XADREZ: dict[str, Any] = {
    "co_versao_motor": "rust_0.10.0",
    "co_versao_contrato": "1.5.0",
    "co_inicio": "adiantado",
    "co_fen_inicial": FEN_INICIAL,
    "co_cor_j1": "preta",
    "co_motivo_fim": "xeque_mate",
    "nu_semente_partida": -123456789,
    "js_extra": None,
    "recusas": RECUSAS,
}

#: Um lance da CPU: a telemetria inteira, com a semente (I-2, I-3).
EXTENSAO_JOGADA_CPU: dict[str, Any] = {
    "co_jogador": -1,
    "co_lance": "e7e5",
    "co_fen_antes": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "co_peca_movida": "peao",
    "co_peca_comida": None,
    "co_promocao": None,
    "co_lance_especial": None,
    "ic_xeque": False,
    "co_acao": "erro_sorteado",
    "qt_nos_visitados": 18734,
    "nu_profundidade_atingida": 2,
    "co_motivo_parada_busca": "nos",
    "nu_tempo_busca_ms": 41,
    "nu_avaliacao_brancas": 35,
    "nu_semente": 1834471023,
    "co_motor_busca": "rust",
    "js_extra": None,
}

#: Um lance do humano: a promocao a dama comendo a torre, e a telemetria
#: toda `None` (I-2).
EXTENSAO_JOGADA_HUMANO: dict[str, Any] = {
    "co_jogador": 1,
    "co_lance": "b7a8q",
    "co_fen_antes": "rn1qkbnr/1Pppppp1/2n5/8/8/8/1PPPPPPP/RNBQKBNR w KQk - 1 5",
    "co_peca_movida": "peao",
    "co_peca_comida": "torre",
    "co_promocao": "dama",
    "co_lance_especial": None,
    "ic_xeque": False,
    "co_acao": None,
    "qt_nos_visitados": None,
    "nu_profundidade_atingida": None,
    "co_motivo_parada_busca": None,
    "nu_tempo_busca_ms": None,
    "nu_avaliacao_brancas": None,
    "nu_semente": None,
    "co_motor_busca": None,
    "js_extra": None,
}

#: Os outros fatos que o app pode mandar, um de cada (para o X-5).
OUTRAS_JOGADAS = [
    {**EXTENSAO_JOGADA_HUMANO, "co_lance": "e1g1", "co_peca_movida": "rei",
     "co_peca_comida": None, "co_promocao": None,
     "co_lance_especial": "roque_curto"},
    {**EXTENSAO_JOGADA_HUMANO, "co_lance": "e1c1", "co_peca_movida": "rei",
     "co_peca_comida": None, "co_promocao": None,
     "co_lance_especial": "roque_longo"},
    {**EXTENSAO_JOGADA_HUMANO, "co_lance": "e5d6", "co_peca_movida": "peao",
     "co_peca_comida": "peao", "co_promocao": None,
     "co_lance_especial": "en_passant"},
    {**EXTENSAO_JOGADA_HUMANO, "co_lance": "h5f7", "co_peca_movida": "dama",
     "co_peca_comida": "peao", "co_promocao": None, "ic_xeque": True},
    {**EXTENSAO_JOGADA_HUMANO, "co_lance": "a7a8n", "co_peca_movida": "peao",
     "co_peca_comida": None, "co_promocao": "cavalo"},
]


def _jogada(**extras: Any) -> dict[str, Any]:
    """Uma jogada generica valida, com o que os extras acrescentarem."""
    base = {
        "id_jogada": "33333333-3333-3333-3333-333333333333",
        "nu_ordem": 1,
        "nu_jogador": 1,
        "dh_jogada": "2026-11-19T10:00:00.000",
        "nu_tempo_decisao_ms": 900,
        "co_origem_decisao": "humano",
    }
    base.update(extras)
    return base


def _partida(**extras: Any) -> dict[str, Any]:
    base = {
        "co_jogo": "xadrez",
        "co_variante": "tradicional",
        "nu_placar_j1": 1,
        "nu_placar_j2": 0,
    }
    base.update(extras)
    return base


def _evento(jogadas: list[dict[str, Any]], partida: dict[str, Any]) -> dict[str, Any]:
    return {
        "co_evento": "ev-xadrez",
        "co_tipo": "partida",
        "payload": {
            "partida": partida,
            "jogadas": jogadas,
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 75}],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# X-1 e X-2: o evento e as chaves
# ═══════════════════════════════════════════════════════════════════════════


class TestX1AppAntigoBackendNovo:
    def test_partida_sem_xadrez_continua_valida(self):
        """O payload de quem tem a 1.5.0, que nunca manda `xadrez`."""
        evento = _evento(
            [_jogada()], partida=_partida(co_jogo="quatro", co_variante="tradicional")
        )
        assert validar_evento(evento) is None

    def test_partida_do_xadrez_com_as_extensoes_e_valida(self):
        evento = _evento(
            [_jogada(xadrez=EXTENSAO_JOGADA_HUMANO)],
            partida=_partida(xadrez=EXTENSAO_PARTIDA_XADREZ),
        )
        assert validar_evento(evento) is None


class TestX2AChaveEConhecida:
    def test_xadrez_esta_entre_as_extensoes_conhecidas(self):
        assert "xadrez" in _EXTENSOES_CONHECIDAS

    def test_nem_a_partida_nem_a_jogada_geram_aviso(self, caplog):
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(
                _partida(xadrez=EXTENSAO_PARTIDA_XADREZ)
            )
            _avisar_extensao_desconhecida(_jogada(xadrez=EXTENSAO_JOGADA_CPU))
        assert caplog.records == []


# ═══════════════════════════════════════════════════════════════════════════
# X-3: as dimensoes
# ═══════════════════════════════════════════════════════════════════════════

DIMENSOES_DO_XADREZ = (
    "regra_recusa_xadrez",
    "motivo_parada_xadrez",
    "inicio_xadrez",
    "motivo_fim_xadrez",
    "acao_xadrez",
)


class TestX3AsDimensoesDoXadrez:
    @pytest.mark.parametrize("dimensao", DIMENSOES_DO_XADREZ)
    def test_leem_pela_VIEW_do_schema_do_xadrez(self, dimensao: str):
        view, _, _ = dimensoes._DIMENSOES[dimensao]
        assert view.startswith("jogo_xadrez.vw"), view

    @pytest.mark.parametrize("dimensao", DIMENSOES_DO_XADREZ)
    def test_a_VIEW_e_a_coluna_existem_na_0039(self, dimensao: str):
        """A view `vwNNN` nasce da `tbNNN` de mesmo numero (`SELECT *`), e as
        duas colunas lidas tem de estar nela."""
        view, codigo, chave = dimensoes._DIMENSOES[dimensao]
        tabela = view.replace(".vw", ".tb")
        colunas = dict(TABELAS_DA_0039[tabela]["colunas"])  # type: ignore[arg-type]
        assert codigo in colunas and chave in colunas, (tabela, colunas)

    def test_nao_colidem_com_as_dos_outros_jogos(self):
        do_xadrez = {dimensoes._DIMENSOES[d][0] for d in DIMENSOES_DO_XADREZ}
        dos_outros = {
            v[0]
            for nome, v in dimensoes._DIMENSOES.items()
            if nome not in DIMENSOES_DO_XADREZ
        }
        assert do_xadrez.isdisjoint(dos_outros)


# ═══════════════════════════════════════════════════════════════════════════
# X-4: o que o ingestor grava
# ═══════════════════════════════════════════════════════════════════════════


class _Resultado:
    """O resultado de um `execute`: `first()` devolve [linha]."""

    def __init__(self, linha: Any) -> None:
        self._linha = linha

    def first(self) -> Any:
        return self._linha


class _SessaoQueAnota:
    """Anota cada comando. O INSERT da jogada generica responde com [jogada_nova]:
    uma linha no `RETURNING` (gravou) ou `None` (ja estava gravada)."""

    def __init__(self, *, jogada_nova: bool = True) -> None:
        self.jogada_nova = jogada_nova
        self.comandos: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, comando: Any, parametros: dict[str, Any] | None = None):
        sql = str(comando)
        self.comandos.append((sql, parametros or {}))
        if "INSERT INTO partida.tb002_jogada" in sql:
            return _Resultado(("id",) if self.jogada_nova else None)
        return _Resultado(None)

    def parametros_de(self, tabela: str) -> list[dict[str, Any]]:
        """Os parametros de cada INSERT em [tabela], na ordem."""
        return [p for sql, p in self.comandos if f"INSERT INTO {tabela}" in sql]


def _linhas_das_dimensoes() -> dict[str, dict[str, int]]:
    """O que cada dimensao do banco responderia: as linhas da 0039, lidas do
    SQL que o `upgrade` executa (e nao copiadas a mao aqui)."""
    sql = SQL_DA_0039
    linhas: dict[str, dict[str, int]] = {}
    for dimensao in DIMENSOES_DO_XADREZ:
        tabela = dimensoes._DIMENSOES[dimensao][0].replace(".vw", ".tb")
        inicio = sql.index(f"INSERT INTO {tabela}")
        trecho = sql[inicio : sql.index("CREATE TABLE", inicio)]
        linhas[dimensao] = {
            c: int(n) for n, c in re.findall(r"\(\s*(\d+)\s*,\s*'([a-z_]+)'", trecho)
        }
    linhas["origem_decisao"] = {"humano": 1, "cpu": 2, "timeout_auto": 3}
    return linhas


SQL_DA_0039 = sql_do_upgrade(MIGRACAO)
TABELAS_DA_0039 = tabelas_do_sql(SQL_DA_0039)
LINHAS_DA_0039 = _linhas_das_dimensoes()


@pytest.fixture
def dimensoes_da_0039(monkeypatch):
    """Troca a leitura do banco pelas linhas da 0039: o codigo conhecido vira o
    numero dele, o desconhecido vira 9999, e o vazio vira `None`."""

    async def resolver(_sessao, dimensao: str, valor: Any):
        if valor is None or valor == "":
            return None, False
        numero = LINHAS_DA_0039.get(dimensao, {}).get(str(valor))
        if numero is None:
            return dimensoes.NU_DESCONHECIDO, True
        return numero, False

    monkeypatch.setattr(modulo_repositorio.dimensoes, "resolver", resolver)


def _repo(sessao: _SessaoQueAnota) -> RepositorioSincronizacao:
    return RepositorioSincronizacao(sessao)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_a_extensao_de_partida_vai_inteira_com_os_codigos_traduzidos(
    dimensoes_da_0039,
):
    """I-1: o app manda TEXTO (`adiantado`, `xeque_mate`); o banco guarda o
    numero da dimensao. A versao do motor vai como veio (sem o `dart_` que a
    normalizacao das damas acrescentaria)."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_partida_xadrez("p1", EXTENSAO_PARTIDA_XADREZ)
    [p] = sessao.parametros_de("jogo_xadrez.tb001_partida")
    assert p == {
        "id_partida": "p1",
        "co_versao_motor": "rust_0.10.0",
        "co_versao_contrato": "1.5.0",
        "nu_inicio": LINHAS_DA_0039["inicio_xadrez"]["adiantado"],
        "co_fen_inicial": FEN_INICIAL,
        "co_cor_j1": "preta",
        "nu_motivo_fim": LINHAS_DA_0039["motivo_fim_xadrez"]["xeque_mate"],
        "nu_semente_partida": -123456789,
        "js_extra": None,
    }
    assert p["nu_inicio"] == 2 and p["nu_motivo_fim"] == 1


@pytest.mark.asyncio
async def test_a_partida_que_nao_acabou_no_tabuleiro_vai_sem_motivo(
    dimensoes_da_0039,
):
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_partida_xadrez(
        "p1", {**EXTENSAO_PARTIDA_XADREZ, "co_motivo_fim": None}
    )
    assert sessao.parametros_de("jogo_xadrez.tb001_partida")[0]["nu_motivo_fim"] is None


@pytest.mark.asyncio
async def test_inicio_e_fim_desconhecidos_vao_ao_9999_com_o_texto_cru(
    dimensoes_da_0039,
):
    """I-1: um app mais novo, com um inicio e um fim que este banco nao conhece."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_partida_xadrez(
        "p1",
        {
            **EXTENSAO_PARTIDA_XADREZ,
            "co_inicio": "xadrez960",
            "co_motivo_fim": "desistencia",
        },
    )
    [p] = sessao.parametros_de("jogo_xadrez.tb001_partida")
    assert p["nu_inicio"] == dimensoes.NU_DESCONHECIDO
    assert p["nu_motivo_fim"] == dimensoes.NU_DESCONHECIDO
    assert json.loads(p["js_extra"]) == {
        "co_inicio_desconhecido": "xadrez960",
        "co_motivo_fim_desconhecido": "desistencia",
    }


@pytest.mark.asyncio
async def test_inicio_ausente_vai_ao_9999_e_nao_estoura_o_NOT_NULL(
    dimensoes_da_0039,
):
    sessao = _SessaoQueAnota()
    sem_inicio = {k: v for k, v in EXTENSAO_PARTIDA_XADREZ.items() if k != "co_inicio"}
    await _repo(sessao)._gravar_partida_xadrez("p1", sem_inicio)
    assert (
        sessao.parametros_de("jogo_xadrez.tb001_partida")[0]["nu_inicio"]
        == dimensoes.NU_DESCONHECIDO
    )


@pytest.mark.asyncio
async def test_as_recusas_vao_com_e_sem_destino(dimensoes_da_0039):
    """A recusa sem destino (o toque numa peca sem lance) vai com `NULL`
    (§8zzzz41); a regra vira o numero da `tb901`."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_partida_xadrez("p1", EXTENSAO_PARTIDA_XADREZ)
    recusas = sessao.parametros_de("jogo_xadrez.tb003_recusa")
    assert [
        (r["nu_ordem"], r["co_casa_origem"], r["co_casa_destino"], r["nu_regra"])
        for r in recusas
    ] == [
        (7, "e1", "g1", 9),
        (9, "c8", None, 11),
    ]
    assert all(r["id_partida"] == "p1" and r["id_recusa"] for r in recusas)
    # O instante vira `datetime` (o asyncpg nao aceita a string ISO).
    assert recusas[0]["dh_recusa"].year == 2026


@pytest.mark.asyncio
async def test_I9_o_teto_de_50_descarta_o_excedente_e_aceita_a_partida(
    dimensoes_da_0039, caplog
):
    sessao = _SessaoQueAnota()
    muitas = [
        {**RECUSAS[0], "nu_ordem": 1, "nu_sequencia": i + 1} for i in range(70)
    ]
    with caplog.at_level(logging.WARNING):
        await _repo(sessao)._gravar_partida_xadrez(
            "p1", {**EXTENSAO_PARTIDA_XADREZ, "recusas": muitas}
        )
    assert len(sessao.parametros_de("jogo_xadrez.tb003_recusa")) == 50
    # A partida entrou.
    assert len(sessao.parametros_de("jogo_xadrez.tb001_partida")) == 1
    assert "70 recusas" in caplog.text


@pytest.mark.asyncio
async def test_casa_fora_da_forma_nao_estoura_o_CHECK(dimensoes_da_0039, caplog):
    """A origem ruim descarta a recusa; o destino ruim vira `NULL`. Um 500 aqui
    travaria a fila do aparelho para sempre."""
    sessao = _SessaoQueAnota()
    with caplog.at_level(logging.WARNING):
        await _repo(sessao)._gravar_recusas_xadrez(
            "p1",
            [
                {**RECUSAS[0], "co_casa_origem": "e9"},
                {**RECUSAS[0], "nu_sequencia": 2, "co_casa_destino": "z1"},
                {**RECUSAS[0], "nu_sequencia": 3, "co_regra": "regra_do_futuro"},
            ],
        )
    gravadas = sessao.parametros_de("jogo_xadrez.tb003_recusa")
    assert [(r["nu_sequencia"], r["co_casa_destino"]) for r in gravadas] == [
        (2, None),
        (3, "g1"),
    ]
    # A regra desconhecida vai ao sentinela, e a recusa entra.
    assert gravadas[1]["nu_regra"] == dimensoes.NU_DESCONHECIDO
    assert "'e9'" in caplog.text


@pytest.mark.asyncio
async def test_o_lance_da_CPU_vai_com_a_telemetria_traduzida(dimensoes_da_0039):
    """I-2, I-3, I-8: a telemetria, a semente e a nota no referencial das
    brancas, como vieram; a acao e a parada viram os numeros da 0039."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada(
        "p1",
        _jogada(nu_jogador=2, co_origem_decisao="cpu", xadrez=EXTENSAO_JOGADA_CPU),
    )
    [p] = sessao.parametros_de("jogo_xadrez.tb002_jogada")
    assert p["co_jogador"] == -1
    assert p["co_lance"] == "e7e5"
    assert p["nu_acao"] == 2  # erro_sorteado
    assert p["nu_motivo_parada_busca"] == 2  # nos
    assert p["qt_nos_visitados"] == 18734
    assert p["nu_semente"] == 1834471023
    assert p["nu_avaliacao_brancas"] == 35
    assert p["co_motor_busca"] == "rust"
    assert p["ic_xeque"] is False
    assert p["js_extra"] is None


@pytest.mark.asyncio
async def test_o_lance_do_humano_vai_sem_telemetria_e_com_os_fatos(
    dimensoes_da_0039,
):
    """I-2: nada inventado no lance de quem joga; `NULL` e a verdade."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada("p1", _jogada(xadrez=EXTENSAO_JOGADA_HUMANO))
    [p] = sessao.parametros_de("jogo_xadrez.tb002_jogada")
    for campo in (
        "nu_acao",
        "qt_nos_visitados",
        "nu_profundidade_atingida",
        "nu_motivo_parada_busca",
        "nu_tempo_busca_ms",
        "nu_avaliacao_brancas",
        "nu_semente",
        "co_motor_busca",
    ):
        assert p[campo] is None, campo
    assert (p["co_peca_movida"], p["co_peca_comida"], p["co_promocao"]) == (
        "peao",
        "torre",
        "dama",
    )


@pytest.mark.asyncio
async def test_acao_e_parada_desconhecidas_vao_ao_9999_com_o_texto_cru(
    dimensoes_da_0039,
):
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada(
        "p1",
        _jogada(
            nu_jogador=2,
            co_origem_decisao="cpu",
            xadrez={
                **EXTENSAO_JOGADA_CPU,
                "co_acao": "livro_de_aberturas",
                "co_motivo_parada_busca": "memoria",
            },
        ),
    )
    [p] = sessao.parametros_de("jogo_xadrez.tb002_jogada")
    assert p["nu_acao"] == dimensoes.NU_DESCONHECIDO
    assert p["nu_motivo_parada_busca"] == dimensoes.NU_DESCONHECIDO
    assert json.loads(p["js_extra"]) == {
        "co_acao_desconhecido": "livro_de_aberturas",
        "co_motivo_parada_busca_desconhecido": "memoria",
    }


@pytest.mark.asyncio
async def test_xeque_None_vira_falso_e_nao_estoura_o_NOT_NULL(dimensoes_da_0039):
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada(
        "p1", _jogada(xadrez={**EXTENSAO_JOGADA_HUMANO, "ic_xeque": None})
    )
    assert sessao.parametros_de("jogo_xadrez.tb002_jogada")[0]["ic_xeque"] is False


@pytest.mark.asyncio
async def test_campo_desconhecido_no_objeto_xadrez_e_ignorado(dimensoes_da_0039):
    """Compatibilidade (§4 do contrato): o app mais novo pode mandar campos que
    este backend nao conhece; eles nao viram coluna nem erro."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada(
        "p1", _jogada(xadrez={**EXTENSAO_JOGADA_HUMANO, "co_campo_do_futuro": "x"})
    )
    await _repo(sessao)._gravar_partida_xadrez(
        "p1", {**EXTENSAO_PARTIDA_XADREZ, "qt_campo_do_futuro": 3}
    )
    [j] = sessao.parametros_de("jogo_xadrez.tb002_jogada")
    [p] = sessao.parametros_de("jogo_xadrez.tb001_partida")
    assert "co_campo_do_futuro" not in j and "qt_campo_do_futuro" not in p


@pytest.mark.asyncio
async def test_I10_a_jogada_ja_gravada_nao_regrava_a_extensao(dimensoes_da_0039):
    """O reenvio da fita (a jogada desfeita pelo "voltar jogada" sobe de novo
    com `ic_cancelada`): a extensao ja esta la, com o FEN de quando foi jogada,
    e grava-la de novo estouraria a PK da 1:1."""
    sessao = _SessaoQueAnota(jogada_nova=False)
    await _repo(sessao)._gravar_jogada("p1", _jogada(xadrez=EXTENSAO_JOGADA_HUMANO))
    assert sessao.parametros_de("jogo_xadrez.tb002_jogada") == []


# ═══════════════════════════════════════════════════════════════════════════
# X-5: o payload cabe nas colunas e nos CHECK da 0039
# ═══════════════════════════════════════════════════════════════════════════


def _tamanhos(tabela: str) -> dict[str, int]:
    """`{coluna: n}` de cada `VARCHAR(n)` da [tabela], lido da 0039."""
    colunas = TABELAS_DA_0039[tabela]["colunas"]  # type: ignore[index]
    tamanhos = {}
    for nome, tipo in colunas:  # type: ignore[union-attr]
        casou = re.match(r"VARCHAR\((\d+)\)", tipo)
        if casou:
            tamanhos[nome] = int(casou.group(1))
    return tamanhos


def _cabe(parametros: dict[str, Any], tabela: str) -> list[str]:
    """As colunas de texto de [tabela] em que o valor NAO cabe."""
    return [
        f"{coluna}={parametros[coluna]!r} > {n}"
        for coluna, n in _tamanhos(tabela).items()
        if isinstance(parametros.get(coluna), str) and len(parametros[coluna]) > n
    ]


PECAS = {"peao", "cavalo", "bispo", "torre", "dama", "rei"}


def _passa_nos_checks_da_jogada(p: dict[str, Any]) -> list[str]:
    """Os `CHECK` da `tb002_jogada` da 0039, um predicado cada, na ordem."""
    falhas = []
    if p["co_jogador"] not in (1, -1):
        falhas.append("ck_xadrez_jogador")
    if p["co_motor_busca"] not in (None, "dart", "rust"):
        falhas.append("ck_xadrez_motor_busca")
    if p["co_peca_movida"] not in PECAS:
        falhas.append("ck_xadrez_peca_movida")
    if p["co_peca_comida"] not in (None, *(PECAS - {"rei"})):
        falhas.append("ck_xadrez_peca_comida")
    if p["co_promocao"] is not None and not (
        p["co_peca_movida"] == "peao"
        and p["co_promocao"] in {"dama", "torre", "bispo", "cavalo"}
    ):
        falhas.append("ck_xadrez_promocao")
    especial = p["co_lance_especial"]
    if not (
        especial is None
        or (especial in ("roque_curto", "roque_longo") and p["co_peca_movida"] == "rei")
        or (
            especial == "en_passant"
            and p["co_peca_movida"] == "peao"
            and p["co_peca_comida"] == "peao"
        )
    ):
        falhas.append("ck_xadrez_lance_especial")
    if p["qt_nos_visitados"] is not None and p["nu_semente"] is None:
        falhas.append("ck_xadrez_semente_da_cpu")
    return falhas


def test_os_predicados_sao_os_CHECK_da_0039():
    """Os nomes dos predicados acima sao todos os CHECK da tabela, e so eles:
    um CHECK novo na migracao cobra um predicado novo aqui."""
    checks = {
        nome
        for nome, especie in TABELAS_DA_0039["jogo_xadrez.tb002_jogada"][
            "constraints"
        ].items()  # type: ignore[union-attr]
        if especie == "CHECK"
    }
    assert checks == {
        "ck_xadrez_jogador",
        "ck_xadrez_motor_busca",
        "ck_xadrez_peca_movida",
        "ck_xadrez_peca_comida",
        "ck_xadrez_promocao",
        "ck_xadrez_lance_especial",
        "ck_xadrez_semente_da_cpu",
    }


def test_os_predicados_pegam_o_que_o_banco_recusaria():
    """O controle: sem isto, um predicado que nunca falha passaria tudo."""
    ruins = {
        "ck_xadrez_peca_comida": {**EXTENSAO_JOGADA_HUMANO, "co_peca_comida": "rei"},
        "ck_xadrez_promocao": {**EXTENSAO_JOGADA_HUMANO, "co_peca_movida": "torre"},
        "ck_xadrez_lance_especial": {
            **EXTENSAO_JOGADA_HUMANO,
            "co_lance_especial": "roque_curto",
        },
        "ck_xadrez_semente_da_cpu": {**EXTENSAO_JOGADA_CPU, "nu_semente": None},
    }
    for check, jogada in ruins.items():
        assert check in _passa_nos_checks_da_jogada(jogada), check


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extensao",
    [EXTENSAO_JOGADA_CPU, EXTENSAO_JOGADA_HUMANO, *OUTRAS_JOGADAS],
    ids=lambda e: e["co_lance"],
)
async def test_cada_jogada_que_o_app_manda_cabe_e_passa_nos_CHECK(
    dimensoes_da_0039, extensao: dict[str, Any]
):
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_jogada("p1", _jogada(xadrez=extensao))
    [p] = sessao.parametros_de("jogo_xadrez.tb002_jogada")
    assert _cabe(p, "jogo_xadrez.tb002_jogada") == []
    assert _passa_nos_checks_da_jogada(p) == []


@pytest.mark.asyncio
async def test_a_partida_e_as_recusas_cabem(dimensoes_da_0039):
    """`branca` tem 6 letras, exatamente o `VARCHAR(6)`; a versao do motor
    composta com um 2o motor ainda cabe nos 60."""
    sessao = _SessaoQueAnota()
    await _repo(sessao)._gravar_partida_xadrez(
        "p1",
        {
            **EXTENSAO_PARTIDA_XADREZ,
            "co_cor_j1": "branca",
            "co_versao_motor": "rust_0.10.0|dart_10.10.10",
        },
    )
    [p] = sessao.parametros_de("jogo_xadrez.tb001_partida")
    assert _cabe(p, "jogo_xadrez.tb001_partida") == []
    assert p["co_cor_j1"] in ("branca", "preta")
    for r in sessao.parametros_de("jogo_xadrez.tb003_recusa"):
        assert _cabe(r, "jogo_xadrez.tb003_recusa") == []


# ═══════════════════════════════════════════════════════════════════════════
# X-6: os codigos do motor cabem nas dimensoes
# ═══════════════════════════════════════════════════════════════════════════


def _codigos_do_match(arquivo: str, tipo: str) -> set[str]:
    """Os textos de `Tipo::Variante => "codigo"` no fonte espelhado do motor."""
    fonte = (jx.FONTES_DO_MOTOR / "src" / arquivo).read_text(encoding="utf-8")
    return set(re.findall(rf'{tipo}::\w+\s*=>\s*"([a-z_]+)"', fonte))


@pytest.mark.parametrize(
    ("arquivo", "tipo", "dimensao", "minimo"),
    [
        (
            "niveis.rs",
            "Acao",
            "acao_xadrez",
            {"busca_melhor", "erro_sorteado", "cegueira", "mate_em_um", "lance_unico"},
        ),
        (
            "busca.rs",
            "Parada",
            "motivo_parada_xadrez",
            {"profundidade", "nos", "tempo", "decidido", "lance_unico"},
        ),
        (
            "fim_de_partida.rs",
            "Motivo",
            "motivo_fim_xadrez",
            {
                "xeque_mate",
                "afogamento",
                "material_insuficiente",
                "repeticao_tripla",
                "cinquenta_lances",
            },
        ),
    ],
)
def test_todo_codigo_que_o_motor_emite_esta_na_dimensao(
    arquivo: str, tipo: str, dimensao: str, minimo: set[str]
):
    do_motor = _codigos_do_match(arquivo, tipo)
    # A leitura nao pode falhar em silencio: os de hoje tem de estar la.
    assert minimo <= do_motor, do_motor
    assert do_motor <= set(LINHAS_DA_0039[dimensao]), (
        do_motor - set(LINHAS_DA_0039[dimensao])
    )


@pytest.mark.skipif(not INICIO_DO_APP.exists(), reason="sem o repositorio do app")
def test_os_inicios_do_app_estao_na_dimensao():
    """O `enum InicioXadrez` do app (o `co_inicio` sai do nome dele)."""
    fonte = INICIO_DO_APP.read_text(encoding="utf-8")
    corpo = fonte[fonte.index("enum InicioXadrez {") :]
    corpo = corpo[: corpo.index("}")]
    # Os valores do `enum`: as linhas que sao so um nome seguido de virgula.
    sem_comentarios = re.sub(r"//[^\n]*", "", corpo)
    valores = set(re.findall(r"\b([a-z][a-zA-Z]*)\s*,", sem_comentarios))
    assert valores == {"tradicional", "adiantado", "desafio"}, valores
    assert valores <= set(LINHAS_DA_0039["inicio_xadrez"])
