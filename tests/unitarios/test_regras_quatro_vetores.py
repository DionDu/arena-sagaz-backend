"""O árbitro do Quatro em Linha confere os vetores de REGRAS (spec 010, T107).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE TESTE PROVA
═══════════════════════════════════════════════════════════════════════════

O árbitro (`motores/quatro/motor_quatro.py`) é a segunda escrita das regras; a
primeira é o motor Dart, que o aparelho e o executável do servidor rodam. Os
vetores (`contratos/vetores-paridade-quatro.json`) foram gerados pelo motor
(`ia/jogos/jogo_quatro/motor_dart/bin/gerar_vetores_paridade_quatro.dart`), e
este teste exige que o árbitro responda IGUAL em cada posição: os lances
legais, o desfecho e as linhas vencedoras, na mesma ordem.

Três níveis, como a bancada do Pontinhos:

| nível | o quê | pula? |
|---|---|---|
| CI | os vetores saíram do motor e do contrato que estão NO ESPELHO deste repositório (resumo e SHA-256 do contrato) | nunca |
| CI | o árbitro responde igual em todas as posições das modalidades do contrato | nunca |
| local | as duas cópias (backend e spec 010 do app) byte a byte, por SHA-256 | sim, com motivo, quando o frontend não está no disco |

⚠️ As posições da modalidade-SONDA (6 × 5, com o `tirar`) ficam para a T108,
que traz a classe de regras dela do lado Python. Aqui elas só são contadas, para
o teste falhar se sumirem do arquivo.
"""

import hashlib
import json
from pathlib import Path

import pytest

from motores.nucleo.processo_dart import resumo_dos_fontes
from motores.quatro import contrato_quatro as cq
from motores.quatro.motor_quatro import MotorQuatro, ler_sequencia

RAIZ = Path(__file__).resolve().parents[2]
COPIA_DAQUI = RAIZ / "contratos" / "vetores-paridade-quatro.json"
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "contracts"
    / "vetores-paridade-quatro.json"
)
FONTES_DO_MOTOR = cq.ESPELHO / "jogos" / "jogo_quatro" / "motor_dart" / "lib"

COMANDO_PARA_REGERAR = (
    "cd ia\\jogos\\jogo_quatro\\motor_dart; dart run "
    "bin/gerar_vetores_paridade_quatro.dart "
    "..\\..\\..\\..\\arena-sagaz-backend\\contratos\\vetores-paridade-quatro.json "
    "..\\..\\..\\..\\arena-sagaz-frontend\\specs\\010-jogo-quatro-em-linha\\"
    "contracts\\vetores-paridade-quatro.json"
)


def _vetores() -> dict:
    assert COPIA_DAQUI.is_file(), (
        f"os vetores não estão em {COPIA_DAQUI}. Gere-os com:\n  {COMANDO_PARA_REGERAR}"
    )
    return json.loads(COPIA_DAQUI.read_text(encoding="utf-8"))


VETORES = _vetores()
MODALIDADES = set(cq.modalidades_declaradas())
DAS_MODALIDADES = [v for v in VETORES["regras"] if v["modalidade"] in MODALIDADES]


def test_os_vetores_sairam_do_motor_e_do_contrato_do_espelho():
    """Sem isto, o árbitro poderia estar conferindo respostas de outro motor.

    ⚠️ O resumo é o dos fontes de `lib/` do ESPELHO: reespelhar um motor novo
    sem regerar os vetores reprova aqui, com o comando na mensagem.
    """
    assert VETORES["motor"]["quatro"] == resumo_dos_fontes(FONTES_DO_MOTOR), (
        "os vetores foram gerados por outro motor que o do espelho. Regere:\n"
        f"  {COMANDO_PARA_REGERAR}"
    )
    assert VETORES["contrato_sha256"] == cq.sha256_do_contrato(), (
        "os vetores foram gerados com outro contrato que o do espelho."
    )


def test_o_arquivo_traz_as_posicoes_das_modalidades_e_da_sonda():
    assert len(DAS_MODALIDADES) >= 1000
    # As da sonda são da T108; aqui só se exige que continuem no arquivo.
    assert any(v["modalidade"] not in MODALIDADES for v in VETORES["regras"])


@pytest.fixture(scope="module")
def motores() -> dict[str, MotorQuatro]:
    return {m: MotorQuatro(m) for m in MODALIDADES}


def test_o_arbitro_responde_igual_ao_motor_em_cada_posicao(motores):
    """Os legais, o desfecho e as linhas, posição a posição.

    ⚠️ Um laço só, e não um caso por posição: são mais de mil, e a mensagem
    junta as primeiras divergências, com a sequência para refazer à mão.
    """
    divergencias = []
    for v in DAS_MODALIDADES:
        motor = motores[v["modalidade"]]
        estado = motor.estado_de_sequencia(v["lances"])
        legais = motor.lances_legais(estado)
        desfecho = motor.desfecho(estado)
        obtido_desfecho = (
            None
            if desfecho is None
            else {
                "vencedor": desfecho.vencedor,
                "linhas": [[list(c) for c in linha] for linha in desfecho.linhas],
            }
        )
        if legais != v["legais"] or obtido_desfecho != v["desfecho"]:
            divergencias.append(
                f"{v['lances']!r}: legais {legais} × {v['legais']}; "
                f"desfecho {obtido_desfecho} × {v['desfecho']}"
            )
    assert not divergencias, (
        f"{len(divergencias)} posições divergem do motor Dart. As primeiras:\n  "
        + "\n  ".join(divergencias[:5])
    )


def test_o_veredito_segue_o_desfecho(motores):
    """O veredito é a outra face do desfecho: acabou, motivo e vencedor 0/±1."""
    for v in DAS_MODALIDADES:
        motor = motores[v["modalidade"]]
        veredito = motor.veredito(motor.estado_de_sequencia(v["lances"]))
        if v["desfecho"] is None:
            assert veredito.acabou is False, v["lances"]
        else:
            esperado = v["desfecho"]["vencedor"] or 0
            assert (veredito.acabou, veredito.vencedor) == (True, esperado), v["lances"]


def test_as_sequencias_dos_vetores_se_leem_lance_a_lance(motores):
    """`ler_sequencia` e a notação do Dart concordam (sem sobra nem falta)."""
    for v in DAS_MODALIDADES:
        assert "".join(ler_sequencia(v["lances"])) == v["lances"]


def test_as_duas_copias_sao_o_mesmo_arquivo():
    """SHA-256 das duas cópias. ⚠️ Pula com motivo se o frontend não estiver aqui."""
    if not COPIA_DO_APP.is_file():
        pytest.skip(
            "o repositório arena-sagaz-frontend não está no disco ao lado deste "
            "(nível local; no CI, os testes acima conferem o arquivo daqui)."
        )
    daqui = COPIA_DAQUI.read_bytes()
    do_app = COPIA_DO_APP.read_bytes()
    assert hashlib.sha256(daqui).hexdigest() == hashlib.sha256(do_app).hexdigest(), (
        "as duas cópias dos vetores divergem. Regere as duas de uma vez:\n"
        f"  {COMANDO_PARA_REGERAR}"
    )
