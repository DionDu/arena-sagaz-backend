"""T049b - a CAMADA DE ESCRITA do job: a conexao e os `INSERT`.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTES CASOS PROVAM, E O QUE ELES NAO PROVAM
═══════════════════════════════════════════════════════════════════════════

Nada aqui toca Postgres. O duble de `fakes_desafio.py` **reconhece** SQL, nunca
o executa — entao o que se prova e o que e **decisao do codigo**: em que ordem as
escritas acontecem, o que acontece quando o dia ja estava publicado, que o job
nao importa a engine da API.

⛔ **Um `JOIN` errado ou um `ON CONFLICT` na constraint errada passariam por aqui
sem um arranhao.** Quem prova isso e o banco de verdade:
`scripts/conferir_migracao_desafio.py` e o portao **T050**.

⚠️ **Com uma excecao, e ela e o caso mais importante deste arquivo:**
[test_o_INSERT_do_desafio_nomeia_TODA_coluna_obrigatoria] le a **migracao** com
`ast` e exige que toda coluna `NOT NULL` sem `DEFAULT` de `desafio.tb001_desafio`
apareca no `INSERT` do job. Esse defeito — coluna nova na tabela, esquecida no
`INSERT` — nao daria erro nenhum ate a primeira execucao no Railway, e a
mensagem seria *"null value in column ... violates not-null constraint"* depois
de o job ter gerado e medido o candidato, que e a parte cara.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from job import banco as banco_do_job
from job.gravacao import LinhaDeDesafio
from job.regua import Medicao
from job.repositorio import (
    SQL_DIAS_PUBLICADOS,
    SQL_GRAVAR_PERFIL,
    SQL_INSERIR_DESAFIO,
    SQL_INSERIR_FEITO,
    SQL_INSERIR_MEDICAO,
    SQL_TIPOS_RECENTES,
    RepositorioDoJob,
    SQL_ASSINATURA_JA_PUBLICADA,
)
from tests.unitarios.fakes_desafio import FakeSessaoSQL
from tests.unitarios.leitura_de_migracao import sql_da_migracao, tabelas_do_sql

RAIZ = Path(__file__).resolve().parents[2]
VERSOES = RAIZ / "migrations" / "versions"
PASTA_DO_JOB = RAIZ / "job"


# ═══════════════════════════════════════════════════════════════════════════
# 1. A conexao — `job/banco.py`
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "bruta",
    [
        "postgresql://um:dois@host:5432/railway",
        "postgres://um:dois@host:5432/railway",  # forma legada
        "postgresql+asyncpg://um:dois@host:5432/railway",
        "sqlite+aiosqlite:///:memory:",  # nao e Postgres: passa intacta
    ],
)
def test_a_normalizacao_da_url_do_JOB_bate_com_a_da_API(bruta: str) -> None:
    """🔒 A mesma regra existe em dois arquivos, e este caso e o preco disso.

    ⚠️ **Nao da para importar a da API sem construir a engine da API**: aquele
    modulo cria a `create_async_engine` no import. Entao a conversao esta escrita
    duas vezes de proposito — e duas copias de uma regra envelhecem torto.

    Este cadeado transforma o esquecimento num teste vermelho, em vez de num job
    que escolhe o driver **sincrono** (`psycopg2`, que nem esta na imagem) e
    morre com `ModuleNotFoundError` no meio da primeira consulta.
    """
    from api.nucleo.banco import _url_async

    assert banco_do_job.normalizar_url(bruta) == _url_async(bruta)


def test_sem_DATABASE_URL_o_job_falha_com_recado_PROPRIO(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⛔ E o defeito de operacao mais provavel de todos: a Variable esquecida.

    ⚠️ O recado precisa dizer **onde arrumar**. Um `KeyError: 'DATABASE_URL'` no
    log do Railway manda quem le olhar o codigo; este manda olhar o console, que
    e onde o problema esta.
    """
    monkeypatch.delenv(banco_do_job.VARIAVEL_DA_URL, raising=False)

    with pytest.raises(banco_do_job.BancoNaoConfigurado) as erro:
        banco_do_job.url_do_banco()

    recado = str(erro.value)
    assert banco_do_job.VARIAVEL_DA_URL in recado
    assert "Railway" in recado
    assert "Variables" in recado


