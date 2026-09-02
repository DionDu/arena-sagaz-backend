"""Testes de `POST /v1/diagnosticos/motor-nativo` (T199b).

Sem Postgres: o serviço é trocado por um fake que só registra o que recebeu
(`dependency_overrides`). O que se valida aqui é o **contrato**: status, corpo,
e — principalmente — as regras do desenho que, se quebradas, não dariam erro
nenhum e só apareceriam como dado faltando meses depois.

O dedupe mora nos **dois lados**, e cada um tem o seu cadeado:

* no **app** é economia de rede, e se perde numa reinstalação —
  `arena-sagaz-frontend/test/core/diagnosticos/relato_motor_nativo_test.dart`;
* no **servidor** é a garantia (`co_assinatura UNIQUE` + `ON CONFLICT DO
  UPDATE`), e o critério dela está guardado no último grupo deste arquivo.

⚠️ **A versão anterior deste cabeçalho dizia que o dedupe do servidor era
impossível "porque exigiria um identificador estável de aparelho".** Estava
errado: deduplicar por **configuração** (modelo, ABI, SO, versões, motivo) não
precisa de identificador de pessoa nenhum — e é exatamente a unidade que se quer
contar.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from api.diagnosticos.repositorio import calcular_assinatura
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
    """Guarda o que a rota mandou gravar, sem tocar em banco.

    Devolve `(id, ocorrencias)` como o serviço de verdade — a tabela guarda uma
    linha por CONFIGURAÇÃO, e o contador vem do UPSERT.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[Optional[str], dict[str, Any]]] = []
        self.ocorrencias = 1

    async def registrar_motor_nativo(
        self, uid: Optional[str], dados: dict[str, Any]
    ) -> tuple[str, int]:
        self.chamadas.append((uid, dados))
        return "11111111-2222-3333-4444-555555555555", self.ocorrencias


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
        "ocorrencias": 1,
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
        "versao_motor": "dart_1.3.0",
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
    assert dados["co_versao_motor"] == "dart_1.3.0"
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


def test_um_stacktrace_inteiro_CABE(client, fake):
    """⚠️ O teto era 300, e a pergunta do dono em 27/08 foi se aquilo comportava
    um stacktrace. **Não comportava** — um stacktrace de Dart tem alguns
    milhares de caracteres, e 300 mal cobrem a primeira linha. A coluna virou
    `TEXT` e o teto do modelo, 4000."""
    stack = "\n".join(
        f"#{i}      MotorRustDamas._carregarUmaVezSo "
        f"(package:arena_sagaz_frontend/modulos/jogos/damas/motor_nativo/"
        f"ponte_rust_damas.dart:{140 + i}:7)"
        for i in range(20)
    )
    assert len(stack) > 300, "o exemplo tem de ser maior que o teto antigo"

    r = client.post(
        "/v1/diagnosticos/motor-nativo",
        headers=CABECALHOS,
        json={**CORPO_MINIMO, "detalhe": stack},
    )
    assert r.status_code == 202
    _uid, dados = fake.chamadas[0]
    assert dados["de_motivo"] == stack


def test_detalhe_absurdo_ainda_da_422(client, fake):
    """O teto de 4000 deixou de espelhar a coluna e virou **sanidade**: ele
    impede que um defeito no app despeje megabytes num endpoint que aceita
    convidado sem login."""
    r = client.post(
        "/v1/diagnosticos/motor-nativo",
        headers=CABECALHOS,
        json={**CORPO_MINIMO, "detalhe": "x" * 4001},
    )
    assert r.status_code == 422
    assert not fake.chamadas


def test_a_resposta_devolve_o_contador_de_ocorrencias(client, fake):
    """O contador serve ao **operador**: dá para bater um relato de suporte
    ("meu Sagaz sumiu") contra a linha certa sem abrir o banco."""
    fake.ocorrencias = 47
    r = client.post(
        "/v1/diagnosticos/motor-nativo", headers=CABECALHOS, json=CORPO_MINIMO
    )
    assert r.json()["ocorrencias"] == 47


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


# ═══════════════════════════════════════════════════════════════════════════
# A ASSINATURA — a garantia de que um telefone não infla a tabela
# ═══════════════════════════════════════════════════════════════════════════
#
# A pergunta do dono em 27/08/2026 foi: "O que vai garantir aí que um mesmo
# telefone de 1 usuário não vai ficar alimentando essa tabela indefinidamente
# com o mesmo registro?"
#
# A resposta é `co_assinatura UNIQUE` + `ON CONFLICT DO UPDATE`. O que estes
# testes guardam é o **critério** da assinatura — o `UNIQUE` do banco não tem
# como saber se ela foi calculada certo, e um erro aqui não daria erro nenhum:
# só faria a tabela voltar a crescer por relato, calada.


