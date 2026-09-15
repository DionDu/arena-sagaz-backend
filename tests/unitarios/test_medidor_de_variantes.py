"""T049f - cadeados do script que MEDE variantes antes de elas serem publicadas.

⚠️ **O script nao roda aqui, e nao pode rodar.** Uma rodada de damas custa **80
minutos** (medido em 12/09/2026); um cadeado que ninguem aguenta rodar nao e
cadeado, e vira o teste que todo mundo pula com `-k`.

O que estes casos guardam e o que o script tem de **barato e quebravel**:

1. **A tabela de candidatas.** Uma candidata com o parametro mal escrito
   (`{'peca': 3}` no lugar de `{'pecas': 3}`) hoje so falha **depois** de o
   gerador rodar dez minutos, e o erro sai no meio de um relatorio longo.
2. **A selecao pelo alvo da linha de comando**, que passou a aceitar um tipo em
   12/09/2026 - e um `or` na ordem errada faria `damas` medir tudo, ou
   `damas_coroar` medir os dois tipos de damas, sem erro nenhum.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from job import editorial as editorial_mod
from job.tipos_de_desafio import RECEITAS, receita_de


def _carregar_o_script():
    """Importa `scripts/medir_variantes_do_editorial.py` como modulo.

    ⚠️ `scripts/` **nao e pacote** (nao tem `__init__.py`), entao `import` comum
    nao o acha. `spec_from_file_location` carrega um arquivo solto pelo caminho.

    ⛔ E o `sys.modules[nome] = modulo` **antes** do `exec_module` nao e zelo: um
    `@dataclass(slots=True)` procura a propria classe em `sys.modules` enquanto o
    modulo ainda esta sendo executado, e sem esta linha o carregamento estoura
    com `'NoneType' object has no attribute '__dict__'`.
    """
    caminho = Path(__file__).parents[2] / "scripts" / "medir_variantes_do_editorial.py"
    spec = importlib.util.spec_from_file_location("medir_variantes", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["medir_variantes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


MEDIDOR = _carregar_o_script()


# ═══════════════════════════════════════════════════════════════════════════
# 1. A tabela de candidatas
# ═══════════════════════════════════════════════════════════════════════════


def _todas_as_candidatas():
    """(tipo, candidata) de tudo o que esta em `A_MEDIR`, para parametrizar."""
    return [
        pytest.param(co_tipo, candidata, id=f"{co_tipo}-{dict(candidata.parametros)}")
        for co_tipo, candidatas in MEDIDOR.A_MEDIR.items()
        for candidata in candidatas
    ]


@pytest.mark.parametrize("co_tipo, candidata", _todas_as_candidatas())
def test_TODA_candidata_monta_chegada_e_frase(co_tipo, candidata):
    """Parametro mal escrito tem de estourar AQUI, e nao depois de 10 minutos.

    ⚠️ O `montar` da receita le as chaves pelo nome (`p["pecas"]`), entao um erro
    de digitacao vira `KeyError` - e hoje ele so aparece quando o gerador ja
    encontrou uma posicao, no meio de um relatorio de uma hora.
    """
    receita = receita_de(co_tipo)
    parametros = dict(candidata.parametros)

    # ⚠️ **`acima_do_guloso` nao monta sozinho, e nao e defeito:** o alvo dele sai
    # da POSICAO (decisao do dono, 11/09/2026), e so vira numero depois que o
    # gerador mede o guloso naquele tabuleiro. Aqui basta um valor qualquer - o
    # que se testa e se as chaves casam, nao quanto vale o alvo.
    # ⚠️ E o mesmo vale para os dois tipos de damas cujo alvo sai do MATERIAL
    # (`capturar`/`entregar`, 16/09/2026): `parametros_para_conferencia` resolve
    # os dois mecanismos com valores de exemplo, que e tudo o que este caso pede.
    parametros = editorial_mod.parametros_para_conferencia(parametros)

    js_chegada = receita.montar(parametros)
    assert js_chegada["janela"], "a chegada saiu sem janela"
    assert js_chegada["clausulas"], "a chegada saiu sem clausula nenhuma"

    # A frase tem de montar tambem: e ela que vira o enunciado na tela.
    receita.valores_da_frase(parametros, "cacau")


def test_a_JANELA_da_candidata_cabe_no_TETO_com_que_ela_sera_medida():
    """⛔ Janela e teto sao o MESMO limite, e medir com eles em desacordo mente.

    ⚠️ As tres unidades ja se confundiram nesta feature, entao, de novo:
    `lances_do_jogador: n` conta os lances **da pessoa**; o teto conta
    **meios-lances** (os dois lados). Nas damas a alternancia e estrita, entao
    `n` lances do jogador sao `2n` meios-lances.

    ⛔ Uma candidata que peca 8 lances do jogador sendo medida com teto 12
    descreveria uma execucao impossivel: o gerador pararia de procurar em 12
    meios-lances (6 lances), e a janela de 8 nunca seria exercida.

    ⚠️ **E este cadeado ja mordeu no dia em que nasceu** (12/09/2026): a primeira
    versao de `{damas: 2, lances: 10, teto: 16}` pedia 20 meios-lances de janela
    com 16 de teto. A medicao teria rodado, saido bonita, e descrito uma execucao
    que o gerador nao faz.

    ⛔ **So cobra de quem escreve teto PROPRIO, e isso e deliberado.** As
    variantes que herdam o teto do tipo podem prometer janela maior do que o
    gerador alcanca - `{damas: 2, lances: 8}` esta no ar assim, com 16
    meios-lances de janela contra 12 de teto, e ⚠️ **e por isso que as janelas de
    8 e de 10 medem identico**: nenhuma das duas e exercida, a folga so esta
    escrita na frase. Quem acrescenta um teto proprio esta justamente
    investigando esse limite, e ai a conta tem de fechar.
    """
    for co_tipo, candidatas in MEDIDOR.A_MEDIR.items():
        receita = receita_de(co_tipo)
        if receita.co_jogo != "damas":
            continue  # so nas damas a alternancia e estrita
        publicacao = editorial_mod.publicacao_de(co_tipo, 0)
        for candidata in candidatas:
            n = candidata.parametros.get("lances")
            if n is None:
                continue
            teto = (
                candidata.nu_maximo_de_meios_lances
                or publicacao.nu_maximo_de_meios_lances
            )
            # ⚠️ O que interessa e a candidata **que pede mais do que o teto
            # alcanca**: ela seria medida por um limite que a frase nao usa.
            if n * 2 > teto:
                assert candidata.nu_maximo_de_meios_lances is None, (
                    f"{co_tipo} {dict(candidata.parametros)} pede {n} lances do "
                    f"jogador ({n * 2} meios-lances) com teto PROPRIO de {teto}: "
                    "quem escreve um teto proprio tem de escreve-lo suficiente"
                )


# ═══════════════════════════════════════════════════════════════════════════
# 2. A selecao pelo alvo da linha de comando
# ═══════════════════════════════════════════════════════════════════════════


def test_o_alvo_TODOS_mede_tudo():
    assert MEDIDOR.tipos_do_alvo("todos") == list(MEDIDOR.A_MEDIR)


def test_o_alvo_por_JOGO_mede_os_tipos_daquele_jogo():
    escolhidos = MEDIDOR.tipos_do_alvo("damas")

    assert escolhidos, "nenhum tipo de damas foi selecionado"
    assert all(receita_de(t).co_jogo == "damas" for t in escolhidos)
    # ⛔ E nao pode ter vazado o outro jogo - o `or` da selecao ja tem tres ramos.
    assert not any(receita_de(t).co_jogo == "pontinhos" for t in escolhidos)


def test_o_alvo_por_TIPO_mede_SO_aquele_tipo():
    """⚠️ Este e o caso novo de 12/09, e o que economiza 80 minutos por rodada."""
    assert MEDIDOR.tipos_do_alvo("damas_capturar_multipla") == [
        "damas_capturar_multipla"
    ]


def test_alvo_desconhecido_nao_mede_nada():
    """⛔ Lista vazia, e nao "mede tudo por garantia" - medir sem ter sido pedido
    e uma hora de maquina que ninguem autorizou."""
    assert MEDIDOR.tipos_do_alvo("damas_coroar_errado") == []
    assert MEDIDOR.principal(["damas_coroar_errado"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 3. O filtro que dispensa a REIMPRESSAO (e so ela)
# ═══════════════════════════════════════════════════════════════════════════


def test_o_filtro_pega_SO_quem_mexe_num_botao_de_geracao():
    """⚠️ Botao de geracao e preparo ou teto - o que muda o que o gerador PROCURA.

    Os `parametros` mudam o que a **frase pede**, e toda candidata tem os seus;
    filtrar por eles nao separaria nada.
    """
    escolhidas = MEDIDOR.so_as_de_botao_proprio(
        MEDIDOR.A_MEDIR["damas_capturar_multipla"]
    )

    assert escolhidas, "nenhuma candidata de teto proprio sobrou"
    assert all(
        c.nu_lances_de_preparo is not None or c.nu_maximo_de_meios_lances is not None
        for c in escolhidas
    )
    # ⛔ E as ja medidas duas vezes ficam de fora - e o motivo do filtro existir.
    assert {"pecas": 3, "lances": 6} not in [dict(c.parametros) for c in escolhidas]


def test_o_filtro_NAO_e_atalho_para_publicar():
    """⛔ Ele dispensa a REIMPRESSAO, nunca a primeira medida.

    ⚠️ O cadeado e sobre a tabela, e nao sobre o codigo: toda candidata **sem**
    botao proprio tem de continuar na rodada cheia. Se um dia alguem "limpar" as
    candidatas antigas para a rodada filtrada ficar curta, a rodada cheia deixa
    de medir o que sustenta o que esta no ar.
    """
    for co_tipo, candidatas in MEDIDOR.A_MEDIR.items():
        cheia = list(candidatas)
        filtrada = MEDIDOR.so_as_de_botao_proprio(candidatas)
        assert len(filtrada) <= len(cheia)
        for c in filtrada:
            assert c in cheia, "o filtro inventou candidata que a tabela nao tem"


def test_a_bandeira_com_alvo_sem_botao_proprio_AVISA_em_vez_de_sair_calada():
    """⛔ Relatorio vazio e silencioso e pior que erro: parece que nada apertou.

    Nenhuma candidata do Pontinhos tem teto proprio hoje, e `acima_do_guloso` tem
    preparo proprio - entao o alvo usado aqui e um tipo cujas candidatas nao
    mexem em botao nenhum.
    """
    assert MEDIDOR.principal(["pontinhos_cadeia_longa", "--com-botao-proprio"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ PROMOVER E MOVER — as duas tabelas nao podem discordar
# ═══════════════════════════════════════════════════════════════════════════


def test_toda_variante_EM_AVALIACAO_tem_uma_proposta_de_verdade():
    """⛔ **O defeito que este caso pega quebrava a rodada no meio.**

    Em 14/09/2026 quatro propostas de Pontinhos subiram para `RECEITAS` e
    **continuaram** em `EM_AVALIACAO`. Uma delas mudou de nome ao subir
    (`pontinhos_nao_entregar_nada` virou `pontinhos_nao_entregar`, o tipo 2 que ja
    existia na `0018`), e o nome velho deixou de existir nos dois lados.

    ⚠️ **O sintoma so aparecia RODANDO**, e tarde: `medir_variantes_do_editorial.py
    em-avaliacao` seguia ate aquele tipo e levantava `TipoSemReceita` — depois de
    ja ter gasto minutos medindo os anteriores.
    """
    for co_tipo in MEDIDOR.EM_AVALIACAO:
        assert MEDIDOR.receita_em_avaliacao_de(co_tipo) is not None, (
            f"⛔ {co_tipo} esta em EM_AVALIACAO e nao tem proposta em "
            "`job/tipos_propostos.py`. Se ele subiu, mova a entrada para A_MEDIR "
            "com o nome e os parametros publicados - promover e MOVER."
        )


def test_nenhuma_variante_EM_AVALIACAO_ja_esta_NO_AR():
    """⛔ O outro lado do mesmo defeito, e este mentia em vez de quebrar.

    ⚠️ As outras tres promovidas continuavam medindo — **com o selo
    `⚠️ EM AVALIACAO, NAO PUBLICAVEL` na tela**, que era falso: elas estavam no ar.
    E pior, com a `Publicacao` vazia dos tipos em avaliacao, e nao com o **preparo
    14** que tres delas exigem: a taxa impressa descreveria uma execucao que nao
    existe, e um numero baixo pareceria defeito do tipo.
    """
    no_ar = set(RECEITAS) & set(MEDIDOR.EM_AVALIACAO)
    assert not no_ar, (
        f"⛔ {sorted(no_ar)} esta(o) em RECEITAS e ainda em EM_AVALIACAO. "
        "Mova para A_MEDIR: um tipo publicado se mede como publicado."
    )


def test_todo_tipo_de_A_MEDIR_esta_MESMO_no_ar():
    """⚠️ O caminho inverso: `A_MEDIR` mede o que esta publicado.

    ⛔ Uma entrada aqui para um tipo que nao subiu buscaria `publicacao_de`, que
    falha alto — mas so na hora de rodar, que e sempre o pior momento para
    descobrir uma tabela desarrumada.
    """
    for co_tipo in MEDIDOR.A_MEDIR:
        assert co_tipo in RECEITAS, (
            f"⛔ {co_tipo} esta em A_MEDIR e nao esta em RECEITAS"
        )


def test_as_duas_tabelas_nao_se_cruzam():
    """⛔ Um tipo nos dois lados seria medido duas vezes, com regras diferentes."""
    assert not set(MEDIDOR.A_MEDIR) & set(MEDIDOR.EM_AVALIACAO)


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A REGUA — a pergunta que o resto deste script NAO responde
# ═══════════════════════════════════════════════════════════════════════════


def test_a_bandeira_da_regua_existe_e_e_OPCIONAL():
    """⚠️ Bandeira, e nao padrao, por preco: ela multiplica a rodada.

    ⛔ Mas a existencia dela e o que impede o `✅ FOLGA` de ser lido como
    aprovacao. `FOLGA 3 de 3` quer dizer *"gerou tres candidatos"*, e o job
    publica **o primeiro que cai na banda de dificuldade** — sao perguntas
    diferentes, e a segunda e a que decide.
    """
    assert MEDIDOR.BANDEIRA_COM_REGUA == "--com-regua"
    assert MEDIDOR.EXECUCOES_DA_SONDA_DE_REGUA >= 1


def test_a_linha_da_regua_NOMEIA_de_que_lado_da_banda_a_variante_caiu():
    """⛔ *"Fora da banda"* sozinho nao diz o que fazer com a variante.

    ⚠️ Duro demais e banal pedem correcoes **opostas** — afrouxar o alvo ou
    aperta-lo —, e um relatorio que so dissesse "fora" obrigaria quem le a abrir
    a taxa e comparar com o piso de cabeca. Foi assim que a escada invertida do
    `damas_sobreviver` passou despercebida por um dia inteiro.
    """
    from job import alvo_observado as alvo_mod
    from job.regua import Medicao

    alvo = alvo_mod.alvo_para_a_regua()

    def medicoes_falsas(resolveu: int) -> list[Medicao]:
        """Tres mascotes com a mesma taxa - so para exercitar o veredito.

        ⚠️ **Com a `Medicao` de verdade, e nao um dublê**: ela tem a propriedade
        `taxa` que o `taxa_media` consome, e um objeto improvisado passaria a
        depender de eu ter adivinhado a forma dela certo.
        """
        return [
            Medicao(
                co_personagem=nome,
                nu_execucoes=10,
                nu_resolveu=resolveu,
                co_versao_perfil="teste",
                co_versao_motor="teste",
            )
            for nome in ("cacau", "tex", "magno")
        ]

    # ⚠️ O texto sai de `_linha_da_regua`, mas medir de verdade custaria minutos;
    # o que se prova aqui e a REGRA do veredito, que e o que engana quem le.
    from job import regua as regua_mod

    for resolveu, esperado in ((3, "DURO DEMAIS"), (10, "BANAL"), (8, None)):
        med = medicoes_falsas(resolveu)
        taxa = regua_mod.taxa_media(med)
        distancia = regua_mod.distancia_da_banda(med, piso=alvo.piso, teto=alvo.teto)
        if esperado is None:
            assert distancia == 0.0, f"taxa {taxa} devia estar na banda"
        else:
            assert distancia > 0.0
            lado = "DURO DEMAIS" if taxa < alvo.piso else "BANAL"
            assert lado == esperado, f"taxa {taxa} foi classificada como {lado}"


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A REGUA ESCOLHE ENTRE OS CANDIDATOS DO DIA — como o job faz
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **A rodada de 15/09/2026 mediu so o PRIMEIRO candidato de cada dia**, e isso
# respondia a pergunta errada: o job pede 3 e publica **o primeiro que cai na
# banda**. Uma variante cujo segundo candidato encaixaria aparecia como reprovada,
# e nada no relatorio dizia que a leitura era pessimista.


class _CandidatoFalso:
    """O minimo que `_linha_da_regua` toca num candidato."""

    def __init__(self, nome: str) -> None:
        self.co_personagem = "pita"
        self.nu_semente = 1
        self.nome = nome


def _regua_falsa(monkeypatch, taxas_por_candidato):
    """Faz a regua devolver taxas escolhidas, sem rodar motor nenhum.

    ⚠️ **Sem isto o teste custaria minutos** — e o que se prova aqui e a REGRA de
    escolha, que e o que estava errado, e nao a contagem dos mascotes (essa ja
    tem os seus casos em `test_regua_e_alvo.py`).
    """
    from job import regua as regua_mod

    chamadas = {"quantas": 0}

    def medir_falso(**kwargs):
        taxa = taxas_por_candidato[chamadas["quantas"]]
        chamadas["quantas"] += 1
        resolveu = round(taxa * 10)
        return [
            regua_mod.Medicao(
                co_personagem=nome,
                nu_execucoes=10,
                nu_resolveu=resolveu,
                co_versao_perfil="t",
                co_versao_motor="t",
            )
            for nome in ("cacau", "tex", "magno")
        ]

    # ⚠️ A bancada falsa precisa dos tres campos que `tentativa_com_motor` le -
    # ela e construida antes de a regua ser chamada, e um `object()` pelado
    # quebraria antes de chegar na regra que este teste prova.
    class _BancadaFalsa:
        jogador = None
        estado_inicial = None
        julgar = None

    monkeypatch.setattr(MEDIDOR.gerador_mod, "bancada", lambda c: _BancadaFalsa())
    monkeypatch.setattr(regua_mod, "medir_candidato", medir_falso)
    monkeypatch.setattr(regua_mod, "tentativa_com_motor", lambda **k: None)
    return chamadas


def test_a_regua_PARA_no_primeiro_candidato_que_cai_na_banda(monkeypatch):
    """⚠️ Como o job: os seguintes nem sao medidos.

    ⛔ E nao e so economia — medir os tres sempre daria um numero que **nenhuma
    execucao real produz**, porque na producao os outros dois nao chegam a ser
    avaliados.
    """
    chamadas = _regua_falsa(monkeypatch, [0.75, 0.30, 0.30])
    linha = MEDIDOR._linha_da_regua(
        [_CandidatoFalso("a"), _CandidatoFalso("b"), _CandidatoFalso("c")],
        teto=12,
        dia="2026-10-01",
    )
    assert chamadas["quantas"] == 1, "mediu candidato que o job nao veria"
    assert "✅" in linha and "candidato 1 de 3" in linha


def test_a_regua_SEGUE_para_o_segundo_quando_o_primeiro_erra(monkeypatch):
    """⛔ **O caso que a rodada de 15/09 nao enxergava.**

    Uma variante cujo primeiro candidato sai banal e o segundo encaixa e uma
    variante **que funciona** — o job publicaria o segundo. Medir so o primeiro a
    reprovaria, e o relatorio pareceria conclusivo.
    """
    chamadas = _regua_falsa(monkeypatch, [1.00, 0.75, 0.30])
    linha = MEDIDOR._linha_da_regua(
        [_CandidatoFalso("a"), _CandidatoFalso("b"), _CandidatoFalso("c")],
        teto=12,
        dia="2026-10-01",
    )
    assert chamadas["quantas"] == 2
    assert "✅" in linha and "candidato 2 de 3" in linha


def test_quando_NENHUM_encaixa_a_linha_diz_de_quanto_foi_o_erro(monkeypatch):
    """⚠️ **E o erro do MENOS PIOR**, que e o que o job publicaria.

    ⛔ Dizer so *"nenhum na banda"* esconderia a diferenca entre errar por 0,03 —
    que e afinar um numero — e errar por 0,40, que e repensar o tipo.
    """
    # ⚠️ **Taxas da GRADE de 10 execucoes** (multiplos de 0,1): a regua falsa
    # converte a taxa em `nu_resolveu` arredondado, entao pedir 0,95 devolveria
    # 1,00 e o teste estaria provando outra coisa - foi o que aconteceu ao
    # escreve-lo.
    _regua_falsa(monkeypatch, [1.00, 0.90, 0.30])
    linha = MEDIDOR._linha_da_regua(
        [_CandidatoFalso("a"), _CandidatoFalso("b"), _CandidatoFalso("c")],
        teto=12,
        dia="2026-10-03",
    )
    assert "NENHUM dos 3" in linha
    assert "banal" in linha and "duro" in linha
    # 0.90 passa 0.10 do teto 0.80, e e o menor erro dos tres.
    assert "0.10" in linha, linha