def test_url_VAZIA_conta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠️ Uma Variable criada e deixada em branco e o mesmo estado, na pratica.

    E ela e mais traicoeira que a ausencia: no console a linha **existe**, e
    quem confere passa o olho e ve o nome la.
    """
    monkeypatch.setenv(banco_do_job.VARIAVEL_DA_URL, "   ")
    with pytest.raises(banco_do_job.BancoNaoConfigurado):
        banco_do_job.url_do_banco()


def test_NAO_ha_padrao_de_fabrica_na_url_do_job() -> None:
    """🔒 Herdar o `localhost` de `api/configuracao.py` seria caro e silencioso.

    ⚠️ **A leitura e por `ast`, e nao por texto**: um `"localhost" not in fonte`
    reprovaria a propria docstring que explica o defeito — que e a **setima** vez
    que esse padrao apareceria neste projeto.

    O que se procura e uma **constante string com esquema de URL** dentro de
    `url_do_banco`: e assim que um padrao de fabrica entraria.
    """
    arvore = ast.parse((PASTA_DO_JOB / "banco.py").read_text(encoding="utf-8"))
    funcao = next(
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == "url_do_banco"
    )
    # A docstring e um `ast.Expr` com `Constant` — ela e o primeiro no do corpo, e
    # sai da varredura junto com as demais mensagens de erro (que nao sao URL).
    urls = [
        no.value
        for no in ast.walk(funcao)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and "://" in no.value
    ]
    assert not urls, (
        f"`url_do_banco` tem uma URL escrita no codigo: {urls}. ⛔ Um padrao de "
        "fabrica faria 'faltou a Variable' se parecer com 'o banco caiu' no log "
        "do Railway."
    )


def _modulos_do_job() -> list[Path]:
    """Todo arquivo `.py` de `job/`.

    ⚠️ **Descoberta, e nao lista escrita a mao** — a licao que este projeto ja
    pagou seis vezes. Um cadeado com os nomes fixos ficaria cego exatamente no
    dia em que alguem acrescentasse um modulo.
    """
    achados = sorted(PASTA_DO_JOB.glob("*.py"))
    assert achados, "⛔ nenhum modulo em job/: nada a varrer e FALHA, nao sucesso"
    return achados


@pytest.mark.parametrize("caminho", _modulos_do_job(), ids=lambda p: p.name)
def test_o_job_NAO_importa_a_engine_da_API(caminho: Path) -> None:
    """🔒 RF-DES-011a: os dois se falam pelo Postgres, nao por dentro um do outro.

    ⚠️ `api/nucleo/banco.py` **constroi a engine no import**. Um `from
    api.nucleo.banco import ...` em qualquer modulo daqui faria a engine da API —
    com o pool dimensionado para um servidor web que fica de pe — nascer dentro do
    container do job, so por importar.

    ⛔ E o pior nao seria a memoria: a gravacao do job passaria a depender da
    afinacao do **servidor**, e mudar o pool da API para aguentar mais gente
    mudaria, calado, como o job escreve.

    ⚠️ Importar `api.desafios.modelos_*` continua permitido, e a diferenca e o
    ponto: aqueles modulos declaram **nomes** (VIEWs, vocabularios), e nao
    conexao. `job/auditoria.py` faz isso desde que nasceu.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    proibidos: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and (no.module or "").startswith(
            "api.nucleo.banco"
        ):
            proibidos.append(f"from {no.module} import ...")
        elif isinstance(no, ast.Import):
            proibidos.extend(
                f"import {alias.name}"
                for alias in no.names
                if alias.name.startswith("api.nucleo.banco")
            )

    assert not proibidos, (
        f"{caminho.name} importa a camada de banco da API: {proibidos}. "
        "⛔ O job tem a sua, em `job/banco.py` (RF-DES-011a)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. O `INSERT` do desafio contra a MIGRACAO
# ═══════════════════════════════════════════════════════════════════════════


def _colunas_obrigatorias(tabela: str) -> list[str]:
    """As colunas `NOT NULL` **sem `DEFAULT`** daquela tabela, lidas da migracao.

    ⚠️ **`NOT NULL` com `DEFAULT` fica de fora de proposito**: `id_desafio`,
    `dh_geracao` e `ic_reprise` sao preenchidas pelo banco, e exigi-las no
    `INSERT` seria exigir que o job carimbasse o que o Postgres carimba melhor.

    ⚠️ **Varre TODAS as migracoes**, e nao a `0018`: a coluna que faltar no
    `INSERT` amanha pode chegar por uma migracao que ainda nao existe — que e
    exatamente o caso em que uma lista escrita a mao ficaria cega.
    """
    obrigatorias: list[str] = []
    for caminho in sorted(VERSOES.glob("[0-9]*.py")):
        tabelas = tabelas_do_sql(sql_da_migracao(caminho))
        if tabela not in tabelas:
            continue
        for nome, tipo in tabelas[tabela]["colunas"]:  # type: ignore[index]
            if "NOT NULL" in tipo and "DEFAULT" not in tipo:
                obrigatorias.append(nome)
    assert obrigatorias, (
        f"⛔ nenhuma coluna obrigatoria encontrada em {tabela}. **Nada a varrer e "
        "FALHA**: sem isso o cadeado compara dois vazios e passa."
    )
    return obrigatorias


def test_o_INSERT_do_desafio_nomeia_TODA_coluna_obrigatoria() -> None:
    """🔒 O caso mais importante deste arquivo.

    Uma coluna `NOT NULL` acrescentada a `desafio.tb001_desafio` e esquecida no
    `INSERT` do job ⛔ **nao da erro nenhum no CI** — nada aqui passa pelo
    Postgres. O estouro chega no Railway, uma vez por dia, **depois** de o
    candidato ter sido gerado e medido pelos tres mascotes: a parte cara e feita,
    e jogada fora.

    ⚠️ A comparacao e contra a **migracao**, e nao contra uma lista: e a migracao
    que descreve o que vai rodar.
    """
    faltando = [
        coluna
        for coluna in _colunas_obrigatorias("desafio.tb001_desafio")
        if coluna not in SQL_INSERIR_DESAFIO
    ]
    assert not faltando, (
        f"colunas obrigatorias fora do INSERT do job: {faltando}. ⛔ O `INSERT` "
        "estouraria no Railway depois de toda a geracao e toda a medicao."
    )


def test_o_cadeado_das_colunas_ENXERGA_a_falta() -> None:
    """🔒 A prova de que a varredura acima reprova quando deve.

    ⚠️ Um cadeado que nunca foi visto falhando e indistinguivel de um cadeado
    quebrado — e este projeto ja teve tres deles verdes e cegos no mesmo dia.
    """
    obrigatorias = _colunas_obrigatorias("desafio.tb001_desafio")
    # Um `INSERT` mutilado: tira a semente, que e `NOT NULL` e sem `DEFAULT`.
    mutilado = SQL_INSERIR_DESAFIO.replace("nu_semente", "nu_XXXXXX")
    faltando = [c for c in obrigatorias if c not in mutilado]
    assert "nu_semente" in faltando


def test_o_INSERT_nao_carimba_o_que_o_BANCO_carimba() -> None:
    """⚠️ `id_desafio`, `dh_geracao` e `ic_reprise` tem `DEFAULT`.

    Nomea-las no `INSERT` faria o job decidir o instante da geracao pelo relogio
    de **quem rodou**, e nao pelo do banco — e dois containers em fusos
    diferentes gravariam a mesma safra com horas diferentes.
    """
    for coluna in ("id_desafio ", "dh_geracao", "ic_reprise"):
        assert coluna not in SQL_INSERIR_DESAFIO, (
            f"`{coluna.strip()}` tem DEFAULT no banco e nao deve entrar no INSERT"
        )


def test_o_desafio_nasce_CANDIDATO() -> None:
    """⛔ RF-DES-012a: nada vai ao ar sem o dono ver.

    O valor vem do parametro (`montar_linha` o fixa em `candidato`), e ⛔ **nao
    ha `DEFAULT 'candidato'` na tabela** de proposito: um padrao faria a curadoria
    virar opcional por acidente, e o primeiro esquecimento poria conteudo no ar
    sem ninguem ter visto.
    """
    assert ":co_curadoria" in SQL_INSERIR_DESAFIO
    assert "'aprovado'" not in SQL_INSERIR_DESAFIO


def test_a_chave_do_feito_vira_nu_feito_NO_BANCO() -> None:
    """⚠️ A traducao acontece no `INSERT`, por subconsulta no catalogo.

    Chave que nao existe faz a subconsulta devolver `NULL`, e `nu_feito` e
    `NOT NULL`: o banco recusa. ⛔ Traduzir em Python antes exigiria
    reimplementar a mesma recusa — e a primeira versao esquecida dela gravaria
    uma medida que **nenhum jogo produz**, e a parcela pagaria zero para sempre,
    sem erro nenhum.
    """
    assert "desafio.vw902_catalogo_feito" in SQL_INSERIR_FEITO
    assert "c.co_feito = :co_feito" in SQL_INSERIR_FEITO


@pytest.mark.parametrize(
    "sql, nome",
    [
        (SQL_DIAS_PUBLICADOS, "SQL_DIAS_PUBLICADOS"),
        (SQL_TIPOS_RECENTES, "SQL_TIPOS_RECENTES"),
        (SQL_ASSINATURA_JA_PUBLICADA, "SQL_ASSINATURA_JA_PUBLICADA"),
        (SQL_INSERIR_FEITO, "SQL_INSERIR_FEITO"),
    ],
)
def test_a_LEITURA_vai_a_VIEW(sql: str, nome: str) -> None:
    """🔒 Convencao do projeto desde a `0001`: le-se pela VIEW.

    ⚠️ Vale tambem para a subconsulta dentro de um `INSERT` — e ela e o lugar
    mais facil de esquecer, porque o comando nao **parece** uma leitura.
    """
    import re

    alvos = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z0-9_]+)", sql, re.I)
    tabelas = [alvo for alvo in alvos if ".tb" in alvo]
    assert not tabelas, f"{nome} le da TABELA em vez da VIEW: {tabelas}"


