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
from job.vizinhanca import conflita

HOJE = date(2026, 9, 16)

#: Uma janela baixada que termina HOJE: nenhum dia futuro travado.
#:
#: ⚠️ Os casos deste arquivo medem as regras de antes de 07/10/2026 (buraco,
#: doador, vizinhanca) e precisam de doadores em D+2 e D+3. A janela de verdade
#: tem caso proprio, no fim do arquivo.
SEM_JANELA = HOJE


def _dia(quantos: int) -> date:
    """`_dia(1)` é amanhã."""
    return HOJE + timedelta(days=quantos)


def _plano(quantos: int = 7) -> list[date]:
    """Os dias que a execução cobre, a partir de hoje."""
    return [_dia(n) for n in range(quantos)]


def _linha(
    quantos: int,
    co_tipo: str,
    co_curadoria: str = "aprovado",
    *,
    co_jogo: str | None = None,
    co_personagem: str | None = None,
    co_modalidade: str | None = None,
) -> LinhaDaFila:
    """Uma linha da fila em `HOJE + quantos`.

    ⚠️ Jogo, personagem e modalidade ficam `None` por padrao: `None` desliga
    **aquela** comparacao (`vizinhanca.conflita`), e e assim que os casos antigos,
    escritos so com o tipo, continuam medindo so o tipo.
    """
    return LinhaDaFila(
        dt_dia=_dia(quantos),
        id_desafio_dia=f"id-{quantos}",
        co_tipo_desafio=co_tipo,
        co_curadoria=co_curadoria,
        co_jogo=co_jogo,
        co_personagem=co_personagem,
        co_modalidade=co_modalidade,
    )


def _aplicar(fila: list[LinhaDaFila], mudancas) -> dict[date, LinhaDaFila]:
    """A fila DEPOIS das mudancas, por dia — para conferir o resultado inteiro."""
    por_id = {linha.id_desafio_dia: linha for linha in fila}
    por_dia = {linha.dt_dia: linha for linha in fila}
    for m in mudancas:
        linha = por_id[m.id_desafio_dia]
        del por_dia[m.dt_de]
        por_dia[m.dt_para] = linha
    return por_dia


def _sem_vizinhos_parecidos(por_dia: dict[date, LinhaDaFila]) -> None:
    """Nenhum par de dias consecutivos pode conflitar (`job/vizinhanca.py`)."""
    for dia, linha in por_dia.items():
        seguinte = por_dia.get(dia + timedelta(days=1))
        if seguinte is None:
            continue
        assert not conflita(linha.ocupante(), seguinte.ocupante()), (
            f"{dia} e {dia + timedelta(days=1)} ficaram parecidos: "
            f"{linha.ocupante()} x {seguinte.ocupante()}"
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
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

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
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

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
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

    # O buraco de amanha recebe o UNICO doador que nao repete os vizinhos.
    para_amanha = [m for m in mudancas if m.dt_para == _dia(1)]
    assert len(para_amanha) == 1
    assert para_amanha[0].co_tipo_desafio == "pontinhos_paciencia"
    assert para_amanha[0].dt_de == _dia(4)
    # ⚠️ E nenhuma mudanca, em lugar nenhum, encosta dois tipos iguais.
    # (Ate 02/10/2026 este caso contava "uma mudanca so"; o `damas_coroar` de
    # D+6 nao descia para D+5 porque conflitava CONSIGO MESMO no dia vizinho.
    # A regra nova tira o doador do lugar antes de comparar - ver
    # `test_o_doador_nao_conflita_CONSIGO_MESMO`.)
    _sem_vizinhos_parecidos(_aplicar(fila, mudancas))


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
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

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
    assert remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA) == []


