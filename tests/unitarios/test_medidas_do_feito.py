"""🔒 Todo tipo do gerador declara o que a frase de feito dele le (T085za).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE CADEADO GUARDA
═══════════════════════════════════════════════════════════════════════════

O cartao de quem resolveu diz o FEITO da pessoa (*"4 caixas em 2 turnos"*), com
numeros do retrato da resolucao (`tb003_resolucao.js_feito`). O que cada frase le
esta declarado no aplicativo e chega aqui pelo manifesto
`contratos/medidas_do_feito.json`. O dono mandou **obrigar** o gerador a
acompanhar (`DECISOES-do-dono.md` §8z item 13) - e sao tres pontas:

    o aplicativo   `medidas_do_feito_test.dart` - a frase le so o declarado, e o
                   medidor de cada jogo produz cada medida exigida
    ESTE ARQUIVO   todo tipo de `RECEITAS` tem entrada, do mesmo jogo, com a
                   janela que a receita monta (e o tipo FORA DO AR que ja tem
                   entrada tambem); e a trava do job funciona
    o job          `job/medidas_do_feito.py` - ⛔ grava tipo sem entrada

⛔ **Nivel de CI: nunca pula.** Manifesto ausente e FALHA.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from job.figuras_quatro import CHAVE_FIGURA
from job.gravacao import montar_linha
from job.medidas_do_feito import (
    MANIFESTO,
    FraseDoFeitoNaoDeclarada,
    exigir_frase_do_feito,
    frases_declaradas,
)
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "contratos" / "catalogo_feitos.json"
#: A copia do aplicativo - so existe quando os repositorios estao lado a lado.
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "medidas-do-feito.json"
)


def _janela_da_receita(receita) -> str:
    """O tipo de janela que a receita monta.

    ⚠️ `montar` pede os parametros do tipo (`turnos`, `lances`, `caixas`...), e
    cada tipo pede os seus. Um `defaultdict` que devolve 1 para qualquer chave
    serve a todos: o que se le aqui e a FORMA da chegada, e ela ⛔ depende do
    valor.

    ⚠️ **Menos a figura** (`quatro_figura`, T147): o parametro dela e um NOME do
    catalogo, e nao uma contagem - com 1 a receita nao acharia figura nenhuma.
    O quadrado e o controle do catalogo; a forma da chegada nao depende de qual.
    """
    parametros = defaultdict(lambda: 1)
    parametros[CHAVE_FIGURA] = "quadrado"
    chegada = receita.montar(parametros)
    return chegada["janela"]["tipo"]


def test_o_manifesto_existe_e_nao_esta_vazio() -> None:
    """⛔ Falha, ⛔ pula: sem o manifesto a trava do job recusaria tudo."""
    assert MANIFESTO.is_file(), f"o manifesto sumiu: {MANIFESTO}"
    assert len(frases_declaradas()) >= 11


@pytest.mark.parametrize("co_tipo", sorted(RECEITAS))
def test_todo_tipo_do_gerador_tem_frase_declarada(co_tipo: str) -> None:
    """🔒 O tipo que o job publica tem entrada, do MESMO jogo.

    ⚠️ **Este e o caso que o dono pediu**: tipo novo em `RECEITAS` sem entrada
    no manifesto reprova aqui - e a correcao e declarar as medidas no app e
    regerar as duas copias, ⛔ tirar o tipo do teste.
    """
    receita = RECEITAS[co_tipo]
    entrada = frases_declaradas().get(receita.co_chave_objetivo)
    assert entrada is not None, (
        f"{co_tipo}: o objetivo {receita.co_chave_objetivo!r} ⛔ tem frase de "
        "feito declarada. Declare em medidasDoFeitoPorObjetivo (app) e rode "
        "tool/gerar_manifesto_medidas_do_feito.dart."
    )
    assert entrada["co_jogo"] == receita.co_jogo


@pytest.mark.parametrize("co_tipo", sorted(RECEITAS))
def test_a_frase_que_pede_a_janela_tem_janela_para_contar(co_tipo: str) -> None:
    """🔒 *"em 2 turnos"* so existe se a chegada conta turnos (ou lances).

    Com a janela `partida` o aplicativo ⛔ tem o que contar - a frase ficaria
    muda em toda resolucao do tipo, sem erro em lugar nenhum.
    """
    receita = RECEITAS[co_tipo]
    entrada = frases_declaradas()[receita.co_chave_objetivo]
    if entrada["janela_gasta"]:
        assert _janela_da_receita(receita) != "partida", (
            f"{co_tipo}: a frase precisa da janela gasta, e a receita monta a "
            "janela 'partida'."
        )


def test_nenhuma_entrada_sobra_sem_tipo() -> None:
    """Entrada sem tipo no gerador e declaracao morta - e o dia em que o tipo
    voltasse com outra frase, ela mentiria.

    ⚠️ **O tipo FORA DO AR conta como tipo** (T131a da spec 010): os textos do
    Quatro existem desde a 1.4.0 mesmo antes de o tipo passar na regua
    (`DECISOES-do-dono.md` §8zzz), e a frase de feito vai junto, para o tipo
    subir depois sem versao nova do app. Nao e declaracao morta: a receita
    existe, so nao esta em `RECEITAS`.
    """
    chaves_do_gerador = {
        r.co_chave_objetivo
        for r in (*RECEITAS.values(), *RECEITAS_FORA_DO_AR.values())
    }
    sobrando = sorted(set(frases_declaradas()) - chaves_do_gerador)
    assert not sobrando, f"entradas sem tipo no gerador: {sobrando}"


@pytest.mark.parametrize(
    "co_tipo",
    sorted(
        t
        for t, r in RECEITAS_FORA_DO_AR.items()
        if r.co_chave_objetivo in frases_declaradas()
    ),
)
def test_o_tipo_FORA_DO_AR_com_entrada_tem_o_mesmo_jogo_e_janela(co_tipo: str) -> None:
    """🔒 A entrada adiantada de um tipo fora do ar ja obedece as regras do
    tipo no ar: o mesmo jogo, e janela gasta so com janela para contar. Sem
    isso, o defeito apareceria no dia da promocao (T124b), e nao hoje.
    """
    receita = RECEITAS_FORA_DO_AR[co_tipo]
    entrada = frases_declaradas()[receita.co_chave_objetivo]
    assert entrada["co_jogo"] == receita.co_jogo
    if entrada["janela_gasta"]:
        assert _janela_da_receita(receita) != "partida", co_tipo


def test_os_nove_tipos_do_Quatro_com_texto_tem_entrada() -> None:
    """🔒 Os onze do Quatro tem frase de feito (os nove de 20/10, o "Encoste" da
    T144, 22/10/2026, e o "Forme a figura" da T149, 27/10/2026); a unica
    coluna, aposentada (`DECISOES-do-dono.md` §8zzzl), nao tem.

    ⚠️ Sem este caso, o parametrizado acima passaria com ZERO tipos se o
    manifesto perdesse as entradas do Quatro.
    """
    # No ar ou fora dele: a promocao (T124b) move o tipo de um registro para o
    # outro, e o que este caso guarda nao muda com ela.
    todas = {**RECEITAS, **RECEITAS_FORA_DO_AR}
    do_quatro = {t for t, r in todas.items() if r.co_jogo == "quatro"}
    com_entrada = {
        t for t in do_quatro if todas[t].co_chave_objetivo in frases_declaradas()
    }
    # O "Forme a figura" ganhou a frase de feito no app na T149 (27/10/2026),
    # ainda fora do ar: a T150 o promove.
    assert do_quatro - com_entrada == {"quatro_unica_coluna"}
    assert len(com_entrada) == 11


def test_toda_medida_exigida_e_do_catalogo_e_do_TABULEIRO() -> None:
    """🔒 A frase le do retrato, e o retrato so tem medida de tabuleiro.

    ⚠️ E a medida tem de ser do jogo da entrada (ou comum a todos): o medidor
    das damas ⛔ conta caixas.
    """
    catalogo = {
        linha["co_feito"]: linha
        for linha in json.loads(CATALOGO.read_text(encoding="utf-8"))["feitos"]
    }
    for chave, entrada in frases_declaradas().items():
        for medida in entrada["medidas"]:
            assert medida in catalogo, f"{chave}: {medida!r} ⛔ esta no catalogo"
            linha = catalogo[medida]
            assert linha["co_procedencia"] == "tabuleiro", (chave, medida)
            assert linha["co_jogo"] in (None, entrada["co_jogo"]), (chave, medida)


def test_as_duas_copias_sao_identicas_quando_o_app_esta_ao_lado() -> None:
    """A copia daqui e a do aplicativo, byte a byte.

    ⚠️ **O unico caso que pode pular**, e pelo motivo do RF-DES-143a: o CI de
    cada repositorio roda sozinho, sem o outro no disco. Na maquina do dono os
    dois estao lado a lado, e ai a comparacao roda.
    """
    if not COPIA_DO_APP.is_file():
        pytest.skip("o aplicativo ⛔ esta ao lado (CI isolado)")
    assert COPIA_DO_APP.read_bytes() == MANIFESTO.read_bytes(), (
        "as duas copias divergiram - rode tool/gerar_manifesto_medidas_do_feito"
        ".dart no aplicativo, que escreve as duas."
    )


# ═══════════════════════════════════════════════════════════════════════════
# A trava do job
# ═══════════════════════════════════════════════════════════════════════════

_TURNOS = {"janela": {"tipo": "turnos_do_jogador", "n": 3}}


def test_a_trava_aceita_o_tipo_declarado() -> None:
    exigir_frase_do_feito(
        co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
        co_jogo="pontinhos",
        js_chegada=_TURNOS,
    )


def test_a_trava_recusa_o_tipo_NAO_declarado() -> None:
    with pytest.raises(FraseDoFeitoNaoDeclarada, match="medidasDoFeitoPorObjetivo"):
        exigir_frase_do_feito(
            co_chave_objetivo="desafioObjetivoInventado",
            co_jogo="pontinhos",
            js_chegada=_TURNOS,
        )


def test_a_trava_recusa_o_jogo_trocado() -> None:
    with pytest.raises(FraseDoFeitoNaoDeclarada, match="jogo"):
        exigir_frase_do_feito(
            co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
            co_jogo="damas",
            js_chegada=_TURNOS,
        )


def test_a_trava_recusa_a_janela_que_nao_se_conta() -> None:
    with pytest.raises(FraseDoFeitoNaoDeclarada, match="janela"):
        exigir_frase_do_feito(
            co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
            co_jogo="pontinhos",
            js_chegada={"janela": {"tipo": "partida"}},
        )


def test_a_gravacao_PASSA_pela_trava() -> None:
    """🔒 `montar_linha` - o ponto unico em que um candidato vira linha - chama a
    trava. Sem este caso, tirar a chamada deixaria os quatro de cima verdes e o
    job publicando tipo sem frase.
    """
    candidato = SimpleNamespace(
        co_jogo="pontinhos",
        co_modalidade=None,
        co_variante="4x3",
        co_formato_posicao="lances",
        js_posicao_inicial={"lances": []},
        receita=SimpleNamespace(
            nu_tipo_desafio=99, co_chave_objetivo="desafioObjetivoInventado"
        ),
        js_chegada=_TURNOS,
        js_objetivo={},
        co_personagem="tex",
        nu_semente=1,
        js_solucao={},
        nu_lances_solucao=1,
    )
    with pytest.raises(FraseDoFeitoNaoDeclarada):
        montar_linha(
            candidato,
            ic_chegada_encerra_partida=False,
            nu_tempo_piso_ms=1,
            nu_tempo_teto_ms=2,
            co_versao_perfil="p",
            co_versao_motor="m",
            co_versao_minima="1.0.0",
            nu_teto_log=10,
        )
