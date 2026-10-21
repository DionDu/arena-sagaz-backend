"""O desafio do Quatro em Linha num app 1.3.1: a tela de atualizar, e a chama (T122).

⚠️ **Nada aqui é código novo: é a CONFERÊNCIA de um caminho que já existe**
(RF-DES-021/024, spec 009), agora com o primeiro jogo que o app em campo não
tem. O Quatro chega na 1.4.0; quem está na 1.3.1 e abre o app num dia de desafio
do Quatro precisa (1) receber o desafio, (2) cair na tela de atualizar e (3)
**não perder a chama** por isso. Os três passos atravessam a porta HTTP de
verdade, com o cabeçalho `X-App-Version: 1.3.1`:

  1. `GET /v1/desafios/hoje` ENTREGA o desafio do Quatro ao 1.3.1. ⛔ O servidor
     não filtra por versão, e é de propósito: quem decide é o app
     (`compatibilidade.dart`, idêntico na tag `v1.3.1+16` e no HEAD de
     21/10/2026), que confere o jogo antes de tudo e responde
     `jogo_desconhecido`. A metade do app está em
     `arena-sagaz-frontend/test/modulos/desafio_do_dia/logica/compatibilidade_test.dart`
     (grupo "T122"), com esta mesma resposta;
  2. `POST /v1/desafios/impedido` grava o dia em
     `desafio_dia.tb007_desafio_impedido`, com a versão lida do CABEÇALHO e a
     versão exigida lida do BANCO - os dois lados do par de diagnóstico;
  3. o ramo da chama que lê os dias impedidos, **copiado do SQL de
     `recalcular_chama`** (e não reescrito aqui), devolve esse dia, e a
     sequência sobrevive a ele.

O banco é o SQLite de memória de `banco_de_aparelho_sqlite.py`, com as tabelas
do dia impedido acrescentadas aqui na forma da migração `0021`. ⚠️ O que ele
não prova é o que é só do Postgres (o `UUID`, o `JSONB`, o `AT TIME ZONE` do
outro ramo da chama); a prova contra o Postgres de verdade é a T125, quando o
desafio do Quatro existir no `des`.

⚠️ **O desafio é montado com as peças REAIS do job** (a receita, o editorial e
a posição reproduzida pelo árbitro), e não com um dicionário escrito à mão: é
a forma exata que o 1.3.1 vai ler, e um campo que o parser dele exige e que o
Quatro deixasse de mandar apareceria aqui.
"""
from __future__ import annotations

import inspect
import re
import sqlite3
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.aparelhos.dependencias import obter_servico_aparelho
from api.aparelhos.regras import chave_da_versao
from api.aparelhos.repositorio import RepositorioAparelho
from api.aparelhos.servico import ServicoAparelho
from api.desafios import impedido as modulo_impedido
from api.desafios import rotas as rotas_desafios
from api.desafios.impedido import RepositorioImpedido
from api.desafios.rotas import obter_repositorio, obter_repositorio_impedido
from api.main import app
from api.nucleo.dependencias import ContextoRequisicao, exigir_cabecalhos, usuario_atual_opcional
from api.nucleo.dependencias_conta_nuvem import UsuarioAutenticado, usuario_autenticado
from api.sincronizacao.repositorio import RepositorioSincronizacao, calcular_sequencia_de_dias
from job.editorial import EDITORIAL, ENCOSTADAS_NA_POSICAO, VERSAO_MINIMA_DO_QUATRO
from job.posicao_inicial import do_quatro
from job.tipos_de_desafio import RECEITAS
from tests.unitarios.banco_de_aparelho_sqlite import abrir_banco, linhas, trocar_cast_jsonb
from tests.unitarios.test_rotas_desafio_publicado import RepoFalso, _linha

# O `sqlite3` não sabe guardar `UUID` nem `datetime` sem adaptador. A rota manda
# os dois (o `id_desafio_dia` do corpo e o `visitado_em`), que é o que o asyncpg
# espera; aqui eles viram texto, que é como o SQLite os guarda de todo jeito.
sqlite3.register_adapter(uuid.UUID, str)
sqlite3.register_adapter(datetime, lambda d: d.isoformat())

ID_USUARIO = "63385354-1e03-44bc-b2a3-82fdb8e34547"

#: 01h30 UTC de 20/10: ainda 22h30 de **19/10** no Brasil. É o instante que
#: separa o dia UTC do dia local - a chama conta o local.
MADRUGADA_UTC = datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc)
DIA_LOCAL = date(2026, 10, 19)

#: O app 1.3.1 em campo: só os cabeçalhos de sempre (ele não manda o código da
#: instalação nem o fuso, que chegaram na 1.4).
CABECALHOS_1_3 = {"X-App-Version": "1.3.1", "X-Platform": "android", "Accept-Language": "pt-BR"}

