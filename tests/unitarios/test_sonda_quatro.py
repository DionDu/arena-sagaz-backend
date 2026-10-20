"""A modalidade-sonda atravessa o árbitro do Quatro em Linha (spec 010, T108).

A promessa é que uma variante nova entra por DADO (o contrato) e por uma
classe de regras, sem `if` por modalidade no árbitro (RF-QTR-019/020). Aqui a
sonda (6 × 5, com o `tirar`) entra pelo contrato de teste e pela família de
regras registrada pelos tipos de lance, e:

  - o árbitro responde igual ao motor Dart nas posições da sonda dos vetores
    (as mesmas que o laboratório gerou com a sonda dele);
  - o contrato dela é lido pelo mesmo `contrato_quatro` (dimensões, tipos, os
    três níveis, e o Sagaz recusado: ela não tem o Magno);
  - e o cadeado de fonte: o nome da modalidade de hoje não aparece entre aspas
    em `motores/quatro/` nem em `job/`.
"""

import json
import re
from pathlib import Path

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import contrato_quatro as cq
from motores.quatro.motor_quatro import MotorQuatro
from tests.unitarios.sonda_quatro import (
    RegrasSondaQuatro,
    limpar_o_cache,
    usar_a_sonda,
)

RAIZ = Path(__file__).resolve().parents[2]
VETORES = json.loads(
    (RAIZ / "contratos" / "vetores-paridade-quatro.json").read_text(encoding="utf-8")
)
DA_SONDA = [v for v in VETORES["regras"] if v["modalidade"] == "sonda"]


@pytest.fixture
def sonda(monkeypatch) -> MotorQuatro:
    usar_a_sonda(monkeypatch)
    yield MotorQuatro("sonda")
    limpar_o_cache()


def test_a_sonda_entra_pelo_contrato_e_pela_familia_de_regras(sonda):
    assert isinstance(sonda.regras, RegrasSondaQuatro)
    assert cq.modalidades_declaradas() == ("sonda",)
    d = cq.dimensoes("sonda")
    assert (d.largura, d.altura, d.alinhar) == (6, 5, 4)
    assert dict(cq.tipos_de_lance("sonda")) == {"s": "soltar", "t": "tirar"}


def test_o_contrato_da_sonda_tem_tres_niveis_e_recusa_o_sagaz(sonda):
    assert cq.niveis_disponiveis("sonda") == ("cacau", "pita", "tex")
    assert cq.parametros_do_personagem("sonda", NivelDeMotor.TEX).teto_de_nos == 5000
    with pytest.raises(cq.ContratoQuatroInvalido, match="não oferece"):
        cq.parametros_do_personagem("sonda", NivelDeMotor.SAGAZ)


def test_o_arbitro_da_sonda_responde_igual_ao_motor_dart(sonda):
    assert len(DA_SONDA) >= 100, "as posições da sonda sumiram dos vetores"
    # Os vetores passam pelo `tirar` (senão a sonda não estaria provando nada).
    assert any("t" in v["lances"] for v in DA_SONDA)
    divergencias = []
    for v in DA_SONDA:
        estado = sonda.estado_de_sequencia(v["lances"])
        desfecho = sonda.desfecho(estado)
        obtido = (
            None
            if desfecho is None
            else {
                "vencedor": desfecho.vencedor,
                "linhas": [[list(c) for c in linha] for linha in desfecho.linhas],
            }
        )
        legais = sonda.lances_legais(estado)
        if legais != v["legais"] or obtido != v["desfecho"]:
            divergencias.append(f"{v['lances']!r}: {legais} × {v['legais']}; {obtido} × {v['desfecho']}")
    assert not divergencias, "\n  ".join([f"{len(divergencias)} divergências:"] + divergencias[:5])


