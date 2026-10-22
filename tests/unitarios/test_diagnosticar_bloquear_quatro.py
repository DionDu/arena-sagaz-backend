"""T124c (spec 010), passo 4 - as partes do `scripts/diagnosticar_bloquear_quatro.py`
que podem errar caladas.

O diagnóstico conta, partida a partida, as ameaças que o adversário criou e as
que quem resolve tapou. O que aqui se protege é o que nenhuma execução
denunciaria:

  * **a contagem de cada partida**: contar o lance do ADVERSÁRIO como bloqueio,
    ou chamar de "ignorada" a ameaça que perdeu a vez para uma vitória, mudaria
    a explicação da escada plana sem erro nenhum;
  * **os controles**: se eles não reprovassem um instrumento errado, o "N de N"
    do relatório seria enfeite;
  * **os denominadores do resumo**: "bloqueou menos de 3 SEM perder" é a falha
    da hipótese, e ela não pode engolir quem perdeu;
  * **a visão da régua**: o par "mascote contra ele mesmo" fica de fora dela,
    como na régua de verdade;
  * **a identidade de cada dia no diário**: é ela que faz a medição retomar.

Nenhum caso abre o motor Dart: o árbitro do Quatro é Python puro.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` para a raiz do backend,
# onde mora a pasta `scripts/` (que não é pacote instalado).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from motores.quatro.motor_quatro import MotorQuatro, ler_sequencia  # noqa: E402
from scripts import diagnosticar_bloquear_quatro as script  # noqa: E402

MOTOR = MotorQuatro("tradicional")


def _analisar(fita: str, iniciais: str = "") -> dict:
    """A análise de uma partida escrita como `"s7s1..."`."""
    return script.analisar_partida(
        MOTOR, ler_sequencia(iniciais) if iniciais else (), ler_sequencia(fita)
    )


# ── A contagem de uma partida ───────────────────────────────────────────────


def test_os_controles_montados_a_mao_contam_certo() -> None:
    assert script.conferir_controles(MOTOR) == []


def test_o_controle_REPROVA_uma_expectativa_errada(monkeypatch) -> None:
    """Sem isto, um `conferir_controles` que sempre devolve vazio passaria."""
    sequencia, esperado = script.CONTROLES["bloqueio"]
    monkeypatch.setitem(
        script.CONTROLES, "bloqueio", (sequencia, {**esperado, "bloqueios": 2})
    )
    falhas = script.conferir_controles(MOTOR)
    assert falhas == ["bloqueio: bloqueios = 1, esperado 2"]


def test_o_lance_do_ADVERSARIO_que_tapa_nao_conta_para_quem_resolve() -> None:
    """O jogador 1 (quem resolve) faz três na coluna 7; o 2 tapa. Nenhum bloqueio
    é DELE, e não havia ameaça do adversário na vez dele."""
    partida = _analisar("s7s1s7s2s7s7")
    assert partida["bloqueios"] == 0
    assert partida["turnos_com_ameaca"] == 0
    assert partida["bloqueios_do_medidor"] == 0


def test_quem_resolve_sai_da_posicao_publicada_e_nao_do_tabuleiro_vazio() -> None:
    """Com um lance publicado, quem resolve é o jogador 2: é o 1 quem ameaça, e o
    lance do 2 na coluna 1 é o bloqueio."""
    partida = _analisar("s7s1s7s1s6s1s1", iniciais="s4")
    assert partida["turnos_com_ameaca"] == 1
    assert partida["bloqueios"] == 1


def test_a_ameaca_ignorada_que_PERDE_a_partida() -> None:
    """O 1 não tapa, e o 2 fecha a coluna: ignorada, e o resultado é perdeu."""
    partida = _analisar(script._TRES_NA_COLUNA_1 + "s2s1")
    assert partida["ignoradas"] == 1
    assert partida["resultado"] == "perdeu"
    assert partida["meios_lances"] == 8


def test_vencer_no_lugar_de_tapar_nao_e_ignorar() -> None:
    partida = _analisar(script.CONTROLES["venceu_no_lugar"][0])
    assert partida["venceu_no_lugar"] == 1
    assert partida["ignoradas"] == 0
    assert partida["resultado"] == "venceu"


def test_a_ameaca_dupla_conta_um_turno_so() -> None:
    """Duas casas no mesmo turno: UM turno com ameaça, e ele é duplo."""
    partida = _analisar(script.CONTROLES["dupla"][0])
    assert (partida["turnos_com_ameaca"], partida["turnos_com_dupla"]) == (1, 1)


def test_a_partida_sem_fim_fica_em_aberto() -> None:
    assert _analisar("s4s4")["resultado"] == "em_aberto"


# ── A conta do desafio, refeita para o controle ─────────────────────────────


def _partida(**campos) -> dict:
    """Uma partida analisada de mentira, com o que o caso não diz zerado."""
    base = {
        "turnos_com_ameaca": 0,
        "turnos_com_dupla": 0,
        "bloqueios": 0,
        "ignoradas": 0,
        "venceu_no_lugar": 0,
        "meios_lances": 10,
        "resultado": "venceu",
        "cumpriu": False,
        "resolve": "tex",
        "adversario": "pita",
        "bloqueios_do_medidor": 0,
    }
    base.update(campos)
    if "bloqueios_do_medidor" not in campos:
        base["bloqueios_do_medidor"] = base["bloqueios"]
    return base


def test_cumpriria_pede_o_numero_do_editorial_e_nao_perder() -> None:
    assert script.AMEACAS == 3
    assert script.cumpriria(_partida(bloqueios=3, resultado="empatou"))
    assert not script.cumpriria(_partida(bloqueios=3, resultado="perdeu"))
    assert not script.cumpriria(_partida(bloqueios=2, resultado="venceu"))
    # "E não perca" pede o fim: em aberto não cumpre.
    assert not script.cumpriria(_partida(bloqueios=5, resultado="em_aberto"))


# ── O resumo ────────────────────────────────────────────────────────────────


def test_poucas_e_so_de_quem_NAO_perdeu() -> None:
    resumo = script.resumir(
        [
            _partida(bloqueios=1, resultado="perdeu"),
            _partida(bloqueios=1, resultado="venceu"),
            _partida(bloqueios=2, resultado="empatou"),
            _partida(bloqueios=3, resultado="venceu", cumpriu=True),
        ]
    )
    assert resumo["n"] == 4
    assert resumo["poucas"] == 0.5
    assert resumo["perdeu"] == 0.25
    assert resumo["cumpriu"] == 0.25
    assert resumo["venceu"] == 0.5


def test_as_faixas_juntam_quatro_ou_mais_no_ultimo_balde() -> None:
    resumo = script.resumir(
        [_partida(bloqueios=b) for b in (0, 0, 2, 3, 4, 7)]
    )
    assert resumo["faixas"] == [2, 0, 1, 1, 2]
    assert resumo["bloqueios"] == 16 / 6


def test_grupo_vazio_nao_divide_por_zero() -> None:
    assert script.resumir([]) == {"n": 0}


# ── O relatório ─────────────────────────────────────────────────────────────


def _linha_do_diario(indice: int, partidas: list[dict]) -> dict:
    return {"indice": indice, "dia": f"d{indice}", "execucoes": 1, "partidas": partidas}


def test_a_visao_da_regua_deixa_de_fora_o_mascote_contra_ele_mesmo() -> None:
    linhas = [
        _linha_do_diario(
            0,
            [
                # Tex contra Tex: fora da visão da régua.
                _partida(resolve="tex", adversario="tex", resultado="perdeu"),
                _partida(resolve="tex", adversario="pita", resultado="venceu"),
            ],
        ),
        {"indice": 1, "dia": "d1", "sem_candidato": True},
    ]
    texto = script.relatorio(linhas)
    regua = texto.split("NA VISÃO DA RÉGUA")[1].split("ADVERSÁRIO DO DIA")[0]
    linha_do_tex = next(l for l in regua.splitlines() if l.strip().startswith("tex"))
    # Uma partida só (a contra a Pita): n = 1, cumpriu 0, perdeu 0. Com o
    # espelho dentro seriam n = 2 e perdeu 0,50.
    assert linha_do_tex.split()[1:4] == ["1", "0.00", "0.00"]
    assert "1 posições (1 dias sem candidato)" in texto
    assert "tex (=)" in texto


def test_os_controles_do_relatorio_acusam_a_partida_que_diverge() -> None:
    linhas = [
        _linha_do_diario(
            0,
            [
                _partida(bloqueios=3, bloqueios_do_medidor=2, resultado="venceu", cumpriu=False),
                _partida(bloqueios=0, resultado="venceu"),
            ],
        )
    ]
    texto = script.relatorio(linhas)
    assert "os do medidor do desafio: 1 de 2" in texto
    assert "'bloqueou 3 e não perdeu': 1 de 2" in texto


# ── A retomada ──────────────────────────────────────────────────────────────


def test_a_identidade_do_dia_e_o_indice() -> None:
    feitas = [{"indice": 0}, {"indice": 2, "sem_candidato": True}]
    # O dia sem candidato também já foi medido: não se tenta de novo.
    assert script.pendentes(feitas, 4) == [1, 3]
