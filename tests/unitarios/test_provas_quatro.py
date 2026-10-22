"""As provas dos dez tipos do Quatro em Linha (`job/provas_quatro.py`, T116).

Duas partes:

  1. **a leitura da busca**, com um duplo do executável: a distância até a
     vitória, o empate provado e o "nada provado" saem da resposta do `buscar`.
     Mais o cadeado que confere os três números da busca contra o fonte Dart
     do espelho, e o que exige uma prova para cada um dos dez tipos;
  2. **cada tipo com uma posição que passa e uma que falha**, com o executável
     de verdade. As posições saíram de partidas jogadas pelo motor (Magno contra
     Magno, Tex e Pita) em 20/10/2026, e cada falha é pelo motivo DAQUELE tipo
     (o "sem o meio" que só vence pelo meio, o Segure sem maioria), e não por
     um motivo genérico que serviria a todos.

E a prova de estado terminal, chamada com o adversário do Quatro: trivial com
42 casas, mas é cadeado (`contracts/desafio-quatro.md` §2).
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from job import estado_terminal
from job import provas_quatro as pq
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import contrato_quatro, feitos_quatro
from motores.quatro import jogador_dart_quatro as jdq
from motores.quatro.jogador_quatro import JogadorQuatro
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, ler_sequencia

MODALIDADE = "tradicional"


def _estado(sequencia: str) -> EstadoQuatro:
    return EstadoQuatro(MODALIDADE, ler_sequencia(sequencia))


# ═══════════════════════════════════════════════════════════════════════════
# 1. A leitura da busca, com um duplo
# ═══════════════════════════════════════════════════════════════════════════


class _Duplo:
    """Responde sempre a mesma coisa ao `buscar`, e conta as perguntas."""

    def __init__(self, **resposta) -> None:
        self.resposta = {"lance": "s1", "profundidadeAtingida": 9, **resposta}
        self.perguntas: list[str] = []

    def buscar(self, *, lances: str, co_modalidade: str, teto_de_nos: int) -> dict:
        self.perguntas.append(lances)
        return self.resposta

    def avaliar(self, *, lances: str, co_modalidade: str) -> int:
        return 0


def test_a_vitoria_decidida_da_o_vencedor_e_a_distancia_em_meios_lances() -> None:
    # Três lances jogados; a vitória do jogador 1 vem no lance 8 da partida:
    # 1000 - 8 = 992, e a distância é 8 - 3 = 5 meios-lances.
    provador = pq.ProvadorQuatro(MODALIDADE, _Duplo(avaliacaoJ1=992, motivoParada="decidido"))
    assert provador.resultado(_estado("s4s4s3")) == pq.Resultado(1, 5, "s1")


def test_a_derrota_decidida_e_do_jogador_2() -> None:
    provador = pq.ProvadorQuatro(MODALIDADE, _Duplo(avaliacaoJ1=-990, motivoParada="decidido"))
    assert provador.resultado(_estado("s4s4s3")).vencedor == -1
    assert provador.resultado(_estado("s4s4s3")).meios_lances == 7


@pytest.mark.parametrize("avaliacao", [pq.LIMIAR_DECIDIDO, -pq.LIMIAR_DECIDIDO, 40])
def test_valor_no_limiar_ou_abaixo_nao_e_decidido(avaliacao: int) -> None:
    """O limiar é estrito: 936 ainda é uma posição sem desfecho visto."""
    provador = pq.ProvadorQuatro(MODALIDADE, _Duplo(avaliacaoJ1=avaliacao, motivoParada="nos"))
    assert provador.resultado(_estado("s4")).vencedor is None


def test_o_empate_so_e_provado_quando_a_busca_viu_o_fim_de_tudo() -> None:
    def resultado(**resposta):
        return pq.ProvadorQuatro(MODALIDADE, _Duplo(**resposta)).resultado(_estado("s4"))

    assert resultado(avaliacaoJ1=0, motivoParada="profundidade").vencedor == 0
    # Zero com o teto de nós estourado é um "não sei", e não um empate.
    assert resultado(avaliacaoJ1=0, motivoParada="nos").vencedor is None
    # Zero no limite contra partida sem fim também não é ter visto o fim.
    assert resultado(
        avaliacaoJ1=0, motivoParada="profundidade", profundidadeAtingida=pq.PROFUNDIDADE_MAXIMA
    ).vencedor is None
    # Valor sem desfecho com a profundidade completa não é empate (seria
    # heurística): só o zero exato é.
    assert resultado(avaliacaoJ1=3, motivoParada="profundidade").vencedor is None


def test_a_mesma_posicao_por_outra_ordem_nao_pergunta_de_novo() -> None:
    duplo = _Duplo(avaliacaoJ1=0, motivoParada="nos")
    provador = pq.ProvadorQuatro(MODALIDADE, duplo)
    provador.resultado(_estado("s1s2s3"))
    provador.resultado(_estado("s3s2s1"))  # o mesmo tabuleiro (transposição)
    assert duplo.perguntas == ["s1s2s3"]
    assert provador.perguntas == 1


def test_com_um_lance_so_a_busca_nao_e_perguntada_sobre_a_raiz(monkeypatch) -> None:
    """A busca responde `lance_unico` sem buscar (valor zero): seria lido como
    empate. O provador joga o lance e pergunta a posição seguinte."""
    duplo = _Duplo(avaliacaoJ1=992, motivoParada="decidido")
    provador = pq.ProvadorQuatro(MODALIDADE, duplo)
    original = provador.arbitro.lances_legais
    monkeypatch.setattr(
        provador.arbitro, "lances_legais",
        lambda e: ["s1"] if e.sequencia == "s4s4" else original(e),
    )
    achado = provador.resultado(_estado("s4s4"))
    assert duplo.perguntas == ["s4s4s1"]
    # 1000 - 992 = lance 8; da posição seguinte (3 lances) faltam 5, e da raiz 6.
    assert achado.vencedor == 1 and achado.meios_lances == 6


def test_os_numeros_da_busca_sao_os_do_fonte_dart_do_espelho() -> None:
    """Mudou um número em `busca_quatro.dart`? Esta leitura passa a mentir."""
    fonte = (
        contrato_quatro.ESPELHO / "jogos" / "jogo_quatro" / "motor_dart" / "lib"
        / "busca_quatro.dart"
    ).read_text(encoding="utf-8")

    def constante(nome: str) -> str:
        achado = re.search(rf"const int {nome} = ([^;]+);", fonte)
        assert achado, f"{nome} sumiu de busca_quatro.dart"
        return achado.group(1).strip()

    assert constante("valorVitoriaQuatro") == str(pq.VALOR_VITORIA)
    assert constante("limiarDecididoQuatro") == "valorVitoriaQuatro - 64"
    assert pq.LIMIAR_DECIDIDO == pq.VALOR_VITORIA - 64
    assert constante("profundidadeMaximaQuatro") == str(pq.PROFUNDIDADE_MAXIMA)


def test_todo_tipo_do_quatro_tem_prova_e_nenhuma_sobra() -> None:
    tipos = {
        co for co, r in {**RECEITAS, **RECEITAS_FORA_DO_AR}.items() if r.co_jogo == "quatro"
    }
    # Os dez da §8zzz e o "Encoste" da §8zzzr (T143, 22/10/2026).
    assert len(tipos) == 11, "o controle: são onze tipos (§8zzz e §8zzzr)"
    assert set(pq.PROVAS) == tipos


def test_tipo_sem_prova_falha_alto() -> None:
    with pytest.raises(KeyError, match="não tem prova"):
        pq.provar("damas_sobreviver", None, _estado("s4"), {})


class _DuploPorPosicao(_Duplo):
    """Responde conforme a posição: `{sequencia: avaliacaoJ1}`; o resto, "não sei"."""

    def __init__(self, avaliacoes: dict[str, int], heuristica: int = 0) -> None:
        super().__init__()
        self.avaliacoes = avaliacoes
        self.heuristica = heuristica

    def buscar(self, *, lances: str, co_modalidade: str, teto_de_nos: int) -> dict:
        self.perguntas.append(lances)
        if lances in self.avaliacoes:
            return {**self.resposta, "avaliacaoJ1": self.avaliacoes[lances],
                    "motivoParada": "decidido"}
        return {**self.resposta, "avaliacaoJ1": 0, "motivoParada": "nos"}

    def avaliar(self, *, lances: str, co_modalidade: str) -> int:
        return self.heuristica


def test_unica_coluna_com_uma_coluna_INDECISA_reprova() -> None:
    """Uma coluna salva (o jogador 1 vence por ela) e as outras a busca não
    decidiu: a indecisa podia ser a segunda salvação, e a prova reprova."""
    provador = pq.ProvadorQuatro(MODALIDADE, _DuploPorPosicao({"s4s4s1": 990}))
    prova = provador.unica_coluna(_estado("s4s4"))
    assert not prova.passou
    assert prova.dados == {"salvam": ["s1"], "perdem": []}


def test_virada_com_heuristica_ZERO_nao_e_virada() -> None:
    """Zero não favorece ninguém: a posição não parece do adversário."""
    provador = pq.ProvadorQuatro(MODALIDADE, _DuploPorPosicao({"s4s4": 990}, heuristica=0))
    prova = provador.virada(_estado("s4s4"))
    assert not prova.passou and "não favorece" in prova.motivo
    # O controle: a mesma posição, com a heurística contra, passa.
    provador = pq.ProvadorQuatro(MODALIDADE, _DuploPorPosicao({"s4s4": 990}, heuristica=-1))
    assert provador.virada(_estado("s4s4")).passou


def test_sem_o_meio_recusa_largura_par() -> None:
    provador = pq.ProvadorQuatro(MODALIDADE, _Duplo(avaliacaoJ1=0, motivoParada="nos"))
    provador.arbitro = SimpleNamespace(
        regras=SimpleNamespace(dimensoes=contrato_quatro.DimensoesQuatro(6, 6, 4))
    )
    prova = provador.sem_o_meio(_estado("s4"))
    assert not prova.passou and "largura par" in prova.motivo


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os dez tipos, com o executável de verdade
# ═══════════════════════════════════════════════════════════════════════════

#: Achadas em partidas do motor. Os comentários dizem o que cada uma prova.
VENCE_EM_5_E_PARECE_PERDIDA = "s4s4s4s4s4s6s3s2s2s6s6"  # heurística -12
ABERTA_SEM_VITORIA = "s4s4s4s4s4s6s3s2"  # nada forçado; heurística +4
PROVADA_PERDIDA = "s4s4s4s4s4s6s3s2s2s6s6s7"  # o jogador 1 perde à força
SEGURE_5_DE_6 = "s1s5s4s4s4s4s5s5s5s2s4s5s7s7s7s7s1s1s7s4"
SEGURE_SO_3_DE_6 = "s4s4s4s4s3s5s5s5s5s3s6s6s7s4s4s2s2s6s2"
UNICA_S2 = "s4s4s4s4s4s6s2s3s2s6s1s7s3s7s2"
CINCO_SALVAM = "s4s4s4s4s5s3s3s3s3s5s2s2s1s4s4"
VENCE_SEM_O_MEIO = "s4s4s4s4s5s3s3s3s3s5s2s2s1s4s2s2s7s6s2"
#: Montada à mão: o 1 tem três no chão (colunas 1 a 3) e a vez; só a coluna 4
#: fecha a linha. Nas partidas do Magno não apareceu uma assim (20/10/2026).
SO_VENCE_PELO_MEIO = "s1s7s2s7s3s6"
#: A vitória livre existe, mas em 11 lances: acima do teto do "sem o meio".
VITORIA_LONGA = "s5s3s3s5s3s3s5s5s6s7s7s5s7s3s2s5"
MEIO_CHEIO = "s4s4s4s4s4s4"
#: E a continuação que o autoplay jogou dali, com dois bloqueios da pessoa.
BLOQUEIO_POSICAO = "s5s3s3s5s3s3s5s5s6s7s7"
BLOQUEIO_CONTINUACAO = "s5s7s3s2s5s2s2s7s7s2s7s1s2s2s1s1s3s1s1s1s6s6s6s4s4s4"


@pytest.fixture(scope="module")
def provador():
    try:
        jdq.caminho_do_executavel()
    except jdq.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do Quatro não está compilado: {erro}")
    with jdq.JogadorDartQuatro() as motor:
        # Um provador por módulo: as respostas guardadas valem para todos os
        # casos (são do mesmo motor e da mesma modalidade).
        yield pq.ProvadorQuatro(MODALIDADE, motor)


def _prova(provador, tipo: str, sequencia: str, continuacao: str | None = None, **par):
    return pq.provar(
        tipo, provador, _estado(sequencia), par,
        continuacao=ler_sequencia(continuacao) if continuacao else None,
    )


def test_vencer_em_n_exige_EXATAMENTE_n(provador) -> None:
    assert _prova(provador, "quatro_vencer_em_n", VENCE_EM_5_E_PARECE_PERDIDA, lances=5).passou
    # Em 4 não dá (a vitória é mais longa), e em 6 o "não em N-1" reprova.
    em_4 = _prova(provador, "quatro_vencer_em_n", VENCE_EM_5_E_PARECE_PERDIDA, lances=4)
    em_6 = _prova(provador, "quatro_vencer_em_n", VENCE_EM_5_E_PARECE_PERDIDA, lances=6)
    assert not em_4.passou and "em 5 lances, e não em 4" in em_4.motivo
    assert not em_6.passou and "em 5 lances, e não em 6" in em_6.motivo
    sem = _prova(provador, "quatro_vencer_em_n", ABERTA_SEM_VITORIA, lances=5)
    assert not sem.passou and "sem vitória forçada" in sem.motivo


def test_segurar_magno_quer_o_empate_e_a_MAIORIA_perdendo(provador) -> None:
    prova = _prova(provador, "quatro_segurar_magno", SEGURE_5_DE_6)
    assert prova.passou and len(prova.dados["perdem"]) == 5
    sem_maioria = _prova(provador, "quatro_segurar_magno", SEGURE_SO_3_DE_6)
    assert not sem_maioria.passou and "não é a maioria" in sem_maioria.motivo
    aberta = _prova(provador, "quatro_segurar_magno", ABERTA_SEM_VITORIA)
    assert not aberta.passou and "empate provado" in aberta.motivo


def test_unica_coluna_quer_UMA_salvacao_e_as_outras_perdidas(provador) -> None:
    prova = _prova(provador, "quatro_unica_coluna", UNICA_S2)
    assert prova.passou and prova.dados == {"coluna": "s2"}
    varias = _prova(provador, "quatro_unica_coluna", CINCO_SALVAM)
    assert not varias.passou and len(varias.dados["salvam"]) == 5


def test_sem_o_meio_acha_a_vitoria_fora_da_coluna_4(provador) -> None:
    prova = _prova(provador, "quatro_sem_o_meio", VENCE_SEM_O_MEIO)
    assert prova.passou and prova.dados == {"lances": 5}
    pelo_meio = _prova(provador, "quatro_sem_o_meio", SO_VENCE_PELO_MEIO)
    assert not pelo_meio.passou and "não sem a coluna 4" in pelo_meio.motivo
    # O controle: a vitória livre dali existe (e é no meio, num lance).
    assert provador.resultado(_estado(SO_VENCE_PELO_MEIO)) == pq.Resultado(1, 1, "s4")
    # ⚠️ Vitória livre mais longa que o teto: a frase não pode dizer que o meio
    # é obrigatório (o laço nem rodaria). Foi o que a 1ª versão fazia.
    longa = _prova(provador, "quatro_sem_o_meio", VITORIA_LONGA)
    assert not longa.passou and "já leva 11 lances" in longa.motivo
    cheia = _prova(provador, "quatro_sem_o_meio", MEIO_CHEIO)
    assert not cheia.passou and "cheia" in cheia.motivo


def test_virada_quer_a_aparencia_contra_e_a_vitoria_a_favor(provador) -> None:
    prova = _prova(provador, "quatro_virada", VENCE_EM_5_E_PARECE_PERDIDA)
    assert prova.passou and prova.dados["heuristica"] < 0 and prova.dados["lances"] == 5
    aparencia_boa = _prova(provador, "quatro_virada", ABERTA_SEM_VITORIA)
    assert not aparencia_boa.passou and "não favorece o adversário" in aparencia_boa.motivo


@pytest.mark.parametrize(
    "tipo, par",
    [
        ("quatro_vencer_diagonal", {}),
        ("quatro_golpe_duplo", {"linhas": 2}),
        ("quatro_linha_de_cinco", {"tamanho": 5}),
    ],
)
def test_os_de_alcance_passam_na_aberta_e_falham_na_perdida(provador, tipo, par) -> None:
    assert _prova(provador, tipo, ABERTA_SEM_VITORIA, **par).passou
    perdida = _prova(provador, tipo, PROVADA_PERDIDA, **par)
    assert not perdida.passou and "provada perdida" in perdida.motivo


def test_os_de_alcance_contam_janelas_sem_peca_do_adversario(provador) -> None:
    """O número das janelas, e não só "passou": com o adversário na diagonal, a
    janela some. Jogador 1 em s1, s2 e s3 no chão; o 2 em cima de cada um."""
    sequencia = "s1s1s2s2s3s3"
    tabuleiro = provador.arbitro.tabuleiro(_estado(sequencia))
    # A vez é do 1. Diagonais de 4 no tabuleiro 7×6: 24 (12 por direção); as que passam
    # por uma casa do 2 (linha 2, colunas 1 a 3) deixam de contar.
    abertas = provador._janelas_abertas(tabuleiro, 1, 4, direcoes=((1, 1), (1, -1)))
    for _direcao, casas in abertas:
        assert all(tabuleiro.peca(casa) != -1 for casa in casas)
    assert 0 < len(abertas) < 24


def test_golpe_duplo_pede_direcoes_DIFERENTES(provador) -> None:
    """Com `linhas` = 5, nenhuma casa cruza cinco direções (só há quatro)."""
    prova = _prova(provador, "quatro_golpe_duplo", ABERTA_SEM_VITORIA, linhas=5)
    assert not prova.passou


def test_encostadas_quer_o_alvo_ACIMA_do_que_ja_ha(provador) -> None:
    arbitro = provador.arbitro
    tabuleiro = arbitro.tabuleiro(_estado(ABERTA_SEM_VITORIA))
    ja = feitos_quatro.pecas_encostadas(arbitro.regras.dimensoes, tabuleiro, tabuleiro.vez)
    prova = _prova(provador, "quatro_encostadas", ABERTA_SEM_VITORIA, pecas=ja + 3)
    assert prova.passou and prova.dados == {"ja": ja, "falta": 3}
    de_graca = _prova(provador, "quatro_encostadas", ABERTA_SEM_VITORIA, pecas=ja)
    assert not de_graca.passou and "cumpre sem jogar" in de_graca.motivo
    # Com 34 casas livres a pessoa joga 17 vezes: 18 a mais não cabe.
    demais = _prova(provador, "quatro_encostadas", ABERTA_SEM_VITORIA, pecas=ja + 18)
    assert not demais.passou and "restam 17 lances" in demais.motivo


def test_encoste_pede_JUNTAR_pecas_soltas(provador) -> None:
    """O "Encoste N em ate M" (T143): o alvo acima de `E + M` pede soltas.

    Na posicao, o jogador 1 tem a vez e quatro pecas: (3,1) e (4,1) juntas, e
    (4,3) e (4,5) SOLTAS, cada uma entre pecas do 2 na coluna 4. Entao `E = 2`
    e ha duas soltas: o alvo pode pedir juntar uma ou duas, e nao tres. Os
    numeros vao por extenso (e nao lidos da prova), para o caso nao se medir
    pela propria regua.
    """
    um = _prova(provador, "quatro_encoste", ABERTA_SEM_VITORIA, pecas=8, lances=5)
    assert um.passou and um.dados == {"ja": 2, "soltas": 2, "juntar": 1}
    dois = _prova(provador, "quatro_encoste", ABERTA_SEM_VITORIA, pecas=9, lances=5)
    assert dois.passou and dois.dados["juntar"] == 2
    tres = _prova(provador, "quatro_encoste", ABERTA_SEM_VITORIA, pecas=10, lances=5)
    assert not tres.passou and "juntar 3 peça(s) solta(s), e há 2" in tres.motivo
    # Alvo E + M: "jogue colado", que todos cumprem. ⛔ Recusa.
    colado = _prova(provador, "quatro_encoste", ABERTA_SEM_VITORIA, pecas=7, lances=5)
    assert not colado.passou and "cabe jogando colado" in colado.motivo
    # O M conta: o mesmo alvo 9 com 6 lances pede juntar so uma.
    com_seis = _prova(provador, "quatro_encoste", ABERTA_SEM_VITORIA, pecas=9, lances=6)
    assert com_seis.passou and com_seis.dados["juntar"] == 1
    perdida = _prova(provador, "quatro_encoste", PROVADA_PERDIDA, pecas=20, lances=5)
    assert not perdida.passou and "provada perdida" in perdida.motivo


def test_bloquear_conta_os_bloqueios_da_continuacao(provador) -> None:
    prova = _prova(
        provador, "quatro_bloquear", BLOQUEIO_POSICAO, BLOQUEIO_CONTINUACAO, ameacas=2
    )
    assert prova.passou and prova.dados == {"ameacas": 2}
    tres = _prova(provador, "quatro_bloquear", BLOQUEIO_POSICAO, BLOQUEIO_CONTINUACAO, ameacas=3)
    assert not tres.passou and "bloqueou 2" in tres.motivo
    sem = _prova(provador, "quatro_bloquear", BLOQUEIO_POSICAO, None, ameacas=2)
    assert not sem.passou and "continuação" in sem.motivo


# ── O objetivo FORÇÁVEL (T124c, item 1 do plano do que sobra) ──────────────
#
# Montadas à mão (21/10/2026), com o desenho no comentário. Nas três primeiras
# a vez é do jogador 1 e a vitória livre vem em 1 lance: o que muda é o JEITO.

#: Linha 1: o 1 em s1, s2, s3; diagonal (1,4) (2,3) (3,2) do 1. O s4 cai em
#: (4,1) e fecha DUAS linhas de quatro: a horizontal e a diagonal.
GOLPE_DUPLO_EM_1 = "s1s1s2s1s3s2s3s7s2s7s1s6"
#: Linha 1: `1 1 _ 1 1 2`. O s3 fecha UMA linha, de cinco.
CINCO_EM_1 = "s1s7s2s7s4s6s5s6"
#: Linha 1: `1 1 1 _`, e o 2 com três na coluna 7. O s4 vence com uma linha de
#: quatro, e qualquer outro lance deixa o s7 do adversário: o único jeito de
#: vencer é o ERRADO para os dois tipos.
SO_A_HORIZONTAL = "s1s7s2s7s3s6"
#: A mesma linha de cinco, com a vez do jogador 2 (o 1 jogou s7, s7, s6, s6, s7).
CINCO_EM_1_DO_JOGADOR_2 = "s7s1s7s2s6s4s6s5s7"
#: Do acervo de autoplay (21/10/2026): a linha de cinco é forçável em 8 lances,
#: os mesmos 8 da vitória livre; o golpe duplo, não.
CINCO_EM_8_DO_ACERVO = "s4s4s4s4s2s5s5s1s5s5s1s5s4s4s1s1s2s6s2s2s2s5s1s1"


def _chegada(tipo: str, **par) -> dict:
    """A linha de chegada da receita, no ar ou fora dele (o tipo muda de lado
    no dia da promoção, e o teste não deve quebrar por isso)."""
    return {**RECEITAS_FORA_DO_AR, **RECEITAS}[tipo].montar(par)


def _forcavel(provador, sequencia: str, tipo: str, *, teto: int = pq.MAXIMO_FORCAVEL, **par):
    return provador.objetivo_forcavel(
        _estado(sequencia), _chegada(tipo, **par), maximo_de_meios_lances=teto
    )


def test_o_golpe_duplo_forcavel_em_1_nao_e_linha_de_cinco(provador) -> None:
    golpe = _forcavel(provador, GOLPE_DUPLO_EM_1, "quatro_golpe_duplo", linhas=2)
    assert golpe.passou and golpe.dados == {"lances": 1, "lances_livre": 1}
    # As duas linhas são de quatro: o mesmo lance não faz a linha de cinco.
    cinco = _forcavel(provador, GOLPE_DUPLO_EM_1, "quatro_linha_de_cinco", teto=1, tamanho=5)
    assert not cinco.passou and "não é forçável em até 1" in cinco.motivo


def test_a_linha_de_cinco_forcavel_em_1_nao_e_golpe_duplo(provador) -> None:
    cinco = _forcavel(provador, CINCO_EM_1, "quatro_linha_de_cinco", tamanho=5)
    assert cinco.passou and cinco.dados == {"lances": 1, "lances_livre": 1}
    # Uma linha só, ainda que de cinco: não é o golpe duplo.
    golpe = _forcavel(provador, CINCO_EM_1, "quatro_golpe_duplo", teto=1, linhas=2)
    assert not golpe.passou and "não é forçável em até 1" in golpe.motivo


@pytest.mark.parametrize(
    "tipo, par", [("quatro_golpe_duplo", {"linhas": 2}), ("quatro_linha_de_cinco", {"tamanho": 5})]
)
def test_vencer_do_jeito_ERRADO_nao_cumpre_o_objetivo(provador, tipo, par) -> None:
    """A vitória livre está a um lance, e por isso a prova "ao alcance" passaria;
    a forçável não, porque o único jeito de vencer é com uma linha de quatro."""
    prova = _forcavel(provador, SO_A_HORIZONTAL, tipo, **par)
    assert not prova.passou
    assert "vitória existe em 1 lances, mas o objetivo não é forçável" in prova.motivo
    # O controle: a busca livre diz que ele vence ali, e em 1.
    assert provador.resultado(_estado(SO_A_HORIZONTAL)).meios_lances == 1


def test_o_objetivo_forcavel_e_de_quem_tem_a_vez_mesmo_o_jogador_2(provador) -> None:
    """Quem resolve é o jogador 2: o medidor da folha tem de medir o lado DELE."""
    prova = _forcavel(provador, CINCO_EM_1_DO_JOGADOR_2, "quatro_linha_de_cinco", tamanho=5)
    assert prova.passou and prova.dados["lances"] == 1


def test_o_objetivo_forcavel_numa_posicao_do_acervo(provador) -> None:
    cinco = _forcavel(provador, CINCO_EM_8_DO_ACERVO, "quatro_linha_de_cinco", tamanho=5)
    assert cinco.passou and cinco.dados == {"lances": 8, "lances_livre": 8}
    golpe = _forcavel(provador, CINCO_EM_8_DO_ACERVO, "quatro_golpe_duplo", linhas=2)
    assert not golpe.passou and "não é forçável em até 8" in golpe.motivo
    # E o teto abaixo da vitória livre recusa sem descer a árvore.
    curto = _forcavel(provador, CINCO_EM_8_DO_ACERVO, "quatro_linha_de_cinco", teto=1, tamanho=5)
    assert not curto.passou and "já leva 8 lances" in curto.motivo


def test_o_objetivo_forcavel_sem_vitoria_livre_recusa(provador) -> None:
    prova = _forcavel(provador, ABERTA_SEM_VITORIA, "quatro_golpe_duplo", linhas=2)
    assert not prova.passou and "sem vitória forçada" in prova.motivo


def test_o_objetivo_forcavel_desiste_no_teto_de_perguntas(provador) -> None:
    """Na posição do golpe duplo, a linha de cinco não existe, mas a vitória
    livre sobrevive a quase todo lance (a ameaça do s4 continua): a árvore
    cresce, e a prova tem de PARAR e dizer "não provado", e não seguir."""
    antes = provador.perguntas
    prova = provador.objetivo_forcavel(
        _estado(GOLPE_DUPLO_EM_1), _chegada("quatro_linha_de_cinco", tamanho=5), perguntas=50
    )
    assert not prova.passou and "passou de 50 perguntas" in prova.motivo
    # O teto é conferido na ENTRADA de cada nó da pessoa, e um nó pergunta no
    # máximo a própria posição e uma por coluna (7); mais a vitória livre, que
    # vem antes da árvore. Passar disso seria a árvore seguindo depois do teto.
    assert provador.perguntas - antes <= 50 + 1 + 1 + 7


def test_o_no_E_recusa_a_resposta_que_vence_mesmo_sem_a_poda(provador) -> None:
    """A guarda do nó do adversário, medida SOZINHA.

    ⚠️ Na árvore inteira ela é a segunda defesa: o lance da pessoa que deixa
    uma vitória ao adversário já sai na poda (a busca não dá a vitória forçada
    à pessoa ali). Um caso pela prova inteira passaria sem ela - por isso este
    chama o nó direto. Linha 1: o 1 em s2, s3, s4 e s6 (ameaça dupla, s1 e s5);
    o 2 com três na coluna 7 e a vez. Qualquer bloqueio perde, menos o s7, que
    VENCE: o nó tem de dizer "não", e não pular a resposta que encerra.
    """
    estado = _estado("s2s7s3s7s4s7s6")
    arvore = pq._Arvore(
        quem=1,
        permitido=lambda _a, _d: True,
        folha=lambda fim: provador.arbitro.veredito(fim).vencedor == 1,
        perguntas_ate=provador.perguntas + 100,
    )
    assert provador._todas_as_respostas(estado, arvore, 2) is False
    # O controle: sem o s7, toda resposta perde para o 1 em um lance.
    for lance in ("s1", "s5"):
        depois = provador.arbitro.aplicar(estado, lance)
        assert provador._forca(depois, arvore, 1) is True


# ── As duas defesas (21/10/2026, a pescaria) ────────────────────────────────
#
# Do acervo, achadas pela busca de 21/10: a vitória livre vem em 6 lances, e o
# objetivo é forçável contra quem defende o JOGO, mas não contra quem só sabota
# o objetivo. A recusa da defesa do objetivo é DEFINITIVA (não estoura o teto).

#: A linha de cinco em 6 lances.
CINCO_SO_CONTRA_O_JOGO = "s4s4s4s4s4s2s2s2s3s2s5s6s7s2s2s6s5s6s6s4s6s3s5s5s5s6s7s7s5"
#: O golpe duplo em 6 lances.
GOLPE_SO_CONTRA_O_JOGO = "s4s4s4s4s7s6s4s3s6s6s6s6s1s3s1s3s3s4s6s3s1s1s2s7s2s2s2s3s5s5s7"
#: O "sem o meio" em 5 lances, contra o jogo (a outra defesa estoura o teto).
SEM_O_MEIO_CONTRA_O_JOGO = "s4s3s4s4s4s6s2s3s3s3s4s2s3s6s6s6s6s3s2s1s2s5s5s1"


@pytest.mark.parametrize(
    "sequencia, tipo, par",
    [
        (CINCO_SO_CONTRA_O_JOGO, "quatro_linha_de_cinco", {"tamanho": 5}),
        (GOLPE_SO_CONTRA_O_JOGO, "quatro_golpe_duplo", {"linhas": 2}),
    ],
)
def test_a_defesa_do_JOGO_acha_o_que_a_do_objetivo_recusa(provador, sequencia, tipo, par) -> None:
    def prova(**defesa):
        return provador.objetivo_forcavel(
            _estado(sequencia), _chegada(tipo, **par), maximo_de_meios_lances=11, **defesa
        )

    jogo = prova(defesa=pq.DEFESA_DO_JOGO)
    assert jogo.passou and jogo.dados["lances"] == 6
    objetivo = prova(defesa=pq.DEFESA_DO_OBJETIVO)
    assert not objetivo.passou and "não é forçável em até 6" in objetivo.motivo
    # ⚠️ O padrão é a defesa do OBJETIVO: é a das provas do gerador, e ela não
    # muda por a pescaria usar a outra.
    assert prova().passou is False


def test_o_sem_o_meio_tambem_aceita_a_defesa_do_jogo(provador) -> None:
    prova = provador.sem_o_meio(
        _estado(SEM_O_MEIO_CONTRA_O_JOGO), maximo_de_meios_lances=9, defesa=pq.DEFESA_DO_JOGO
    )
    assert prova.passou and prova.dados == {"lances": 5}


def _respostas(tabela: dict[str, pq.Resultado]) -> set[str]:
    """`_respostas_do_jogo` com os resultados escritos à mão, por sequência."""
    provador = pq.ProvadorQuatro(MODALIDADE, _Duplo(avaliacaoJ1=0, motivoParada="nos"))
    provador.resultado = lambda estado: tabela[estado.sequencia]
    netos = [_estado(sequencia) for sequencia in tabela]
    return {neto.sequencia for neto in provador._respostas_do_jogo(netos, 1)}


def test_a_resposta_do_jogo_e_a_que_ADIA_a_derrota_e_todas_as_empatadas_nela() -> None:
    """Todas perdem para o 1: o motor escolhe a mais longa (7), e as duas de 7 contam."""
    tabela = {"s1": pq.Resultado(1, 3), "s2": pq.Resultado(1, 7), "s3": pq.Resultado(1, 7)}
    assert _respostas(tabela) == {"s2", "s3"}


@pytest.mark.parametrize("vencedor", [0, -1, None])
def test_a_resposta_que_nao_perde_ou_nao_se_sabe_e_escolha_do_adversario(vencedor) -> None:
    """Empate, vitória do adversário ou "a busca não decidiu": o motor pode
    escolhê-la, e a mais longa das que perdem deixa de contar."""
    tabela = {"s1": pq.Resultado(1, 9), "s2": pq.Resultado(vencedor, None)}
    assert _respostas(tabela) == {"s2"}


def test_a_prova_do_sem_o_meio_cabe_no_teto_de_perguntas(provador) -> None:
    """O controle do teto: medido em 20/10, a média foi 27 perguntas."""
    antes = provador.perguntas
    provador._guardados.clear()
    _prova(provador, "quatro_sem_o_meio", VENCE_SEM_O_MEIO)
    assert provador.perguntas - antes <= pq.PERGUNTAS_SEM_O_MEIO


# ═══════════════════════════════════════════════════════════════════════════
# 3. A prova de estado terminal, com o adversário do Quatro
# ═══════════════════════════════════════════════════════════════════════════


def test_a_partida_de_um_desafio_do_quatro_chega_ao_fim(provador) -> None:
    jogador = JogadorQuatro(MODALIDADE, motor_dart=provador.oraculo)
    prova = estado_terminal.provar_termino(
        jogador=jogador,
        estado_inicial=_estado(ABERTA_SEM_VITORIA),
        veredito_de=jogador.arbitro.veredito,
        nu_semente=20261020,
    )
    assert prova.tem_fim
    assert prova.co_motivo in ("alinhou", "tabuleiro_cheio")
    # Nunca mais lances do que as casas livres (34): o tabuleiro enche.
    assert 0 < prova.nu_lances <= 34


def test_o_adversario_do_quatro_exige_a_semente(provador) -> None:
    jogador = JogadorQuatro(MODALIDADE, motor_dart=provador.oraculo)
    with pytest.raises(ValueError, match="semente"):
        jogador.escolher_lance(_estado("s4"), NivelDeMotor.TEX)
    lance = jogador.escolher_lance(_estado("s4"), NivelDeMotor.TEX, semente=7)
    assert lance in jogador.arbitro.lances_legais(_estado("s4"))
