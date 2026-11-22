"""O desafio do xadrez num app 1.4.0: a tela de atualizar, e a chama (T080 da spec 012).

⚠️ **Nada aqui é código novo: é a CONFERÊNCIA de um caminho que já existe**
(RF-DES-021/024, spec 009; RF-XDR-187, RF-XDR-235, SC-015 da 012), no molde de
`test_quatro_num_app_1_3.py`. O xadrez chega na 1.6.0; quem está na 1.4.0 e abre
o app num dia de desafio de xadrez precisa (1) receber o desafio numa forma que o
parser da 1.4.0 aceita, (2) cair na tela de atualizar e (3) **não perder a chama**
por isso. Os passos atravessam a porta HTTP de verdade, com os cabeçalhos que a
1.4.0 manda.

⚠️ **O que é "a 1.4.0" aqui.** É a versão EM CAMPO nas duas lojas, a 1.4.0+18
(`version: 1.4.0+18`, commit `2f35759a` do frontend, tag `v1.4.0+18`). Até
21/11/2026 este arquivo falava da 1.5.0 (os cards, spec 011), mas ela não foi às
lojas sozinha: a próxima versão publicada leva os cards E o xadrez
(`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zzzz67). ⚠️ Nada do que este
arquivo confere mudou de uma para a outra: os cinco arquivos citados abaixo são
idênticos entre `2f35759a` (1.4.0+18) e `958fd93c` (1.5.0+19), conferido por
`git diff` em 22/11/2026. A única diferença no caminho é o `Accept-Language`, que a
1.4.0 monta com `locale?.languageCode ?? 'pt'` (o código da língua, sem região).
Os trechos citados abaixo são da 1.4.0+18:

  * os cabeçalhos: `lib/core/rede/cliente_api.dart` (`_aoEnviar`): a versão é o
    `PackageInfo.version`, **sem** o build (`1.4.0`), mais `X-Platform`,
    `Accept-Language`, `X-Install-Id` e `X-Utc-Offset` (desde a 1.4);
  * o parser: `lib/core/desafios/desafio.dart` (`Desafio.doJson`). ⚠️ No
    formato `fen` ele EXIGE `tabuleiro` como texto e recusa `tabuleiro` e
    `posicao` juntos: um desafio de xadrez servido com a posição inteira no
    `posicao` seria `DesafioInvalido`, que sobe como defeito do dado - a 1.4.0
    não grava o dia impedido, e a chama da pessoa quebra. É o defeito caro, e o
    1º caso abaixo o trava para os onze tipos;
  * a compatibilidade: `lib/modulos/desafio_do_dia/logica/compatibilidade.dart`
    confere o JOGO antes de tudo (`app.jogos[desafio.jogo]`), e a 1.4.0 conhece
    `damas`, `pontinhos` e `quatro` (`capacidades_deste_app.dart`): o xadrez é
    `jogo_desconhecido`;
  * o dia impedido: `lib/modulos/desafio_do_dia/dados/registro_de_impedimento.dart`
    (o corpo de `registrar`, sem `motores`, como o provider o chama).

E a outra travessia (SC-015): a partida de xadrez de um app 1.6.0 chegando a um
backend sem o ingestor do xadrez (o da `main`, que o `prd` roda até o merge)
**sobe sem o objeto**, com o aviso de extensão desconhecida, e não é rejeitada.
"""
from __future__ import annotations

import logging
import random
import sqlite3
import uuid
from datetime import date, datetime

import pytest
import pytest_asyncio
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
from api.nucleo.dependencias import usuario_atual_opcional
from api.nucleo.dependencias_conta_nuvem import usuario_autenticado
from api.sincronizacao import repositorio as modulo_repositorio
from api.sincronizacao.repositorio import (
    _avisar_extensao_de_partida_desconhecida,
    _avisar_extensao_desconhecida,
    calcular_sequencia_de_dias,
)
from api.sincronizacao.validacao import validar_evento
from job import provas_xadrez as pv
from job.editorial import EDITORIAL, VERSAO_MINIMA_DO_XADREZ
from job.medidas_de_saida import PARAMETRO_LANCES_DA_SOLUCAO
from job.tipos_de_desafio import RECEITAS
from tests.unitarios.banco_de_aparelho_sqlite import abrir_banco, linhas, trocar_cast_jsonb
from tests.unitarios.test_contrato_extensao_xadrez import (
    EXTENSAO_JOGADA_CPU,
    EXTENSAO_PARTIDA_XADREZ,
    _evento,
    _jogada,
    _partida,
)
from tests.unitarios.test_quatro_num_app_1_3 import (
    CAST_MOTORES,
    DIA_LOCAL,
    ID_USUARIO,
    MADRUGADA_UTC,
    _dono_pelo_cabecalho,
    _ESQUEMA_DO_DIA_IMPEDIDO,
    _impedidos,
    _ramo_dos_dias_impedidos,
)
from tests.unitarios.test_rotas_desafio_publicado import RepoFalso, _linha

