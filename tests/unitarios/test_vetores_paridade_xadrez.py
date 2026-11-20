"""Os vetores de paridade do xadrez, na 3ª ponta: o executável do servidor (T064).

Cada vetor é um pedido de `buscar` e a resposta que o motor deu no laboratório
(o lance, a `acao` e os nós). Aqui o MESMO pedido atravessa o executável que
escolhe os lances do gabarito e da régua (`motores/xadrez/jogador_xadrez.py`),
pelo código de `motores/xadrez/paridade_xadrez.py`, o mesmo que o portão do build
(`scripts/conferir_motor_xadrez.py`) usa dentro da imagem.

| o que confere | pode pular? |
|---|---|
| a forma do arquivo daqui e de que motor e contrato ele saiu | nunca |
| as três cópias (servidor, laboratório, app) byte a byte | sim, com motivo, quando o outro repositório não está no disco |
| cada vetor pelo executável | sim, com motivo, quando o executável não está compilado; **no build da imagem, nunca** (o portão 3e do `Dockerfile.job`) |

⚠️ Falhou? Leia a mensagem antes de mexer. Os vetores só se regeram quando o
motor muda de comportamento DE PROPÓSITO (sobe a versão do `Cargo.toml`), e aí
na mesma resposta: a fonte, a cópia do app, esta cópia e os binários.
"""

from __future__ import annotations

import copy

import pytest

from motores.xadrez import jogador_xadrez as jx
from motores.xadrez import paridade_xadrez as px


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. Ausência é falha, e não motivo para pular."""
    assert px.CAMINHO_DOS_VETORES.is_file(), (
        f"os vetores não estão em {px.CAMINHO_DOS_VETORES}. Copie-os de "
        f"{px.FONTE_NO_LABORATORIO}."
    )
    return px.ler_vetores()


@pytest.fixture(scope="module")
def motor():
    """O executável, ou o pulo com a receita (fora da imagem, ele é local)."""
    try:
        jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")
    with jx.JogadorXadrez() as aberto:
        yield aberto


# ── A forma e a origem (nunca pula) ─────────────────────────────────────────


def test_os_vetores_sao_do_motor_e_do_contrato_do_espelho(documento):
    assert px.problemas_do_cabecalho(documento) == []


def test_o_cabecalho_acusa_versao_errada_e_arquivo_truncado(documento):
    """O controle: sem ele, um `problemas_do_cabecalho` que sempre devolvesse
    lista vazia deixaria o caso de cima verde e cego."""
    for campo, valor in (("versao_do_motor", "0.0.0"), ("versao_do_contrato", "0.0.0")):
        mexido = {**documento, campo: valor}
        assert any(campo.split("_")[-1] in p for p in px.problemas_do_cabecalho(mexido)), campo
    truncado = {**documento, "vetores": documento["vetores"][:10], "quantos": 10}
    assert px.problemas_do_cabecalho(truncado)


def test_cada_vetor_nomeia_um_personagem_do_contrato(documento):
    # O `NIVEL_DO_PERSONAGEM` levantaria `KeyError` no meio da conferência; aqui
    # a falha diz qual nome veio.
    nomes = {v["nivel"] for v in documento["vetores"]}
    assert nomes <= set(px.NIVEL_DO_PERSONAGEM), nomes - set(px.NIVEL_DO_PERSONAGEM)


# ── As três cópias (pula com motivo, sem o repositório ao lado) ─────────────


@pytest.mark.parametrize(
    "outra", [px.FONTE_NO_LABORATORIO, px.COPIA_DO_APP], ids=["laboratorio", "app"]
)
def test_a_copia_do_servidor_e_byte_identica(outra):
    if not outra.is_file():
        pytest.skip(f"a outra cópia não está no disco ao lado deste repositório: {outra}")
    assert px.sha256_do_arquivo(px.CAMINHO_DOS_VETORES) == px.sha256_do_arquivo(outra), (
        "os vetores DIVERGIRAM entre o servidor e "
        f"{outra}. A fonte é o laboratório: copie de lá na mesma resposta em que "
        "ela foi regerada."
    )


# ── Pelo executável ─────────────────────────────────────────────────────────


def test_cada_vetor_pelo_executavel_da_o_mesmo_lance_acao_e_nos(motor, documento):
    falhas = px.conferir_todos(motor, documento)
    # Todas de uma vez (até 10 na mensagem): um motor que mudou costuma mudar
    # muitos vetores, e o padrão ajuda a achar a causa.
    assert falhas == [], (
        f"{len(falhas)} de {len(documento['vetores'])} vetores divergiram; os "
        "primeiros:\n" + "\n".join(falhas[:10])
    )


def test_a_conferencia_acusa_um_vetor_mexido(motor, documento):
    """O controle: um vetor com o lance, a `acao`, os nós ou a semente mexidos
    é acusado. Um vetor de busca de verdade (com nós), e não um mate em um."""
    original = next(v for v in documento["vetores"] if v["acao"] == "erro_sorteado")
    assert px.conferir_vetor(motor, original) is None
    for campo, valor in (
        ("lance", "a1a1"),
        ("acao", "busca_melhor"),
        ("nos", 1),
        ("semente", original["semente"] + 1),
    ):
        mexido = copy.deepcopy(original)
        mexido[campo] = valor
        assert px.conferir_vetor(motor, mexido) is not None, campo
