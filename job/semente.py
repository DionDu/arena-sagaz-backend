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

    semente_do_lance(nu_semente, n) = f(nu_semente, n)

⚠️ A funcao precisa de duas propriedades, e nenhuma delas e "ser criptografica":

  1. **determinismo** — a mesma dupla da sempre o mesmo numero, em qualquer
     maquina e qualquer versao do Python;
  2. **dispersao** — lances vizinhos nao produzem sementes vizinhas, senao o
     sorteio do lance 3 fica parecido com o do lance 4.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE A SEMENTE **NAO** FAZ (RF-DES-211)
═══════════════════════════════════════════════════════════════════════════

**Ela nao iguala Python e Dart.** Os dois geram numeros diferentes a partir da
mesma semente, e ⛔ **nao precisam ser iguais**: o papel do job e **calibrar** (a
taxa em 20 execucoes), nao **prever** a partida de ninguem. Um adversario
estatisticamente equivalente basta para a banda de 70-80%.

⚠️ **A igualdade que importa e entre PESSOAS, e ela e Dart x Dart** — dois
aparelhos com a mesma versao do aplicativo enfrentam o mesmo adversario.

⛔ E por isso um gerador pseudoaleatorio proprio ficou **fora** desta entrega:
ele obrigaria a mexer no motor espelhado (que e cópia byte-idêntica do
laboratorio, com SHA-256 conferido) para comprar uma precisao que ninguem
precisa.
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
        nu_semente: a semente publicada no desafio.
        nu_lance: o numero do lance, contado de 1.

    ⚠️ **A conta e um hash, e nao `nu_semente + nu_lance`.** Somar daria sementes
    vizinhas para lances vizinhos, e geradores lineares (o `Random` do Dart e um
    deles) produzem primeiros valores parecidos a partir de sementes parecidas —
    o adversario ficaria repetitivo de um jeito que se percebe jogando.

    ⚠️ **Esta funcao existe nos dois lados**, e ⛔ **nao precisa dar o mesmo
    numero** que a do Dart: o que ela precisa e ser deterministica em cada lado.
    A igualdade que importa e entre pessoas (Dart x Dart).
    """
    validar(nu_semente)
    if nu_lance < 1:
        raise SementeInvalida(f"nu_lance comeca em 1; veio {nu_lance}")

    material = f"{nu_semente}:{nu_lance}".encode("utf-8")
    bruto = int.from_bytes(hashlib.sha256(material).digest()[:4], "big")
    return (bruto % SEMENTE_MAXIMA) + 1
