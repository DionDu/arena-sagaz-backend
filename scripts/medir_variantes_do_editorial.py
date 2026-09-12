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
    com o preparo 8 da publicacao no ar devolveria `pior 0` — um ⛔ merecido pela
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
    #     {damas:1, lances: 6}   pior 3   6.8   103s   ← no ar, e a linha de controle
    #     {damas:1, lances: 4}   pior 3   6.1   176s   ← no ar
    #     {damas:2, lances: 8}   pior 1   9.6   525s   ← no ar
    #     {damas:2, lances:10}   pior 1   9.6   532s
    #
    # ⚠️ O controle nao se moveu; `{damas:2}` caiu de `pior 3` para `pior 1`. Ver
    # `docs/historico_decisoes.md` de 12/09 para a leitura das duas hipoteses
    # (acervo mais dificil × maquina dividida com a suite do aplicativo).
    "damas_coroar": (
        Candidata({"damas": 1, "lances": 6}),
        Candidata({"damas": 1, "lances": 4}),
        # ✅ MEDIDA em 12/09: duas damas muda o objetivo, e nao a folga — e E
        # alcancavel a partir dos moldes escritos para UMA (`pior 1`). ⚠️ As duas
        # janelas dao o mesmo numero, entao so a de 8 esta publicada.
        Candidata({"damas": 2, "lances": 8}),
        Candidata({"damas": 2, "lances": 10}),
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
        #     {pecas:3, lances:4}   pior 0   ⛔ NAO ENTRA            696s
        #     {pecas:3, lances:6}   pior 1   solucao media 10.3     691s
        #
        # ⚠️ 10,3 meios-lances sao ~5,2 lances do jogador — a tarefa mais longa
        # que as damas tem, mais longa ate que o coroar de duas damas (9,6).
        # ⛔ E ela encosta no teto: 10,3 contra um `teto_de_lances` de **12**.
        Candidata({"pecas": 3, "lances": 4}),
        Candidata({"pecas": 3, "lances": 6}),
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


def medir(co_tipo: str, variantes: Sequence[Mapping[str, Any]]) -> None:
    """Mede cada variante de um tipo e imprime o resultado, linha a linha."""
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

        pior = min(por_dia)
        media_da_solucao = (
            sum(lances_da_solucao) / len(lances_da_solucao) if lances_da_solucao else 0.0
        )
        # ⚠️ O PIOR dia manda: uma variante com 3 num dia e 0 no outro publica dia
        # descoberto a cada duas aparicoes, e a media de 1,5 esconderia isso.
        selo = "✅" if pior >= 1 else "⛔"
        # ⚠️ Os botoes entram na linha **so quando diferem** da publicacao no
        # ar: repeti-los em toda linha esconderia justamente a que e diferente.
        proprios = ""
        if preparo != publicacao.nu_lances_de_preparo:
            proprios += f" preparo={preparo}"
        if teto != publicacao.nu_maximo_de_meios_lances:
            proprios += f" teto={teto}"
        print(
            f"  {selo} {str(dict(parametros)):<32} "
            f"candidatos por dia {por_dia} (pior {pior}) · "
            f"solucao media {media_da_solucao:.1f} meios-lances · "
            f"{time.time() - inicio:.0f}s{proprios}"
        )


def principal(argumentos: Sequence[str]) -> int:
    """Mede os tipos de um jogo, ou todos. Devolve o codigo de saida."""
    alvo = argumentos[0] if argumentos else "todos"

    tipos = [
        co_tipo
        for co_tipo in A_MEDIR
        if alvo == "todos" or gerador_mod.receita_de(co_tipo).co_jogo == alvo
    ]
    if not tipos:
        print(f"⛔ nada a medir para {alvo!r}. Use: pontinhos · damas · todos")
        return 2

    inicio = time.time()
    for co_tipo in tipos:
        medir(co_tipo, A_MEDIR[co_tipo])

    print()
    print(f"total: {time.time() - inicio:.0f}s")
    print()
    print("⚠️ O numero que decide e o PIOR dia. Variante com ⛔ nao entra no")
    print("   editorial — ela publicaria dia descoberto, e o log so diria")
    print("   'sem candidato', que e sintoma e nao causa.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