def test_tirar_desce_a_coluna_e_so_tira_a_propria_peca(sonda):
    # J1 solta na 1 e o J2 na 1: a de baixo é do J1. O J1 pode tirar; o J2 não.
    estado = sonda.estado_de_sequencia("s1s1")
    assert "t1" in sonda.lances_legais(estado)
    depois = sonda.aplicar(estado, "t1")
    # A peça do J2 desceu para o fundo.
    assert sonda.tabuleiro(depois).colunas[0] == (-1,)
    # Agora a de baixo é do J2, e a vez também: ele pode tirar.
    assert sonda.vez_de(depois) == -1
    assert "t1" in sonda.lances_legais(depois)
    # Com a peça de baixo do OUTRO, não se tira: depois de `s1` a vez é do J2,
    # e a peça do fundo é do J1.
    assert "t1" not in sonda.lances_legais(sonda.estado_de_sequencia("s1"))
    with pytest.raises(ValueError):
        sonda.aplicar(sonda.estado_de_sequencia("s1"), "t1")


# ── O cadeado de fonte ───────────────────────────────────────────────────────

# O nome da modalidade de hoje entre aspas simples ou duplas. ⚠️ O nome é
# montado em duas partes para este arquivo não reprovar a si mesmo se um dia
# entrar na varredura.
_NOME = "tradi" + "cional"
_LITERAL = re.compile(r"""['"]""" + _NOME + r"""['"]""")


def test_o_cadeado_acha_o_literal_quando_ele_existe():
    """O controle: a expressão pega as duas aspas, e não pega a palavra solta."""
    assert _LITERAL.search(f"x = '{_NOME}'")
    assert _LITERAL.search(f'x = "{_NOME}"')
    assert not _LITERAL.search(f"a modalidade {_NOME} tem 7 colunas")


def test_o_nome_da_modalidade_nao_esta_escrito_no_codigo_do_jogo():
    """⛔ Modalidade é DADO (RF-QTR-020): quem escolhe é quem chama, pelo contrato.

    Varre `motores/quatro/` e `job/` inteiros (achados na pasta, e não numa
    lista escrita à mão, que ficaria cega para o arquivo novo).
    """
    achados = []
    for pasta in (RAIZ / "motores" / "quatro", RAIZ / "job"):
        for arquivo in sorted(pasta.rglob("*.py")):
            for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                if _LITERAL.search(linha):
                    achados.append(f"{arquivo.relative_to(RAIZ)}:{n}: {linha.strip()}")
    assert not achados, (
        "o nome da modalidade está escrito no código; leia-o do contrato "
        "(contrato_quatro.modalidades_declaradas()):\n  " + "\n  ".join(achados)
    )


# ═══════════════════════════════════════════════════════════════════════════
# A SONDA CRESCE (fase 4, T113): ela atravessa os feitos e o JUIZ do desafio
# ═══════════════════════════════════════════════════════════════════════════
#
# A sonda entra no juiz pela mesma porta da modalidade de verdade: o
# `co_modalidade` que quem chama passa, o contrato e a família de regras. Se
# fazê-la passar exigisse uma linha em `motores/juiz.py` ou em
# `motores/quatro/feitos_quatro.py` que a citasse, seria o defeito que ela
# existe para achar. E ela tem o que a de verdade não tem: o `tirar` (um lance
# que não ocupa casa nova) e a largura PAR (sem coluna do meio).

from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.medidor_por_fita import CUMPRIU, NAO_CUMPRIU  # noqa: E402
from motores.quatro import feitos_quatro as fq  # noqa: E402
from motores.quatro.motor_quatro import ler_sequencia  # noqa: E402

FITAS_DA_SONDA = [v for v in VETORES["fitas"] if v["modalidade"] == "sonda"]
MEDIDAS_DA_SONDA = [v for v in VETORES["medidas"] if v["modalidade"] == "sonda"]


