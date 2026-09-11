"""T049h - de onde vem a POSICAO DE PARTIDA de um desafio de Pontinhos.

⚠️ **Ela vem do autoplay, e nao de um sorteio de tracos** (decisao do dono,
11/09/2026 — `DECISOES-do-dono.md` §8h). O acervo deste modulo foi extraido dos
mesmos estados de minimax com que a CNN do aplicativo foi treinada; quem o
constroi e `scripts/extrair_posicoes_de_autoplay_pontinhos.py`, que explica o
porque com todas as letras.

O resumo, para quem chegou aqui primeiro: **o gabarito do desafio e produzido
pela propria CNN** — o backend roda o mesmo `.tflite` do aplicativo, e o portao
T001 existe para provar que os dois runtimes concordam. Uma posicao fora da
distribuicao de treino produz uma solucao de referencia subotima, a regua mede a
coisa errada, e ⛔ **nada no log denuncia**.

═══════════════════════════════════════════════════════════════════════════
O QUE O ACERVO GUARDA, E POR QUE CABE EM 32 BITS
═══════════════════════════════════════════════════════════════════════════

So posicoes **sem nenhuma caixa fechada**. Nelas o placar e 0-0, a vez sai da
paridade, e — a propriedade que faz tudo isto funcionar — **qualquer ordem dos
mesmos tracos da o mesmo estado**. Entao a posicao inteira e o *conjunto* de
tracos marcados, e 31 tracos cabem num inteiro de 32 bits: um bit por traco, na
ordem canonica dos rotulos.

⚠️ **A ordem canonica e gravada DENTRO do arquivo** (`co_rotulo`), e nao
combinada de boca entre o script e este modulo. Um bit lido com a ordem errada
daria um tabuleiro diferente e igualmente valido — o erro mais caro que existe,
porque nada o acusa.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MODULO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao sorteia a semente** — ela vem do dia, e quem a passa e o gerador. Trocar
a fonte da posicao nao pode custar a idempotencia de T038, e por isso a unica
fonte de acaso aqui e o `random.Random` que chega pronto.
⛔ **Nao valida a sequencia** — quem faz isso e `posicao_inicial.do_pontinhos()`,
reproduzindo lance a lance pelo motor. Uma segunda validacao aqui seria a segunda
fonte da verdade que o projeto passa o tempo todo evitando.
"""

from __future__ import annotations

import functools
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# `parents[1]` sobe de `job/este_arquivo.py` para a raiz do backend.
RAIZ = Path(__file__).resolve().parents[1]

#: O acervo, construido por `scripts/extrair_posicoes_de_autoplay_pontinhos.py`.
#:
#: ⚠️ Ele **viaja no repositorio** (2,6 MB), e de proposito: o job roda no Railway,
#: e os NPZ de origem (106 MB) sao do laboratorio e nao vao para la.
CAMINHO_DO_ACERVO = RAIZ / "dados" / "jogo_pontinhos" / "posicoes_de_autoplay_pequeno.npz"

#: Quantos tracos tem o tabuleiro 4x3 — o teto do bitmask.
TRACOS_DO_TABULEIRO = 31


class SemPosicaoDeAutoplay(RuntimeError):
    """Nao ha posicao de autoplay com a quantidade de tracos pedida.

    ⚠️ **Falha alto de proposito.** O caminho natural para este erro e alguem
    escolher, no editorial, um `nu_lances_de_preparo` que nenhuma partida real
    alcanca sem fechar caixa — acima de 20 tracos, no 4x3, essa posicao **nao
    existe**. Cair de volta no sorteio as cegas resolveria o sintoma e
    reintroduziria, calado, exatamente o defeito que T049h veio corrigir.
    """


@dataclass(frozen=True, slots=True)
class Acervo:
    """As posicoes de autoplay, prontas para consulta por fase da partida.

    Atributos:
        nu_mascara: as posicoes distintas, **ordenadas por quantidade de tracos**
            e, dentro dela, pelo valor — e essa ordem que torna "as posicoes com
            N tracos" uma fatia contigua.
        co_rotulo: os 31 rotulos na ordem canonica. O bit `i` da mascara e o
            traco `co_rotulo[i]`.
        nu_inicio: onde comeca cada fase. As posicoes com `n` tracos sao
            `nu_mascara[nu_inicio[n] : nu_inicio[n + 1]]`. Tem
            `TRACOS_DO_TABULEIRO + 2` entradas para que a fatia de qualquer `n`
            de 0 a 31 seja valida — inclusive as vazias, que dao fatia vazia em
            vez de `IndexError`.
    """

    nu_mascara: np.ndarray
    co_rotulo: tuple[str, ...]
    nu_inicio: np.ndarray

    def com_tracos(self, nu_tracos: int) -> np.ndarray:
        """As posicoes que tem exatamente `nu_tracos` tracos marcados."""
        if not 0 <= nu_tracos <= TRACOS_DO_TABULEIRO:
            return self.nu_mascara[:0]
        return self.nu_mascara[self.nu_inicio[nu_tracos] : self.nu_inicio[nu_tracos + 1]]


