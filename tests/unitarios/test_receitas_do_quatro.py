"""Os dez tipos do Quatro em Linha no job (T115 da spec 010).

Nasceram todos fora do ar: as receitas em `job/tipos_de_desafio.RECEITAS_FORA_DO_AR`
e os numeros em `job/editorial.EDITORIAL_FORA_DO_AR`. ⚠️ **Desde a T124b um deles
esta no ar** (a `quatro_virada`, em `RECEITAS`/`EDITORIAL`), e por isso os casos
leem [RECEITAS_DO_QUATRO] e [EDITORIAL_DO_QUATRO], que juntam os dois lados: os
cadeados valem para o tipo onde quer que ele more, e a promocao de outro tipo nao
os desliga. Este arquivo aplica a eles os mesmos cadeados que os tipos no ar
recebem nos outros testes - a chegada valida, so o vocabulario fechado, ninguem
cumpre sem jogar, os pesos fechando em 1,000 - e mais os que sao so deles:

- os dez batem com a dimensao que a migracao `0035` grava (numero e codigo);
- cada clausula consulta uma medida que o medidor do Quatro PRODUZ, e cada
  predicado um que ele RESPONDE (senao o juiz recusaria a tentativa);
- com fitas reais (os vetores do motor Dart, T106), cada tipo tem partida que
  cumpre e partida que nao cumpre, e o juiz concorda com a leitura direta.

⚠️ **Por que o juiz roda so em UMA fita por tipo.** `julgar_desafio` reproduz a
partida a cada lance (para achar o lance em que o objetivo caiu), e passar as
198 fitas pelos onze tipos levaria minutos. A leitura direta - medir a fita
inteira uma vez e avaliar a chegada - e o que roda em todas; o juiz confere que
essa leitura e a dele.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from job import editorial as editorial_mod
from job.editorial import (
    EDITORIAL,
    EDITORIAL_FORA_DO_AR,
    ENCOSTADAS_NA_POSICAO,
    ENCOSTADAS_PARA_NOTA_CHEIA,
    VERSAO_MINIMA_DO_QUATRO,
    parametros_efetivos,
    parametros_para_conferencia,
)
from job.medidas_de_saida import FAIXA, conferir
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.juiz import julgar_desafio
from motores.nucleo.chegada import JANELAS, LinhaDeChegada, avaliar
from motores.nucleo.medidor_por_fita import CUMPRIU, NAO_CUMPRIU
from motores.quatro import contrato_quatro as cq
from motores.quatro import feitos_quatro as fq
from motores.quatro.motor_quatro import MotorQuatro, ler_sequencia

RAIZ = Path(__file__).resolve().parents[2]
MIGRACAO = RAIZ / "migrations" / "versions" / "0035_desafio_quatro.py"
VETORES = json.loads(
    (RAIZ / "contratos" / "vetores-paridade-quatro.json").read_text(encoding="utf-8")
)

#: A primeira modalidade do contrato (hoje a de 7 x 6). ⚠️ Lida do contrato, e
#: nao escrita aqui: o cadeado da T108 recusa o nome dela entre aspas no job, e
#: o teste segue a mesma disciplina.
MODALIDADE = cq.modalidades_declaradas()[0]

#: As receitas do Quatro, no ar ou fora dele (a promocao MOVE de um para o outro).
RECEITAS_DO_QUATRO = {
    co_tipo: receita
    for co_tipo, receita in {**RECEITAS, **RECEITAS_FORA_DO_AR}.items()
    if receita.co_jogo == "quatro"
}

#: Os numeros de cada uma, do mesmo lado em que a receita mora.
EDITORIAL_DO_QUATRO = {
    co_tipo: (EDITORIAL if co_tipo in RECEITAS else EDITORIAL_FORA_DO_AR)[co_tipo]
    for co_tipo in RECEITAS_DO_QUATRO
}

#: Todas as variantes, achatadas, para os casos parametrizados.
VARIANTES = [
    (co_tipo, publicacao)
    for co_tipo, publicacoes in EDITORIAL_DO_QUATRO.items()
    for publicacao in publicacoes
]


def _id(valor) -> str:
    """O nome legivel de cada caso no relatorio do pytest."""
    if isinstance(valor, str):
        return valor
    return str(dict(getattr(valor, "parametros", {})))


@pytest.fixture(scope="module")
def motor() -> MotorQuatro:
    return MotorQuatro(MODALIDADE)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os dez, e onde eles NAO estao
# ═══════════════════════════════════════════════════════════════════════════


def test_os_dez_tipos_batem_com_a_dimensao_da_0035() -> None:
    """🔒 O numero e o codigo de cada receita sao os que a migracao grava.

    ⚠️ Um numero trocado nao daria erro na geracao: o desafio sairia gravado com
    o tipo de outro, e a curadoria e o rodizio o contariam errado.
    """
    # As linhas da migracao tem a forma `(  40, 'quatro_vencer_em_n', ...`.
    na_migracao = {
        codigo: int(numero)
        for numero, codigo in re.findall(
            r"\(\s*(\d+),\s*'(quatro_\w+)'", MIGRACAO.read_text(encoding="utf-8")
        )
    }
    assert len(na_migracao) == 10
    nas_receitas = {
        codigo: receita.nu_tipo_desafio for codigo, receita in RECEITAS_DO_QUATRO.items()
    }
    assert nas_receitas == na_migracao
    for codigo, receita in RECEITAS_DO_QUATRO.items():
        assert receita.co_tipo_desafio == codigo
        assert receita.co_jogo == "quatro"


def test_cada_tipo_do_quatro_mora_de_UM_lado_so() -> None:
    """⛔ No ar quer dizer `RECEITAS` E `EDITORIAL`; fora, os dois de fora.

    ⚠️ **Promover e MOVER.** No dia em que um tipo vai ao ar ele sai dos dois
    dicionarios de fora e entra nos dois de dentro, na mesma resposta; uma
    receita nos dois lados seria duas fontes da verdade para a mesma regra. E
    entrar em `RECEITAS` antes do vetor e da frase seria publicar um tipo que o
    aplicativo pode julgar diferente, calado (`test_todo_tipo_com_receita_TEM_vetor`).
    """
    assert not set(RECEITAS_FORA_DO_AR) & set(RECEITAS)
    assert not set(EDITORIAL_FORA_DO_AR) & set(EDITORIAL)
    assert set(EDITORIAL_FORA_DO_AR) == set(RECEITAS_FORA_DO_AR)
    no_ar = {t for t in RECEITAS_DO_QUATRO if t in RECEITAS}
    assert no_ar <= set(EDITORIAL)
    # ⚠️ O retrato de hoje: a virada (T124b, `DECISOES-do-dono.md` §8zzzl), e o
    # *"venca em ate 7"* e o Segure, que passaram na remedicao de 21/10 (T124c),
    # e a diagonal e as encostadas, que passaram com o perseguidor do objetivo
    # (T124c, defeito 1). Promover outro tipo e atualizar este conjunto na mesma
    # resposta.
    assert no_ar == {
        "quatro_virada",
        "quatro_vencer_em_n",
        "quatro_segurar_magno",
        "quatro_vencer_diagonal",
        "quatro_encostadas",
    }
    assert "quatro_unica_coluna" in RECEITAS_FORA_DO_AR, "aposentada, e nao apagada"


def test_a_chave_do_objetivo_e_uma_chave_do_quatro_e_nunca_a_frase() -> None:
    """A chave `.arb` do enunciado (a T131 a cria nos tres idiomas)."""
    chaves = [r.co_chave_objetivo for r in RECEITAS_DO_QUATRO.values()]
    assert len(set(chaves)) == 10, "duas receitas com a mesma chave de frase"
    for chave in chaves:
        assert " " not in chave
        assert chave.startswith("desafioObjetivoQuatro"), chave


# ═══════════════════════════════════════════════════════════════════════════
# 2. A chegada: valida, so o vocabulario de hoje, e julgavel pelo Quatro
# ═══════════════════════════════════════════════════════════════════════════


def _medidas_e_predicados_do_quatro(motor: MotorQuatro) -> tuple[set, set]:
    """As chaves que o medidor do Quatro produz e os predicados que responde.

    Lidas de uma chamada de verdade, e nao de uma lista escrita aqui: uma lista
    a mao concordaria com a receita e discordaria do medidor no mesmo dia.
    """
    v = next(v for v in VETORES["fitas"] if v["modalidade"] == MODALIDADE)
    iniciais, fita = ler_sequencia(v["lances_iniciais"]), ler_sequencia(v["fita"])
    medidas = fq.medir(motor, iniciais, fita)
    predicados = fq.responder_predicados(motor, iniciais, fita)
    return set(medidas), set(predicados)


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_a_chegada_e_valida_e_usa_so_o_que_o_quatro_mede(
    co_tipo, publicacao, motor
) -> None:
    """🔒 O avaliador aceita a chegada, e o juiz do Quatro sabe responde-la.

    ⚠️ Chave que o medidor nao produz e `ChegadaInvalida` na hora de julgar - a
    tentativa de todo mundo viraria dado invalido, e o defeito so apareceria
    depois do primeiro desafio publicado.
    """
    parametros = parametros_para_conferencia(publicacao.parametros)
    chegada = LinhaDeChegada.de_dado(RECEITAS_DO_QUATRO[co_tipo].montar(parametros))
    assert chegada.clausulas
    assert chegada.janela.tipo in JANELAS

    medidas, predicados = _medidas_e_predicados_do_quatro(motor)
    for clausula in chegada.clausulas:
        disponiveis = medidas if clausula.tipo == "medida" else predicados
        assert clausula.chave in disponiveis, (co_tipo, clausula.chave)

    # A frase monta, e recebe o personagem.
    valores = RECEITAS_DO_QUATRO[co_tipo].valores_da_frase(parametros, "pita")
    assert valores["personagem"] == "pita"


#: As medidas de quem ainda nao jogou, no Quatro: nada aconteceu, e as pecas
#: encostadas sao as da posicao publicada.
#:
#: ⚠️ `pecas_encostadas` vale o MESMO `E` que a conferencia usa: com outro numero
#: o caso compararia duas posicoes que nao existem juntas (a ressalva do
#: `MATERIAL_DE_EXEMPLO` no editorial).
MEDIDAS_DE_QUEM_NAO_JOGOU = {
    "vitoria": 0,
    "empate": 0,
    "lances_do_jogador": 0,
    "pecas_encostadas": editorial_mod.ENCOSTADAS_DE_EXEMPLO,
    "pecas_encostadas_do_adversario": editorial_mod.ENCOSTADAS_DE_EXEMPLO,
    "vitoria_diagonal": 0,
    "linhas_no_lance_final": 0,
    "maior_linha": 0,
    "lances_na_coluna_central": 0,
    "ameacas_bloqueadas": 0,
}


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_ninguem_cumpre_sem_jogar(co_tipo, publicacao) -> None:
    """⛔ A chegada nao vale antes do primeiro lance.

    ⚠️ O caso que importa e o `quatro_sem_o_meio`: `lances_na_coluna_central <= 0`
    ja vale no inicio, e quem o segura e a `vitoria`. E os de "nao perca", em que
    quem segura e o predicado `None` antes do fim.
    """
    parametros = parametros_para_conferencia(publicacao.parametros)
    chegada = LinhaDeChegada.de_dado(RECEITAS_DO_QUATRO[co_tipo].montar(parametros))
    assert not avaliar(chegada, MEDIDAS_DE_QUEM_NAO_JOGOU, {"quatro_perdeu": None})


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_a_chegada_so_vale_com_a_partida_terminada(co_tipo, publicacao) -> None:
    """🔒 Os dez tem `ic_chegada_encerra_partida` TRUE, e a razao esta na chegada.

    Toda chegada consulta `vitoria` ou o predicado `quatro_perdeu`, e os dois so
    respondem no fim. ⚠️ Se um tipo novo do Quatro vier sem nenhum dos dois, o
    valor TRUE digitado no editorial passa a mentir, e este caso cai.
    """
    assert publicacao.ic_chegada_encerra_partida is True
    js = RECEITAS_DO_QUATRO[co_tipo].montar(
        parametros_para_conferencia(publicacao.parametros)
    )
    chaves = {c["chave"] for c in js["clausulas"]}
    assert chaves & {"vitoria", "quatro_perdeu"}, co_tipo


# ═══════════════════════════════════════════════════════════════════════════
# 3. O editorial: versao, personagem, faixa do hub e medidas de saida
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_todos_saem_na_versao_que_traz_o_jogo(co_tipo, publicacao) -> None:
    """⚠️ A 1.4.0 (R-22). Um tipo do Quatro na 1.3.0 chegaria a quem nao tem o
    jogo, e a pessoa veria uma chave crua em vez da tela de atualizar."""
    assert VERSAO_MINIMA_DO_QUATRO == "1.4.0"
    assert publicacao.co_versao_minima == VERSAO_MINIMA_DO_QUATRO


def test_segurar_o_magno_e_so_contra_o_magno() -> None:
    """O nome do tipo e a restricao: no rodizio dos quatro ele mentiria."""
    for publicacao in EDITORIAL_DO_QUATRO["quatro_segurar_magno"]:
        assert publicacao.co_personagens == ("magno",)
    outros = [
        p
        for co_tipo, publicacoes in EDITORIAL_DO_QUATRO.items()
        if co_tipo != "quatro_segurar_magno"
        for p in publicacoes
    ]
    assert all(p.co_personagens is None for p in outros)


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_a_faixa_do_hub_cabe_na_frase(co_tipo, publicacao) -> None:
    """🔒 O piso nunca passa do teto, nem da janela que a frase promete.

    ⚠️ No `quatro_vencer_em_n` a frase e um teto de lances DO JOGADOR: com a
    alternancia estrita, *"em ate N"* cabe em `2N - 1` meios-lances. Um N que nao
    alcanca o piso nunca geraria candidato, e o log diria so *"sem candidato"*.
    """
    piso = publicacao.nu_minimo_de_meios_lances
    assert piso == editorial_mod.MINIMO_DE_MEIOS_LANCES_PADRAO, (
        "o Quatro alterna como as damas e herda a faixa do hub"
    )
    assert piso <= publicacao.nu_maximo_de_meios_lances
    if "lances" in publicacao.parametros:
        assert 2 * publicacao.parametros["lances"] - 1 >= piso, publicacao.parametros


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_as_medidas_de_saida_fecham_e_as_encostadas_mandam(co_tipo, publicacao) -> None:
    """🔒 Contrato §4: `pecas_encostadas` em faixa e com o peso maior; o resto
    so medida, menos a economia de lances no `vencer_em_n`.
    """
    parametros = parametros_para_conferencia(publicacao.parametros)
    linhas = publicacao.medidas(parametros)
    conferir(linhas)  # pesos em 1,000, chaves no catalogo, ordem sem repetir

    por_chave = {linha["co_feito"]: linha for linha in linhas}
    encostadas = por_chave["pecas_encostadas"]
    assert encostadas["co_normalizacao"] == FAIXA
    assert encostadas["vr_peso"] == max(l["vr_peso"] for l in linhas)
    # A faixa parte do que ja estava encostado na posicao, e nao de zero.
    assert encostadas["vr_min"] == parametros[ENCOSTADAS_NA_POSICAO]

    # A do adversario e sempre medida e nunca pontua.
    assert por_chave["pecas_encostadas_do_adversario"]["vr_peso"] == 0

    pontuam = {l["co_feito"] for l in linhas if l["vr_peso"] > 0}
    if co_tipo == "quatro_vencer_em_n":
        assert pontuam == {"pecas_encostadas", "lances_do_jogador"}
    else:
        assert pontuam == {"pecas_encostadas"}, co_tipo


def test_o_criterio_de_cada_tipo_aparece_com_peso_zero() -> None:
    """O Raio-X mostra a medida que decidiu o desafio, e ela nao pontua."""
    criterios = {
        "quatro_vencer_diagonal": "vitoria_diagonal",
        "quatro_golpe_duplo": "linhas_no_lance_final",
        "quatro_linha_de_cinco": "maior_linha",
        "quatro_sem_o_meio": "lances_na_coluna_central",
        "quatro_bloquear": "ameacas_bloqueadas",
    }
    for co_tipo, chave in criterios.items():
        publicacao = EDITORIAL_DO_QUATRO[co_tipo][0]
        linhas = publicacao.medidas(parametros_para_conferencia(publicacao.parametros))
        linha = next(l for l in linhas if l["co_feito"] == chave)
        assert linha["vr_peso"] == 0, co_tipo


def test_o_topo_da_faixa_e_o_alvo_no_encostadas_e_E_mais_a_folga_nos_outros() -> None:
    publicacao = EDITORIAL_DO_QUATRO["quatro_encostadas"][0]
    p = parametros_efetivos(publicacao.parametros, encostadas=6)
    faixa = publicacao.medidas(p)[0]
    assert (faixa["vr_min"], faixa["vr_max"]) == (6, p["pecas"])

    publicacao = EDITORIAL_DO_QUATRO["quatro_virada"][0]
    faixa = publicacao.medidas(parametros_efetivos(publicacao.parametros, encostadas=6))[0]
    assert (faixa["vr_min"], faixa["vr_max"]) == (6, 6 + ENCOSTADAS_PARA_NOTA_CHEIA)


# ═══════════════════════════════════════════════════════════════════════════
# 4. O alvo relativo das encostadas
# ═══════════════════════════════════════════════════════════════════════════


def test_o_alvo_das_encostadas_e_o_da_posicao_mais_o_a_mais() -> None:
    p = parametros_efetivos({"a_mais": 3}, encostadas=5)
    assert p["pecas"] == 8
    assert p[ENCOSTADAS_NA_POSICAO] == 5
    # O relativo continua ao lado do absoluto, como no material das damas.
    assert p["a_mais"] == 3


def test_o_alvo_relativo_sem_a_posicao_falha_alto() -> None:
    with pytest.raises(TypeError, match="encostadas"):
        parametros_efetivos({"a_mais": 3})


def test_zero_a_mais_e_recusado() -> None:
    """⛔ Seria "venca com as encostadas que voce ja tem": cumprido de saida."""
    with pytest.raises(ValueError):
        parametros_efetivos({"a_mais": 0}, encostadas=5)


def test_as_variantes_dos_outros_jogos_nao_mudam() -> None:
    """⚠️ A porta nova nao toca os outros jogos: sem `encostadas`, a saida e a
    de sempre (o Pontinhos e as damas nunca a passam)."""
    fixos = {"caixas": 4, "turnos": 2}
    assert parametros_efetivos(fixos) == fixos
    assert ENCOSTADAS_NA_POSICAO not in parametros_efetivos(
        {"capturar": 3}, material=(8, 8)
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Com partidas de verdade: cada tipo cumpre e deixa de cumprir
# ═══════════════════════════════════════════════════════════════════════════


def _casos_reais(motor: MotorQuatro) -> list[dict]:
    """Posicao + fita das partidas dos vetores do motor Dart (T106).

    As 198 fitas da familia `fitas`, e mais as partidas terminadas com linha de
    cinco da familia `medidas` - nenhuma fita a tem, e sem elas o
    `quatro_linha_de_cinco` nunca seria visto cumprido. Dessas, a posicao e a
    partida sem os tres ultimos lances: o ultimo e do vencedor, entao ele tem a
    vez no corte.
    """
    casos = []
    for v in VETORES["fitas"]:
        if v["modalidade"] == MODALIDADE:
            casos.append((ler_sequencia(v["lances_iniciais"]), ler_sequencia(v["fita"])))
    for v in VETORES["medidas"]:
        if v["modalidade"] == MODALIDADE and v["maior_linha"] >= 5:
            lances = ler_sequencia(v["lances"])
            casos.append((lances[:-3], lances[-3:]))

    saida = []
    for iniciais, fita in casos:
        estado = motor.estado_de_sequencia("".join(iniciais))
        vez = motor.vez_de(estado)
        saida.append(
            {
                "iniciais": iniciais,
                "fita": fita,
                "vez": vez,
                "posicao": motor.para_dado(estado),
                "encostadas": fq.pecas_encostadas(
                    motor.regras.dimensoes, motor.tabuleiro(estado), vez
                ),
                "medidas": fq.medir(motor, iniciais, fita),
                "predicados": fq.responder_predicados(motor, iniciais, fita),
            }
        )
    return saida


@pytest.fixture(scope="module")
def casos_reais(motor) -> list[dict]:
    return _casos_reais(motor)


@pytest.mark.parametrize(("co_tipo", "publicacao"), VARIANTES, ids=_id)
def test_cada_tipo_cumpre_numa_partida_real_e_nao_cumpre_noutra(
    co_tipo, publicacao, motor, casos_reais
) -> None:
    """🔒 A chegada separa partidas reais, e o juiz concorda com a leitura direta.

    ⚠️ Uma chegada que nenhuma partida cumpre (ou que todas cumprem) passaria em
    todos os cadeados de forma acima: e valida, e julgavel, e mesmo assim nao
    distingue ninguem. Aqui ela e posta contra partidas jogadas pelo motor.
    """
    receita = RECEITAS_DO_QUATRO[co_tipo]
    cumprem, nao_cumprem = [], []
    for caso in casos_reais:
        parametros = parametros_efetivos(
            publicacao.parametros, encostadas=caso["encostadas"]
        )
        chegada = LinhaDeChegada.de_dado(receita.montar(parametros))
        if avaliar(chegada, caso["medidas"], caso["predicados"]):
            cumprem.append((caso, parametros))
        else:
            nao_cumprem.append((caso, parametros))
    assert cumprem, f"{co_tipo}: nenhuma partida real cumpre"
    assert nao_cumprem, f"{co_tipo}: toda partida real cumpre"

    # O juiz de verdade, numa de cada lado (ver o cabecalho: ele e caro).
    for (caso, parametros), esperado in ((cumprem[0], CUMPRIU), (nao_cumprem[0], NAO_CUMPRIU)):
        fita = [
            {"n": i, "jogador": caso["vez"] if i % 2 == 1 else -caso["vez"], "lance": lance}
            for i, lance in enumerate(caso["fita"], start=1)
        ]
        julgamento = julgar_desafio(
            co_jogo="quatro",
            js_posicao_inicial=caso["posicao"],
            js_chegada=receita.montar(parametros),
            fita=fita,
            jogador=caso["vez"],
            co_modalidade=MODALIDADE,
        )
        assert julgamento.veredito == esperado, (co_tipo, caso["fita"])
        if esperado == CUMPRIU:
            # Todas as chegadas do Quatro so valem no fim: o objetivo cai no
            # ultimo lance da fita, e nunca antes.
            assert julgamento.nu_lance_cumpre_desafio == len(fita), co_tipo
