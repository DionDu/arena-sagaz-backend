"""A bancada de paridade do Quatro em Linha (T111 da spec 010).

O arquivo `contratos/bancada-paridade-quatro.json` é GERADO pelo servidor
(`scripts/gerar_bancada_paridade_quatro.py`) e reproduzido lance a lance pelo
aplicativo (`test/modulos/jogos/quatro/paridade_com_servidor_quatro_test.dart`).
Aqui se confere o lado do servidor:

  1. as duas cópias são byte-idênticas;
  2. o arquivo saiu do motor e do contrato que estão no espelho HOJE (o
     cadeado do envelhecimento);
  3. a forma: todos os níveis do contrato, as três sementes do tabuleiro vazio
     e a partida da posição publicada em cada nível;
  4. a semente de cada lance é a derivada da mestra por `job/semente.py`, com
     `n` contado a partir da posição publicada;
  5. as partidas são jogáveis pelo árbitro e terminam no desfecho gravado;
  6. o executável de hoje refaz as partidas da posição publicada (quando ele
     está compilado nesta máquina).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from job import semente as semente_mod
from motores.quatro import contrato_quatro
from motores.quatro import jogador_dart_quatro as jdq
from motores.quatro.motor_quatro import MotorQuatro, estado_inicial

RAIZ = Path(__file__).resolve().parents[2]
COPIA_DAQUI = RAIZ / "contratos" / "bancada-paridade-quatro.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "contracts"
    / "bancada-paridade-quatro.json"
)

#: A versão do formato que este teste sabe conferir.
VERSAO = 1


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. Ausência é falha, e não motivo para pular."""
    assert COPIA_DAQUI.is_file(), (
        f"a bancada não está em {COPIA_DAQUI}. Gere-a com "
        "`.venv\\Scripts\\python scripts\\gerar_bancada_paridade_quatro.py`."
    )
    return json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))


def test_as_duas_copias_sao_byte_identicas() -> None:
    """SHA-256 das duas cópias. Pula com motivo se o app não estiver ao lado."""
    if not COPIA_DO_APP.is_file():
        pytest.skip("o repositório arena-sagaz-frontend não está ao lado deste.")
    daqui = hashlib.sha256(COPIA_DAQUI.read_bytes()).hexdigest()
    do_app = hashlib.sha256(COPIA_DO_APP.read_bytes()).hexdigest()
    assert daqui == do_app, (
        "as duas cópias da bancada do Quatro divergiram. Rode "
        "`python scripts/gerar_bancada_paridade_quatro.py`, que escreve as duas; "
        "não edite uma delas à mão."
    )


def test_o_arquivo_saiu_do_motor_e_do_contrato_do_espelho_HOJE(documento: dict) -> None:
    """O cadeado do envelhecimento: mexeu no motor ou no contrato, regere.

    ⚠️ É o único caso desta suíte que falha sem ninguém tocar no arquivo. O
    conserto é regerar, e não afrouxar este teste.
    """
    assert documento["motor"]["quatro"] == jdq.resumo_dos_fontes(), (
        "a bancada saiu de outro motor. Regere: "
        "`python scripts/gerar_bancada_paridade_quatro.py`."
    )
    assert documento["motor"]["contrato"] == contrato_quatro.sha256_do_contrato(), (
        "a bancada saiu de outro contrato. Regere: "
        "`python scripts/gerar_bancada_paridade_quatro.py`."
    )


def test_a_versao_e_os_identificadores(documento: dict) -> None:
    assert documento["versao"] == VERSAO
    ids = [p["id"] for p in documento["partidas"]]
    assert len(ids) == len(set(ids)), "há identificador de partida repetido"


def test_cobre_todo_nivel_de_toda_modalidade_e_a_posicao_publicada(documento: dict) -> None:
    """Todos os níveis que o contrato oferece, cada um com três partidas do
    tabuleiro vazio e uma da posição publicada.

    ⚠️ A posição publicada é a que pega o deslocamento da semente (o defeito
    do desafio do Pontinhos): com zero lances publicados, a conta errada e a
    certa coincidem.
    """
    partidas = documento["partidas"]
    for co_modalidade in contrato_quatro.modalidades_declaradas():
        for personagem in contrato_quatro.niveis_disponiveis(co_modalidade):
            do_nivel = [
                p
                for p in partidas
                if p["co_modalidade"] == co_modalidade
                and p["argumentos"]["personagem"] == personagem
            ]
            vazio = [p for p in do_nivel if p["lances_iniciais"] == ""]
            publicada = [p for p in do_nivel if p["lances_iniciais"] != ""]
            assert len({p["nu_semente"] for p in vazio}) == 3, (co_modalidade, personagem)
            assert publicada, f"{co_modalidade}/{personagem} sem posição publicada"
            # Seis lances, e não um: um deslocamento de 1 pode coincidir por acaso.
            for p in publicada:
                assert len(MotorQuatro(co_modalidade).estado_de_sequencia(
                    p["lances_iniciais"]
                ).lances) >= 6