def _base() -> dict:
    """Um conjunto completo de colunas, para variar um campo por vez."""
    return {
        "co_jogo": "damas",
        "co_motor": "rust",
        "co_motivo": "biblioteca_ausente",
        "co_plataforma": "android",
        "co_versao_so": "Android 13 (SDK 33)",
        "no_modelo_aparelho": "samsung SM-A045M",
        "co_abi": "arm64-v8a",
        "co_versao_app": "1.1.0+8",
        "co_versao_motor": "dart_1.3.0",
        "co_versao_binario_encontrada": None,
        "co_flavor": "prd",
        "co_modo_build": "release",
    }


def test_a_mesma_configuracao_da_a_mesma_assinatura():
    assert calcular_assinatura(_base()) == calcular_assinatura(_base())
    # 64 hex — o tamanho de `CHAR(64)` na coluna.
    assert len(calcular_assinatura(_base())) == 64


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("co_jogo", "pontinhos"),
        ("co_motor", "tflite"),
        ("co_motivo", "simbolo_ausente"),
        ("co_plataforma", "ios"),
        ("co_versao_so", "Android 14 (SDK 34)"),
        ("no_modelo_aparelho", "samsung SM-A065M"),
        ("co_abi", "armeabi-v7a"),
        ("co_versao_app", "1.2.0+9"),
        ("co_versao_motor", "dart_1.4.0"),
        ("co_versao_binario_encontrada", "0.2.0"),
        ("co_flavor", "des"),
        ("co_modo_build", "debug"),
    ],
)
def test_cada_campo_da_configuracao_muda_a_assinatura(campo, valor):
    """Doze campos, doze testes. Um campo que deixasse de contar juntaria duas
    configurações diferentes numa linha só, e a segunda sumiria — silenciosa."""
    outro = {**_base(), campo: valor}
    assert calcular_assinatura(_base()) != calcular_assinatura(outro)


def test_o_USUARIO_nao_muda_a_assinatura():
    """⚠️ A tabela conta **configurações quebradas**, não pessoas. Dois irmãos
    com o mesmo celular têm o mesmo problema uma vez, não duas."""
    com_dono = {**_base(), "id_usuario": "11111111-1111-1111-1111-111111111111"}
    assert calcular_assinatura(_base()) == calcular_assinatura(com_dono)


def test_o_DETALHE_nao_muda_a_assinatura():
    """⚠️ O texto cru carrega a mensagem do sistema, que varia entre execuções
    (endereços, caminhos temporários). Incluí-lo faria a garantia sumir sem que
    nada denunciasse — o único sintoma seria a tabela crescer."""
    a = {**_base(), "de_motivo": "dlopen falhou em 0x7f2a"}
    b = {**_base(), "de_motivo": "dlopen falhou em 0x91cc"}
    assert calcular_assinatura(a) == calcular_assinatura(b)


def test_a_versao_ESPERADA_do_binario_nao_muda_a_assinatura():
    """Ela é derivada da versão do app (que já está na assinatura): o mesmo
    código Dart sempre exige o mesmo mínimo. Incluí-la não acrescentaria
    distinção nenhuma, só ruído."""
    outro = {**_base(), "co_versao_binario_esperada": "9.9.9"}
    assert calcular_assinatura(_base()) == calcular_assinatura(outro)


def test_nulo_nao_se_confunde_com_texto_vazio():
    """`None` e `''` são coisas diferentes: "não houve a quem perguntar" e "o
    binário devolveu vazio". A primeira é o caso normal; a segunda é defeito."""
    com_nulo = {**_base(), "co_versao_binario_encontrada": None}
    com_vazio = {**_base(), "co_versao_binario_encontrada": ""}
    assert calcular_assinatura(com_nulo) != calcular_assinatura(com_vazio)


def test_o_separador_impede_colisao_por_deslocamento():
    """⚠️ Sem um separador explícito, `('ab','c')` e `('a','bc')` dariam o mesmo
    hash — e duas configurações diferentes cairiam na mesma linha, com a segunda
    desaparecendo para sempre."""
    a = {**_base(), "co_jogo": "ab", "co_motor": "c"}
    b = {**_base(), "co_jogo": "a", "co_motor": "bc"}
    assert calcular_assinatura(a) != calcular_assinatura(b)
