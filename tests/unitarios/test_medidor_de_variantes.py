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
from datetime import date
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


def test_os_dias_pedidos_tem_padrao_de_TRES_e_recusam_o_invalido():
    """`--dias=N` (T124c, 21/10/2026): sem ele, os 3 de sempre.

    ⛔ O invalido e RECUSA (`None`), e nao o padrao: `--dias=nove` medindo 3
    dias calado devolveria o resultado de sempre a quem pediu nove.
    """
    assert MEDIDOR.DIAS_MEDIDOS == 3
    assert MEDIDOR.dias_pedidos(["quatro_sem_o_meio", "--com-regua"]) == 3
    assert MEDIDOR.dias_pedidos(["quatro_sem_o_meio", "--dias=9"]) == 9
    for invalido in ("--dias=0", "--dias=nove", "--dias=", "--dias=-2", "--dias=9.5"):
        assert MEDIDOR.dias_pedidos([invalido]) is None, invalido
    assert MEDIDOR.principal(["quatro_sem_o_meio", "--dias=nove"]) == 2


def test_os_dias_pedidos_chegam_ate_a_lista_de_dias(monkeypatch):
    """Do argumento ao `_dias_do_jogo`: a rodada mede MESMO os dias pedidos.

    ⚠️ E o `--dias=9` nao vira o alvo (ele comeca com `-`): o tipo medido e o
    pedido, e nao um tipo chamado "9".
    """
    pedidos: list[tuple[str, int]] = []

    def medir_de_mentira(co_tipo, candidatas, *, com_regua, nu_dias, do_dia):
        # Sem `--do-dia=`, a rodada comeca no primeiro dia.
        assert do_dia == 1
        pedidos.append((co_tipo, nu_dias))
        return 0.0

    monkeypatch.setattr(MEDIDOR, "medir", medir_de_mentira)
    # ⚠️ Um tipo FORA do ar: o "sem o meio", que nasceu neste caso, subiu em
    # 22/10/2026, e o medidor recusa (saida 2) o tipo do Quatro no ar. O
    # bloquear esta aposentado, mas continua medivel pelo nome.
    assert MEDIDOR.principal(["quatro_bloquear", "--dias=9"]) == 0
    assert pedidos == [("quatro_bloquear", 9)]

    class Parou(Exception):
        """Para o `medir` de verdade logo depois de pedir os dias."""

    def dias_do_jogo(co_jogo, quantos):
        raise Parou(quantos)

    monkeypatch.undo()
    monkeypatch.setattr(MEDIDOR, "_dias_do_jogo", dias_do_jogo)
    variantes = MEDIDOR.candidatas_fora_do_ar("quatro_bloquear")
    with pytest.raises(Parou) as parou:
        MEDIDOR.medir("quatro_bloquear", variantes, nu_dias=9)
    assert parou.value.args == (9,)


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
        # ⚠️ Desde a T117 (spec 010) a linha da regua passa o jogo a regua, que
        # decide por ele se mede em paralelo.
        self.co_jogo = "damas"
        self.co_personagem = "pita"
        self.nu_semente = 1
        self.nome = nome


#: Uma escada que PASSA, como taxa por mascote.
#:
#: ⛔ **Desde 16/09/2026 uma taxa UNIFORME nunca cabe na escada**, e isso nao e um
#: detalhe de teste: a escada exige que os mascotes resolvam em proporcoes
#: **diferentes** (`regua.ESCADA_ALVO`), entao "todos com 0,75" e, por definicao,
#: um desafio mal calibrado — e era exatamente o que a media aprovava.
#:
#: ⚠️ Estes tres numeros caem cada um na faixa do seu mascote.
ESCADA_QUE_PASSA = {"cacau": 0.1, "tex": 0.6, "magno": 0.9}

#: Uma escada que NAO cabe: todos resolvem quase tudo (o desafio banal).
ESCADA_BANAL = {"cacau": 1.0, "tex": 1.0, "magno": 1.0}

#: Uma escada que NAO cabe: quase ninguem resolve (o desafio duro demais).
ESCADA_DURA = {"cacau": 0.3, "tex": 0.3, "magno": 0.3}


