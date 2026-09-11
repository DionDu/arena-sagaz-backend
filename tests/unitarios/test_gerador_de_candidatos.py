"""T034 - o gerador de candidatos: as tres escolhas e as duas portas.

⚠️ **A maioria destes testes nao gera desafio nenhum**, e isso e de proposito: a
geracao de verdade roda motor, e um teste que a exercite a cada `pytest` cobraria
segundos de todo mundo por uma garantia que dois casos ja dao.

O que os casos rapidos guardam e o que costuma quebrar sem fazer barulho: o
rodizio deixar de ser deterministico, um tipo sem receita ou sem vetor escapar
para a fila, e o mascote virar o degrau errado da escada.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from job.gerador import (
    EPOCA_DO_RODIZIO,
    JOGOS_DO_RODIZIO,
    MODALIDADES_POR_JOGO,
    PERSONAGENS,
    SemCandidato,
    escolher_jogo,
    escolher_personagem,
    escolher_tipo,
    exigir_vetor,
    gerar_candidatos,
    nivel_do_personagem,
    tipos_com_vetor,
)
from job.tipos_de_desafio import RECEITAS, TipoSemReceita, receita_de, tipos_do_jogo
from motores.nucleo.papeis import NivelDeMotor


# ═══════════════════════════════════════════════════════════════════════════
# 1. As tres escolhas do dia
# ═══════════════════════════════════════════════════════════════════════════


def test_as_escolhas_sao_DETERMINISTICAS() -> None:
    """🔒 Duas execucoes do job para o mesmo dia escolhem a mesma coisa.

    ⚠️ E disso que a idempotencia de T038 depende. Se a escolha fosse sorteada, a
    segunda execucao geraria um desafio diferente, e "rodar duas vezes nao troca o
    publicado" viraria "nao troca porque o `UNIQUE` barrou" — o que e verdade,
    mas deixaria a fila com candidatos orfaos de todo dia.
    """
    dia = date(2026, 9, 15)
    assert escolher_jogo(dia) == escolher_jogo(dia)
    assert escolher_personagem(dia) == escolher_personagem(dia)
    assert escolher_tipo("pontinhos", dia) == escolher_tipo("pontinhos", dia)


def test_o_rodizio_de_jogo_passa_por_todos() -> None:
    """Em dias consecutivos, cada jogo aparece."""
    vistos = {escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) for n in range(8)}
    assert vistos == set(JOGOS_DO_RODIZIO)


def test_o_rodizio_de_personagem_passa_pelos_quatro() -> None:
    """⚠️ O personagem e o NIVEL: a fila precisa variar de dificuldade."""
    vistos = {
        escolher_personagem(EPOCA_DO_RODIZIO + timedelta(days=n)) for n in range(8)
    }
    assert vistos == set(PERSONAGENS)


def test_o_tipo_NAO_repete_o_recente() -> None:
    """Dois dias seguidos de "feche N caixas" fazem o dia parecer o de ontem."""
    dia = date(2026, 9, 15)
    primeiro = escolher_tipo("pontinhos", dia)
    segundo = escolher_tipo("pontinhos", dia, tipos_recentes=[primeiro])
    assert segundo != primeiro


def test_com_TODOS_recentes_o_rodizio_nao_falha() -> None:
    """⚠️ Um jogo com poucos tipos nao pode ficar sem desafio por variedade.

    A regra de nao repetir e sobre a experiencia; ficar sem desafio do dia e sobre
    o produto nao funcionar. A segunda perde.
    """
    dia = date(2026, 9, 15)
    todos = tipos_do_jogo("pontinhos")
    assert escolher_tipo("pontinhos", dia, tipos_recentes=todos) in todos


def test_jogo_sem_tipo_publicavel_falha_ALTO() -> None:
    with pytest.raises(SemCandidato):
        escolher_tipo("velha", date(2026, 9, 15))


@pytest.mark.parametrize(
    "personagem, nivel",
    [
        ("cacau", NivelDeMotor.CACAU),
        ("pita", NivelDeMotor.PITA),
        ("tex", NivelDeMotor.TEX),
        ("magno", NivelDeMotor.SAGAZ),
    ],
)
def test_o_mascote_vira_o_degrau_certo(personagem: str, nivel: NivelDeMotor) -> None:
    """⚠️ **Sagaz e o nome do DEGRAU; Magno e o nome do PERSONAGEM.**

    Os dois vocabularios convivem no projeto desde as damas, e trocar um pelo
    outro e o engano mais comum de quem chega — e ele nao daria erro: so mediria
    a regua com o adversario errado.
    """
    assert nivel_do_personagem(personagem) is nivel


def test_personagem_inventado_falha() -> None:
    with pytest.raises(ValueError):
        nivel_do_personagem("magno_jr")


# ═══════════════════════════════════════════════════════════════════════════
# 2. As duas portas
# ═══════════════════════════════════════════════════════════════════════════


def test_todo_tipo_com_receita_TEM_vetor() -> None:
    """🔒 As duas portas fecham juntas, ou a fila publica o que ninguem confere.

    ⚠️ E este o teste que impede a tentacao de escrever a receita e "acrescentar o
    vetor depois": no intervalo entre as duas, o tipo seria publicavel e a
    divergencia entre Dart e Python nasceria calada.
    """
    com_vetor = tipos_com_vetor()
    sem = sorted(set(RECEITAS) - com_vetor)
    assert not sem, (
        f"tipos com receita e sem vetor de verificacao: {sem}. ⛔ Escreva o vetor "
        "antes de deixar o tipo publicavel."
    )


def test_tipo_sem_vetor_e_RECUSADO() -> None:
    with pytest.raises(SemCandidato, match="vetor"):
        exigir_vetor("damas_final_da_base")


def test_tipo_sem_receita_e_RECUSADO() -> None:
    """⚠️ A alternativa (chegada vazia) daria um desafio impossivel, sem erro."""
    with pytest.raises(TipoSemReceita):
        receita_de("pontinhos_lance_unico")


def test_a_receita_monta_uma_chegada_VALIDA() -> None:
    """O que a receita emite tem de passar pelo avaliador — senao ela e decoracao."""
    from motores.nucleo.chegada import LinhaDeChegada

    parametros = {"caixas": 4, "turnos": 2, "damas": 1, "lances": 3, "pecas": 2}
    for codigo, receita in RECEITAS.items():
        chegada = LinhaDeChegada.de_dado(receita.montar(parametros))
        assert chegada.clausulas, codigo
        # A frase precisa dos valores, e o personagem entra nela.
        valores = receita.valores_da_frase(parametros, "pita")
        assert valores["personagem"] == "pita", codigo


def test_a_chave_do_objetivo_nunca_e_a_frase() -> None:
    """⛔ O aplicativo recebe a CHAVE de i18n, nunca o texto pronto.

    Uma frase gravada no banco viajaria num idioma so — e o app e trilingue desde
    o nascimento.
    """
    for codigo, receita in RECEITAS.items():
        chave = receita.co_chave_objetivo
        assert " " not in chave, f"{codigo}: {chave!r} parece uma frase"
        assert chave.startswith("desafioObjetivo"), codigo


# ═══════════════════════════════════════════════════════════════════════════
# 3. A geracao de verdade — dois casos, e sao caros
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def candidato_de_damas():
    """Gera UM candidato de damas, uma vez para o arquivo inteiro.

    ⚠️ **`scope="module"` nao e detalhe de estilo: e o preco da suite.** Esta
    geracao roda o motor e leva cerca de 30 segundos. Dois testes que a
    repetissem cobrariam um minuto de todo `pytest` do projeto por uma garantia
    que uma geracao ja da — e uma suite lenta e uma suite que se roda menos.
    """
    # ⚠️ **O dia e escolhido pelo TIPO, e nao so pelo jogo.** `damas_coroar` e o
    # tipo cujos moldes foram escritos exatamente para isto — finais com uma
    # branca a poucos passos da oitava fileira.
    #
    # ⛔ `damas_capturar_multipla` **nao serve de fixture**: a geracao dele e
    # dependente da data (a semente sai do dia), e ha dias em que dez tentativas
    # dao zero candidatos. Medido em 10/09/2026. Isso e uma fragilidade real da
    # geracao — e nao deste teste —, e o lugar de resolve-la e nos moldes, nao
    # aqui: um teste que dependesse da sorte do calendario falharia sozinho
    # semanas depois, e ensinaria a ignorar a suite.
    dia = next(
        EPOCA_DO_RODIZIO + timedelta(days=n)
        for n in range(10)
        if escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) == "damas"
        and escolher_tipo("damas", EPOCA_DO_RODIZIO + timedelta(days=n))
        == "damas_coroar"
    )
    # ⚠️ **Os numeros saem do EDITORIAL, e nao sao escritos aqui.** Ate 10/09/2026
    # esta fixture fixava `parametros`, `lances_de_preparo` e `maximo_de_lances` a
    # mao — e no dia em que o rodizio de tipo foi consertado ela passou a gerar
    # outro tipo com os botoes do anterior, e deu zero candidatos. ⛔ O teste
    # estava medindo uma configuracao que a producao nao usa.
    # ⚠️ **A variante e a do DIA, e nao a primeira da lista** (T049f): desde
    # 11/09/2026 cada tipo tem uma lista de variantes de parametros, e medir com
    # a primeira repetiria o defeito que o comentario acima descreve — o teste
    # exercitaria uma configuracao que a producao daquele dia nao usa.
    from job.editorial import variantes_de
    from job.gerador import escolher_variante

    co_tipo = escolher_tipo("damas", dia)
    variantes = variantes_de(co_tipo)
    publicacao = variantes[
        escolher_variante("damas", dia, quantas_variantes=len(variantes))
    ]
    candidatos = gerar_candidatos(
        dia,
        parametros=publicacao.parametros,
        quantos=1,
        tentativas_por_candidato=4,
        lances_de_preparo=publicacao.nu_lances_de_preparo,
        maximo_de_lances=publicacao.nu_maximo_de_lances,
    )
    assert candidatos, (
        "nenhum candidato de damas. ⚠️ Isto guarda a descoberta de 09/09/2026: o "
        "gerador ingenuo (lances aleatorios a partir da abertura) da ZERO "
        "candidatos de damas, e a regressao para ele so apareceria como fila "
        "vazia, dias depois."
    )
    return candidatos[0]


def test_gera_um_candidato_de_damas_a_partir_de_um_MOLDE(candidato_de_damas) -> None:
    """O candidato sai completo: posicao, formato e gabarito.

    ⚠️ **Todo candidato sai com gabarito**, e e essa a prova de que o desafio TEM
    solucao (RF-DES-196). Um desafio sem solucao conhecida nao e publicado.
    """
    candidato = candidato_de_damas
    assert candidato.co_jogo == "damas"
    assert candidato.co_formato_posicao == "fen"
    assert candidato.nu_lances_solucao >= 1
    assert candidato.js_solucao["lances"]
    assert 1 <= candidato.js_solucao["lance_chave"] <= candidato.nu_lances_solucao


def test_o_candidato_gerado_e_JULGADO_como_cumprido_pela_sua_propria_solucao(
    candidato_de_damas,
) -> None:
    """🔒 O fecho do circulo: a solucao publicada resolve o desafio publicado.

    ⚠️ Parece obvio, e nao e: a solucao e achada com uma linha de chegada, e
    gravada ao lado dela. Se as duas se separarem — um parametro lido de um lugar
    e escrito de outro —, o gabarito de D+1 mostraria uma sequencia que nao
    cumpre o objetivo do dia, e ninguem descobriria antes de alguem reclamar.
    """
    from motores.juiz import julgar_desafio

    candidato = candidato_de_damas
    julgamento = julgar_desafio(
        co_jogo=candidato.co_jogo,
        js_posicao_inicial=candidato.js_posicao_inicial,
        js_chegada=candidato.js_chegada,
        fita=candidato.js_solucao["lances"],
        jogador=candidato.js_posicao_inicial["vez_de"],
        co_modalidade=candidato.co_modalidade or "brasileira",
    )
    assert julgamento.cumpriu, (
        f"o gabarito do candidato NAO cumpre a propria linha de chegada: "
        f"{julgamento.veredito} ({julgamento.de_motivo})"
    )


def test_o_rodizio_de_TIPO_nao_fica_travado_em_fase_com_o_de_JOGO() -> None:
    """🔒 O defeito que a primeira execucao real expos (10/09/2026).

    ⛔ `escolher_jogo` usava `dias % 2` e `escolher_tipo` usava `dias % 2`. Um
    jogo so aparece numa das duas paridades de `dias`, entao **para ele o segundo
    `% 2` e constante**: sete dias seguidos escolheram `pontinhos_chegar_ao_placar`
    e `damas_coroar`, e os outros dois tipos publicaveis nunca sairiam.

    ⚠️ **E era quase invisivel:** `tipos_recentes` mascarava metade do sintoma,
    trocando o tipo **so depois** de um dia ter publicado. Nos dias em que a
    geracao falhava, nada entrava em recentes e o mesmo tipo quebrado voltava —
    quatro vezes seguidas, no `des`.

    ⚠️ Este caso roda **sem `tipos_recentes`** de proposito: e assim que se ve o
    rodizio de verdade, e nao o remendo que o mascarava.
    """
    for co_jogo in JOGOS_DO_RODIZIO:
        vistos = {
            escolher_tipo(co_jogo, EPOCA_DO_RODIZIO + timedelta(days=n))
            for n in range(40)
            if escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) == co_jogo
        }
        assert vistos == set(tipos_do_jogo(co_jogo)), (
            f"o rodizio de {co_jogo} so produziu {sorted(vistos)} em 40 dias; os "
            f"publicaveis sao {tipos_do_jogo(co_jogo)}. ⛔ Rodizio travado em fase."
        )


# ═══════════════════════════════════════════════════════════════════════════
# O rodizio de MODALIDADE (decisao do dono, 10/09/2026)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_modalidade_e_o_tipo_NAO_travam_em_fase() -> None:
    """🔒 O mesmo defeito do rodizio de tipo, um andar acima.

    ⛔ Se a modalidade usasse `vez_do_jogo % 4` enquanto o tipo usa
    `vez_do_jogo % 2`, os dois andariam juntos: o tipo par so sairia com as
    modalidades pares, e **metade das combinacoes nunca apareceria**.

    ⚠️ E seria mais dificil de ver que o anterior: a fila pareceria variada —
    tipos alternando, modalidades alternando — e so uma contagem revelaria que
    metade dos pares nunca sai.
    """
    from job.gerador import escolher_modalidade

    for co_jogo, modalidades in MODALIDADES_POR_JOGO.items():
        if not modalidades:
            continue
        pares = {
            (
                escolher_tipo(co_jogo, EPOCA_DO_RODIZIO + timedelta(days=n)),
                escolher_modalidade(co_jogo, EPOCA_DO_RODIZIO + timedelta(days=n)),
            )
            for n in range(200)
            if escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) == co_jogo
        }
        esperados = len(tipos_do_jogo(co_jogo)) * len(modalidades)
        assert len(pares) == esperados, (
            f"{co_jogo}: so {len(pares)} das {esperados} combinacoes "
            f"(tipo x modalidade) aparecem em 200 dias. ⛔ Travamento em fase."
        )


def test_jogo_SEM_modalidade_devolve_None() -> None:
    """⚠️ E `None`, e nao `"brasileira"`: o Pontinhos nao tem regulamento.

    Um padrao aqui poria `modalidade` no enunciado de um jogo que nao tem uma, e
    a frase falaria de uma regra inexistente.
    """
    from job.gerador import escolher_modalidade

    assert escolher_modalidade("pontinhos", EPOCA_DO_RODIZIO) is None


def test_o_MOTOR_nasce_com_a_modalidade_do_candidato(candidato_de_damas) -> None:
    """🔒 ⛔ O defeito que nao daria erro nenhum.

    `MotorDamas()` tem `brasileira` por padrao. Se a bancada de medicao o
    construisse sem a modalidade, a regua mediria por um regulamento enquanto o
    desafio publicado diria outro — ⚠️ **e os dois lados seriam internamente
    coerentes**. A divergencia so apareceria no aparelho de quem jogasse, como
    "lance ilegal" num gabarito que o servidor jurava valido.

    E a mesma classe do `uid` do Firebase: tipo errado que atravessa tudo calado.
    """
    from job.gerador import bancada

    esperada = candidato_de_damas.co_modalidade
    assert esperada, "o candidato de damas saiu sem modalidade"
    banc = bancada(candidato_de_damas)
    assert banc.jogador.co_modalidade == esperada, (
        "a bancada montou o motor com um regulamento diferente do publicado"
    )


def test_o_enunciado_carrega_ONDE_e_COMO_se_joga(candidato_de_damas) -> None:
    """⚠️ Decisao do dono: a modalidade entra em `js_objetivo`.

    ⛔ Sem ela, quem so joga brasileira receberia regras anglo — pedra sem
    captura para tras, coroacao encerrando o lance, as pretas comecando — e
    concluiria que o aplicativo esta quebrado.
    """
    js = candidato_de_damas.js_objetivo
    assert js["modalidade"] == candidato_de_damas.co_modalidade
    assert js["variante"] == candidato_de_damas.co_variante


def test_a_variante_das_damas_ACOMPANHA_a_modalidade(candidato_de_damas) -> None:
    """🔒 `co_variante` das damas usa o vocabulario de `partida.tb001`.

    ⚠️ E la o aplicativo grava a modalidade (`coVariante: config.modalidade`); a
    migracao `0012` diz o mesmo. Um rotulo fixo `"brasileiras"` faria o desafio
    sair com `variante: brasileiras` ao lado de `modalidade: casa`, e ⛔ um
    `JOIN` com o log de partidas nunca casaria.
    """
    assert candidato_de_damas.co_variante == candidato_de_damas.co_modalidade


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ T049f — o TERCEIRO DIGITO do odometro, e a armadilha que ja pegou duas vezes
# ═══════════════════════════════════════════════════════════════════════════


def _combinacoes_em(dias: int) -> set[tuple[str, str, str | None, int]]:
    """Todas as `(jogo, tipo, modalidade, variante)` que saem em `dias` dias."""
    from job.editorial import variantes_de
    from job.gerador import escolher_modalidade, escolher_variante

    vistas: set[tuple[str, str, str | None, int]] = set()
    for n in range(dias):
        dia = EPOCA_DO_RODIZIO + timedelta(days=n)
        co_jogo = escolher_jogo(dia)
        co_tipo = escolher_tipo(co_jogo, dia)
        vistas.add(
            (
                co_jogo,
                co_tipo,
                escolher_modalidade(co_jogo, dia),
                escolher_variante(
                    co_jogo, dia, quantas_variantes=len(variantes_de(co_tipo))
                ),
            )
        )
    return vistas


def test_o_odometro_de_TRES_digitos_cobre_TODAS_as_combinacoes() -> None:
    """🔒 ⛔ A armadilha da fase, pela terceira vez — e agora com cadeado.

    ⚠️ **Duas vezes em 10/09/2026 o mesmo erro apareceu:** primeiro `dias % 2`
    escolhendo o jogo **e** o tipo (sete dias seguidos com o mesmo tipo), depois a
    modalidade quase usando o contador do tipo (metade das combinacoes nunca
    sairia). ⚠️ **O segundo seria pior de enxergar:** a fila *pareceria* variada,
    com tipos e modalidades alternando, e so uma contagem revelaria os ausentes.

    Este caso e a contagem. Ele conta o **produto** esperado — tipos x
    modalidades x variantes de cada tipo — e exige que todos saiam.
    """
    from job.editorial import variantes_de
    from job.gerador import MODALIDADES_POR_JOGO

    esperadas = 0
    for co_jogo in JOGOS_DO_RODIZIO:
        quantas_modalidades = max(1, len(MODALIDADES_POR_JOGO.get(co_jogo, ())))
        for co_tipo in tipos_do_jogo(co_jogo):
            esperadas += quantas_modalidades * len(variantes_de(co_tipo))

    # 400 dias dao ~200 aparicoes de cada jogo — folga suficiente para o digito
    # mais lento (a variante das damas, que anda a cada 8 aparicoes) dar voltas.
    vistas = _combinacoes_em(400)
    assert len(vistas) == esperadas, (
        f"saem {len(vistas)} combinacoes, e deveriam sair {esperadas}. ⛔ Algum "
        "digito do odometro anda EM FASE com outro, e uma fatia das combinacoes "
        f"nunca aparece. Vistas: {sorted(vistas)}"
    )


def test_a_variante_NAO_anda_em_fase_com_o_tipo() -> None:
    """🔒 O sintoma especifico: cada tipo precisa ver TODAS as suas variantes.

    ⚠️ Se a variante usasse `vez_do_jogo` (o contador do tipo), um tipo so
    apareceria com as variantes de uma paridade — e o teste da contagem acima
    pegaria, mas sem dizer **qual** digito quebrou. Este diz.
    """
    from job.editorial import variantes_de

    por_tipo: dict[str, set[int]] = {}
    for _co_jogo, co_tipo, _co_modalidade, nu_variante in _combinacoes_em(400):
        por_tipo.setdefault(co_tipo, set()).add(nu_variante)

    for co_tipo, vistas in por_tipo.items():
        assert vistas == set(range(len(variantes_de(co_tipo)))), (
            f"o tipo {co_tipo!r} so viu as variantes {sorted(vistas)}, e tem "
            f"{len(variantes_de(co_tipo))}"
        )


def test_a_variante_NAO_anda_em_fase_com_a_MODALIDADE() -> None:
    """🔒 O outro sintoma: cada modalidade precisa ver todas as variantes.

    ⚠️ E o engano que quase aconteceu com a modalidade em 10/09/2026, agora um
    digito adiante: se a variante dividisse so por `quantos_tipos`, ela giraria
    junto com a modalidade, e ⛔ **as damas publicariam sempre a mesma variante em
    cada regulamento** — com a fila parecendo variada.
    """
    from job.editorial import variantes_de

    por_par: dict[tuple[str, str | None], set[int]] = {}
    for _co_jogo, co_tipo, co_modalidade, nu_variante in _combinacoes_em(400):
        por_par.setdefault((co_tipo, co_modalidade), set()).add(nu_variante)

    for (co_tipo, co_modalidade), vistas in por_par.items():
        assert vistas == set(range(len(variantes_de(co_tipo)))), (
            f"{co_tipo!r}/{co_modalidade!r} so viu as variantes {sorted(vistas)}"
        )


def test_a_variante_e_DETERMINISTICA() -> None:
    """⚠️ A idempotencia de T038 nao pode passar a depender de sorte.

    Duas execucoes do job para o mesmo dia precisam gerar o mesmo desafio — e se
    a variante fosse sorteada, os parametros mudariam entre elas.
    """
    from job.gerador import escolher_variante

    dia = date(2026, 9, 20)
    assert escolher_variante("pontinhos", dia, quantas_variantes=4) == (
        escolher_variante("pontinhos", dia, quantas_variantes=4)
    )


def test_tipo_com_UMA_variante_sempre_devolve_zero() -> None:
    """As damas hoje — enquanto as candidatas nao forem medidas.

    ⛔ E um `% 1` daria zero de qualquer jeito; o atalho existe para o Pontinhos
    nao dividir por `len(MODALIDADES) == 0`.
    """
    from job.gerador import escolher_variante

    for n in range(30):
        dia = EPOCA_DO_RODIZIO + timedelta(days=n)
        assert escolher_variante("damas", dia, quantas_variantes=1) == 0


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A POSICAO QUE VAI AO AR NAO SE RESOLVE NO PRIMEIRO TOQUE
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Os moldes ja passam por `moldes_triviais` (T049g), e mesmo assim a primeira
# execucao real no Railway publicou um desafio de UM lance: o que vai ao ar e o
# molde **mais um lance de variacao**, e ninguem perguntava nada sobre o
# resultado dessa soma.


def test_a_posicao_do_candidato_NAO_se_resolve_no_PRIMEIRO_TOQUE(
    candidato_de_damas,
) -> None:
    """🔒 A pergunta feita sobre o que o job realmente publica.

    ⚠️ **De graca:** usa a fixture de modulo, entao nao gera nada de novo.
    """
    from job.moldes_de_damas import objetivo_no_primeiro_lance

    candidato = candidato_de_damas
    fen = candidato.js_posicao_inicial["fen"]
    lance = objetivo_no_primeiro_lance(
        fen, candidato.receita.co_tipo_desafio, candidato.co_modalidade
    )
    assert lance is None, (
        f"o candidato publicaria {fen}, onde {lance} cumpre o objetivo sozinho — "
        "um desafio de um toque, com regua, XP e gabarito bem formados"
    )


def test_o_gerador_RECUSA_toda_posicao_trivial_em_vez_de_publicar(monkeypatch) -> None:
    """🔒 O controle positivo: com TODA posicao trivial, nada e publicado.

    ⛔ Sem este caso, o de cima poderia estar verde por sorte — os moldes de hoje
    raramente produzem uma variacao trivial, e um `continue` apagado por engano
    so apareceria meses depois, num dia de captura.

    ⚠️ **A posicao forcada aqui e a de producao** (`72542794`, 11/09/2026): as
    pretas capturam duas de uma vez com `21x30x23`.
    """
    from job import gerador as gerador_mod
    from motores.damas.motor_damas import EstadoDamas

    trivial = "B:W25,26,29:B16,17,18,21"

    def sempre_trivial(*_args, **kwargs):
        return EstadoDamas(
            co_modalidade=kwargs.get("co_modalidade", "brasileira"),
            fen_inicial=trivial,
        )

    monkeypatch.setattr(gerador_mod, "_preparar_damas", sempre_trivial)

    dia = next(
        EPOCA_DO_RODIZIO + timedelta(days=n)
        for n in range(10)
        if escolher_jogo(EPOCA_DO_RODIZIO + timedelta(days=n)) == "damas"
        and escolher_tipo("damas", EPOCA_DO_RODIZIO + timedelta(days=n))
        == "damas_capturar_multipla"
    )
    candidatos = gerador_mod.gerar_candidatos(
        dia,
        parametros={"pecas": 2, "lances": 4},
        quantos=1,
        tentativas_por_candidato=2,
        lances_de_preparo=8,
        maximo_de_lances=8,
    )
    assert candidatos == [], (
        "com todas as posicoes triviais o gerador tem de voltar de maos vazias — "
        "o dia cai na reprise, que e o caminho previsto. ⛔ Publicar um desafio "
        "de um toque nao e uma alternativa aceitavel a um dia sem desafio."
    )


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ QUEM RESOLVE O DESAFIO E O JOGADOR 1 — EM TODO JOGO
# ═══════════════════════════════════════════════════════════════════════════


def test_o_solucionador_das_damas_e_o_JOGADOR_1(candidato_de_damas) -> None:
    """🔒 A regra canonica do projeto, aplicada a posicao publicada.

    ⚠️ `CLAUDE.md`: *"jogador 1 = AZUL e jogador 2 = VERMELHO. Sempre. Em todos
    os modos e em todos os jogos (...) No modo contra a CPU, o humano e o Jogador
    1 (azul)"*.

    ⛔ Ate 11/09/2026 todo desafio de damas saiu com `vez_de: -1`, porque a
    variacao a partir do molde era de **um** lance e cada lance troca o lado. O
    dono viu o efeito no painel: *"no App eu sou sempre as pecas e arestas azuis;
    nas damas o humano sempre joga com as pecas iniciando na parte de baixo do
    tabuleiro, nao no topo"*.

    ⚠️ E a posicao no tabuleiro vem junto: as brancas sao as de baixo, entao
    exigir `W:` e exigir que a pessoa jogue de baixo para cima, como no jogo
    normal.
    """
    posicao = candidato_de_damas.js_posicao_inicial
    assert posicao["vez_de"] == 1, (
        "a pessoa tem de resolver o desafio como jogador 1 (azul); veio "
        f"{posicao['vez_de']}"
    )
    assert posicao["fen"].startswith("W:"), (
        f"a FEN publicada tem de ter as brancas a jogar; veio {posicao['fen']}"
    )


def test_o_PONTINHOS_tambem_publica_com_o_jogador_1() -> None:
    """🔒 O irmao do caso acima, que ja passava — e e por isso que entra.

    ⚠️ **Metade da fila estava certa**, e foi isso que escondeu o defeito das
    damas: quem olhasse um desafio de Pontinhos veria tudo no lugar.
    """
    from job.posicao_inicial import do_pontinhos

    js = do_pontinhos(["H_0_1", "V_1_0"])
    assert js["vez_de"] == 1