def test_os_vetores_da_sonda_tem_o_tirar_e_derrotas():
    """Controle: as fitas da sonda trazem o `tirar` e partidas perdidas."""
    assert len(FITAS_DA_SONDA) >= 20 and len(MEDIDAS_DA_SONDA) >= 10
    assert any("t" in v["fita"] for v in FITAS_DA_SONDA)
    assert any(v["quatro_perdeu"] for v in FITAS_DA_SONDA)


def test_os_feitos_da_sonda_batem_com_o_motor_dart(sonda):
    """As medidas da fita, o predicado e as do fim, na sonda."""
    divergencias = []
    for v in FITAS_DA_SONDA:
        iniciais, fita = ler_sequencia(v["lances_iniciais"]), ler_sequencia(v["fita"])
        obtido = fq.medir(sonda, iniciais, fita)
        esperado = {k: v[k] for k in ("lances_do_jogador", "lances_na_coluna_central", "ameacas_bloqueadas")}
        recorte = {k: obtido[k] for k in esperado}
        terminou = sonda.veredito(sonda.estado_de_sequencia(v["lances_iniciais"] + v["fita"])).acabou
        resposta = fq.responder_predicados(sonda, iniciais, fita)["quatro_perdeu"]
        if recorte != esperado or resposta != (v["quatro_perdeu"] if terminou else None):
            divergencias.append(f"{v['lances_iniciais']}|{v['fita']}: {recorte} × {esperado}, {resposta}")
    for v in MEDIDAS_DA_SONDA:
        obtido = fq.medir(sonda, (), ler_sequencia(v["lances"]), jogador=1)
        venceu = v["vencedor"] == 1
        esperado = {
            "pecas_encostadas": v["pecas_encostadas_j1"],
            "pecas_encostadas_do_adversario": v["pecas_encostadas_j2"],
            "maior_linha": v["maior_linha"] if venceu else 0,
            "linhas_no_lance_final": v["linhas_no_lance_final"] if venceu else 0,
        }
        recorte = {k: obtido[k] for k in esperado}
        if recorte != esperado:
            divergencias.append(f"{v['lances']}: {recorte} × {esperado}")
    assert not divergencias, "\n  ".join(divergencias[:5])


def test_a_sonda_atravessa_o_juiz_com_uma_fita_que_tira(sonda):
    """Uma fita da sonda com `tirar`, terminada sem derrota da pessoa, julgada
    pelo "não perca": cumpre no último lance; cortada no meio, não cumpre."""
    v = next(
        f
        for f in FITAS_DA_SONDA
        if "t" in f["fita"]
        and len(ler_sequencia(f["fita"])) >= 3
        and sonda.veredito(sonda.estado_de_sequencia(f["lances_iniciais"] + f["fita"])).acabou
        and not f["quatro_perdeu"]
    )
    vez = sonda.vez_de(sonda.estado_de_sequencia(v["lances_iniciais"]))
    fita = [
        {"n": i, "jogador": vez if i % 2 == 1 else -vez, "lance": lance}
        for i, lance in enumerate(ler_sequencia(v["fita"]), start=1)
    ]
    chegada = {
        "versao": 1,
        "janela": {"tipo": "partida"},
        "clausulas": [
            {"tipo": "predicado", "chave": "quatro_perdeu", "comparador": "igual", "valor": False}
        ],
    }
    args = dict(
        co_jogo="quatro",
        js_posicao_inicial=sonda.para_dado(sonda.estado_de_sequencia(v["lances_iniciais"])),
        js_chegada=chegada,
        jogador=vez,
        co_modalidade="sonda",
    )
    inteira = julgar_desafio(fita=fita, **args)
    assert inteira.veredito == CUMPRIU
    assert inteira.nu_lance_cumpre_desafio == len(fita)
    # A largura par: nenhum lance conta como coluna do meio.
    assert inteira.feitos["lances_na_coluna_central"] == 0
    assert julgar_desafio(fita=fita[:2], **args).veredito == NAO_CUMPRIU