def _regua_falsa(monkeypatch, escadas_por_candidato):
    """Faz a regua devolver taxas escolhidas, sem rodar motor nenhum.

    Args:
        escadas_por_candidato: uma lista de `{co_personagem: taxa}`, uma entrada
            por candidato que o medidor for avaliar.

    ⚠️ **Sem isto o teste custaria minutos** — e o que se prova aqui e a REGRA de
    escolha, que e o que estava errado, e nao a contagem dos mascotes (essa ja
    tem os seus casos em `test_regua_e_alvo.py`).

    ⛔ **Ate 16/09/2026 este duble recebia UMA taxa por candidato**, aplicada aos
    tres mascotes. Funcionava enquanto a decisao era a media; com a escada, uma
    taxa uniforme e sempre reprovada — entao o duble passou a receber a escada
    inteira, que e a forma que o criterio de verdade enxerga.
    """
    from job import regua as regua_mod

    chamadas = {"quantas": 0}

    def medir_falso(**kwargs):
        escada = escadas_por_candidato[chamadas["quantas"]]
        chamadas["quantas"] += 1
        return [
            regua_mod.Medicao(
                co_personagem=nome,
                nu_execucoes=10,
                nu_resolveu=round(taxa * 10),
                co_versao_perfil="t",
                co_versao_motor="t",
            )
            for nome, taxa in escada.items()
        ]

    # ⚠️ A bancada falsa precisa dos campos que `tentativa_com_motor` le - ela e
    # construida antes de a regua ser chamada, e um `object()` pelado quebraria
    # antes de chegar na regra que este teste prova.
    class _BancadaFalsa:
        jogador = None
        estado_inicial = None
        julgar = None
        # ⚠️ De 16/09/2026: o solucionador do TIPO, quando ha um.
        solucionador = None

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
    chamadas = _regua_falsa(monkeypatch, [ESCADA_QUE_PASSA, ESCADA_DURA, ESCADA_DURA])
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
    chamadas = _regua_falsa(monkeypatch, [ESCADA_BANAL, ESCADA_QUE_PASSA, ESCADA_DURA])
    linha = MEDIDOR._linha_da_regua(
        [_CandidatoFalso("a"), _CandidatoFalso("b"), _CandidatoFalso("c")],
        teto=12,
        dia="2026-10-01",
    )
    assert chamadas["quantas"] == 2
    assert "✅" in linha and "candidato 2 de 3" in linha


def test_quando_NENHUM_encaixa_a_linha_diz_QUAL_DEGRAU_errou(monkeypatch):
    """⚠️ **E a escada do MENOS PIOR**, que e o candidato que o job publicaria.

    ⛔ Dizer so *"nenhum na escada"* esconderia a diferenca entre errar por 0,03 —
    que e afinar um numero — e errar por 0,40, que e repensar o tipo.

    ⚠️ **E desde 16/09/2026 a linha diz mais que o quanto: diz QUAL degrau.** Uma
    distancia media de 0,15 pode ser um mascote muito fora ou tres pouco fora, e
    as duas pedem reacoes opostas — tipo mal escolhido × calibracao.

    ⚠️ **Taxas da GRADE de 10 execucoes** (multiplos de 0,1): a regua falsa
    converte a taxa em `nu_resolveu` arredondado, entao pedir 0,95 devolveria
    1,00 e o teste estaria provando outra coisa - foi o que aconteceu ao
    escreve-lo.
    """
    # O do meio e o menos pior: so o Tex erra, e por 0,10.
    quase = {"cacau": 0.1, "tex": 0.3, "magno": 0.9}
    _regua_falsa(monkeypatch, [ESCADA_BANAL, quase, ESCADA_DURA])
    linha = MEDIDOR._linha_da_regua(
        [_CandidatoFalso("a"), _CandidatoFalso("b"), _CandidatoFalso("c")],
        teto=12,
        dia="2026-10-03",
    )
    assert "NENHUM dos 3" in linha
    # ⛔ O degrau que errou aparece nomeado, e os que acertaram tambem — e a
    # combinacao das duas coisas que diz se e calibracao ou tipo errado.
    assert "tex" in linha and "cacau 0.10 ✅" in linha, linha
    # Tex 0,30 erra 0,15 do piso 0,45; dividido pelos tres mascotes, 0,05.
    assert "0.05" in linha, linha


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ O ALVO `no-ar` — medir O QUE ESTA PUBLICADO, e nao uma lista paralela
# ═══════════════════════════════════════════════════════════════════════════