# O `sqlite3` não sabe guardar `UUID` nem `datetime` sem adaptador (ver o
# arquivo do Quatro: a rota manda os dois).
sqlite3.register_adapter(uuid.UUID, str)
sqlite3.register_adapter(datetime, lambda d: d.isoformat())

#: Os cabeçalhos da 1.4.0 (`cliente_api.dart` da 1.4.0+18): a versão SEM o build,
#: o idioma só com a língua (`languageCode`), o código da instalação e o
#: deslocamento em minutos, como texto.
CABECALHOS_1_4 = {
    "X-App-Version": "1.4.0",
    "X-Platform": "android",
    "Accept-Language": "pt",
    "X-Install-Id": "5b0c8f3e-2d4a-4c1e-9f7b-0a6d3e8c1b2f",
    "X-Utc-Offset": "-180",
}

#: Os tipos do xadrez no ar (T078): todo dia de xadrez é um deles.
TIPOS_NO_AR = sorted(t for t, r in RECEITAS.items() if r.co_jogo == "xadrez")

#: Os jogos que a 1.4.0 julga no desafio (`capacidades_deste_app.dart` da 1.4.0+18).
JOGOS_DA_1_4 = frozenset({"damas", "pontinhos", "quatro"})

#: As extensões que o backend da `main` sabe gravar (`_EXTENSOES_CONHECIDAS` de
#: `api/sincronizacao/repositorio.py` na `main`): sem o xadrez.
EXTENSOES_DO_BACKEND_DA_MAIN = frozenset({"pontinhos", "velha", "damas", "quatro"})


def _linha_do_xadrez(co_tipo: str) -> dict:
    """O desafio de hoje do xadrez, como `repositorio.py` o devolveria.

    ⚠️ Com as peças REAIS do job, como no Quatro: a posição sorteada pelo mesmo
    `sortear_posicao` do gerador, a chegada e a frase da receita com as peças da
    posição, e as medidas de saída da 1ª publicação do editorial.
    """
    receita = RECEITAS[co_tipo]
    publicacao = EDITORIAL[co_tipo][0]
    escolhida = pv.sortear_posicao(
        random.Random(7), co_tipo=co_tipo, parametros=dict(publicacao.parametros), co_personagem=None
    )
    # As peças escolhidas entram nos parâmetros, como no gerador.
    parametros = {**publicacao.parametros, **escolhida.pecas}
    linha = _linha(co_jogo="xadrez", co_formato="fen")
    linha.update(
        co_modalidade="tradicional",
        # A variante do xadrez É a modalidade (`job/gerador.py`).
        co_variante="tradicional",
        js_posicao_inicial=escolhida.js_posicao_inicial,
        co_tipo_desafio=co_tipo,
        js_chegada=receita.montar(parametros),
        co_chave_objetivo=receita.co_chave_objetivo,
        js_objetivo=receita.valores_da_frase(parametros, "tex"),
        co_personagem="tex",
        co_versao_minima=publicacao.co_versao_minima,
        # ⚠️ O job põe o tamanho do gabarito nos parâmetros na hora de publicar
        # (`job/__main__.py`, T049t); sete lances é um gabarito qualquer.
        medidas_de_saida=publicacao.medidas({**parametros, PARAMETRO_LANCES_DA_SOLUCAO: 7}),
    )
    return linha


