"""O AVALIADOR DE RESOLUCOES — T043a (RF-DES-035/036, SC-013).

⚠️ **Os casos usam os MESMOS vetores de verificacao** de T027
(`contratos/vetores-verificacao-desafio.json`), e isso e de proposito: a
auditoria nao tem regra propria — ela e o arbitro aplicado a uma fita que chegou
de fora. Escrever fitas novas aqui criaria uma segunda nocao de "cumpriu".

O que estes casos protegem:

  · ⛔ **divergencia nao corrige nada** — o `UPDATE` toca duas colunas, e `nu_xp`
    nao e uma delas;
  · **lance ilegal e dado invalido, e vira divergencia**, nunca "nao cumpriu";
  · **defeito do DESAFIO nao vira divergencia da pessoa** — seria acusa-la do
    erro de outro, e ainda apagaria o rastro do desafio quebrado;
  · **uma resolucao torta nao derruba o lote**;
  · ⛔ **"validar nao e jogar"**: nao ha caminho daqui ate `escolher_lance`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from uuid import uuid4

import pytest

from job import auditoria
from job.auditoria import (
    CONFERE,
    DIVERGENTE,
    PENDENTE,
    AuditoriaImpossivel,
    Veredito,
    auditar,
    auditar_lote,
    fita_do_log,
)
from tests.unitarios.fakes_desafio import FakeSessaoSQL

RAIZ = Path(__file__).resolve().parents[2]
VETORES = json.loads(
    (RAIZ / "contratos" / "vetores-verificacao-desafio.json").read_text(
        encoding="utf-8"
    )
)["vetores"]

POR_ID = {v["id"]: v for v in VETORES}


def _linha_do_vetor(vetor: dict, *, nu_lance: int | None = None) -> dict:
    """Uma linha de `SQL_PENDENTES` montada a partir de um vetor."""
    return {
        "id_resolucao": uuid4(),
        "id_desafio_dia": uuid4(),
        "id_usuario": "uid-1",
        "id_tentativa": uuid4(),
        "id_partida": uuid4(),
        "nu_lance_cumpre_desafio": (
            nu_lance
            if nu_lance is not None
            else vetor.get("nu_lance_cumpre_desafio") or 1
        ),
        "nu_xp": 26,
        "id_desafio": uuid4(),
        "co_jogo": vetor["co_jogo"],
        "co_modalidade": vetor.get("co_modalidade"),
        "js_posicao_inicial": vetor["js_posicao_inicial"],
        "js_chegada": vetor["js_chegada"],
    }


def _fita(vetor: dict) -> list[dict]:
    """A fita do vetor, ja no vocabulario do juiz."""
    return list(vetor["lances"])


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os tres desfechos do arbitro
# ═══════════════════════════════════════════════════════════════════════════


def test_a_resolucao_que_cumpre_o_objetivo_CONFERE():
    """O caminho feliz, sobre o vetor da escada do Pontinhos."""
    vetor = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    fita = _fita(vetor)

    veredito = auditar(
        linha=_linha_do_vetor(vetor, nu_lance=len(fita)), fita=fita
    )

    assert veredito.co_auditoria == CONFERE
    assert veredito.de_auditoria is None


def test_objetivo_que_nao_caiu_vira_DIVERGENTE_e_nada_mais():
    """⛔ **Divergencia nao corrige nada** (RF-DES-032, D-05): vale o aplicativo.

    A pessoa continua no quadro e o XP dela nao muda. Esta linha existe para ser
    **investigada** — um recalculo pode ter bug proprio, e punir com base nele
    tiraria XP de gente honesta na primeira versao errada do arbitro.
    """
    vetor = POR_ID["P1-escada-fecha-3-nao-cumpre-por-pouco"]

    veredito = auditar(linha=_linha_do_vetor(vetor), fita=_fita(vetor))

    assert veredito.co_auditoria == DIVERGENTE
    assert "objetivo NAO caiu" in veredito.de_auditoria
    # ⛔ E a mensagem diz, para quem ler o painel, que o XP ficou intacto.
    assert "XP nao foi mexido" in veredito.de_auditoria


def test_lance_ilegal_e_DADO_INVALIDO_e_nao_derrota():
    """⛔ A distincao nao e formal (D-05).

    Uma sincronizacao com defeito, um aplicativo adulterado ou um bug de gravacao
    produzem fita irreproduzivel — e tratar isso como tentativa fracassada
    esconderia o defeito atras de milhares de derrotas legitimas.
    """
    vetor = POR_ID["D6-lance-ilegal-e-dado-invalido"]

    veredito = auditar(linha=_linha_do_vetor(vetor), fita=_fita(vetor))

    assert veredito.co_auditoria == DIVERGENTE
    assert "irreproduzivel" in veredito.de_auditoria


def test_traco_repetido_tambem_e_fita_irreproduzivel():
    """O mesmo, pelo lado do Pontinhos."""
    vetor = POR_ID["P1-lance-repetido-e-dado-invalido"]

    veredito = auditar(linha=_linha_do_vetor(vetor), fita=_fita(vetor))

    assert veredito.co_auditoria == DIVERGENTE
    assert "irreproduzivel" in veredito.de_auditoria


def test_o_lance_que_cumpriu_tambem_se_confere():
    """⚠️ E a coluna que o Raio-X usa para abrir o replay no ponto certo.

    Errada, o replay abre num lance qualquer — e **ninguem notaria**, porque a
    tela funcionaria do mesmo jeito.
    """
    vetor = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]

    veredito = auditar(
        linha=_linha_do_vetor(vetor, nu_lance=99), fita=_fita(vetor)
    )

    assert veredito.co_auditoria == DIVERGENTE
    assert "e a resolucao diz 99" in veredito.de_auditoria


def test_fita_vazia_e_divergencia_de_DADO():
    """⚠️ Resolucao sem lance nenhum: ou a partida chegou vazia, ou o
    `id_partida` aponta para o lugar errado. Os dois sao divergencia de dado."""
    vetor = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]

    veredito = auditar(linha=_linha_do_vetor(vetor), fita=[])

    assert veredito.co_auditoria == DIVERGENTE
    assert "nenhuma jogada" in veredito.de_auditoria


# ═══════════════════════════════════════════════════════════════════════════
# 2. ⚠️ Defeito do DESAFIO nao vira divergencia da pessoa
# ═══════════════════════════════════════════════════════════════════════════


def test_chegada_malformada_e_AUDITORIA_IMPOSSIVEL():
    """⚠️ Nao ha o que comparar: o defeito e do que foi publicado.

    Marcar a pessoa como divergente seria acusa-la do erro de outro — e ainda
    apagaria o rastro de que ha um desafio quebrado no ar.
    """
    vetor = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    linha = _linha_do_vetor(vetor)
    linha["js_chegada"] = {"versao": 1, "janela": {"tipo": "nao_existe", "n": 2},
                           "clausulas": []}

    with pytest.raises(AuditoriaImpossivel):
        auditar(linha=linha, fita=_fita(vetor))


def test_jogo_sem_medidor_e_AUDITORIA_IMPOSSIVEL():
    """⚠️ Jogo novo sem medidor devolveria "nao cumpriu" para todo mundo.

    Um desafio impossivel, sem erro nenhum no log — e por isso o juiz falha
    alto, e por isso isto **nao** vira divergencia.
    """
    vetor = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    linha = _linha_do_vetor(vetor)
    linha["co_jogo"] = "xadrez"

    with pytest.raises(AuditoriaImpossivel):
        auditar(linha=linha, fita=_fita(vetor))


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ Validar nao e jogar (RF-DES-035)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_auditoria_nao_tem_caminho_ate_escolher_lance():
    """⛔ **Estrutural, e nao promessa.**

    A separacao de papeis de T004 e o que torna RF-DES-035 impossivel de burlar:
    este modulo so importa `julgar_desafio`, que so enxerga o arbitro. ⛔ Nao ha
    caminho daqui ate `escolher_lance` — nao por disciplina, por importacao.
    """
    # ⚠️ **Lido com `ast`, e nao com `in fonte`** — e a licao que este projeto
    # ja pagou CINCO vezes, e a quinta foi aqui, escrevendo este proprio teste:
    # a docstring do modulo **menciona** `escolher_lance` justamente para dizer
    # que nao o chama, e um cadeado que le texto cru reprovou o codigo correto.
    #
    # Sempre a mesma especie de defeito: **o cadeado confundiu o que o modulo diz
    # com o que ele faz**. Ver a docstring de `leitura_de_migracao.py`, que
    # guarda os quatro anteriores.
    arvore = ast.parse(
        Path(auditoria.__file__).read_text(encoding="utf-8"),
        filename=auditoria.__file__,
    )

    importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
            importados.update(f"{no.module}.{a.name}" for a in no.names)

    chamados = {
        no.func.attr
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    } | {
        no.func.id
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }

    # ⛔ Nenhum motor de jogo importado direto: so o juiz, que so ve o arbitro.
    proibidos = [
        m for m in importados
        if "motor_pontinhos" in m or "motor_damas" in m or m.endswith("MotorDamas")
        or m.endswith("MotorPontinhos")
    ]
    assert not proibidos, f"a auditoria importa motor direto: {proibidos}"

    # ⛔ E nao CHAMA nada que escolha lance.
    assert "escolher_lance" not in chamados

    # ⚠️ O unico ponto de contato com os motores e o juiz.
    assert "motores.juiz.julgar_desafio" in importados


def test_o_update_toca_apenas_duas_colunas():
    """⛔ `nu_xp` nao aparece no `UPDATE`, e essa ausencia e o requisito.

    ⚠️ E o `WHERE co_auditoria = 'pendente'` deixa a rotina segura contra duas
    execucoes simultaneas: a segunda nao reescreve o que a primeira concluiu.
    """
    assert "nu_xp" not in auditoria.SQL_MARCAR
    assert "co_auditoria = :co_auditoria" in auditoria.SQL_MARCAR
    assert "de_auditoria = :de_auditoria" in auditoria.SQL_MARCAR
    assert f"co_auditoria = '{PENDENTE}'" in auditoria.SQL_MARCAR


# ═══════════════════════════════════════════════════════════════════════════
# 4. A fita, lida do log
# ═══════════════════════════════════════════════════════════════════════════


def test_a_fita_traduz_1_2_para_mais_e_menos_um():
    """⚠️ Duas convencoes, **de proposito**.

    O generico usa `nu_jogador` 1/2; a extensao usa o sinal +1/-1, e o `CHECK` da
    migracao `0012` impede que uma vire a outra por descuido. A traducao acontece
    num lugar so.
    """
    fita = fita_do_log(
        [
            {"nu_ordem": 1, "nu_jogador": 1, "co_lance": "H_0_1"},
            {"nu_ordem": 2, "nu_jogador": 2, "co_lance": "V_1_0"},
        ]
    )
    assert [linha["jogador"] for linha in fita] == [1, -1]
    assert [linha["n"] for linha in fita] == [1, 2]


def test_a_fita_une_a_coluna_dos_dois_jogos():
    """⚠️ `co_aresta` no Pontinhos e `co_lance` nas damas — o `COALESCE` as une.

    Os `LEFT JOIN` sao obrigatorios: uma jogada sem extensao precisa chegar como
    `NULL` para o julgamento acusar dado invalido, em vez de **sumir da fita**.
    """
    assert "COALESCE(p.co_aresta, dm.co_lance)" in auditoria.SQL_FITA
    assert "LEFT JOIN jogo_pontinhos" in auditoria.SQL_FITA
    assert "LEFT JOIN jogo_damas" in auditoria.SQL_FITA
    # ⛔ A ordem e por `nu_ordem`: sequencia continua que nunca recua nem repete.
    assert "ORDER BY j.nu_ordem ASC" in auditoria.SQL_FITA


# ═══════════════════════════════════════════════════════════════════════════
# 5. O lote
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_o_lote_conta_os_TRES_desfechos():
    """⚠️ "Auditei 200" nao diz nada.

    E a contagem de **divergentes** que precisa aparecer no log do Railway — e a
    de impossiveis, que denuncia desafio quebrado no ar.
    """
    cumpre = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    falha = POR_ID["P1-escada-fecha-3-nao-cumpre-por-pouco"]
    linhas = [
        _linha_do_vetor(cumpre, nu_lance=len(_fita(cumpre))),
        _linha_do_vetor(falha),
    ]
    fitas = {
        linhas[0]["id_partida"]: _fita(cumpre),
        linhas[1]["id_partida"]: _fita(falha),
    }

    def jogadas(parametros):
        return [
            {"nu_ordem": l["n"], "nu_jogador": 1 if l["jogador"] == 1 else 2,
             "co_lance": l["lance"]}
            for l in fitas[parametros["id_partida"]]
        ]

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": linhas,
            "FROM partida.tb002_jogada": jogadas,
            "UPDATE desafio_dia.tb003_resolucao": [{"id_resolucao": uuid4()}],
        }
    )

    contagem = await auditar_lote(sessao)

    assert contagem == {"conferem": 1, "divergentes": 1, "impossiveis": 0}
    assert sessao.commits == 1


@pytest.mark.asyncio
async def test_uma_resolucao_torta_NAO_derruba_o_lote():
    """⚠️ A auditoria e a rotina mais exposta a dado torto do projeto.

    Ela le o que chegou de milhoes de aparelhos; um `raise` no meio deixaria as
    199 seguintes pendentes por causa de uma.
    """
    cumpre = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    quebrada = _linha_do_vetor(cumpre)
    quebrada["co_jogo"] = "xadrez"  # jogo sem medidor
    boa = _linha_do_vetor(cumpre, nu_lance=len(_fita(cumpre)))

    def jogadas(_parametros):
        return [
            {"nu_ordem": l["n"], "nu_jogador": 1 if l["jogador"] == 1 else 2,
             "co_lance": l["lance"]}
            for l in _fita(cumpre)
        ]

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": [quebrada, boa],
            "FROM partida.tb002_jogada": jogadas,
            "UPDATE desafio_dia.tb003_resolucao": [{"id_resolucao": uuid4()}],
        }
    )

    contagem = await auditar_lote(sessao)

    assert contagem["impossiveis"] == 1
    assert contagem["conferem"] == 1


@pytest.mark.asyncio
async def test_desafio_quebrado_deixa_a_resolucao_PENDENTE():
    """⚠️ Fica pendente **de proposito**: o defeito e do desafio, e ele pode ser
    consertado. Marcar como divergente acusaria a pessoa e apagaria o rastro."""
    cumpre = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    quebrada = _linha_do_vetor(cumpre)
    quebrada["co_jogo"] = "xadrez"

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": [quebrada],
            "FROM partida.tb002_jogada": [
                {"nu_ordem": 1, "nu_jogador": 1, "co_lance": "H_2_1"}
            ],
        }
    )

    await auditar_lote(sessao)

    assert not sessao.sql_executado("UPDATE desafio_dia.tb003_resolucao")


def test_o_veredito_nunca_e_pendente():
    """Este objeto so existe porque a auditoria rodou."""
    assert Veredito(CONFERE).co_auditoria != PENDENTE
    assert Veredito(DIVERGENTE, "x").divergiu is True
