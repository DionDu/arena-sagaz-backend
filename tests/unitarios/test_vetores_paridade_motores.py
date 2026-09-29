"""T094 - a bancada de paridade: a forma do arquivo, e de que motor ele saiu.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO CONFERE, E O QUE ELE ⛔ CONFERE
═══════════════════════════════════════════════════════════════════════════

Quem compara os lances e o **aplicativo**, em
`test/modulos/jogos/damas/paridade_da_bancada_test.dart`: e la que as partidas
sao jogadas de novo e cada meio-lance e comparado. Aqui e o lado do servidor, e
sao tres perguntas que so este lado sabe responder:

| nivel | o que confere | pode pular? |
|---|---|---|
| **CI** | a forma do arquivo daqui, e se ele saiu do motor que esta no espelho HOJE | ⛔ **nunca** |
| **local** | as duas copias byte a byte, por SHA-256 | sim, com motivo, quando o frontend nao esta no disco |

E o mesmo desenho de `test_vetores_verificacao.py`, e pela mesma razao: no CI
cada repositorio roda sozinho, e um teste que exigisse o impossivel seria
desligado na primeira semana.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CADEADO QUE MAIS IMPORTA AQUI: O ARQUIVO ENVELHECE
═══════════════════════════════════════════════════════════════════════════

As partidas foram jogadas por **um** motor, num dia. Mexer no motor sem regerar
o arquivo deixaria a bancada comparando o aplicativo de hoje com um adversario
que ⛔ existe mais - e ela passaria, porque quem mudou foi o aplicativo **e** o
executavel, juntos.

Por isso o documento carrega o resumo SHA-256 dos fontes do motor, e este teste
o confere contra o espelho. Quando ele falhar, o conserto e regerar:

    .venv\\Scripts\\python -u scripts\\gerar_vetores_paridade_motores.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from job.semente import semente_do_lance  # noqa: E402
from motores.damas import jogador_dart  # noqa: E402
from motores.damas.contrato_damas import (  # noqa: E402
    modalidades_declaradas,
    parametros_do_nivel,
)
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402

COPIA_DAQUI = RAIZ / "contratos" / "vetores-paridade-motores.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-paridade-motores.json"
)

#: A versao do formato que este teste sabe conferir.
VERSAO = 1


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. ⛔ Ausencia e falha, nao motivo para pular."""
    assert COPIA_DAQUI.is_file(), (
        f"a bancada nao esta em {COPIA_DAQUI}. Gere-a com "
        "`.venv\\Scripts\\python scripts/gerar_vetores_paridade_motores.py`."
    )
    return json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Nivel LOCAL — as duas copias
# ═══════════════════════════════════════════════════════════════════════════


