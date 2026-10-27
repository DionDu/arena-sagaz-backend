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
from job.semente import (  # noqa: E402
    SEMENTE_MAXIMA,
    SEMENTE_MINIMA,
    semente_do_lance,
)
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR  # noqa: E402
from motores.damas.motor_damas import EstadoDamas, MotorDamas  # noqa: E402
from motores.damas import feitos_damas  # noqa: E402
from motores.pontinhos import feitos_pontinhos  # noqa: E402
from motores.pontinhos.motor_pontinhos import EstadoPontinhos  # noqa: E402
from motores.quatro import feitos_quatro  # noqa: E402
from motores.quatro.motor_quatro import MotorQuatro  # noqa: E402
from job import posicao_inicial as posicao_inicial_mod  # noqa: E402

#: A versao do documento. ⚠️ **2 desde 26/09/2026**, quando o bloco `sementes`
#: entrou: um leitor da versao 1 nao encontraria a chave, e e melhor que ele saiba
#: disso pelo numero do que por um `KeyError`.
VERSAO = 2

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
            elif vetor["co_jogo"] == "quatro":
                motor = MotorQuatro(vetor["co_modalidade"])
                estado = motor.de_dado(vetor["js_posicao_inicial"])
                for lance in fita:
                    estado = motor.aplicar(estado, lance)
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


# ═══════════════════════════════════════════════════════════════════════════
# OS DOIS TIPOS DE DAMAS DE 16/09/2026 — sacrificio e sobreviver
# ═══════════════════════════════════════════════════════════════════════════


#: As medidas que o medidor Python das damas produz e o do aplicativo **nao**.
#:
#: ⚠️ Declarado no topo de `medidor_desafio_damas.dart`: elas exigem o veredito
#: completo da partida — empate por repeticao, lances sem captura —, que no
#: aplicativo vive fora do medidor.
#:
#: ⛔ **E e esta lacuna que bloqueia `damas_final_da_base` (7) e `damas_vencer`
#: (10)**: os dois consultam `vitoria`, e publicá-los hoje faria o aplicativo
#: levantar `ChegadaInvalida` na cara de quem jogasse.
MEDIDAS_QUE_O_APLICATIVO_NAO_PRODUZ = ("vitoria", "empate")


def _feitos_das_damas_alternando(fen: str, fita: list[str]) -> dict[str, float]:
    """Os feitos das brancas numa fita em que **os dois lados jogam**.

    ⛔ **`_feitos_das_damas` nao serve para estes dois tipos, e nao e defeito
    dele.** Aquele helper trata a fita inteira como sendo do jogador, o que vale
    para `damas_coroar` e `damas_capturar_multipla`: os vetores deles sao de **um
    lance**, e `lances_do_jogador = len(fita)` esta certo ali.

    ⚠️ **Aqui nao vale.** O sacrificio exige que o jogador **perca** uma peca, e
    quem a captura e o adversario, no lance dele; o sobreviver conta lances do
    jogador ao longo de uma resistencia. Nos dois a fita alterna, e `len(fita)`
    contaria o dobro.

    ✅ **Por isso este helper chama o MEDIDOR DE PRODUCAO** (`feitos_damas.medir`)
    em vez de recontar. ⛔ Recontar seria a segunda fonte da verdade da regra que
    o vetor existe para provar — o vetor passaria a comparar o Dart com uma
    terceira implementacao, e nao com o Python que roda no job.

    ⚠️ **E os vetores antigos continuam com o helper antigo, de proposito:** vetor
    nunca e editado, e trocar o calculo deles mudaria numeros ja publicados.
    """
    medidas = feitos_damas.medir(
        MOTOR_DAMAS,
        _estado_damas(fen),
        list(fita),
        jogador=1,
    )
    # ⛔ **AS DUAS QUE O APLICATIVO NAO PRODUZ SAEM DAQUI — e isto foi ACHADO
    # pelos proprios vetores** (16/09/2026): os seis novos reprovaram do lado
    # Dart com `vitoria: esperado 0, medido null`.
    #
    # ⚠️ **Nao e defeito de nenhum dos dois lados**, e ja estava declarado:
    # `lib/modulos/jogos/damas/logica/medidor_desafio_damas.dart` diz, no topo,
    # que `vitoria` e `empate` **nao existem la** — elas exigem o veredito
    # completo da partida (empate por repeticao, lances sem captura), que no
    # aplicativo mora em outro lugar. ⛔ E e exatamente essa lacuna que bloqueia
    # `damas_final_da_base` (7) e `damas_vencer` (10).
    #
    # ⛔ **Filtrar aqui NAO esconde a divergencia:** o vetor e um contrato entre
    # as duas implementacoes, e um contrato so pode exigir o que as duas cumprem.
    # Quem guarda a lacuna e `test_vetores_nao_exigem_o_que_o_dart_nao_produz`,
    # que LE o arquivo Dart — no dia em que ele passar a produzir `vitoria`, o
    # cadeado falha e manda revisar estes vetores.
    return {
        chave: valor
        for chave, valor in medidas.items()
        if chave not in MEDIDAS_QUE_O_APLICATIVO_NAO_PRODUZ
    }


#: A posicao dos vetores do sacrificio: **6 pecas de cada lado**, de onde uma
#: partida real do Sagaz (semente 777) produziu a troca que o tipo pede.
#:
#: ⚠️ Ela sai do acervo pescado em partidas reais do `des`, e nao foi desenhada
#: para o teste — por isso os numeros abaixo sao os de uma partida que aconteceu.
FEN_DO_SACRIFICIO = "W:W21,22,24,25,27,29:B5,9,11,13,14,20"

#: A fita dessa partida, meio-lance a meio-lance:
#:
#:     1. 27-23      brancas avancam
#:     2. 20x27x18   ⚠️ **as pretas capturam DUAS** — e a entrega
#:     3. 22x15x8    as brancas retomam duas
#:     4. 14-18
#:     5. 25-22
#:     6. 18x25      as pretas capturam mais uma
#:     7. 29x22      ✅ as brancas retomam: 3 pretas a menos, 3 brancas a menos
FITA_DO_SACRIFICIO = [
    "27-23",
    "20x27x18",
    "22x15x8",
    "14-18",
    "25-22",
    "18x25",
    "29x22",
]

#: A posicao que **captura tres SEM entregar nada** — a que separa o sacrificio do
#: `damas_capturar_multipla`, no ar desde 12/09/2026.
#:
#: ⛔ Sem este vetor, uma implementacao que esquecesse a clausula de material
#: proprio passaria em todos os outros casos: ela julga igual em tudo **menos**
#: aqui.
FEN_DA_CADEIA_TRIPLA = "W:W25,31,32:B18,19,23,26"
LANCE_DA_CADEIA_TRIPLA = "31x22x15x24"

#: A posicao dos vetores do sobreviver: quem joga esta **duas pecas atras**.
FEN_DO_SOBREVIVER = "W:W24,26,29,32:B5,9,10,11,14,17"

#: A fita dos tres vetores do sobreviver, com os numeros que cada corte produz:
#:
#:     4 meios-lances  →  lances_do_jogador 2, material proprio 3
#:     5 meios-lances  →  lances_do_jogador 3, material proprio 3   ✅ cumpre
#:     9 meios-lances  →  lances_do_jogador 5, material proprio 2
#:
#: ⛔ **Os tres saem da MESMA fita, de proposito.** E o unico jeito de provar que
#: o que separa "cumpriu" de "nao cumpriu" e a **clausula**, e nao a posicao:
#: fitas diferentes deixariam a duvida de a divergencia vir de outro lugar.
#:
#: ⚠️ **Sao lances LEGAIS quaisquer** — o primeiro que o motor oferece a cada
#: passo —, e nao a escolha do Sagaz. O que o vetor prova e a CONTA dos feitos,
#: e nao a qualidade do jogo; gastar busca aqui nao tornaria a prova mais forte.
#: ⛔ E eles vem do motor: a primeira versao desta fita foi escrita a mao e era
#: ilegal (`29x22` numa posicao em que aquele lance nao existe).
FITA_DO_SOBREVIVER = [
    "24-19",
    "9-13",
    "19-15",
    "10x19",
    "26-22",
    "17x26",
    "29-25",
    "5-9",
    "25-21",
]