@pytest.mark.parametrize(
    "sql, nome",
    [
        (SQL_GRAVAR_PERFIL, "SQL_GRAVAR_PERFIL"),
        (SQL_INSERIR_DESAFIO, "SQL_INSERIR_DESAFIO"),
        (SQL_INSERIR_MEDICAO, "SQL_INSERIR_MEDICAO"),
        (SQL_INSERIR_FEITO, "SQL_INSERIR_FEITO"),
    ],
)
def test_a_ESCRITA_vai_a_TABELA(sql: str, nome: str) -> None:
    """O outro sentido da mesma convencao: `INSERT` numa VIEW nem sempre falha.

    ⚠️ Uma VIEW simples de uma tabela so e **atualizavel** no Postgres, entao o
    engano nao daria erro — passaria a escrever por um caminho que ninguem
    esperava, e o dia em que a VIEW ganhasse um `JOIN` a gravacao quebraria sem
    explicacao.
    """
    import re

    (alvo,) = re.findall(r"INSERT INTO\s+([a-z_]+\.[a-z0-9_]+)", sql, re.I)
    assert ".tb" in alvo, f"{nome} escreve numa VIEW: {alvo}"


# ═══════════════════════════════════════════════════════════════════════════
# 3. A ordem das escritas
# ═══════════════════════════════════════════════════════════════════════════