#: O trecho do SQL do dia impedido que o SQLite não entende, e o que entra no
#: lugar dele. Ver `trocar_cast_jsonb` (o mesmo cuidado, pelo mesmo motivo: no
#: SQLite o `CAST(x AS JSONB)` não dá erro, ele vira `NUMERIC` e grava zero).
CAST_MOTORES = "CAST(:js_motores AS JSONB)"

#: As tabelas do dia impedido, na forma mais próxima da `0021` que o SQLite
#: aceita (os nomes e a ordem das colunas são os da migração). A `un001` é o
#: que faz o `ON CONFLICT (id_usuario, dt_dia_local)` valer.
#:
#: ⚠️ As duas `vw001` são tabelas aqui, com só as colunas que a subconsulta da
#: versão exigida lê: é ela que põe o "1.4.0" ao lado do "1.3.1" na linha.
_ESQUEMA_DO_DIA_IMPEDIDO = (
    "ATTACH DATABASE ':memory:' AS desafio_dia",
    "ATTACH DATABASE ':memory:' AS desafio",
    """
    CREATE TABLE desafio_dia.tb007_desafio_impedido (
        id_desafio_impedido      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        id_usuario               TEXT NOT NULL,
        dt_dia_local             TEXT NOT NULL,
        dh_visita                TEXT NOT NULL,
        nu_offset_minuto         INTEGER,
        id_desafio_dia           TEXT,
        co_motivo                TEXT NOT NULL,
        co_desconhecido          TEXT,
        co_versao_app            TEXT,
        co_plataforma            TEXT,
        co_versao_minima_exigida TEXT,
        js_motores               TEXT,
        dh_registro              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT un001_dia_impedido UNIQUE (id_usuario, dt_dia_local)
    )
    """,
    # A view mora no MESMO banco anexado da tabela e a cita sem prefixo: no
    # SQLite uma view de banco anexado só enxerga o próprio banco.
    "CREATE VIEW desafio_dia.vw007_desafio_impedido AS SELECT * FROM tb007_desafio_impedido",
    "CREATE TABLE desafio_dia.vw001_desafio_dia (id_desafio_dia TEXT, id_desafio TEXT)",
    "CREATE TABLE desafio.vw001_desafio (id_desafio TEXT, co_versao_minima TEXT)",
)


def _linha_do_quatro() -> dict:
    """O desafio de hoje do Quatro, como `repositorio.py` o devolveria.

    ⚠️ Parte da linha de damas de `test_rotas_desafio_publicado.py` (a régua de
    tempo, a régua da nota, as datas) e troca **tudo o que é do jogo** pelo que
    o job grava de verdade para a `quatro_virada`, o tipo do Quatro que está no
    ar desde a T124b.
    """
    receita = RECEITAS["quatro_virada"]
    publicacao = EDITORIAL["quatro_virada"][0]
    linha = _linha(co_jogo="quatro", co_formato="sequencia_lances")
    linha.update(
        co_modalidade="tradicional",
        # ⚠️ A variante do Quatro É a modalidade (`job/gerador.py`), como nas damas.
        co_variante="tradicional",
        # A posição reproduzida pelo árbitro: doze lances de preparo, como a
        # `nu_lances_de_preparo` da publicação.
        js_posicao_inicial=do_quatro(
            ["s4", "s4", "s3", "s5", "s3", "s2", "s4", "s3", "s5", "s6", "s2", "s1"],
            co_modalidade="tradicional",
        ),
        co_tipo_desafio=receita.co_tipo_desafio,
        js_chegada=receita.montar({}),
        co_chave_objetivo=receita.co_chave_objetivo,
        js_objetivo=receita.valores_da_frase({}, "tex"),
        co_personagem="tex",
        co_versao_minima=publicacao.co_versao_minima,
        medidas_de_saida=publicacao.medidas({ENCOSTADAS_NA_POSICAO: 4}),
    )
    return linha


def _dono_pelo_cabecalho(
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
) -> UsuarioAutenticado:
    """O dono da requisição, com o contexto lido dos CABEÇALHOS de verdade.

    ⚠️ Só a busca da conta pelo uid do Firebase fica de fora (ela tem o seu
    cadeado em `test_desafio_impedido.py`). O `exigir_cabecalhos` é o real: é
    ele que põe o "1.3.1" na linha, e um contexto escrito à mão aqui provaria
    só que o teste sabe escrever "1.3.1".
    """
    return UsuarioAutenticado(id_usuario=ID_USUARIO, co_usuario="ana", contexto=contexto)


