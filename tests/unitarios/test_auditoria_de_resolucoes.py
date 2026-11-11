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


def test_a_fita_une_a_coluna_dos_tres_jogos():
    """⚠️ `co_aresta` no Pontinhos, `co_lance` nas damas e letra + coluna no
    Quatro — o `COALESCE` as une.

    Os `LEFT JOIN` sao obrigatorios: uma jogada sem extensao precisa chegar como
    `NULL` para o julgamento acusar dado invalido, em vez de **sumir da fita**.

    ⛔ **O Quatro faltou aqui ate 11/11/2026**, e o job do Desafio do Dia caiu
    todo dia, em `des` e `prd`, na primeira resolucao do Quatro que entrou na
    fila. Este caso e o cadeado: um jogo novo no hub que esquecer a auditoria
    falha aqui, e nao no log do Railway.
    """
    from api.desafios.quadro import LETRA_DO_LANCE_QUATRO_SQL, SQL_LANCES

    assert "LEFT JOIN jogo_pontinhos" in auditoria.SQL_FITA
    assert "LEFT JOIN jogo_damas" in auditoria.SQL_FITA
    # A VIEW do Quatro (e nao a tabela): e ela que traz o tipo por extenso.
    assert "LEFT JOIN jogo_quatro.vw002_jogada q" in auditoria.SQL_FITA
    # ⚠️ O MESMO `CASE` do replay, e nao uma copia: a letra mora num lugar so.
    assert f"({LETRA_DO_LANCE_QUATRO_SQL}) || q.nu_coluna" in auditoria.SQL_FITA
    # A irma: o replay junta exatamente os mesmos tres jogos.
    for juncao in ("jogo_pontinhos", "jogo_damas", "jogo_quatro.vw002_jogada"):
        assert juncao in SQL_LANCES
    # ⛔ A ordem e por `nu_ordem`: sequencia continua que nunca recua nem repete.
    assert "ORDER BY j.nu_ordem ASC" in auditoria.SQL_FITA


def test_lance_NULO_do_quatro_e_divergencia_de_DADO_e_nao_estouro():
    """⛔ **A regressao exata de 11/2026.**

    Com o Quatro fora da `SQL_FITA`, cada lance dele chegava `None`, e o motor o
    entregava ao `re.match` — `TypeError`, que ninguem acima esperava, e o job
    inteiro caia. Um lance `NULL` e jogada sem extensao: **dado invalido**, e a
    resolucao sai divergente com o motivo, como qualquer fita irreproduzivel.
    """
    vetor = POR_ID["quatro-virada-cumpriu"]
    fita = _fita(vetor)
    fita[0] = {**fita[0], "lance": None}

    veredito = auditar(linha=_linha_do_vetor(vetor), fita=fita)

    assert veredito.co_auditoria == DIVERGENTE
    assert "fita irreproduzivel" in veredito.de_auditoria
    assert "None" in veredito.de_auditoria


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
async def test_um_estouro_INESPERADO_tambem_NAO_derruba_o_lote(monkeypatch, capsys):
    """⛔ A promessa da docstring valia so para o erro esperado.

    Ate 11/11/2026 o lote so pegava `AuditoriaImpossivel`, e um `TypeError` do
    Quatro derrubou o job inteiro todo dia. Agora qualquer estouro conta como
    impossivel, a resolucao fica PENDENTE (o defeito e do codigo, nao da
    pessoa), o rastro de pilha vai para o log e o lote segue.
    """
    cumpre = POR_ID["P1-escada-fecha-4-em-1-turno-cumpre"]
    torta = _linha_do_vetor(cumpre)
    boa = _linha_do_vetor(cumpre, nu_lance=len(_fita(cumpre)))

    auditar_de_verdade = auditoria.auditar

    def auditar_que_estoura_na_torta(*, linha, fita):
        # Um defeito qualquer do codigo, so na primeira resolucao. ⚠️ Pelo id, e
        # nao por `is`: o lote copia cada linha (`dict(m)`) antes de auditar.
        if linha["id_resolucao"] == torta["id_resolucao"]:
            raise TypeError("defeito simulado")
        return auditar_de_verdade(linha=linha, fita=fita)

    monkeypatch.setattr(auditoria, "auditar", auditar_que_estoura_na_torta)

    def jogadas(_parametros):
        return [
            {"nu_ordem": l["n"], "nu_jogador": 1 if l["jogador"] == 1 else 2,
             "co_lance": l["lance"]}
            for l in _fita(cumpre)
        ]

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": [torta, boa],
            "FROM partida.tb002_jogada": jogadas,
            "UPDATE desafio_dia.tb003_resolucao": [{"id_resolucao": uuid4()}],
        }
    )

    contagem = await auditar_lote(sessao)

    assert contagem == {"conferem": 1, "divergentes": 0, "impossiveis": 1}
    # A boa foi marcada e confirmada; a torta, nao (so um UPDATE, o da boa).
    assert sessao.commits == 1
    erros = capsys.readouterr().err
    assert "erro inesperado" in erros
    assert str(torta["id_resolucao"]) in erros
    assert "Traceback" in erros