#: ⛔ **UM LANCE ILEGAL, E O MESMO PARA OS DOIS TIPOS.** O terceiro caso de todo
#: vetor e `dado_invalido`, e ele nao e burocracia: ⚠️ **um julgador que
#: engolisse lance ilegal aceitaria uma fita forjada** — e o desafio e resolvido
#: no aparelho da pessoa, que e o lugar de onde a fita vem.
#:
#: `9-13` e um lance das PRETAS, e na posicao inicial quem joga e o branco.
LANCE_ILEGAL = "9-13"


def vetores_das_damas_de_16_09() -> list[dict[str, Any]]:
    """Os seis vetores de `damas_sacrificio` e `damas_sobreviver`.

    ⚠️ **Os dois tipos usam numeros RELATIVOS a posicao** (`capturar`/`entregar`),
    e o que vai no vetor e sempre o **absoluto ja resolvido** — porque e ele que o
    aplicativo recebe. ⛔ Publicar o relativo obrigaria o Dart a refazer a conta do
    gerador, que e exatamente a fronteira que RF-DES-192 protege.
    """

    def chegada(clausulas: list[tuple[str, str, int]]) -> dict[str, Any]:
        return {
            "versao": 1,
            "janela": {"tipo": "partida"},
            "clausulas": [
                {"tipo": "medida", "chave": chave, "comparador": comparador, "valor": valor}
                for chave, comparador, valor in clausulas
            ],
        }

    def vetor(
        identificador: str,
        descricao: str,
        nu_tipo: int,
        co_tipo: str,
        fen: str,
        fita: list[str],
        js_chegada: dict[str, Any],
        veredito: str,
    ) -> dict[str, Any]:
        esperado: dict[str, Any] = {"veredito": veredito}
        esperado["feitos"] = (
            {}
            if veredito == "dado_invalido"
            else _feitos_das_damas_alternando(fen, fita)
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
            # ⚠️ **O dono de cada lance ALTERNA**, e e isso que distingue estes
            # vetores dos de damas anteriores: la a fita era de um lance so.
            "lances": [
                {"n": n, "jogador": 1 if n % 2 else -1, "lance": lance}
                for n, lance in enumerate(fita, start=1)
            ],
            "js_chegada": js_chegada,
            "esperado": esperado,
        }

    # ⚠️ Na posicao do sacrificio ha 6 de cada lado, entao `{capturar: 3,
    # entregar: 1}` vira `material_do_adversario <= 3` e `material_restante <= 5`.
    chegada_sacrificio = chegada(
        [
            ("material_do_adversario", "menor_ou_igual", 3),
            ("material_restante", "menor_ou_igual", 5),
        ]
    )
    # ⚠️ E na da cadeia tripla ha 3 brancas contra 4 pretas: capturar 3 leva o
    # adversario a 1, e o jogador continua com as 3 dele (o teto de 2 nao cai).
    chegada_na_cadeia = chegada(
        [
            ("material_do_adversario", "menor_ou_igual", 1),
            ("material_restante", "menor_ou_igual", 2),
        ]
    )
    # ⚠️ No sobreviver, 4 brancas contra 6 pretas. ⛔ Os numeros do VETOR sao
    # menores que os da publicacao (3 lances, piso 3) de proposito: um vetor de 8
    # lances precisaria de uma fita de 16 meios-lances escrita a mao, e o que ele
    # prova — a conjuncao de tempo e material — cabe em tres.
    chegada_sobreviver = chegada(
        [
            ("lances_do_jogador", "maior_ou_igual", 3),
            ("material_restante", "maior_ou_igual", 3),
        ]
    )
    # ⛔ **A chegada do terceiro caso pede MAIS TEMPO, e isso nao e capricho.**
    #
    # ⚠️ Com `lances >= 3` a conjuncao fecha no 5o meio-lance — e o material so
    # cai no 6o. O juiz dizia **cumpriu**, e estava certo: ele para no primeiro
    # instante em que as clausulas valem, e **perder depois nao desfaz**. E a
    # mesma licao do vetor P12 do Pontinhos, agora nas damas.
    #
    # ✅ Pedindo 5 lances do jogador, os dois nunca valem juntos nesta fita: o
    # material ja caiu para 2 quando o 5o lance chega. ⛔ Ai o que reprova e o
    # material, que e o que este vetor existe para provar.
    chegada_sobreviver_longa = chegada(
        [
            ("lances_do_jogador", "maior_ou_igual", 5),
            ("material_restante", "maior_ou_igual", 3),
        ]
    )

    return [
        vetor(
            "damas-sacrificio-cumpriu",
            "A troca completa: as pretas comem 3 ao longo da partida e as brancas "
            "retomam 3. No 7o meio-lance as duas clausulas valem ao mesmo tempo.",
            5,
            "damas_sacrificio",
            FEN_DO_SACRIFICIO,
            FITA_DO_SACRIFICIO,
            chegada_sacrificio,
            "cumpriu",
        ),
        vetor(
            "damas-sacrificio-faltou-capturar",
            "A MESMA partida, parada no 3o meio-lance: as brancas ja entregaram "
            "duas pecas (dentro do teto de material proprio), mas o adversario "
            "ainda tem 4 - falta comer uma. Ataca a clausula de captura.",
            5,
            "damas_sacrificio",
            FEN_DO_SACRIFICIO,
            FITA_DO_SACRIFICIO[:3],
            chegada_sacrificio,
            "nao_cumpriu",
        ),
        vetor(
            "damas-sacrificio-capturou-sem-entregar",
            "O VETOR QUE SEPARA ESTE TIPO DO `damas_capturar_multipla`: um unico "
            "lance come TRES pecas e o jogador nao perde nenhuma. A clausula de "
            "captura vale; a de material proprio, nao. Uma implementacao que "
            "esquecesse a segunda passaria em todos os outros casos e falharia so "
            "aqui.",
            5,
            "damas_sacrificio",
            FEN_DA_CADEIA_TRIPLA,
            [LANCE_DA_CADEIA_TRIPLA],
            chegada_na_cadeia,
            "nao_cumpriu",
        ),
        vetor(
            "damas-sobreviver-cumpriu",
            "Tres lances do jogador a partir de uma posicao em desvantagem, "
            "perdendo so uma peca. A janela e `partida`, e quem faz o piso de "
            "tempo e a clausula de `lances_do_jogador`.",
            9,
            "damas_sobreviver",
            FEN_DO_SOBREVIVER,
            FITA_DO_SOBREVIVER[:5],
            chegada_sobreviver,
            "cumpriu",
        ),
        vetor(
            "damas-sobreviver-faltou-um-lance",
            "A MESMA fita com meios-lances a menos: o material esta de pe e faltam "
            "lances do jogador. E o cadeado da familia 'aguente' - sem a clausula "
            "de `lances_do_jogador` este caso sairia CUMPRIDO.",
            9,
            "damas_sobreviver",
            FEN_DO_SOBREVIVER,
            FITA_DO_SOBREVIVER[:4],
            chegada_sobreviver,
            "nao_cumpriu",
        ),
        vetor(
            "damas-sobreviver-perdeu-material-demais",
            "O outro lado: lances do jogador suficientes, material abaixo do piso. "
            "A pessoa resistiu o tempo pedido e chegou la com pecas de menos - e o "
            "teto de perdas e o que diz que isso nao conta.",
            9,
            "damas_sobreviver",
            FEN_DO_SOBREVIVER,
            FITA_DO_SOBREVIVER[:9],
            chegada_sobreviver_longa,
            "nao_cumpriu",
        ),
        vetor(
            "damas-sacrificio-lance-ilegal-e-dado-invalido",
            "Um lance das PRETAS na vez das brancas. O julgador tem de recusar a "
            "fita inteira, e nao medir o que der: a fita chega do aparelho de "
            "quem jogou, e um julgador que engolisse lance ilegal aceitaria uma "
            "fita forjada.",
            5,
            "damas_sacrificio",
            FEN_DO_SACRIFICIO,
            [LANCE_ILEGAL],
            chegada_sacrificio,
            "dado_invalido",
        ),
        vetor(
            "damas-sobreviver-lance-ilegal-e-dado-invalido",
            "O mesmo no outro tipo. Repetir o caso por tipo nao e redundancia: o "
            "julgamento passa pela chegada de cada um, e um tipo pode recusar "
            "onde o outro aceita.",
            9,
            "damas_sobreviver",
            FEN_DO_SOBREVIVER,
            [LANCE_ILEGAL],
            chegada_sobreviver,
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - a virada (T124b da spec 010, 20/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **O vetor prova o JULGAMENTO, e nao a virada.** Que a posicao publicada
# "parece perdida" e a pessoa vence a forca e a prova da GERACAO
# (`job/provas_quatro.py`, T116), feita pela busca do executavel. O que o vetor
# confere e a outra metade: dado uma posicao e uma fita, o Dart e o Python dizem
# o mesmo veredito e as mesmas medidas. Por isso as posicoes sao pequenas e
# conferiveis de cabeca, como as dos outros jogos.
#
# A posicao-base e `s3 s3 s4 s4` no tradicional (7x6): o J1 tem as casas de
# baixo das colunas 3 e 4, o J2 as de cima delas, e a vez e do J1.
#
#     linha 2   . . O O . . .
#     linha 1   . . X X . . .
#               1 2 3 4 5 6 7
#
# ⚠️ **O campo `jogador` e novo** (so nos vetores do Quatro): a vez na posicao
# publicada e de quem o desafio e, e no Quatro ela pode ser do J2 - o preparo
# sorteia dentro de uma janela de seis lances (`gerador.JANELA_DO_PREPARO_QUATRO`).
# Os dois julgadores o leem com `+1` por padrao, que e o que os vetores antigos
# dizem calados. Sem ele, o desafio do J2 seria julgado do lado errado - e o
# medidor do Quatro recusa isso, nos dois lados.

#: A chegada da virada: so a vitoria (a receita, e nao um JSON escrito a mao).
_CHEGADA_DA_VIRADA = RECEITAS["quatro_virada"].montar({})

#: A posicao-base, um lance por item.
_BASE_DO_QUATRO = ["s3", "s3", "s4", "s4"]

#: A mesma posicao com um lance a mais do J1 na coluna 1: a vez passa ao J2.
_BASE_DO_QUATRO_COM_O_J2 = _BASE_DO_QUATRO + ["s1"]


def _vetor_do_quatro(
    receita: Any,
    chegada: dict[str, Any],
    identificador: str,
    descricao: str,
    iniciais: list[str],
    fita: list[str],
    veredito: str,
    feitos_ate: int | None = None,
) -> dict[str, Any]:
    """Um vetor do Quatro: a posicao, a fita e o que os dois julgadores dizem.

    Args:
        feitos_ate: quantos lances da fita os feitos medem. `None` mede a fita
            inteira, que e o caso de todo tipo que so se decide no fim. ⚠️ No
            tipo que FECHA NO MEIO (o "Encoste", T143) o juiz devolve os feitos
            do instante em que decidiu - o lance que cumpriu, ou o fim da
            janela -, e a fita pode seguir depois dele (RF-DES-213).

    Nasceu dentro de `vetores_do_quatro` (a virada, T124b) e subiu para ca na
    T124c, quando o Segure e o *"venca em ate 7"* chegaram: o formato e o mesmo
    nos tres tipos, e o que muda e so a receita e a chegada.

    ⚠️ **Os feitos saem do MEDIDOR DE PRODUCAO** (`feitos_quatro.medir`), como
    nos tipos de damas de 16/09: recontar aqui seria uma terceira implementacao
    da regra que o vetor existe para conferir. ⚠️ A pessoa e quem tem a vez na
    posicao publicada (`vez_de`), e o dono de cada lance alterna a partir dela.
    """
    co_modalidade = "tradicional"
    motor = MotorQuatro(co_modalidade)
    posicao = posicao_inicial_mod.do_quatro(iniciais, co_modalidade=co_modalidade)
    pessoa = posicao["vez_de"]
    esperado: dict[str, Any] = {"veredito": veredito}
    esperado["feitos"] = (
        {}
        if veredito == "dado_invalido"
        else feitos_quatro.medir(motor, iniciais, fita[:feitos_ate], jogador=pessoa)
    )
    return {
        "id": identificador,
        "de_vetor": descricao,
        "co_jogo": "quatro",
        "co_variante": co_modalidade,
        "co_modalidade": co_modalidade,
        "co_formato_posicao": posicao["co_formato_posicao"],
        "js_posicao_inicial": posicao,
        "nu_tipo_desafio": receita.nu_tipo_desafio,
        "co_tipo_desafio": receita.co_tipo_desafio,
        "jogador": pessoa,
        # O dono de cada lance alterna, a partir de quem tem a vez.
        "lances": [
            {"n": n, "jogador": pessoa if n % 2 else -pessoa, "lance": lance}
            for n, lance in enumerate(fita, start=1)
        ],
        "js_chegada": chegada,
        "esperado": esperado,
    }


def vetores_do_quatro() -> list[dict[str, Any]]:
    """Os cinco vetores de `quatro_virada` (T124b)."""
    receita = RECEITAS["quatro_virada"]

    def vetor(*argumentos: Any) -> dict[str, Any]:
        # A virada so muda a receita e a chegada; o resto e `_vetor_do_quatro`.
        return _vetor_do_quatro(receita, _CHEGADA_DA_VIRADA, *argumentos)

    return [
        vetor(
            "quatro-virada-cumpriu",
            "O J1 solta na coluna 5 e fica com tres embaixo (3, 4 e 5) e duas "
            "pontas livres; o J2 tapa a 2, e o J1 vence pela 6. A vitoria cai no "
            "3o meio-lance, o 2o lance da pessoa.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "cumpriu",
        ),
        vetor(
            "quatro-virada-parou-antes-de-vencer",
            "A MESMA fita sem o ultimo lance: a vitoria esta ao alcance, e a "
            "partida para antes dela. E o caso 'nao cumpre por pouco' - quem "
            "julgasse a ameaca no lugar da vitoria diria cumpriu.",
            _BASE_DO_QUATRO,
            ["s5", "s2"],
            "nao_cumpriu",
        ),
        vetor(
            "quatro-virada-o-adversario-venceu",
            "A pessoa solta na 6 (3, 4 e 6 embaixo) e o J2 tapa a 5; a pessoa "
            "solta na 7 e o J2 sobe na linha 2 (3, 4 e 5); a pessoa solta na "
            "coluna 1 em vez de tapar a 6, e o J2 fecha a linha 2 por ela. A "
            "partida termina, e com a derrota: nao cumpre.",
            _BASE_DO_QUATRO,
            ["s6", "s5", "s7", "s5", "s1", "s6"],
            "nao_cumpriu",
        ),
        vetor(
            "quatro-virada-a-pessoa-e-o-J2",
            "A vez na posicao publicada e do J2 (o J1 jogou na coluna 1). O J2 "
            "tapa a 2 e a 6, sobe na linha 2 e vence pela coluna 1: quatro na "
            "linha 2. Julgado com o jogador +1, o medidor recusaria a fita - e "
            "o vetor que obriga os dois julgadores a ler o `jogador`.",
            _BASE_DO_QUATRO_COM_O_J2,
            ["s2", "s5", "s6", "s5", "s2", "s7", "s1"],
            "cumpriu",
        ),
        vetor(
            "quatro-virada-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 8, num tabuleiro de 7). O julgador "
            "recusa a fita inteira, em vez de ignorar o lance e medir o resto.",
            _BASE_DO_QUATRO,
            ["s8"],
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - o Segure e o "venca em ate 7" (T124c, 21/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# Os dois tipos que passaram na remedicao de 21/10. As fitas longas (o empate de
# tabuleiro cheio, a vitoria no 7o e no 8o lance) foram achadas por uma busca e
# conferidas pelo arbitro: cada uma diz na descricao o que acontece nela, e o
# `provar_que_o_invalido_e_mesmo_invalido` e os dois julgadores as reproduzem.
#
# ⚠️ **O Segure e o primeiro tipo do Quatro no ar com PREDICADO**
# (`quatro_perdeu`), e e ele que cobre as PORTAS do juiz (T112/T113) - a
# virada nao as consulta, e tira-las do juiz do app sobrevivia (T124b). Dois
# casos so existem por elas: o empate termina num lance do ADVERSARIO (a porta
# `terminou_ate`), e a partida que nao terminou responde `None`, que nunca e
# `igual false`.

#: "Venca em ate 7 lances": a unica variante no ar (`EDITORIAL`, T124c).
_CHEGADA_DO_VENCER_EM_7 = RECEITAS["quatro_vencer_em_n"].montar({"lances": 7})

#: "Segure {personagem}: nao perca a partida".
_CHEGADA_DO_SEGURE = RECEITAS["quatro_segurar_magno"].montar({})

#: Um empate de tabuleiro cheio a partir da posicao-base: 38 meios-lances, o
#: ultimo do J2 (sao 42 casas, e a base ja tem 4 pecas).
_FITA_DO_EMPATE = (
    "s4 s2 s2 s7 s2 s5 s6 s7 s6 s2 s1 s6 s1 s2 s7 s2 s5 s1 s7 s7 "
    "s6 s5 s6 s4 s1 s7 s4 s4 s6 s1 s5 s5 s3 s3 s3 s5 s3 s1"
).split()


def vetores_do_quatro_de_21_10() -> list[dict[str, Any]]:
    """Os vetores do `quatro_vencer_em_n` (`{lances: 7}`) e do `quatro_segurar_magno`."""
    vencer = RECEITAS["quatro_vencer_em_n"]
    segurar = RECEITAS["quatro_segurar_magno"]

    def em_7(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(vencer, _CHEGADA_DO_VENCER_EM_7, *argumentos)

    def segure(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(segurar, _CHEGADA_DO_SEGURE, *argumentos)

    return [
        # ── "Venca em ate 7 lances" ───────────────────────────────────────────
        em_7(
            "quatro-vencer-em-7-cumpriu-no-limite",
            "A pessoa vence no 7o lance dela (o 13o meio-lance), com quatro na "
            "linha de baixo, das colunas 2 a 5; ninguem vence antes. E o limite: "
            "quem trocasse `menor_ou_igual` por `menor` diria nao cumpriu.",
            _BASE_DO_QUATRO,
            "s3 s7 s2 s6 s7 s3 s3 s1 s2 s7 s4 s3 s5".split(),
            "cumpriu",
        ),
        em_7(
            "quatro-vencer-em-7-venceu-no-8o-lance",
            "A pessoa vence, mas no 8o lance dela (o 15o meio-lance): a vitoria "
            "veio, e um lance tarde demais. Nao cumpre - quem julgasse so a "
            "vitoria diria cumpriu.",
            _BASE_DO_QUATRO,
            "s2 s6 s7 s3 s3 s1 s2 s7 s4 s3 s4 s6 s1 s6 s5".split(),
            "nao_cumpriu",
        ),
        em_7(
            "quatro-vencer-em-7-cumpriu-cedo",
            "A pessoa vence no 2o lance dela (3, 4, 5 e 6 embaixo). Bem dentro "
            "do limite: cumpre.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "cumpriu",
        ),
        em_7(
            "quatro-vencer-em-7-o-adversario-venceu",
            "A mesma derrota do vetor da virada: o J2 fecha a linha 2 no 6o "
            "meio-lance. Poucos lances, e sem vitoria: nao cumpre.",
            _BASE_DO_QUATRO,
            ["s6", "s5", "s7", "s5", "s1", "s6"],
            "nao_cumpriu",
        ),
        em_7(
            "quatro-vencer-em-7-lance-depois-do-fim-e-dado-invalido",
            "A pessoa vence no 2o lance dela, e a fita segue com mais um lance "
            "do adversario. Depois do fim nenhum lance e legal: o julgador "
            "recusa a fita inteira, em vez de parar na vitoria e ignorar o resto.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6", "s1"],
            "dado_invalido",
        ),
        # ── "Segure {personagem}: nao perca a partida" ────────────────────────
        segure(
            "quatro-segure-empate-de-tabuleiro-cheio",
            "Ninguem alinha, e o tabuleiro enche: empate, e a pessoa nao perdeu. "
            "Cumpre - no ULTIMO meio-lance, que e do ADVERSARIO: o juiz so ve o "
            "fim se avaliar o lance que encerra a partida, seja de quem for (a "
            "porta `terminou_ate`).",
            _BASE_DO_QUATRO,
            _FITA_DO_EMPATE,
            "cumpriu",
        ),
        segure(
            "quatro-segure-a-partida-nao-terminou",
            "O MESMO empate sem o ultimo lance: falta uma casa, e a partida nao "
            "acabou. O `quatro_perdeu` responde nulo, e nulo nunca e `igual "
            "false`: nao cumpre. Quem respondesse `false` no meio da partida "
            "daria o desafio a quem abandonasse.",
            _BASE_DO_QUATRO,
            _FITA_DO_EMPATE[:-1],
            "nao_cumpriu",
        ),
        segure(
            "quatro-segure-a-pessoa-venceu",
            "A pessoa vence no 2o lance dela. Vencer tambem e nao perder: cumpre.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "cumpriu",
        ),
        segure(
            "quatro-segure-o-adversario-venceu",
            "O J2 fecha a linha 2 no 6o meio-lance, um lance do adversario: a "
            "pessoa perdeu, e nao cumpre.",
            _BASE_DO_QUATRO,
            ["s6", "s5", "s7", "s5", "s1", "s6"],
            "nao_cumpriu",
        ),
        segure(
            "quatro-segure-a-pessoa-e-o-J2-e-perdeu",
            "A vez na posicao publicada e do J2. Ele solta na 7, o J1 solta na 5 "
            "(1, 3, 4 e 5 embaixo), o J2 tapa a 2 e o J1 fecha pela 6. Quem perdeu "
            "foi a pessoa: nao cumpre. Medido do lado do J1, o mesmo fim seria "
            "uma vitoria.",
            _BASE_DO_QUATRO_COM_O_J2,
            ["s7", "s5", "s2", "s6"],
            "nao_cumpriu",
        ),
        segure(
            "quatro-segure-coluna-cheia-e-dado-invalido",
            "Os dois enchem a coluna 1 (seis pecas alternadas, ninguem alinha) e "
            "o 7o lance cai nela de novo: a coluna nao tem mais casa. Dado "
            "invalido.",
            _BASE_DO_QUATRO,
            ["s1"] * 7,
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - a diagonal e as encostadas (T124c, defeito 1, 21/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# Os dois tipos que passaram na regua com o perseguidor do objetivo. Os dois
# pedem um JEITO de vencer, e por isso cada um tem o caso que separa o jeito
# certo do errado: a vitoria pela horizontal num desafio de diagonal, e a
# vitoria com uma peca encostada a menos. As fitas foram achadas por sorteio e
# conferidas pelo medidor de producao.
#
# ⚠️ **O alvo das encostadas e RELATIVO** (`editorial.parametros_efetivos`): o que
# ja esta encostado na posicao publicada mais o `a_mais` da variante. Na base, o
# J1 tem duas pecas encostadas ((3,1) e (4,1)), entao o alvo e 2 + 3 = 5.


def _chegada_das_encostadas() -> dict[str, Any]:
    """A chegada das encostadas na posicao-base, como o gerador a monta."""
    from job import editorial as editorial_mod

    motor = MotorQuatro("tradicional")
    tabuleiro = motor.tabuleiro(motor.estado_de_sequencia("".join(_BASE_DO_QUATRO)))
    encostadas = feitos_quatro.pecas_encostadas(
        motor.regras.dimensoes, tabuleiro, tabuleiro.vez
    )
    (publicacao,) = editorial_mod.EDITORIAL["quatro_encostadas"]
    parametros = editorial_mod.parametros_efetivos(
        publicacao.parametros, encostadas=encostadas
    )
    return RECEITAS["quatro_encostadas"].montar(parametros)


def vetores_do_quatro_perseguidos() -> list[dict[str, Any]]:
    """Os vetores do `quatro_vencer_diagonal` e do `quatro_encostadas`."""
    diagonal = RECEITAS["quatro_vencer_diagonal"]
    encostadas = RECEITAS["quatro_encostadas"]
    chegada_diagonal = diagonal.montar({})
    chegada_encostadas = _chegada_das_encostadas()

    def da_diagonal(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(diagonal, chegada_diagonal, *argumentos)

    def das_encostadas(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(encostadas, chegada_encostadas, *argumentos)

    return [
        # ── "Venca {personagem} com uma diagonal" ─────────────────────────────
        da_diagonal(
            "quatro-diagonal-cumpriu",
            "A pessoa vence no 4o lance dela com a diagonal que desce da "
            "esquerda: (3,4)-(4,3)-(5,2)-(6,1). `vitoria_diagonal` 1.",
            _BASE_DO_QUATRO,
            "s6 s3 s3 s5 s5 s3 s4".split(),
            "cumpriu",
        ),
        da_diagonal(
            "quatro-diagonal-venceu-pela-horizontal",
            "A pessoa vence pela LINHA DE BAIXO (3, 4, 5 e 6), e nao pela "
            "diagonal. Venceu, e nao cumpre: quem julgasse so a vitoria diria "
            "cumpriu.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "nao_cumpriu",
        ),
        da_diagonal(
            "quatro-diagonal-do-adversario",
            "O ADVERSARIO fecha a diagonal (5,1)-(4,2)-(3,3)-(2,4). Ha uma "
            "diagonal no tabuleiro, e nao e da pessoa: nao cumpre - quem contasse "
            "a diagonal de qualquer um diria cumpriu.",
            _BASE_DO_QUATRO,
            "s2 s5 s2 s3 s2 s2".split(),
            "nao_cumpriu",
        ),
        da_diagonal(
            "quatro-diagonal-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 9). Dado invalido.",
            _BASE_DO_QUATRO,
            ["s9"],
            "dado_invalido",
        ),
        # ── "Venca {personagem} com {pecas} pecas encostadas" ─────────────────
        das_encostadas(
            "quatro-encostadas-cumpriu",
            "A pessoa vence com cinco pecas encostadas, o alvo (as duas da "
            "posicao mais tres).",
            _BASE_DO_QUATRO,
            "s4 s6 s2 s4 s6 s1 s5".split(),
            "cumpriu",
        ),
        das_encostadas(
            "quatro-encostadas-uma-a-menos",
            "A pessoa vence pela linha de baixo (2 a 5) com QUATRO pecas "
            "encostadas, uma a menos que o alvo: nao cumpre por pouco - quem "
            "trocasse `maior_ou_igual` por `maior` erraria o caso do alvo exato, "
            "e quem esquecesse o relativo (alvo 3) diria cumpriu.",
            _BASE_DO_QUATRO,
            "s2 s7 s4 s4 s5".split(),
            "nao_cumpriu",
        ),
        das_encostadas(
            "quatro-encostadas-o-adversario-venceu",
            "A derrota de sempre: o J2 fecha a linha 2. Nao cumpre.",
            _BASE_DO_QUATRO,
            ["s6", "s5", "s7", "s5", "s1", "s6"],
            "nao_cumpriu",
        ),
        das_encostadas(
            "quatro-encostadas-lance-depois-do-fim-e-dado-invalido",
            "A pessoa vence pela linha de baixo e a fita segue com um lance. "
            "Dado invalido.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6", "s1"],
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - o golpe duplo e a linha de cinco (T124c, 21/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# Os dois tipos que subiram com a posicao do banco pescado. Os dois pedem um
# JEITO de vencer, e cada um tem os mesmos tres casos da diagonal: o jeito certo,
# o errado (a vitoria pela linha de baixo, de QUATRO e UMA linha so - nao e
# golpe duplo nem linha de cinco) e o jeito certo feito pelo ADVERSARIO. As fitas
# foram achadas por sorteio a partir da base e conferidas pelo medidor de
# producao (os feitos do vetor saem dele).


def vetores_do_quatro_do_banco() -> list[dict[str, Any]]:
    """Os vetores do `quatro_golpe_duplo` e do `quatro_linha_de_cinco`."""
    golpe = RECEITAS["quatro_golpe_duplo"]
    cinco = RECEITAS["quatro_linha_de_cinco"]
    chegada_golpe = golpe.montar({"linhas": 2})
    chegada_cinco = cinco.montar({"tamanho": 5})

    def do_golpe(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(golpe, chegada_golpe, *argumentos)

    def da_linha_de_cinco(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(cinco, chegada_cinco, *argumentos)

    return [
        # ── "Venca {personagem} fechando {linhas} linhas com a mesma peca" ────
        do_golpe(
            "quatro-golpe-duplo-cumpriu",
            "A pessoa vence no s1 do 5o lance dela, e a peca fecha DUAS linhas "
            "de uma vez. `linhas_no_lance_final` 2.",
            _BASE_DO_QUATRO,
            "s2 s4 s4 s5 s2 s5 s3 s7 s1".split(),
            "cumpriu",
        ),
        do_golpe(
            "quatro-golpe-duplo-uma-linha-so",
            "A pessoa vence pela linha de baixo (3, 4, 5 e 6): UMA linha so. "
            "Venceu, e nao cumpre - quem julgasse so a vitoria diria cumpriu, e "
            "quem trocasse `maior_ou_igual 2` por `maior_ou_igual 1` tambem.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "nao_cumpriu",
        ),
        do_golpe(
            "quatro-golpe-duplo-do-adversario",
            "O ADVERSARIO vence fechando duas linhas com a mesma peca. Ha um "
            "golpe duplo no tabuleiro, e nao e da pessoa: nao cumpre.",
            _BASE_DO_QUATRO,
            "s1 s6 s3 s6 s7 s4 s1 s3 s5 s5".split(),
            "nao_cumpriu",
        ),
        do_golpe(
            "quatro-golpe-duplo-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 9). Dado invalido.",
            _BASE_DO_QUATRO,
            ["s9"],
            "dado_invalido",
        ),
        # ── "Venca {personagem} com {tamanho} em linha" ───────────────────────
        da_linha_de_cinco(
            "quatro-linha-de-cinco-cumpriu",
            "A pessoa fecha a linha de baixo da coluna 3 a 7: CINCO em linha. "
            "`maior_linha` 5.",
            _BASE_DO_QUATRO,
            "s7 s1 s6 s7 s5".split(),
            "cumpriu",
        ),
        da_linha_de_cinco(
            "quatro-linha-de-cinco-so-quatro",
            "A pessoa vence pela linha de baixo com QUATRO (3 a 6), uma a menos "
            "que o alvo: nao cumpre - quem trocasse `maior_ou_igual 5` por "
            "`maior_ou_igual 4` diria cumpriu.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "nao_cumpriu",
        ),
        da_linha_de_cinco(
            "quatro-linha-de-cinco-do-adversario",
            "O ADVERSARIO vence com cinco em linha. A linha de cinco existe, e "
            "nao e da pessoa: nao cumpre.",
            _BASE_DO_QUATRO,
            "s6 s5 s2 s6 s7 s2 s6 s5".split(),
            "nao_cumpriu",
        ),
        da_linha_de_cinco(
            "quatro-linha-de-cinco-lance-depois-do-fim-e-dado-invalido",
            "A pessoa vence pela linha de baixo e a fita segue com um lance. "
            "Dado invalido.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6", "s1"],
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - o "sem o meio" (T124c, 22/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# Subiu com o piso de 9 lances da pessoa e sem a Cacau (§8zzzp, §8zzzq). Pede um
# JEITO de vencer, e por isso tem os casos que separam o certo do errado: a
# vitoria sem tocar na coluna 4; a vitoria que passou UMA vez pela coluna 4
# (quem trocasse `menor_ou_igual 0` por `menor_ou_igual 1`, ou julgasse so a
# vitoria, diria cumpriu); e a derrota sem tocar no meio (quem julgasse so a
# coluna diria cumpriu). ⚠️ Na base a pessoa ja tem uma peca na coluna 4, posta
# no PREPARO: a medida conta so os lances da fita, e e por isso que o primeiro
# caso cumpre.


def vetores_do_quatro_sem_o_meio() -> list[dict[str, Any]]:
    """Os vetores do `quatro_sem_o_meio`."""
    receita = RECEITAS["quatro_sem_o_meio"]
    chegada = receita.montar({})

    def do_sem_o_meio(*argumentos: Any) -> dict[str, Any]:
        return _vetor_do_quatro(receita, chegada, *argumentos)

    return [
        do_sem_o_meio(
            "quatro-sem-o-meio-cumpriu",
            "A pessoa vence pela linha de baixo (3, 4, 5 e 6) jogando nas "
            "colunas 5 e 6: nenhum lance DA FITA na coluna 4. A peca dela na "
            "coluna 4 veio do preparo, e nao conta. `lances_na_coluna_central` 0.",
            _BASE_DO_QUATRO,
            ["s5", "s2", "s6"],
            "cumpriu",
        ),
        do_sem_o_meio(
            "quatro-sem-o-meio-passou-uma-vez-pelo-meio",
            "A pessoa joga UMA vez na coluna 4 e depois vence pela linha de "
            "baixo. Venceu, e nao cumpre: quem julgasse so a vitoria, ou "
            "trocasse `menor_ou_igual 0` por `menor_ou_igual 1`, diria cumpriu.",
            _BASE_DO_QUATRO,
            "s4 s1 s5 s1 s6".split(),
            "nao_cumpriu",
        ),
        do_sem_o_meio(
            "quatro-sem-o-meio-o-adversario-venceu",
            "A pessoa nunca joga na coluna 4, e o J2 fecha a linha 2. Nao "
            "cumpre: quem julgasse so a coluna diria cumpriu.",
            _BASE_DO_QUATRO,
            ["s6", "s5", "s7", "s5", "s1", "s6"],
            "nao_cumpriu",
        ),
        do_sem_o_meio(
            "quatro-sem-o-meio-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 9). Dado invalido.",
            _BASE_DO_QUATRO,
            ["s9"],
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# O QUATRO EM LINHA - o "Encoste N pecas em ate M lances" (T143, 22/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# O primeiro tipo do Quatro que FECHA NO MEIO: uma medida (`pecas_encostadas`)
# numa janela de M lances da pessoa, sem `vitoria`. Os casos separam as quatro
# leituras erradas que um juiz poderia ter: (a) "a partida acabou mal, entao
# nao cumpriu" - a pessoa cumpre e DEPOIS o adversario vence, e o veredito
# continua cumpriu; (b) "olhe o fim, e nao a janela" - o alvo e alcancado um
# lance depois do prazo; (c) "vencer basta" - a pessoa vence com menos pecas
# encostadas que o alvo; (d) "conte os encostos" - o exemplo do dono tem 4
# pecas e 5 pares de vizinhas. ⚠️ Na base, as duas pecas da pessoa na linha de baixo
# ja estao encostadas (E = 2); a peca solta que ela poe em cima de uma do
# adversario (s3) nao conta ate ganhar uma vizinha DELA (s4), e entao as duas
# contam de uma vez.
#
# ⚠️ Os numeros da frase sao pequenos (M = 2 ou 3, N = 5), e nao os do
# editorial: o vetor confere a REGRA do juiz, e a regra nao muda com o numero.


def vetores_do_quatro_encoste() -> list[dict[str, Any]]:
    """Os vetores do `quatro_encoste`."""
    receita = RECEITAS["quatro_encoste"]
    em_tres = receita.montar({"lances": 3, "pecas": 5})
    em_dois = receita.montar({"lances": 2, "pecas": 5})

    def do_encoste(chegada: dict[str, Any], *argumentos: Any, **opcoes: Any) -> dict[str, Any]:
        return _vetor_do_quatro(receita, chegada, *argumentos, **opcoes)

    # s3 (solta, em cima do adversario) · s4 (encosta nela: 2 -> 4) · s5 (encosta
    # na linha de baixo: 5). O adversario empilha na coluna 7.
    ate_o_alvo = ["s3", "s7", "s4", "s7", "s5"]
    return [
        do_encoste(
            em_tres,
            "quatro-encoste-cumpriu-e-depois-perdeu",
            "A pessoa chega a 5 pecas encostadas no 3o lance dela (lance 5 da "
            "fita), e a partida segue: o adversario fecha a coluna 7 no lance 8. "
            "Cumpriu, no lance 5 - quem julgasse pelo fim da partida diria que nao.",
            _BASE_DO_QUATRO,
            ate_o_alvo + ["s7", "s1", "s7"],
            "cumpriu",
            feitos_ate=5,
        ),
        do_encoste(
            em_tres,
            "quatro-encoste-cumpriu-no-ultimo-lance-da-janela",
            "A mesma fita, parada no lance que cumpre: o 3o e ultimo lance da "
            "janela. Cumpriu.",
            _BASE_DO_QUATRO,
            ate_o_alvo,
            "cumpriu",
        ),
        do_encoste(
            em_dois,
            "quatro-encoste-alcancou-depois-da-janela",
            "Com a janela de 2 lances, as 5 encostadas chegam no 3o lance da "
            "pessoa, um depois do prazo. Nao cumpre, e os feitos sao os do fim da "
            "janela (4 encostadas, lance 4): quem olhasse a fita inteira diria "
            "cumpriu.",
            _BASE_DO_QUATRO,
            ate_o_alvo,
            "nao_cumpriu",
            feitos_ate=4,
        ),
        do_encoste(
            em_tres,
            "quatro-encoste-venceu-sem-o-alvo",
            "A pessoa fecha a linha de baixo (2, 3, 4 e 5) no 2o lance dela, com "
            "4 pecas encostadas. A partida acabou antes do alvo de 5: nao cumpre. "
            "Quem tratasse a vitoria como cumprimento diria cumpriu.",
            _BASE_DO_QUATRO,
            ["s5", "s7", "s2"],
            "nao_cumpriu",
        ),
        # ── O exemplo do dono (a proposta §1): A, B e C lado a lado, e D em
        # cima de B. Sao 4 PECAS encostadas, e 5 PARES de vizinhas (A-B, B-C,
        # B-D, e D toca A e C na diagonal): os dois vetores separam as duas
        # contagens. O tabuleiro comeca vazio, e o adversario joga longe.
        do_encoste(
            receita.montar({"lances": 4, "pecas": 4}),
            "quatro-encoste-o-exemplo-do-dono-quatro-pecas",
            "A (s2), B (s3) e C (s4) na linha de baixo e D (s3) em cima de B: "
            "4 pecas encostadas no 4o lance. Pelo caminho, A sozinha conta 0 e, "
            "com B ao lado, as duas contam (2). Cumpriu o alvo de 4.",
            [],
            ["s2", "s7", "s3", "s7", "s4", "s6", "s3"],
            "cumpriu",
        ),
        do_encoste(
            receita.montar({"lances": 4, "pecas": 5}),
            "quatro-encoste-o-exemplo-do-dono-conta-pecas-e-nao-pares",
            "A mesma fita com o alvo de 5. Sao 4 pecas e 5 pares de vizinhas: "
            "nao cumpre. Quem contasse encostos, e nao pecas, diria cumpriu.",
            [],
            ["s2", "s7", "s3", "s7", "s4", "s6", "s3"],
            "nao_cumpriu",
        ),
        do_encoste(
            em_tres,
            "quatro-encoste-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 9). Dado invalido.",
            _BASE_DO_QUATRO,
            ["s9"],
            "dado_invalido",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# A CLAUSULA `figura` (T146 da spec 010, §8zzzr item 10)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **As chegadas daqui sao escritas a mao**, no formato do contrato (nasceram
# na T146, antes da receita): o que estes vetores conferem e a REGRA da clausula
# nos dois juizes - a translacao, o espelho, as duas cores, a casa vazia, de
# quem e o desafio. As figuras que o job publica tem vetores proprios, montados
# pela receita (`vetores_das_figuras_no_ar`, T150).
#
# Os desenhos, de cima para baixo (`X` da pessoa, `O` do adversario, `_` vazia,
# `.` fora da figura):
#
#     L          losango      U (oco ou cheio)   U so oco    o i curto
#     X .        . X .        X . X              X _ X       X
#     X .        X O X        X X X              X X X       X
#     X X        . X .                                       O
#
# O tabuleiro comeca vazio e a pessoa e o J1, salvo no vetor do J2; nenhuma
# fita forma quatro em linha, de nenhum dos lados.


#: A receita do `quatro_figura`, esteja ela fora do ar (ate a T150) ou no ar.
#: ⚠️ Lida dos DOIS dicionarios para a promocao nao precisar mexer aqui: o tipo
#: mora de um lado so (`test_cada_tipo_do_quatro_mora_de_UM_lado_so`).
_RECEITA_DA_FIGURA = {**RECEITAS_FORA_DO_AR, **RECEITAS}["quatro_figura"]


def _chegada_da_figura(desenho: list[str], lances: int, *, espelhar: bool = False) -> dict[str, Any]:
    """A linha de chegada de "forme a figura em ate N lances"."""
    return {
        "versao": 1,
        "janela": {"tipo": "lances_do_jogador", "n": lances},
        "clausulas": [{"tipo": "figura", "desenho": desenho, "espelhar": espelhar}],
    }


def vetores_da_figura() -> list[dict[str, Any]]:
    """Os vetores da clausula `figura`."""
    # O numero (51) e o nome do tipo saem da receita (`_RECEITA_DA_FIGURA`).
    tipo = _RECEITA_DA_FIGURA
    l_ = ["X.", "X.", "XX"]
    losango = [".X.", "XOX", ".X."]
    u_qualquer = ["X.X", "XXX"]
    u_oco = ["X_X", "XXX"]

    def da_figura(chegada: dict[str, Any], *argumentos: Any, **opcoes: Any) -> dict[str, Any]:
        return _vetor_do_quatro(tipo, chegada, *argumentos, **opcoes)

    # A pessoa sobe a coluna 5 (tres pecas) e poe a 4a na 6, embaixo: o L, na
    # parte de baixo e a direita do tabuleiro. O adversario joga em 1 e 2.
    o_l_na_direita = ["s5", "s1", "s5", "s2", "s5", "s1", "s6"]
    # A mesma coluna 5, e a 4a peca na 4: o espelho do L (um J).
    o_j = ["s5", "s1", "s5", "s2", "s5", "s1", "s4"]
    # O U: a linha de baixo 3-4-5 e as pontas em 3 e 5. Na 1a fita a casa de
    # cima da 4 fica vazia; na 2a o adversario a ocupa no lance 4.
    u_vazio = ["s3", "s1", "s4", "s1", "s5", "s7", "s3", "s7", "s5"]
    u_ocupado = ["s3", "s1", "s4", "s4", "s5", "s7", "s3", "s7", "s5"]

    return [
        da_figura(
            _chegada_da_figura(l_, 4),
            "quatro-figura-o-L-em-outro-lugar-cumpriu",
            "A pessoa forma o L nas colunas 5 e 6, longe do canto de cima e da "
            "esquerda: a figura vale em qualquer coluna e qualquer altura. "
            "Cumpriu no 4o lance dela (lance 7 da fita).",
            [],
            o_l_na_direita,
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(l_, 3),
            "quatro-figura-o-L-um-lance-depois-da-janela",
            "A mesma fita com a janela de 3 lances: o L fecha no 4o lance da "
            "pessoa, um depois do prazo. Nao cumpre, e os feitos sao os do fim "
            "da janela (lance 6).",
            [],
            o_l_na_direita,
            "nao_cumpriu",
            feitos_ate=6,
        ),
        da_figura(
            _chegada_da_figura(l_, 4, espelhar=True),
            "quatro-figura-o-espelho-aceito",
            "A pessoa forma o espelho do L (a 4a peca na coluna 4, e nao na 6), "
            "e a figura aceita o espelho. Cumpriu no lance 7.",
            [],
            o_j,
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(l_, 4),
            "quatro-figura-o-espelho-recusado",
            "A mesma fita, com a figura que NAO aceita o espelho: o J nao e o L. "
            "Nao cumpre. Quem espelhasse sempre diria cumpriu.",
            [],
            o_j,
            "nao_cumpriu",
        ),
        da_figura(
            _chegada_da_figura(losango, 4),
            "quatro-figura-o-losango-cumpriu",
            "O adversario poe a peca dele em cima da primeira da pessoa (coluna "
            "4), e ela a cerca: em cima, e dos lados nas colunas 3 e 5. A peca "
            "do meio e DELE, como o desenho pede. Cumpriu no lance 7.",
            [],
            ["s4", "s4", "s4", "s3", "s3", "s5", "s5"],
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(losango, 5),
            "quatro-figura-a-casa-O-com-peca-da-pessoa",
            "O mesmo desenho, mas o meio e da PESSOA: ela fez a cruz inteira "
            "(coluna 4 com tres, e as 3 e 5 no meio). A casa `O` pede a peca do "
            "adversario. Nao cumpre. Quem lesse `O` como 'qualquer peca' diria "
            "cumpriu.",
            [],
            ["s4", "s3", "s4", "s5", "s3", "s1", "s5", "s1", "s4"],
            "nao_cumpriu",
        ),
        da_figura(
            _chegada_da_figura(l_, 5),
            "quatro-figura-so-pecas-do-adversario",
            "Quem forma o L e o ADVERSARIO (coluna 5 com tres e a 6 embaixo), e "
            "a pessoa joga um 5o lance depois. A figura e da pessoa: nao cumpre. "
            "Quem conferisse a forma sem a cor diria cumpriu.",
            [],
            ["s1", "s5", "s1", "s5", "s2", "s5", "s2", "s6", "s7"],
            "nao_cumpriu",
        ),
        da_figura(
            _chegada_da_figura(u_qualquer, 5),
            "quatro-figura-o-U-oco-vale",
            "O U com o miolo vazio, e o desenho com `.` no miolo: vale (o dono "
            "decidiu que o U vale oco ou cheio). Cumpriu no lance 9.",
            [],
            u_vazio,
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(u_qualquer, 5),
            "quatro-figura-o-U-cheio-vale",
            "O U com a peca do ADVERSARIO no miolo, e o mesmo desenho com `.`: "
            "vale tambem. Cumpriu no lance 9.",
            [],
            u_ocupado,
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(u_oco, 5),
            "quatro-figura-a-casa-vazia-ocupada",
            "O desenho com `_` no miolo (a casa tem de estar VAZIA), e o "
            "adversario a ocupou. Nao cumpre. Quem lesse `_` como `.` diria "
            "cumpriu.",
            [],
            u_ocupado,
            "nao_cumpriu",
        ),
        da_figura(
            _chegada_da_figura(u_oco, 6),
            "quatro-figura-a-casa-vazia-fecha-no-instante",
            "O U oco se forma no lance 9, com o miolo vazio, e o adversario o "
            "ocupa no lance 10. O juiz fecha no 9, e o que vem depois nao "
            "desfaz: cumpriu, com os feitos do lance 9. Quem julgasse pelo fim "
            "da janela diria nao.",
            [],
            u_vazio + ["s4", "s7"],
            "cumpriu",
            feitos_ate=9,
        ),
        da_figura(
            _chegada_da_figura(["X", "X", "O"], 2),
            "quatro-figura-a-pessoa-e-o-J2",
            "A vez na posicao publicada e do J2, e `X` e dele: ele poe a 2a peca "
            "na coluna 3, por cima da sua e da do J1. Cumpriu no 1o lance. Quem "
            "lesse `X` como o J1 diria nao cumpriu.",
            _BASE_DO_QUATRO_COM_O_J2,
            ["s3"],
            "cumpriu",
        ),
        da_figura(
            _chegada_da_figura(l_, 4),
            "quatro-figura-lance-ilegal-e-dado-invalido",
            "Uma coluna que nao existe (a 9). Dado invalido.",
            [],
            ["s9"],
            "dado_invalido",
        ),
    ]


# ── As figuras NO AR (T150, 23/10/2026) ─────────────────────────────────────
#
# ⚠️ Os vetores acima conferem a REGRA da clausula com desenhos escritos a mao.
# Estes conferem as figuras que o job PUBLICA, com a chegada montada pela
# propria receita (`_RECEITA_DA_FIGURA.montar`): se o catalogo mudar um
# desenho, o vetor muda junto, e o juiz em Dart tem de concordar de novo.
#
# Uma fita por figura, do tabuleiro vazio, com a janela exata (o numero de
# lances da pessoa): a figura fecha no ultimo lance. Nenhuma fita forma quatro
# em linha. Coordenadas `(coluna, linha)`, linha 1 embaixo.

#: As fitas das figuras no ar (uma por figura), e quantos lances a pessoa joga.
_FITAS_DAS_FIGURAS_NO_AR: dict[str, tuple[list[str], int, str]] = {
    # X em (4,1) (5,1) e (3,2) (4,2); o (3,1) e do adversario, e da o apoio.
    "z": (["s4", "s3", "s5", "s1", "s4", "s1", "s3"], 4, "o Z com o apoio do adversario"),
    # X nas linhas 1 e 3 das colunas 3 e 4; a linha 2 do meio e do adversario.
    "igual": (["s3", "s3", "s4", "s4", "s3", "s1", "s4"], 4, "o igual com o meio do adversario"),
    # A coluna 4, de baixo para cima: X, X, O (o adversario) e X - o desenho
    # `X / O / X / X`, lido de cima.
    "i": (["s4", "s1", "s4", "s4", "s4"], 3, "o i com a peca do adversario no meio"),
    # X em (3,1) (4,1) (3,2) (4,2).
    "quadrado": (["s3", "s1", "s4", "s1", "s3", "s7", "s4"], 4, "o quadrado no chao"),
    # X nos cantos (3,1) (5,1) (3,3) (5,3) e no centro (4,2); os apoios (4,1),
    # (3,2) e (5,2) sao do adversario.
    "xis": (
        ["s3", "s4", "s5", "s3", "s4", "s5", "s3", "s1", "s5"],
        5,
        "o xis com os tres apoios do adversario",
    ),
    # As do segundo lote que a regua aprovou (T150, 27/10/2026).
    #
    # A coluna 4, de baixo para cima: X, X, X, O (o adversario) e X - o desenho
    # `X / O / X / X / X`, lido de cima. Os outros lances do adversario vao para
    # a coluna 1, longe da figura.
    "i_longo": (
        ["s4", "s1", "s4", "s1", "s4", "s4", "s4"],
        4,
        "o i longo com a peca do adversario no meio",
    ),
    # X em (3,1) (4,1) e (3,3) (4,3); a linha 2, entre elas, e do adversario.
    "igual_sanduiche": (
        ["s3", "s1", "s4", "s3", "s3", "s4", "s4"],
        4,
        "o igual com o recheio do adversario",
    ),
    # X em (4,1), (3,2), (5,2) e (4,3); o centro (4,2) e do adversario, e os
    # apoios (3,1) e (5,1) tambem.
    "losango": (
        ["s4", "s3", "s3", "s4", "s4", "s5", "s5"],
        4,
        "o losango com o centro do adversario",
    ),
    # A exclamacao (DECISOES §8zzzu) nao tem vetor: a regua de 27/10/2026 a
    # deixou fora do ar (11, 19 e 21 de 36), e esta tabela e so das publicadas.
}


def vetores_das_figuras_no_ar() -> list[dict[str, Any]]:
    """Um vetor por figura publicada: cumpre no ultimo lance da janela exata."""
    receita = _RECEITA_DA_FIGURA
    return [
        _vetor_do_quatro(
            receita,
            receita.montar({"figura": nome, "lances": lances}),
            f"quatro-figura-no-ar-{nome}-cumpriu",
            f"A chegada da receita, com {descricao}, em ate {lances} lances: a "
            f"figura fecha no {lances}o lance da pessoa (lance {len(fita)} da fita).",
            [],
            fita,
            "cumpriu",
        )
        for nome, (fita, lances, descricao) in _FITAS_DAS_FIGURAS_NO_AR.items()
    ]


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ AS SEMENTES POR LANCE — o segundo bloco do documento (26/09/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Este bloco nao julga nada**, e por isso ele e uma lista propria em vez de
# mais uns vetores: os `vetores` respondem *"esta resolucao cumpriu?"*, e estes
# respondem *"os dois lados derivam a MESMA semente?"*.
#
# ⛔ **Por que ele existe.** Ate 26/09/2026 o servidor derivava a semente de cada
# lance por SHA-256 e o aplicativo por Knuth — contas diferentes, declaradas
# diferentes de proposito, num tempo em que o servidor jogava com o port Python e
# nao sortearia igual de qualquer jeito. Quando o servidor passou a jogar com o
# **motor do aparelho** (25/09), o sorteador virou o mesmo e a semente ficou sendo
# a unica peca fora do lugar: o gabarito de todo desafio contra Cacau, Pita ou Tex
# deixou de ser reproduzivel, ja no **primeiro lance da CPU**.
#
# O relato do dono, no dia seguinte: *"o lance 2, da CPU, do gabarito esta
# divergindo do que a CPU fez jogando contra mim"*.
#
# ⚠️ **Contra o Magno nada disso aparecia** (`ruido=0`, `chance_de_errar=0`): ele
# nao consulta o sorteador. Foi por isso que o vetor de paridade dos motores, que
# e uma partida contra o Magno, passou sem tocar no defeito.


def sementes_de_verificacao() -> list[dict[str, Any]]:
    """Pares `(semente, lance) -> esperado`, conferidos nos DOIS lados.

    O `esperado` sai da propria conta do Python; o que prova a igualdade e o teste
    Dart (`test/core/jogos/semente_da_partida_test.dart`) ler o **mesmo arquivo** e
    exigir os mesmos numeros de `SementeDaPartida.para`.
    """
    casos: list[dict[str, Any]] = [
        {
            "id": f"semente-do-defeito-de-26-09-lance-{lance}",
            "de_caso": "A semente publicada do desafio 449864e6 (damas_sobreviver "
            "anglo contra a Pita), que foi onde o defeito apareceu. O lance 1 e de "
            "quem resolve; o 2 e o primeiro da CPU, e era o que divergia.",
            "nu_semente": 697571591,
            "nu_lance": lance,
        }
        for lance in (1, 2, 3, 4)
    ]
    casos += [
        {
            "id": "semente-minima-lance-1",
            "de_caso": "O piso da faixa publicavel (`ck006_semente`).",
            "nu_semente": SEMENTE_MINIMA,
            "nu_lance": 1,
        },
        {
            "id": "semente-maxima-lance-1",
            "de_caso": "O teto da faixa: aqui a soma passa de 32 bits, e o que "
            "sobra depende do corte. E o caso em que uma implementacao que usasse "
            "inteiro de tamanho fixo divergiria de uma de inteiro grande.",
            "nu_semente": SEMENTE_MAXIMA,
            "nu_lance": 1,
        },
        {
            "id": "semente-maxima-lance-alto",
            "de_caso": "O mesmo teto num lance longe do inicio — uma partida de "
            "damas publicada chega a 20 meios-lances.",
            "nu_semente": SEMENTE_MAXIMA,
            "nu_lance": 20,
        },
        {
            "id": "semente-que-deriva-ZERO",
            "de_caso": "⚠️ `1640531535 + 2654435761` da exatamente 2^32, e o corte "
            "de 31 bits devolve **zero**. Zero e resposta legitima: `Random(0)` "
            "vale nas duas linguagens. Este caso existe para que ninguem 'conserte' "
            "a conta somando 1 ao resultado, como faz a semente da PARTIDA — que "
            "tem outra faixa, por ter um CHECK no banco.",
            "nu_semente": 1640531535,
            "nu_lance": 1,
        },
    ]

    for caso in casos:
        caso["esperado"] = semente_do_lance(caso["nu_semente"], caso["nu_lance"])

    identificadores = [c["id"] for c in casos]
    assert len(set(identificadores)) == len(identificadores), (
        f"ha identificador de semente repetido: {identificadores}"
    )
    return casos


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
        + vetores_das_damas_de_16_09()
        # ⚠️ No fim, para o diff do dia ser acrescimo (T124b da spec 010).
        + vetores_do_quatro()
        # O Segure e o "venca em ate 7" (T124c), tambem no fim.
        + vetores_do_quatro_de_21_10()
        # A diagonal e as encostadas (T124c, defeito 1), tambem no fim.
        + vetores_do_quatro_perseguidos()
        # O golpe duplo e a linha de cinco (T124c, o banco pescado), no fim.
        + vetores_do_quatro_do_banco()
        # O "sem o meio" (T124c, o piso de 9), no fim.
        + vetores_do_quatro_sem_o_meio()
        # O "Encoste" (T143, o primeiro que fecha no meio), no fim.
        + vetores_do_quatro_encoste()
        # A clausula `figura` (T146), no fim.
        + vetores_da_figura()
        # As figuras no ar (T150), montadas pela receita, no fim.
        + vetores_das_figuras_no_ar()
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
        # ⚠️ Chave nova em 26/09/2026 (versao 2). Ela entra **no fim** para que o
        # diff do dia mostre acrescimo, e nao um arquivo inteiro reordenado.
        "sementes": sementes_de_verificacao(),
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

    print(
        f"{len(documento['vetores'])} vetores e "
        f"{len(documento['sementes'])} sementes, versao {VERSAO}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