def test_os_argumentos_sao_os_do_contrato(documento: dict) -> None:
    """O que o servidor manda é o que o contrato diz para aquele nível."""
    for partida in documento["partidas"]:
        nivel = next(
            n
            for n, personagem in contrato_quatro.PERSONAGEM_DO_NIVEL.items()
            if personagem == partida["argumentos"]["personagem"]
        )
        assert nivel.value == partida["co_nivel"], partida["id"]
        esperado = contrato_quatro.parametros_do_personagem(
            partida["co_modalidade"], nivel
        ).para_pedido()
        gravado = {k: v for k, v in partida["argumentos"].items() if k != "personagem"}
        assert gravado == esperado, partida["id"]


def test_a_semente_de_cada_lance_e_a_derivada_da_mestra(documento: dict) -> None:
    """`n` começa em 1 DEPOIS da posição publicada, e é contínuo."""
    for partida in documento["partidas"]:
        for indice, lance in enumerate(partida["lances"], start=1):
            assert lance["n"] == indice, partida["id"]
            assert lance["semente"] == semente_mod.semente_do_lance(
                partida["nu_semente"], indice
            ), f"{partida['id']}, lance {indice}"


def test_as_partidas_sao_jogaveis_e_terminam_no_desfecho_gravado(documento: dict) -> None:
    """O árbitro aceita cada lance e chega ao desfecho e à sequência gravados."""
    for partida in documento["partidas"]:
        arbitro = MotorQuatro(partida["co_modalidade"])
        estado = (
            arbitro.estado_de_sequencia(partida["lances_iniciais"])
            if partida["lances_iniciais"]
            else estado_inicial(partida["co_modalidade"])
        )
        for lance in partida["lances"]:
            assert not arbitro.veredito(estado).acabou, partida["id"]
            assert lance["lance"] in arbitro.lances_legais(estado), partida["id"]
            estado = arbitro.aplicar(estado, lance["lance"])
        veredito = arbitro.veredito(estado)
        assert veredito.acabou, f"{partida['id']} parou antes do fim"
        assert (veredito.co_motivo, veredito.vencedor) == (
            partida["co_desfecho"],
            partida["vencedor"],
        ), partida["id"]
        assert estado.sequencia == partida["co_lances_finais"], partida["id"]


def test_o_executavel_de_hoje_refaz_a_posicao_publicada(documento: dict) -> None:
    """As partidas da posição publicada, refeitas pelo executável desta máquina.

    São as que importam para o desafio, e custam poucos segundos. Pula com
    motivo quando o executável não está compilado (a imagem do job o compila
    no build, e o portão de lá confere outra referência: o aparelho).
    """
    try:
        jdq.caminho_do_executavel()
    except jdq.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do Quatro não está compilado: {erro}")

    from motores.nucleo.papeis import NivelDeMotor

    with jdq.JogadorDartQuatro() as motor:
        for partida in documento["partidas"]:
            if not partida["lances_iniciais"]:
                continue
            sequencia = partida["lances_iniciais"]
            for lance in partida["lances"]:
                resposta = motor.decidir(
                    lances=sequencia,
                    co_modalidade=partida["co_modalidade"],
                    nivel=NivelDeMotor(partida["co_nivel"]),
                    semente=lance["semente"],
                )
                obtido = (
                    resposta["lance"],
                    resposta["acao"],
                    resposta["nosVisitados"],
                    resposta["profundidadeAtingida"],
                    resposta["motivoParada"],
                )
                queria = (
                    lance["lance"],
                    lance["acao"],
                    lance["nos"],
                    lance["profundidade"],
                    lance["motivo"],
                )
                assert obtido == queria, f"{partida['id']}, lance {lance['n']}"
                sequencia += lance["lance"]