@pytest.mark.asyncio
async def test_a_resolucao_do_QUATRO_confere_pelo_lote():
    """O caminho inteiro do Quatro: linha pendente → fita do log → juiz → CONFERE.

    ⚠️ A fita chega do jeito que a `SQL_FITA` corrigida a entrega (`s5`, `s2`...,
    a letra ja junta da coluna) — e e o mesmo vetor de T027 que o app usa.
    """
    vetor = POR_ID["quatro-virada-cumpriu"]
    linha = _linha_do_vetor(vetor)

    def jogadas(_parametros):
        return [
            {"nu_ordem": l["n"], "nu_jogador": 1 if l["jogador"] == 1 else 2,
             "co_lance": l["lance"]}
            for l in _fita(vetor)
        ]

    # O lance em que o objetivo caiu, pelo proprio juiz: o vetor nao o traz.
    from motores.juiz import julgar_desafio

    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=_fita(vetor),
        co_modalidade=vetor["co_modalidade"],
    )
    linha["nu_lance_cumpre_desafio"] = julgamento.nu_lance_cumpre_desafio

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": [linha],
            "FROM partida.tb002_jogada": jogadas,
            "UPDATE desafio_dia.tb003_resolucao": [{"id_resolucao": uuid4()}],
        }
    )

    contagem = await auditar_lote(sessao)

    assert contagem == {"conferem": 1, "divergentes": 0, "impossiveis": 0}


@pytest.mark.asyncio
async def test_no_QUATRO_a_pessoa_e_o_J1_do_app_mesmo_quando_e_o_menos_um_do_motor():
    """⚠️ A posicao publicada com numero IMPAR de lances: a vez e do `-1`.

    O vetor traz a fita nos sinais do MOTOR (a pessoa e o `-1`). O log, nao: no
    app a pessoa e sempre o Jogador 1, e e assim que ela chega da `SQL_FITA`
    (`nu_jogador = 1`). Este caso monta a fita como o LOG a entrega e exige que
    a auditoria a traduza e julgue com `jogador = vez_de`. Sem isso, o juiz
    recusava a fita ("o desafio e do jogador +1, mas a vez e do -1") e metade das
    resolucoes do Quatro sairia DIVERGENTE, acusando quem jogou.
    """
    vetor = POR_ID["quatro-virada-a-pessoa-e-o-J2"]
    vez = vetor["js_posicao_inicial"]["vez_de"]
    assert vez == -1  # a premissa do caso

    from motores.juiz import julgar_desafio

    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=vetor["js_posicao_inicial"],
        js_chegada=vetor["js_chegada"],
        fita=_fita(vetor),
        jogador=vez,
        co_modalidade=vetor["co_modalidade"],
    )
    linha = _linha_do_vetor(vetor, nu_lance=julgamento.nu_lance_cumpre_desafio)

    def jogadas(_parametros):
        # A pessoa (o `vez_de` no motor) vira o Jogador 1 do app, e o
        # personagem, o Jogador 2 — exatamente como o app grava o log.
        return [
            {"nu_ordem": l["n"], "nu_jogador": 1 if l["jogador"] == vez else 2,
             "co_lance": l["lance"]}
            for l in _fita(vetor)
        ]

    sessao = FakeSessaoSQL(
        respostas={
            "co_auditoria = 'pendente'": [linha],
            "FROM partida.tb002_jogada": jogadas,
            "UPDATE desafio_dia.tb003_resolucao": [{"id_resolucao": uuid4()}],
        }
    )

    contagem = await auditar_lote(sessao)

    assert contagem == {"conferem": 1, "divergentes": 0, "impossiveis": 0}


def test_o_jogador_do_desafio_e_o_vez_de_e_sem_ele_o_mais_um():
    """O mesmo numero do gerador e do app; a FEN das damas nao traz o campo."""
    assert auditoria.jogador_do_desafio({"vez_de": -1}) == -1
    assert auditoria.jogador_do_desafio({"vez_de": -1.0}) == -1
    assert auditoria.jogador_do_desafio({"vez_de": 1}) == 1
    assert auditoria.jogador_do_desafio({"fen": "W:W21:B12"}) == 1
    assert auditoria.jogador_do_desafio({"vez_de": 7}) == 1


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
