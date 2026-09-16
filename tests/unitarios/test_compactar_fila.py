"""🔒 A compactação da fila: o aprovado que está longe desce para o buraco perto.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O dono descreveu o sintoma em 16/09/2026, depois de curar a fila no painel:

> *"Se eu rejeitar o desafio de amanhã e depois de amanhã, nenhum outro desafio
> já aprovado passa a ocupar o 'buraco' que ficou."*

⚠️ **O job já regenerava o buraco** - mas só na execução seguinte, de madrugada.
Uma reprovação às dez da noite deixava o dia seguinte vazio, com um desafio já
aprovado parado em D+5.

⚠️ E o caso real que motivou tudo: em 16/09 a fila estava
`15 ✅ · 16 ✅ · 17 ⛔ · 18 ✅ · 19 ✅ · 20 ✅ · 21 ⛔ · 22 ✅`, e o buraco do dia
**17** era o de amanhã.
"""

from __future__ import annotations

from datetime import date, timedelta

from job.compactar_fila import LinhaDaFila, remanejar, resumo

HOJE = date(2026, 9, 16)


def _dia(quantos: int) -> date:
    """`_dia(1)` é amanhã."""
    return HOJE + timedelta(days=quantos)


def _plano(quantos: int = 7) -> list[date]:
    """Os dias que a execução cobre, a partir de hoje."""
    return [_dia(n) for n in range(quantos)]