def test_o_alvo_no_ar_cobre_TODO_tipo_publicado():
    """⛔ **`A_MEDIR` e uma tabela PARALELA ao editorial, e as duas ja divergiram.**

    ⚠️ **Achado investigando o job de 15/09/2026**, em que 6 dos 7 dias sairam
    fora da banda: `pontinhos_paciencia` e `pontinhos_nao_entregar` estao no ar
    desde 14/09 e **nao estao em `A_MEDIR`**. Uma delas publicou no dia 18/09 com
    taxa 0,50, e ⛔ nenhuma rodada de medicao a teria examinado.

    ⚠️ **E o proprio comentario de `A_MEDIR` avisa desse defeito** — *"variante
    publicada fora da lista deixa de ser remedida quando o gerador muda"*. O aviso
    estava escrito; o que faltava era quem o cobrasse.

    ✅ O alvo `no-ar` le `RECEITAS` e o editorial **na hora**, entao ele nao pode
    envelhecer: tipo novo entra sozinho.
    """
    no_ar = set(MEDIDOR.tipos_do_alvo(MEDIDOR.ALVO_NO_AR))
    # ⚠️ A unica excecao e o tipo no ar de jogo FORA do rodizio (a virada do
    # Quatro, T124b da spec 010, ate a T125): medido pelo alvo `no-ar`, ele seria
    # gerado com o jogo da data - outro jogo. Quem diz quais sao e a mesma funcao
    # que o medidor usa, e nao uma lista daqui.
    fora_do_rodizio = {
        co_tipo for co_tipo in RECEITAS if MEDIDOR.no_ar_e_fora_do_rodizio(co_tipo)
    }
    publicados = {
        co_tipo
        for co_tipo in RECEITAS
        if editorial_mod.variantes_de(co_tipo) and co_tipo not in fora_do_rodizio
    }
    assert not no_ar & fora_do_rodizio
    assert no_ar == publicados, (
        "⛔ o alvo `no-ar` deixou de cobrir algum tipo publicado. Ele existe "
        "justamente para nao depender de uma lista escrita a mao."
    )

    # ⚠️ E o cadeado morde nos dois sentidos: se um tipo publicado voltar a faltar
    # em `A_MEDIR`, isto NAO falha — mas a mensagem abaixo diz quais sao, para
    # quem for ler o relatorio de uma rodada `todos` e se perguntar o que sumiu.
    fora_da_tabela = publicados - set(MEDIDOR.A_MEDIR)
    assert fora_da_tabela == {"pontinhos_nao_entregar", "pontinhos_paciencia"}, (
        "⚠️ mudou a lista de tipos publicados que NAO estao em `A_MEDIR`: "
        f"{sorted(fora_da_tabela)}. Isso nao e erro — `A_MEDIR` guarda as "
        "candidatas em estudo, e `no-ar` mede as publicadas —, mas a divergencia "
        "merece ser vista de proposito, e nao descoberta num job."
    )


def test_as_candidatas_do_no_ar_levam_os_botoes_DE_CADA_variante():
    """⛔ `medir()` usa os botoes da variante 0 para todas, e isso NAO vale aqui.

    ⚠️ **A simplificacao e legitima em `A_MEDIR`**, onde as candidatas de um tipo
    quase sempre compartilham preparo e teto — e as que nao compartilham trazem o
    botao escrito a mao na linha delas.

    ⛔ **No editorial ela mentiria:** `pontinhos_chegar_ao_placar` publica tres
    variantes com preparo 8 e duas de `acima_do_guloso` com preparo **14** (sem
    cadeia formada nao ha double dealing a cobrar), e `damas_sobreviver` publica
    com teto **18** (`lances: 8` sao 16 meios-lances). Medir com os botoes da
    variante 0 devolveria uma taxa que descreve uma execucao que o job nao faz.
    """
    for co_tipo in MEDIDOR.tipos_do_alvo(MEDIDOR.ALVO_NO_AR):
        candidatas = MEDIDOR.candidatas_do_editorial(co_tipo)
        publicacoes = editorial_mod.variantes_de(co_tipo)
        assert len(candidatas) == len(publicacoes), co_tipo

        for candidata, publicacao in zip(candidatas, publicacoes):
            assert candidata.parametros == publicacao.parametros, co_tipo
            assert (
                candidata.nu_lances_de_preparo == publicacao.nu_lances_de_preparo
            ), f"{co_tipo}: preparo diferente do publicado"
            assert (
                candidata.nu_maximo_de_meios_lances
                == publicacao.nu_maximo_de_meios_lances
            ), f"{co_tipo}: teto diferente do publicado"

    # ⚠️ **E o caso so prova alguma coisa se houver variedade de botao para
    # provar.** Sem isto ele passaria num editorial em que tudo usa o padrao, e
    # daria a impressao de cobrir o que nao cobre.
    preparos = {
        c.nu_lances_de_preparo
        for co_tipo in MEDIDOR.tipos_do_alvo(MEDIDOR.ALVO_NO_AR)
        for c in MEDIDOR.candidatas_do_editorial(co_tipo)
    }
    assert len(preparos) >= 2, (
        "⛔ todas as variantes no ar passaram a usar o mesmo preparo, e este caso "
        "deixou de provar o que promete. Reveja-o."
    )