@pytest_asyncio.fixture
async def banco(monkeypatch):
    """A sessão do SQLite ligada às rotas, com um desafio de xadrez no ar."""
    trocar_cast_jsonb(monkeypatch)
    assert CAST_MOTORES in modulo_impedido.SQL_GRAVAR_IMPEDIDO
    monkeypatch.setattr(
        modulo_impedido,
        "SQL_GRAVAR_IMPEDIDO",
        modulo_impedido.SQL_GRAVAR_IMPEDIDO.replace(CAST_MOTORES, ":js_motores"),
    )

    engine, sessao = await abrir_banco()
    for comando in _ESQUEMA_DO_DIA_IMPEDIDO:
        await sessao.execute(text(comando))

    linha = _linha_do_xadrez("xadrez_espia_comer")
    # O dia e o desafio, para a subconsulta da versão exigida achar o "1.6.0".
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
    """O cliente HTTP no mesmo laço de eventos da sessão do SQLite."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as c:
        yield c


def _corpo_do_impedido(linha: dict) -> dict:
    """O que a 1.4.0 manda (`registro_de_impedimento.dart` da 1.4.0+18)."""
    return {
        "id_desafio_dia": str(linha["id_desafio_dia"]),
        "motivo": "jogo_desconhecido",
        "desconhecido": "xadrez",
        "visitado_em": MADRUGADA_UTC.isoformat(),
        "nu_offset_minuto": -180,
    }


def _o_parser_da_1_4_aceita(corpo: dict) -> None:
    """As exigências de `Desafio.doJson` da 1.4.0, campo a campo.

    ⚠️ Qualquer uma que falhe é `DesafioInvalido` lá: o app nem chega à
    compatibilidade, e o dia impedido não é gravado.
    """
    for campo in (
        "id_desafio", "jogo", "tipo", "forma_verificacao", "variante",
        "personagem", "versao_minima_app", "versao_perfil",
    ):
        assert isinstance(corpo[campo], str) and corpo[campo], campo
    # O formato fechado, e no `fen` o `tabuleiro` como texto e a `posicao` vazia
    # (os dois juntos são recusados).
    assert corpo["formato_posicao"] == "fen"
    assert isinstance(corpo["tabuleiro"], str) and corpo["tabuleiro"]
    assert corpo["posicao"] is None
    assert isinstance(corpo["parametros"], dict)
    assert isinstance(corpo["objetivo"]["chave"], str) and corpo["objetivo"]["chave"]
    assert isinstance(corpo["semente"], int) and 1 <= corpo["semente"] <= 4294967295
    assert isinstance(corpo["teto_log_meios_lances"], int) and corpo["teto_log_meios_lances"] >= 1
    assert 0 < corpo["tempo_piso_ms"] < corpo["tempo_teto_ms"]
    assert corpo["medidas_de_saida"], "lista vazia é DesafioInvalido na 1.4.0"
    for medida in corpo["medidas_de_saida"]:
        assert isinstance(medida["chave"], str) and medida["chave"]
        assert 0 <= medida["peso"] <= 1
        # As três normalizações que a 1.4.0 conhece, com o que cada uma exige.
        assert medida["normalizacao"] in {"faixa", "fracao", "nenhuma"}, medida
        if medida["normalizacao"] == "faixa":
            assert isinstance(medida["minimo"], (int, float)), medida
            assert isinstance(medida["maximo"], (int, float)), medida
        if medida["normalizacao"] == "fracao":
            assert isinstance(medida["sobre"], str) and medida["sobre"], medida
    assert corpo["regua_nota"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O servidor entrega, numa forma que a 1.4.0 lê; quem decide é o app
# ═══════════════════════════════════════════════════════════════════════════


async def test_a_1_4_RECEBE_o_desafio_do_xadrez_com_a_versao_minima_dele(banco, cliente):
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["jogo"] == "xadrez"
    assert corpo["versao_minima_app"] == VERSAO_MINIMA_DO_XADREZ == "1.6.0"
    # A versão da 1.4.0 é MENOR que a exigida, pela régua do servidor.
    assert chave_da_versao(CABECALHOS_1_4["X-App-Version"]) < chave_da_versao("1.6.0")
    # E o jogo não é nenhum dos que a 1.4.0 julga: a compatibilidade dela para
    # no 1º passo, com `jogo_desconhecido`.
    assert corpo["jogo"] not in JOGOS_DA_1_4


@pytest.mark.parametrize("co_tipo", TIPOS_NO_AR)
async def test_cada_tipo_do_xadrez_passa_no_parser_da_1_4(co_tipo, monkeypatch, cliente):
    """🔒 Os onze, um por um: a forma que o parser da 1.4.0 exige."""
    linha = _linha_do_xadrez(co_tipo)
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=linha)
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    monkeypatch.setattr(rotas_desafios, "agora_utc", lambda: MADRUGADA_UTC)
    try:
        resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)
    finally:
        app.dependency_overrides.clear()

    assert resposta.status_code == 200
    corpo = resposta.json()
    _o_parser_da_1_4_aceita(corpo)
    # O FEN servido é o da posição publicada.
    assert corpo["tabuleiro"] == linha["js_posicao_inicial"]["fen"]

    # ⚠️ E o resto da posição chega pelo campo NOVO (§8zzzz66), que a 1.4.0
    # ignora: tudo o que o job gravou, menos a FEN (que já veio no `tabuleiro`).
    # Sem ele, a 1.6.0 não saberia a cor da pessoa, nem qual peça é a espiã.
    esperado = {
        chave: valor
        for chave, valor in linha["js_posicao_inicial"].items()
        if chave != "fen"
    }
    assert corpo["complemento_posicao"] == esperado
    assert "fen" not in corpo["complemento_posicao"], "a FEN tem uma fonte só"
    assert corpo["complemento_posicao"]["cor_da_pessoa"] in ("branca", "preta")


async def test_nas_DAMAS_o_complemento_continua_nulo(monkeypatch, cliente):
    """🔒 O campo novo não muda as damas: a posição delas é `{versao, fen, vez_de}`,
    tudo o que a FEN já diz, e o complemento sai `null`.

    ⚠️ É o que deixa a decisão de 21/11/2026 sem efeito nos três jogos que já
    estão em campo.
    """
    linha = _linha()
    assert linha["co_formato_posicao"] == "fen", "o molde é o das damas"
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=linha)
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    monkeypatch.setattr(rotas_desafios, "agora_utc", lambda: MADRUGADA_UTC)
    try:
        resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)
    finally:
        app.dependency_overrides.clear()

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["jogo"] == "damas"
    assert corpo["complemento_posicao"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. O dia impedido, gravado com a versão do cabeçalho
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_dia_impedido_da_1_4_e_GRAVADO_no_dia_local(banco, cliente):
    sessao, linha = banco

    resposta = await cliente.post(
        "/v1/desafios/impedido", headers=CABECALHOS_1_4, json=_corpo_do_impedido(linha)
    )

    assert resposta.status_code == 204
    assert await _impedidos(sessao) == [
        {
            # 01h30 UTC de 20/10 é a noite de 19/10 para quem visitou.
            "dt_dia_local": DIA_LOCAL.isoformat(),
            "co_motivo": "jogo_desconhecido",
            "co_desconhecido": "xadrez",
            # Do CABEÇALHO...
            "co_versao_app": "1.4.0",
            "co_plataforma": "android",
            # ... e do BANCO: os dois lados do par de diagnóstico.
            "co_versao_minima_exigida": "1.6.0",
        }
    ]


async def test_abrir_o_app_de_novo_no_mesmo_dia_NAO_duplica(banco, cliente):
    sessao, linha = banco
    for _ in range(3):
        resposta = await cliente.post(
            "/v1/desafios/impedido", headers=CABECALHOS_1_4, json=_corpo_do_impedido(linha)
        )
        assert resposta.status_code == 204
    assert len(await _impedidos(sessao)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. A chama lê esse dia, e sobrevive a ele
# ═══════════════════════════════════════════════════════════════════════════


async def test_a_chama_LE_o_dia_que_a_rota_gravou(banco, cliente):
    sessao, linha = banco
    await cliente.post(
        "/v1/desafios/impedido", headers=CABECALHOS_1_4, json=_corpo_do_impedido(linha)
    )

    dias = await linhas(sessao, _ramo_dos_dias_impedidos(), id=ID_USUARIO)

    assert dias == [{"dia": DIA_LOCAL.isoformat()}]
    assert await linhas(sessao, _ramo_dos_dias_impedidos(), id=str(uuid.uuid4())) == []


def test_o_dia_impedido_SEGURA_a_sequencia():
    """Jogou em 17 e 18/10, abriu a 1.4.0 no dia do xadrez (19/10) e jogou em 20/10."""
    jogados = [date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 20)]

    assert calcular_sequencia_de_dias(sorted([*jogados, DIA_LOCAL])) == 4
    assert calcular_sequencia_de_dias(jogados) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. A partida do xadrez num backend sem o ingestor dele
# ═══════════════════════════════════════════════════════════════════════════


def _evento_do_xadrez() -> dict:
    """A partida que a 1.6.0 manda, com a extensão na partida e na jogada."""
    return _evento(
        [_jogada(xadrez=EXTENSAO_JOGADA_CPU)],
        partida=_partida(xadrez=EXTENSAO_PARTIDA_XADREZ),
    )


def test_a_partida_do_xadrez_e_ACEITA_pela_validacao_de_sempre():
    """⚠️ `validacao.py` é o mesmo da `main` (nenhuma linha mudou na branch):
    o evento da 1.6.0 não é rejeitado por trazer `xadrez`."""
    assert validar_evento(_evento_do_xadrez()) is None


def test_no_backend_da_main_a_extensao_vai_ao_aviso_e_nao_derruba(monkeypatch, caplog):
    """O backend sem o detalhe: a extensão é ignorada com o aviso (V-5).

    ⚠️ Rejeitar faria o app descartar a partida inteira; ignorar perde só o
    detalhe. O conjunto é o da `main`, escrito por extenso acima.
    """
    monkeypatch.setattr(
        modulo_repositorio, "_EXTENSOES_CONHECIDAS", EXTENSOES_DO_BACKEND_DA_MAIN
    )
    evento = _evento_do_xadrez()
    with caplog.at_level(logging.WARNING):
        _avisar_extensao_de_partida_desconhecida(evento["payload"]["partida"])
        _avisar_extensao_desconhecida(evento["payload"]["jogadas"][0])
    avisos = [r.getMessage() for r in caplog.records]
    assert len(avisos) == 2
    assert all("'xadrez'" in aviso and "ACEITO" in aviso for aviso in avisos)


def test_e_neste_backend_o_xadrez_e_conhecido(caplog):
    """O outro sentido: aqui ele não gera aviso (o ingestor existe)."""
    evento = _evento_do_xadrez()
    with caplog.at_level(logging.WARNING):
        _avisar_extensao_de_partida_desconhecida(evento["payload"]["partida"])
        _avisar_extensao_desconhecida(evento["payload"]["jogadas"][0])
    assert caplog.records == []


# ═══════════════════════════════════════════════════════════════════════════
# 1b. O complemento da posição, sem o HTTP (§8zzzz66)
# ═══════════════════════════════════════════════════════════════════════════


def test_o_complemento_e_so_do_formato_fen_e_nunca_traz_a_fen():
    """🔒 As três formas de posição que existem, uma por linha."""
    from api.desafios.publicacao import complemento_publicado

    # As damas: tudo o que a posição tem a FEN já diz, e o complemento é nulo.
    damas = {"versao": 1, "fen": "W:W18,24,K27:B12,16,K22", "vez_de": 1}
    assert complemento_publicado("fen", damas) is None
    # O Pontinhos e o Quatro: a posição inteira já vai em `posicao`.
    sequencia = {"versao": 1, "lances": [], "vez_de": 1}
    assert complemento_publicado("sequencia_lances", sequencia) is None
    # Posição ausente não derruba a resposta.
    assert complemento_publicado("fen", None) is None
    # O xadrez: sobra tudo menos a FEN.
    xadrez = {
        "jogo": "xadrez",
        "modalidade": "tradicional",
        "fen": "4k3/8/8/8/8/2N5/8/4K3 w - - 0 1",
        "cor_da_pessoa": "branca",
        "marcas": {"espia": "c3"},
        "origem": "base_equilibrada",
    }
    assert complemento_publicado("fen", xadrez) == {
        "jogo": "xadrez",
        "modalidade": "tradicional",
        "cor_da_pessoa": "branca",
        "marcas": {"espia": "c3"},
        "origem": "base_equilibrada",
    }
    # E a posição gravada não é alterada (a função copia, não remove).
    assert "fen" in xadrez
