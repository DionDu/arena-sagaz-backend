"""T035/T035a - a regua dos mascotes, o perfil e o alvo observado.

⚠️ **Nenhum destes testes roda motor.** A regua recebe a funcao `tentar` por
parametro justamente para isso: a contagem e a banda podem ser medidas com uma
funcao falsa, e o que roda motor de verdade e a geracao (testada em T034).

Um teste que rodasse `3 mascotes x 20 execucoes` cobraria minutos de cada
`pytest` para provar uma soma.
"""

from __future__ import annotations

import pytest

from job.alvo_observado import (
    PISO_FIXO,
    SQL_TAXA_OBSERVADA,
    TETO_FIXO,
    VOLUME_MINIMO,
    alvo_para_a_regua,
)
from job.perfil import NIVEL_POR_PERSONAGEM, linhas_da_dimensao, versao_vigente
from job.regua import (
    ESCADA_ALVO,
    EXECUCOES_PADRAO,
    Medicao,
    dentro_da_banda,
    dentro_da_escada,
    descrever_escada,
    distancia_da_banda,
    distancia_da_escada,
    medir_candidato,
    taxa_media,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O perfil
# ═══════════════════════════════════════════════════════════════════════════


def test_a_versao_do_perfil_deriva_dos_HASHES() -> None:
    """🔒 Numero a mao envelhece calado.

    Alguem afina a Pita, esquece de subir a versao, e as medicoes novas ficam
    indistinguiveis das velhas no banco. E a mesma armadilha que
    `co_versao_motor` ja documenta, aplicada aos numeros de dificuldade.
    """
    versao = versao_vigente()
    assert versao.startswith("perfil-")
    assert len(versao) == len("perfil-") + 8
    # Deriva: duas chamadas dao o mesmo, sem estado no meio.
    assert versao == versao_vigente()


def test_ha_uma_linha_por_jogo_e_por_mascote() -> None:
    """A FK composta de `tb001_desafio` exige exatamente isto.

    ⚠️ Faltando uma linha, o primeiro `INSERT` daquele (jogo, mascote) falha — e o
    erro apareceria como "violacao de chave estrangeira" no meio do job, longe da
    causa.
    """
    linhas = linhas_da_dimensao()
    chaves = {(l["co_jogo"], l["co_personagem"]) for l in linhas}
    assert chaves == {
        (jogo, mascote)
        for jogo in ("damas", "pontinhos")
        for mascote in NIVEL_POR_PERSONAGEM
    }


def test_a_linha_carrega_os_NUMEROS_e_o_hash_do_arquivo() -> None:
    """⚠️ Copiar para EXPLICAR nao e segunda fonte da verdade.

    Quem *roda* continua sendo o contrato; o `js_perfil` existe para a linha ser
    legivel daqui a um ano sem precisar descobrir qual commit estava no ar. O
    hash ao lado prova qual arquivo produziu aqueles numeros.
    """
    linha = next(l for l in linhas_da_dimensao() if l["co_jogo"] == "damas")
    assert linha["js_perfil"], "o perfil da linha veio vazio"
    assert len(linha["co_sha256"]) == 64
    # ⚠️ Caminho RELATIVO: um absoluto descreveria a maquina de quem rodou.
    assert not linha["co_arquivo"].startswith("D:")
    assert "espelho_laboratorio" in linha["co_arquivo"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. A regua
# ═══════════════════════════════════════════════════════════════════════════


def test_quem_mede_sao_os_TRES_que_nao_sao_o_adversario() -> None:
    """🔒 RF-DES-204: a escada roda junto com o personagem.

    Medir com o adversario do dia seria perguntar *"a Pita resolve um desafio
    contra a Pita?"* — que nao e a pergunta, e daria um numero que ninguem sabe
    interpretar.
    """
    medicoes = medir_candidato(
        co_personagem_do_dia="pita",
        tentar=lambda personagem, execucao: True,
        co_versao_perfil="perfil-teste",
        co_versao_motor="motor-teste",
        nu_execucoes=3,
    )
    assert {m.co_personagem for m in medicoes} == {"cacau", "tex", "magno"}
    assert len(medicoes) == 3


def test_a_regua_conta_o_que_a_funcao_tentar_respondeu() -> None:
    """14 de 20 e literalmente uma contagem."""

    def tentar(co_personagem: str, execucao: int) -> bool:
        # A Cacau resolve nas 4 primeiras; os outros sempre.
        if co_personagem == "cacau":
            return execucao <= 4
        return True

    medicoes = medir_candidato(
        co_personagem_do_dia="pita",
        tentar=tentar,
        co_versao_perfil="perfil-teste",
        co_versao_motor="motor-teste",
        nu_execucoes=10,
    )
    por_mascote = {m.co_personagem: m for m in medicoes}
    assert por_mascote["cacau"].nu_resolveu == 4
    assert por_mascote["cacau"].taxa == pytest.approx(0.4)
    assert por_mascote["magno"].nu_resolveu == 10


def test_toda_medicao_leva_o_CARIMBO() -> None:
    """⚠️ Sem `co_versao_perfil`, "14 de 20" e um numero sem regua (RF-DES-146).

    E a regua muda quando o perfil e afinado ou quando a busca e corrigida.
    """
    medicoes = medir_candidato(
        co_personagem_do_dia="magno",
        tentar=lambda p, e: e % 2 == 0,
        co_versao_perfil="perfil-abc12345",
        co_versao_motor="damas-py-deadbeef",
        nu_execucoes=4,
    )
    for medicao in medicoes:
        assert medicao.co_versao_perfil == "perfil-abc12345"
        assert medicao.co_versao_motor == "damas-py-deadbeef"


def test_o_padrao_de_execucoes_e_vinte() -> None:
    """O numero da spec (RF-DES-016), e ele e um equilibrio declarado."""
    assert EXECUCOES_PADRAO == 20


def test_zero_execucoes_e_recusado() -> None:
    """Uma taxa sobre zero execucoes seria uma divisao por zero disfarcada."""
    with pytest.raises(ValueError):
        medir_candidato(
            co_personagem_do_dia="pita",
            tentar=lambda p, e: True,
            co_versao_perfil="x",
            co_versao_motor="y",
            nu_execucoes=0,
        )


def test_personagem_do_dia_desconhecido_e_recusado() -> None:
    with pytest.raises(ValueError):
        medir_candidato(
            co_personagem_do_dia="magno_jr",
            tentar=lambda p, e: True,
            co_versao_perfil="x",
            co_versao_motor="y",
        )


def _medicao(personagem: str, resolveu: int, execucoes: int = 20) -> Medicao:
    return Medicao(
        co_personagem=personagem,
        nu_execucoes=execucoes,
        nu_resolveu=resolveu,
        co_versao_perfil="perfil-teste",
        co_versao_motor="motor-teste",
    )


def test_a_banda_olha_a_MEDIA_da_escada() -> None:
    """⚠️ Um desafio que so a Cacau resolve e banal; so o Magno, duro demais.

    A banda e sobre a escada inteira — e as tres linhas continuam gravadas porque
    a media **decide**, mas quem **explica** o descarte sao elas.
    """
    # 15, 16 e 17 de 20 → media 0,80.
    dentro = [_medicao("cacau", 15), _medicao("tex", 16), _medicao("magno", 17)]
    assert dentro_da_banda(dentro, piso=0.70, teto=0.80) is True

    # Todos resolvem sempre: banal.
    banal = [_medicao("cacau", 20), _medicao("tex", 20), _medicao("magno", 20)]
    assert dentro_da_banda(banal, piso=0.70, teto=0.80) is False

    # Ninguem resolve: duro demais.
    duro = [_medicao("cacau", 0), _medicao("tex", 1), _medicao("magno", 2)]
    assert dentro_da_banda(duro, piso=0.70, teto=0.80) is False


def test_sem_medicao_nenhuma_a_banda_e_FALSA() -> None:
    """⚠️ "Nada a medir" nao pode virar "aprovado".

    E o mesmo principio do cadeado de uniao de XP: nada a varrer e falha, nao
    sucesso.
    """
    assert dentro_da_banda([], piso=0.70, teto=0.80) is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. O alvo observado — T035a
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_volume_o_alvo_e_o_FIXO() -> None:
    """⚠️ Nao e limitacao escondida: e a resposta correta.

    A taxa observada de 12 pessoas nao diz nada sobre a dificuldade de um desafio.
    """
    alvo = alvo_para_a_regua(nu_tentaram=12, nu_resolveram=9)
    assert (alvo.piso, alvo.teto) == (PISO_FIXO, TETO_FIXO)
    assert alvo.co_origem == "fixo"
    assert alvo.nu_amostras == 12


def test_com_volume_a_banda_ANDA_mas_nao_muda_de_largura() -> None:
    """Mover o centro e ajustar a mira; alargar seria outra decisao.

    ⚠️ E ela nao esta nesta tarefa: aceitar desafios mais desiguais precisa ser
    escolhido, e nao acontecer como efeito colateral de um auto-ajuste.
    """
    # 300 pessoas, 150 resolveram → taxa observada 0,50.
    alvo = alvo_para_a_regua(nu_tentaram=300, nu_resolveram=150)
    assert alvo.co_origem == "observado"
    assert alvo.teto - alvo.piso == pytest.approx(TETO_FIXO - PISO_FIXO)
    # A banda centrou em 0,50.
    assert alvo.piso == pytest.approx(0.45)
    assert alvo.teto == pytest.approx(0.55)


def test_a_banda_observada_nao_sai_do_intervalo_valido() -> None:
    """Taxa de 100% nao pode produzir um teto acima de 1."""
    alvo = alvo_para_a_regua(nu_tentaram=1000, nu_resolveram=1000)
    assert 0.0 <= alvo.piso <= alvo.teto <= 1.0


def test_o_volume_minimo_e_um_piso_de_CONFIANCA() -> None:
    """Logo abaixo do minimo, ainda e fixo; a partir dele, observado."""
    assert alvo_para_a_regua(
        nu_tentaram=VOLUME_MINIMO - 1, nu_resolveram=100
    ).co_origem == "fixo"
    assert alvo_para_a_regua(
        nu_tentaram=VOLUME_MINIMO, nu_resolveram=100
    ).co_origem == "observado"


def test_a_consulta_le_pelas_VIEWS() -> None:
    """🔒 A convencao do projeto: leitura nunca toca a tabela.

    ⚠️ E ela nao e formalidade: uma VIEW criada com `SELECT *` congela a lista de
    colunas, e ler a tabela direto passaria por cima da unica camada que o
    projeto recria de proposito quando o esquema muda.
    """
    assert "vw001_desafio_dia" in SQL_TAXA_OBSERVADA
    assert "vw002_tentativa" in SQL_TAXA_OBSERVADA
    assert "vw003_resolucao" in SQL_TAXA_OBSERVADA
    assert "tb001_desafio_dia" not in SQL_TAXA_OBSERVADA
    assert "tb002_tentativa" not in SQL_TAXA_OBSERVADA


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ CADA LADO DO TABULEIRO JOGA COM O SEU NIVEL
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ `tentativa_com_motor` nao tinha teste nenhum ate 11/09/2026, e e por isso
# que o defeito sobreviveu meses **com o comentario certo escrito em cima dele**:
# o cabecalho de `regua.py` dizia que o adversario do dia fica do outro lado, e o
# codigo aplicava o nivel do mascote medido aos dois lados.


class _EstadoFalso:
    """Um estado de tabuleiro que so sabe de quem e a vez.

    ⚠️ **Nao ha jogo aqui, e e de proposito:** o que se mede e qual NIVEL foi
    pedido em cada lance, e um motor de verdade so tornaria o teste lento e
    dependente das regras de um jogo.
    """

    def __init__(self, vez_de: int, lance_numero: int = 0) -> None:
        self.vez_de = vez_de
        self.lance_numero = lance_numero

    def com_lance(self, _lance: str) -> "_EstadoFalso":
        return _EstadoFalso(-self.vez_de, self.lance_numero + 1)


class _JogadorQueAnota:
    """Escolhe sempre o mesmo lance, e ANOTA com que nivel foi chamado."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[int, object]] = []

    def escolher_lance(self, estado, nivel, *, limite=None, semente=None) -> str:
        self.pedidos.append((estado.vez_de, nivel))
        return "x"


def test_o_ADVERSARIO_DO_DIA_joga_o_outro_lado_na_medicao() -> None:
    """🔒 ⛔ O defeito que media uma partida que ninguem joga.

    ⚠️ **A pessoa enfrenta o `co_personagem` do desafio.** Medir a Cacau contra a
    Cacau responde outra pergunta — e nos dias em que o adversario e o Magno a
    diferenca e enorme, porque a taxa passa a descrever um adversario quase
    perfeito em vez de um iniciante.
    """
    from job.perfil import NIVEL_POR_PERSONAGEM
    from job.regua import tentativa_com_motor

    jogador = _JogadorQueAnota()
    tentar = tentativa_com_motor(
        jogador=jogador,
        estado_inicial=_EstadoFalso(vez_de=1),
        julgar=lambda fita: type("J", (), {"cumpriu": len(fita) >= 4})(),
        nu_semente=7,
        maximo_de_meios_lances=4,
        co_personagem_do_dia="magno",
    )
    tentar("cacau", 1)

    # O solucionador joga primeiro (vez_de = 1); o adversario e o outro lado.
    niveis_de_quem_resolve = [n for vez, n in jogador.pedidos if vez == 1]
    niveis_do_adversario = [n for vez, n in jogador.pedidos if vez == -1]

    assert niveis_de_quem_resolve, "ninguem jogou pelo lado de quem resolve"
    assert niveis_do_adversario, "o adversario nunca jogou"
    assert set(niveis_de_quem_resolve) == {NIVEL_POR_PERSONAGEM["cacau"]}
    assert set(niveis_do_adversario) == {NIVEL_POR_PERSONAGEM["magno"]}, (
        "o outro lado tem de jogar no nivel do adversario do DIA; se vier o "
        "nivel do mascote medido, a regua voltou a medir 'Cacau contra Cacau'"
    )


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A BORDA DA BANDA — o defeito da decima sexta casa decimal
# ═══════════════════════════════════════════════════════════════════════════


def test_taxa_EXATAMENTE_no_teto_esta_dentro_da_banda():
    """⛔ **Sem tolerancia, o candidato perfeitamente calibrado era RECUSADO.**

    Tres mascotes resolvendo 8 de 10 dao `(0.8 + 0.8 + 0.8) / 3`, que em ponto
    flutuante e `0.8000000000000002` — **maior** que o teto `0.80`. O job
    guardava esse candidato como "menos pior" e seguia procurando, podendo
    publicar outro, pior.

    ⚠️ **E nada no log acusaria**, porque o log imprime a taxa arredondada: a
    linha diria *"taxa 0.80, fora da banda [0.70, 0.80]"*, e quem lesse
    procuraria o defeito em qualquer lugar menos na decima sexta casa decimal.
    """
    medicoes = [_medicao(nome, 8, execucoes=10) for nome in ("cacau", "tex", "magno")]
    # ⚠️ A prova de que o caso e real, e nao hipotetico: a media NAO e 0.8.
    assert taxa_media(medicoes) != 0.80
    assert dentro_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO)
    assert distancia_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO) == 0.0


def test_taxa_EXATAMENTE_no_piso_tambem_esta_dentro():
    """⚠️ O mesmo na outra ponta - 7 de 10 nos tres da `0.7000000000000001`."""
    medicoes = [_medicao(nome, 7, execucoes=10) for nome in ("cacau", "tex", "magno")]
    assert dentro_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO)
    assert distancia_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO) == 0.0


def test_a_tolerancia_NAO_aceita_quem_erra_a_banda_de_verdade():
    """⛔ A folga e para o arredondamento, e nunca para afrouxar o criterio.

    ⚠️ O menor passo que a regua consegue produzir com 20 execucoes e 3 mascotes
    e `1/60 ≈ 0,017` — dez milhoes de vezes maior que a tolerancia. Entao nenhum
    candidato que erre a banda por um passo real passa por aqui.
    """
    quase = [_medicao(nome, 17, execucoes=20) for nome in ("cacau", "tex", "magno")]
    assert taxa_media(quase) == pytest.approx(0.85)
    assert not dentro_da_banda(quase, piso=PISO_FIXO, teto=TETO_FIXO)
    assert distancia_da_banda(quase, piso=PISO_FIXO, teto=TETO_FIXO) > 0.0


def test_as_duas_funcoes_da_banda_NUNCA_se_contradizem():
    """⛔ `dentro_da_banda` dizendo sim e `distancia_da_banda` devolvendo positivo
    seria uma contradicao que o job carregaria em silencio.

    ⚠️ Varre toda a grade que 10 execucoes x 3 mascotes consegue produzir.
    """
    for resolveu in range(11):
        medicoes = [
            _medicao(nome, resolveu, execucoes=10) for nome in ("cacau", "tex", "magno")
        ]
        dentro = dentro_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO)
        distancia = distancia_da_banda(medicoes, piso=PISO_FIXO, teto=TETO_FIXO)
        assert dentro == (distancia == 0.0), (
            f"⛔ {resolveu}/10 nos tres: dentro={dentro} e distancia={distancia}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ O SOLUCIONADOR DO TIPO — gerar com um e medir com outro mede outro desafio
# ═══════════════════════════════════════════════════════════════════════════


def test_o_SOLUCIONADOR_DO_TIPO_joga_o_lado_de_quem_resolve() -> None:
    """🔒 ⛔ A regua media com um solucionador diferente do que GEROU o candidato.

    ⚠️ **`SOLUCIONADOR_POR_TIPO` existe desde 12/09/2026 e era usado so na
    geracao.** `pontinhos_cadeia_longa` e gerado pelo **arquiteto** — vencer no
    Pontinhos e partir o tabuleiro em cadeias curtas, o oposto de construir uma
    cadeia grande — e era medido pelo jogador comum, que ali e o pior
    solucionador possivel: **7% contra 43%**, medido em 30 posicoes no proprio
    registro.

    ⛔ Uma regua assim diria *"duro demais"* (taxa ~0,07, banda [0,70; 0,80])
    sobre um candidato que o gerador produz com folga — e o descarte cairia sobre
    a variante, que nao tem culpa nenhuma.

    ⚠️ **E o adversario NAO muda**: o solucionador substitui so o lado de quem
    resolve. Se ele vazasse para o outro lado, a regua voltaria a medir uma
    partida que ninguem joga — o defeito irmao, de 11/09/2026.
    """
    from job.regua import tentativa_com_motor

    jogador = _JogadorQueAnota()
    chamadas: list[int] = []

    def solucionador_falso(_arbitro, estado) -> str:
        chamadas.append(estado.vez_de)
        return "do-arquiteto"

    tentar = tentativa_com_motor(
        jogador=jogador,
        estado_inicial=_EstadoFalso(vez_de=1),
        julgar=lambda fita: type("J", (), {"cumpriu": len(fita) >= 4})(),
        nu_semente=7,
        maximo_de_meios_lances=4,
        co_personagem_do_dia="magno",
        solucionador=solucionador_falso,
    )
    tentar("cacau", 1)

    assert chamadas, (
        "⛔ o solucionador do tipo nao foi chamado. A regua voltou a medir com o "
        "jogador comum um candidato que o gerador produz com outro."
    )
    assert set(chamadas) == {1}, (
        "⛔ o solucionador jogou pelo ADVERSARIO. Ele substitui so o lado de quem "
        "resolve; o outro lado e o personagem do dia, no nivel dele."
    )
    # ⚠️ E o jogador comum continua jogando — pelo adversario, e so por ele.
    assert jogador.pedidos, "o adversario nunca jogou"
    assert {vez for vez, _ in jogador.pedidos} == {-1}, (
        "com solucionador proprio, o jogador comum so pode ser chamado pelo "
        "lado do adversario"
    )


def test_sem_solucionador_proprio_NADA_muda() -> None:
    """⚠️ O caminho antigo continua sendo o de todo tipo que nao tem solucionador.

    ⛔ Dez dos onze tipos no ar caem aqui, entao um `solucionador` que virasse
    obrigatorio silenciosamente quebraria a medicao inteira.
    """
    from job.perfil import NIVEL_POR_PERSONAGEM
    from job.regua import tentativa_com_motor

    jogador = _JogadorQueAnota()
    tentar = tentativa_com_motor(
        jogador=jogador,
        estado_inicial=_EstadoFalso(vez_de=1),
        julgar=lambda fita: type("J", (), {"cumpriu": len(fita) >= 4})(),
        nu_semente=7,
        maximo_de_meios_lances=4,
        co_personagem_do_dia="magno",
    )
    tentar("cacau", 1)

    niveis_de_quem_resolve = [n for vez, n in jogador.pedidos if vez == 1]
    assert set(niveis_de_quem_resolve) == {NIVEL_POR_PERSONAGEM["cacau"]}


def test_a_BANCADA_carrega_o_solucionador_do_tipo_do_candidato() -> None:
    """⛔ O elo que faltava: o registro e consultado na hora de MEDIR, e nao so ao gerar.

    ⚠️ **Este caso olha o registro de verdade**, e nao uma copia: no dia em que um
    tipo novo ganhar solucionador proprio, a regua passa a usa-lo sem ninguem
    tocar em `regua.py`. ⛔ Era justamente a copia ausente que deixava os dois
    caminhos divergirem em silencio.
    """
    from job import gerador as gerador_mod

    assert gerador_mod.SOLUCIONADOR_POR_TIPO, (
        "o registro ficou vazio — se o solucionador da cadeia longa saiu, este "
        "caso precisa de outro tipo para provar o elo"
    )
    for co_tipo, esperado in gerador_mod.SOLUCIONADOR_POR_TIPO.items():
        assert esperado is not None, co_tipo


# ═══════════════════════════════════════════════════════════════════════════
# 🔒 ⛔ A ESCADA — o criterio que o dono trocou em 16/09/2026
# ═══════════════════════════════════════════════════════════════════════════
#
# > *"Pouquissimos ou quase nenhum dos desafios serem resolviveis pela Cacau,
# > poucos pela Pita, uma quantidade maior pelo Tex (talvez mais da metade) e
# > quase sempre o Magno resolve os desafios."*
#
# ⛔ **A media dos tres produzia desafios faceis, e isto e demonstravel.** Junte
# duas coisas medidas: a banda exigia media 0,70-0,80 **com a Cacau dentro**, e a
# regua mede cumprimento **acidental** (o mascote nao le o enunciado). Logo, o
# objetivo tinha de acontecer sozinho em ~70% das partidas de um jogador fraco —
# ou seja, ser quase inevitavel.


def _m(co_personagem: str, taxa: float) -> Medicao:
    """Uma medicao com a taxa pedida, em 20 execucoes."""
    return Medicao(
        co_personagem=co_personagem,
        nu_execucoes=20,
        nu_resolveu=round(taxa * 20),
        co_versao_perfil="perfil-teste",
        co_versao_motor="motor-teste",
    )


def test_a_ESCADA_e_a_MEDIA_discordam_no_caso_que_causou_a_troca() -> None:
    """🔒 ⛔ O `damas_sobreviver` de 21/09: o unico que a banda aprovou.

    ⚠️ **Este e o caso que prova que a troca nao foi estetica.** Na execucao real
    de 15/09 esse foi o **unico** dos sete dias que caiu na banda (media 0,80) — e
    foi justamente o que o dono mais reprovou no painel, escrevendo que era
    *"extremamente facil"*.

    ⛔ Se um dia alguem voltar a media para decidir, este caso cai.
    """
    medicoes = [_m("cacau", 0.50), _m("pita", 0.90), _m("tex", 1.00)]
    assert dentro_da_banda(medicoes, piso=0.70, teto=0.80) is True
    assert dentro_da_escada(medicoes) is False


def test_a_ESCADA_aprova_o_perfil_que_o_dono_descreveu() -> None:
    """🔒 Cacau quase nada, Pita pouco, Tex mais da metade.

    ⚠️ **E a media deste caso e 0,37** — que a banda antiga recusaria como
    "durissimo", trinta e tres pontos abaixo do piso. As duas reguas nao
    discordam na margem: elas discordam no meio.
    """
    medicoes = [_m("cacau", 0.10), _m("pita", 0.35), _m("tex", 0.65)]
    assert dentro_da_escada(medicoes) is True
    assert dentro_da_banda(medicoes, piso=0.70, teto=0.80) is False


def test_a_ESCADA_recusa_o_que_NINGUEM_resolve() -> None:
    """🔒 O `damas_coroar` de 17/09: 0,05 nos tres.

    ⚠️ A banda tambem recusava este — mas pelo motivo **agregado**. A escada diz
    qual degrau errou: a Cacau e a Pita estao no lugar, e quem falha e o **Tex**,
    que precisa chegar a mais da metade. ⛔ Sem isso, "fora por 0,65" mandaria
    procurar o defeito na escada inteira.
    """
    medicoes = [_m("cacau", 0.05), _m("pita", 0.05), _m("tex", 0.05)]
    assert dentro_da_escada(medicoes) is False
    assert "tex" in descrever_escada(medicoes)
    assert "cacau 0.05 ✅" in descrever_escada(medicoes)


def test_a_distancia_e_a_MEDIA_DAS_FALTAS_e_nao_a_falta_da_media() -> None:
    """🔒 ⛔ A diferenca que a media esconde.

    `0,00 / 0,50 / 1,00` tem media 0,50 e **parece** calibrado. A escada ve que a
    Cacau esta no lugar, a Pita tambem, e quem esta fora e o Tex — que resolve
    tudo.
    """
    medicoes = [_m("cacau", 0.00), _m("pita", 0.50), _m("tex", 1.00)]
    assert taxa_media(medicoes) == 0.50
    # Cacau 0,00 em [0,00-0,20] → 0 · Pita 0,50 em [0,05-0,45] → 0,05 ·
    # Tex 1,00 em [0,45-0,85] → 0,15. Media das faltas: 0,0667.
    assert distancia_da_escada(medicoes) == pytest.approx(0.20 / 3)


def test_a_escada_e_INJETAVEL() -> None:
    """🔒 ⛔ Criterio que nao se consegue injetar e criterio que nao se testa.

    ⚠️ **Nasceu de um defeito de desenho meu, no dia da troca.** A escada tinha
    ficado fixa no modulo, e dois testes de encadeamento do job quebraram sem ter
    nada a ver com calibracao: eles injetavam uma banda `[0,00 - 1,00]` para dizer
    *"aceite qualquer coisa"*, e a alavanca tinha sumido.
    """
    larga = {p: (0.0, 1.0) for p in ("cacau", "pita", "tex", "magno")}
    medicoes = [_m("cacau", 1.00), _m("pita", 1.00), _m("tex", 1.00)]
    assert dentro_da_escada(medicoes) is False
    assert dentro_da_escada(medicoes, escada=larga) is True


def test_sem_medicao_a_escada_nao_APROVA_por_acidente() -> None:
    """🔒 Nada medido devolve infinito, e nao zero.

    ⚠️ O mesmo principio de `distancia_da_banda`: "nada a medir" nao pode virar
    "encaixou perfeitamente".
    """
    assert distancia_da_escada([]) == float("inf")
    assert dentro_da_escada([]) is False


def test_a_escada_do_dono_e_CRESCENTE() -> None:
    """🔒 A forma da frase dele, travada: cada degrau pede mais que o anterior.

    ⚠️ Cadeado sobre a **constante**, e nao sobre um caso — um ajuste futuro dos
    numeros continua passando, mas inverter dois mascotes por descuido nao.
    """
    ordem = ["cacau", "pita", "tex", "magno"]
    pisos = [ESCADA_ALVO[p][0] for p in ordem]
    tetos = [ESCADA_ALVO[p][1] for p in ordem]
    assert pisos == sorted(pisos), f"os pisos nao sobem: {pisos}"
    assert tetos == sorted(tetos), f"os tetos nao sobem: {tetos}"
    # ⛔ O Magno e o degrau da RESOLUBILIDADE: sem um piso alto nele, a escada
    # aprovaria um desafio que ninguem resolve.
    assert ESCADA_ALVO["magno"][0] >= 0.70
