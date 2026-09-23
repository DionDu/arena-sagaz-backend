"""T036/T037/T038 - a prova de termino, as medidas de saida e a gravacao.

As tres pecas que fecham o BLOCO 2 do lado do job. Nenhuma delas toca banco, e
nenhuma roda motor: o que elas guardam sao **regras**, e regra se testa com
numero pequeno.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from job.estado_terminal import Prova, prova_a_partir_da_regua
from job.gravacao import (
    DIAS_MAXIMOS,
    DIAS_MINIMOS,
    SQL_PUBLICAR_O_DIA,
    GravacaoInvalida,
    conferir_plano,
    dias_a_cobrir,
    montar_plano,
    versao_do_catalogo,
)
from job.medidas_de_saida import (
    MULTIPLO_DA_ECONOMIA_DE_LANCES,
    PARAMETRO_LANCES_DA_SOLUCAO,
    MedidasInvalidas,
    conferir,
    direcao_de,
    lances_do_solucionador,
    linha_da_economia_de_lances,
    linha_de_faixa,
    linha_de_fracao,
    linha_so_medida,
    regua_de_tempo,
)


# ═══════════════════════════════════════════════════════════════════════════
# T036 — a prova de que a partida tem fim
# ═══════════════════════════════════════════════════════════════════════════


class _Veredito:
    """Um veredito falso, com a mesma forma do que o arbitro devolve."""

    def __init__(self, acabou: bool, co_motivo: str | None = None) -> None:
        self.acabou = acabou
        self.co_motivo = co_motivo


def test_uma_execucao_terminal_BASTA() -> None:
    """⚠️ A pergunta e se a partida PODE acabar, e nao se ela SEMPRE acaba.

    Um desafio em que so um dos caminhos leva ao fim continua sendo um desafio de
    um jogo que tem fim.
    """
    prova = prova_a_partir_da_regua(
        [_Veredito(False), _Veredito(True, "vitoria_brancas"), _Veredito(False)]
    )
    assert prova.tem_fim is True
    assert prova.co_motivo == "vitoria_brancas"
    assert prova.de_descarte is None


def test_nenhuma_execucao_terminal_DESCARTA() -> None:
    prova = prova_a_partir_da_regua([_Veredito(False), _Veredito(False)])
    assert prova.tem_fim is False
    assert prova.de_descarte


def test_lista_vazia_e_FALHA_e_nao_sucesso() -> None:
    """⚠️ "Nada a inspecionar" nao pode virar "aprovado".

    E o mesmo principio do cadeado de uniao de XP: nada a varrer e falha.
    """
    assert prova_a_partir_da_regua([]).tem_fim is False


def test_o_motivo_de_descarte_distingue_NAO_PROVADO_de_SEM_FIM() -> None:
    """🔒 As duas coisas sao diferentes, e a linha precisa dizer qual foi.

    Descartar por nao conseguir provar nao e o mesmo que provar que o jogo nao
    acaba — e quem investigar uma fila curta meses depois precisa saber a
    diferenca.
    """
    motivo = Prova(tem_fim=False, nu_lances=200).de_descarte
    assert motivo is not None
    assert "NAO prova" in motivo
    assert "200 lances" in motivo


# ═══════════════════════════════════════════════════════════════════════════
# T037 — as medidas de saida
# ═══════════════════════════════════════════════════════════════════════════


def _conjunto_valido() -> list[dict]:
    """Um conjunto de medidas que fecha: 0,600 + 0,400 + 0,000 = 1,000."""
    return [
        linha_de_faixa(
            "caixas_fechadas", nu_ordem=1, vr_peso="0.600", vr_min=0, vr_max=4
        ),
        # ⚠️ A economia de lances como o job a publica desde a T049t: FAIXA
        # de L a 3L. ⛔ Até 23/09/2026 esta fixture era a fração sobre
        # `lances_da_solucao` - o próprio defeito, aprovado como "válido".
        linha_da_economia_de_lances(
            {PARAMETRO_LANCES_DA_SOLUCAO: 4}, nu_ordem=2, vr_peso="0.400"
        ),
        linha_so_medida("caixas_do_adversario", nu_ordem=3),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# T049t — a fração sem denominador, e a economia de lances que a substituiu
# ═══════════════════════════════════════════════════════════════════════════


def test_T049t_fracao_sobre_chave_FORA_do_catalogo_e_recusada() -> None:
    """🔒 O defeito exato que o editorial publicou de 10 a 23/09/2026.

    `lances_da_solucao` ⛔ é medida de jogo nenhum: o aplicativo recusava
    calcular `Q` (`MedidaDeSaidaInvalida`) e o servidor, a resolução - e ninguém
    conseguia resolver aqueles desafios. O `conferir` roda ANTES de gravar.
    """
    linhas = _conjunto_valido()
    linhas[1] = linha_de_fracao(
        "lances_do_jogador",
        nu_ordem=2,
        vr_peso="0.400",
        co_sobre="lances_da_solucao",
    )
    with pytest.raises(MedidasInvalidas, match="nao esta no catalogo"):
        conferir(linhas)


def test_T049t_fracao_sobre_medida_de_SESSAO_e_recusada() -> None:
    """O denominador é medida da mesma PARTIDA - tempo e tentativas ⛔ são."""
    linhas = _conjunto_valido()
    linhas[1] = linha_de_fracao(
        "lances_do_jogador",
        nu_ordem=2,
        vr_peso="0.400",
        co_sobre="tentativas",
    )
    with pytest.raises(MedidasInvalidas, match="nao e medida do tabuleiro"):
        conferir(linhas)


def test_T049t_fracao_sobre_medida_do_TABULEIRO_continua_aceita() -> None:
    """⚠️ O par das duas de cima: a guarda mira a CHAVE, e ⛔ a forma.

    Sem este caso, recusar toda `fracao` passaria nos dois testes acima.
    """
    linhas = _conjunto_valido()
    linhas[1] = linha_de_fracao(
        "lances_do_jogador",
        nu_ordem=2,
        vr_peso="0.400",
        co_sobre="caixas_fechadas",
    )
    conferir(linhas)


def test_T049t_a_economia_de_lances_e_FAIXA_de_L_a_3L() -> None:
    """🔒 A decisão do dono (§8v): nota cheia no gabarito, zero em 3x.

    ⚠️ Os números entram escritos (4 e 12), e ⛔ lidos da constante: um caso que
    lesse `MULTIPLO_DA_ECONOMIA_DE_LANCES` passaria com qualquer múltiplo.
    """
    linha = linha_da_economia_de_lances(
        {PARAMETRO_LANCES_DA_SOLUCAO: 4}, nu_ordem=2, vr_peso="0.400"
    )
    assert linha["co_feito"] == "lances_do_jogador"
    assert linha["co_normalizacao"] == "faixa"
    assert linha["co_sobre"] is None
    assert linha["vr_min"] == Decimal("4")
    assert linha["vr_max"] == Decimal("12")
    assert MULTIPLO_DA_ECONOMIA_DE_LANCES == 3


def test_T049t_solucao_sem_lance_de_quem_resolve_e_recusada() -> None:
    """Sem L a faixa degenera (min = max = 0) - e dividiria por zero."""
    with pytest.raises(MedidasInvalidas, match="0 lance"):
        linha_da_economia_de_lances(
            {PARAMETRO_LANCES_DA_SOLUCAO: 0}, nu_ordem=2, vr_peso="0.400"
        )


def test_T049t_L_conta_SO_os_lances_de_quem_resolve() -> None:
    """⚠️ A solução das damas traz os dois lados.

    O `damas_coroar` de 23/09/2026 no `des`: 9 lances na solução, 5 da pessoa.
    Com o total, a faixa começaria em 9 - e quem jogou os 5 do gabarito
    ganharia a mesma nota de quem jogou 9.
    """
    solucao = {
        "lances": [
            {"n": n, "jogador": 1 if n % 2 else -1, "lance": "x"}
            for n in range(1, 10)
        ]
    }
    assert lances_do_solucionador(solucao, vez_de=1) == 5
    assert lances_do_solucionador(solucao, vez_de=-1) == 4


def test_um_conjunto_que_fecha_passa() -> None:
    conferir(_conjunto_valido())


def test_os_pesos_precisam_somar_1000() -> None:
    """🔒 E a soma que mantem `Q` dentro de [0, 1].

    ⚠️ E ela e teste, e nao `CHECK`: soma entre linhas nao cabe num `CHECK` de
    linha.
    """
    linhas = _conjunto_valido()
    linhas[0]["vr_peso"] = Decimal("0.500")
    with pytest.raises(MedidasInvalidas, match="somam"):
        conferir(linhas)


def test_os_pesos_sao_DECIMAL_e_nao_float() -> None:
    """⚠️ `0.6 + 0.4` em ponto flutuante nao da `1.0`.

    Um conjunto correto seria reprovado pela aritmetica, e alguem "consertaria" o
    teste afrouxando a comparacao — que e como uma regra vira decoracao.
    """
    soma = sum((l["vr_peso"] for l in _conjunto_valido()), start=Decimal("0"))
    assert soma == Decimal("1.000")
    assert isinstance(soma, Decimal)


def test_chave_fora_do_catalogo_e_RECUSADA() -> None:
    """⚠️ Uma chave inventada e uma medida que nenhum jogo produz.

    A parcela pagaria zero para sempre, e nada acusaria.
    """
    linhas = _conjunto_valido()
    linhas[0]["co_feito"] = "caixas_fechada"  # sem o "s"
    with pytest.raises(MedidasInvalidas, match="fora do catalogo"):
        conferir(linhas)


def test_medida_de_SESSAO_no_merito_e_RECUSADA() -> None:
    """⛔ Tempo, tentativas e dicas ja tem peso proprio em `Q` (RF-DES-042).

    ⚠️ Pesa-las tambem no merito faria a mesma medida contar **duas vezes** - e
    a soma dos relativos continuaria 1,000, entao nenhuma outra conferencia
    veria. Achado em 16/09/2026, ao ligar as quatro parcelas no servidor.
    """
    linhas = _conjunto_valido()
    linhas[0] = linha_de_faixa(
        "tempo_ate_resolver", nu_ordem=1, vr_peso="0.600", vr_min=0, vr_max=60000
    )
    with pytest.raises(MedidasInvalidas, match="sessao"):
        conferir(linhas)


def test_as_de_TABULEIRO_continuam_aceitas() -> None:
    """⚠️ A guarda acima mira a **procedencia**, e nao uma lista de nomes.

    Sem este par, a recusa poderia estar barrando qualquer coisa e o caso de cima
    passaria igual.
    """
    conferir(_conjunto_valido())


def test_faixa_sem_maximo_divide_por_nulo() -> None:
    linhas = _conjunto_valido()
    linhas[0]["vr_max"] = None
    with pytest.raises(MedidasInvalidas, match="vr_min e vr_max"):
        conferir(linhas)


def test_faixa_com_maximo_igual_ao_minimo_e_recusada() -> None:
    """Iguais dividiriam por zero na hora de normalizar."""
    linhas = _conjunto_valido()
    linhas[0]["vr_min"] = Decimal("4")
    linhas[0]["vr_max"] = Decimal("4")
    with pytest.raises(MedidasInvalidas, match="maior que"):
        conferir(linhas)


def test_nenhuma_SO_existe_com_peso_zero() -> None:
    """⚠️ `nenhuma` e "medido e exibido, nao pontuado" — com peso, seria mentira.

    O `ck003_faixa` da migracao diz o mesmo; falhar aqui aponta para quem montou
    as linhas, e nao para um `INSERT` que estourou tres camadas abaixo.
    """
    linhas = _conjunto_valido()
    linhas[2]["vr_peso"] = Decimal("0.100")
    with pytest.raises(MedidasInvalidas):
        conferir(linhas)


def test_ordem_repetida_e_recusada() -> None:
    """O Raio-X mostraria duas medidas na mesma posicao."""
    linhas = _conjunto_valido()
    linhas[1]["nu_ordem"] = 1
    with pytest.raises(MedidasInvalidas, match="nu_ordem"):
        conferir(linhas)


def test_desafio_sem_medida_nenhuma_e_recusado() -> None:
    with pytest.raises(MedidasInvalidas):
        conferir([])


@pytest.mark.parametrize(
    "co_feito, esperada",
    [
        ("caixas_fechadas", "maior_melhor"),
        ("tempo_ate_resolver", "menor_melhor"),
        ("tentativas", "menor_melhor"),
        ("dicas_usadas", "menor_melhor"),
        ("vitoria", "marco_atingido"),
    ],
)
def test_a_direcao_vem_do_CATALOGO(co_feito: str, esperada: str) -> None:
    """🔒 O defeito mais silencioso da economia de XP.

    Mais tempo, mais tentativas e mais dica **reduzem**; mais merito aumenta. Uma
    parcela na direcao errada nao daria erro nenhum — so pagaria mais a quem jogou
    pior. Por isso a direcao mora no catalogo, uma vez, e este modulo a LE.
    """
    assert direcao_de(co_feito) == esperada


def test_a_regua_de_tempo_nunca_e_degenerada() -> None:
    """Teto igual ao piso faria a parcela de tempo dividir por zero."""
    piso, teto = regua_de_tempo(nu_tempo_do_gabarito_ms=30_000)
    assert piso == 30_000
    assert teto > piso


def test_a_regua_de_tempo_tem_piso_minimo() -> None:
    """⚠️ Um gabarito de 200 ms daria uma janela que ninguem alcanca.

    O piso minimo existe para que "rapido" continue sendo humano.
    """
    piso, teto = regua_de_tempo(nu_tempo_do_gabarito_ms=200)
    assert piso >= 5_000
    assert teto > piso


# ═══════════════════════════════════════════════════════════════════════════
# T038 — a gravacao
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_saber_a_proxima_execucao_cobre_o_MINIMO() -> None:
    """⚠️ E a conta inclui HOJE.

    Um job que comecasse em D+1 deixaria o proprio dia da execucao descoberto
    justamente quando a fila tivesse acabado — a situacao em que ele mais precisa
    cobrir.
    """
    hoje = date(2026, 9, 10)
    dias = dias_a_cobrir(dt_hoje=hoje)
    assert len(dias) == DIAS_MINIMOS
    assert dias[0] == hoje


def test_com_proxima_execucao_distante_cobre_ate_la_MAIS_a_folga() -> None:
    """Cobrir so ate a proxima execucao nao deixaria margem nenhuma.

    Bastaria ela falhar para o dia seguinte ficar vazio.
    """
    hoje = date(2026, 9, 10)
    dias = dias_a_cobrir(dt_hoje=hoje, dt_proxima_execucao=hoje + timedelta(days=7))
    assert len(dias) == 7 + DIAS_MINIMOS


def test_a_cobertura_nunca_passa_do_MAXIMO() -> None:
    """⚠️ Gerar com muita antecedencia faz o dono aprovar conteudo que so vai ao
    ar dali a meses, sem saber o que mais estara publicado junto."""
    hoje = date(2026, 9, 10)
    dias = dias_a_cobrir(dt_hoje=hoje, dt_proxima_execucao=hoje + timedelta(days=90))
    assert len(dias) == DIAS_MAXIMOS


def test_proxima_execucao_no_passado_e_recusada() -> None:
    hoje = date(2026, 9, 10)
    with pytest.raises(GravacaoInvalida):
        dias_a_cobrir(dt_hoje=hoje, dt_proxima_execucao=hoje - timedelta(days=1))


def test_o_plano_MARCA_os_dias_ja_publicados_em_vez_de_pula_los() -> None:
    """⚠️ E o que permite ao log distinguir "fila cheia" de "job nao fez nada".

    Um numero sozinho ("gerei 2") nao diz qual das duas aconteceu.
    """
    hoje = date(2026, 9, 10)
    publicados = [hoje, hoje + timedelta(days=1)]
    plano = montar_plano(dt_hoje=hoje, dias_ja_publicados=publicados)

    assert len(plano) == DIAS_MINIMOS
    assert [p.ja_publicado for p in plano[:2]] == [True, True]
    assert sum(1 for p in plano if p.precisa_gerar) == DIAS_MINIMOS - 2


def test_o_plano_e_conferido_contra_a_folga() -> None:
    hoje = date(2026, 9, 10)
    conferir_plano(montar_plano(dt_hoje=hoje, dias_ja_publicados=[]))

    curto = montar_plano(dt_hoje=hoje, dias_ja_publicados=[])[:3]
    with pytest.raises(GravacaoInvalida, match="minimo"):
        conferir_plano(curto)

    with pytest.raises(GravacaoInvalida, match="vazio"):
        conferir_plano([])


def test_a_idempotencia_mora_no_BANCO() -> None:
    """🔒 ⛔ Uma checagem "ja existe?" antes do INSERT nao basta.

    Duas execucoes simultaneas passariam as duas pela checagem, e so o `UNIQUE`
    as separa. A checagem do plano existe para **evitar trabalho**, nunca para
    garantir a unicidade.
    """
    assert "ON CONFLICT (dt_dia) DO NOTHING" in SQL_PUBLICAR_O_DIA
    assert "INSERT INTO desafio_dia.tb001_desafio_dia" in SQL_PUBLICAR_O_DIA


def test_o_carimbo_do_catalogo_sai_do_MANIFESTO() -> None:
    """⚠️ Uma constante aqui poderia discordar da dimensao sem nada acusar.

    E o `nu_versao_catalogo` e `NOT NULL`: sem ele, o `INSERT` falharia depois de
    toda a medicao ter sido feita.
    """
    versao = versao_do_catalogo()
    assert isinstance(versao, int)
    assert versao >= 1
