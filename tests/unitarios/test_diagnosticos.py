"""Testes de `POST /v1/diagnosticos/motor-nativo` (T199b).

Sem Postgres: o serviço é trocado por um fake que só registra o que recebeu
(`dependency_overrides`). O que se valida aqui é o **contrato**: status, corpo,
e — principalmente — as regras do desenho que, se quebradas, não dariam erro
nenhum e só apareceriam como dado faltando meses depois.

⚠️ **A regra 1 (deduplicar) não é testada aqui**, e é de propósito: ela mora no
APP, não no servidor. Deduplicar aqui exigiria um identificador estável de
aparelho, que a regra 5 proíbe. O cadeado dela está em
`arena-sagaz-frontend/test/modulos/jogos/damas/relato_motor_nativo_test.dart`.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from api.diagnosticos.rotas import obter_servico_diagnostico
from api.main import app
from api.nucleo.dependencias import usuario_atual_opcional
from api.nucleo.seguranca_firebase import IdentidadeFirebase

# Cabeçalhos que a diretriz de versionamento da API torna obrigatórios em TODA
# requisição do app. É deles que saem `co_plataforma` e `co_versao_app`.
CABECALHOS = {"X-App-Version": "1.1.0+8", "X-Platform": "android"}

# Um corpo mínimo válido — só o que o modelo exige.
CORPO_MINIMO = {"jogo": "damas", "motor": "rust", "motivo": "biblioteca_ausente"}


class FakeServicoDiagnostico:
    """Guarda o que a rota mandou gravar, sem tocar em banco."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[Optional[str], dict[str, Any]]] = []

    async def registrar_motor_nativo(
        self, uid: Optional[str], dados: dict[str, Any]
    ) -> str:
        self.chamadas.append((uid, dados))
        return "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def fake() -> FakeServicoDiagnostico:
    return FakeServicoDiagnostico()


@pytest.fixture
def client(fake):
    app.dependency_overrides[obter_servico_diagnostico] = lambda: fake
    # O padrão de toda a suíte: sem token, e sem Firebase para verificar.
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
# O contrato básico
# ═══════════════════════════════════════════════════════════════════════════


def test_relato_minimo_devolve_202_e_o_id(client, fake):
    r = client.post(
        "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=CORPO_MINIMO
    )

    # 202 e não 201: não há recurso a buscar depois. Ver a docstring da rota.
    assert r.status_code == 202
    assert r.json() == {
        "id_diagnostico": "11111111-2222-3333-4444-555555555555",
        "registrado": True,
    }
    assert len(fake.chamadas) == 1


def test_a_resposta_nao_e_cacheavel(client):
    r = client.post(
        "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=CORPO_MINIMO
    )
    # Um proxy que guardasse o 202 faria os relatos seguintes nunca chegarem.
    assert r.headers.get("Cache-Control") == "no-store"


def test_o_corpo_completo_chega_inteiro_ao_servico(client, fake):
    corpo = {
        **CORPO_MINIMO,
        "motivo": "versao_insuficiente",
        "detalhe": "binario 0.2.0 e mais velho que o minimo 0.3.0",
        "versao_binario_esperada": "0.3.0",
        "versao_binario_encontrada": "0.2.0",
        "versao_so": "Android 13 (SDK 33)",
        "modelo_aparelho": "samsung SM-A045M",
        "abi": "arm64-v8a",
        "flavor": "prd",
        "modo_build": "release",
    }
    r = client.post(
        "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=corpo
    )
    assert r.status_code == 202

    _uid, dados = fake.chamadas[0]
    assert dados["co_motivo"] == "versao_insuficiente"
    assert dados["de_motivo"].startswith("binario 0.2.0")
    assert dados["co_versao_binario_esperada"] == "0.3.0"
    assert dados["co_versao_binario_encontrada"] == "0.2.0"
    assert dados["co_versao_so"] == "Android 13 (SDK 33)"
    assert dados["no_modelo_aparelho"] == "samsung SM-A045M"
    assert dados["co_abi"] == "arm64-v8a"
    assert dados["co_flavor"] == "prd"
    assert dados["co_modo_build"] == "release"


# ═══════════════════════════════════════════════════════════════════════════
# Regra 2 — funciona SEM login, e este é o caso mais provável
# ═══════════════════════════════════════════════════════════════════════════