def _linha_de_exemplo() -> LinhaDeDesafio:
    """Uma linha de `tb001_desafio` completa, no formato do `data-model.md`."""
    return LinhaDeDesafio(
        co_jogo="pontinhos",
        co_modalidade=None,
        co_variante="pequeno",
        co_formato_posicao="sequencia_lances",
        js_posicao_inicial={"versao": 1, "lances": []},
        nu_tipo_desafio=1,
        js_chegada={"versao": 1, "janela": {"tipo": "partida"}, "clausulas": []},
        ic_chegada_encerra_partida=False,
        co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
        js_objetivo={"caixas": 4, "turnos": 2, "personagem": "pita"},
        co_personagem="pita",
        nu_semente=2087461933,
        js_solucao={"versao": 1, "lances": []},
        nu_lances_solucao=5,
        nu_tempo_piso_ms=30_000,
        nu_tempo_teto_ms=180_000,
        nu_versao_catalogo=1,
        co_versao_minima="1.3.0",
        co_versao_perfil="perfil-abcd1234",
        co_versao_motor="pontinhos-py-2.1.0",
        nu_teto_log=120,
    )


def _medicoes() -> list[Medicao]:
    """As tres linhas da regua — os mascotes que NAO sao o adversario do dia."""
    return [
        Medicao(
            co_personagem=quem,
            nu_execucoes=20,
            nu_resolveu=14,
            co_versao_perfil="perfil-abcd1234",
            co_versao_motor="pontinhos-py-2.1.0",
        )
        for quem in ("cacau", "tex", "magno")
    ]


