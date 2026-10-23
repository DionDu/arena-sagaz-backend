"""O gerador de candidatos com o Quatro em Linha (T117 da spec 010).

O ramo do Quatro em `gerar_candidatos`, montado para que a régua pudesse medir
os dez tipos antes da promoção (T124b):

  1. **as peças**: a modalidade com acervo, a posição do acervo na faixa do
     preparo, a recusa da vitória no 1º lance, o carimbo do motor e a bancada;
  2. **a ordem**: a prova do tipo (T116) vem ANTES do gabarito - posição que
     não serve não paga a partida do Magno;
  3. **um candidato de verdade**, com o executável: a posição publicada se
     confere, o alvo das encostadas sai da posição, o gabarito cumpre a
     chegada e traz o motivo de cada lance;
  4. **os botões do editorial fora do ar** e o medidor de variantes, que agora
     mede o Quatro.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import date
from unittest import mock
from pathlib import Path

import pytest

from job import banco_forcavel_quatro as banco_mod
from job import editorial as editorial_mod
from job import gerador
from job import posicao_inicial as posicao_mod
from job import posicoes_de_autoplay_quatro as acervo_mod
from job import provas_quatro
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.quatro import contrato_quatro, feitos_quatro
from motores.quatro import jogador_dart_quatro as jdq
from motores.quatro.jogador_quatro import JogadorQuatro
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, ler_sequencia

MODALIDADE = "tradicional"
DIA = date(2026, 10, 1)


def _estado(sequencia: str) -> EstadoQuatro:
    return EstadoQuatro(MODALIDADE, ler_sequencia(sequencia))


def _gerar(co_tipo: str, **extra):
    """`gerar_candidatos` com os botões da variante 0 do editorial do tipo.

    ⚠️ O tipo pode estar FORA do ar (vai como `receita_em_avaliacao`, que força o
    tipo) ou NO AR - a diagonal e as encostadas subiram na T124c, e o gerador
    recusa, com razão, receita "em avaliação" de tipo publicado. No ar, o caminho
    é o NORMAL (com o vetor de verificação exigido), e o jogo e o tipo do dia são
    fixados com `mock.patch`: assim o caso não depende de qual dia o rodízio dá
    a qual tipo.
    """
    no_ar = co_tipo in RECEITAS
    publicacao = (
        editorial_mod.EDITORIAL if no_ar else editorial_mod.EDITORIAL_FORA_DO_AR
    )[co_tipo][0]
    argumentos = dict(
        parametros=publicacao.parametros,
        quantos=1,
        lances_de_preparo=publicacao.nu_lances_de_preparo,
        maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
        minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances,
        personagens_possiveis=publicacao.co_personagens,
    )
    if not no_ar:
        argumentos["receita_em_avaliacao"] = RECEITAS_FORA_DO_AR[co_tipo]
    argumentos.update(extra)
    if not no_ar:
        return gerador.gerar_candidatos(DIA, **argumentos)
    # `patch.object` troca o atributo do módulo só dentro do `with`.
    with mock.patch.object(gerador, "escolher_jogo", lambda *a, **k: "quatro"),             mock.patch.object(gerador, "escolher_tipo", lambda *a, **k: co_tipo):
        return gerador.gerar_candidatos(DIA, **argumentos)


# ═══════════════════════════════════════════════════════════════════════════
# 1. As peças
# ═══════════════════════════════════════════════════════════════════════════


def test_toda_modalidade_do_quatro_no_rodizio_tem_contrato_e_acervo() -> None:
    """Modalidade sem acervo daria `FileNotFoundError` no dia dela, no job."""
    modalidades = gerador.MODALIDADES_POR_JOGO["quatro"]
    assert modalidades
    for co_modalidade in modalidades:
        assert co_modalidade in contrato_quatro.modalidades_declaradas()
        assert acervo_mod.caminho_do_acervo(co_modalidade).is_file()


def test_a_escolha_da_modalidade_do_quatro_e_a_tradicional() -> None:
    assert gerador.escolher_modalidade("quatro", DIA) == MODALIDADE


@pytest.mark.parametrize("semente", range(30))
def test_a_posicao_do_quatro_fica_na_faixa_do_preparo(semente: int) -> None:
    estado, continuacao = gerador._preparar_quatro(random.Random(semente), 10, MODALIDADE)
    janela = gerador.JANELA_DO_PREPARO_QUATRO
    assert 10 <= len(estado.lances) <= 10 + janela
    assert continuacao
    # A posição e a continuação são uma partida do acervo, inteira.
    partidas = {p.lances for p in acervo_mod.carregar(MODALIDADE).partidas}
    assert estado.lances + continuacao in partidas


def test_a_faixa_da_as_duas_cores() -> None:
    """O motivo da janela: com comprimento fixo, a vez seria sempre do mesmo."""
    vezes = {
        len(gerador._preparar_quatro(random.Random(s), 10, MODALIDADE)[0].lances) % 2
        for s in range(40)
    }
    assert vezes == {0, 1}


def test_a_vitoria_no_primeiro_lance_e_achada() -> None:
    arbitro = MotorQuatro(MODALIDADE)
    # O J1 tem três na coluna 1 e joga: `s1` fecha.
    assert gerador.vitoria_imediata_quatro(arbitro, _estado("s1s2s1s2s1s3")) == "s1"
    # A ameaça é do ADVERSÁRIO (o J2 tem três na 2), e não de quem joga.
    assert gerador.vitoria_imediata_quatro(arbitro, _estado("s1s2s1s2s3s2")) is None
    assert gerador.vitoria_imediata_quatro(arbitro, _estado("s4")) is None


def test_o_lance_que_empata_nao_e_vitoria_no_primeiro_lance() -> None:
    """O último lance de uma partida empatada ENCERRA a partida, e não é vitória:
    "acabou" não basta, tem de ser vitória de quem joga. A posição sai de uma
    partida empatada do acervo, um lance antes do fim."""
    arbitro = MotorQuatro(MODALIDADE)
    empatadas = [p for p in acervo_mod.carregar(MODALIDADE).partidas if p.vencedor == 0]
    assert empatadas
    vespera = EstadoQuatro(MODALIDADE, empatadas[0].lances[:-1])
    assert len(arbitro.lances_legais(vespera)) == 1
    assert gerador.vitoria_imediata_quatro(arbitro, vespera) is None


def test_o_carimbo_do_motor_do_quatro() -> None:
    assert gerador.versao_do_motor_de("quatro") == contrato_quatro.versao_do_motor()


def test_a_bancada_do_quatro_joga_e_arbitra_a_modalidade_do_candidato() -> None:
    receita = RECEITAS["quatro_virada"]
    estado = _estado("s4s4s3")
    candidato = gerador.Candidato(
        co_jogo="quatro",
        co_variante=MODALIDADE,
        co_modalidade=MODALIDADE,
        co_formato_posicao="sequencia_lances",
        js_posicao_inicial=posicao_mod.do_quatro(list(estado.lances), co_modalidade=MODALIDADE),
        receita=receita,
        js_chegada=receita.montar({}),
        js_objetivo={},
        co_personagem="tex",
        nu_semente=1,
        js_solucao={},
        nu_lances_solucao=0,
        parametros={},
        estado_inicial=estado,
    )
    bancada = gerador.bancada(candidato)
    assert isinstance(bancada.jogador, JogadorQuatro)
    assert bancada.arbitro is bancada.jogador.arbitro
    assert bancada.arbitro.co_modalidade == MODALIDADE
    # O juiz responde pela linha de chegada do candidato: a fita vazia não cumpre.
    assert bancada.julgar([]).cumpriu is False


# ═══════════════════════════════════════════════════════════════════════════
# 2. A prova vem antes do gabarito
# ═══════════════════════════════════════════════════════════════════════════


def test_posicao_reprovada_na_prova_nao_chega_ao_gabarito(monkeypatch, capsys) -> None:
    perguntas: list[str] = []

    def reprova(co_tipo, provador, estado, parametros, *, continuacao=None):
        perguntas.append(co_tipo)
        return provas_quatro.ProvaQuatro(False, "reprovada pelo teste")

    def resolver(*args, **kwargs):
        raise AssertionError("o gabarito foi buscado para uma posição reprovada")

    # Um provador de mentira: o real abriria o executável só para ser ignorado.
    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", reprova)
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(gerador, "_resolver", resolver)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    # ⚠️ A diagonal, e nao a virada (que era o tipo destes casos ate a T124b):
    # o caminho de "tipo em avaliacao" so aceita tipo fora do ar.
    assert _gerar("quatro_vencer_diagonal", tentativas_por_candidato=5) == []
    assert perguntas and set(perguntas) == {"quatro_vencer_diagonal"}
    assert "reprovada pelo teste" in capsys.readouterr().out


def test_na_figura_o_teto_do_gabarito_e_o_prazo_DESTE_candidato(monkeypatch) -> None:
    """No "Forme a figura" (T147) o prazo sai da posicao, e o teto do gabarito e
    apertado a ele: `2M - 1` meios-lances. A variante 0 (o T, folga 2, desde a
    triagem de 23/10/2026) declara 15, o teto do maior prazo; uma posicao com a
    figura a 2 casas tem M = 4, e o gabarito so pode olhar 7 meios-lances
    (depois disso a janela fechou)."""
    prazos: list[int] = []
    tetos: list[int] = []

    def aprova(co_tipo, provador, estado, parametros, *, continuacao=None):
        prazos.append(parametros["lances"])
        return provas_quatro.ProvaQuatro(True, "aprovada pelo teste")

    def resolver(*args, maximo_de_meios_lances, **kwargs):
        tetos.append(maximo_de_meios_lances)
        return None

    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", aprova)
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(gerador, "_resolver", resolver)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    assert _gerar("quatro_figura", tentativas_por_candidato=6) == []
    assert tetos and len(tetos) == len(prazos)
    assert tetos == [min(15, 2 * m - 1) for m in prazos]
    # E o aperto aconteceu de fato em alguma posicao (senao o caso nao mede nada).
    assert any(teto < 15 for teto in tetos), prazos


def test_vitoria_no_primeiro_lance_recusa_antes_da_prova(monkeypatch, capsys) -> None:
    """A recusa mais barata vem primeiro: a prova nem é perguntada."""

    def nao_pergunte(*args, **kwargs):
        raise AssertionError("a prova foi perguntada para uma posição que cai no lance 1")

    monkeypatch.setattr(gerador, "vitoria_imediata_quatro", lambda arbitro, estado: "s1")
    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", nao_pergunte)
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    assert _gerar("quatro_vencer_diagonal", tentativas_por_candidato=2) == []
    assert "cai no lance 1" in capsys.readouterr().out


def test_a_prova_recebe_a_continuacao_e_o_alvo_das_encostadas(monkeypatch) -> None:
    vistos: list[tuple] = []

    def anota(co_tipo, provador, estado, parametros, *, continuacao=None):
        vistos.append((estado, dict(parametros), continuacao))
        return provas_quatro.ProvaQuatro(False, "so anotando")

    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", anota)
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    _gerar("quatro_encostadas", tentativas_por_candidato=3)
    assert vistos
    arbitro = MotorQuatro(MODALIDADE)
    for estado, parametros, continuacao in vistos:
        tabuleiro = arbitro.tabuleiro(estado)
        encostadas = feitos_quatro.pecas_encostadas(
            arbitro.regras.dimensoes, tabuleiro, tabuleiro.vez
        )
        # O alvo é ABSOLUTO e sai da posição: o que já está encostado mais três.
        assert parametros["pecas"] == encostadas + 3
        assert parametros[editorial_mod.ENCOSTADAS_NA_POSICAO] == encostadas
        assert continuacao


# ═══════════════════════════════════════════════════════════════════════════
# 3. Um candidato de verdade, com o executável
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def executavel():
    try:
        jdq.caminho_do_executavel()
    except jdq.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do Quatro não está compilado: {erro}")


def test_um_candidato_das_encostadas_de_ponta_a_ponta(executavel) -> None:
    """Medido em 20/10/2026: a 1ª variante dá candidato nos três primeiros dias."""
    candidatos = _gerar("quatro_encostadas", quantos=1)
    assert len(candidatos) == 1
    candidato = candidatos[0]
    assert candidato.co_jogo == "quatro"
    assert candidato.co_variante == candidato.co_modalidade == MODALIDADE
    # A posição publicada se confere pelo mesmo caminho do job.
    posicao_mod.conferir(
        candidato.co_formato_posicao, candidato.js_posicao_inicial, co_modalidade=MODALIDADE
    )
    assert candidato.js_posicao_inicial["co_lances"] == candidato.estado_inicial.sequencia
    # O gabarito cumpre a chegada, e cada lance DO ADVERSÁRIO traz o motivo da
    # política. ⚠️ Desde a T124c (defeito 1) quem resolve as encostadas é o
    # perseguidor do objetivo (`gerador.SOLUCIONADOR_POR_TIPO`), e lance de
    # solucionador não tem `co_acao`: quem resolve não erra de propósito.
    bancada = gerador.bancada(candidato)
    fita = candidato.js_solucao["lances"]
    assert bancada.julgar(fita).cumpriu
    pessoa = candidato.js_posicao_inicial["vez_de"]
    do_adversario = [passo for passo in fita if passo["jogador"] != pessoa]
    assert do_adversario and all(passo.get("co_acao") for passo in do_adversario)
    assert not any(passo.get("co_acao") for passo in fita if passo["jogador"] == pessoa)
    # ⛔ E a BANCADA da régua entrega o perseguidor com a chegada do candidato
    # (`solucionadores.com_chegada`): sem ela, ele falharia só na hora de medir.
    from job.solucionadores import ContextoDoSolucionador
    from motores.nucleo.papeis import NivelDeMotor

    legais = bancada.arbitro.lances_legais(candidato.estado_inicial)
    lance = bancada.solucionador(
        ContextoDoSolucionador(
            arbitro=bancada.arbitro,
            jogador=bancada.jogador,
            estado_inicial=candidato.estado_inicial,
            estado=candidato.estado_inicial,
            nivel=NivelDeMotor.TEX,
            semente=1,
            lance_do_nivel=lambda: legais[0],
        )
    )
    assert lance in legais
    assert candidato.nu_lances_solucao >= editorial_mod.MINIMO_DE_MEIOS_LANCES_PADRAO


def test_o_mesmo_dia_gera_o_mesmo_candidato(executavel) -> None:
    """A idempotência de T038 vale para o Quatro: a semente sai do dia."""
    a = _gerar("quatro_encostadas", quantos=1)
    b = _gerar("quatro_encostadas", quantos=1)
    assert a[0].js_posicao_inicial == b[0].js_posicao_inicial
    assert a[0].js_solucao == b[0].js_solucao


# ═══════════════════════════════════════════════════════════════════════════
# 4. Os botões fora do ar e o medidor de variantes
# ═══════════════════════════════════════════════════════════════════════════

#: Os tipos cujo teto NÃO precisa chegar ao fim do tabuleiro (ver o editorial).
#: ⚠️ O "sem o meio" saiu daqui em 21/10/2026: a posição dele vem do banco
#: pescado, com vitórias de até 12 lances, e o teto passou a cobrir o tabuleiro.
#: ⚠️ O "Encoste N em ate M" (T143) entrou aqui em 22/10/2026: ele fecha no
#: MEIO, e depois do M-esimo lance da pessoa a janela fechou - o teto e `2M - 1`
#: (o caso logo abaixo do de "ate o fim").
TETO_PROPRIO = {"quatro_vencer_em_n", "quatro_encoste", "quatro_figura"}


#: Os numeros de cada tipo do Quatro, no ar ou fora dele (a promocao MOVE).
EDITORIAL_DO_QUATRO = {
    co_tipo: publicacoes
    for co_tipo, publicacoes in {
        **editorial_mod.EDITORIAL,
        **editorial_mod.EDITORIAL_FORA_DO_AR,
    }.items()
    if co_tipo.startswith("quatro_")
}


@pytest.mark.parametrize("co_tipo", sorted(EDITORIAL_DO_QUATRO))
def test_os_tipos_julgados_no_fim_tem_teto_ate_o_fim(co_tipo: str) -> None:
    """⛔ Com o teto padrão (20), um "não perca" nunca veria o fim da partida, e o
    tipo sairia SEM DESAFIO por um botão. O teto cobre o que resta do tabuleiro
    a partir do INÍCIO da faixa do preparo."""
    if co_tipo in TETO_PROPRIO:
        pytest.skip("teto fixado pela prova")
    for publicacao in EDITORIAL_DO_QUATRO[co_tipo]:
        assert (
            publicacao.nu_lances_de_preparo + publicacao.nu_maximo_de_meios_lances
            >= editorial_mod.CASAS_DO_TRADICIONAL
        )


def test_o_teto_da_figura_e_o_do_maior_prazo_e_cabe_acima_do_piso() -> None:
    """No "Forme a figura" o prazo sai da posicao (`distancia + folga`), e a
    variante declara o teto do MAIOR prazo possivel: distancia 6 (a maxima
    aceita) mais a folga. Os numeros por extenso: folga 1, 2 e 3, tetos 13, 15 e
    17. O gerador aperta o teto para `2M - 1` em cada candidato."""
    tetos = sorted(
        {
            (p.parametros["folga"], p.nu_maximo_de_meios_lances)
            for p in EDITORIAL_DO_QUATRO["quatro_figura"]
        }
    )
    assert tetos == [(1, 13), (2, 15), (3, 17)]
    for publicacao in EDITORIAL_DO_QUATRO["quatro_figura"]:
        assert publicacao.nu_minimo_de_meios_lances == 9
        assert publicacao.nu_minimo_de_meios_lances <= publicacao.nu_maximo_de_meios_lances


def test_as_variantes_da_figura_sao_as_14_da_triagem_e_do_catalogo() -> None:
    """Os pares (figura, folga) do editorial sao escritos a mao desde a triagem
    de 23/10/2026. ⚠️ Um nome errado ("quadrada") nao daria erro na geracao: a
    variante so nunca acharia lugar, e o dia sairia sem candidato. Por isso cada
    figura tem de existir no catalogo, cada folga tem de ser uma das medidas, e
    nenhum par se repete. Os 14 por extenso: a lista da triagem."""
    from job import figuras_quatro as fq

    pares = [
        (p.parametros[fq.CHAVE_FIGURA], p.parametros[fq.CHAVE_FOLGA_DA_FIGURA])
        for p in EDITORIAL_DO_QUATRO["quatro_figura"]
    ]
    # Sem repeticao: um par duplicado pesaria em dobro no rodizio de variantes.
    assert len(pares) == len(set(pares))
    for figura, folga in pares:
        assert figura in fq.FIGURAS_QUATRO, figura
        assert folga in fq.FOLGAS_DA_FIGURA, (figura, folga)
    assert sorted(pares) == sorted(
        [
            ("t", 2), ("t", 3), ("z", 3), ("igual", 1), ("igual", 2),
            ("losango", 1), ("losango", 2), ("c", 1), ("c", 3), ("i", 2),
            ("i", 3), ("quadrado", 2), ("quadrado", 3), ("xis", 3),
        ]
    )


def test_o_teto_do_encoste_e_a_JANELA_e_cabe_acima_do_piso() -> None:
    """No "Encoste" o teto e a janela (`2M - 1` meios-lances: M da pessoa e M - 1
    do adversario), e o piso padrao de 9 tem de caber nela - senao a variante
    nunca geraria. Os numeros por extenso: M de 5 a 7, tetos 9, 11 e 13."""
    tetos = sorted(
        {
            (p.parametros["lances"], p.nu_maximo_de_meios_lances)
            for p in EDITORIAL_DO_QUATRO["quatro_encoste"]
        }
    )
    assert tetos == [(5, 9), (6, 11), (7, 13)]
    for publicacao in EDITORIAL_DO_QUATRO["quatro_encoste"]:
        assert publicacao.nu_minimo_de_meios_lances == 9
        assert publicacao.nu_minimo_de_meios_lances <= publicacao.nu_maximo_de_meios_lances


@pytest.mark.parametrize("co_tipo", sorted(banco_mod.TIPOS_DO_BANCO))
def test_o_teto_dos_tipos_do_banco_cobre_a_posicao_mais_curta_do_banco(co_tipo) -> None:
    """O "preparo" dos tipos do banco é o comprimento mínimo de uma posição
    pescada: com ele, o cadeado acima garante o teto até o fim do tabuleiro. E
    o banco gravado não pode ter posição mais curta que isso."""
    for publicacao in EDITORIAL_DO_QUATRO[co_tipo]:
        assert publicacao.nu_lances_de_preparo == banco_mod.MINIMO_DE_LANCES_JOGADOS
    posicoes = banco_mod.carregar(MODALIDADE)[co_tipo]
    assert min(len(p.lances) for p in posicoes) >= banco_mod.MINIMO_DE_LANCES_JOGADOS


# ═══════════════════════════════════════════════════════════════════════════
# O banco pescado (T124c, 21/10/2026)
# ═══════════════════════════════════════════════════════════════════════════

#: Uma posição de mentira do banco (a prova não roda: o tabuleiro só precisa ser
#: legal). ⚠️ Ela cai no lance 1 (o s3 fecha a linha), então os casos que a usam
#: desligam a recusa do lance 1, que não é o que se confere aqui.
PESCADA = banco_mod.PosicaoDoBanco(
    lances=ler_sequencia("s1s7s2s7s4s6s5s6"), lances_da_pessoa=9, confronto="tex_tex"
)


@pytest.mark.parametrize("co_tipo", sorted(banco_mod.TIPOS_DO_BANCO))
def test_os_tipos_do_banco_tiram_a_posicao_do_BANCO_e_nao_refazem_a_prova(
    monkeypatch, co_tipo
) -> None:
    vistos: list[tuple[str, ...]] = []

    def resolver(jogador, base, **kwargs):
        # O gabarito recebe a posição PESCADA; parar aqui basta ao caso.
        vistos.append(tuple(base.lances))
        return None

    def nao_prove(*args, **kwargs):
        raise AssertionError("a prova foi refeita para uma posição do banco")

    def nao_sorteie_do_acervo(*args, **kwargs):
        raise AssertionError("um tipo do banco sorteou do acervo do gerador")

    monkeypatch.setattr(gerador.banco_quatro_mod, "sortear", lambda *a, **k: PESCADA)
    monkeypatch.setattr(gerador, "_preparar_quatro", nao_sorteie_do_acervo)
    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", nao_prove)
    monkeypatch.setattr(gerador, "vitoria_imediata_quatro", lambda arbitro, estado: None)
    monkeypatch.setattr(gerador, "_resolver", resolver)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    _gerar(co_tipo, tentativas_por_candidato=2)
    assert vistos and set(vistos) == {PESCADA.lances}


#: Outra posição legal (o espelho da `PESCADA`), para o banco de mentira do caso
#: abaixo ter duas posições distintas.
PESCADA_ESPELHO = banco_mod.PosicaoDoBanco(
    lances=ler_sequencia("s7s1s6s1s4s2s3s2"), lances_da_pessoa=8, confronto="tex_tex"
)


def test_o_GERADOR_sorteia_o_sem_o_meio_com_o_piso_do_tipo(monkeypatch) -> None:
    """O caminho do job inteiro, e não só o `sortear`: com um banco de mentira em
    que o "sem o meio" tem uma posição de 8 lances da pessoa e outra de 9, o
    gabarito só recebe a de 9. Pega o gerador passando o piso padrão (7), que
    deixaria a de 8 entrar."""
    vistos: list[tuple[str, ...]] = []

    def resolver(jogador, base, **kwargs):
        vistos.append(tuple(base.lances))
        return None

    banco_de_mentira = {"quatro_sem_o_meio": (PESCADA_ESPELHO, PESCADA)}
    monkeypatch.setattr(banco_mod, "carregar", lambda co_modalidade: banco_de_mentira)
    monkeypatch.setattr(gerador, "vitoria_imediata_quatro", lambda arbitro, estado: None)
    monkeypatch.setattr(gerador, "_resolver", resolver)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))

    _gerar("quatro_sem_o_meio", tentativas_por_candidato=12)
    assert vistos and set(vistos) == {PESCADA.lances}


def test_os_outros_tipos_do_quatro_continuam_no_acervo(monkeypatch) -> None:
    def nao_use_o_banco(*args, **kwargs):
        raise AssertionError("um tipo fora do banco sorteou do banco")

    monkeypatch.setattr(gerador.banco_quatro_mod, "sortear", nao_use_o_banco)
    monkeypatch.setattr(
        gerador.provas_quatro_mod, "provar",
        lambda *a, **k: provas_quatro.ProvaQuatro(False, "so conferindo a origem"),
    )
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))
    assert _gerar("quatro_bloquear", tentativas_por_candidato=2) == []


def test_os_tipos_do_banco_sao_perseguidos_no_gabarito() -> None:
    """A régua mede com o perseguidor; sem ele no registro, o Magno que só
    vence jogaria o gabarito, e no "sem o meio" ocuparia a coluna proibida."""
    for co_tipo in banco_mod.TIPOS_DO_BANCO:
        assert co_tipo in gerador.SOLUCIONADOR_POR_TIPO


def test_o_sorteio_do_banco_respeita_o_PISO_e_falha_alto_sem_posicao() -> None:
    curta = banco_mod.PosicaoDoBanco(("s4",) * 8, lances_da_pessoa=6, confronto="x")
    longa = banco_mod.PosicaoDoBanco(("s3",) * 8, lances_da_pessoa=7, confronto="x")
    banco = {"quatro_golpe_duplo": (curta, longa)}
    for semente in range(20):
        achada = banco_mod.sortear(
            random.Random(semente), "quatro_golpe_duplo", MODALIDADE, banco=banco
        )
        assert achada is longa
    with pytest.raises(banco_mod.BancoSemPosicao):
        banco_mod.sortear(
            random.Random(0), "quatro_golpe_duplo", MODALIDADE, banco=banco, piso=8
        )
    with pytest.raises(banco_mod.BancoSemPosicao):
        banco_mod.sortear(random.Random(0), "quatro_sem_o_meio", MODALIDADE, banco=banco)


def test_o_banco_gravado_tem_os_tres_tipos_acima_do_piso() -> None:
    """O arquivo que vai ao Railway: lido pelo leitor de produção, com posição
    acima do piso DO TIPO em cada um (senão o gerador falharia alto no dia do
    tipo)."""
    banco = banco_mod.carregar(MODALIDADE)
    assert set(banco) == set(banco_mod.TIPOS_DO_BANCO)
    for co_tipo, posicoes in banco.items():
        assert any(p.lances_da_pessoa >= banco_mod.piso_do_tipo(co_tipo) for p in posicoes)


def test_o_piso_do_sem_o_meio_e_9_e_os_outros_dois_continuam_em_7() -> None:
    """A decisão do dono de 22/10/2026 (§8zzzq): posições mais longas só no
    "sem o meio". ⚠️ Os números entram por extenso, e não lidos das constantes:
    um caso que lesse `PISO_POR_TIPO` passaria com qualquer valor lá dentro. O
    golpe duplo e a linha de cinco foram medidos e publicados com 7."""
    assert banco_mod.piso_do_tipo("quatro_sem_o_meio") == 9
    assert banco_mod.piso_do_tipo("quatro_golpe_duplo") == 7
    assert banco_mod.piso_do_tipo("quatro_linha_de_cinco") == 7
    # Todo tipo com piso próprio é um tipo do banco (um nome errado na tabela
    # deixaria o "sem o meio" no padrão, calado).
    assert set(banco_mod.PISO_POR_TIPO) <= banco_mod.TIPOS_DO_BANCO


def test_no_banco_gravado_o_sem_o_meio_sorteia_so_posicoes_de_9_lances_ou_mais() -> None:
    """Sem `piso=` (como o gerador chama), o sorteio do "sem o meio" no banco de
    produção nunca devolve uma posição de 5 a 8 lances da pessoa - e o banco tem
    dessas (o caso confere que a recusa foi exercida)."""
    posicoes = banco_mod.carregar(MODALIDADE)["quatro_sem_o_meio"]
    assert any(p.lances_da_pessoa < 9 for p in posicoes)
    assert sum(p.lances_da_pessoa >= 9 for p in posicoes) >= 20
    for semente in range(200):
        achada = banco_mod.sortear(random.Random(semente), "quatro_sem_o_meio", MODALIDADE)
        assert achada.lances_da_pessoa >= 9
    # E o golpe duplo continua alcançando as posições de 7 e 8.
    vistos = {
        banco_mod.sortear(random.Random(s), "quatro_golpe_duplo", MODALIDADE).lances_da_pessoa
        for s in range(400)
    }
    assert {7, 8} <= vistos


def test_o_banco_de_outra_modalidade_ou_formato_e_recusado(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(acervo_mod, "PASTA_DO_ACERVO", tmp_path)
    banco_mod.carregar.cache_clear()
    try:
        caminho = banco_mod.caminho_do_banco(MODALIDADE)
        caminho.write_text('{"versao": 1, "co_modalidade": "outra", "tipos": {}}', encoding="utf-8")
        with pytest.raises(ValueError, match="outra"):
            banco_mod.carregar(MODALIDADE)
        banco_mod.carregar.cache_clear()
        caminho.write_text('{"versao": 99, "co_modalidade": "tradicional", "tipos": {}}', encoding="utf-8")
        with pytest.raises(ValueError, match="99"):
            banco_mod.carregar(MODALIDADE)
        banco_mod.carregar.cache_clear()
        caminho.unlink()
        with pytest.raises(FileNotFoundError, match="pescar_posicoes_forcaveis_quatro"):
            banco_mod.carregar(MODALIDADE)
    finally:
        # O cache não pode guardar o banco de mentira para os casos seguintes.
        banco_mod.carregar.cache_clear()


def test_as_casas_do_tradicional_batem_com_o_contrato() -> None:
    dimensoes = contrato_quatro.dimensoes(MODALIDADE)
    assert editorial_mod.CASAS_DO_TRADICIONAL == dimensoes.largura * dimensoes.altura


def _medidor():
    caminho = Path(__file__).parents[2] / "scripts" / "medir_variantes_do_editorial.py"
    spec = importlib.util.spec_from_file_location("medir_variantes", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["medir_variantes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


MEDIDOR = _medidor()


def test_o_alvo_quatro_mede_os_tipos_fora_do_ar() -> None:
    tipos = MEDIDOR.tipos_do_alvo("quatro")
    assert tipos == sorted(t for t, r in RECEITAS_FORA_DO_AR.items() if r.co_jogo == "quatro")
    # Eram dez; a virada subiu na T124b, o vencer em N e o Segure na T124c, e a
    # diagonal e as encostadas com o perseguidor (T124c, defeito 1), e o golpe
    # duplo e a linha de cinco com o banco pescado (T124c, 21/10), e o "sem o
    # meio" com o piso de 9 (T124c, 22/10), e o "Encoste N em ate M" com a
    # regua de 18 dias (T143, 22/10). Sobram os dois aposentados, e o "Forme a
    # figura" (T147, 23/10), que espera a regua da T148.
    assert len(tipos) == 3
    assert MEDIDOR.tipos_do_alvo("quatro_bloquear") == ["quatro_bloquear"]
    # ⛔ E o `todos` de rotina continua sem eles.
    assert not set(MEDIDOR.tipos_do_alvo("todos")) & set(tipos)


def test_as_candidatas_do_quatro_tem_os_botoes_do_editorial_fora_do_ar() -> None:
    for co_tipo, publicacoes in editorial_mod.EDITORIAL_FORA_DO_AR.items():
        candidatas = MEDIDOR.candidatas_fora_do_ar(co_tipo)
        assert [c.parametros for c in candidatas] == [p.parametros for p in publicacoes]
        assert [c.nu_lances_de_preparo for c in candidatas] == [
            p.nu_lances_de_preparo for p in publicacoes
        ]
        assert [c.nu_maximo_de_meios_lances for c in candidatas] == [
            p.nu_maximo_de_meios_lances for p in publicacoes
        ]


def test_o_tipo_fora_do_ar_e_medido_como_em_avaliacao() -> None:
    for co_tipo in RECEITAS_FORA_DO_AR:
        assert MEDIDOR.receita_em_avaliacao_de(co_tipo) is RECEITAS_FORA_DO_AR[co_tipo]
    # O que está no ar segue pelo caminho normal.
    assert MEDIDOR.receita_em_avaliacao_de(next(iter(RECEITAS))) is None


def test_a_linha_da_regua_do_medidor_informa_o_jogo(monkeypatch) -> None:
    """⛔ Sem o `co_jogo`, a régua do medidor rodava em SÉRIE (o padrão seguro),
    inclusive nas damas: o mesmo número, oito vezes mais lento."""
    from job import regua

    vistos: list[str] = []

    def medir_candidato(**kwargs):
        vistos.append(kwargs.get("co_jogo", ""))
        return [regua.Medicao("cacau", 10, 0, "p", "m")]

    candidato = gerador.Candidato(
        co_jogo="quatro", co_variante=MODALIDADE, co_modalidade=MODALIDADE,
        co_formato_posicao="sequencia_lances", js_posicao_inicial={},
        receita=RECEITAS["quatro_virada"], js_chegada={}, js_objetivo={},
        co_personagem="tex", nu_semente=1, js_solucao={}, nu_lances_solucao=9,
        parametros={},
    )
    monkeypatch.setattr(regua, "medir_candidato", medir_candidato)
    monkeypatch.setattr(regua, "tentativa_com_motor", lambda **kwargs: None)
    monkeypatch.setattr(
        MEDIDOR.gerador_mod, "bancada",
        lambda c: gerador.Bancada(jogador=None, arbitro=None, estado_inicial=None, julgar=None),
    )
    MEDIDOR._linha_da_regua([candidato], teto=20, dia="2026-10-01")
    assert vistos == ["quatro"]


def test_jogo_fora_do_rodizio_mede_em_dias_seguidos() -> None:
    assert "quatro" not in gerador.JOGOS_DO_RODIZIO
    dias = MEDIDOR._dias_do_jogo("quatro", 3)
    assert [(d - dias[0]).days for d in dias] == [0, 1, 2]


# ═══════════════════════════════════════════════════════════════════════════
# A virada NO AR (T124b) - e o jogo ainda fora do rodizio
# ═══════════════════════════════════════════════════════════════════════════


def test_o_rodizio_ainda_NAO_sorteia_o_quatro() -> None:
    """🔒 Estar em `RECEITAS` nao faz o job gerar o Quatro: o JOGO vem da data.

    ⚠️ Desde a T120 o Quatro entra pela ADOCAO (`gerador.JOGOS_EM_ADOCAO`), e
    nunca pelo rodizio: sem a faixa de adocao, `escolher_jogo` continua dando so
    os dois jogos de sempre. Quem prova que ele aparece quando ha aparelhos na
    versao e `test_adocao_nao_muda_a_fila.py`.
    """
    assert "quatro" not in gerador.JOGOS_DO_RODIZIO
    assert "quatro" in gerador.JOGOS_EM_ADOCAO
    dias = [DIA.fromordinal(DIA.toordinal() + n) for n in range(60)]
    assert {gerador.escolher_jogo(dia) for dia in dias} == set(gerador.JOGOS_DO_RODIZIO)


def test_o_tipo_no_ar_gera_pelo_caminho_NORMAL_quando_o_quatro_for_do_dia(
    monkeypatch,
) -> None:
    """Com o Quatro como jogo do dia, o rodizio de tipo acha um tipo do Quatro
    no ar, e o caminho normal exige o vetor de verificacao - que existe.

    ⚠️ Nasceu na T124b como "a virada no ar", quando ela era o unico tipo do
    Quatro em `RECEITAS`. Com tres (T124c), o tipo do dia e o que o rodizio
    (`escolher_tipo`) escolhe, e o caso usa a publicacao DELE - nao a da virada.

    ⚠️ Desde a T120 o dia do Quatro sai da ADOCAO, e o caso usa o caminho real:
    uma faixa de 1 em 3 e o primeiro dia que ela da ao Quatro (antes, um duble
    trocava o `escolher_jogo` inteiro).
    """
    from job.adocao import Frequencia

    frequencias = {"quatro": Frequencia(um_dia_em=3)}
    # ⚠️ O primeiro dia do Quatro cujo tipo NAO vem do banco pescado: os tipos do
    # banco (`TIPOS_DO_BANCO`) nao passam pela prova da geracao que este caso
    # anota, e sim pelo banco. Ate 22/10/2026 o primeiro dia do Quatro caia num
    # tipo do acervo; com o "sem o meio" no ar, o rodizio passou a dar a ele.
    dia = next(
        d
        for d in (DIA.fromordinal(DIA.toordinal() + n) for n in range(90))
        if gerador.escolher_jogo(d, frequencias=frequencias) == "quatro"
        and gerador.escolher_tipo("quatro", d) not in banco_mod.TIPOS_DO_BANCO
    )
    escolhidos: list[str] = []

    def anota(co_tipo, provador, estado, parametros, *, continuacao=None):
        escolhidos.append(co_tipo)
        return provas_quatro.ProvaQuatro(False, "so anotando")

    monkeypatch.setattr(gerador.provas_quatro_mod, "provar", anota)
    monkeypatch.setattr(gerador.provas_quatro_mod, "ProvadorQuatro", lambda *a, **k: None)
    monkeypatch.setattr(JogadorQuatro, "motor_dart", property(lambda self: None))
    co_tipo = gerador.escolher_tipo("quatro", dia)
    assert RECEITAS[co_tipo].co_jogo == "quatro"
    publicacao = editorial_mod.EDITORIAL[co_tipo][0]
    assert (
        gerador.gerar_candidatos(
            dia,
            parametros=publicacao.parametros,
            frequencias=frequencias,
            quantos=1,
            tentativas_por_candidato=2,
            lances_de_preparo=publicacao.nu_lances_de_preparo,
            maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
            minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances,
        )
        == []
    )
    assert escolhidos and set(escolhidos) == {co_tipo}


def test_o_medidor_RECUSA_medir_a_virada_pelo_alvo_no_ar() -> None:
    """⛔ O gerador mediria outro jogo com o nome dela (ver
    `no_ar_e_fora_do_rodizio` no medidor): os alvos `no-ar` a deixam de fora
    (desde a T120, para sempre: o Quatro entra pela adocao, e nao pelo rodizio),
    e o pedido pelo nome sai vazio."""
    assert MEDIDOR.no_ar_e_fora_do_rodizio("quatro_virada")
    assert not MEDIDOR.no_ar_e_fora_do_rodizio("quatro_bloquear")  # fora do ar
    assert not MEDIDOR.no_ar_e_fora_do_rodizio("damas_sobreviver")
    assert "quatro_virada" not in MEDIDOR.tipos_do_alvo("no-ar")
    assert MEDIDOR.tipos_do_alvo("no-ar:quatro_virada") == []
    assert MEDIDOR.tipos_do_alvo("quatro_virada") == []
