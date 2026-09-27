"""A SEMENTE do desafio, e como ela vira uma semente POR LANCE (T033).

═══════════════════════════════════════════════════════════════════════════
POR QUE PUBLICAR A SEMENTE (RF-DES-206)
═══════════════════════════════════════════════════════════════════════════

Decisao do dono, 04/09/2026: o desafio carrega `nu_semente`, e **todo mundo
enfrenta exatamente o mesmo adversario**.

*Recusado:* deixar a dificuldade variar por sorte. O quadro do dia passaria a
ordenar **sorte**, e *"a Pita entregou tudo para o fulano"* e reclamacao que nao
se responde.

═══════════════════════════════════════════════════════════════════════════
⚠️ A SEMENTE E DERIVADA POR LANCE, NUNCA A MESMA REPETIDA (RF-DES-210)
═══════════════════════════════════════════════════════════════════════════

E concreto, e vem do motor das damas: a busca roda **num isolate novo a cada
lance**, e o `Buscador` e construido com a semente **daquele lance**. Passar a
mesma constante faria a CPU recomecar o mesmo fluxo de sorteios a cada jogada —
e o adversario repetiria padroes de um jeito que se percebe jogando.

    semente_do_lance(nu_semente, n) = (nu_semente + n * 2654435761) & 0x7FFFFFFF

⚠️ A funcao precisa de tres propriedades:

  1. **determinismo** — a mesma dupla da sempre o mesmo numero, em qualquer
     maquina e qualquer versao do Python;
  2. **dispersao** — lances vizinhos nao produzem sementes vizinhas, senao o
     sorteio do lance 3 fica parecido com o do lance 4;
  3. ⛔ **ser a MESMA conta do aplicativo** — ver a secao seguinte, que e a razao
     de este modulo ter sido reescrito em 26/09/2026.

═══════════════════════════════════════════════════════════════════════════
⛔ ELA E A CONTA DO APLICATIVO — E ISTO CUSTOU UM DEFEITO
═══════════════════════════════════════════════════════════════════════════

A fonte da verdade e `arena-sagaz-frontend/lib/core/jogos/semente_da_partida.dart`,
no metodo `SementeDaPartida.para(ordem)`:

    int para(int ordem) => (mestra + ordem * 2654435761) & 0x7FFFFFFF;

`2654435761` e a constante de Knuth (a razao aurea em 32 bits), o multiplicador
impar classico de espalhamento; o `& 0x7FFFFFFF` mantem o resultado no inteiro
positivo de 32 bits, que e o dominio que o `Random` do Dart aceita em toda
plataforma.

⚠️ **Ate 26/09/2026 esta funcao era um SHA-256 de `"{semente}:{lance}"`**, e o
cabecalho declarava, com todas as letras, que ⛔ *"nao precisa dar o mesmo numero
que a do Dart: o papel do job e calibrar, nao prever a partida de ninguem"*.

⛔ **Essa premissa deixou de valer, e ninguem percebeu no dia em que deixou.**
Ela foi escrita quando o servidor jogava com o **port Python**, que nao sortearia
igual ao Dart de jeito nenhum — logo igualar a semente nao compraria nada. Em
25/09/2026 o servidor passou a jogar com **o motor do aparelho**
(`motores/damas/jogador_dart.py`), e dali em diante o sorteador dos dois lados e
o mesmo `Random` do Dart. Sobrou **uma unica** peca fora do lugar: o numero
entregue a ele. Duas contas diferentes, o mesmo sorteador, adversarios
diferentes.

E o `js_solucao` nao e mais so calibracao: ele e a **"Solucao oficial"** que o
Raio-X mostra na tela, lance a lance, ao lado da resolucao da pessoa.

**Como o defeito aparecia** (relato do dono, 26/09/2026, desafio
`449864e6-095f-498a-afdc-f2c0f51c277e`, *damas_sobreviver* anglo contra a
**Pita**, semente publicada `697571591`):

| ordem | o aplicativo derivava | o job derivava |
|---|---|---|
| 1 | 1204523704 | 1960240702 |
| 2 | **1711475817** | **2857670330** |

O lance 1 e de quem resolve, entao batia. O lance **2** e o primeiro da CPU — e
divergia, ja no primeiro lance dela.

⚠️ **E so aparecia nos niveis que erram de proposito.** O Sagaz tem `ruido=0` e
`chance_de_errar=0,0`: ele nao consulta o sorteador, e por isso o desafio contra
o Magno se reproduzia mesmo com a semente errada. Cacau (`ruido=90`,
`errar=0,35`), Pita (`ruido=40`, `errar=0,25`) e Tex (`errar=0,08`) consultam — o
Tex raramente, que e o pior caso, porque diverge de forma **intermitente**.

⛔ **E por isso o vetor de paridade de 25/09 passou sem tocar no defeito:** ele e
a partida do dono contra o **Magno**, o unico adversario a quem a semente nao
muda nada.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CADEADO: o bloco `sementes` dos vetores de verificacao
═══════════════════════════════════════════════════════════════════════════

Igualdade que so existe em comentario volta a divergir.
`contratos/vetores-verificacao-desafio.json` ganhou um bloco `sementes`, com
pares `(semente, lance) -> esperado`, e ele e lido pelos **dois** lados:

    tests/unitarios/test_gabarito_e_semente.py     (Python, este modulo)
    test/core/jogos/semente_da_partida_test.dart   (Dart, o aplicativo)

⚠️ O arquivo e o mesmo nos dois repositorios, com SHA-256 conferido — mudar a
conta de um lado so passa a **quebrar a suite do outro**.
"""

