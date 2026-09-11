"""T049e - `desafio.tb904_motor`: o carimbo do motor tem de ser DECIFRAVEL.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTES CADEADOS GUARDAM, E A CLASSE DE DEFEITO QUE ELES CACAM
═══════════════════════════════════════════════════════════════════════════

`co_versao_motor` e um resumo de 8 digitos hexadecimais. ⛔ **Todo texto de 8
hexadecimais e um resumo perfeitamente bem-formado** — decifrar errado, listar
arquivos de menos ou gravar o hash de outro manifesto produziria uma linha que
**parece** certa, entra no banco, atravessa a API e so falharia meses depois, na
hora de responder *"este desafio foi medido com que motor?"*.

Por isso o cadeado central daqui nao pergunta "o codigo roda": ele **parte da
linha, refaz a conta e exige chegar de volta ao carimbo**. E, para que ele nao
vire decoracao, ha um caso que estraga a lista de proposito e exige que a conta
**deixe** de bater.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from job import motor as motor_mod
from job import repositorio as repositorio_mod
from motores.damas import contrato_damas
from motores.pontinhos import motor_pontinhos
from tests.unitarios.fakes_desafio import FakeSessaoSQL
from tests.unitarios.leitura_de_migracao import sql_da_migracao, tabelas_do_sql

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0022_motor_decifravel.py"

#: O prefixo de cada jogo no carimbo — `damas-py-<8 hex>`.
PREFIXO_ESPERADO = {"damas": "damas-py-", "pontinhos": "pontinhos-py-"}


@pytest.fixture(scope="module")
def linhas() -> list[dict]:
    """As linhas que o job gravaria hoje — uma por jogo."""
    return motor_mod.linhas_da_dimensao()


@pytest.fixture(scope="module")
def sql_da_0022() -> str:
    """O SQL que a migracao `0022` executa, lido com `ast`."""
    return sql_da_migracao(MIGRACAO)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O cadeado central: a linha se decifra sozinha
# ═══════════════════════════════════════════════════════════════════════════


def _resumo_a_partir_da_linha(linha: dict) -> str:
    """Refaz o carimbo **usando so o que esta na linha**.

    ⚠️ Esta funcao e deliberadamente uma **segunda implementacao** da conta: ela
    nao chama `versao_do_motor()`. Um cadeado que reusasse a funcao de producao
    provaria apenas que ela e igual a si mesma.
    """
    hashes = sorted(
        arquivo["sha256"] for arquivo in linha["js_arquivos"]["arquivos"]
    )
    return hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()[:8]


@pytest.mark.parametrize("co_jogo", ["damas", "pontinhos"])
def test_o_carimbo_SE_REFAZ_a_partir_da_linha(linhas, co_jogo) -> None:
    """🔒 ⛔ O cadeado mais importante do arquivo: a linha basta.

    ⚠️ **E e isso que liberta a decifracao da formula de hoje.** Enquanto a unica
    forma de decifrar for *"descobrir o commit e refazer a conta"*, no dia em que
    alguem mudar a funcao que deriva o resumo **toda string antiga fica
    irresolvivel para sempre** — e ninguem notaria, porque nada quebra: o banco
    simplesmente passa a guardar carimbos que ninguem mais consegue explicar.
    """
    linha = next(l for l in linhas if l["co_jogo"] == co_jogo)
    assert linha["co_versao_motor"] == (
        PREFIXO_ESPERADO[co_jogo] + _resumo_a_partir_da_linha(linha)
    )


def test_o_cadeado_acima_ENXERGA_uma_lista_estragada(linhas) -> None:
    """🔒 O controle negativo — sem ele o caso anterior poderia ser decorativo.

    Tira **um** arquivo da lista e exige que a conta deixe de bater. Se esta
    afirmacao falhar, a que esta acima nao esta provando nada.
    """
    linha = dict(linhas[0])
    arquivos = linha["js_arquivos"]["arquivos"]
    linha["js_arquivos"] = {"versao": 1, "arquivos": arquivos[:-1]}

    assert linha["co_versao_motor"] != (
        PREFIXO_ESPERADO[linha["co_jogo"]] + _resumo_a_partir_da_linha(linha)
    )


@pytest.mark.parametrize("co_jogo", ["damas", "pontinhos"])
def test_os_ARQUIVOS_da_linha_existem_no_disco_com_aquele_hash(
    linhas, co_jogo
) -> None:
    """A linha descreve arquivos reais, e nao uma lista herdada.

    ⚠️ **O sintoma que isto pega e o espelho desatualizado**: alguem troca um
    arquivo do motor sem reespelhar, o manifesto continua descrevendo o antigo, e
    o carimbo gravado passa a identificar um motor que nao e o que jogou.
    """
    linha = next(l for l in linhas if l["co_jogo"] == co_jogo)
    espelho = motor_mod.CAMINHO_DO_MANIFESTO.parent

    for arquivo in linha["js_arquivos"]["arquivos"]:
        caminho = espelho / arquivo["caminho"]
        assert caminho.is_file(), f"{arquivo['caminho']} nao esta no espelho"
        real = hashlib.sha256(caminho.read_bytes()).hexdigest()
        assert real == arquivo["sha256"], (
            f"{arquivo['caminho']}: o manifesto diz {arquivo['sha256'][:12]} e o "
            f"disco diz {real[:12]}"
        )


def test_o_SHA256_da_linha_e_o_do_manifesto_no_disco(linhas) -> None:
    """🔒 `co_sha256` identifica o manifesto — e nao qualquer outra coisa.

    ⚠️ E ele a ancora que torna a lista de arquivos **conferivel**: com o hash do
    manifesto na linha, da para dizer qual documento declarava aqueles arquivos
    naquele dia.
    """
    real = hashlib.sha256(motor_mod.CAMINHO_DO_MANIFESTO.read_bytes()).hexdigest()
    for linha in linhas:
        assert linha["co_sha256"] == real
        assert len(linha["co_sha256"]) == 64, "a coluna e CHAR(64)"


# ═══════════════════════════════════════════════════════════════════════════
# 2. A lista de arquivos e a MESMA que o motor resumiu
# ═══════════════════════════════════════════════════════════════════════════


def test_os_dois_motores_expoem_a_lista_QUE_ELES_MESMOS_resumem() -> None:
    """🔒 ⛔ Nao ha dois filtros de arquivo — ha um, exposto.

    ⚠️ **Este e o defeito que `arquivos_do_motor()` nasceu para impedir.** Antes
    de T049e a lista vivia **dentro** de `versao_do_motor`, como variavel local;
    montar a linha do banco exigiria reescrever o filtro noutro modulo, e as duas
    copias divergiriam no primeiro arquivo novo do motor. O sintoma seria o pior
    possivel: a linha do banco afirmando que o resumo saiu de um conjunto de
    arquivos, quando ele saiu de outro — sem erro nenhum.

    Aqui a conta e refeita **a partir da lista exposta** e comparada com o
    carimbo que o proprio motor publica.
    """
    for modulo, prefixo in (
        (contrato_damas, "damas-py-"),
        (motor_pontinhos, "pontinhos-py-"),
    ):
        hashes = sorted(a["sha256"] for a in modulo.arquivos_do_motor())
        digesto = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
        assert modulo.versao_do_motor() == f"{prefixo}{digesto[:8]}"


def test_a_lista_cobre_TODO_o_manifesto_daquele_motor() -> None:
    """Nenhum arquivo do prefixo fica de fora, e nenhum estranho entra.

    ⚠️ **Um arquivo a menos nao daria erro** — daria outro resumo, tao valido
    quanto. E um a mais (um arquivo de outro jogo) faria o carimbo das damas
    mudar quando o Pontinhos mudasse, o que e pior: as medicoes antigas pareceriam
    ter sido feitas com outro motor.
    """
    manifesto = json.loads(
        motor_mod.CAMINHO_DO_MANIFESTO.read_text(encoding="utf-8")
    )
    for modulo, prefixos in (
        (contrato_damas, (contrato_damas.PREFIXO_DO_MOTOR,)),
        (motor_pontinhos, motor_pontinhos.PREFIXOS_DO_MOTOR),
    ):
        esperados = {
            item["caminho"]
            for item in manifesto["arquivos"]
            if item["caminho"].startswith(prefixos)
        }
        obtidos = {a["caminho"] for a in modulo.arquivos_do_motor()}
        assert obtidos == esperados


def test_a_lista_vem_ORDENADA_pelo_caminho() -> None:
    """A ordem de leitura humana, estavel entre execucoes.

    ⚠️ A ordem do **manifesto** pode mudar sem que nada tenha mudado de verdade;
    uma lista que oscila faria duas linhas iguais parecerem diferentes na
    revisao, e o `json` gravado mudaria sem motivo.
    """
    for modulo in (contrato_damas, motor_pontinhos):
        caminhos = [a["caminho"] for a in modulo.arquivos_do_motor()]
        assert caminhos == sorted(caminhos)


# ═══════════════════════════════════════════════════════════════════════════
# 3. `js_motores` fecha o par de diagnostico
# ═══════════════════════════════════════════════════════════════════════════


def test_js_motores_tem_a_MESMA_forma_da_tb007_do_aplicativo(linhas) -> None:
    """🔒 As duas metades do diagnostico precisam se comparar sem tradutor.

    O aparelho reporta `dart_1.4.0|rust_0.4.0` em
    `desafio_dia.tb007_desafio_impedido.js_motores`; o servidor guarda o seu aqui.
    ⛔ **Se as formas divergirem, a pergunta *"por que este desafio nao coube no
    aparelho desta pessoa?"* volta a nao ter resposta** — que e o problema que
    esta tabela existe para resolver.

    As chaves sao as tres da `0021`, e nao duas nem quatro.
    """
    for linha in linhas:
        js = linha["js_motores"]
        assert js["versao"] == 1, "a versao do formato e obrigatoria"
        assert isinstance(js["motores"], list), "e LISTA, nao dicionario por jogo"
        assert js["motores"], "lista vazia descreveria um jogador que nao existe"
        for registro in js["motores"]:
            assert set(registro) == {"co_jogo", "co_motor", "co_versao"}
            assert registro["co_jogo"] == linha["co_jogo"]
            assert all(isinstance(v, str) and v for v in registro.values())


def test_a_lista_do_servidor_declara_o_CONTRATO_que_o_aplicativo_carrega(
    linhas,
) -> None:
    """⚠️ E o contrato a metade compartilhada — o resto nao tem numero em comum.

    O port Python do servidor e o Dart do aparelho sao implementacoes diferentes;
    ⛔ comparar `damas-py-2f8e15cd` com `dart_1.4.0` nao responde nada. O que os
    dois lados obedecem, byte a byte, e o contrato.
    """
    esperado = {
        "damas": contrato_damas.versao_do_contrato(),
        "pontinhos": str(motor_pontinhos.contrato_de_codificacao()["versao"]),
    }
    for linha in linhas:
        versoes = {
            registro["co_motor"]: registro["co_versao"]
            for registro in linha["js_motores"]["motores"]
        }
        declarada = versoes.get("contrato") or versoes.get("codificacao")
        assert declarada == esperado[linha["co_jogo"]]


def test_o_carimbo_CABE_na_coluna(linhas) -> None:
    """`VARCHAR(40)` — e o carimbo mais longo hoje tem 21 caracteres.

    ⚠️ Um carimbo truncado silenciosamente pelo banco apontaria para a linha
    errada da dimensao, ou para nenhuma.
    """
    for linha in linhas:
        assert len(linha["co_versao_motor"]) <= 40


# ═══════════════════════════════════════════════════════════════════════════
# 4. A migracao 0022
# ═══════════════════════════════════════════════════════════════════════════


def test_a_0022_cria_a_dimensao_com_as_colunas_que_o_job_grava(sql_da_0022) -> None:
    """🔒 Toda coluna `NOT NULL` sem `DEFAULT` aparece no `INSERT` do job.

    ⚠️ **Este defeito nao daria erro no CI e estouraria no Railway** — como o
    cadeado irmao de `tb001_desafio` (T049b) ja registra. E ele estouraria
    **antes** do primeiro desafio, derrubando a execucao inteira.
    """
    tabelas = tabelas_do_sql(sql_da_0022)
    assert "desafio.tb904_motor" in tabelas, "a 0022 nao cria a dimensao"

    insert = repositorio_mod.SQL_GRAVAR_MOTOR
    for nome, tipo in tabelas["desafio.tb904_motor"]["colunas"]:
        obrigatoria = "NOT NULL" in tipo and "DEFAULT" not in tipo
        if obrigatoria:
            assert nome in insert, (
                f"{nome} e NOT NULL sem DEFAULT e nao aparece no INSERT do job"
            )


def test_a_0022_tem_a_chave_da_dimensao(sql_da_0022) -> None:
    """`un001_motor` sobre `(co_versao_motor, co_jogo)` — o destino das FKs.

    ⚠️ Sem esta `UNIQUE` o Postgres **recusa** a FK composta, e a migracao
    falharia no meio. Com ela pela metade (so `co_versao_motor`), dois jogos do
    mesmo espelho nao caberiam na tabela.
    """
    limpo = " ".join(sql_da_0022.split())
    assert "CONSTRAINT un001_motor UNIQUE (co_versao_motor, co_jogo)" in limpo


@pytest.mark.parametrize(
    "tabela", ["desafio.tb001_desafio", "desafio.tb002_medicao_regua"]
)
def test_a_0022_referencia_a_dimensao_a_partir_das_DUAS_tabelas(
    sql_da_0022, tabela
) -> None:
    """🔒 *"Um catalogo que ninguem referencia nao e catalogo"* (o dono, 08/09).

    ⚠️ **E as duas tabelas carimbam o motor**: o desafio diz com que motor foi
    gerado, e a medicao da regua diz com que motor a taxa da Pita foi medida.
    Deixar a segunda sem FK permitiria uma medicao apontar para motor que ninguem
    declarou — que e exatamente a lacuna que a `fk001_perfil` ja fecha do lado do
    perfil.
    """
    limpo = " ".join(sql_da_0022.split())
    esperado = (
        f"ALTER TABLE {tabela} ADD CONSTRAINT fk002_motor FOREIGN KEY "
        "(co_versao_motor, co_jogo) REFERENCES desafio.tb904_motor "
        "(co_versao_motor, co_jogo) NOT VALID"
    )
    assert esperado in limpo


def test_as_FKs_sao_NOT_VALID_e_isso_e_DELIBERADO(sql_da_0022) -> None:
    """⚠️ O `des` ja tem desafios de antes da dimensao.

    A unica forma de valida-los agora seria **inventar** uma linha de dimensao
    para eles, com um `co_sha256` de manifesto que ninguem conferiu — ⛔ o oposto
    do que esta tabela existe para fazer. `NOT VALID` diz *"confira as novas, nao
    revarra as antigas"*, e ⛔ **nao afrouxa nada para frente**.
    """
    assert sql_da_0022.upper().count("NOT VALID") == 2


def test_a_MIGRACAO_nao_escreve_na_dimensao(sql_da_0022) -> None:
    """⛔ Quem grava e o job, nunca a migracao — a mesma regra do perfil.

    ⚠️ Uma migracao que soubesse o hash do motor estaria afirmando, por `INSERT`,
    um fato sobre arquivos que ela nao tem como conferir. E o mesmo argumento que
    deixa `tb903_perfil_dificuldade` nascer vazia.
    """
    assert not re.search(
        r"INSERT\s+INTO\s+desafio\.tb904_motor", sql_da_0022, re.I
    )


def test_a_0022_encadeia_na_0021() -> None:
    """A cadeia do Alembic nao pode ter ramo nem revisao orfa."""
    fonte = MIGRACAO.read_text(encoding="utf-8")
    assert 'revision: str = "0022_motor_decifravel"' in fonte
    assert 'down_revision: Union[str, None] = "0021_desafio_impedido"' in fonte
    # ⚠️ O id de revisao do Alembic tem limite de 32 caracteres: passar disso faz
    # o upgrade RODAR o DDL inteiro e falhar so no fim, revertendo tudo.
    assert len("0022_motor_decifravel") <= 32


# ═══════════════════════════════════════════════════════════════════════════
# 5. A escrita, pelo repositorio do job
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_garantir_motor_grava_UMA_linha_por_jogo(linhas) -> None:
    """Duas linhas, e os JSON viajam como texto para o `CAST(... AS JSONB)`."""
    sessao = FakeSessaoSQL(
        respostas={"INSERT INTO desafio.tb904_motor": [{"id_motor": "m"}]}
    )
    repositorio = repositorio_mod.RepositorioDoJob(sessao)

    assert await repositorio.garantir_motor(linhas) == 2

    parametros = [p for texto, p in sessao.executadas if "tb904_motor" in texto]
    assert len(parametros) == 2
    for p in parametros:
        # ⚠️ `json.loads` e a prova de que o que sobe e **texto**: passar o dict
        # direto faria o asyncpg recusar o parametro, e so no banco de verdade.
        assert json.loads(p["js_motores"])["versao"] == 1
        assert json.loads(p["js_arquivos"])["arquivos"]


@pytest.mark.asyncio
async def test_garantir_motor_e_IDEMPOTENTE(linhas) -> None:
    """⚠️ Zero linhas novas e o caso comum e saudavel.

    O `ON CONFLICT DO NOTHING` faz o `RETURNING` nao devolver nada quando a linha
    ja existe — e e assim que a contagem sai zero sem ninguem contar de novo.
    """
    sessao = FakeSessaoSQL(respostas={"INSERT INTO desafio.tb904_motor": []})
    repositorio = repositorio_mod.RepositorioDoJob(sessao)
    assert await repositorio.garantir_motor(linhas) == 0


def test_o_INSERT_nao_REESCREVE_a_linha_existente() -> None:
    """🔒 ⛔ `DO NOTHING`, e nunca `DO UPDATE`.

    ⚠️ A linha existente explica desafios **ja publicados**. Reescreve-la apagaria
    a procedencia de tudo o que foi medido com aquela versao — e sem erro nenhum,
    porque o `UPDATE` de um `ON CONFLICT` e sempre bem-sucedido.
    """
    sql = " ".join(repositorio_mod.SQL_GRAVAR_MOTOR.split())
    assert "ON CONFLICT (co_versao_motor, co_jogo) DO NOTHING" in sql
    assert "DO UPDATE" not in sql.upper()


@pytest.mark.asyncio
async def test_motores_orfaos_pergunta_pela_VIEW_e_nomeia_o_jogo() -> None:
    """A pergunta que adianta uma falha de **reprise**.

    ⚠️ A `fk002_motor` e `NOT VALID`, entao os desafios antigos ficaram como
    estavam — mas uma **reprise** copia o `co_versao_motor` da origem, e copia e
    linha nova. Se a origem for anterior a `0022`, o `INSERT` bate na FK ⛔ **no
    pior dia operacional**: aquele em que a fila de aprovados secou e a reprise e
    o unico caminho.
    """
    sessao = FakeSessaoSQL(
        respostas={
            "vw904_motor": [
                {"co_versao_motor": "damas-py-2f8e15cd", "co_jogo": "damas"}
            ]
        }
    )
    repositorio = repositorio_mod.RepositorioDoJob(sessao)

    assert await repositorio.motores_orfaos() == ["damas/damas-py-2f8e15cd"]
    # ⛔ Leitura vai a VIEW, escrita vai a tabela — a convencao desde a `0001`.
    assert "desafio.vw001_desafio" in repositorio_mod.SQL_MOTORES_ORFAOS
    assert "desafio.tb001_desafio" not in repositorio_mod.SQL_MOTORES_ORFAOS


# ═══════════════════════════════════════════════════════════════════════════
# 6. O lugar no encadeamento do job
# ═══════════════════════════════════════════════════════════════════════════


def test_o_job_IMPORTA_a_dimensao_do_motor() -> None:
    """🔒 Lido com `ast`, e nao com `in fonte`.

    ⚠️ Um arquivo bem documentado **menciona** o que ele nao faz — e foi assim
    que o cadeado de T043a reprovou codigo correto. Quem responde "este modulo
    usa aquele?" e a arvore, nunca o texto.
    """
    arvore = ast.parse(
        (RAIZ / "job" / "__main__.py").read_text(encoding="utf-8")
    )
    importados = {
        alias.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
        for alias in no.names
    }
    assert "motor" in importados


def test_a_dimensao_do_motor_NAO_conhece_o_banco() -> None:
    """⛔ `job/motor.py` monta linhas; quem grava e o repositorio.

    ⚠️ A mesma fronteira de `job/perfil.py`. Um modulo que soubesse gravar
    passaria a precisar de sessao para ser testado, e o cadeado que refaz a conta
    a partir da linha — o mais valioso daqui — deixaria de ser barato.
    """
    fonte = (RAIZ / "job" / "motor.py").read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    modulos = {
        no.module or ""
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
    }
    assert not any("banco" in m or "repositorio" in m for m in modulos)
    assert "sqlalchemy" not in fonte