@functools.lru_cache(maxsize=1)
def carregar() -> Acervo:
    """Le o acervo do disco, uma vez por processo.

    `lru_cache` porque sao 897 mil posicoes, e o job consulta o acervo varias
    vezes por dia gerado — reler o arquivo a cada consulta trocaria milissegundos
    de CPU por dezenas de megabytes de leitura repetida.

    Raises:
        FileNotFoundError: com a receita de como reconstruir o arquivo. ⚠️ Uma
            mensagem generica aqui mandaria alguem procurar defeito no gerador.
    """
    if not CAMINHO_DO_ACERVO.is_file():
        raise FileNotFoundError(
            f"o acervo de posicoes de autoplay nao esta no disco ({CAMINHO_DO_ACERVO}).\n"
            "Reconstrua com, na maquina do dono (a origem e o laboratorio de IA):\n"
            "  .venv\\Scripts\\python scripts\\extrair_posicoes_de_autoplay_pontinhos.py"
        )

    arquivo = np.load(CAMINHO_DO_ACERVO)
    mascaras = arquivo["nu_mascara"]
    rotulos = tuple(str(x) for x in arquivo["co_rotulo"])

    if len(rotulos) != TRACOS_DO_TABULEIRO:
        raise ValueError(
            f"o acervo traz {len(rotulos)} rotulos, e o tabuleiro 4x3 tem "
            f"{TRACOS_DO_TABULEIRO}. ⛔ O arquivo nao e do tabuleiro pequeno."
        )

    return Acervo(
        nu_mascara=mascaras,
        co_rotulo=rotulos,
        nu_inicio=_inicio_de_cada_fase(mascaras),
    )


def _inicio_de_cada_fase(mascaras: np.ndarray) -> np.ndarray:
    """Onde comeca, no vetor ordenado, o bloco de cada quantidade de tracos.

    ⚠️ **Derivado, e nao gravado no arquivo.** Guardar os deslocamentos ao lado
    das mascaras criaria dois fatos que precisam concordar, e o dia em que
    discordassem produziria posicoes com a quantidade errada de tracos — sem
    erro nenhum, porque toda mascara e um tabuleiro valido.

    `np.searchsorted` sobre a contagem de bits acha a fronteira de cada bloco em
    tempo logaritmico; o vetor ja chega ordenado por essa contagem.
    """
    quantos = _contar_bits(mascaras)
    # `side="left"` devolve o primeiro indice cujo valor e >= n — que e
    # exatamente onde o bloco de `n` comeca (ou onde ele comecaria, se vazio).
    return np.searchsorted(
        quantos, np.arange(TRACOS_DO_TABULEIRO + 2), side="left"
    ).astype(np.int64)


def _contar_bits(mascaras: np.ndarray) -> np.ndarray:
    """Quantos bits ligados tem cada mascara — ou seja, quantos tracos marcados.

    `np.bitwise_count` existe do numpy 2.0 em diante, e `requirements_job.txt`
    trava o `numpy==2.2.6` — a imagem que roda o job tem a funcao.
    """
    return np.bitwise_count(mascaras)


def tracos_da_mascara(mascara: int, co_rotulo: tuple[str, ...]) -> list[str]:
    """Os rotulos dos tracos ligados numa mascara, na ordem canonica.

    ⚠️ `1 << i` testa o bit `i`; o `&` devolve zero quando ele esta desligado. E
    a operacao inversa exata da que o script de extracao fez ao montar a mascara.
    """
    return [rotulo for i, rotulo in enumerate(co_rotulo) if mascara & (1 << i)]


def sortear(sorteio: random.Random, nu_tracos: int) -> tuple[str, ...]:
    """Uma posicao de autoplay com `nu_tracos` tracos, como sequencia de lances.

    Args:
        sorteio: o `random.Random` **ja semeado pelo dia**. ⛔ Este modulo nao
            cria gerador proprio: a idempotencia de T038 depende de a semente
            atravessar inteira.
        nu_tracos: quantos tracos a posicao de partida deve ter. E o
            `nu_lances_de_preparo` do editorial.

    Returns:
        Os rotulos na ordem em que devem ser jogados.

    Raises:
        SemPosicaoDeAutoplay: quando nao ha nenhuma posicao com essa quantidade.

    ⚠️ **A ORDEM e embaralhada, e nao a canonica.** Sem caixa fechada os jogadores
    se alternam estritamente, entao a ordem decide **de quem e cada traco** — e e
    isso que o aplicativo pinta de azul e vermelho. A ordem canonica (uma
    varredura geometrica do tabuleiro) daria sempre o mesmo padrao de cores, e o
    desafio pareceria montado a regua em vez de jogado.

    ✅ **E embaralhar e seguro**: "sem caixa fechada" e monotono — se o conjunto
    final nao fecha caixa nenhuma, nenhum prefixo dele fecha. Qualquer ordem e
    uma sequencia legal, e todas terminam no mesmo tabuleiro, com o mesmo placar
    0-0 e a mesma vez.

    ⚠️ E a ordem **nao** tira a posicao da distribuicao da CNN: a rede nao ve
    dono de traco — `partida_para_dataset` manda todo traco ocupado para `9`,
    seja de quem for.
    """
    acervo = carregar()
    candidatas = acervo.com_tracos(nu_tracos)

    if len(candidatas) == 0:
        disponiveis = [
            n
            for n in range(TRACOS_DO_TABULEIRO + 1)
            if len(acervo.com_tracos(n)) > 0
        ]
        raise SemPosicaoDeAutoplay(
            f"nenhuma posicao de autoplay tem {nu_tracos} tracos sem caixa fechada. "
            f"⛔ Acima de {max(disponiveis)} tracos essa posicao nao existe no 4x3: "
            "para chegar la, alguma caixa teve de ser fechada. "
            f"Quantidades com acervo: {min(disponiveis)} a {max(disponiveis)}. "
            "Ajuste `nu_lances_de_preparo` no editorial."
        )

    # `randrange` e nao `choice`: `candidatas` e um vetor de numpy, e `choice`
    # devolveria um `np.uint32` que vira `1 << i` com semantica de numpy —
    # estouro silencioso em vez de inteiro grande do Python.
    mascara = int(candidatas[sorteio.randrange(len(candidatas))])

    lances = tracos_da_mascara(mascara, acervo.co_rotulo)
    sorteio.shuffle(lances)
    return tuple(lances)
