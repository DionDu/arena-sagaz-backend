"""O ALVO QUE SAI DO MATERIAL — `damas_sacrificio` (14/09/2026).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE MECANISMO PRECISOU EXISTIR
═══════════════════════════════════════════════════════════════════════════

O `damas_sacrificio` pede *"troque 1 peca por 3 de Pita"*, e isso e uma afirmacao
sobre **quanto sobrou dos dois lados**. Escrever `material_restante <= 4` a mao no
editorial valeria para um molde e mentiria em todos os outros: os moldes pescados
de partidas reais tem de 5 a 12 pecas por lado.

⛔ **E os dois erros possiveis sao silenciosos:**

  · teto alto demais  →  o desafio ja nasce cumprido, e a pessoa "resolve" no
                         primeiro toque;
  · teto baixo demais →  ninguem cumpre, o gerador nao acha candidato, e o
                         sintoma chega como **dia descoberto**, semanas depois.

⚠️ **E o irmao mais velho deste mecanismo ja existia:** `acima_do_guloso` faz o
mesmo com as caixas do Pontinhos desde 11/09/2026. A diferenca e o preco — medir
o guloso custa uma partida inteira, e contar pecas custa um `split`.
"""

from __future__ import annotations

import pytest

from job import editorial as editorial_mod
from job.moldes_de_damas import (
    SEM_SOLUCAO_DE_UM_LANCE,
    CUMPRIU_O_OBJETIVO,
    material_de_quem_joga,
    objetivo_no_primeiro_lance,
)
from job.editorial import EDITORIAL
from job.tipos_de_desafio import RECEITAS
from motores.nucleo.chegada import LinhaDeChegada, avaliar


# ═══════════════════════════════════════════════════════════════════════════
# 1. Contar as pecas — e contar as do lado CERTO
# ═══════════════════════════════════════════════════════════════════════════


def test_o_material_e_de_QUEM_JOGA_e_nao_das_brancas():
    """⛔ O erro que esta funcao existe para nao deixar acontecer.

    ⚠️ **A posicao publicada de um desafio de damas sai com as PRETAS a jogar:**
    o molde tem as brancas (`W:`), o gerador joga um lance de variacao, e e com as
    pretas que a pessoa resolve. Contar sempre as brancas devolveria o numero do
    lado errado — e devolveria **um numero**, que parece certo.
    """
    posicao = "W:W18,22,26:B10,11,14,15,19"
    assert material_de_quem_joga(posicao) == (3, 5)

    # A MESMA posicao, com a vez trocada: o par vira do avesso.
    assert material_de_quem_joga("B" + posicao[1:]) == (5, 3)


def test_uma_dama_conta_como_UMA_peca():
    """⚠️ Material aqui e contagem de pecas, e nao de pontos.

    O `K` fica colado na casa (`K31`), entao ele nao atrapalha a contagem — mas
    tambem nao vale dois. ⛔ Se um dia valer, e a chegada do sacrificio que muda
    de significado, e nao so esta funcao.
    """
    assert material_de_quem_joga("W:WK31,27:B10,K14") == (2, 2)


# ═══════════════════════════════════════════════════════════════════════════
# 2. A traducao: relativo -> absoluto
# ═══════════════════════════════════════════════════════════════════════════


def test_capturar_e_entregar_viram_tetos_absolutos():
    """A conta e a mais simples possivel, e e por isso que ela cabe no gerador."""
    efetivos = editorial_mod.parametros_efetivos(
        {"capturar": 3, "entregar": 1}, material=(8, 7)
    )
    assert efetivos["resta_ao_adversario"] == 4   # 7 - 3
    assert efetivos["resta_a_voce"] == 7          # 8 - 1


