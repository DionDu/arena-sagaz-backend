"""As duas rotas que gravam o aparelho, pela porta HTTP (T118).

* `GET /v1/desafios/hoje` - a leitura que a Home faz ao abrir, e que passou a
  gravar a versão do app no dia do aparelho;
* `POST /v1/aparelhos/detalhes` - o envio diário dos detalhes, do app 1.4.

Os cabeçalhos passam pela dependência de verdade (`exigir_cabecalhos` e a do
aparelho); o serviço e o repositório do aparelho são os de verdade, sobre o
SQLite de `banco_de_aparelho_sqlite.py`. Só o desafio publicado e a identidade
do Firebase são de mentira.

⚠️ **O cliente é o `AsyncClient` com `ASGITransport`, e não o `TestClient`**: o
`TestClient` roda o app noutro laço de eventos, e a sessão do SQLite de memória
pertence ao laço do teste.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from api.aparelhos import rotas as rotas_aparelhos
from api.aparelhos.dependencias import obter_servico_aparelho
from api.aparelhos.repositorio import RepositorioAparelho
from api.aparelhos.servico import ServicoAparelho
from api.configuracao import configuracoes
from api.desafios import rotas as rotas_desafios
from api.desafios.rotas import obter_repositorio
from api.main import app
from api.nucleo.dependencias import usuario_atual_opcional
from api.nucleo.seguranca_firebase import IdentidadeFirebase
from tests.unitarios.banco_de_aparelho_sqlite import abrir_banco, linhas, trocar_cast_jsonb
from tests.unitarios.test_rotas_desafio_publicado import RepoFalso, _linha

APARELHO = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
UID = "firebase-uid-da-pessoa"
ID_USUARIO = "63385354-1e03-44bc-b2a3-82fdb8e34547"

#: 01h30 UTC de 20/10: 22h30 de 19/10 no Brasil. É o instante que separa o
#: dia UTC do dia local.
MADRUGADA_UTC = datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc)

#: O app 1.3 em campo: só os cabeçalhos de sempre.
CABECALHOS_1_3 = {"X-App-Version": "1.3.1", "X-Platform": "android", "Accept-Language": "pt-BR"}
#: O app 1.4: os de sempre, mais o código da instalação e o fuso.
CABECALHOS_1_4 = {
    "X-App-Version": "1.4.0",
    "X-Platform": "android",
    "Accept-Language": "es",
    "X-Install-Id": APARELHO,
    "X-Utc-Offset": "-180",
}


@pytest_asyncio.fixture
async def banco(monkeypatch):
    """A sessão do SQLite, ligada às duas rotas; o instante fixado na madrugada."""
    trocar_cast_jsonb(monkeypatch)
    engine, sessao = await abrir_banco()
    await sessao.execute(
        text("INSERT INTO conta.vw001_usuario VALUES (:id, :uid)"),
        {"id": ID_USUARIO, "uid": UID},
    )
    await sessao.commit()

    app.dependency_overrides[obter_servico_aparelho] = lambda: ServicoAparelho(
        repo=RepositorioAparelho(sessao), sessao=sessao
    )
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())
    monkeypatch.setattr(rotas_desafios, "agora_utc", lambda: MADRUGADA_UTC)
    monkeypatch.setattr(rotas_aparelhos, "agora_utc", lambda: MADRUGADA_UTC)
    yield sessao
    app.dependency_overrides.clear()
    await sessao.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as c:
        yield c


def _logado() -> None:
    app.dependency_overrides[usuario_atual_opcional] = lambda: IdentidadeFirebase(uid=UID)


async def _dias(sessao) -> list[dict]:
    return await linhas(
        sessao,
        "SELECT id_aparelho, dt_dia_local, id_usuario, co_versao_app, co_idioma, "
        "nu_espaco_app_kb, js_espaco_app FROM log.tb004_aparelho_dia",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. A leitura do desafio de hoje grava a versão do dia
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_app_1_4_grava_o_dia_LOCAL_com_a_versao_do_cabecalho(banco, cliente):
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)

    assert resposta.status_code == 200
    assert await _dias(banco) == [
        {
            "id_aparelho": APARELHO,
            "dt_dia_local": "2026-10-19",
            "id_usuario": None,
            "co_versao_app": "1.4.0",
            "co_idioma": "es",
            "nu_espaco_app_kb": None,
            "js_espaco_app": None,
        }
    ]


async def test_duas_aberturas_no_mesmo_dia_dao_uma_linha_com_a_maior_versao(banco, cliente):
    await cliente.get("/v1/desafios/hoje", headers={**CABECALHOS_1_4, "X-App-Version": "1.4.0"})
    await cliente.get("/v1/desafios/hoje", headers={**CABECALHOS_1_4, "X-App-Version": "1.4.1"})
    await cliente.get("/v1/desafios/hoje", headers={**CABECALHOS_1_4, "X-App-Version": "1.4.0"})

    dias = await _dias(banco)
    assert [(d["dt_dia_local"], d["co_versao_app"]) for d in dias] == [("2026-10-19", "1.4.1")]


async def test_o_app_1_3_logado_entra_como_legado(banco, cliente):
    _logado()
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_3)

    assert resposta.status_code == 200
    aparelhos = await linhas(banco, "SELECT ic_legado FROM log.tb003_aparelho")
    assert aparelhos == [{"ic_legado": 1}]
    dias = await _dias(banco)
    assert [(d["id_usuario"], d["co_versao_app"]) for d in dias] == [(ID_USUARIO, "1.3.1")]


async def test_o_convidado_1_3_le_o_desafio_e_nao_entra(banco, cliente):
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_3)

    assert resposta.status_code == 200
    assert await _dias(banco) == []


async def test_o_dia_sem_desafio_tambem_conta(banco, cliente):
    """O 404 `sem_desafio_hoje` é um dia em que o aparelho foi visto."""
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=None)
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)

    assert resposta.status_code == 404
    assert len(await _dias(banco)) == 1


async def test_um_codigo_ilegivel_nao_impede_ninguem_de_ver_o_desafio(banco, cliente):
    """Um `X-Install-Id` com defeito vale como ausente: o convidado continua
    vendo o desafio, e a leitura simplesmente não entra na amostra."""
    resposta = await cliente.get(
        "/v1/desafios/hoje", headers={**CABECALHOS_1_4, "X-Install-Id": "lixo"}
    )
    assert resposta.status_code == 200
    assert await _dias(banco) == []


async def test_a_falha_do_registro_nao_derruba_o_desafio(banco, cliente, monkeypatch, capsys):
    """O banco sem a 0036, uma corrida perdida: o desafio chega igual, e a falha
    fica no log com nome."""

    async def quebra(*_args, **_kwargs):
        raise RuntimeError("relation log.tb004_aparelho_dia does not exist")

    monkeypatch.setattr(RepositorioAparelho, "registrar_dia", quebra)
    resposta = await cliente.get("/v1/desafios/hoje", headers=CABECALHOS_1_4)

    assert resposta.status_code == 200
    assert resposta.json()["id_desafio"]
    # O logger do projeto escreve JSON no stdout e não propaga para o `caplog`.
    assert "registro do aparelho falhou" in capsys.readouterr().out
    # O `rollback` levou junto a linha do aparelho que a anotação começou: nada
    # fica pela metade.
    assert await linhas(banco, "SELECT 1 FROM log.tb003_aparelho") == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O envio diário dos detalhes
# ═══════════════════════════════════════════════════════════════════════════

CORPO = {
    "fabricante": "samsung",
    "modelo": "SM-A065M",
    "abi": "arm64-v8a",
    "processador": "MT6769V/CZ",
    "nucleos": 8,
    "ram_mb": 3741,
    "tela_largura_dp": 384,
    "tela_altura_dp": 853,
    "densidade_tela": 2.8125,
    "versao_so": "Android 14 (SDK 34)",
    # 200 MB e 3 KB: acima de 150, abaixo de 300.
    "espaco_app_kb": 204803,
    "espaco_app": {"cache": 190000, "tmp": 0, "banco": 332, "pasta_nova": 9},
}


@pytest.fixture
def limites(monkeypatch):
    """⚠️ Números DIFERENTES nas duas plataformas: com os dois em 150, um código
    que lesse o limite errado passaria igual."""
    monkeypatch.setattr(configuracoes, "ESPACO_APP_DETALHE_MB_ANDROID", 150)
    monkeypatch.setattr(configuracoes, "ESPACO_APP_DETALHE_MB_IOS", 300)


async def test_os_detalhes_respondem_202_e_gravam_o_aparelho(banco, cliente, limites):
    resposta = await cliente.post("/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json=CORPO)

    assert resposta.status_code == 202
    assert resposta.json() == {
        "registrado": True,
        "dia_local": "2026-10-19",
        "detalhe_do_espaco_guardado": True,
    }
    assert resposta.headers["cache-control"] == "no-store"
    aparelho = (await linhas(banco, "SELECT * FROM log.tb003_aparelho"))[0]
    assert (aparelho["no_modelo"], aparelho["qt_nucleos"], aparelho["nu_densidade_tela"]) == (
        "SM-A065M",
        8,
        "2.81",
    )


async def test_no_android_acima_do_limite_o_detalhe_e_guardado(banco, cliente, limites):
    await cliente.post("/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json=CORPO)

    dia = (await _dias(banco))[0]
    assert dia["nu_espaco_app_kb"] == 204803
    assert json.loads(dia["js_espaco_app"]) == {"cache": 190000, "tmp": 0, "banco": 332}


async def test_no_ios_os_mesmos_200_mb_ficam_abaixo_do_limite(banco, cliente, limites):
    resposta = await cliente.post(
        "/v1/aparelhos/detalhes",
        headers={**CABECALHOS_1_4, "X-Platform": "ios"},
        json=CORPO,
    )

    assert resposta.json()["detalhe_do_espaco_guardado"] is False
    dia = (await _dias(banco))[0]
    assert dia["nu_espaco_app_kb"] == 204803 and dia["js_espaco_app"] is None


async def test_o_limite_do_ios_tambem_e_lido(banco, cliente, limites):
    """Acima de 300 MB no iOS, guarda: o limite dele é lido, e não só existe."""
    resposta = await cliente.post(
        "/v1/aparelhos/detalhes",
        headers={**CABECALHOS_1_4, "X-Platform": "ios"},
        json={**CORPO, "espaco_app_kb": 300 * 1024 + 7},
    )
    assert resposta.json()["detalhe_do_espaco_guardado"] is True


async def test_os_detalhes_do_logado_levam_a_pessoa(banco, cliente, limites):
    _logado()
    await cliente.post("/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json=CORPO)
    assert (await _dias(banco))[0]["id_usuario"] == ID_USUARIO


@pytest.mark.parametrize("valor", [None, "lixo", str(uuid.uuid5(uuid.NAMESPACE_URL, "x"))])
async def test_sem_codigo_de_aparelho_os_detalhes_voltam_400(banco, cliente, valor):
    cabecalhos = {k: v for k, v in CABECALHOS_1_4.items() if k != "X-Install-Id"}
    if valor is not None:
        cabecalhos["X-Install-Id"] = valor
    resposta = await cliente.post("/v1/aparelhos/detalhes", headers=cabecalhos, json=CORPO)

    assert resposta.status_code == 400
    assert resposta.json()["codigo"] == "aparelho_invalido"
    assert await _dias(banco) == []


async def test_versao_ilegivel_nos_detalhes_volta_400(banco, cliente):
    resposta = await cliente.post(
        "/v1/aparelhos/detalhes",
        headers={**CABECALHOS_1_4, "X-App-Version": "dev"},
        json=CORPO,
    )
    assert resposta.status_code == 400
    assert resposta.json()["codigo"] == "versao_invalida"


async def test_texto_mais_largo_que_a_coluna_volta_422_e_nao_500(banco, cliente):
    """O modelo de 81 caracteres estouraria `no_modelo VARCHAR(80)` no banco."""
    resposta = await cliente.post(
        "/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json={**CORPO, "modelo": "M" * 81}
    )
    assert resposta.status_code == 422


async def test_densidade_que_nao_cabe_no_numeric_volta_422(banco, cliente):
    """`NUMERIC(4,2)` vai até 99,99."""
    resposta = await cliente.post(
        "/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json={**CORPO, "densidade_tela": 100}
    )
    assert resposta.status_code == 422


async def test_o_corpo_vazio_vale(banco, cliente):
    """Todos os campos são opcionais: um aparelho que não informa nada ainda
    deixa a versão do dia."""
    resposta = await cliente.post("/v1/aparelhos/detalhes", headers=CABECALHOS_1_4, json={})

    assert resposta.status_code == 202
    assert (await _dias(banco))[0]["co_versao_app"] == "1.4.0"