def _medidas() -> list[dict[str, Any]]:
    """Duas medidas de saida, com os pesos ja fechando em 1,000."""
    return [
        {
            "co_feito": "caixas_fechadas",
            "nu_ordem": 1,
            "vr_peso": Decimal("0.600"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("4"),
            "co_sobre": None,
        },
        {
            "co_feito": "lances_do_jogador",
            "nu_ordem": 2,
            "vr_peso": Decimal("0.400"),
            "co_normalizacao": "fracao",
            "vr_min": None,
            "vr_max": None,
            "co_sobre": "lances_da_solucao",
        },
    ]


def _sessao_que_publica() -> FakeSessaoSQL:
    """Um duble em que o desafio grava e o dia e publicado com sucesso."""
    return FakeSessaoSQL(
        respostas={
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": "id-do-desafio"}],
            "INSERT INTO desafio.tb002_medicao_regua": [{"id_medicao": "m"}],
            "INSERT INTO desafio.tb003_feito_desafio": [{"id_feito_desafio": "f"}],
            "INSERT INTO desafio_dia.tb001_desafio_dia": [{"id_desafio_dia": "d"}],
        }
    )


@pytest.mark.asyncio
async def test_o_DIA_e_a_ULTIMA_escrita() -> None:
    """🔒 Publicar antes dos feitos abriria uma janela que ninguem veria.

    ⛔ O aplicativo baixaria um desafio **sem medidas de saida**, e ele pagaria so
    o piso de XP. ⚠️ **Nada daria erro**: o `INSERT` passa, a resposta sai, e a
    diferenca so apareceria no extrato de quem jogou — que ninguem confere.

    E a mesma licao que `job/reprise.py` ja registra sobre `SQL_COPIAR_FEITOS`;
    aqui ela vira teste.
    """
    sessao = _sessao_que_publica()
    await RepositorioDoJob(sessao).publicar_desafio(
        dt_dia=date(2026, 9, 20),
        linha=_linha_de_exemplo(),
        medicoes=_medicoes(),
        medidas=_medidas(),
    )

    ordem = [texto for texto, _ in sessao.executadas]
    posicao_do_dia = next(
        i for i, sql in enumerate(ordem) if "tb001_desafio_dia" in sql
    )
    assert posicao_do_dia == len(ordem) - 1, (
        "o dia foi publicado antes de alguma outra escrita: "
        f"{ordem[posicao_do_dia + 1:]}"
    )


@pytest.mark.asyncio
async def test_a_regua_e_as_medidas_vem_DEPOIS_do_desafio() -> None:
    """Elas tem chave estrangeira para ele — nao ha outra ordem possivel."""
    sessao = _sessao_que_publica()
    await RepositorioDoJob(sessao).publicar_desafio(
        dt_dia=date(2026, 9, 20),
        linha=_linha_de_exemplo(),
        medicoes=_medicoes(),
        medidas=_medidas(),
    )

    ordem = [texto for texto, _ in sessao.executadas]
    primeiro = next(i for i, s in enumerate(ordem) if "tb001_desafio\n" in s or "tb001_desafio " in s)
    regua = next(i for i, s in enumerate(ordem) if "tb002_medicao_regua" in s)
    feitos = next(i for i, s in enumerate(ordem) if "tb003_feito_desafio" in s)
    assert primeiro < regua < feitos


@pytest.mark.asyncio
async def test_UM_commit_so_por_desafio() -> None:
    """⛔ Um `commit` por `INSERT` deixaria desafio pela metade no banco.

    ⚠️ Se a maquina caisse entre o desafio e as medidas, a curadoria veria um
    candidato de aparencia perfeita que pagaria so o piso — e nada nele diria
    isso.
    """
    sessao = _sessao_que_publica()
    await RepositorioDoJob(sessao).publicar_desafio(
        dt_dia=date(2026, 9, 20),
        linha=_linha_de_exemplo(),
        medicoes=_medicoes(),
        medidas=_medidas(),
    )
    assert sessao.commits == 1


@pytest.mark.asyncio
async def test_dia_JA_PUBLICADO_devolve_None_e_nao_erro() -> None:
    """⚠️ E a idempotencia de RF-DES-013 funcionando, e ela mora no BANCO.

    O `ON CONFLICT (dt_dia) DO NOTHING` absorve a corrida entre duas execucoes.
    ⛔ Uma checagem "ja existe?" antes do `INSERT` **nao bastaria**: as duas
    execucoes passariam por ela, e so o `un001_dia` as separa.

    ⚠️ E o desafio recem gravado **fica no banco**, como candidato sem dia. Isso e
    inofensivo (ninguem chega a ele) e util (a curadoria o ve, e ele serve de
    reserva); desfazer tudo jogaria fora minutos de CPU por causa de uma corrida
    que o banco ja resolveu.
    """
    sessao = FakeSessaoSQL(
        respostas={
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": "id-do-desafio"}],
            # O dia nao devolve nada: o `DO NOTHING` engoliu a insercao.
            "INSERT INTO desafio_dia.tb001_desafio_dia": [],
        }
    )
    resultado = await RepositorioDoJob(sessao).publicar_desafio(
        dt_dia=date(2026, 9, 20),
        linha=_linha_de_exemplo(),
        medicoes=_medicoes(),
        medidas=_medidas(),
    )
    assert resultado is None
    assert sessao.commits == 1


@pytest.mark.asyncio
async def test_a_medicao_herda_o_co_jogo_do_DESAFIO() -> None:
    """⚠️ `co_jogo` e repetido na regua para fechar a `fk001_perfil` sem `JOIN`.

    Ele sai da **linha do desafio**, e nao de um parametro solto: repetir o valor
    a mao abriria a chance de a medicao dizer que mediu um jogo e o desafio ser de
    outro — e a FK composta aceitaria, porque as duas linhas seriam coerentes
    consigo mesmas.
    """
    sessao = _sessao_que_publica()
    await RepositorioDoJob(sessao).publicar_desafio(
        dt_dia=date(2026, 9, 20),
        linha=_linha_de_exemplo(),
        medicoes=_medicoes(),
        medidas=_medidas(),
    )
    medicoes = [
        parametros
        for sql, parametros in sessao.executadas
        if "tb002_medicao_regua" in sql
    ]
    assert medicoes
    assert all(p["co_jogo"] == "pontinhos" for p in medicoes)


# ═══════════════════════════════════════════════════════════════════════════
# 4. O perfil, que vem antes de tudo
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_o_perfil_conta_as_linhas_NOVAS() -> None:
    """⚠️ Zero e o caso comum e saudavel, e nao um erro.

    O perfil so muda quando os contratos de dificuldade mudam — e ai a versao
    muda junto, porque ela **deriva** dos hashes deles.
    """
    sessao = FakeSessaoSQL(
        respostas={"INSERT INTO desafio.tb903_perfil_dificuldade": []}
    )
    linhas = [
        {
            "co_versao_perfil": "perfil-abcd1234",
            "co_jogo": "pontinhos",
            "co_personagem": quem,
            "js_perfil": {"epsilon": 0.2},
            "co_arquivo": "espelho_laboratorio/contrato.json",
            "co_sha256": "0" * 64,
        }
        for quem in ("cacau", "pita", "tex", "magno")
    ]
    assert await RepositorioDoJob(sessao).garantir_perfil(linhas) == 0


@pytest.mark.asyncio
async def test_o_perfil_NAO_reescreve_a_linha_existente() -> None:
    """⛔ Duas versoes de perfil convivem de proposito.

    ⚠️ `co_versao_perfil` deriva dos hashes dos contratos: se os numeros mudaram,
    a versao mudou junto e a linha e **outra**. Um `DO UPDATE` aqui reescreveria
    a explicacao de medicoes antigas — e *"a Pita resolveu 14 de 20"* deixaria de
    ter regua conhecida.
    """
    assert "ON CONFLICT" in SQL_GRAVAR_PERFIL
    assert "DO NOTHING" in SQL_GRAVAR_PERFIL
    assert "DO UPDATE" not in SQL_GRAVAR_PERFIL


@pytest.mark.asyncio
async def test_o_js_perfil_sobrevive_a_um_numero_que_o_json_NAO_serializa() -> None:
    """⚠️ Os numeros do perfil sao EXTRAIDOS dos contratos, e a forma varia.

    Um `Decimal`, um `Enum` ou um `Path` estouraria o `json.dumps` — e o job
    morreria no **primeiro passo**, antes de gerar nada, por causa de um campo que
    existe apenas para *explicar* a medicao depois.
    """
    from decimal import Decimal as D

    sessao = FakeSessaoSQL(
        respostas={"INSERT INTO desafio.tb903_perfil_dificuldade": [{"id_perfil": "p"}]}
    )
    linhas = [
        {
            "co_versao_perfil": "perfil-abcd1234",
            "co_jogo": "damas",
            "co_personagem": "magno",
            "js_perfil": {"multiplicador": D("2.0")},
            "co_arquivo": "espelho_laboratorio/contrato_damas.json",
            "co_sha256": "1" * 64,
        }
    ]
    assert await RepositorioDoJob(sessao).garantir_perfil(linhas) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. ⛔ T049i — nenhum desafio se repete
# ═══════════════════════════════════════════════════════════════════════════


def test_a_assinatura_olha_o_HISTORICO_INTEIRO_e_nao_a_janela() -> None:
    """🔒 ⛔ A diferenca desta consulta para as duas irmas e a AUSENCIA de recorte.

    ⚠️ `SQL_DIAS_PUBLICADOS` e `SQL_TIPOS_RECENTES` tem `BETWEEN` de proposito — o
    rodizio existe para o dia nao parecer o de ontem, e o que foi publicado ha
    tres meses nao atrapalha ninguem. **Aqui e o contrario:** um desafio e
    publicado uma vez so, e repetir o de tres meses atras e exatamente o que a
    regra proibe.

    Um `BETWEEN` que aparecesse aqui faria o cadeado proteger so a janela — e a
    fila voltaria a repetir, calada, no primeiro desafio com mais de 30 dias.
    """
    assert "BETWEEN" not in SQL_ASSINATURA_JA_PUBLICADA.upper()
    assert "dt_inicio" not in SQL_ASSINATURA_JA_PUBLICADA


def test_a_assinatura_compara_os_QUATRO_campos() -> None:
    """A assinatura e `(tipo, modalidade, posicao inicial, chegada)`.

    ⚠️ **A modalidade nao e redundante com o tipo.** `damas_coroar` roda nas
    quatro modalidades sobre os MESMOS moldes: a mesma posicao inicial jogada por
    regulamentos diferentes e um desafio diferente, e tirar a modalidade daqui
    recusaria tres candidatos legitimos por dia de damas.
    """
    for campo in (
        ":co_tipo_desafio",
        ":co_modalidade",
        ":js_posicao_inicial",
        ":js_chegada",
    ):
        assert campo in SQL_ASSINATURA_JA_PUBLICADA, f"falta {campo}"


def test_a_modalidade_NULA_casa_com_a_nula() -> None:
    """🔒 ⛔ O defeito que teria deixado o Pontinhos sem cadeado, em silencio.

    `co_modalidade` e **nula** no Pontinhos, e em SQL `NULL = NULL` da `NULL`, e
    nao `TRUE`. Com um `=` simples, todo desafio de Pontinhos pareceria inedito
    para sempre: a consulta rodaria, nao acusaria nada, e o cadeado protegeria
    apenas as damas — sem que ninguem percebesse.
    """
    assert "IS NOT DISTINCT FROM" in SQL_ASSINATURA_JA_PUBLICADA


def test_a_comparacao_de_json_e_JSONB_e_nao_texto() -> None:
    """⚠️ O Postgres normaliza `jsonb`: ordem de chave e espaco nao contam.

    Comparar `::text` diria "inedito" para o mesmo tabuleiro com as chaves em
    outra ordem — e nada denunciaria, porque a consulta continuaria valida.
    """
    assert "CAST(:js_posicao_inicial AS JSONB)" in SQL_ASSINATURA_JA_PUBLICADA
    assert "CAST(:js_chegada AS JSONB)" in SQL_ASSINATURA_JA_PUBLICADA


@pytest.mark.asyncio
async def test_assinatura_INEDITA_devolve_None() -> None:
    """Sem linha no banco, o candidato e novo — e o job segue com ele."""
    sessao = FakeSessaoSQL()
    achado = await RepositorioDoJob(sessao).assinatura_ja_publicada(
        co_tipo_desafio="pontinhos_fechar_caixas",
        co_modalidade=None,
        js_posicao_inicial={"versao": 1, "lances": []},
        js_chegada={"janela": {}, "clausulas": []},
    )
    assert achado is None


@pytest.mark.asyncio
async def test_assinatura_REPETIDA_devolve_o_id_anterior() -> None:
    """⚠️ Devolve o **id**, e nao um booleano — e a diferenca vai para o log.

    *"Recusado por repeticao"* nao ajuda ninguem a investigar; *"repetiria o
    desafio `<uuid>`"* leva direto a linha que ja existe, e e assim que se
    descobre que o acervo daquele tipo se esgotou.
    """
    sessao = FakeSessaoSQL(
        respostas={"SELECT d.id_desafio": [{"id_desafio": "o-de-marco"}]}
    )
    achado = await RepositorioDoJob(sessao).assinatura_ja_publicada(
        co_tipo_desafio="damas_coroar",
        co_modalidade="portuguesa",
        js_posicao_inicial={"versao": 1, "fen": "W:W12,25,28:B13,15,17"},
        js_chegada={"janela": {}, "clausulas": []},
    )
    assert achado == "o-de-marco"


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A CONEXAO DO JOB NAO DORME NO POOL
# ═══════════════════════════════════════════════════════════════════════════


def test_a_engine_do_job_usa_NULLPOOL() -> None:
    """🔒 O cadeado do crash de 11/09/2026 no Railway.

    A engine tinha `pool_size=1` + `pool_pre_ping=True`, e o comentario que
    justificava o ping descrevia o problema certo: a geracao de um dia passa
    minutos em CPU sem tocar no banco, e o proxy do Railway derruba a conexao
    parada.

    ⛔ **A defesa e que estava errada.** O pre-ping abre uma transacao para testar
    a conexao; numa conexao derrubada o asyncpg devolve

        InternalClientError: cannot switch to state 15;
        another operation (2) is in progress

    que o dialeto do SQLAlchemy **nao** reconhece como desconexao. Em vez de
    trocar a conexao, o erro sobe — e matou o dia 2026-09-17 depois de seis dias
    gerados, deixando buraco na fila.

    ⚠️ Sem pool nao ha conexao dormindo, e o problema deixa de existir por
    construcao. O preco (uma conexao nova por operacao) e irrelevante num
    processo que acorda uma vez por dia.
    """
    from sqlalchemy.pool import NullPool

    from job.banco import criar_engine

    engine = criar_engine("postgresql+asyncpg://u:s@h:5432/d")
    assert isinstance(engine.pool, NullPool), (
        f"a engine do job voltou a usar {type(engine.pool).__name__}. ⛔ Qualquer "
        "pool guarda conexao entre as operacoes, e e exatamente a conexao "
        "guardada que o proxy derruba durante a busca."
    )