def test_o_dia_com_CANDIDATO_nao_e_buraco() -> None:
    """🔒 ⚠️ Ele tem conteúdo esperando decisão - compactar por cima apagaria uma
    decisão que ainda não foi tomada."""
    fila = [
        _linha(0, "damas_coroar"),
        _linha(1, "pontinhos_paciencia", "candidato"),
        _linha(5, "damas_sacrificio"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    assert all(m.dt_para != _dia(1) for m in mudancas)


def test_o_DESCARTADO_deixa_o_dia_vago() -> None:
    """🔒 Um descartado não é um desafio: é um buraco com linha."""
    fila = [
        _linha(0, "damas_coroar"),
        _linha(1, "damas_sobreviver", "descartado"),
        _linha(5, "damas_sacrificio"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    assert mudancas[0].dt_para == _dia(1)


def test_NUNCA_move_para_a_frente() -> None:
    """🔒 ⛔ Um desafio só anda em direção a hoje.

    O único aprovado está no dia 1 e o buraco está no dia 5. Empurrá-lo adiaria
    conteúdo aprovado sem ninguém pedir - e ainda abriria um buraco em D+1.
    """
    fila = [_linha(n, f"tipo_{n}") for n in range(5)]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
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
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    assert all(m.id_desafio_dia != "antigo" for m in mudancas)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Os cantos
# ═══════════════════════════════════════════════════════════════════════════


def test_fila_CHEIA_nao_mexe_em_nada() -> None:
    """🔒 Sem buraco, nenhuma escrita - o caso comum, e o mais barato."""
    fila = [_linha(n, f"tipo_{n}") for n in range(7)]
    assert remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA) == []


def test_fila_VAZIA_nao_inventa_movimento() -> None:
    """🔒 Sem doador não há o que mover: quem cobre é a geração."""
    assert remanejar([], dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA) == []


def test_o_resumo_do_log_nomeia_o_que_MUDOU() -> None:
    """🔒 ⚠️ O log precisa dizer o que andou, não só quantos andaram.

    Uma linha *"2 mudanças"* não permite conferir nada depois; com o tipo e as
    duas datas, o dono confere a fila no painel sem abrir o banco.
    """
    fila = [_linha(0, "damas_coroar"), _linha(5, "pontinhos_paciencia")]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    texto = resumo(mudancas)
    assert "pontinhos_paciencia" in texto
    assert str(_dia(5)) in texto and str(_dia(1)) in texto
    assert resumo([]) == "nenhuma"


# ═══════════════════════════════════════════════════════════════════════════
# 5. A alternancia de jogo, personagem e modalidade (02/10/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ O dono, ao pedir que os desafios nascessem pre-aprovados: *"E claro que
# sempre precisa garantir a alternancia de jogos/modalidades/personagens do
# desafio de um dia para o outro"*. Ate ali a compactacao so olhava o tipo.


def test_NAO_poe_o_mesmo_JOGO_em_dias_consecutivos() -> None:
    """🔒 Buraco entre dois dias de damas: o doador de damas mais distante e
    recusado, e quem desce e o de Pontinhos, mesmo estando mais perto."""
    fila = [
        _linha(0, "damas_coroar", co_jogo="damas"),
        _linha(2, "damas_sacrificio", co_jogo="damas"),
        _linha(4, "pontinhos_paciencia", co_jogo="pontinhos"),
        _linha(6, "damas_sobreviver", co_jogo="damas"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

    para_amanha = [m for m in mudancas if m.dt_para == _dia(1)]
    assert [m.dt_de for m in para_amanha] == [_dia(4)]
    _sem_vizinhos_parecidos(_aplicar(fila, mudancas))


def test_NAO_poe_o_mesmo_PERSONAGEM_em_dias_consecutivos() -> None:
    """🔒 Jogos alternando nao bastam: o Tex dois dias seguidos tambem e repeticao."""
    fila = [
        _linha(0, "pontinhos_paciencia", co_jogo="pontinhos", co_personagem="tex"),
        _linha(2, "pontinhos_cadeia_longa", co_jogo="pontinhos", co_personagem="pita"),
        _linha(4, "damas_coroar", co_jogo="damas", co_personagem="cacau"),
        _linha(6, "damas_sacrificio", co_jogo="damas", co_personagem="tex"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

    para_amanha = [m for m in mudancas if m.dt_para == _dia(1)]
    # O de D+6 e o mais distante, mas e o Tex - o mesmo de hoje.
    assert [m.dt_de for m in para_amanha] == [_dia(4)]
    _sem_vizinhos_parecidos(_aplicar(fila, mudancas))


def test_NAO_poe_a_mesma_MODALIDADE_em_dias_consecutivos() -> None:
    """🔒 A modalidade so compara quando os DOIS dias tem uma."""
    fila = [
        _linha(0, "damas_coroar", co_modalidade="anglo"),
        _linha(2, "damas_sacrificio", co_modalidade="casa"),
        _linha(4, "damas_sobreviver", co_modalidade="portuguesa"),
        _linha(6, "damas_capturar_multipla", co_modalidade="anglo"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)

    para_amanha = [m for m in mudancas if m.dt_para == _dia(1)]
    assert [m.dt_de for m in para_amanha] == [_dia(4)]


def test_sem_doador_compativel_o_buraco_fica_para_a_GERACAO() -> None:
    """🔒 ⚠️ A regra vale mais que o buraco tapado agora: se todo doador repete
    um vizinho, nada desce - e a geracao, que desvia dos vizinhos ao escolher
    jogo e personagem, cobre o dia."""
    fila = [
        _linha(0, "damas_coroar", co_jogo="damas"),
        _linha(2, "damas_sacrificio", co_jogo="damas"),
        _linha(5, "damas_sobreviver", co_jogo="damas"),
    ]
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    assert all(m.dt_para != _dia(1) for m in mudancas)


def test_o_doador_nao_conflita_CONSIGO_MESMO() -> None:
    """🔒 Buraco em D+5 e doador em D+6: o vizinho de cima do buraco E o doador.

    ⚠️ Ate 02/10/2026 ele era comparado com o proprio lugar, conflitava consigo
    mesmo e nunca descia um dia. Ele sai do lugar antes da comparacao.
    """
    fila = [_linha(n, f"tipo_{n}", co_jogo=("a" if n % 2 else "b")) for n in range(5)]
    # D+4 e do jogo "b", entao o doador e do "a" - so o proprio lugar o barraria.
    fila.append(_linha(6, "tipo_6", co_jogo="a"))
    mudancas = remanejar(fila, dias_do_plano=_plano(), dt_hoje=HOJE, dt_fim_janela_baixada=SEM_JANELA)
    assert [(m.dt_de, m.dt_para) for m in mudancas] == [(_dia(6), _dia(5))]
