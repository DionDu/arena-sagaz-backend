"""T049f - mede se uma VARIANTE DE PARAMETROS gera desafio antes de publica-la.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

⚠️ **Prioridade do dono, 10/09/2026:** *"e muito importante que estes parametros
variem, senao os desafios viram pura repeticao"*. Hoje o `EDITORIAL` tem **um**
dicionario por tipo: todo `chegar_ao_placar` e "7 caixas", todo `coroar` e "1
dama em 6 lances". A posicao varia; a **tarefa**, nao.

⛔ **E nenhuma variante entra sem ser medida.** A licao esta escrita no proprio
editorial, e custou quatro dias descobertos na primeira execucao real:

    pontinhos_fechar_caixas    → 0 candidatos com preparo 8;  1 com preparo 14
    pontinhos_chegar_ao_placar → 0 candidatos com teto 12;    1 com teto 34

Nada disso aparece antes de a variante virar **dia descoberto**, duas semanas
depois de entrar — e ai o log diz "sem candidato", que e sintoma e nao causa.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\medir_variantes_do_editorial.py pontinhos
    .venv\\Scripts\\python -u scripts\\medir_variantes_do_editorial.py damas
    .venv\\Scripts\\python -u scripts\\medir_variantes_do_editorial.py damas_capturar_multipla

⚠️ **O alvo pode ser um JOGO, `todos`, ou UM TIPO** (a terceira linha). O tipo
existe porque a rodada `damas` inteira custa **80 minutos** (medido em
12/09/2026): investigar um botao de um tipo nao deve pagar a medicao dos outros.

⚠️ **E `--com-botao-proprio` mede so as candidatas que mexem em PREPARO ou
TETO** - as que estao sob investigacao:

    .venv\Scripts\python -u scripts\medir_variantes_do_editorial.py damas --com-botao-proprio

⛔ **Ele dispensa a REIMPRESSAO, nunca a primeira medida.** Uma variante nova sem
botao proprio continua precisando da rodada cheia; o que este atalho evita e
pagar ~55 minutos para reimprimir linhas que ja sairam identicas duas vezes.

⚠️ **E a medicao e REPRODUTIVEL, o que da peso ao numero.** As damas foram
medidas duas vezes em 12/09/2026, com ~2 h entre as rodadas: **sete das nove**
linhas sairam identicas digito a digito, e as duas que variaram (`{damas: 2}`)
mudaram de `[1, 3, 3]` para `[1, 2, 3]` sem trocar de rotulo. ⛔ O que varia e a
**regua** (3 mascotes x 20 execucoes, com sorteio); as **posicoes** nao variam,
porque a semente sai do dia.

⚠️ **O Pontinhos leva segundos; as damas, minutos.** Uma geracao de damas custa
~26 s (medido em 11/09/2026), e a medicao roda cada variante em varios dias
diferentes — sao posicoes de partida diferentes, e uma variante que so funciona
num molde nao serve para a fila.

⚠️ **Rode com `-u`**: sem ele o Python bufferiza o `stdout` redirecionado e o
arquivo de saida fica vazio ate o fim.

═══════════════════════════════════════════════════════════════════════════
COMO LER O RESULTADO
═══════════════════════════════════════════════════════════════════════════

Uma linha por variante, com quantos candidatos sairam em cada dia medido e o
tamanho medio da solucao. ⚠️ **O numero que decide e o PIOR dia, e nao a media:**
uma variante que gera 3 candidatos num dia e 0 no outro publica um dia descoberto
a cada duas aparicoes, e a media de 1,5 esconderia isso.

⛔ Este script **nao escreve no editorial**. Quem decide o que entra e quem le o
numero — e a decisao fica registrada em `docs/historico_decisoes.md`.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

# ⚠️ Um script em `scripts/` nao e pacote: sem isto, `from job import ...` falha.
# `parents[1]` sobe de `scripts/este_arquivo.py` para a raiz do backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ⛔ **O console do Windows fala cp1252, e este arquivo fala UTF-8.** Sem estas
# duas linhas, o primeiro `═` do cabecalho derruba a medicao inteira com
# `UnicodeEncodeError` — depois de minutos de geracao de damas, e por causa de um
# enfeite. `errors="replace"` e a rede: um caractere que o terminal nao saiba
# desenhar vira `?`, e nao uma excecao.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job import editorial as editorial_mod  # noqa: E402
from job import gerador as gerador_mod  # noqa: E402

#: Quantos candidatos pedir por dia — o mesmo do job (`CANDIDATOS_POR_DIA`).
#:
#: ⚠️ **Medir com um numero diferente do job daria uma taxa que descreve outra
#: execucao.** E a mesma razao pela qual a regua usa o teto de lances da geracao.
QUANTOS_POR_DIA = 3

#: Em quantos dias diferentes cada variante e medida.
#:
#: ⚠️ **Dias diferentes sao POSICOES DE PARTIDA diferentes** (a semente sai do
#: dia), e e disso que se precisa: uma variante que so funciona a partir de um
#: molde especifico geraria bem hoje e nada no mes que vem.
DIAS_MEDIDOS = 3

#: O primeiro dia da medicao. Qualquer um serve; fixo para a medicao ser
#: repetivel.
DIA_BASE = date(2026, 10, 1)

@dataclass(frozen=True, slots=True)
class Candidata:
    """Uma variante a medir, com os botoes de geracao que ela precisa.

    Atributos:
        parametros: os numeros que a receita consome (`{"caixas": 7}`).
        nu_lances_de_preparo: quantos lances a posicao de partida ja traz. `None`
            herda o da publicacao no ar.
        nu_maximo_de_meios_lances: o teto de meios-lances do gabarito. `None` herda.

    ⛔ **Os dois botoes precisam ser POR CANDIDATA, e descobrir isso custou uma
    execucao.** Ate 12/09/2026 eles saiam sempre da publicacao no ar, o que estava
    certo enquanto toda candidata era a mesma tarefa com outro numero. Deixou de
    estar no dia em que `acima_do_guloso` apareceu: ele exige **preparo 14** (com
    8 tracos nao ha cadeia formada, e nao ha double dealing sem cadeia), e medi-lo
    com o preparo 8 da publicacao no ar devolveria **0 de 3 no dia mais fraco** — um ⛔ merecido pela
    medicao errada, e nao pela variante.
    """

    parametros: Mapping[str, Any]
    nu_lances_de_preparo: int | None = None
    nu_maximo_de_meios_lances: int | None = None


#: As variantes a medir, por tipo. ⚠️ **A primeira de cada lista e a que esta no
#: ar hoje** — ela entra na medicao de proposito, como linha de comparacao: sem
#: ela nao ha como saber se um numero baixo e da variante ou do tipo.
A_MEDIR: dict[str, tuple[Candidata, ...]] = {
    "pontinhos_cadeia_longa": (
        # ⚠️ Preparo 4: cadeia longa se CONSTROI, e com o tabuleiro cheio nao ha
        # o que moldar. E o unico tipo de Pontinhos que nao usa 14.
        Candidata({"caixas": 6}),
        Candidata({"caixas": 5}),
        Candidata({"caixas": 7}),
    ),
    "pontinhos_fechar_caixas": (
        Candidata({"caixas": 4, "turnos": 2}),
        Candidata({"caixas": 3, "turnos": 2}),
        Candidata({"caixas": 5, "turnos": 2}),
        Candidata({"caixas": 4, "turnos": 3}),
        # ⚠️ Tambem esta no ar e faltava aqui, como a `{caixas: 5}` do outro tipo.
        Candidata({"caixas": 5, "turnos": 3}),
        Candidata({"caixas": 6, "turnos": 3}),
    ),
    "pontinhos_chegar_ao_placar": (
        Candidata({"caixas": 7}),
        Candidata({"caixas": 6}),
        # ⚠️ **Tambem esta no ar** (entrou em 11/09) e faltava aqui — uma variante
        # publicada fora da lista deixa de ser remedida quando o gerador muda, que
        # e exatamente quando o numero dela pode ter mudado.
        Candidata({"caixas": 5}),
        Candidata({"caixas": 8}),
        Candidata({"caixas": 9}),
        # ── A variante em que o ALVO SAI DA POSICAO, e nao daqui (11/09/2026) ──
        #
        # O editorial publica *"supere o guloso em N"*; o gerador calcula quantas
        # caixas um jogador que nunca recusa uma caixa faria naquela posicao, soma
        # N, e e esse numero absoluto que vai na frase. ⚠️ **Quem so captura nao
        # resolve** — a solucao ingenua fica excluida por construcao, e nao por
        # alguem ter julgado que era facil demais.
        #
        # ⛔ **Preparo 14, e nao o 8 da publicacao no ar.** Com 8 tracos o
        # tabuleiro e comeco de jogo, sem cadeia formada — e sem cadeia nao ha
        # double dealing a cobrar. Medido em 60 posicoes reais do `prd` com 14
        # tracos: 27% delas rendem `D > G`, com diferencas de +1 a +5.
        Candidata({"acima_do_guloso": 1}, nu_lances_de_preparo=14),
        Candidata({"acima_do_guloso": 2}, nu_lances_de_preparo=14),
    ),
    # ⚠️ **O QUE A RODADA DE 11/09/2026 ENSINOU, e vale para escrever candidata
    # nova:** `lances` e a janela em **lances do jogador**, e a solucao media que
    # este script imprime conta **meios-lances** (a fita do gabarito inclui o
    # adversario). Coroar cai em ~6,8 meios-lances = ~3,4 lances do jogador, entao
    # ⛔ **toda janela de 6 para cima e folga pura**: 6, 8 e 10 sairam identicas,
    # inclusive no tempo de geracao, porque o gerador nao descarta nada por causa
    # delas. So a de 4 apertou (210s contra 117s, solucao caindo para 4,3).
    #
    # ⛔ **Candidata que so afrouxa a janela nao e variante** — e a mesma tarefa
    # com outro numero na frase, que e a "pura repeticao" que T049f existe para
    # acabar. As de baixo mexem no que **muda a tarefa**.
    # ⚠️ **E o ACERVO MUDOU em 12/09**: 185 moldes reais entraram, e o do coroar
    # foi de 330 para 515, agora com solucoes de ate 11 lances. ⛔ Os numeros
    # acima, medidos em 11/09, descrevem o acervo ANTERIOR — medicao nao e selo
    # vitalicio.
    #
    # ✅ **REMEDIDO em 12/09**, com o acervo novo (77 min a rodada inteira):
    #
    #     {damas:1, lances: 6}   FOLGA       (3 de 3)     6.8   103s   ← no ar, e a linha de controle
    #     {damas:1, lances: 4}   FOLGA       (3 de 3)     6.1   176s   ← no ar
    #     {damas:2, lances: 8}   NO LIMITE   (1 de 3)     9.6   525s   ← no ar
    #     {damas:2, lances:10}   NO LIMITE   (1 de 3)     9.6   532s
    #
    # ⚠️ O controle nao se moveu; `{damas:2}` caiu de **3 de 3 no dia mais fraco** para **1 de 3 no dia mais fraco**.
    #
    # ✅ **E a SEGUNDA RODADA, ~2 h depois, desempatou as duas hipoteses:**
    #
    #     {damas:1, lances: 6}   FOLGA       (3 de 3)     6.8   103s   identica
    #     {damas:1, lances: 4}   FOLGA       (3 de 3)     6.1   177s   identica
    #     {damas:2, lances: 8}   NO LIMITE   (1 de 3)     9.3   636s   [1,3,3] → [1,2,3]
    #     {damas:2, lances:10}   NO LIMITE   (1 de 3)     9.3   636s   [1,3,3] → [1,2,3]
    #
    # ⛔ **Nao era a maquina dividida: e o acervo.** O rotulo nao mudou em
    # nenhuma das quatro, e as duas de uma dama sairam identicas ao digito. ⚠️ A
    # rodada "livre" foi ate **mais lenta** (636s contra 525s), o que derruba de
    # vez a hipotese do relogio.
    #
    # ⚠️ **O que varia entre rodadas e a REGUA, e nao a posicao.** As posicoes
    # saem da semente do dia e sao as mesmas sempre; a banda de dificuldade e
    # medida com 3 mascotes x 20 execucoes sorteadas, e e dai que vem a diferenca
    # de um candidato num dia.
    "damas_coroar": (
        Candidata({"damas": 1, "lances": 6}),
        Candidata({"damas": 1, "lances": 4}),
        # ✅ MEDIDA em 12/09: duas damas muda o objetivo, e nao a folga — e E
        # alcancavel a partir dos moldes escritos para UMA (**1 de 3 no dia mais fraco**). ⚠️ As duas
        # janelas dao o mesmo numero, entao so a de 8 esta publicada.
        Candidata({"damas": 2, "lances": 8}),
        Candidata({"damas": 2, "lances": 10}),
        # ⚠️ **Duas damas tambem estao coladas no teto**: 9,3 meios-lances contra
        # um teto de 12. Pela mesma leitura de `damas_capturar_multipla`, e o
        # teto — e nao a janela — que decide quantos candidatos sobram, e esta
        # linha diz se e ele que segura `{damas: 2}` em 1 de 3.
        #
        # ⛔ **A janela e a MESMA que esta no ar (8), de proposito.** Subir as
        # duas de uma vez daria uma linha melhor sem dizer qual dos dois botoes a
        # melhorou. Aqui o unico que se move e o teto.
        Candidata({"damas": 2, "lances": 8}, nu_maximo_de_meios_lances=16),
    ),
    "damas_capturar_multipla": (
        Candidata({"pecas": 2, "lances": 4}),
        # ✅ MEDIDA em 12/09, e a resposta MUDOU com o acervo real: `lances: 2`
        # agora aperta de verdade (3,0 contra 3,7, com 70 s a mais de geracao).
        # Nos 9 moldes sinteticos as tres janelas eram indistinguiveis.
        Candidata({"pecas": 2, "lances": 2}),
        Candidata({"pecas": 2, "lances": 3}),
        # ── ⚠️ `pecas: 3` VOLTOU A MESA em 12/09/2026 ────────────────────────
        #
        # Ate hoje este comentario dizia que tres em sequencia *"contra um Sagaz
        # quase nao acontece — 185 de 295 candidatas nem as duas conseguiram"*.
        # ⛔ **Esse numero e da T049g, e foi medido no acervo SINTETICO** — o
        # mesmo cuja premissa caiu nesta manha: as candidatas nasciam de
        # tabuleiros quase vazios (material ~7), onde nao ha pecas para uma
        # cadeia de tres existir. O acervo de hoje tem material **17,3**.
        #
        # ⚠️ A pergunta e do dono: *"o capture 2 pecas num so lance, este 2 e
        # fixo ou varia?"*. Hoje e fixo, e e uma variante so. Estas duas linhas
        # respondem se pode deixar de ser.
        #
        # ✅ **RESPONDIDO no mesmo dia: varia, e a JANELA decide.**
        #
        #     {pecas:3, lances:4}   SEM DESAFIO (0 de 3)     ⛔ NAO ENTRA            696s
        #     {pecas:3, lances:6}   NO LIMITE   (1 de 3)     solucao media 10.3     691s
        #
        # ⚠️ 10,3 meios-lances sao ~5,2 lances do jogador — a tarefa mais longa
        # que as damas tem, mais longa ate que o coroar de duas damas (9,6).
        # ⛔ E ela encosta no teto: 10,3 contra um `teto_de_lances` de **12**.
        Candidata({"pecas": 3, "lances": 4}),
        Candidata({"pecas": 3, "lances": 6}),
        # ── ⛔ E A SEGUNDA RODADA DISSE ONDE ESTA O APERTO: NO TETO ──────────
        #
        # ✅ **Medida de novo em 12/09/2026, com ~2 h de intervalo**, e as cinco
        # linhas deste tipo sairam **identicas digito a digito** — inclusive o
        # `0 de 3` da janela de 4 e o `10.3` da janela de 6. ⛔ Isso encerra a
        # duvida da "maquina dividida": a leitura e do acervo, e nao do relogio.
        #
        # ⚠️ **E o log mostra POR QUE `{pecas: 3}` fica em 1 de 3.** Das 18
        # posicoes tentadas por dia, so **tres** aparecem descartadas por
        # "objetivo no lance 1". As outras ~14 morrem em `_resolver`, que e o
        # Sagaz **nao achando a captura de tres dentro do teto de 12
        # meios-lances** — e as que passam vem com solucao media **10,3**,
        # colada no teto.
        #
        # ⛔ **Entao subir a janela sozinha nao traz candidato de volta**, e a
        # janela de 4 contra a de 6 ja provou isso na direcao contraria: 0 de 3
        # contra 1 de 3, mesma posicao, mesmo acervo.
        #
        # ✅ **O dono autorizou subir o teto por qualidade** (12/09/2026, §8k-5
        # de `DECISOES-do-dono.md`): *"se precisarmos subir o teto de lances para
        # comportar desafios mais interessantes e de maior qualidade, eu nao vejo
        # problema algum"*. ⚠️ **Janela e teto sobem JUNTOS** — a janela e o que a
        # pessoa le, o teto e o que o gerador procura, e subir so um deixa o
        # gerador achando solucao que a frase nao aceita.
        #
        # ⏳ **Estas quatro linhas respondem se o teto e mesmo o que aperta.**
        # Se `{pecas:3, lances:8, teto:16}` subir para FOLGA, esta e a melhor
        # variante que as damas tem: a mais longa (10,3 contra 3,0 a 9,6 de todas
        # as outras) e a unica que ampliaria o tipo, que hoje e uma so.
        Candidata({"pecas": 3, "lances": 8}, nu_maximo_de_meios_lances=16),
        Candidata({"pecas": 3, "lances": 10}, nu_maximo_de_meios_lances=20),
        # ⚠️ **O controle**: a variante de DUAS pecas com o mesmo teto maior. Sem
        # ela, uma melhora em `{pecas: 3}` poderia ser do teto beneficiando tudo,
        # e nao da tarefa de tres pecas passando a caber.
        Candidata({"pecas": 2, "lances": 8}, nu_maximo_de_meios_lances=16),
    ),
}


def _dias_do_jogo(co_jogo: str, quantos: int) -> list[date]:
    """Os primeiros `quantos` dias em que aquele jogo e o jogo do rodizio.

    ⚠️ **Nao adianta medir num dia do outro jogo:** `gerar_candidatos` decide o
    jogo pela data, e pedir damas num dia de Pontinhos geraria Pontinhos com os
    parametros das damas — sem erro, e com um numero que nao quer dizer nada.
    """
    dias: list[date] = []
    passo = 0
    while len(dias) < quantos:
        dia = DIA_BASE + timedelta(days=passo)
        if gerador_mod.escolher_jogo(dia) == co_jogo:
            dias.append(dia)
        passo += 1
    return dias


def _como_ler(dia_mais_fraco: int) -> tuple[str, str]:
    """Traduz o numero do dia mais fraco em algo que se le sem decorar.

    ⚠️ **A pedido do dono, 12/09/2026:** *"consegue mudar essas expressoes 'pior
    1', '3 de 3 no dia mais fraco'? Isso e confuso demais. Tem hora que eu acho que entendi, mas
    depois de um tempo nao lembro mais o que isso significa"*.

    ⛔ E ele tem razao: **3 de 3 no dia mais fraco** era **bom** e **1 de 3 no dia mais fraco** era **ruim**, o oposto do
    que a palavra "pior" sugere a quem le de passagem. O numero sozinho tambem
    nao dizia de quantos era — 1 de 3 e 1 de 10 sao situacoes diferentes.

    O que cada faixa quer dizer, em termos do que acontece na fila:

      FOLGA       sobra candidato, e o job escolhe o mais bem calibrado
      APERTADO    ja publica, com menos escolha
      NO LIMITE   publica o unico que houver, calibrado ou nao
      SEM DESAFIO a fila fica com um dia vazio — e a pessoa ve isso na tela
    """
    if dia_mais_fraco <= 0:
        return "⛔", "SEM DESAFIO"
    if dia_mais_fraco == 1:
        return "⚠️", "NO LIMITE"
    if dia_mais_fraco < QUANTOS_POR_DIA:
        return "⚠️", "APERTADO"
    return "✅", "FOLGA"


def so_as_de_botao_proprio(candidatas: Sequence["Candidata"]) -> list["Candidata"]:
    """As candidatas que mexem num BOTAO DE GERACAO, e nao so num numero da frase.

    ⚠️ **Botao de geracao** e `nu_lances_de_preparo` ou `nu_maximo_de_meios_lances`:
    os dois que mudam **o que o gerador procura**. Os `parametros` mudam o que a
    **frase pede**, e toda candidata tem os seus.

    ⛔ **Este filtro existe por aritmetica de relogio.** Medir
    `damas_capturar_multipla` inteiro custa ~100 minutos, e cinco das oito linhas
    ja foram medidas DUAS vezes com resultado identico ao digito (12/09/2026).
    Reimprimi-las cobra ~55 minutos por nada.

    ⚠️ **E o filtro NAO serve para publicar.** Uma variante sem botao proprio que
    nunca foi medida continua precisando da rodada cheia - o que este atalho
    dispensa e a **reimpressao**, nunca a primeira medida.
    """
    return [
        c
        for c in candidatas
        if c.nu_lances_de_preparo is not None or c.nu_maximo_de_meios_lances is not None
    ]


def medir(co_tipo: str, variantes: Sequence["Candidata"]) -> None:
    """Mede cada variante de um tipo e imprime o resultado, linha a linha."""
    if not variantes:
        return
    receita = gerador_mod.receita_de(co_tipo)
    # ⚠️ Os dois botoes da geracao (preparo e teto) saem da variante **que esta
    # no ar hoje**, e nao de numeros escritos aqui: medir com outros botoes
    # daria uma taxa que descreve uma execucao que nao existe.
    publicacao = editorial_mod.publicacao_de(co_tipo, 0)
    dias = _dias_do_jogo(receita.co_jogo, DIAS_MEDIDOS)

    print()
    print("═" * 75)
    print(f"{co_tipo}  ({receita.co_jogo})")
    print(
        f"  preparo={publicacao.nu_lances_de_preparo}  "
        f"teto_de_lances={publicacao.nu_maximo_de_meios_lances}  "
        f"(padrao do tipo; candidata com botao proprio aparece na linha dela)  "
        f"dias={[d.isoformat() for d in dias]}"
    )
    print("═" * 75)

    for candidata in variantes:
        parametros = candidata.parametros
        # ⚠️ `None` herda o botao da publicacao no ar — que e o certo para toda
        # candidata que so troca um numero da mesma tarefa.
        preparo = candidata.nu_lances_de_preparo or publicacao.nu_lances_de_preparo
        teto = candidata.nu_maximo_de_meios_lances or publicacao.nu_maximo_de_meios_lances
        # ⛔ **O tipo do dia tem de ser ESTE tipo.** `gerar_candidatos` reescolhe
        # o tipo pela data, e num dia em que ele escolher o outro tipo do jogo a
        # medicao estaria medindo o vizinho — com os parametros errados, e sem
        # erro nenhum. `tipos_recentes` e o unico botao que forca a escolha:
        # marcar os OUTROS como recentes deixa so este "fresco".
        outros = [t for t in gerador_mod.tipos_do_jogo(receita.co_jogo) if t != co_tipo]

        por_dia: list[int] = []
        lances_da_solucao: list[int] = []
        inicio = time.time()
        for dia in dias:
            candidatos = gerador_mod.gerar_candidatos(
                dia,
                parametros=parametros,
                quantos=QUANTOS_POR_DIA,
                tipos_recentes=outros,
                maximo_de_meios_lances=teto,
                lances_de_preparo=preparo,
                # ⚠️ A mesma restricao da publicacao no ar: medir contra um
                # adversario que o tipo nao publica descreveria outra execucao.
                personagens_possiveis=publicacao.co_personagens,
            )
            por_dia.append(len(candidatos))
            lances_da_solucao.extend(c.nu_lances_solucao for c in candidatos)

        dia_mais_fraco = min(por_dia)
        media_da_solucao = (
            sum(lances_da_solucao) / len(lances_da_solucao) if lances_da_solucao else 0.0
        )
        # ⚠️ **O DIA MAIS FRACO manda, e nao a media.** Uma variante com 3 num dia
        # e 0 no outro publica dia descoberto a cada duas aparicoes, e a media de
        # 1,5 esconderia isso.
        selo, rotulo = _como_ler(dia_mais_fraco)
        # ⚠️ Os botoes entram na linha **so quando diferem** da publicacao no
        # ar: repeti-los em toda linha esconderia justamente a que e diferente.
        proprios = ""
        if preparo != publicacao.nu_lances_de_preparo:
            proprios += f" preparo={preparo}"
        if teto != publicacao.nu_maximo_de_meios_lances:
            proprios += f" teto={teto}"
        print(
            f"  {selo} {rotulo:<12} {str(dict(parametros)):<32} "
            f"no dia mais fraco: {dia_mais_fraco} de {QUANTOS_POR_DIA} · "
            f"dias {por_dia} · "
            f"solucao {media_da_solucao:.1f} meios-lances · "
            f"{time.time() - inicio:.0f}s{proprios}"
        )


def tipos_do_alvo(alvo: str) -> list[str]:
    """Quais tipos de `A_MEDIR` o argumento da linha de comando seleciona.

    ⚠️ **O alvo aceita TRES granularidades**, e a do meio foi acrescentada em
    12/09/2026 por um motivo medido: a rodada `damas` inteira custa **80
    minutos**, e uma investigacao que so mexe num botao de `capturar_multipla`
    pagava os 80 para reimprimir cinco linhas ja decididas.

    ⛔ E o desperdicio nao e so de relogio: enquanto a medicao roda, a maquina
    fica ocupada, e foi exatamente a **maquina dividida** que pos em duvida a
    leitura de `{damas: 2}` na primeira rodada (ver o comentario de `A_MEDIR`).

    ⚠️ **Esta funcao existe separada de `principal` para poder ser testada.**
    Testar a selecao de dentro de `principal` obrigaria a **rodar a medicao**, que
    leva minutos — e um cadeado que ninguem aguenta rodar nao e cadeado.

      `todos`                    → todos os tipos
      `damas`                    → os tipos daquele JOGO
      `damas_capturar_multipla`  → so aquele tipo
      qualquer outra coisa       → lista vazia (quem chama avisa e sai com 2)
    """
    return [
        co_tipo
        for co_tipo in A_MEDIR
        if alvo == "todos"
        or alvo == co_tipo
        or gerador_mod.receita_de(co_tipo).co_jogo == alvo
    ]


BANDEIRA_BOTAO_PROPRIO = "--com-botao-proprio"


def principal(argumentos: Sequence[str]) -> int:
    """Mede os tipos de um jogo, de um tipo so, ou todos. Devolve o codigo de saida."""
    so_botao_proprio = BANDEIRA_BOTAO_PROPRIO in argumentos
    posicionais = [a for a in argumentos if not a.startswith("-")]
    alvo = posicionais[0] if posicionais else "todos"

    tipos = tipos_do_alvo(alvo)
    if not tipos:
        print(f"⛔ nada a medir para {alvo!r}.")
        print("   Use um JOGO (pontinhos · damas), `todos`, ou um TIPO:")
        for co_tipo in A_MEDIR:
            print(f"     {co_tipo}")
        return 2

    if so_botao_proprio:
        print(
            f"⚠️ {BANDEIRA_BOTAO_PROPRIO}: medindo so as candidatas que mexem num "
            "botao de geracao (preparo ou teto). As demais ficam de fora."
        )

    inicio = time.time()
    medidas = 0
    for co_tipo in tipos:
        candidatas = A_MEDIR[co_tipo]
        if so_botao_proprio:
            candidatas = tuple(so_as_de_botao_proprio(candidatas))
        medidas += len(candidatas)
        medir(co_tipo, candidatas)

    # ⛔ Zero linhas com a bandeira ligada nao e "tudo certo": e a bandeira
    # aplicada a um alvo que nao tem nenhuma candidata de botao proprio, e sem
    # este aviso o relatorio sairia vazio e silencioso.
    if not medidas:
        print()
        print(
            f"⛔ nenhuma candidata de {alvo!r} mexe num botao de geracao. "
            f"Rode sem {BANDEIRA_BOTAO_PROPRIO}."
        )
        return 2

    print()
    print(f"total: {time.time() - inicio:.0f}s")
    print()
    print("COMO LER ESTE RELATORIO")
    print("  O job pede 3 candidatos por dia e publica UM: o primeiro que cai na")
    print("  banda de dificuldade. O numero que decide e o do DIA MAIS FRACO —")
    print("  nao a media, que esconderia um dia zerado atras de dois bons.")
    print()
    print("  ✅ FOLGA         3 de 3  sobra candidato; o job escolhe o mais bem calibrado")
    print("  ⚠️ APERTADO      2 de 3  ja publica, com menos escolha")
    print("  ⚠️ NO LIMITE     1 de 3  publica o unico que houver, calibrado ou nao")
    print("  ⛔ SEM DESAFIO   0 de 3  a fila fica com um dia vazio, e a pessoa ve na tela")
    print()
    print("  ⚠️ E A AMOSTRA E DE 3 DIAS, NAO DO ANO. Em 2026-09-18 uma variante")
    print("     medida NO LIMITE deu ZERO na execucao real: 18 posicoes tentadas,")
    print("     18 recusadas, e a fila ficou com um dia descoberto.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