def test_convidado_sem_token_registra_com_dono_nulo(client, fake):
    r = client.post(
        "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=CORPO_MINIMO
    )
    assert r.status_code == 202
    uid, _dados = fake.chamadas[0]
    # `None` aqui não é falta de dado: é a sessão de convidado, que é justamente
    # quem está experimentando o app pela primeira vez.
    assert uid is None


def test_com_token_valido_o_uid_chega_ao_servico(fake):
    app.dependency_overrides[obter_servico_diagnostico] = lambda: fake
    app.dependency_overrides[usuario_atual_opcional] = lambda: IdentidadeFirebase(
        uid="uid-de-teste"
    )
    try:
        c = TestClient(app)
        r = c.post(
            "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=CORPO_MINIMO
        )
        assert r.status_code == 202
        uid, _dados = fake.chamadas[0]
        assert uid == "uid-de-teste"
    finally:
        app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
# A plataforma e a versão vêm do CABEÇALHO, e não do corpo
# ═══════════════════════════════════════════════════════════════════════════


def test_plataforma_e_versao_saem_dos_cabecalhos(client, fake):
    client.post(
        "/v1/diagnosticos/motor-nativo",
        headers={"X-App-Version": "1.2.0+9", "X-Platform": "ios"},
        json=CORPO_MINIMO,
    )
    _uid, dados = fake.chamadas[0]
    assert dados["co_plataforma"] == "ios"
    assert dados["co_versao_app"] == "1.2.0+9"


def test_plataforma_web_vira_outra_e_nao_nulo(client, fake):
    """`X-Platform: web` é válido para a API (ambiente de desenvolvimento), mas
    não é um aparelho que se possa consertar. Ele vira `outra` — e **não**
    `NULL`, que o faria sumir de qualquer contagem por plataforma."""
    client.post(
        "/v1/diagnosticos/motor-nativo",
        headers={"X-App-Version": "1.1.0", "X-Platform": "web"},
        json=CORPO_MINIMO,
    )
    _uid, dados = fake.chamadas[0]
    assert dados["co_plataforma"] == "outra"


def test_sem_cabecalho_obrigatorio_da_400(client, fake):
    r = client.post("/v1/diagnosticos/motor-nativo", json=CORPO_MINIMO)
    assert r.status_code == 400
    assert not fake.chamadas


# ═══════════════════════════════════════════════════════════════════════════
# Os conjuntos fechados — o 422 aqui existe para não virar 500 lá
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("motor", "wasm"),
        ("motivo", "deu_ruim"),
        ("flavor", "homolog"),
        ("modo_build", "jit"),
    ],
)
def test_valor_fora_do_conjunto_da_422_e_nao_chega_ao_banco(
    client, fake, campo, valor
):
    """Cada um destes espelha um `CHECK` da migração 0016.

    ⚠️ **É por isso que a validação existe em dois lugares.** Um valor que
    passasse aqui e batesse no `CHECK` do banco viraria um `500` no meio da
    noite, com o relato perdido — em vez de um `422` claro, na hora, apontando
    o campo.
    """
    r = client.post(
        "/v1/diagnosticos/motor-nativo",
        headers=CABECALHOS,
        json={**CORPO_MINIMO, campo: valor},
    )
    assert r.status_code == 422
    assert not fake.chamadas


def test_detalhe_longo_demais_da_422(client, fake):
    """300 é o tamanho da coluna `de_motivo`. O app já corta antes de enviar;
    isto é a segunda rede, para uma build antiga que não cortasse não tomar
    `500` do banco."""
    r = client.post(
        "/v1/diagnosticos/motor-nativo",
        headers=CABECALHOS,
        json={**CORPO_MINIMO, "detalhe": "x" * 301},
    )
    assert r.status_code == 422
    assert not fake.chamadas


def test_plataforma_sem_motor_e_valor_legitimo(client, fake):
    """Não é defeito: é o que a VM do `flutter test` e qualquer desktop
    respondem. Está no conjunto para não cair em `falha_desconhecida` e poluir
    a contagem do que importa."""
    r = client.post(
        "/v1/diagnosticos/motor-nativo",
        headers=CABECALHOS,
        json={**CORPO_MINIMO, "motivo": "plataforma_sem_motor"},
    )
    assert r.status_code == 202
    _uid, dados = fake.chamadas[0]
    assert dados["co_motivo"] == "plataforma_sem_motor"