def test_os_numeros_RELATIVOS_continuam_no_dicionario():
    """⚠️ Porque e deles que a FRASE se serve.

    A clausula le `resta_ao_adversario`; o enunciado le `capturar`. ⛔ Apagar os
    relativos na traducao deixaria o desafio com a regra certa e a frase vazia —
    e a frase vazia so apareceria na tela de quem jogasse.
    """
    efetivos = editorial_mod.parametros_efetivos(
        {"capturar": 3, "entregar": 1}, material=(8, 7)
    )
    assert efetivos["capturar"] == 3
    assert efetivos["entregar"] == 1


def test_variante_de_alvo_fixo_passa_intacta():
    """O caminho que todos os outros tipos usam nao muda."""
    fixos = {"pecas": 2, "lances": 4}
    assert editorial_mod.parametros_efetivos(fixos) == fixos
    assert not editorial_mod.alvo_sai_do_material(fixos)


# ═══════════════════════════════════════════════════════════════════════════
# 3. ⛔ A posicao que nao serve, e que precisa DIZER que nao serve
# ═══════════════════════════════════════════════════════════════════════════


def test_adversario_pequeno_demais_RECUSA_em_vez_de_pedir_o_impossivel():
    """⛔ `material_do_adversario <= -1` nao e cumprido por partida nenhuma.

    ⚠️ E o pior e que ele nao da erro: o gerador tentaria, nao acharia solucao, e
    o dia sairia descoberto sem uma linha apontando para a causa.
    """
    with pytest.raises(editorial_mod.MaterialInsuficiente) as erro:
        editorial_mod.parametros_efetivos({"capturar": 3}, material=(8, 2))
    assert "capturar 3" in str(erro.value)


def test_quem_entrega_precisa_sobrar_com_PELO_MENOS_uma_peca():
    """⛔ Com `resta_a_voce: 0` o desafio seria cumprido por quem PERDEU a partida.

    ⚠️ Nas damas ficar sem pecas e derrota. Um teto de zero transformaria o
    sacrificio em *"deixe-se liquidar"* — e a clausula ficaria verdadeira
    exatamente no instante em que a pessoa perde.
    """
    with pytest.raises(editorial_mod.MaterialInsuficiente):
        editorial_mod.parametros_efetivos({"entregar": 1}, material=(1, 8))


def test_falta_de_referencia_falha_ALTO():
    """⚠️ Um padrao silencioso aqui publicaria um teto que ninguem escolheu."""
    with pytest.raises(TypeError):
        editorial_mod.parametros_efetivos({"capturar": 3})
    with pytest.raises(TypeError):
        editorial_mod.parametros_efetivos({"acima_do_guloso": 2})


def test_a_conferencia_sem_posicao_resolve_os_DOIS_mecanismos():
    """⚠️ E o que permite ao teste montar uma chegada sem gerar candidato."""
    do_guloso = editorial_mod.parametros_para_conferencia({"acima_do_guloso": 2})
    assert do_guloso["caixas"] == editorial_mod.GULOSO_DE_EXEMPLO + 2

    do_material = editorial_mod.parametros_para_conferencia(
        {"capturar": 3, "entregar": 1}
    )
    assert do_material["resta_ao_adversario"] == 9   # 12 - 3
    assert do_material["resta_a_voce"] == 11         # 12 - 1


# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ DE ONDE SAEM OS NUMEROS DESTE ARQUIVO — e por que nao estao escritos aqui
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **Ate 16/09/2026 eles vinham de `tipos_propostos.PARAMETROS_DE_EXEMPLO`**, e
# com a promocao dos dois tipos aquela tabela deixou de te-los: os numeros de quem
# publica moram no EDITORIAL, que e onde estao as variantes medidas.
#
# ⚠️ **Entao este arquivo PROCURA a variante, e nao a reescreve.** Os numeros
# esperados mais abaixo (`<= 5`, `<= 7`, piso 10) sao *derivados* dela — copia-los
# para ca faria o teste continuar verde no dia em que a variante saisse do ar,
# provando uma regra que ninguem mais publica.