def test_os_alvos_no_ar_por_JOGO_particionam_o_editorial():
    """⚠️ `no-ar-damas` e `no-ar-pontinhos` existem por PRECO, nao por arrumacao.

    A rodada com regua das 10 variantes de damas custa ~2h20 e a das 17 de
    Pontinhos ~1h. ⛔ Um alvo unico obrigaria a pagar as duas para investigar uma.

    ⚠️ **E eles tem de PARTICIONAR**: juntos dao o `no-ar` inteiro, e nenhum tipo
    aparece nos dois. Um jogo novo que nao entrasse em nenhum sumiria da medicao
    sem erro nenhum — e e assim que uma variante fica anos sem ser remedida.
    """
    inteiro = set(MEDIDOR.tipos_do_alvo(MEDIDOR.ALVO_NO_AR))
    das_damas = set(MEDIDOR.tipos_do_alvo("no-ar-damas"))
    dos_pontinhos = set(MEDIDOR.tipos_do_alvo("no-ar-pontinhos"))

    assert das_damas | dos_pontinhos == inteiro, (
        "⛔ os dois alvos por jogo nao cobrem o `no-ar` inteiro. Se um jogo novo "
        "entrou no catalogo, ele precisa do alvo dele em `ALVOS_NO_AR`."
    )
    assert not (das_damas & dos_pontinhos), "um tipo caiu nos dois jogos"
    assert all(receita_de(t).co_jogo == "damas" for t in das_damas)
    assert all(receita_de(t).co_jogo == "pontinhos" for t in dos_pontinhos)


# ═══════════════════════════════════════════════════════════════════════════
# A RODADA RETOMAVEL (22/10/2026, DECISOES-do-dono §8zzzm e §8zzzr item 12)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Nenhum caso daqui roda motor: o trabalho de uma unidade (`medir_um_dia`)
# e trocado por um duplo, e o pool nao e usado (`processos=1` roda no proprio
# processo). O que se prova e o que a rodada faz COM as unidades: quais mede,
# o que grava, o que pula ao retomar e o que o relatorio conta.


def test_o_primeiro_dia_tem_padrao_UM_e_recusa_o_invalido():
    """`--do-dia=N`: sem ele, o primeiro dia; invalido ou depois do ultimo, recusa."""
    assert MEDIDOR.primeiro_dia_pedido(["quatro_encoste"]) == 1
    assert MEDIDOR.primeiro_dia_pedido(["--do-dia=10"]) == 10
    for invalido in ("--do-dia=0", "--do-dia=dez", "--do-dia=", "--do-dia=-1"):
        assert MEDIDOR.primeiro_dia_pedido([invalido]) is None, invalido
    # ⛔ Primeiro dia depois do ultimo: "mediu zero dias" nao pode sair como resultado.
    assert MEDIDOR.principal(["quatro_bloquear", "--dias=9", "--do-dia=10"]) == 2
    assert MEDIDOR.principal(["quatro_bloquear", "--do-dia=0"]) == 2


def test_os_processos_tem_padrao_dos_nucleos_menos_um(monkeypatch):
    """§8zzzm: os nucleos logicos menos um, e `--processos=N` muda."""
    import os

    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    assert MEDIDOR.processos_pedidos(["quatro_encoste"]) == 15
    assert MEDIDOR.processos_pedidos(["--processos=4"]) == 4
    # Uma maquina de um nucleo so ainda mede, com um processo.
    monkeypatch.setattr(os, "cpu_count", lambda: 1)
    assert MEDIDOR.processos_padrao() == 1
    for invalido in ("--processos=0", "--processos=oito", "--processos="):
        assert MEDIDOR.processos_pedidos([invalido]) is None, invalido
    assert MEDIDOR.principal(["quatro_bloquear", "--processos=0"]) == 2


def test_o_do_dia_mede_SO_os_dias_do_fim(monkeypatch):
    """`--dias=18 --do-dia=10` mede os dias 10 a 18 da MESMA lista de 18.

    ⚠️ E o que permite somar a rodada nova a triagem de 9 dias: o 10o dia daqui
    e o 10o de uma rodada de 18, e nao o 1o deslocado.
    """
    vistos: list = []

    def espiao(dia, **_resto):
        vistos.append(dia)
        return []

    monkeypatch.setattr(MEDIDOR.gerador_mod, "gerar_candidatos", espiao)
    # ⚠️ Um tipo FORA do ar (o bloquear, aposentado mas medivel pelo nome): o
    # tipo do Quatro no ar e recusado pelo medidor.
    uma = MEDIDOR.candidatas_fora_do_ar("quatro_bloquear")[:1]
    MEDIDOR.medir("quatro_bloquear", uma, nu_dias=18, do_dia=10)

    assert vistos == MEDIDOR._dias_do_jogo("quatro", 18)[9:]
    assert len(vistos) == 9
    # Nos jogos do rodizio os dias pulam, e o corte e na lista, e nao no calendario.
    assert MEDIDOR.dias_da_rodada("damas", 6, 4) == MEDIDOR._dias_do_jogo("damas", 6)[3:]


