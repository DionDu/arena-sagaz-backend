"""O QUATRO EM LINHA DESENHADO NO PAINEL (27/10/2026).

Relato do dono: o dia 28/10/2026, o primeiro do Quatro no calendario do `des`,
respondia *Internal Server Error*. O Quatro grava o MESMO formato do Pontinhos
(`sequencia_lances`), e o desenho mandava a posicao para o Pontinhos, que tentou
ler `s4` como traco (`H_0_1`) e estourou.

O que estes casos protegem:

  · **o dia do Quatro abre** (o caso exato do relato);
  · **a posicao e a do arbitro**: cada peca desenhada e a que o `MotorQuatro`
    diz que esta la, nas cores dos jogadores;
  · **a fita do gabarito** sai quadro a quadro, com o aro de ouro no ultimo lance;
  · **uma sequencia torta vira aviso desenhado**, nunca um 500;
  · **o Pontinhos continua indo para o Pontinhos**.
"""

from __future__ import annotations

from dataclasses import replace

from api.desafios.painel import desenho, pagina
from motores.quatro.motor_quatro import MotorQuatro
from tests.unitarios.test_painel_curadoria import POSICAO_PONTINHOS, _desafio

#: A posicao publicada do desafio de 28/10/2026 no `des` (a do relato).
LANCES_DO_RELATO = "s4 s4 s4 s4 s5 s3 s3 s3 s3 s5 s2 s4 s2 s6 s6".split()

POSICAO_QUATRO = {
    "versao": 1,
    "vez_de": -1,
    "co_jogo": "quatro",
    "co_lances": "".join(LANCES_DO_RELATO),
    "co_modalidade": "tradicional",
    "sequencia_lances": LANCES_DO_RELATO,
    "co_formato_posicao": "sequencia_lances",
}

SOLUCAO_QUATRO = {
    "lances": [
        {"n": 1, "lance": "s4", "jogador": -1},
        {"n": 2, "lance": "s3", "jogador": 1},
        {"n": 3, "lance": "s6", "jogador": -1},
    ],
    "lance_chave": 3,
}


def _tabuleiro(lances: list[str]):
    motor = MotorQuatro("tradicional")
    return motor.tabuleiro(motor.estado_de_sequencia("".join(lances)))


def _pecas(svg: str, cor: str) -> int:
    """Quantos furos estao pintados com [cor]."""
    return svg.count(f'fill="{cor}" stroke="{desenho.MADEIRA_ESC}"')


def test_o_dia_do_QUATRO_abre_no_painel() -> None:
    """🔒 O relato: a pagina do dia com o Quatro respondia 500."""
    item = replace(
        _desafio(co_curadoria="aprovado", co_jogo="quatro", posicao=POSICAO_QUATRO,
                 co_formato="sequencia_lances"),
        js_solucao=SOLUCAO_QUATRO,
        co_modalidade="tradicional",
    )
    from datetime import date

    html = pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=date(2026, 10, 28), desafio=item),
        dt_hoje=date(2026, 10, 27),
        dt_sugerida=date(2026, 10, 27),
        dt_fim_janela_baixada=date(2026, 10, 30),
    )
    assert 'aria-label="tabuleiro do Quatro em Linha"' in html


def test_as_pecas_sao_as_que_o_ARBITRO_diz_nas_cores_dos_jogadores() -> None:
    svg = desenho.posicao("sequencia_lances", POSICAO_QUATRO, maior=True)
    tabuleiro = _tabuleiro(LANCES_DO_RELATO)
    j1 = sum(p == 1 for coluna in tabuleiro.colunas for p in coluna)
    j2 = sum(p == -1 for coluna in tabuleiro.colunas for p in coluna)
    assert (j1, j2) == (8, 7)  # 15 lances, o J1 abriu
    assert _pecas(svg, desenho.AZUL_J1) == j1
    assert _pecas(svg, desenho.VERMELHO_J2) == j2
    # E o resto dos 42 furos, vazio.
    assert _pecas(svg, desenho.PAPEL) == 42 - j1 - j2


def test_a_peca_cai_no_CHAO_e_nao_no_topo() -> None:
    """Um lance so (`s1`): a peca azul fica na fileira de BAIXO do desenho."""
    svg = desenho.quatro({"co_jogo": "quatro", "co_modalidade": "tradicional",
                          "sequencia_lances": ["s1"]})
    # Na miniatura a casa tem 26 px e a margem 6: o chao (linha 1) tem o
    # centro em y = 6 + 5,5 x 26 = 149.
    assert f'cy="149.0" r="9.9" fill="{desenho.AZUL_J1}"' in svg


def test_a_fita_do_gabarito_sai_QUADRO_A_QUADRO_com_o_aro_no_ultimo_lance() -> None:
    quadros = desenho.fita_da_solucao("sequencia_lances", POSICAO_QUATRO, SOLUCAO_QUATRO)
    assert [q["tipo"] for q in quadros] == ["inicio", "lance", "lance", "lance"]
    # Cada quadro tem uma peca a mais que o anterior.
    totais = [
        _pecas(q["svg"], desenho.AZUL_J1) + _pecas(q["svg"], desenho.VERMELHO_J2)
        for q in quadros
    ]
    assert totais == [15, 16, 17, 18]
    # O aro de ouro so nos quadros de lance, e um por quadro.
    assert [q["svg"].count(f'stroke="{desenho.OURO}"') for q in quadros] == [0, 1, 1, 1]
    # Quem resolve e o `vez_de` (-1): o 1o lance e "voce".
    assert quadros[1]["de_quem"] == "voce"
    assert quadros[3]["chave"]


def test_sequencia_TORTA_vira_aviso_e_nao_500() -> None:
    """Sete pecas numa coluna de seis: o arbitro recusa, e o painel mostra o motivo."""
    torta = {"co_jogo": "quatro", "co_modalidade": "tradicional",
             "sequencia_lances": ["s1"] * 7}
    svg = desenho.posicao("sequencia_lances", torta)
    assert "Quatro:" in svg and "tabuleiro do Quatro" not in svg


def test_modalidade_DESCONHECIDA_vira_aviso_e_nao_500() -> None:
    svg = desenho.posicao(
        "sequencia_lances", {**POSICAO_QUATRO, "co_modalidade": "pop_out_futuro"}
    )
    assert "Quatro:" in svg


def test_sem_a_lista_le_a_sequencia_CONCATENADA() -> None:
    sem_lista = {k: v for k, v in POSICAO_QUATRO.items() if k != "sequencia_lances"}
    assert desenho.posicao("sequencia_lances", sem_lista) == desenho.posicao(
        "sequencia_lances", POSICAO_QUATRO
    )


def test_o_PONTINHOS_continua_indo_para_o_pontinhos() -> None:
    """O controle: sem `co_jogo: quatro`, o mesmo formato e o do Pontinhos."""
    svg = desenho.posicao("sequencia_lances", POSICAO_PONTINHOS)
    assert "tabuleiro do Quatro" not in svg
    assert desenho.posicao("sequencia_lances", POSICAO_PONTINHOS) == desenho.pontinhos(
        POSICAO_PONTINHOS
    )