def _variante_publicada(co_tipo: str, **parametros) -> dict:
    """Os parametros de uma variante que esta NO AR, procurada pelos numeros.

    Raises:
        AssertionError: quando aquela variante nao esta mais no editorial — que e
            exatamente a hora de revisar os numeros esperados deste arquivo.
    """
    for publicacao in EDITORIAL[co_tipo]:
        if dict(publicacao.parametros) == parametros:
            return dict(publicacao.parametros)
    raise AssertionError(
        f"⛔ {co_tipo} nao publica mais {parametros}. As variantes no ar hoje sao "
        f"{[dict(p.parametros) for p in EDITORIAL[co_tipo]]}. ⚠️ Os numeros "
        "esperados neste arquivo derivam dela: reveja-os antes de trocar a busca."
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. ⛔ A chegada do sacrificio julga o que promete
# ═══════════════════════════════════════════════════════════════════════════


def _chegada_do_sacrificio(material: tuple[int, int]) -> LinhaDeChegada:
    """A linha de chegada do sacrificio para uma posicao de dado material."""
    efetivos = editorial_mod.parametros_efetivos(
        _variante_publicada("damas_sacrificio", capturar=3, entregar=1), material=material
    )
    return LinhaDeChegada.de_dado(RECEITAS["damas_sacrificio"].montar(efetivos))


#: Uma posicao de 8 contra 8, que e o que os moldes reais costumam ter.
MATERIAL = (8, 8)


def test_capturar_tres_SEM_entregar_nada_nao_cumpre():
    """⛔ **E o caso que separa este tipo do `damas_capturar_multipla`.**

    Capturar tres sem dar nada e o desafio que ja esta no ar desde 12/09/2026. Se
    esta conjuncao o aceitasse, o catalogo teria dois tipos com a mesma regra e
    frases diferentes — e o rodizio publicaria o "mesmo" desafio duas vezes por
    semana, com a pessoa achando que viu um bug.
    """
    medidas = {"material_do_adversario": 5, "material_restante": 8}
    assert not avaliar(_chegada_do_sacrificio(MATERIAL), medidas)


def test_entregar_uma_SEM_capturar_nada_nao_cumpre():
    """⛔ O outro lado: perder peca sozinho e so perder peca."""
    medidas = {"material_do_adversario": 8, "material_restante": 7}
    assert not avaliar(_chegada_do_sacrificio(MATERIAL), medidas)


def test_a_troca_completa_cumpre():
    """✅ Tres dele a menos, uma sua a menos: e o sacrificio."""
    medidas = {"material_do_adversario": 5, "material_restante": 7}
    assert avaliar(_chegada_do_sacrificio(MATERIAL), medidas)


def test_a_posicao_de_PARTIDA_nunca_cumpre():
    """⛔ O cadeado da familia: ninguem resolve sem jogar.

    ⚠️ Aqui ele sai de graca, e a razao e estrutural: os dois tetos sao
    **estritamente menores** que o material da propria posicao, entao a chegada e
    falsa por construcao antes do primeiro lance. E o unico tipo da familia
    *"aguente"* que nao precisou da clausula de `lances_do_jogador` (§8k-10).
    """
    medidas = {"material_do_adversario": 8, "material_restante": 8}
    assert not avaliar(_chegada_do_sacrificio(MATERIAL), medidas)


# ═══════════════════════════════════════════════════════════════════════════
# 5. ⛔ Todo tipo de damas sabe responder "isto cai no primeiro lance?"
# ═══════════════════════════════════════════════════════════════════════════


def test_todo_tipo_cacado_tem_verificador_OU_razao_declarada():
    """⛔ Tipo sem nenhum dos dois e tipo que ninguem esta conferindo.

    ⚠️ **Sao dois caminhos, e nenhum deles e o silencio:** ou o tipo tem uma
    pergunta que se faz a posicao (`CUMPRIU_O_OBJETIVO`), ou tem uma **prova
    escrita** de que nenhum lance unico o cumpre (`SEM_SOLUCAO_DE_UM_LANCE`). Um
    tipo novo que nao aparecesse em nenhum dos dois levantaria `KeyError` no meio
    de uma cacada de uma hora — e so ali.
    """
    from scripts.cacar_moldes_damas import TIPOS

    for co_tipo in TIPOS:
        assert co_tipo in CUMPRIU_O_OBJETIVO or co_tipo in SEM_SOLUCAO_DE_UM_LANCE, (
            f"⛔ {co_tipo} e cacado e nao sabe dizer se cai no primeiro lance"
        )

    # ⛔ E nunca os dois: um tipo com verificador E com razao para nao ter um
    # significaria que alguem escreveu a prova sem apagar a pergunta, e a prova
    # ganharia — silenciosamente.
    assert not set(CUMPRIU_O_OBJETIVO) & set(SEM_SOLUCAO_DE_UM_LANCE)


@pytest.mark.parametrize("co_tipo", sorted(SEM_SOLUCAO_DE_UM_LANCE))
def test_os_tipos_sem_solucao_de_um_lance_nao_gastam_busca(co_tipo: str):
    """⚠️ A resposta sai sem gerar um lance sequer — e e `None`, nao um erro."""
    assert objetivo_no_primeiro_lance(
        "W:W18,22,26,27,31:B10,11,14,15,19", co_tipo, "brasileira"
    ) is None


# ═══════════════════════════════════════════════════════════════════════════
# 6. ⛔ O PISO DO `damas_sobreviver` E RELATIVO — a regua obrigou
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **O desenho de 14/09 premiava jogar MAL, e nenhum teste de forma via isso.**
# A chegada era `lances_do_jogador >= 8` e `material_restante >= 1`, e ela e
# impecavel pelos criterios deste arquivo: valida, sem vocabulario novo, falsa na
# posicao de partida. ⛔ So a regua mostrou o defeito — a Cacau resolveu **30 de
# 30** em tres dias, enquanto o Tex e o Magno ficavam em 7 e 8 de 10.
#
# A razao e estrutural: **resistir nao e vencer**. Quem joga para vencer troca
# pecas e as vezes se liquida; quem anda ao acaso so empurra pedra, e a partida
# arrasta ate o oitavo lance sozinha.


def test_o_piso_do_sobreviver_NAO_e_uma_peca_solta():
    """⛔ `material_restante >= 1` e a forma que invertia a escada do produto.

    ⚠️ **O cadeado olha o VALOR, e nao so a chave**, porque a chave continua a
    mesma: o que mudou foi o numero passar a sair da posicao. Um `1` literal aqui
    seria a volta do desenho antigo, e ⛔ nada mais no projeto o acusaria — os
    testes de forma passam nos dois.
    """
    efetivos = editorial_mod.parametros_para_conferencia(
        _variante_publicada("damas_sobreviver", lances=8, entregar=2)
    )
    chegada = RECEITAS["damas_sobreviver"].montar(efetivos)
    material = [c for c in chegada["clausulas"] if c["chave"] == "material_restante"]
    assert len(material) == 1, "o sobreviver tem de cobrar material"
    assert material[0]["valor"] > 1, (
        "⛔ o piso de material voltou a ser absoluto. Com `>= 1` a Cacau resolve "
        "30 de 30 e o Magno 7 de 10: a escada do produto sai INVERTIDA, e nenhum "
        "teste de forma acusa. O piso sai da posicao (`resta_a_voce`)."
    )


def test_o_sobreviver_cobra_material_RELATIVO_a_posicao():
    """⚠️ Duas posicoes diferentes tem de produzir dois pisos diferentes.

    ⛔ E o que separa este tipo do desenho antigo: um piso fixo vale para um molde
    e mente em todos os outros, e o acervo vai de 10 a 22 pecas.
    """
    def piso(material: tuple[int, int]) -> int:
        efetivos = editorial_mod.parametros_efetivos(
            _variante_publicada("damas_sobreviver", lances=8, entregar=2), material=material
        )
        chegada = RECEITAS["damas_sobreviver"].montar(efetivos)
        return next(
            c["valor"] for c in chegada["clausulas"] if c["chave"] == "material_restante"
        )

    assert piso((12, 12)) == 10
    assert piso((6, 9)) == 4
    assert piso((12, 12)) != piso((6, 9))


def test_os_dois_tipos_usam_o_MESMO_mecanismo_com_o_comparador_VIRADO():
    """⚠️ Um numero relativo, dois tipos opostos - e e isso que os torna irmaos.

    ⛔ `damas_sacrificio` **exige** a perda (`<= M - entregar`); `damas_sobreviver`
    a **limita** (`>= M - entregar`). Trocar um comparador pelo outro nao daria
    erro nenhum: daria o outro tipo, com a frase errada.
    """
    # ⚠️ Uma variante no ar de cada tipo — a que o outro caso deste arquivo usa.
    PARAMETROS_NO_AR = {
        "damas_sacrificio": _variante_publicada(
            "damas_sacrificio", capturar=3, entregar=1
        ),
        "damas_sobreviver": _variante_publicada(
            "damas_sobreviver", lances=8, entregar=2
        ),
    }

    def clausula_de_material(co_tipo: str) -> dict:
        efetivos = editorial_mod.parametros_para_conferencia(
            PARAMETROS_NO_AR[co_tipo]
        )
        chegada = RECEITAS[co_tipo].montar(efetivos)
        return next(
            c for c in chegada["clausulas"] if c["chave"] == "material_restante"
        )

    assert clausula_de_material("damas_sacrificio")["comparador"] == "menor_ou_igual"
    assert clausula_de_material("damas_sobreviver")["comparador"] == "maior_ou_igual"


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ AS MEDIDAS DE SAIDA TAMBEM DEPENDEM DA POSICAO, E ISSO SO QUEBRA LA
# ═══════════════════════════════════════════════════════════════════════════


def test_as_medidas_de_saida_sao_GRAVAVEIS_em_qualquer_material_do_acervo():
    """⛔ A faixa do XP destes dois tipos sai da POSICAO, como a chegada.

    ⚠️ **E e por isso que este caso varre materiais em vez de conferir um.** No
    sacrificio a faixa de `material_do_adversario` vai de `resta_ao_adversario`
    ate `A`; no sobreviver, de 0 ate `resta_a_voce`. ⛔ `medidas_de_saida`
    recusa `vr_max <= vr_min` — dividir por zero na hora de pontuar —, e um
    material em que isso acontecesse **nao daria erro na geracao**: daria erro
    ao gravar, no meio de uma rodada de horas, ou pior, no calculo do XP de
    alguem.

    ⚠️ **A varredura vai de 5 a 12 pecas por lado**, que e a faixa dos moldes
    pescados de partidas reais (`job/tipos_de_desafio.py`). ⛔ Escrever um so
    material aqui repetiria o defeito que `parametros_efetivos` existe para
    curar: um numero que vale para um molde e mente nos outros.
    """
    from job.medidas_de_saida import conferir

    for co_tipo in ("damas_sacrificio", "damas_sobreviver"):
        for publicacao in EDITORIAL[co_tipo]:
            for meu in range(5, 13):
                for do_adversario in range(5, 13):
                    try:
                        efetivos = editorial_mod.parametros_efetivos(
                            publicacao.parametros, material=(meu, do_adversario)
                        )
                    except editorial_mod.MaterialInsuficiente:
                        # ✅ Posicao que o gerador DESCARTA — ela nunca chega as
                        # medidas de saida, e recusa-la e o comportamento certo.
                        continue

                    # ⛔ Nao basta montar: tem de passar pelo mesmo `conferir`
                    # que o job chama antes de gravar.
                    conferir(publicacao.medidas(efetivos))