def test_a_unidade_leva_os_BOTOES_da_variante_ate_o_gerador(monkeypatch):
    """O teto, o piso e o preparo do "Encoste" chegam ao gerador como no job.

    ⚠️ Os botoes viajam como `dict` de valores simples (para o pickle e para o
    JSON do diario); o caso confere que eles voltam a ser o que o gerador espera.
    """
    pedidos: list[dict] = []

    def espiao(_dia, **kwargs):
        pedidos.append(kwargs)
        return []

    monkeypatch.setattr(MEDIDOR.gerador_mod, "gerar_candidatos", espiao)
    _, publicacao, _ = MEDIDOR._receita_e_publicacao("quatro_encoste")
    # ⛔ As variantes NO AR (desde 22/10/2026), e nunca uma lista vazia: com a
    # promocao, `candidatas_fora_do_ar` passou a devolver zero, e este laco
    # passava sem rodar nenhuma vez.
    variantes = MEDIDOR.candidatas_do_editorial("quatro_encoste")
    assert len(variantes) == 4
    for candidata in variantes:
        botoes = MEDIDOR.botoes_da_candidata(candidata, publicacao)
        resultado = MEDIDOR.medir_um_dia(
            "quatro_encoste", candidata.parametros, botoes, date(2026, 10, 10), com_regua=True
        )
        # Sem candidato nao ha regua, e o dia fica sem veredito (fora da escada).
        assert resultado == {
            "candidatos": 0, "lances_da_solucao": [], "na_escada": None, "regua": None
        }
        lances = candidata.parametros["lances"]
        assert pedidos[-1]["maximo_de_meios_lances"] == 2 * lances - 1
        assert pedidos[-1]["minimo_de_meios_lances"] == 9
        assert pedidos[-1]["lances_de_preparo"] == 10
        # No ar: o gerador escolhe pelo caminho normal, e exige o vetor.
        assert pedidos[-1]["receita_em_avaliacao"] is None
        recentes = pedidos[-1]["tipos_recentes"]
        assert recentes and "quatro_encoste" not in recentes


def test_os_botoes_com_lista_voltam_a_ser_TUPLA_no_gerador(monkeypatch):
    """Acervo e adversarios: listas no diario, tuplas no gerador (como no job)."""
    pedidos: list[dict] = []

    def espiao(_dia, **kwargs):
        pedidos.append(kwargs)
        return []

    monkeypatch.setattr(MEDIDOR.gerador_mod, "gerar_candidatos", espiao)
    botoes = {
        "preparo": 10, "teto": 9, "piso": 9,
        "moldes": ["a", "b"], "personagens": ["pita", "tex"],
    }
    MEDIDOR.medir_um_dia(
        "quatro_encoste", {"lances": 5, "a_mais": 7}, botoes, date(2026, 10, 1), com_regua=False
    )
    assert pedidos[0]["moldes"] == ("a", "b")
    assert pedidos[0]["personagens_possiveis"] == ("pita", "tex")


#: As duas variantes da rodada falsa. ⚠️ De um tipo FORA do ar (o bloquear,
#: aposentado mas medivel pelo nome), porque so esses o medidor aceita; os
#: numeros sao escritos aqui, e nao lidos do editorial, para o caso nao depender
#: de quantas variantes o tipo tem.
DUAS = (MEDIDOR.Candidata({"ameacas": 2}), MEDIDOR.Candidata({"ameacas": 3}))


def _duas_variantes():
    """As duas variantes, com a forma de `por_tipo`."""
    return [("quatro_bloquear", DUAS)]


def _um_dia_falso(chamadas: list, *, para_na: int | None = None):
    """Um `medir_um_dia` sem motor: a 1a variante cai na escada so no dia 3;
    a 2a, em nenhum - e no dia 4 ela nao gera candidato.

    Args:
        chamadas: onde anotar cada unidade medida.
        para_na: a chamada (contando de 1) em que simula um Ctrl+C.
    """

    def medir_um_dia(co_tipo, parametros, botoes, dia, *, com_regua):
        chamadas.append((parametros["ameacas"], dia.isoformat()))
        if para_na is not None and len(chamadas) == para_na:
            raise KeyboardInterrupt
        primeira = parametros["ameacas"] == 2
        if not primeira and dia.day == 4:
            return {"candidatos": 0, "lances_da_solucao": [], "na_escada": None, "regua": None}
        na_escada = primeira and dia.day == 3
        return {
            "candidatos": 3,
            "lances_da_solucao": [9, 9, 9],
            "na_escada": na_escada,
            "regua": f"      {dia}: {'✅' if na_escada else '⛔'} linha falsa",
        }

    return medir_um_dia


