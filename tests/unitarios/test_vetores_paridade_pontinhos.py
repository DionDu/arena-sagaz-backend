"""T093 - a bancada de paridade do Pontinhos: a forma, e de que motor ela saiu.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO CONFERE, E O QUE ELE ⛔ CONFERE
═══════════════════════════════════════════════════════════════════════════

Quem compara os lances contra o **aplicativo** e
`test/modulos/jogos/pontinhos/paridade_da_bancada_pontinhos_test.dart`: e la que
as partidas sao jogadas de novo, com as mesmas sementes, e cada meio-lance e
comparado. Aqui e o lado do servidor, e sao as perguntas que so este lado sabe
responder:

| nivel | o que confere | pode pular? |
|---|---|---|
| **CI** | a forma do arquivo daqui, e se ele saiu do motor do espelho HOJE | ⛔ **nunca** |
| **local** | as duas copias byte a byte, por SHA-256 | sim, com motivo, quando o frontend nao esta no disco |

E o mesmo desenho de `test_vetores_paridade_motores.py` (a bancada das damas),
pela mesma razao: no CI cada repositorio roda sozinho, e um teste que exigisse o
impossivel seria desligado na primeira semana.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CADEADO QUE MAIS IMPORTA AQUI: O ARQUIVO ENVELHECE
═══════════════════════════════════════════════════════════════════════════

As partidas foram jogadas por **um** motor, num dia. Mexer no motor sem regerar o
arquivo deixaria a bancada comparando o aplicativo de hoje com um adversario que
⛔ existe mais - e ela passaria, porque quem mudou foi o aplicativo **e** o
executavel, juntos.

Por isso o documento carrega o resumo SHA-256 dos fontes do motor, e este teste o
confere contra o espelho. Quando ele falhar, o conserto e regerar:

    .venv\\Scripts\\python -u scripts\\gerar_vetores_paridade_pontinhos.py
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
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.pontinhos import jogador_dart_pontinhos  # noqa: E402
from motores.pontinhos.motor_pontinhos import MotorPontinhos, TAMANHO  # noqa: E402
from motores.pontinhos.politica import parametros_do_nivel  # noqa: E402

COPIA_DAQUI = RAIZ / "contratos" / "vetores-paridade-pontinhos.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-paridade-pontinhos.json"
)

#: A versao do formato que este teste sabe conferir.
VERSAO = 1

#: Quantos tracos o tabuleiro pequeno tem - e, portanto, quantos meios-lances
#: uma partida inteira tem. ⚠️ **E aritmetica, nao estimativa**: cada lance ocupa
#: um traco e nenhum lance os devolve.
TRACOS_DO_PEQUENO = 31


@pytest.fixture(scope="module")
def documento() -> dict:
    """O arquivo daqui. ⛔ Ausencia e falha, nao motivo para pular."""
    assert COPIA_DAQUI.is_file(), (
        f"a bancada nao esta em {COPIA_DAQUI}. Gere-a com "
        "`.venv\\Scripts\\python scripts/gerar_vetores_paridade_pontinhos.py`."
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
        "as duas copias da bancada do Pontinhos divergiram.\n"
        f"  {COPIA_DAQUI}: {len(daqui)} bytes\n"
        f"  {COPIA_DO_APP}: {len(do_app)} bytes\n"
        "Conserto: rode `python scripts/gerar_vetores_paridade_pontinhos.py`, "
        "que escreve as duas. ⛔ Nao edite uma delas a mao."
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
    esperado = jogador_dart_pontinhos.resumo_dos_fontes()
    assert documento["motor"]["pontinhos"] == esperado, (
        "a bancada foi gerada por um motor diferente do que esta no espelho.\n"
        f"  no arquivo: {documento['motor']['pontinhos']}\n"
        f"  no espelho: {esperado}\n"
        "Regere: `python scripts/gerar_vetores_paridade_pontinhos.py`."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Nivel CI — a forma do arquivo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_versao_e_a_que_este_teste_confere(documento: dict) -> None:
    assert documento["versao"] == VERSAO


def test_os_identificadores_sao_unicos(documento: dict) -> None:
    ids = [p["id"] for p in documento["partidas"]]
    assert len(set(ids)) == len(ids), f"ha id repetido em {ids}"


def test_a_bancada_cobre_os_quatro_niveis(documento: dict) -> None:
    """⛔ **Os niveis fracos entram**, e e o ponto da bancada.

    Os episodios de divergencia moraram nos niveis que erram de proposito ou so
    apareceram neles. Uma bancada que rodasse so o Sagaz repetiria o ponto cego.
    """
    partidas = documento["partidas"]
    assert {p["co_nivel"] for p in partidas} == {n.value for n in NivelDeMotor}
    assert {p["co_tamanho_tabuleiro"] for p in partidas} == {TAMANHO}


def test_cada_nivel_tem_as_TRES_sementes(documento: dict) -> None:
    """⚠️ Inclusive o Sagaz - e e a diferenca para a bancada de damas.

    Nas damas o Sagaz ⛔ consulta o sorteador, e as tres sementes dariam a mesma
    partida. Aqui ⛔: o Magno **sorteia a abertura** quando e ele quem abre, e
    tres sementes sao tres partidas diferentes.
    """
    por_nivel: dict[str, set[int]] = {}
    for partida in documento["partidas"]:
        por_nivel.setdefault(partida["co_nivel"], set()).add(partida["nu_semente"])
    for nivel, sementes in por_nivel.items():
        assert len(sementes) == 3, f"{nivel} tem {len(sementes)} semente(s), e nao 3"


def test_as_partidas_do_sagaz_sao_DIFERENTES_entre_si(documento: dict) -> None:
    """A prova de que as tres sementes do Magno valem a pena.

    ⛔ Se as tres dessem a mesma partida, guardar as tres so engordaria o arquivo
    e a suite - foi o que se mediu nas damas, e por isso la ele joga uma so.
    """
    do_sagaz = [p for p in documento["partidas"] if p["co_nivel"] == "sagaz"]
    sequencias = {tuple(p["sequencia_final"]) for p in do_sagaz}
    assert len(sequencias) == len(do_sagaz), (
        "duas partidas do Magno sairam identicas com sementes diferentes. Se a "
        "Fase 0 (a abertura sorteada) sumiu, este arquivo passou a guardar a "
        "mesma partida varias vezes."
    )


def test_os_argumentos_sao_os_do_CONTRATO(documento: dict) -> None:
    """O bloco `argumentos` de cada partida e o que o contrato declara hoje.

    ⚠️ **E a comparacao que acusa o defeito pelo NOME.** As travas de antes
    comparam SHA-256 de arquivo e provam que os dois lados rodam o mesmo codigo;
    aqui se confere o lado do servidor, e o lado do aparelho se confere no teste
    Dart, contra o enum `Dificuldade` do motor.
    """
    for partida in documento["partidas"]:
        nivel = NivelDeMotor(partida["co_nivel"])
        p = parametros_do_nivel(nivel)
        argumentos = partida["argumentos"]
        assert argumentos["chave"] == p.chave, partida["id"]
        assert argumentos["epsilon"] == p.epsilon, partida["id"]
        assert argumentos["usa_captura_gulosa"] == p.usa_captura_gulosa, partida["id"]
        assert argumentos["timer_segundos"] == p.timer_segundos, partida["id"]


def test_o_mapeamento_gravado_e_o_do_espelho(documento: dict) -> None:
    """Rotulo → indice, uma vez no documento, e igual ao que a rede usa.

    ⚠️ Um mapeamento diferente faria os dois lados lerem a **mesma** softmax como
    tracos diferentes - e a falha apareceria como "divergencia no lance 1",
    mandando procurar na politica, que nao teria culpa nenhuma.
    """
    assert documento["mapeamento"] == MotorPontinhos().mapeamento_de_rotulos


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


def test_toda_partida_enche_o_tabuleiro(documento: dict) -> None:
    """31 tracos, 31 meios-lances, e o desfecho e sempre `tabuleiro_cheio`.

    ⚠️ **E aritmetica, nao sorte**: cada lance ocupa um traco e nenhum lance os
    devolve. Uma partida mais curta aqui quer dizer que o motor parou de devolver
    lance antes da hora - e o arquivo estaria guardando meia partida.
    """
    for partida in documento["partidas"]:
        assert len(partida["lances"]) == TRACOS_DO_PEQUENO, partida["id"]
        assert partida["co_desfecho"] == "tabuleiro_cheio", partida["id"]
        placar = partida["placar_final"]
        assert placar["1"] + placar["-1"] == 12, (
            f"{partida['id']}: as 12 caixas do 4x3 nao foram todas fechadas "
            f"({placar})"
        )


def test_a_softmax_de_cada_lance_esta_inteira(documento: dict) -> None:
    """Os 31 numeros crus, em todo lance.

    ⛔ **Sem eles a bancada ⛔ existe do lado do aplicativo**: em `flutter test`
    nao ha TFLite, e e a softmax gravada que permite reproduzir a decisao sem
    inferir nada.
    """
    quantos_rotulos = len(documento["mapeamento"])
    for partida in documento["partidas"]:
        for lance in partida["lances"]:
            softmax = lance["softmax"]
            assert len(softmax) == quantos_rotulos, (
                f"{partida['id']}, lance {lance['n']}: a softmax tem "
                f"{len(softmax)} numeros e o mapeamento tem {quantos_rotulos}"
            )
            assert all(isinstance(v, float) for v in softmax), partida["id"]


def test_todo_lance_traz_o_codigo_de_acao(documento: dict) -> None:
    """⚠️ O `co_acao` e metade da comparacao, e nao um enfeite de log.

    Dois lados podem escolher o mesmo traco por caminhos diferentes - um pela
    captura gulosa, outro pelo argmax. Comparar so o lance deixaria passar uma
    politica que mudou de fase sem mudar de resultado naquele lance.
    """
    for partida in documento["partidas"]:
        for lance in partida["lances"]:
            assert lance["co_acao"], f"{partida['id']}, lance {lance['n']}"
            assert lance["vez_de"] in (1, -1), partida["id"]