from __future__ import annotations

import hashlib

#: A faixa de `nu_semente`: 32 bits **sem o zero**.
#:
#: ⚠️ E o que qualquer gerador aceita, e travar a faixa evita depender do que
#: cada linguagem faz com semente negativa — em Dart, `Random(-1)` nao e erro,
#: mas tambem nao e o que quem escreveu esperava.
SEMENTE_MINIMA = 1
SEMENTE_MAXIMA = 4_294_967_295

#: A constante de Knuth — a razao aurea em 32 bits.
#:
#: ⛔ **Nao e um numero escolhido aqui.** Ele e copia do que esta em
#: `SementeDaPartida.para`, no aplicativo, e os dois tem de continuar iguais; ver
#: o cabecalho deste modulo.
CONSTANTE_DE_KNUTH = 2_654_435_761

#: O dominio do `Random` do Dart: o inteiro positivo de 32 bits.
#:
#: ⚠️ **O zero cabe aqui, e de proposito** — `Random(0)` e valido nas duas
#: linguagens. E por isso que a semente **do lance** nao passa por `validar()`,
#: que exige `>= 1`: aquela faixa e a da semente **publicada**, a que vai para a
#: coluna `nu_semente` e tem um `CHECK` no banco.
MASCARA_DO_RANDOM = 0x7FFF_FFFF


class SementeInvalida(ValueError):
    """A semente esta fora da faixa de 32 bits sem zero."""


def validar(nu_semente: int) -> int:
    """Confere a faixa e devolve a semente. Falha alto fora dela.

    ⚠️ O `CHECK` da migracao `0018` diz a mesma coisa. Ter as duas nao e
    redundancia: o `CHECK` guarda o banco de qualquer origem, e esta funcao
    guarda o job — e o erro dela aponta para quem gerou o numero, nao para um
    `INSERT` que falhou tres camadas abaixo.
    """
    if not isinstance(nu_semente, int) or isinstance(nu_semente, bool):
        raise SementeInvalida(f"a semente precisa ser inteira; veio {nu_semente!r}")
    if not SEMENTE_MINIMA <= nu_semente <= SEMENTE_MAXIMA:
        raise SementeInvalida(
            f"semente {nu_semente} fora da faixa "
            f"[{SEMENTE_MINIMA}, {SEMENTE_MAXIMA}]"
        )
    return nu_semente


def sortear(*, id_desafio: str) -> int:
    """A semente de um desafio, derivada do identificador dele.

    ⚠️ **Derivada, e nao sorteada de verdade**, e isso e decisao: assim a
    calibracao e **reproduzivel** (RF-DES-208). Rodar a regua de novo meses
    depois da os mesmos numeros, e um desafio contestado pode ser reauditado —
    o que um `random.randint()` tornaria impossivel.

    ⚠️ E ela nao precisa ser imprevisivel. Nao ha nada a proteger: a semente e
    **publicada** no desafio, de propósito.

    ⚠️ **Esta conta continua sendo um SHA-256, e pode continuar:** ela nao tem
    par do outro lado. Quem nasce aqui e a semente da PARTIDA, e o aplicativo a
    recebe pronta, publicada no desafio. Quem precisa ser identica nos dois lados
    e a derivacao **por lance**, logo abaixo.
    """
    digerido = hashlib.sha256(id_desafio.encode("utf-8")).digest()
    # Os quatro primeiros bytes viram um inteiro de 32 bits; o `% MAXIMA + 1`
    # tira o zero da faixa sem introduzir vies perceptivel (a faixa tem 2^32-1
    # valores e o resto vem de 2^32 — um valor a mais em 4 bilhoes).
    bruto = int.from_bytes(digerido[:4], "big")
    return (bruto % SEMENTE_MAXIMA) + 1


def semente_do_lance(nu_semente: int, nu_lance: int) -> int:
    """A semente que o motor recebe **naquele** lance (RF-DES-210).

    Args:
        nu_semente: a semente publicada no desafio — a "mestra", no vocabulario
            do aplicativo.
        nu_lance: o numero do lance, contado de 1. ⚠️ E o mesmo numero que o
            aplicativo usa (`estado.lancesJogados + 1`): os dois contam a partir
            da **posicao publicada**, e nao do inicio de uma partida cheia.

    Returns:
        Um inteiro em `[0, 2^31 - 1]` — o dominio do `Random` do Dart.

    ⛔ **Esta conta e copia da do aplicativo**, e mudar uma sem a outra quebra o
    gabarito de todo desafio contra Cacau, Pita ou Tex. O cadeado que impede
    isso, e a historia do defeito que custou a descoberta, estao no cabecalho
    deste modulo.

    ⚠️ **Por que multiplicar, e nao somar.** `nu_semente + nu_lance` daria
    sementes vizinhas para lances vizinhos, e geradores lineares (o `Random` do
    Dart e um deles) produzem primeiros valores parecidos a partir de sementes
    parecidas — o adversario ficaria repetitivo de um jeito que se percebe
    jogando, e nenhum teste de igualdade acusaria.
    """
    validar(nu_semente)
    if nu_lance < 1:
        raise SementeInvalida(f"nu_lance comeca em 1; veio {nu_lance}")

    return (nu_semente + nu_lance * CONSTANTE_DE_KNUTH) & MASCARA_DO_RANDOM
