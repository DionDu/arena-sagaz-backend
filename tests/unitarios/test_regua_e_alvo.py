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
from job.regua import EXECUCOES_PADRAO, Medicao, dentro_da_banda, medir_candidato


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
        maximo_de_lances=4,
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