def _linha(quantos: int, co_tipo: str, co_curadoria: str = "aprovado") -> LinhaDaFila:
    return LinhaDaFila(
        dt_dia=_dia(quantos),
        id_desafio_dia=f"id-{quantos}",
        co_tipo_desafio=co_tipo,
        co_curadoria=co_curadoria,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. O caso do dono
# ═══════════════════════════════════════════════════════════════════════════


def test_o_aprovado_DISTANTE_desce_para_o_buraco_de_amanha() -> None:
    """🔒 O pedido, na forma mais curta: amanhã está vazio, D+5 está cheio."""
    fila = [
        _linha(0, "pontinhos_troca_favoravel"),
        # ⛔ o dia 1 (amanhã) não está aqui: é o buraco
        _linha(2, "pontinhos_paciencia"),
        _linha(5, "damas_sacrificio"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)

    assert len(mudancas) == 1
    assert mudancas[0].dt_de == _dia(5)
    assert mudancas[0].dt_para == _dia(1)
    assert mudancas[0].co_tipo_desafio == "damas_sacrificio"


def test_o_doador_e_o_MAIS_DISTANTE_e_nao_o_mais_proximo() -> None:
    """🔒 ⚠️ As duas escolhas preenchem o buraco; a diferença é onde fica o novo.

    Puxando do fim da fila, o buraco que sobra é o menos urgente que existe - e a
    próxima execução tem uma noite inteira para cobri-lo. Puxando o vizinho, o
    buraco andaria um dia e continuaria urgente.
    """
    fila = [_linha(2, "damas_coroar"), _linha(6, "pontinhos_paciencia")]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)

    assert mudancas[0].dt_de == _dia(6), "puxou o vizinho em vez do mais distante"


# ═══════════════════════════════════════════════════════════════════════════
# 2. A variabilidade
# ═══════════════════════════════════════════════════════════════════════════


def test_NAO_poe_o_mesmo_tipo_ao_lado_do_mesmo_tipo() -> None:
    """🔒 *"sem repetir desafios muito semelhantes em dias consecutivos"*.

    O buraco do dia 1 tem `damas_coroar` de cada lado (dias 0 e 2). O doador mais
    distante também é `damas_coroar` - e tem de ser recusado em favor do outro.
    """
    fila = [
        _linha(0, "damas_coroar"),
        _linha(2, "damas_coroar"),
        _linha(4, "pontinhos_paciencia"),
        _linha(6, "damas_coroar"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)

    assert len(mudancas) == 1
    assert mudancas[0].co_tipo_desafio == "pontinhos_paciencia"
    assert mudancas[0].dt_de == _dia(4)


def test_a_vizinhanca_e_RECALCULADA_a_cada_movimento() -> None:
    """🔒 ⛔ Duas mudanças na mesma execução não podem encostar tipos iguais.

    ⚠️ Os buracos são os dias 1 e 2, lado a lado. Os dois doadores mais distantes
    são ambos `damas_coroar`: se a vizinhança fosse calculada uma vez no início,
    os dois desceriam e ficariam grudados - que é o que o critério proíbe.
    """
    fila = [
        _linha(0, "pontinhos_paciencia"),
        _linha(4, "damas_coroar"),
        _linha(5, "pontinhos_cadeia_longa"),
        _linha(6, "damas_coroar"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)

    destinos = {m.dt_para: m.co_tipo_desafio for m in mudancas}
    if _dia(1) in destinos and _dia(2) in destinos:
        assert destinos[_dia(1)] != destinos[_dia(2)], (
            "dois tipos iguais foram parar em dias consecutivos"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ O que NÃO se move
# ═══════════════════════════════════════════════════════════════════════════


def test_o_CANDIDATO_nao_desce() -> None:
    """🔒 ⛔ Ele pode ser reprovado amanhã; adiantá-lo só adianta o problema."""
    fila = [_linha(0, "damas_coroar"), _linha(5, "damas_sacrificio", "candidato")]
    assert remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE) == []


def test_o_dia_com_CANDIDATO_nao_e_buraco() -> None:
    """🔒 ⚠️ Ele tem conteúdo esperando decisão - compactar por cima apagaria uma
    decisão que ainda não foi tomada."""
    fila = [
        _linha(0, "damas_coroar"),
        _linha(1, "pontinhos_paciencia", "candidato"),
        _linha(5, "damas_sacrificio"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)
    assert all(m.dt_para != _dia(1) for m in mudancas)


def test_o_DESCARTADO_deixa_o_dia_vago() -> None:
    """🔒 Um descartado não é um desafio: é um buraco com linha."""
    fila = [
        _linha(0, "damas_coroar"),
        _linha(1, "damas_sobreviver", "descartado"),
        _linha(5, "damas_sacrificio"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)
    assert mudancas[0].dt_para == _dia(1)


def test_NUNCA_move_para_a_frente() -> None:
    """🔒 ⛔ Um desafio só anda em direção a hoje.

    O único aprovado está no dia 1 e o buraco está no dia 5. Empurrá-lo adiaria
    conteúdo aprovado sem ninguém pedir - e ainda abriria um buraco em D+1.
    """
    fila = [_linha(n, f"tipo_{n}") for n in range(5)]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)
    assert mudancas == []


def test_NAO_toca_no_passado() -> None:
    """🔒 ⛔ Desafio publicado é imutável - reescrever a data de um dia vivido
    apagaria a história de quem o resolveu."""
    fila = [
        LinhaDaFila(
            dt_dia=HOJE - timedelta(days=3),
            id_desafio_dia="antigo",
            co_tipo_desafio="damas_coroar",
            co_curadoria="aprovado",
        ),
        _linha(5, "pontinhos_paciencia"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)
    assert all(m.id_desafio_dia != "antigo" for m in mudancas)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Os cantos
# ═══════════════════════════════════════════════════════════════════════════


def test_fila_CHEIA_nao_mexe_em_nada() -> None:
    """🔒 Sem buraco, nenhuma escrita - o caso comum, e o mais barato."""
    fila = [_linha(n, f"tipo_{n}") for n in range(7)]
    assert remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE) == []


def test_fila_VAZIA_nao_inventa_movimento() -> None:
    """🔒 Sem doador não há o que mover: quem cobre é a geração."""
    assert remanejar([], dias_do_plano=_plano(), dt_hoje=HOJE) == []


def test_o_resumo_do_log_nomeia_o_que_MUDOU() -> None:
    """🔒 ⚠️ O log precisa dizer o que andou, não só quantos andaram.

    Uma linha *"2 mudanças"* não permite conferir nada depois; com o tipo e as
    duas datas, o dono confere a fila no painel sem abrir o banco.
    """
    fila = [_linha(0, "damas_coroar"), _linha(5, "pontinhos_paciencia")]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE)
    texto = resumo(mudancas)
    assert "pontinhos_paciencia" in texto
    assert str(_dia(5)) in texto and str(_dia(1)) in texto
    assert resumo([]) == "nenhuma"
