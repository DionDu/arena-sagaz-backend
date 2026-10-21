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
from pathlib import Path

import pytest

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
    """`gerar_candidatos` com os botões da variante 0 do editorial fora do ar."""
    publicacao = editorial_mod.EDITORIAL_FORA_DO_AR[co_tipo][0]
    argumentos = dict(
        parametros=publicacao.parametros,
        quantos=1,
        lances_de_preparo=publicacao.nu_lances_de_preparo,
        maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
        minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances,
        personagens_possiveis=publicacao.co_personagens,
        receita_em_avaliacao=RECEITAS_FORA_DO_AR[co_tipo],
    )
    argumentos.update(extra)
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
TETO_PROPRIO = {"quatro_vencer_em_n", "quatro_sem_o_meio"}


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


def test_o_teto_do_sem_o_meio_e_o_da_prova() -> None:
    (publicacao,) = editorial_mod.EDITORIAL_FORA_DO_AR["quatro_sem_o_meio"]
    assert publicacao.nu_maximo_de_meios_lances == provas_quatro.MAXIMO_SEM_O_MEIO


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
    # Eram dez; a virada subiu na T124b, o vencer em N e o Segure na T124c.
    assert len(tipos) == 7
    assert MEDIDOR.tipos_do_alvo("quatro_encostadas") == ["quatro_encostadas"]
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
    dia = next(
        DIA.fromordinal(DIA.toordinal() + n)
        for n in range(30)
        if gerador.escolher_jogo(
            DIA.fromordinal(DIA.toordinal() + n), frequencias=frequencias
        )
        == "quatro"
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
    assert not MEDIDOR.no_ar_e_fora_do_rodizio("quatro_encostadas")  # fora do ar
    assert not MEDIDOR.no_ar_e_fora_do_rodizio("damas_sobreviver")
    assert "quatro_virada" not in MEDIDOR.tipos_do_alvo("no-ar")
    assert MEDIDOR.tipos_do_alvo("no-ar:quatro_virada") == []
    assert MEDIDOR.tipos_do_alvo("quatro_virada") == []
