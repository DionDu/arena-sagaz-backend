"""T027 - EMITE OS VETORES DE VERIFICACAO DO DESAFIO (RF-DES-198).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

A regra que decide se alguem cumpriu um desafio esta escrita **duas vezes**: em
Dart, no aplicativo (RF-DES-030), e em Python, no servidor (RF-DES-035). ⛔ Nao da
para ter uma implementacao so — o aplicativo julga sem rede, e o servidor
reconfere.

Da para ter **um teste so**, rodando dos dois lados sobre os mesmos dados. E isso
que este arquivo produz.

⚠️ **A licao e do proprio projeto**: a paridade do motor das damas e comparada em
2.000 posicoes, e a copia do contrato da CNN e conferida por SHA-256 que falha o
merge. Aqui e a mesma disciplina, aplicada a regra que decide quem ganha XP.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE OS VETORES PROVAM, E O QUE NAO PROVAM
═══════════════════════════════════════════════════════════════════════════

Os `esperado` NAO sao digitados a mao: eles saem do **motor**, que e a fonte da
verdade das regras de cada jogo (copia byte-identica do laboratorio). O que se
digita a mao e a **posicao** e a **fita** — e as duas foram escolhidas pequenas
justamente para poderem ser conferidas de cabeca.

Consequencia honesta, e ela esta escrita tambem no `.md` do contrato:

  ✅ **provam** que o Dart e o Python concordam nos casos escritos, e que o
     julgamento do Python nao muda sem alguem perceber;
  ⛔ **nao provam** que as duas implementacoes sao a mesma coisa. Por isso a
     regra 1 do contrato exige o caso *"nao cumpre por pouco"*: e onde duas
     implementacoes de fronteira de janela costumam divergir de verdade.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\gerar_vetores_verificacao.py

Ele escreve as **duas** copias, byte-identicas:

    arena-sagaz-backend/contratos/vetores-verificacao-desafio.json
    arena-sagaz-frontend/specs/009-desafio-do-dia/contracts/vetores-verificacao-desafio.json

⚠️ **Vetor nunca e apagado nem editado** (regra 4 do contrato). Corrigir um vetor
errado e **vetor novo**; o antigo, se descrevia algo impossivel, e marcado
`"obsoleto": true` com o motivo. Mesma regra das chaves de feito: o passado
gravado nao se reescreve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ As chegadas dos vetores de 14/09 saem das RECEITAS, e nao de JSON escrito a
# mao: um vetor que julgasse por uma chegada propria provaria que os dois lados
# concordam sobre algo que ninguem publica.
from job.tipos_de_desafio import RECEITAS  # noqa: E402
from motores.damas.motor_damas import EstadoDamas, MotorDamas  # noqa: E402
from motores.pontinhos import feitos_pontinhos  # noqa: E402
from motores.pontinhos.motor_pontinhos import EstadoPontinhos  # noqa: E402

VERSAO = 1

# As duas copias. A do frontend fica em `contracts/` porque e artefato de
# contrato da spec; a daqui fica em `contratos/`, ao lado do manifesto do
# catalogo de feitos.
DESTINOS = (
    RAIZ / "contratos" / "vetores-verificacao-desafio.json",
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-verificacao-desafio.json",
)


# ═══════════════════════════════════════════════════════════════════════════
# A posicao de Pontinhos que serve de base a quatro vetores
# ═══════════════════════════════════════════════════════════════════════════
#
# Tabuleiro `pequeno`: 4 linhas x 3 colunas de caixas, matriz 9x7.
#
# Os rotulos: `H_r_c` com `r` par e `c` impar (tracos horizontais); `V_r_c` com
# `r` impar e `c` par (verticais). A caixa (i, j) tem quatro lados:
#
#     topo H_{2i}_{2j+1} · base H_{2i+2}_{2j+1} · esq V_{2i+1}_{2j} · dir V_{2i+1}_{2j+2}
#
# ⚠️ **A preparacao foi montada para NAO fechar nenhuma caixa.** Ela marca os
# dois lados verticais das quatro caixas da coluna da esquerda e o topo da
# primeira — cada uma fica com no maximo tres lados. Assim o placar inicial e
# 0 x 0, e a vez volta para o jogador 1 (numero PAR de lances, sem turno extra).
#
# O resultado e uma "escada" de quatro caixas que fecham uma a uma, de cima para
# baixo: marcar `H_2_1` fecha a caixa 0 e deixa a 1 com tres lados, e assim por
# diante. Quem fecha caixa joga de novo — entao as quatro cabem num TURNO SO, e e
# exatamente isso que torna esta posicao boa para testar janela.
PREPARACAO_ESCADA = [
    "V_1_0", "V_1_2",   # caixa (0,0): esquerda e direita
    "V_3_0", "V_3_2",   # caixa (1,0)
    "V_5_0", "V_5_2",   # caixa (2,0)
    "V_7_0", "V_7_2",   # caixa (3,0)
    "H_0_1",            # o topo da escada
    "H_0_3",            # ⚠️ lance NEUTRO, longe da escada: existe so para o
                        #    numero de lances ficar par e a vez voltar ao J1
]

# Os quatro lances que descem a escada, cada um fechando exatamente uma caixa.
DESCER_A_ESCADA = ["H_2_1", "H_4_1", "H_6_1", "H_8_1"]


# ═══════════════════════════════════════════════════════════════════════════
# A CADEIA LONGA (tipo 22) — o tabuleiro cheio, com uma cadeia aberta
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Esta preparacao NAO e conferivel de cabeca, e isso e assumido.** As outras
# posicoes deste arquivo sao pequenas de proposito; esta precisa de um tabuleiro
# quase cheio, porque **cadeia longa so existe com o tabuleiro cheio** — e o
# proprio enredo do tipo: primeiro se constroi, depois se captura.
#
# Como ela foi obtida, para quem precisar refaze-la: marcam-se **so tracos
# seguros** (os que nao entregam caixa, `abertura_forcada.caixas_entregues == 0`)
# ate o zugzwang — a posicao em que todo traco entrega alguma coisa —, e ai o
# adversario abre a maior cadeia. O resultado e uma cadeia de **dez** caixas
# esperando o jogador 1.
#
# ⚠️ Os dezessete primeiros sao a construcao; `H_0_1`, o ultimo, e a **abertura do
# adversario** — e e ele que poe a cadeia na mesa.
PREPARACAO_CADEIA = [
    "V_3_0", "V_1_2", "H_4_1", "V_7_2", "H_0_3", "V_1_0",
    "H_8_1", "V_3_4", "H_6_5", "V_5_6", "H_0_5", "V_7_6",
    "H_4_3", "V_1_6", "V_3_6", "H_8_3", "V_5_2",
    "H_0_1",   # a abertura: o adversario entrega a cadeia inteira
]

#: A cadeia inteira, capturada de uma vez: dez caixas, dez lances seguidos.
CAPTURAR_A_CADEIA = [
    "H_2_1", "V_3_2", "H_2_3", "V_1_4", "H_2_5",
    "H_4_5", "V_5_4", "H_6_3", "V_7_4", "H_8_5",
]

#: ⚠️ **O traco que QUEBRA a corrida** — ele nao fecha caixa, entao a vez passa.
#:
#: E o que permite escrever os casos de fronteira: parar em seis (cumpre, no
#: limite) e parar em cinco (nao cumpre por pouco). ⛔ Sem ele nao daria para
#: parar: quem fecha caixa joga de novo, e a corrida so termina quando alguem
#: **deixa** de fechar. E, de quebra, e o proprio *double dealing* — a jogada que
#: o tipo existe para ensinar.
QUEBRA_A_CORRIDA = "V_5_0"


def _posicao_do_pontinhos() -> tuple[dict[str, Any], EstadoPontinhos]:
    """Monta `js_posicao_inicial` da escada e devolve o estado correspondente.

    ⚠️ `vez_de` e `placar` sao **derivados**, e vao para o JSON como conferencia:
    quem le reconstroi a sequencia e compara. Divergiu, o dado esta corrompido —
    o mesmo principio de `ic_chegada_encerra_partida`, que ninguem digita.
    """
    estado = EstadoPontinhos(lances=tuple(PREPARACAO_ESCADA))
    # A preparacao nao pode ter fechado caixa nenhuma: se fechou, a escada nao e
    # o que este arquivo diz que ela e, e todos os vetores abaixo estao errados.
    assert estado.placar == {1: 0, -1: 0}, (
        f"a preparacao fechou caixa: {estado.placar}"
    )
    assert estado.vez_de == 1, f"a vez nao voltou ao jogador 1: {estado.vez_de}"

    posicao = {
        "versao": 1,
        "lances": [
            {"n": n, "jogador": 1 if n % 2 else -1, "lance": lance}
            for n, lance in enumerate(PREPARACAO_ESCADA, start=1)
        ],
        "vez_de": estado.vez_de,
        "placar": {"j1": estado.placar[1], "j2": estado.placar[-1]},
    }
    return posicao, estado


def _feitos_do_pontinhos(base: EstadoPontinhos, fita: list[str]) -> dict[str, int]:
    """Reproduz a fita a partir da posicao base e mede os feitos do jogador 1.

    Quem conta as caixas e o **motor** (`EstadoPontinhos`), nao este script: as
    regras do Pontinhos moram no espelho do laboratorio, e reimplementa-las aqui
    criaria uma segunda fonte da verdade — exatamente o que o projeto inteiro
    tenta evitar.
    """
    estado = base
    for lance in fita:
        estado = estado.com_lance(lance)
    placar_antes = base.placar
    placar_depois = estado.placar
    return {
        "caixas_fechadas": placar_depois[1] - placar_antes[1],
        "caixas_do_adversario": placar_depois[-1] - placar_antes[-1],
        "lances_do_jogador": len(fita),
    }


def _fita(base_jogador: int, lances: list[str]) -> list[dict[str, Any]]:
    """A fita no vocabulario do log: `n`, `jogador`, `lance`.

    ⚠️ Todos os lances destas fitas sao do **mesmo** jogador, porque nas duas
    situacoes montadas aqui ele fecha caixa e joga de novo. Um vetor com troca de
    vez precisaria calcular o jogador lance a lance — quando esse caso entrar,
    ele vem com a vez lida do motor, nunca escrita a mao.
    """
    return [
        {"n": n, "jogador": base_jogador, "lance": lance}
        for n, lance in enumerate(lances, start=1)
    ]


def vetores_do_pontinhos() -> list[dict[str, Any]]:
    """Os seis vetores de Pontinhos: dois tipos x (cumpre · por pouco · invalido)."""
    posicao, base = _posicao_do_pontinhos()
    comum = {
        "co_jogo": "pontinhos",
        "co_variante": "pequeno",
        "co_formato_posicao": "sequencia_lances",
        "js_posicao_inicial": posicao,
    }

    # ── Tipo 1: fechar caixas dentro de uma janela de turnos ────────────────
    chegada_4_em_2_turnos = {
        "versao": 1,
        "janela": {"tipo": "turnos_do_jogador", "n": 2},
        "clausulas": [
            {
                "tipo": "medida",
                "chave": "caixas_fechadas",
                "comparador": "maior_ou_igual",
                "valor": 4,
            }
        ],
    }

    # ── Tipo 2: chegar a um placar, sem limite de turnos ────────────────────
    chegada_placar_4 = {
        "versao": 1,
        "janela": {"tipo": "partida"},
        "clausulas": [
            {
                "tipo": "medida",
                "chave": "caixas_fechadas",
                "comparador": "maior_ou_igual",
                "valor": 4,
            }
        ],
    }

    quatro = DESCER_A_ESCADA
    tres = DESCER_A_ESCADA[:3]
    # O lance ilegal: `H_0_1` ja foi marcado na preparacao. ⚠️ Lance repetido e
    # **dado invalido**, e nao "nao cumpriu" — a diferenca importa, porque uma
    # fita corrompida nao pode ser confundida com uma tentativa fracassada (D-05).
    invalido = ["H_2_1", "H_0_1"]

    return [
        {
            "id": "P1-escada-fecha-4-em-1-turno-cumpre",
            **comum,
            "de_vetor": "Desce a escada inteira: quatro caixas em quatro lances, "
            "todos do mesmo turno, porque quem fecha caixa joga de novo.",
            "nu_tipo_desafio": 1,
            "co_tipo_desafio": "pontinhos_fechar_caixas",
            "lances": _fita(1, quatro),
            "js_chegada": chegada_4_em_2_turnos,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_do_pontinhos(base, quatro),
            },
        },
        {
            "id": "P1-escada-fecha-3-nao-cumpre-por-pouco",
            **comum,
            "de_vetor": "Para uma caixa antes do objetivo. E o caso que pega erro "
            "de fronteira: 3 >= 4 e falso, e um comparador trocado passaria.",
            "nu_tipo_desafio": 1,
            "co_tipo_desafio": "pontinhos_fechar_caixas",
            "lances": _fita(1, tres),
            "js_chegada": chegada_4_em_2_turnos,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_do_pontinhos(base, tres),
            },
        },
        {
            "id": "P1-lance-repetido-e-dado-invalido",
            **comum,
            "de_vetor": "O segundo lance marca um traco que a posicao inicial ja "
            "tinha. ⚠️ Isso e DADO INVALIDO, nunca 'nao cumpriu'.",
            "nu_tipo_desafio": 1,
            "co_tipo_desafio": "pontinhos_fechar_caixas",
            "lances": _fita(1, invalido),
            "js_chegada": chegada_4_em_2_turnos,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
        {
            "id": "P4-placar-4-na-partida-cumpre",
            **comum,
            "de_vetor": "A MESMA fita do primeiro vetor, com janela `partida`. O "
            "par existe para separar o julgamento da janela do julgamento da "
            "clausula: se os dois derem resultados diferentes, o erro esta na "
            "janela.",
            "nu_tipo_desafio": 4,
            "co_tipo_desafio": "pontinhos_chegar_ao_placar",
            "lances": _fita(1, quatro),
            "js_chegada": chegada_placar_4,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_do_pontinhos(base, quatro),
            },
        },
        {
            "id": "P4-placar-3-nao-cumpre-por-pouco",
            **comum,
            "de_vetor": "Tres caixas na partida inteira: nao chega ao placar.",
            "nu_tipo_desafio": 4,
            "co_tipo_desafio": "pontinhos_chegar_ao_placar",
            "lances": _fita(1, tres),
            "js_chegada": chegada_placar_4,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_do_pontinhos(base, tres),
            },
        },
        {
            "id": "P4-traco-inexistente-e-dado-invalido",
            **comum,
            "de_vetor": "`H_9_9` nao existe num tabuleiro 4x3. Rotulo fora do "
            "tabuleiro e dado invalido, como o traco repetido.",
            "nu_tipo_desafio": 4,
            "co_tipo_desafio": "pontinhos_chegar_ao_placar",
            "lances": _fita(1, ["H_9_9"]),
            "js_chegada": chegada_placar_4,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════
# As damas
# ═══════════════════════════════════════════════════════════════════════════
#
# As posicoes sao **finais montados**, com pouquissimas pecas: cabem de cabeca, e
# o motor confirma que cada lance da fita e legal.
#
# A numeracao e a de 1 a 32 das casas escuras, com as brancas embaixo (21-32) e
# as pretas em cima (1-12). Branca que chega a 1-4 coroa; preta que chega a
# 29-32 coroa. Um lance simples e `27-23`; uma captura e `27x18`, e uma captura
# multipla encadeia as casas: `27x18x11`.

MOTOR_DAMAS = MotorDamas()


def _estado_damas(fen: str) -> EstadoDamas:
    return EstadoDamas(co_modalidade="brasileira", fen_inicial=fen)


def _feitos_das_damas(fen: str, fita: list[str]) -> dict[str, int]:
    """Aplica a fita com o motor e mede os feitos das BRANCAS.

    Quem valida legalidade e conta capturas e o motor — as regras das damas vivem
    no espelho do laboratorio, e este script nao as reimplementa.

    ⚠️ `capturas_extras` conta as pecas **alem da primeira** de cada lance: uma
    captura simples paga zero. Capturar e obrigatorio nas damas, e premiar uma
    captura simples seria premiar o cumprimento da regra. `maior_captura` e o
    melhor lance isolado — comer tres de uma vez exige enxergar a combinacao
    antes de mover, e comer tres em tres lances nao e a mesma proeza.
    """
    estado = _estado_damas(fen)
    coroadas = 0
    capturas_extras = 0
    maior_captura = 0

    for lance in fita:
        antes = estado
        estado = MOTOR_DAMAS.aplicar(estado, lance)
        # O numero de capturas sai da forma do lance: `27x18x11` come duas.
        capturas = lance.count("x")
        maior_captura = max(maior_captura, capturas)
        if capturas > 1:
            capturas_extras += capturas - 1
        # Coroou? A FEN passa a ter um `K` a mais do lado das brancas.
        if antes.fen.split(":")[1].count("K") < estado.fen.split(":")[1].count("K"):
            coroadas += 1

    brancas, pretas = estado.fen.split(":")[1:]
    return {
        "damas_coroadas": coroadas,
        "capturas_extras": capturas_extras,
        "maior_captura": maior_captura,
        "material_restante": len(brancas[1:].split(",")) if len(brancas) > 1 else 0,
        "material_do_adversario": len(pretas[1:].split(",")) if len(pretas) > 1 else 0,
        "lances_do_jogador": len(fita),
    }


def vetores_das_damas() -> list[dict[str, Any]]:
    """Os seis vetores de damas: coroar e captura multipla, tres casos cada."""
    chegada_coroar = {
        "versao": 1,
        "janela": {"tipo": "lances_do_jogador", "n": 1},
        "clausulas": [
            {
                "tipo": "medida",
                "chave": "damas_coroadas",
                "comparador": "maior_ou_igual",
                "valor": 1,
            }
        ],
    }
    chegada_captura_dupla = {
        "versao": 1,
        "janela": {"tipo": "lances_do_jogador", "n": 1},
        "clausulas": [
            {
                "tipo": "medida",
                "chave": "maior_captura",
                "comparador": "maior_ou_igual",
                "valor": 2,
            }
        ],
    }

    def vetor(
        identificador: str,
        descricao: str,
        nu_tipo: int,
        co_tipo: str,
        fen: str,
        fita: list[str],
        chegada: dict[str, Any],
        veredito: str,
    ) -> dict[str, Any]:
        esperado: dict[str, Any] = {"veredito": veredito}
        esperado["feitos"] = (
            {} if veredito == "dado_invalido" else _feitos_das_damas(fen, fita)
        )
        return {
            "id": identificador,
            "de_vetor": descricao,
            "co_jogo": "damas",
            "co_variante": "brasileiras",
            "co_modalidade": "brasileira",
            "co_formato_posicao": "fen",
            "js_posicao_inicial": {"versao": 1, "fen": fen, "vez_de": 1},
            "nu_tipo_desafio": nu_tipo,
            "co_tipo_desafio": co_tipo,
            "lances": [
                {"n": n, "jogador": 1, "lance": lance}
                for n, lance in enumerate(fita, start=1)
            ],
            "js_chegada": chegada,
            "esperado": esperado,
        }

    return [
        vetor(
            "D6-coroa-no-primeiro-lance-cumpre",
            "A branca em 5 tem um passo ate a oitava fileira. `5-1` coroa.",
            6,
            "damas_coroar",
            "W:W5:B28",
            ["5-1"],
            chegada_coroar,
            "cumpriu",
        ),
        vetor(
            "D6-fica-a-um-passo-nao-cumpre",
            "A mesma ideia, uma casa atras: `9-5` aproxima e nao coroa. E o caso "
            "'por pouco' — a medida vale 0, e o objetivo pede 1.",
            6,
            "damas_coroar",
            "W:W9:B28",
            ["9-5"],
            chegada_coroar,
            "nao_cumpriu",
        ),
        vetor(
            "D6-lance-ilegal-e-dado-invalido",
            "`5-6` nao e um lance de damas: 6 nao e casa vizinha de 5 na diagonal "
            "de avanco. ⚠️ Legalidade continua sendo do ARBITRO (RF-DES-035); este "
            "vetor so garante que a recusa acontece dos dois lados.",
            6,
            "damas_coroar",
            "W:W5:B28",
            ["5-6"],
            chegada_coroar,
            "dado_invalido",
        ),
        vetor(
            "D8-captura-dupla-cumpre",
            "Branca em 27, pretas em 23 e 15: `27x18x11` come as duas num lance "
            "so. `maior_captura` = 2 e `capturas_extras` = 1.",
            8,
            "damas_capturar_multipla",
            "W:W27:B23,15,4",
            ["27x18x11"],
            chegada_captura_dupla,
            "cumpriu",
        ),
        vetor(
            "D8-captura-simples-nao-cumpre-por-pouco",
            "So uma peca no caminho: a captura acontece, mas come uma. "
            "⚠️ `capturas_extras` = 0 de proposito — capturar e obrigatorio, e "
            "premiar a captura simples seria premiar o cumprimento da regra.",
            8,
            "damas_capturar_multipla",
            "W:W27:B23,4",
            ["27x18"],
            chegada_captura_dupla,
            "nao_cumpriu",
        ),
        vetor(
            "D8-ignora-a-captura-obrigatoria-e-dado-invalido",
            "Com captura disponivel, um lance simples e ilegal (lei da captura "
            "obrigatoria). O motor recusa, e o veredito e dado invalido.",
            8,
            "damas_capturar_multipla",
            "W:W27:B23,4",
            ["27-22"],
            chegada_captura_dupla,
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# A escrita
# ═══════════════════════════════════════════════════════════════════════════


def provar_que_o_invalido_e_mesmo_invalido(vetores: list[dict[str, Any]]) -> None:
    """Todo vetor `dado_invalido` tem de ser RECUSADO pelo motor. Aqui, agora.

    ⚠️ **Sem isto, o vetor mais importante do conjunto seria o menos confiavel.**
    Os vetores `cumpriu`/`nao_cumpriu` tem os feitos calculados pelo motor — se a
    fita fosse ilegal, a geracao explodiria. Ja o `dado_invalido` nao passa pelo
    motor na geracao (ele nao tem feitos a medir), entao um lance que por acaso
    FOSSE legal viraria um vetor mentiroso: os dois lados o julgariam
    `nao_cumpriu`, concordando, e o arquivo diria que ambos erraram.

    Este passo fecha o buraco: cada fita marcada invalida e aplicada de verdade, e
    o motor precisa recusa-la.
    """
    for vetor in vetores:
        if vetor["esperado"]["veredito"] != "dado_invalido":
            continue
        fita = [lance["lance"] for lance in vetor["lances"]]
        recusou = False
        try:
            if vetor["co_jogo"] == "pontinhos":
                estado = EstadoPontinhos(
                    lances=tuple(
                        lance["lance"] for lance in vetor["js_posicao_inicial"]["lances"]
                    )
                )
                for lance in fita:
                    estado = estado.com_lance(lance)
                # `EstadoPontinhos` so reproduz a partida quando lhe perguntam
                # algo — o `placar` e o que dispara a validacao da sequencia.
                estado.placar
            else:
                estado = _estado_damas(vetor["js_posicao_inicial"]["fen"])
                for lance in fita:
                    estado = MOTOR_DAMAS.aplicar(estado, lance)
        except (ValueError, KeyError) as erro:
            recusou = True
            motivo = str(erro)[:70]

        assert recusou, (
            f"o vetor {vetor['id']!r} diz `dado_invalido`, mas o motor ACEITOU a "
            f"fita {fita}. O vetor esta errado — nao o motor."
        )
        print(f"  invalido confirmado: {vetor['id']} ({motivo})")


def _feitos_com_a_fita(base: EstadoPontinhos, lances: list[str]) -> dict[str, int]:
    """Os feitos medidos pelo **medidor de verdade**, com o caminho.

    ⚠️ **Diferente de `_feitos_do_pontinhos`, que e anterior a isto**, e a
    diferenca nao e estilo: `maior_cadeia_capturada` nao se le no estado final, e
    so o medidor sabe calcula-la. Reimplementar a corrida aqui criaria uma segunda
    fonte da verdade sobre a regra que os vetores existem para travar.

    ⛔ **E por que a funcao antiga nao foi trocada por esta?** Porque isso
    acrescentaria a medida nova ao `esperado` dos vetores ja publicados, e ⚠️
    **vetor nao se edita** (regra 4 do contrato). Os antigos continuam declarando
    o que declaravam; a chave nova aparece nos vetores que nascem com ela.
    """
    estado = base
    for lance in lances:
        estado = estado.com_lance(lance)
    medidas = feitos_pontinhos.medir(
        base,
        estado,
        jogador=1,
        lances_do_jogador=len(lances),
        fita=_fita_pela_vez(base, lances),
    )
    return {chave: int(valor) for chave, valor in medidas.items()}


def _fita_pela_vez(base: EstadoPontinhos, lances: list[str]) -> list[dict[str, Any]]:
    """A fita com o `jogador` de cada passo lido do MOTOR.

    ⛔ **Nao da para escrever a vez a mao aqui.** Na cadeia longa a corrida quebra
    no meio — e justamente disso que tratam os casos de fronteira —, e uma
    alternancia inventada faria o vetor descrever uma partida que o motor nao
    reconhece.
    """
    passos: list[dict[str, Any]] = []
    atual = base
    for numero, lance in enumerate(lances, start=1):
        passos.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = atual.com_lance(lance)
    return passos


def vetores_da_cadeia_longa() -> list[dict[str, Any]]:
    """Os quatro vetores do tipo 22 — a medida que le o CAMINHO, e nao o fim."""
    base = EstadoPontinhos(lances=tuple(PREPARACAO_CADEIA))
    assert base.vez_de == 1, f"a cadeia nao e do jogador 1: vez de {base.vez_de}"
    assert base.placar == {1: 0, -1: 0}, (
        f"a preparacao ja fechou caixa: {base.placar}"
    )

    posicao = {
        "versao": 1,
        "lances": _fita_pela_vez(EstadoPontinhos(lances=()), PREPARACAO_CADEIA),
        "vez_de": base.vez_de,
        "placar": {"j1": base.placar[1], "j2": base.placar[-1]},
    }
    comum = {
        "co_jogo": "pontinhos",
        "co_variante": "pequeno",
        "co_formato_posicao": "sequencia_lances",
        "js_posicao_inicial": posicao,
        "nu_tipo_desafio": 22,
        "co_tipo_desafio": "pontinhos_cadeia_longa",
    }
    def chegada(alvo: int) -> dict[str, Any]:
        return {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {
                    "tipo": "medida",
                    "chave": "maior_cadeia_capturada",
                    "comparador": "maior_ou_igual",
                    "valor": alvo,
                }
            ],
        }

    chegada_6_em_sequencia = chegada(6)

    # ⚠️ **A fita de um vetor que CUMPRE termina no lance em que o objetivo cai.**
    # O julgamento mede lance a lance e para no primeiro em que a chegada passa a
    # valer — e os feitos que ele devolve sao os **daquele instante**, nao os do
    # fim da fita. Uma fita que continuasse depois declararia medidas que o juiz
    # nunca veria, e o vetor reprovaria uma implementacao correta.
    seis = CAPTURAR_A_CADEIA[:6]
    # ⚠️ No caso que NAO cumpre nao ha instante nenhum, entao o juiz mede a fita
    # inteira — e ai o traco que quebra a corrida pode (e precisa) entrar.
    cinco = CAPTURAR_A_CADEIA[:5] + [QUEBRA_A_CORRIDA]
    # `V_3_0` ja esta na preparacao — traco repetido e DADO INVALIDO.
    invalido = [CAPTURAR_A_CADEIA[0], "V_3_0"]

    return [
        {
            "id": "P22-cadeia-inteira-dez-caixas-cumpre",
            **comum,
            "de_vetor": "Captura a cadeia inteira: dez caixas em dez lances "
            "seguidos, porque quem fecha caixa joga de novo. ⚠️ O alvo aqui e DEZ "
            "de proposito — com alvo seis o objetivo cairia no sexto lance, e o "
            "vetor declararia medidas que o juiz nunca chega a ver.",
            "lances": _fita_pela_vez(base, CAPTURAR_A_CADEIA),
            "js_chegada": chegada(10),
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_com_a_fita(base, CAPTURAR_A_CADEIA),
            },
        },
        {
            "id": "P22-seis-no-limite-cumpre",
            **comum,
            "de_vetor": "Seis caixas seguidas, e o objetivo e seis: 6 >= 6 "
            "cumpre. E a fronteira de cima — um comparador trocado para `maior` "
            "reprovaria este vetor, e so este.",
            "lances": _fita_pela_vez(base, seis),
            "js_chegada": chegada_6_em_sequencia,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_com_a_fita(base, seis),
            },
        },
        {
            "id": "P22-cinco-nao-cumpre-por-pouco",
            **comum,
            "de_vetor": "Para em CINCO: 5 >= 6 e falso. E o caso que separa esta "
            "medida de `caixas_fechadas` — o jogador continua fechando caixas "
            "depois, mas a CORRIDA ja quebrou.",
            "lances": _fita_pela_vez(base, cinco),
            "js_chegada": chegada_6_em_sequencia,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_com_a_fita(base, cinco),
            },
        },
        {
            "id": "P22-traco-repetido-e-dado-invalido",
            **comum,
            "de_vetor": "O segundo lance marca `V_3_0`, que a posicao inicial ja "
            "tinha. Dado invalido, nunca 'nao cumpriu'.",
            "lances": _fita_pela_vez(base, invalido),
            "js_chegada": chegada_6_em_sequencia,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
    ]


#: ⚠️ **Traços das BORDAS OPOSTAS, e nenhum fecha caixa.** É a posição de que os
#: dois tipos de *"aguente"* precisam: no tabuleiro cheio da cadeia não existe
#: lance que não entregue nada, e é justamente isso que aqueles vetores medem.
SEM_FECHAR_NADA = [
    "V_1_0", "V_5_0", "V_1_6", "V_5_6",
    "V_3_0", "V_7_6", "H_0_1", "H_8_5",
]


def _feitos_alternando(base: EstadoPontinhos, lances: list[str]) -> dict[str, int]:
    """Os feitos de uma fita em que a vez ALTERNA, e não é sempre do jogador 1.

    ⛔ **`_feitos_com_a_fita` não serve aqui**, e a diferença é uma linha: ela
    passa `lances_do_jogador=len(lances)`, o que só vale na cadeia longa, onde
    quem captura nunca perde a vez. ⚠️ Nos quatro tipos de 14/09 a vez passa o
    tempo todo, e contar os lances do adversário como meus faria a cláusula de
    `lances_do_jogador` fechar cedo demais — exatamente o defeito que ela existe
    para impedir.
    """
    fita = _fita_pela_vez(base, lances)
    estado = base
    for lance in lances:
        estado = estado.com_lance(lance)
    meus = sum(1 for passo in fita if passo["jogador"] == base.vez_de)
    medidas = feitos_pontinhos.medir(
        base,
        estado,
        jogador=base.vez_de,
        lances_do_jogador=meus,
        fita=fita,
    )
    return {chave: int(valor) for chave, valor in medidas.items()}


def _posicao_de(base: EstadoPontinhos, preparacao: list[str]) -> dict[str, Any]:
    """`js_posicao_inicial` no formato do contrato, com `vez_de` e placar do motor."""
    return {
        "versao": 1,
        "lances": _fita_pela_vez(EstadoPontinhos(lances=()), preparacao),
        "vez_de": base.vez_de,
        "placar": {"j1": base.placar[1], "j2": base.placar[-1]},
    }


def vetores_dos_tipos_de_14_09() -> list[dict[str, Any]]:
    """Os nove vetores dos quatro tipos de Pontinhos que entraram em 14/09/2026.

    ⚠️ **Dois deles guardam uma regra que nenhum vetor anterior guardava:** a
    cláusula `lances_do_jogador >= n` que faz a família *"impeça"* / *"aguente"*
    funcionar. ⛔ Sem ela os tipos 2 e 15 são cumpridos no primeiro lance, porque
    *"o adversário não fechou caixa"* já é verdade antes de ele jogar — medido, e
    é o motivo de os dois terem nascido quebrados.

    ⚠️ **Os casos de "não cumpre por pouco" atacam a cláusula certa em cada um:**
    no tipo 2, falta **um lance**; no 15, fechou **uma caixa**; no 14, faltou
    **uma caixa**; no 12, cedeu **uma a mais**. É onde duas implementações
    divergem de verdade.
    """
    # ── A posição em que NINGUÉM fecha nada: os dois tipos de "aguente" ──────
    vazio = EstadoPontinhos(lances=())
    assert vazio.vez_de == 1, "a partida não começa com o jogador 1"
    posicao_limpa = _posicao_de(vazio, [])

    # ── A cadeia armada: os dois tipos de "fechar" ───────────────────────────
    cadeia = EstadoPontinhos(lances=tuple(PREPARACAO_CADEIA))
    posicao_cadeia = _posicao_de(cadeia, PREPARACAO_CADEIA)

    limpa = {
        "co_jogo": "pontinhos",
        "co_variante": "pequeno",
        "co_formato_posicao": "sequencia_lances",
        "js_posicao_inicial": posicao_limpa,
    }
    armada = {
        "co_jogo": "pontinhos",
        "co_variante": "pequeno",
        "co_formato_posicao": "sequencia_lances",
        "js_posicao_inicial": posicao_cadeia,
    }

    # ⚠️ As chegadas saem das MESMAS receitas que o job publica, e não de JSON
    # escrito aqui: um vetor que julgasse por uma chegada própria provaria que o
    # Dart e o Python concordam sobre algo que ninguém publica.
    chegada_nao_entregar = RECEITAS["pontinhos_nao_entregar"].montar({"lances": 4})
    chegada_paciencia = RECEITAS["pontinhos_paciencia"].montar({"lances": 3})
    chegada_economia = RECEITAS["pontinhos_economia_de_lances"].montar(
        {"caixas": 5, "lances": 8}
    )
    chegada_troca = RECEITAS["pontinhos_troca_favoravel"].montar(
        {"ganhar": 4, "ceder": 2}
    )

    # ⚠️ **A fita de quem CUMPRE termina no lance em que o objetivo cai** — o
    # juiz para ali, e os feitos que ele devolve são os daquele instante.
    quatro_lances_meus = SEM_FECHAR_NADA[:7]   # meus=4, fechei=0, cedi=0
    tres_lances_meus = SEM_FECHAR_NADA[:5]     # meus=3, fechei=0, cedi=0
    cinco_capturas = CAPTURAR_A_CADEIA[:5]     # meus=5, fechei=5, cedi=0
    quatro_capturas = CAPTURAR_A_CADEIA[:4]    # meus=4, fechei=4, cedi=0
    tres_capturas = CAPTURAR_A_CADEIA[:3]      # meus=3, fechei=3, cedi=0
    # ⛔ **Eu recuso a cadeia e ele a leva**: meus=1, fechei=0, cedi=3.
    #
    # ⚠️ **A tentativa ÓBVIA de escrever este caso não funciona, e o motivo vale
    # mais que o vetor:** a primeira versão fechava quatro caixas e SÓ DEPOIS
    # cedia três. O juiz disse *"cumpriu"*, e com razão — no quarto lance já
    # valiam `4 >= 4` e `0 <= 2`, e ele para no primeiro instante em que a
    # conjunção vale. ✅ **Ceder depois não desfaz o que já foi cumprido**, e essa
    # é a semântica certa deste tipo.
    recusou_a_cadeia = [QUEBRA_A_CORRIDA] + CAPTURAR_A_CADEIA[:3]

    return [
        # ── tipo 2 · pontinhos_nao_entregar ─────────────────────────────────
        {
            "id": "P2-quatro-lances-sem-ceder-cumpre",
            **limpa,
            "nu_tipo_desafio": 2,
            "co_tipo_desafio": "pontinhos_nao_entregar",
            "de_vetor": "Quatro lances meus, e o adversário não fechou caixa "
            "nenhuma. ⚠️ Cumpre NO QUARTO, e não antes: `caixas_do_adversario "
            "<= 0` já valia no primeiro, e é a cláusula de `lances_do_jogador` "
            "que segura o julgamento até aqui.",
            "lances": _fita_pela_vez(vazio, quatro_lances_meus),
            "js_chegada": chegada_nao_entregar,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_alternando(vazio, quatro_lances_meus),
            },
        },
        {
            "id": "P2-tres-lances-nao-cumpre-por-pouco",
            **limpa,
            "nu_tipo_desafio": 2,
            "co_tipo_desafio": "pontinhos_nao_entregar",
            "de_vetor": "A MESMA partida, um lance mais curta: três lances meus, "
            "nada cedido, e `3 >= 4` é falso. ⛔ É o caso que uma implementação "
            "sem a cláusula de lances declararia CUMPRIDO — e por isso ele é o "
            "vetor mais importante dos nove.",
            "lances": _fita_pela_vez(vazio, tres_lances_meus),
            "js_chegada": chegada_nao_entregar,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_alternando(vazio, tres_lances_meus),
            },
        },
        # ── tipo 15 · pontinhos_paciencia ───────────────────────────────────
        {
            "id": "P15-tres-lances-sem-mexer-no-placar-cumpre",
            **limpa,
            "nu_tipo_desafio": 15,
            "co_tipo_desafio": "pontinhos_paciencia",
            "de_vetor": "Três lances meus sem fechar nada e sem ceder nada. As "
            "três cláusulas valem no terceiro, e é ali que o juiz para.",
            "lances": _fita_pela_vez(vazio, tres_lances_meus),
            "js_chegada": chegada_paciencia,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_alternando(vazio, tres_lances_meus),
            },
        },
        {
            "id": "P15-fechou-uma-caixa-nao-cumpre",
            **armada,
            "nu_tipo_desafio": 15,
            "co_tipo_desafio": "pontinhos_paciencia",
            "de_vetor": "Três lances meus, nada cedido — e TRÊS caixas fechadas. "
            "⚠️ É o caso que separa a paciência do `nao_entregar`: para aquele "
            "isto cumpriria; aqui `caixas_fechadas == 0` é falso.",
            "lances": _fita_pela_vez(cadeia, CAPTURAR_A_CADEIA[:3]),
            "js_chegada": chegada_paciencia,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_alternando(cadeia, CAPTURAR_A_CADEIA[:3]),
            },
        },
        # ── tipo 14 · pontinhos_economia_de_lances ──────────────────────────
        {
            "id": "P14-cinco-caixas-em-cinco-lances-cumpre",
            **armada,
            "nu_tipo_desafio": 14,
            "co_tipo_desafio": "pontinhos_economia_de_lances",
            "de_vetor": "Cinco caixas em cinco lances, e a janela permitia oito. "
            "⚠️ Os cinco lances são todos MEUS porque quem fecha caixa joga de "
            "novo — e é essa a diferença entre este tipo e o que conta turnos.",
            "lances": _fita_pela_vez(cadeia, cinco_capturas),
            "js_chegada": chegada_economia,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_alternando(cadeia, cinco_capturas),
            },
        },
        {
            "id": "P14-quatro-caixas-nao-cumpre-por-pouco",
            **armada,
            "nu_tipo_desafio": 14,
            "co_tipo_desafio": "pontinhos_economia_de_lances",
            "de_vetor": "Uma caixa a menos: `4 >= 5` é falso. A fronteira de "
            "baixo da cláusula de caixas.",
            "lances": _fita_pela_vez(cadeia, quatro_capturas),
            "js_chegada": chegada_economia,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_alternando(cadeia, quatro_capturas),
            },
        },
        # ── tipo 12 · pontinhos_troca_favoravel ─────────────────────────────
        {
            "id": "P12-quatro-fechadas-nada-cedido-cumpre",
            **armada,
            "nu_tipo_desafio": 12,
            "co_tipo_desafio": "pontinhos_troca_favoravel",
            "de_vetor": "Quatro caixas fechadas sem ceder nenhuma: `4 >= 4` e "
            "`0 <= 2`. As duas cláusulas valem no quarto lance.",
            "lances": _fita_pela_vez(cadeia, quatro_capturas),
            "js_chegada": chegada_troca,
            "esperado": {
                "veredito": "cumpriu",
                "feitos": _feitos_alternando(cadeia, quatro_capturas),
            },
        },
        {
            "id": "P12-tres-fechadas-nao-cumpre-por-pouco",
            **armada,
            "nu_tipo_desafio": 12,
            "co_tipo_desafio": "pontinhos_troca_favoravel",
            "de_vetor": "Uma caixa a menos na PRIMEIRA cláusula: `3 >= 4` é "
            "falso, e a segunda (`0 <= 2`) valia o tempo todo. É a fronteira de "
            "quem julga a conjunção como se fosse só a metade fácil.",
            "lances": _fita_pela_vez(cadeia, tres_capturas),
            "js_chegada": chegada_troca,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_alternando(cadeia, tres_capturas),
            },
        },
        {
            "id": "P12-cedeu-a-cadeia-inteira-nao-cumpre",
            **armada,
            "nu_tipo_desafio": 12,
            "co_tipo_desafio": "pontinhos_troca_favoravel",
            "de_vetor": "O outro lado da conjunção: recuso a cadeia, o adversário "
            "leva três, e `3 <= 2` é falso — com `0 >= 4` também falso. ⚠️ Os dois "
            "vetores de falha deste tipo atacam cláusulas diferentes, e é por isso "
            "que são dois.",
            "lances": _fita_pela_vez(cadeia, recusou_a_cadeia),
            "js_chegada": chegada_troca,
            "esperado": {
                "veredito": "nao_cumpriu",
                "feitos": _feitos_alternando(cadeia, recusou_a_cadeia),
            },
        },
        # ── um dado inválido POR TIPO ───────────────────────────────────────
        #
        # ⚠️ **Os três vereditos por tipo são regra do contrato** (regra 3), e não
        # zelo: sem o caso inválido, uma implementação que tratasse lance
        # impossível como *"não cumpriu"* passaria em tudo. ⛔ E a diferença é
        # material: *"não cumpriu"* é um resultado da partida; *"dado inválido"*
        # é um registro corrompido, que não sustenta resolução nem a favor nem
        # contra.
        #
        # ⚠️ Os três repetem `V_3_0`, que a preparação da cadeia já marcou.
        {
            "id": "P15-traco-repetido-e-dado-invalido",
            **armada,
            "nu_tipo_desafio": 15,
            "co_tipo_desafio": "pontinhos_paciencia",
            "de_vetor": "O segundo lance marca `V_3_0`, que a posição inicial já "
            "tinha. Dado inválido, nunca 'não cumpriu'.",
            "lances": [
                {"n": 1, "jogador": 1, "lance": QUEBRA_A_CORRIDA},
                {"n": 2, "jogador": 1, "lance": "V_3_0"},
            ],
            "js_chegada": chegada_paciencia,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
        {
            "id": "P14-traco-repetido-e-dado-invalido",
            **armada,
            "nu_tipo_desafio": 14,
            "co_tipo_desafio": "pontinhos_economia_de_lances",
            "de_vetor": "O segundo lance marca `V_3_0`, que a posição inicial já "
            "tinha. Dado inválido, nunca 'não cumpriu'.",
            "lances": [
                {"n": 1, "jogador": 1, "lance": CAPTURAR_A_CADEIA[0]},
                {"n": 2, "jogador": 1, "lance": "V_3_0"},
            ],
            "js_chegada": chegada_economia,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
        {
            "id": "P12-traco-repetido-e-dado-invalido",
            **armada,
            "nu_tipo_desafio": 12,
            "co_tipo_desafio": "pontinhos_troca_favoravel",
            "de_vetor": "O segundo lance marca `V_3_0`, que a posição inicial já "
            "tinha. Dado inválido, nunca 'não cumpriu'.",
            "lances": [
                {"n": 1, "jogador": 1, "lance": CAPTURAR_A_CADEIA[0]},
                {"n": 2, "jogador": 1, "lance": "V_3_0"},
            ],
            "js_chegada": chegada_troca,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
        {
            "id": "P2-traco-repetido-e-dado-invalido",
            **limpa,
            "nu_tipo_desafio": 2,
            "co_tipo_desafio": "pontinhos_nao_entregar",
            "de_vetor": "O terceiro lance repete `V_1_0`, que o primeiro já havia "
            "marcado. Dado inválido, nunca 'não cumpriu' — a diferença importa "
            "porque um registro corrompido não sustenta resolução nem a favor "
            "nem contra.",
            "lances": [
                {"n": 1, "jogador": 1, "lance": "V_1_0"},
                {"n": 2, "jogador": -1, "lance": "V_5_0"},
                {"n": 3, "jogador": 1, "lance": "V_1_0"},
            ],
            "js_chegada": chegada_nao_entregar,
            "esperado": {"veredito": "dado_invalido", "feitos": {}},
        },
    ]


def montar() -> dict[str, Any]:
    """O documento inteiro, com os vetores em ordem estavel.

    ⚠️ **Ordem estavel importa**: as duas copias sao comparadas byte a byte, e uma
    reordenacao inocente faria o cadeado acusar divergencia onde nao ha.
    """
    vetores = (
        vetores_do_pontinhos()
        + vetores_da_cadeia_longa()
        + vetores_dos_tipos_de_14_09()
        + vetores_das_damas()
    )
    provar_que_o_invalido_e_mesmo_invalido(vetores)

    identificadores = [v["id"] for v in vetores]
    assert len(set(identificadores)) == len(identificadores), (
        f"ha identificador repetido: {identificadores}"
    )

    return {
        "de_documento": "Vetores de verificacao do Desafio do Dia (RF-DES-198). "
        "GERADO por scripts/gerar_vetores_verificacao.py - nao edite a mao. "
        "Vetor nunca e apagado nem editado: corrigir e vetor NOVO.",
        "versao": VERSAO,
        "vetores": vetores,
    }


def main() -> int:
    documento = montar()
    # `ensure_ascii=False` mantem os acentos legiveis no diff; `indent=2` deixa o
    # arquivo revisavel. O `\n` final e explicito, e a escrita usa `newline=""`
    # porque este arquivo e comparado por SHA-256 entre repositorios — o
    # `write_text` do Windows converteria LF em CRLF e as duas copias deixariam de
    # bater por um motivo que nao tem nada a ver com o conteudo.
    texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"

    for destino in DESTINOS:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8", newline="") as arquivo:
            arquivo.write(texto)
        print(f"escrito: {destino} ({len(texto.encode('utf-8'))} bytes)")

    print(f"{len(documento['vetores'])} vetores, versao {VERSAO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