@pytest_asyncio.fixture
async def banco(monkeypatch):
    """A sessão do SQLite ligada às três rotas, com o desafio do Quatro no ar."""
    trocar_cast_jsonb(monkeypatch)
    assert CAST_MOTORES in modulo_impedido.SQL_GRAVAR_IMPEDIDO, (
        "o dia impedido já não grava os motores com CAST: confira a troca abaixo"
    )
    monkeypatch.setattr(
        modulo_impedido,
        "SQL_GRAVAR_IMPEDIDO",
        modulo_impedido.SQL_GRAVAR_IMPEDIDO.replace(CAST_MOTORES, ":js_motores"),
    )

    engine, sessao = await abrir_banco()
    for comando in _ESQUEMA_DO_DIA_IMPEDIDO:
        await sessao.execute(text(comando))

    linha = _linha_do_quatro()
    # O dia e o desafio, para a subconsulta da versão exigida achar o "1.4.0".
    await sessao.execute(
        text("INSERT INTO desafio_dia.vw001_desafio_dia VALUES (:dia, :desafio)"),
        {"dia": str(linha["id_desafio_dia"]), "desafio": str(linha["id_desafio"])},
    )
    await sessao.execute(
        text("INSERT INTO desafio.vw001_desafio VALUES (:desafio, :versao)"),
        {"desafio": str(linha["id_desafio"]), "versao": linha["co_versao_minima"]},
    )
    await sessao.commit()

    app.dependency_overrides[obter_servico_aparelho] = lambda: ServicoAparelho(
        repo=RepositorioAparelho(sessao), sessao=sessao
    )
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=linha)
    app.dependency_overrides[obter_repositorio_impedido] = lambda: RepositorioImpedido(sessao)
    app.dependency_overrides[usuario_autenticado] = _dono_pelo_cabecalho
    monkeypatch.setattr(rotas_desafios, "agora_utc", lambda: MADRUGADA_UTC)
    yield sessao, linha
    app.dependency_overrides.clear()
    await sessao.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def cliente():
    """O cliente HTTP no mesmo laço de eventos da sessão do SQLite.

    ⚠️ `AsyncClient` + `ASGITransport`, e não o `TestClient`: ver o cabeçalho de
    `test_rotas_do_aparelho.py`.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as c:
        yield c


def _corpo_do_impedido(linha: dict) -> dict:
    """O que o 1.3.1 manda (`registro_de_impedimento.dart` da tag `v1.3.1+16`)."""
    return {
        "id_desafio_dia": str(linha["id_desafio_dia"]),
        "motivo": "jogo_desconhecido",
        "desconhecido": "quatro",
        "visitado_em": MADRUGADA_UTC.isoformat(),
        "nu_offset_minuto": -180,
    }


async def _impedidos(sessao) -> list[dict]:
    return await linhas(
        sessao,
        "SELECT dt_dia_local, co_motivo, co_desconhecido, co_versao_app, "
        "co_plataforma, co_versao_minima_exigida FROM desafio_dia.vw007_desafio_impedido",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. O servidor entrega; quem decide é o app
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_1_3_RECEBE_o_desafio_do_quatro_com_a_versao_minima_dele(banco, cliente):
    """⚠️ O servidor não esconde o desafio de quem não pode jogá-lo.

    Esconder faria o 1.3.1 ver "sem desafio hoje" - e a pessoa não saberia que
    existe versão nova, nem gravaria o dia impedido. Quem o recusa é o app, e
    ele precisa do desafio para isso.
    """
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_3)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["jogo"] == "quatro"
    assert corpo["modalidade"] == "tradicional"
    assert corpo["formato_posicao"] == "sequencia_lances"
    assert corpo["versao_minima_app"] == VERSAO_MINIMA_DO_QUATRO == "1.4.0"
    # E a versão do app em campo é MENOR que a exigida, pela régua do servidor.
    assert chave_da_versao("1.3.1") < chave_da_versao(corpo["versao_minima_app"])


async def test_a_resposta_tem_tudo_o_que_o_parser_do_1_3_EXIGE(banco, cliente):
    """🔒 O parser do 1.3.1 (`Desafio.fromJson`) recusa a resposta inteira se
    faltar um campo obrigatório - e aí o app nem chega à compatibilidade.

    ⚠️ **Esse seria o defeito caro**: `DesafioInvalido` sobe como defeito do
    dado (`repositorio_desafios.dart` faz `rethrow`), o 1.3.1 não grava o dia
    impedido, e a chama da pessoa quebra. A lista abaixo são os campos que o
    parser da tag `v1.3.1+16` lê sem valor padrão.
    """
    corpo = (await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_3)).json()

    for campo in (
        "id_desafio", "jogo", "tipo", "forma_verificacao", "variante",
        "personagem", "versao_minima_app", "versao_perfil",
    ):
        assert isinstance(corpo[campo], str) and corpo[campo], campo
    assert isinstance(corpo["parametros"], dict)
    assert isinstance(corpo["posicao"], dict) and corpo["tabuleiro"] is None
    assert isinstance(corpo["objetivo"]["chave"], str)
    assert isinstance(corpo["semente"], int)
    assert isinstance(corpo["teto_log_meios_lances"], int)
    assert 0 < corpo["tempo_piso_ms"] < corpo["tempo_teto_ms"]
    assert corpo["medidas_de_saida"], "lista vazia é DesafioInvalido no 1.3.1"
    for medida in corpo["medidas_de_saida"]:
        # As três normalizações que o 1.3.1 conhece; uma quarta seria
        # DesafioInvalido (e não "app antigo").
        assert medida["normalizacao"] in {"faixa", "fracao", "nenhuma"}
        assert 0 <= medida["peso"] <= 1
    assert corpo["regua_nota"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. O dia impedido, gravado com a versão do cabeçalho
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_dia_impedido_do_1_3_e_GRAVADO_no_dia_local(banco, cliente):
    sessao, linha = banco

    resposta = await cliente.post(
        "/v1/desafios/impedido", headers=CABECALHOS_1_3, json=_corpo_do_impedido(linha)
    )

    assert resposta.status_code == 204
    assert await _impedidos(sessao) == [
        {
            # 01h30 UTC de 20/10 é a noite de 19/10 para quem visitou.
            "dt_dia_local": DIA_LOCAL.isoformat(),
            "co_motivo": "jogo_desconhecido",
            "co_desconhecido": "quatro",
            # Do CABEÇALHO...
            "co_versao_app": "1.3.1",
            "co_plataforma": "android",
            # ... e do BANCO: os dois lados do par de diagnóstico.
            "co_versao_minima_exigida": "1.4.0",
        }
    ]


async def test_abrir_o_app_de_novo_no_mesmo_dia_NAO_duplica(banco, cliente):
    """O 1.3.1 reenvia pela fila e a pessoa abre a aba várias vezes: 204 sempre,
    e uma linha só (`un001_dia_impedido`)."""
    sessao, linha = banco

    for _ in range(3):
        resposta = await cliente.post(
            "/v1/desafios/impedido", headers=CABECALHOS_1_3, json=_corpo_do_impedido(linha)
        )
        assert resposta.status_code == 204

    assert len(await _impedidos(sessao)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. A chama lê esse dia, e sobrevive a ele
# ═══════════════════════════════════════════════════════════════════════════


def _ramo_dos_dias_impedidos() -> str:
    """O ramo do `UNION` de `recalcular_chama` que lê os dias impedidos.

    ⚠️ **Tirado do código, e não reescrito aqui**: um ramo copiado à mão
    seguiria verde no dia em que o de produção mudasse de view ou de coluna.
    O outro ramo (as partidas) usa `AT TIME ZONE` e `make_interval`, que o
    SQLite não tem, e por isso fica de fora.
    """
    fonte = inspect.getsource(RepositorioSincronizacao.recalcular_chama)
    achado = re.search(
        r"UNION\s+(SELECT dt_dia_local AS dia\s+FROM desafio_dia\.vw007_desafio_impedido"
        r"\s+WHERE id_usuario = :id)",
        fonte,
    )
    assert achado, "⛔ recalcular_chama já não une os dias impedidos depois de um UNION"
    return achado.group(1)


async def test_a_chama_LE_o_dia_que_a_rota_gravou(banco, cliente):
    sessao, linha = banco
    await cliente.post(
        "/v1/desafios/impedido", headers=CABECALHOS_1_3, json=_corpo_do_impedido(linha)
    )

    dias = await linhas(sessao, _ramo_dos_dias_impedidos(), id=ID_USUARIO)

    assert dias == [{"dia": DIA_LOCAL.isoformat()}]
    # ⚠️ E só os da pessoa: o `WHERE` do ramo é o que separa uma chama da outra.
    assert await linhas(sessao, _ramo_dos_dias_impedidos(), id=str(uuid.uuid4())) == []


def test_o_dia_impedido_SEGURA_a_sequencia():
    """A conta da chama com e sem o dia do Quatro no meio.

    Jogou em 17 e 18/10, abriu o 1.3.1 no dia do Quatro (19/10) e jogou de novo
    em 20/10. Com o dia impedido, a chama chega a 4; sem ele, o buraco de 19/10
    a faz cair para 1 (a regra gentil: cai o número de dias faltados, com piso 1).
    """
    jogados = [date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 20)]

    assert calcular_sequencia_de_dias(sorted([*jogados, DIA_LOCAL])) == 4
    assert calcular_sequencia_de_dias(jogados) == 1