def test_as_duas_copias_sao_byte_identicas() -> None:
    """SHA-256 das duas copias. ⚠️ Pula com motivo se o frontend nao estiver aqui."""
    if not COPIA_DO_APP.is_file():
        pytest.skip(
            "o repositorio arena-sagaz-frontend nao esta no disco ao lado deste "
            "(esperado em CI). A conferencia de forma continua rodando."
        )

    daqui = COPIA_DAQUI.read_bytes()
    do_app = COPIA_DO_APP.read_bytes()
    assert hashlib.sha256(daqui).hexdigest() == hashlib.sha256(do_app).hexdigest(), (
        "as duas copias da bancada divergiram.\n"
        f"  {COPIA_DAQUI}: {len(daqui)} bytes\n"
        f"  {COPIA_DO_APP}: {len(do_app)} bytes\n"
        "Conserto: rode `python scripts/gerar_vetores_paridade_motores.py`, que "
        "escreve as duas. ⛔ Nao edite uma delas a mao."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Nivel CI — de que motor este arquivo saiu
# ═══════════════════════════════════════════════════════════════════════════


def test_o_arquivo_saiu_do_motor_que_esta_no_espelho_HOJE(documento: dict) -> None:
    """O resumo gravado e o dos fontes do espelho, agora.

    ⚠️ **E o cadeado do envelhecimento**, e o unico teste desta suite que pode
    falhar sem ninguem ter tocado no arquivo: basta mexer no motor. Quando isso
    acontecer, as partidas gravadas descrevem um adversario que ⛔ existe mais, e
    o conserto e regerar - ⛔ afrouxar este teste.
    """
    assert documento["motor"]["damas"] == jogador_dart.resumo_dos_fontes(), (
        "a bancada foi gerada por um motor diferente do que esta no espelho.\n"
        f"  no arquivo: {documento['motor']['damas']}\n"
        f"  no espelho: {jogador_dart.resumo_dos_fontes()}\n"
        "Regere: `python scripts/gerar_vetores_paridade_motores.py`."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Nivel CI — a forma do arquivo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_versao_e_a_que_este_teste_confere(documento: dict) -> None:
    assert documento["versao"] == VERSAO


def test_os_identificadores_sao_unicos(documento: dict) -> None:
    ids = [p["id"] for p in documento["partidas"]]
    assert len(set(ids)) == len(ids), f"ha id repetido em {ids}"


def test_a_bancada_cobre_as_modalidades_e_os_quatro_niveis(documento: dict) -> None:
    """⛔ **Os niveis fracos entram**, e e o ponto da bancada.

    Os tres episodios de divergencia moraram nos niveis que erram de proposito
    ou so apareceram neles. Uma bancada que rodasse so o Sagaz repetiria o ponto
    cego que deixou o defeito da semente, de 26/09/2026, passar por baixo dos
    vetores de verificacao.
    """
    partidas = documento["partidas"]
    assert {p["co_nivel"] for p in partidas} == {n.value for n in NivelDeMotor}
    assert {p["co_modalidade"] for p in partidas} == set(modalidades_declaradas())


def test_os_argumentos_sao_os_do_CONTRATO(documento: dict) -> None:
    """O bloco `argumentos` de cada partida e o que o contrato declara hoje.

    ⚠️ **E a comparacao que acusa o defeito pelo NOME.** As travas de antes
    comparam SHA-256 de arquivo e provam que os dois lados rodam o mesmo codigo;
    os tres episodios foram o mesmo codigo com **argumentos** diferentes. Aqui
    se confere o lado do servidor; o lado do aparelho se confere no teste Dart,
    contra o `niveisPorIdentificador` dele.
    """
    for partida in documento["partidas"]:
        nivel = NivelDeMotor(partida["co_nivel"])
        p = parametros_do_nivel(nivel)
        argumentos = partida["argumentos"]
        assert argumentos["profundidade"] == p.profundidade, partida["id"]
        assert argumentos["ruido"] == p.ruido, partida["id"]
        assert argumentos["teto_de_nos"] == p.teto_de_nos, partida["id"]
        assert argumentos["extensao_de_captura"] == p.extensao_de_captura, (
            partida["id"]
        )
        assert argumentos["chance_de_errar"] == p.chance_de_errar, partida["id"]
        assert argumentos["margem_do_erro"] == p.margem_do_erro, partida["id"]


def test_o_relogio_NAO_esta_no_arquivo(documento: dict) -> None:
    """⛔ `tempo_maximo` nao entra, e a ausencia e a decisao de 25/09/2026.

    O servidor joga **sem relogio**: nao ha ninguem esperando na tela, e um ponto
    de parada que depende da carga da maquina faria o mesmo desafio dar lances
    diferentes em duas execucoes. Se um dia ele voltar ao arquivo, e porque
    alguem reintroduziu o primeiro dos tres episodios.
    """
    for partida in documento["partidas"]:
        assert "tempo_maximo" not in partida["argumentos"], partida["id"]


def test_a_semente_de_cada_lance_e_a_derivada_da_mestra(documento: dict) -> None:
    """Cada lance carrega `semente_do_lance(mestra, n)`, e os `n` vem em ordem.

    ⚠️ **E barato e pega o pior caso**: um arquivo cuja semente gravada nao fosse
    a derivada faria o teste do aplicativo comparar duas partidas diferentes e
    acusar o motor, que nao teria culpa nenhuma.
    """
    for partida in documento["partidas"]:
        mestra = partida["nu_semente"]
        lances = partida["lances"]
        assert lances, f"{partida['id']} nao tem lance nenhum"
        assert [lance["n"] for lance in lances] == list(
            range(1, len(lances) + 1)
        ), f"{partida['id']}: os numeros de lance nao sao 1, 2, 3..."
        for lance in lances:
            assert lance["semente"] == semente_do_lance(mestra, lance["n"]), (
                f"{partida['id']}, lance {lance['n']}"
            )


def test_nenhuma_partida_passou_do_teto_dela(documento: dict) -> None:
    """E quem parou no teto diz isso no desfecho, em vez de parecer terminada."""
    for partida in documento["partidas"]:
        teto = partida["maximo_de_meios_lances"]
        quantos = len(partida["lances"])
        assert quantos <= teto, f"{partida['id']}: {quantos} lances, teto {teto}"
        if quantos == teto:
            assert partida["co_desfecho"] == "teto_de_lances", partida["id"]