def _rodar(tmp_path):
    """A rodada dos dias 3 e 4 (de 4) com as duas variantes, num processo so."""
    return MEDIDOR.medir_retomavel(
        _duas_variantes(), alvo="quatro_bloquear", nu_dias=4, do_dia=3,
        com_regua=True, processos=1, pasta=tmp_path,
    )


def test_a_rodada_retomavel_GRAVA_uma_linha_por_unidade_e_o_relatorio(monkeypatch, tmp_path):
    """Duas variantes x dois dias = quatro linhas no diario, e o relatorio no arquivo."""
    chamadas: list = []
    monkeypatch.setattr(MEDIDOR, "medir_um_dia", _um_dia_falso(chamadas))

    assert _rodar(tmp_path) == 0

    assert len(chamadas) == 4
    linhas = MEDIDOR.ler_diario(tmp_path / "diario.jsonl")
    assert len(linhas) == 4
    assert {linha["dia"] for linha in linhas} == {"2026-10-03", "2026-10-04"}

    relatorio = (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8")
    # A 1a variante: na escada so no dia 3. A 2a: em nenhum, e o dia 4 sem
    # candidato conta como FORA (na producao e um dia descoberto).
    assert relatorio.count("NA ESCADA em 1 de 2 dias") == 1, relatorio
    assert relatorio.count("NA ESCADA em 0 de 2 dias") == 1, relatorio
    assert "dias 3 a 4" in relatorio
    # O dia mais fraco da 2a variante e o dia sem candidato.
    assert "SEM DESAFIO" in relatorio and "dias [3, 0]" in relatorio, relatorio
    # As linhas da regua saem em ordem de calendario.
    assert relatorio.index("2026-10-03: ✅") < relatorio.index("2026-10-04: ⛔")


def test_rodar_de_novo_NAO_mede_o_que_esta_no_diario(monkeypatch, tmp_path):
    """⛔ O retomar: o mesmo comando, com o diario cheio, nao mede nada."""
    chamadas: list = []
    monkeypatch.setattr(MEDIDOR, "medir_um_dia", _um_dia_falso(chamadas))
    _rodar(tmp_path)
    primeiro = (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8")

    chamadas.clear()
    _rodar(tmp_path)

    assert chamadas == []
    assert len(MEDIDOR.ler_diario(tmp_path / "diario.jsonl")) == 4
    assert (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8") == primeiro


def test_o_ctrl_c_no_meio_perde_SO_a_unidade_em_andamento(monkeypatch, tmp_path):
    """Interrompida na 3a unidade: as duas primeiras ficam, e o retomar mede as outras duas.

    ⚠️ E uma linha cortada no fim do diario (o Ctrl+C no meio do `write`) e pulada.
    """
    chamadas: list = []
    monkeypatch.setattr(MEDIDOR, "medir_um_dia", _um_dia_falso(chamadas, para_na=3))
    with pytest.raises(KeyboardInterrupt):
        _rodar(tmp_path)
    diario = tmp_path / "diario.jsonl"
    assert len(MEDIDOR.ler_diario(diario)) == 2
    with open(diario, "a", encoding="utf-8") as saida:
        saida.write('{"chave": "cortad')

    retomadas: list = []
    monkeypatch.setattr(MEDIDOR, "medir_um_dia", _um_dia_falso(retomadas))
    _rodar(tmp_path)

    assert len(retomadas) == 2
    assert set(retomadas).isdisjoint(chamadas[:2])
    relatorio = (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8")
    assert "NA ESCADA em 1 de 2 dias" in relatorio


def test_linha_de_OUTRA_versao_do_codigo_nao_vale(monkeypatch, tmp_path):
    """⛔ Mudou o codigo, o diario antigo nao responde: tudo e medido de novo, e o relatorio avisa."""
    chamadas: list = []
    monkeypatch.setattr(MEDIDOR, "medir_um_dia", _um_dia_falso(chamadas))
    _rodar(tmp_path)

    monkeypatch.setattr(MEDIDOR, "impressao_do_codigo", lambda: "outra-versao")
    chamadas.clear()
    _rodar(tmp_path)

    assert len(chamadas) == 4
    relatorio = (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8")
    assert "4 linha(s) do diario sao de outra versao do codigo" in relatorio


def test_a_chave_NAO_depende_da_ordem_da_grade():
    """Tirar uma variante da grade nao invalida as medidas das outras."""
    duas = DUAS

    def chaves(candidatas):
        unidades = MEDIDOR.unidades_da_rodada(
            [("quatro_bloquear", candidatas)], nu_dias=2, do_dia=1, com_regua=True, versao="v"
        )
        return {MEDIDOR.chave_da_unidade(u) for u in unidades}

    assert chaves(duas[1:]) <= chaves(duas)
    # Duas variantes x dois dias: quatro chaves diferentes.
    assert len(chaves(duas)) == 4


def test_a_impressao_do_codigo_muda_com_o_codigo(monkeypatch, tmp_path):
    """Conteudo e nome de arquivo de `job/` e `motores/` entram; o resto nao."""
    (tmp_path / "job").mkdir()
    (tmp_path / "motores").mkdir()
    (tmp_path / "job" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "motores" / "b.py").write_text("y = 2\n", encoding="utf-8")
    monkeypatch.setattr(MEDIDOR, "RAIZ", tmp_path)

    antes = MEDIDOR.impressao_do_codigo()
    assert antes == MEDIDOR.impressao_do_codigo() and len(antes) == 16
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "c.py").write_text("z = 3\n", encoding="utf-8")
    assert MEDIDOR.impressao_do_codigo() == antes, "scripts/ nao e o codigo medido"

    (tmp_path / "motores" / "b.py").write_text("y = 3\n", encoding="utf-8")
    depois = MEDIDOR.impressao_do_codigo()
    assert depois != antes
    (tmp_path / "job" / "a.py").rename(tmp_path / "job" / "a2.py")
    assert MEDIDOR.impressao_do_codigo() != depois


def test_o_processo_do_pool_poe_a_regua_em_SERIE(monkeypatch):
    """15 processos x 8 threads seriam 120 motores: no pool, a regua roda em serie."""
    from job import regua

    # `setenv` antes registra o estado original, e o `monkeypatch` o devolve no fim.
    monkeypatch.setenv(regua.ENV_PARALELA, "7")
    MEDIDOR._preparar_processo()
    assert regua.trabalhadores_para("quatro") == 1


def test_com_regua_o_principal_vai_para_a_rodada_RETOMAVEL(monkeypatch):
    """`--com-regua` nao passa pelo `medir` serial, e leva os dias e os processos."""
    pedidos: list[dict] = []

    def retomavel(por_tipo, **kwargs):
        pedidos.append({"tipos": [t for t, _ in por_tipo], **kwargs})
        return 0

    def medir_proibido(*_a, **_k):
        raise AssertionError("a rodada com regua passou pelo caminho serial")

    monkeypatch.setattr(MEDIDOR, "medir_retomavel", retomavel)
    monkeypatch.setattr(MEDIDOR, "medir", medir_proibido)
    assert MEDIDOR.principal(
        ["quatro_bloquear", "--com-regua", "--dias=18", "--do-dia=10", "--processos=3"]
    ) == 0
    assert pedidos == [
        {
            "tipos": ["quatro_bloquear"], "alvo": "quatro_bloquear", "nu_dias": 18,
            "do_dia": 10, "com_regua": True, "processos": 3,
        }
    ]


def test_o_nome_do_relatorio_nao_leva_dois_pontos():
    """O `:` de `no-ar:<tipo>` nao e aceito em nome de arquivo no Windows."""
    assert MEDIDOR.nome_do_relatorio("no-ar:damas_coroar") == "relatorio_no-ar_damas_coroar.txt"
    assert MEDIDOR.nome_do_relatorio("quatro_encoste") == "relatorio_quatro_encoste.txt"


def test_o_piso_ZERO_chega_ao_gerador(monkeypatch):
    """⛔ Zero e um piso legitimo (desligado): `0 or X` o trocaria pelo da publicacao."""
    pedidos: list[dict] = []

    def espiao(_dia, **kwargs):
        pedidos.append(kwargs)
        return []

    monkeypatch.setattr(MEDIDOR.gerador_mod, "gerar_candidatos", espiao)
    _, publicacao, _ = MEDIDOR._receita_e_publicacao("quatro_encoste")
    assert publicacao.nu_minimo_de_meios_lances == 9
    sem_piso = MEDIDOR.Candidata({"lances": 5, "a_mais": 7}, nu_minimo_de_meios_lances=0)
    botoes = MEDIDOR.botoes_da_candidata(sem_piso, publicacao)
    MEDIDOR.medir_um_dia(
        "quatro_encoste", sem_piso.parametros, botoes, date(2026, 10, 1), com_regua=False
    )
    assert pedidos[0]["minimo_de_meios_lances"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# O resultado POR ADVERSARIO (23/10/2026, DECISOES §8zzzs)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ As linhas abaixo sao copiadas do relatorio real do "Forme a figura" (dias 10
# a 18): o adversario e o mascote que a regua NAO cita.

#: Um dia na escada contra o Tex (a linha cita cacau, pita e magno).
LINHA_CONTRA_O_TEX = (
    "      2026-10-10: ✅ candidato 2 de 3 NA ESCADA — cacau 0/10 · pita 3/10 · "
    "magno 9/10 → media 0.40"
)
#: Um dia fora da escada contra a Cacau: a linha tem duas partes, e a segunda
#: cita pita, tex e magno.
LINHA_CONTRA_A_CACAU = (
    "      2026-10-12: ⛔ NENHUM dos 3 na escada — o job publicaria errando por 0.07\n"
    "         pita 0.10 ✅ · tex 0.40 ⛔(-0.05 de [0.45,0.85]) · "
    "magno 0.60 ⛔(-0.15 de [0.75,1.00])"
)


def test_os_mascotes_do_relatorio_sao_os_da_escada():
    """`MASCOTES` e escrito a mao no script (a regua puxa os motores); tem de ser
    a mesma lista, na mesma ordem, da escada que decide."""
    from job import regua as regua_mod

    assert MEDIDOR.MASCOTES == tuple(regua_mod.ESCADA_ALVO)


def test_o_adversario_e_o_mascote_que_a_regua_nao_cita():
    assert MEDIDOR.adversario_da_linha(LINHA_CONTRA_O_TEX) == "tex"
    assert MEDIDOR.adversario_da_linha(LINHA_CONTRA_A_CACAU) == "cacau"
    # Sem linha (dia sem candidato), ou uma linha que nao cita tres mascotes:
    # nao da para dizer, e o dia fica fora da conta por adversario.
    assert MEDIDOR.adversario_da_linha(None) is None
    assert MEDIDOR.adversario_da_linha("      2026-10-03: ✅ linha falsa") is None


def test_por_adversario_conta_dentro_e_total_e_pula_o_dia_sem_candidato():
    resultados = [
        {"na_escada": True, "regua": LINHA_CONTRA_O_TEX},
        {"na_escada": False, "regua": LINHA_CONTRA_A_CACAU},
        {"na_escada": True, "regua": LINHA_CONTRA_O_TEX.replace("2026-10-10", "2026-10-14")},
        # O dia sem candidato: sem regua, fora da conta por adversario.
        {"na_escada": None, "regua": None},
    ]
    assert MEDIDOR.por_adversario(resultados) == {
        "cacau": (0, 1),
        "pita": (0, 0),
        "tex": (2, 2),
        "magno": (0, 0),
    }


def test_o_relatorio_traz_o_por_adversario_e_o_QUADRO(monkeypatch, tmp_path):
    """A 1a variante: dia 3 na escada contra o Tex, dia 4 fora contra a Cacau.
    A 2a: os mesmos adversarios, fora nos dois dias."""

    def medir_um_dia(co_tipo, parametros, botoes, dia, *, com_regua):
        primeira = parametros["ameacas"] == 2
        contra_o_tex = dia.day == 3
        return {
            "candidatos": 3,
            "lances_da_solucao": [9, 9, 9],
            "na_escada": primeira and contra_o_tex,
            "regua": LINHA_CONTRA_O_TEX if contra_o_tex else LINHA_CONTRA_A_CACAU,
        }

    monkeypatch.setattr(MEDIDOR, "medir_um_dia", medir_um_dia)
    _rodar(tmp_path)
    relatorio = (tmp_path / "relatorio_quatro_bloquear.txt").read_text(encoding="utf-8")

    assert "por adversario do dia: cacau 0/1 · pita 0/0 · tex 1/1 · magno 0/0" in relatorio
    assert "por adversario do dia: cacau 0/1 · pita 0/0 · tex 0/1 · magno 0/0" in relatorio
    assert "QUADRO: dias na escada por variante" in relatorio
    # Sem a Cacau sobra o dia contra o Tex: 1 de 1 na 1a, 0 de 1 na 2a.
    assert relatorio.count("sem a Cacau: 1/1") == 1, relatorio
    assert relatorio.count("sem a Cacau: 0/1") == 1, relatorio
    # 1 de 2 nao chega a 2 de 3: nenhuma linha do quadro leva o ✅.
    quadro = relatorio[relatorio.index("QUADRO"):relatorio.index("COMO LER")]
    assert "✅ {" not in quadro, quadro
