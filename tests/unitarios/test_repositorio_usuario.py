"""Testes do RepositorioUsuario (T014) — sem banco real.

Usamos uma **sessão falsa** que captura o SQL e os parâmetros. Assim validamos a
regra do projeto (LER pela VIEW `vwNNN`, ESCREVER na TABELA `tbNNN`) e a ligação
correta de parâmetros, sem precisar de um PostgreSQL de verdade.
"""
import asyncio

from api.conta.repositorio import RepositorioUsuario


class _ResultadoFake:
    """Imita o Result do SQLAlchemy: `.mappings().first()/.all()`."""

    def __init__(self, linhas):
        self._linhas = linhas

    def mappings(self):
        return self

    def first(self):
        return self._linhas[0] if self._linhas else None

    def all(self):
        return list(self._linhas)


class _SessaoFake:
    """Captura cada execute (SQL + params) e devolve linhas pré-configuradas."""

    def __init__(self, retorno=None):
        self.execucoes = []  # (sql_normalizado, params)
        self._retorno = retorno if retorno is not None else []
        self.commits = 0

    async def execute(self, stmt, params=None):
        # `str(stmt)` devolve o SQL do text(); normalizamos espaços para asserts.
        sql = " ".join(str(stmt).split())
        self.execucoes.append((sql, params))
        return _ResultadoFake(self._retorno)

    async def commit(self):
        self.commits += 1


def _ultimo_sql(sessao: _SessaoFake) -> str:
    return sessao.execucoes[-1][0]


def _ultimos_params(sessao: _SessaoFake) -> dict:
    return sessao.execucoes[-1][1]


# ── Leituras pela VIEW ───────────────────────────────────────────────────────


def test_buscar_por_identidade_externa_le_da_view():
    sessao = _SessaoFake(retorno=[{"id_usuario": "u1", "co_usuario": "abc12345"}])
    repo = RepositorioUsuario(sessao)
    achado = asyncio.run(repo.buscar_por_identidade_externa("firebase-uid-1"))

    assert achado["co_usuario"] == "abc12345"
    assert "conta.vw001_usuario" in _ultimo_sql(sessao)
    assert "tb001_usuario" not in _ultimo_sql(sessao)  # leitura NUNCA na tabela
    assert _ultimos_params(sessao) == {"id": "firebase-uid-1"}


def test_buscar_inexistente_devolve_none():
    sessao = _SessaoFake(retorno=[])  # nada encontrado
    repo = RepositorioUsuario(sessao)
    assert asyncio.run(repo.buscar_por_email("x@y.com")) is None
    assert "conta.vw001_usuario" in _ultimo_sql(sessao)


def test_listar_provedores_le_da_view002():
    sessao = _SessaoFake(retorno=[{"co_provedor": "google"}, {"co_provedor": "apple"}])
    repo = RepositorioUsuario(sessao)
    lista = asyncio.run(repo.listar_provedores("u1"))
    assert len(lista) == 2
    assert "conta.vw002_provedor_login" in _ultimo_sql(sessao)


# ── Escritas na TABELA ───────────────────────────────────────────────────────


def test_criar_escreve_na_tabela001_com_returning():
    linha = {"id_usuario": "u1", "co_usuario": "k7m3p9rt"}
    sessao = _SessaoFake(retorno=[linha])
    repo = RepositorioUsuario(sessao)

    criado = asyncio.run(
        repo.criar(
            co_usuario="k7m3p9rt",
            co_identidade_externa="uid-1",
            co_provedor_principal="google",
            no_email="a@b.com",
        )
    )
    sql = _ultimo_sql(sessao)
    assert criado["co_usuario"] == "k7m3p9rt"
    assert "INSERT INTO conta.tb001_usuario" in sql
    assert "RETURNING" in sql
    assert "vw001" not in sql  # escrita NUNCA na view
    assert _ultimos_params(sessao)["co_identidade_externa"] == "uid-1"


def test_vincular_provedor_e_idempotente():
    sessao = _SessaoFake(retorno=[{"id_provedor_login": "p1"}])
    repo = RepositorioUsuario(sessao)
    asyncio.run(
        repo.vincular_provedor(
            id_usuario="u1",
            co_provedor="google",
            co_identidade_provedor="sub-123",
        )
    )
    sql = _ultimo_sql(sessao)
    assert "INSERT INTO conta.tb002_provedor_login" in sql
    assert "ON CONFLICT" in sql  # idempotente


def test_registrar_aceite_legal_insere_em_tb003():
    sessao = _SessaoFake(retorno=[{"id_aceite_legal": "a1"}])
    repo = RepositorioUsuario(sessao)
    asyncio.run(
        repo.registrar_aceite_legal(
            id_usuario="u1",
            co_documento="privacidade",
            co_versao="1.0",
            co_idioma="pt",
        )
    )
    assert "INSERT INTO conta.tb003_aceite_legal" in _ultimo_sql(sessao)


def test_consentimento_faz_upsert_em_tb004():
    sessao = _SessaoFake(retorno=[{"id_consentimento": "c1"}])
    repo = RepositorioUsuario(sessao)
    asyncio.run(
        repo.definir_consentimento(
            id_usuario="u1", ic_rastreamento=True, ic_marketing=False
        )
    )
    sql = _ultimo_sql(sessao)
    assert "INSERT INTO conta.tb004_consentimento" in sql
    assert "ON CONFLICT (id_usuario) DO UPDATE" in sql


def test_atualizar_perfil_usa_coalesce_e_carimba_data():
    sessao = _SessaoFake(retorno=[{"id_usuario": "u1"}])
    repo = RepositorioUsuario(sessao)
    asyncio.run(repo.atualizar_perfil(id_usuario="u1", no_exibicao="Fernando"))
    sql = _ultimo_sql(sessao)
    assert "UPDATE conta.tb001_usuario" in sql
    assert "COALESCE(:no_exibicao, no_exibicao)" in sql
    assert "dh_atualizacao = now()" in sql
