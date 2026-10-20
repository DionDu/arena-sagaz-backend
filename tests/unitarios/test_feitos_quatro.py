"""Os feitos e o predicado do Quatro em Linha, e o juiz que os usa (T112).

O que se confere:
  - as medidas do fim e as peças encostadas batem com os vetores da T106 (o
    motor Dart é a fonte), dos dois lados da partida, com as medidas do fim
    valendo só para quem venceu;
  - as medidas da fita e o predicado batem com as fitas dos vetores, e o
    predicado não tem resposta antes do fim;
  - as casas de ameaça batem com as `ameacas` da família `regras`;
  - o juiz julga o Quatro: "não perca" só vale no FIM (quem abandona não
    cumpre), "vença em N" para no lance da vitória, e o desafio julgado do lado
    errado é dado inválido.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from motores.juiz import JogoDesconhecido, julgar_desafio
from motores.nucleo.medidor_por_fita import CUMPRIU, DADO_INVALIDO, NAO_CUMPRIU
from motores.quatro import contrato_quatro as cq
from motores.quatro import feitos_quatro as fq
from motores.quatro.motor_quatro import MotorQuatro, ler_sequencia

RAIZ = Path(__file__).resolve().parents[2]
VETORES = json.loads(
    (RAIZ / "contratos" / "vetores-paridade-quatro.json").read_text(encoding="utf-8")
)
MODALIDADES = set(cq.modalidades_declaradas())
MODALIDADE = cq.modalidades_declaradas()[0]


@pytest.fixture(scope="module")
def motores() -> dict[str, MotorQuatro]:
    return {m: MotorQuatro(m) for m in MODALIDADES}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Contra os vetores do motor Dart
# ═══════════════════════════════════════════════════════════════════════════


def test_os_vetores_tem_o_que_conferir() -> None:
    """Controle: as três famílias chegam com conteúdo, e com casos que importam."""
    medidas = [v for v in VETORES["medidas"] if v["modalidade"] in MODALIDADES]
    fitas = [v for v in VETORES["fitas"] if v["modalidade"] in MODALIDADES]
    assert len(medidas) >= 50 and len(fitas) >= 150
    assert any(v["vitoria_diagonal"] for v in medidas)
    assert any(v["linhas_no_lance_final"] >= 2 for v in medidas)
    assert any(v["maior_linha"] >= 5 for v in medidas)
    assert any(v["vencedor"] is None for v in medidas), "nenhum empate"
    assert any(v["ameacas_bloqueadas"] > 0 for v in fitas)
    assert any(v["lances_na_coluna_central"] > 0 for v in fitas)
    assert any(v["quatro_perdeu"] for v in fitas)


def test_as_medidas_do_fim_batem_com_o_motor_dos_dois_lados(motores) -> None:
    """Para cada partida terminada, medida do ponto de vista do J1 e do J2.

    A pessoa é quem tem a vez na posição publicada: com zero lances iniciais é
    o J1, com um lance inicial é o J2. ⚠️ As medidas do fim são da PESSOA: só
    valem o do vetor quando ela venceu.
    """
    divergencias = []
    for v in VETORES["medidas"]:
        if v["modalidade"] not in MODALIDADES:
            continue
        motor = motores[v["modalidade"]]
        lances = ler_sequencia(v["lances"])
        for iniciais, pessoa in (((), 1), (lances[:1], -1)):
            obtido = fq.medir(motor, iniciais, lances[len(iniciais):], jogador=pessoa)
            venceu = v["vencedor"] == pessoa
            esperado = {
                "vitoria": 1 if venceu else 0,
                "empate": 1 if v["vencedor"] is None else 0,
                "pecas_encostadas": v["pecas_encostadas_j1" if pessoa == 1 else "pecas_encostadas_j2"],
                "pecas_encostadas_do_adversario": v["pecas_encostadas_j2" if pessoa == 1 else "pecas_encostadas_j1"],
                "vitoria_diagonal": int(v["vitoria_diagonal"]) if venceu else 0,
                "linhas_no_lance_final": v["linhas_no_lance_final"] if venceu else 0,
                "maior_linha": v["maior_linha"] if venceu else 0,
            }
            recorte = {k: obtido[k] for k in esperado}
            if recorte != esperado:
                divergencias.append(f"{v['lances']} pessoa {pessoa:+d}: {recorte} × {esperado}")
    assert not divergencias, "\n  ".join([f"{len(divergencias)} divergências:"] + divergencias[:5])


def test_as_medidas_da_fita_e_o_predicado_batem_com_o_motor(motores) -> None:
    divergencias = []
    for v in VETORES["fitas"]:
        if v["modalidade"] not in MODALIDADES:
            continue
        motor = motores[v["modalidade"]]
        iniciais = ler_sequencia(v["lances_iniciais"])
        fita = ler_sequencia(v["fita"])
        obtido = fq.medir(motor, iniciais, fita)
        esperado = {k: v[k] for k in ("lances_do_jogador", "lances_na_coluna_central", "ameacas_bloqueadas")}
        recorte = {k: obtido[k] for k in esperado}
        # O predicado: o do motor quando a partida terminou; sem resposta antes.
        terminou = motor.veredito(motor.estado_de_sequencia(v["lances_iniciais"] + v["fita"])).acabou
        resposta = fq.responder_predicados(motor, iniciais, fita)["quatro_perdeu"]
        predicado_ok = resposta == v["quatro_perdeu"] if terminou else resposta is None
        if recorte != esperado or not predicado_ok:
            divergencias.append(
                f"{v['lances_iniciais']}|{v['fita']}: {recorte} × {esperado}; "
                f"quatro_perdeu {resposta} × {v['quatro_perdeu']} (terminou: {terminou})"
            )
    assert not divergencias, "\n  ".join([f"{len(divergencias)} divergências:"] + divergencias[:5])


def test_as_casas_de_ameaca_batem_com_as_ameacas_do_motor(motores) -> None:
    """As casas de cada cor, contra o `do_j1`/`do_j2` da família `regras`."""
    divergencias = []
    conferidas = 0
    for v in VETORES["regras"]:
        if v["modalidade"] not in MODALIDADES:
            continue
        motor = motores[v["modalidade"]]
        tabuleiro = motor.tabuleiro(motor.estado_de_sequencia(v["lances"]))
        dimensoes = motor.regras.dimensoes
        for cor, campo in ((1, "do_j1"), (-1, "do_j2")):
            esperado = {tuple(a["casa"]) for a in v["ameacas"] if a[campo]}
            obtido = set(fq.casas_de_ameaca(dimensoes, tabuleiro, cor))
            conferidas += len(esperado)
            if obtido != esperado:
                divergencias.append(f"{v['lances']!r} cor {cor:+d}: {sorted(obtido)} × {sorted(esperado)}")
    assert conferidas > 100, "controle: quase nenhuma ameaça nos vetores"
    assert not divergencias, "\n  ".join([f"{len(divergencias)} divergências:"] + divergencias[:5])


# ═══════════════════════════════════════════════════════════════════════════
# 2. Casos montados à mão
# ═══════════════════════════════════════════════════════════════════════════


def test_bloquear_e_ocupar_a_casa_da_ameaca_e_nao_a_de_baixo(motores) -> None:
    """O J2 tem três na horizontal (colunas 1 a 3, linha 1); a casa da ameaça
    é (4, 1). O J1 ocupa (4, 1): conta. Ocupar uma casa ao lado não conta."""
    motor = motores[MODALIDADE]
    # J1: s7 s7 s6 ; J2: s1 s2 s3 → depois de 6 lances, vez do J1.
    iniciais = ler_sequencia("s7s1s7s2s6s3")
    assert fq.medir(motor, iniciais, ["s4"])["ameacas_bloqueadas"] == 1
    assert fq.medir(motor, iniciais, ["s5"])["ameacas_bloqueadas"] == 0


def test_a_linha_do_adversario_nao_e_feito_da_pessoa(motores) -> None:
    """O adversário vence com uma diagonal: a pessoa não ganha `vitoria_diagonal`."""
    motor = motores[MODALIDADE]
    perdida = next(
        v for v in VETORES["medidas"]
        if v["modalidade"] == MODALIDADE and v["vencedor"] == -1 and v["vitoria_diagonal"]
    )
    medidas = fq.medir(motor, (), ler_sequencia(perdida["lances"]), jogador=1)
    assert (medidas["vitoria"], medidas["vitoria_diagonal"], medidas["maior_linha"]) == (0, 0, 0)


def test_o_lance_depois_do_fim_e_recusado(motores) -> None:
    motor = motores[MODALIDADE]
    with pytest.raises(ValueError):
        fq.medir(motor, (), ler_sequencia("s1s2s1s2s1s2s1s3"))


# ═══════════════════════════════════════════════════════════════════════════
# 3. O juiz
# ═══════════════════════════════════════════════════════════════════════════


def _posicao(motor: MotorQuatro, lances: str) -> dict:
    return motor.para_dado(motor.estado_de_sequencia(lances))


def _fita(motor: MotorQuatro, iniciais: str, lances: list[str]) -> list[dict]:
    """A fita no vocabulário do log: `n`, `jogador` (absoluto) e `lance`."""
    vez = motor.vez_de(motor.estado_de_sequencia(iniciais))
    return [
        {"n": i, "jogador": vez if i % 2 == 1 else -vez, "lance": lance}
        for i, lance in enumerate(lances, start=1)
    ]


NAO_PERCA = {
    "versao": 1,
    "janela": {"tipo": "partida"},
    "clausulas": [
        {"tipo": "predicado", "chave": "quatro_perdeu", "comparador": "igual", "valor": False}
    ],
}


def _uma_fita(motores, condicao):
    """Uma fita dos vetores que termina como [condicao] pede."""
    motor = motores[MODALIDADE]
    for v in VETORES["fitas"]:
        if v["modalidade"] != MODALIDADE:
            continue
        final = motor.estado_de_sequencia(v["lances_iniciais"] + v["fita"])
        if condicao(motor.veredito(final), v["pessoa"]):
            return v
    pytest.fail("nenhuma fita dos vetores termina assim")


def test_nao_perca_so_vale_no_fim_da_partida(motores) -> None:
    """A pessoa venceu: cumpre no ÚLTIMO lance, e não no primeiro.

    ⚠️ É o caso que pega o predicado respondido como `False` no meio da
    partida: com ele, o juiz pararia no 1º lance da pessoa.
    """
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou and ver.vencedor == pessoa)
    fita = _fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"]))
    assert len(fita) >= 3
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=NAO_PERCA,
        fita=fita,
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.veredito == CUMPRIU
    assert julgamento.nu_lance_cumpre_desafio == len(fita)


def test_quem_abandona_nao_segurou_o_magno(motores) -> None:
    """A mesma fita, cortada no meio: a partida não terminou, e não cumpre."""
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou and ver.vencedor == pessoa)
    fita = _fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"]))[:2]
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=NAO_PERCA,
        fita=fita,
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.veredito == NAO_CUMPRIU


def test_quem_perdeu_nao_cumpre_o_nao_perca(motores) -> None:
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou and ver.vencedor == -pessoa)
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=NAO_PERCA,
        fita=_fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"])),
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.veredito == NAO_CUMPRIU
    assert julgamento.feitos["vitoria"] == 0


def test_venca_em_n_para_no_lance_da_vitoria(motores) -> None:
    """`vitoria` ∧ `lances_do_jogador ≤ N`, com N = os lances que ela usou."""
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou and ver.vencedor == pessoa)
    fita = _fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"]))

    def chegada(n: int) -> dict:
        return {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {"tipo": "medida", "chave": "vitoria", "comparador": "igual", "valor": 1},
                {"tipo": "medida", "chave": "lances_do_jogador", "comparador": "menor_ou_igual", "valor": n},
            ],
        }

    args = dict(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        fita=fita,
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    usados = v["lances_do_jogador"]
    assert julgar_desafio(js_chegada=chegada(usados), **args).veredito == CUMPRIU
    # Um a menos que o que ela usou: não cumpre.
    assert julgar_desafio(js_chegada=chegada(usados - 1), **args).veredito == NAO_CUMPRIU


def test_o_desafio_julgado_do_lado_errado_e_dado_invalido(motores) -> None:
    """O juiz recebe o jogador que não tem a vez na posição publicada."""
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou)
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=NAO_PERCA,
        fita=_fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"])),
        jogador=-v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.veredito == DADO_INVALIDO


def test_a_posicao_de_outro_jogo_e_recusada(motores) -> None:
    """A posição das damas (FEN) chegando ao Quatro estoura, e não vira partida."""
    with pytest.raises(ValueError):
        julgar_desafio(
            co_jogo="quatro",
            js_posicao_inicial={"co_formato_posicao": "fen", "fen": "W:W1:B2"},
            js_chegada=NAO_PERCA,
            fita=[],
            co_modalidade=MODALIDADE,
        )


def test_jogo_sem_medidor_continua_recusado() -> None:
    with pytest.raises(JogoDesconhecido):
        julgar_desafio(
            co_jogo="velha", js_posicao_inicial={}, js_chegada=NAO_PERCA, fita=[]
        )


def test_o_empate_fechado_pelo_adversario_cumpre_o_nao_perca(motores) -> None:
    """O adversário joga na última casa e a partida empata: quem resolve segurou.

    ⚠️ O `julgar` só avaliava os lances da pessoa, e o fim aqui cai num lance
    do adversário: sem a porta `terminou_ate`, "não perca" nunca seria avaliado
    no fim, e quem segurou o Magno até o empate não cumpriria (achado pela
    sonda, T113).
    """
    motor = motores[MODALIDADE]
    v = next(
        f
        for f in VETORES["fitas"]
        if f["modalidade"] == MODALIDADE
        and len(ler_sequencia(f["fita"])) % 2 == 0
        and motor.veredito(motor.estado_de_sequencia(f["lances_iniciais"] + f["fita"])).vencedor == 0
    )
    fita = _fita(motor, v["lances_iniciais"], ler_sequencia(v["fita"]))
    assert fita[-1]["jogador"] != v["pessoa"], "controle: o último lance é do adversário"
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=NAO_PERCA,
        fita=fita,
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.veredito == CUMPRIU
    assert julgamento.nu_lance_cumpre_desafio == len(fita)
    assert julgamento.feitos["empate"] == 1


def test_o_lance_do_adversario_no_meio_continua_sem_fechar_a_conta(motores) -> None:
    """A exceção é só para o lance que ENCERRA: no meio, nada muda.

    A medida `pecas_encostadas_do_adversario` cresce no lance DO ADVERSÁRIO.
    Uma chegada que passa a valer ali só cumpre no lance seguinte da pessoa,
    e não no do adversário.
    """
    motor = motores[MODALIDADE]
    v = _uma_fita(motores, lambda ver, pessoa: ver.acabou)
    iniciais = ler_sequencia(v["lances_iniciais"])
    lances = ler_sequencia(v["fita"])
    fita = _fita(motor, v["lances_iniciais"], lances)
    # O 1º lance do adversário (no meio da partida) que faz a medida crescer.
    anterior = fq.medir(motor, iniciais, [])["pecas_encostadas_do_adversario"]
    alvo = None
    for q in range(1, len(lances)):
        valor = fq.medir(motor, iniciais, lances[:q])["pecas_encostadas_do_adversario"]
        if fita[q - 1]["jogador"] != v["pessoa"] and valor > anterior:
            alvo = (q, valor)
            break
        anterior = max(anterior, valor)
    assert alvo is not None, "controle: a fita não tem o caso"
    q, valor = alvo
    chegada = {
        "versao": 1,
        "janela": {"tipo": "partida"},
        "clausulas": [
            {"tipo": "medida", "chave": "pecas_encostadas_do_adversario", "comparador": "maior_ou_igual", "valor": valor}
        ],
    }
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=_posicao(motor, v["lances_iniciais"]),
        js_chegada=chegada,
        fita=fita,
        jogador=v["pessoa"],
        co_modalidade=MODALIDADE,
    )
    assert julgamento.nu_lance_cumpre_desafio == q + 1
