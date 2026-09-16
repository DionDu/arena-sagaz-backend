"""🔒 A pescaria que responde por VARIOS alvos na mesma busca.

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

⚠️ **Pergunta do dono, 16/09/2026, com a pescaria de uma coroacao ja rodando:**

> *"o script nao conseguiria em uma unica busca ja buscar coroacao de 2 damas e
> de 1 dama, economizando metade do tempo? Ou realmente precisa ser separado?"*

✅ **Consegue, e a economia e maior que metade** — e a razao e estrutural, nao um
truque: o lance sai de `motor.escolher_lance(estado, SAGAZ, limite, semente)`, e
**o objetivo nao entra na escolha**. O Sagaz joga a PARTIDA, nao o DESAFIO. Entao,
para a mesma FEN e a mesma modalidade, a fita e identica quer se procure uma
coroacao, duas ou tres; o que muda e so o `julgar_desafio` a cada meio-lance.

⛔ **Procurar `{damas: 1}` PARA quando a primeira coroa; `{damas: 2}` continua.**
Uma busca unica que vai ate o alvo mais exigente ja contem a resposta do menos
exigente — o custo do combinado e o do mais caro sozinho, e os outros saem de
graca.

⚠️ **A equivalencia das duas funcoes foi provada contra o motor de verdade** (5
FENs reais do acervo, `resolve` x `resolve_varios_alvos`, resultado identico nas
5). Este arquivo guarda o que e barato de guardar: o formato do diario, os nomes
dos alvos e os resumos — a parte que um `assert` pega sem pagar minutos de busca.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pescar_moldes_de_partidas import (
    _alvos_do_diario,
    _nome_do_alvo,
    _por_alvo,
    _resumo_da_medicao,
    _resumo_da_peneira,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O nome do alvo — ele vai para o diario, entao tem de ser ESTAVEL
# ═══════════════════════════════════════════════════════════════════════════


def test_o_nome_sai_do_que_DIFERE_do_padrao() -> None:
    """Um rotulo curto: so o que este alvo tem de diferente."""
    padrao = {"damas": 1, "lances": 6}
    assert _nome_do_alvo({"damas": 2, "lances": 6}, padrao) == "damas=2"
    assert _nome_do_alvo({"damas": 2, "lances": 10}, padrao) == "damas=2,lances=10"


def test_o_alvo_IGUAL_ao_padrao_tem_nome_proprio() -> None:
    """⛔ Um nome vazio viraria chave vazia no diario, e duas pescarias
    diferentes poderiam colidir nela sem ninguem notar."""
    padrao = {"damas": 1, "lances": 6}
    assert _nome_do_alvo(padrao, padrao) == "damas=1,lances=6"


def test_o_nome_NAO_depende_da_ordem_em_que_o_dono_escreveu() -> None:
    """🔒 Retomar com as chaves invertidas pareceria outro alvo.

    ⚠️ E o diario recusaria a retomada, mandando recomecar horas de pescaria por
    causa da ordem das chaves num JSON — que nao significa nada.
    """
    padrao = {"damas": 1, "lances": 6}
    a = _nome_do_alvo({"damas": 3, "lances": 10}, padrao)
    b = _nome_do_alvo({"lances": 10, "damas": 3}, padrao)
    assert a == b == "damas=3,lances=10"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O diario antigo continua legivel
# ═══════════════════════════════════════════════════════════════════════════


def test_o_formato_ANTIGO_de_um_alvo_so_continua_lido() -> None:
    """⚠️ Diarios escritos antes de 16/09/2026 guardam um numero solto.

    ⛔ Quebrar isso apagaria, na pratica, as ~3 h da pescaria de 16/09 e as ~7 h
    das anteriores — e "nada e apagado" e regra do projeto.
    """
    # Formato novo: um valor por alvo.
    assert _por_alvo({"damas=1": 9, "damas=2": 15}, "damas=1") == 9
    assert _por_alvo({"damas=1": 9, "damas=2": None}, "damas=2") is None
    # Formato antigo: um numero solto responde por qualquer alvo perguntado.
    assert _por_alvo(7, "damas=1") == 7
    assert _por_alvo(None, "damas=1") is None


def test_os_alvos_saem_do_proprio_DIARIO() -> None:
    """⛔ Uma lista escrita a mao ficaria cega quando o diario mudasse."""

    class DiarioFalso:
        peneira = {"fen1": {"damas=1": 9, "damas=2": 15}}
        medicao: dict = {}

    assert _alvos_do_diario(DiarioFalso()) == ["damas=1", "damas=2"]

    class DiarioAntigo:
        peneira = {"fen1": 9}
        medicao: dict = {}

    # ⚠️ Sem alvo nomeado, um alvo anonimo — e os resumos saem sem rotulo.
    assert _alvos_do_diario(DiarioAntigo()) == [""]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Os resumos separam os alvos — juntar mentiria sobre os dois
# ═══════════════════════════════════════════════════════════════════════════


class _Diario:
    """Um diario de mentira, com o formato que a pescaria grava."""

    def __init__(self, peneira: dict, medicao: dict) -> None:
        self.peneira = peneira
        self.medicao = medicao


def test_o_resumo_da_peneira_CONTA_CADA_ALVO_separado() -> None:
    """⛔ Somar os dois diria "6 elegiveis" onde ha 4 de um tipo e 2 de outro.

    ⚠️ E a decisao que esse numero alimenta e *"vale a pena publicar esta
    variante?"* — que e por variante, nunca pelo total.
    """
    diario = _Diario(
        peneira={
            "a": {"damas=1": 9, "damas=2": 15},
            "b": {"damas=1": 11, "damas=2": None},
            "c": {"damas=1": None, "damas=2": None},
        },
        medicao={},
    )
    resumo = _resumo_da_peneira(diario)
    assert "[damas=1] elegiveis 2" in resumo
    assert "[damas=2] elegiveis 1" in resumo
    # A distancia tambem e por alvo.
    assert "9L:1" in resumo and "11L:1" in resumo
    assert "15L:1" in resumo


def test_o_resumo_da_medicao_exige_o_MINIMO_DE_MODALIDADES() -> None:
    """🔒 Um molde que so serve a duas modalidades nao e molde.

    ⚠️ O piso e `MINIMO_DE_MODALIDADES` (3 de 4), e ele vale **por alvo**: o mesmo
    tabuleiro pode servir as quatro para uma coroacao e a nenhuma para duas.
    """
    diario = _Diario(
        peneira={"W:W9,13:B20,24": {"damas=1": 9, "damas=2": 15}},
        medicao={
            # 4 modalidades validas para um alvo, so 2 para o outro.
            "W:W9,13:B20,24": {
                "damas=1": [9, 9, 11, 9],
                "damas=2": [15, None, None, 17],
            }
        },
    )
    resumo = _resumo_da_medicao(diario)
    assert "[damas=1] moldes 1" in resumo
    assert "[damas=2] moldes 0" in resumo


def test_o_resumo_sem_alvo_nomeado_nao_poe_ROTULO() -> None:
    """⚠️ Um `[]` vazio na tela pareceria defeito."""
    diario = _Diario(peneira={"a": 9, "b": None}, medicao={})
    resumo = _resumo_da_peneira(diario)
    assert "[]" not in resumo
    assert "elegiveis 1" in resumo


# ═══════════════════════════════════════════════════════════════════════════
# 4. A trava que impede misturar dois acervos no mesmo arquivo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_assinatura_do_diario_LEVA_os_alvos() -> None:
    """🔒 Retomar com outro alvo misturaria dois acervos, e pareceria normal.

    ⛔ Metade das posicoes julgada por *"coroar 1"* e metade por *"coroar 2"*, num
    arquivo so — e o bloco final publicaria a mistura. ⚠️ Provado contra o script
    de verdade em 16/09: a retomada e recusada, dizendo qual campo divergiu.
    """
    fonte = Path("scripts/pescar_moldes_de_partidas.py").read_text(encoding="utf-8")
    assert '"parametros": [' in fonte
    assert "[nome, sorted(valores.items())] for nome, valores in sorted(alvos.items())" in fonte


def test_a_peneira_aprova_quem_passou_em_PELO_MENOS_UM_alvo() -> None:
    """⚠️ Exigir todos jogaria fora o acervo de uma coroacao inteiro.

    ⛔ E jogaria fora **de graca**: a medicao custa o mesmo para um alvo ou tres,
    porque a fita e uma so. Exigir os tres seria pagar o caro e guardar o pouco.
    """
    fonte = Path("scripts/pescar_moldes_de_partidas.py").read_text(encoding="utf-8")
    assert "if any(" in fonte
    assert "_por_alvo(diario.peneira.get(f), nome) is not None for nome in alvos" in fonte


def test_o_bloco_final_sai_UM_POR_ALVO() -> None:
    """⛔ Uma lista so publicaria o desafio errado.

    ⚠️ Coroar duas damas e uma tarefa diferente de coroar uma: o molde que serve a
    uma pode nao servir a outra, e `job/tipos_de_desafio.py` precisa de um acervo
    por tarefa.
    """
    fonte = Path("scripts/pescar_moldes_de_partidas.py").read_text(encoding="utf-8")
    assert "for nome in alvos:" in fonte
    assert 'print(f"\\n# ── colar em job/tipos_de_desafio.py{rotulo} ──")' in fonte


def test_a_distancia_e_impressa_em_MEIOS_LANCES_com_a_conversao() -> None:
    """⛔ A ambiguidade "lance x meio-lance" ja custou TRES leituras erradas.

    ⚠️ O dono em 12/09 (leu "teto de 12" como doze lances dele), e o assistente em
    11/09 e de novo em 16/09 — a ultima virou um acervo apresentado como "distancia
    de 3 a 11 lances" quando eram meios-lances, metade disso.
    """
    fonte = Path("scripts/pescar_moldes_de_partidas.py").read_text(encoding="utf-8")
    assert "distancia ate o objetivo (meios-lances, media das modalidades)" in fonte
    assert "meios-lances (~{-(-meios // 2)} do jogador)" in fonte


def test_varios_alvos_sao_nomeados_pelo_que_os_DISTINGUE_ENTRE_SI() -> None:
    """⛔ Nomear contra o padrao saiu confuso, e esta foi a primeira versao.

    Com o padrao `{damas: 1, lances: 6}`, o alvo `{damas: 1, lances: 10}` virava
    `lances=10` — **sem a palavra `damas`** — ao lado de `damas=2,lances=10`. ⚠️ O
    leitor precisava saber o padrao de cor para entender que o primeiro era "uma
    dama".
    """
    from scripts.pescar_moldes_de_partidas import _nomear_alvos

    padrao = {"damas": 1, "lances": 6}
    nomes = list(
        _nomear_alvos(
            [
                {"damas": 1, "lances": 10},
                {"damas": 2, "lances": 10},
                {"damas": 3, "lances": 10},
            ],
            padrao,
        )
    )
    # ⚠️ `lances` e igual nos tres, entao nao distingue nada e sai do nome.
    assert nomes == ["damas=1", "damas=2", "damas=3"]


def test_um_alvo_so_continua_nomeado_contra_o_PADRAO() -> None:
    """⚠️ Sem com quem comparar, o rotulo mais curto e o diff do padrao."""
    from scripts.pescar_moldes_de_partidas import _nomear_alvos

    nomes = list(_nomear_alvos([{"damas": 2, "lances": 10}], {"damas": 1, "lances": 6}))
    assert nomes == ["damas=2,lances=10"]


def test_alvos_REPETIDOS_colapsam_num_so() -> None:
    """⚠️ Medir o mesmo alvo duas vezes seria pagar o dobro pelo mesmo numero."""
    from scripts.pescar_moldes_de_partidas import _nomear_alvos

    alvos = _nomear_alvos(
        [{"damas": 2, "lances": 10}, {"damas": 2, "lances": 10}],
        {"damas": 1, "lances": 6},
    )
    assert len(alvos) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. A janela tem de caber no teto — o defeito nº 1 desta familia
# ═══════════════════════════════════════════════════════════════════════════


def test_a_pescaria_RECUSA_janela_que_nao_cabe_no_teto() -> None:
    """🔒 Uma janela maior que o teto nunca fecha, e o log nao acusa a causa.

    ⛔ **Ja custou uma cacada inteira:** a primeira do `damas_sobreviver`
    (10/09/2026) aprovou ZERO moldes porque o teto ficava abaixo da janela do
    tipo — e o motivo registrado era `nao_cumpriu_no_teto`, indistinguivel de
    *"o jogo nao permite"*.

    ⚠️ **E o risco voltou em 16/09**, quando `--parametros` passou a deixar o dono
    escrever a janela a mao. A aritmetica: os lados alternam e o jogador comeca,
    entao o N-esimo lance DELE e o meio-lance `2N - 1`.

    ⛔ **Erro, e nao aviso** — um aviso seria lido depois de trinta segundos de
    barra de progresso, quando a pescaria ja parece estar indo bem.
    """
    fonte = Path("scripts/pescar_moldes_de_partidas.py").read_text(encoding="utf-8")
    assert "preciso = 2 * valores[\"lances\"] - 1" in fonte
    assert "if preciso > teto:" in fonte
    assert "raise SystemExit(" in fonte


def test_a_janela_de_10_CABE_no_teto_de_20() -> None:
    """✅ A aritmetica da pescaria que o dono vai rodar, travada aqui.

    10 lances do jogador → o 10º lance dele e o meio-lance 19, e o teto e 20.
    ⚠️ Se alguem baixar `nu_maximo_de_meios_lances` do `damas_coroar`, este teste
    cai antes de a pescaria gastar horas para nao achar nada.
    """
    from job.editorial import variantes_de

    teto = max(p.nu_maximo_de_meios_lances for p in variantes_de("damas_coroar"))
    assert 2 * 10 - 1 <= teto, f"janela de 10 lances nao cabe no teto {teto}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. A tabela que escolhe o `p` da frase
# ═══════════════════════════════════════════════════════════════════════════


def test_a_tabela_do_p_usa_a_aritmetica_2p_menos_1() -> None:
    """🔒 Um molde cabe em `p` quando a solucao cabe em `p` lances DO JOGADOR.

    ⚠️ Os lados alternam e o jogador comeca, entao o `p`-esimo lance dele e o
    meio-lance `2p - 1`. ⛔ Usar `2p` daria um lance a mais de folga e a tabela
    prometeria moldes que a variante nao publicaria.
    """
    from collections import Counter

    from scripts.pescar_moldes_de_partidas import tabela_do_p

    # Um molde de 9 meios-lances cabe em p = 5 (o 5º lance e o meio-lance 9).
    linhas = tabela_do_p(Counter({9: 1}), 0)
    assert any("p =  5 lances: 1 moldes" in linha for linha in linhas)
    # E nao cabe em p = 4 (o 4º lance e o meio-lance 7).
    assert not any("p =  4 lances" in linha for linha in linhas)


def test_a_tabela_do_p_MOSTRA_o_efeito_do_piso() -> None:
    """⛔ Sem a coluna do piso a tabela mentiria sobre o que o job publica.

    ⚠️ Com o acervo de 16/09 (133 moldes) e o piso de 9, `p = 6` renderia 133
    moldes pela distancia e **20** de verdade — o gerador recusa o resto. A
    diferenca so apareceria como *"sem candidato"* semanas depois.
    """
    from collections import Counter

    from scripts.pescar_moldes_de_partidas import tabela_do_p

    real = Counter({3: 43, 4: 13, 5: 21, 6: 10, 7: 12, 8: 14, 9: 10, 10: 7, 11: 3})
    linhas = "\n".join(tabela_do_p(real, 9))
    assert "p =  6 lances: 133 moldes  (com o piso de hoje: 20)" in linhas
    # ⚠️ E o acervo de hoje NAO chega a p = 7: ele foi pescado com teto 12.
    assert "p =  7 lances" not in linhas


def test_a_tabela_do_p_some_quando_nao_ha_molde() -> None:
    """⚠️ Um cabecalho sozinho pareceria defeito."""
    from collections import Counter

    from scripts.pescar_moldes_de_partidas import tabela_do_p

    assert tabela_do_p(Counter(), 0) == []


def test_sem_piso_a_tabela_nao_poe_a_COLUNA() -> None:
    """⚠️ `(com o piso de hoje: N)` repetindo o mesmo numero seria so ruido."""
    from collections import Counter

    from scripts.pescar_moldes_de_partidas import tabela_do_p

    linhas = "\n".join(tabela_do_p(Counter({3: 5, 9: 2}), 0))
    assert "com o piso" not in linhas
