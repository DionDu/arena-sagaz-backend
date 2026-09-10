"""A ESCADA DE MASCOTES NO QUADRO — regua, e nao enfeite (RF-DES-060a/b/c, 203).

═══════════════════════════════════════════════════════════════════════════
POR QUE ELES ESTAO NO QUADRO
═══════════════════════════════════════════════════════════════════════════

O quadro **nunca fica vazio**, o alvo e sempre escalonado, e ⛔ **nao ha
mentira**: sao personagens declarados do aplicativo, e nao usuarios falsos. A
frase que a pessoa le nao e *"voce foi o 3o de 4"* — e **"voce passou o Tex;
faltou o Magno"**.

⚠️ **Eles estao la desde 00:00 UTC** (RF-DES-060a). Regua que aparece aos poucos
nao serve para medir, e um quadro sem o Tex as 9h contradiria, na tela ao lado, o
*"voce passou o Tex"* que o aplicativo acabou de dizer.

⚠️ **Sao TRES, e nao quatro** — o adversario do dia fica de fora. Ver a secao
sobre RF-DES-203, mais abaixo.

═══════════════════════════════════════════════════════════════════════════
⚠️ O TEMPO E ENCENADO, E E OBRIGATORIO QUE SEJA
═══════════════════════════════════════════════════════════════════════════

Com o tempo **real** — milissegundos de um motor rodando — os quatro levariam
sempre a parcela de tempo cheia de `Q`, e o quadro **nasceria com o topo
fechado**: ninguem passaria o Magno nunca, e a regua deixaria de ser regua.

O valor e sorteado numa faixa por personagem, **deterministico a partir do
`id_desafio`** — todo mundo ve o mesmo numero —, com a Cacau demorando e o Magno
rapido, e ⛔ **nenhum instantaneo**.

⚠️ **Deterministico e nao aleatorio**, e a diferenca e visivel: com `random`, dois
aparelhos veriam tempos diferentes para o mesmo mascote no mesmo dia, e a
conversa *"o Magno fez em 21 segundos"* deixaria de fazer sentido. O sorteio sai
de um SHA-256 de `(id_desafio, personagem)`, que e sempre o mesmo em qualquer
maquina e em qualquer versao do Python.

⛔ **`hash()` do Python nao serve** — ele e salgado por processo desde a 3.3, e
daria numeros diferentes a cada reinicio do servidor.

═══════════════════════════════════════════════════════════════════════════
⚠️ O XP TAMBEM E ENCENADO — E ESSA E UMA DECISAO, NAO UM ATALHO
═══════════════════════════════════════════════════════════════════════════

Seria natural calcular o `Q` do mascote pela formula real. Nao da, e a razao e
estrutural: `Q` soma parcelas de **tentativas**, **tempo** e **dicas**, e o
mascote nao tem nenhuma das tres de verdade — ele resolve na primeira, em
milissegundos, sem dica. Calcular daria `Q = 1` para todos eles.

Entao o XP sai da mesma maquina do tempo: **faixa por personagem, deterministica
do `id_desafio`**. ⚠️ **Com um modulador real:** a faixa e deslocada pela **taxa
medida** daquele mascote naquele desafio (`desafio.tb002_medicao_regua`). Um
desafio em que o Magno so resolve 4 de 20 lhe da XP no pe da faixa — porque
aquele desafio **e duro para ele**, e isso foi medido, nao inventado.

⛔ **Mascote nao recebe reacao e nao conta no denominador** (RF-DES-060c). Ele e
cenario e regua; a fracao e sobre gente. E isso e **estrutura**, nao `if` na
tela: reacao aponta para resolucao, e mascote nao tem resolucao.

═══════════════════════════════════════════════════════════════════════════
⛔ E O ADVERSARIO DO DIA NAO ENTRA NA ESCADA (RF-DES-203)
═══════════════════════════════════════════════════════════════════════════

Ele **nao joga contra si mesmo**, logo nao e regua naquele dia. A escada tem
**tres** degraus, e ela **roda junto** com o adversario:

    dia de Magno  →  Cacau · Pita · Tex     (mais encorajadora)
    dia de Cacau  →  Pita · Tex · Magno     (mais dura)

⚠️ **Isto reescreve a leitura literal de RF-DES-060a** (*"os quatro estao no
quadro"*), e a regra de precedencia da spec e explicita: onde os blocos
discordarem, vale o **mais recente** — e RF-DES-203 e de 04/09/2026.

⚠️ E e por isso que RF-DES-204 diz que a regua e a **taxa dos tres que nao sao o
adversario**: a banda *"a Pita resolve, a Cacau nao"* pressupunha adversario
fixo, e com rotacao ela deixou de fazer sentido.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence
from uuid import UUID

from api.desafios.modelos_evento import XP_PISO_POR_RESOLVER, XP_TETO_DO_DIA

#: A ordem da escada, do mais fraco ao mais forte. ⚠️ E a mesma de
#: `lib/core/jogos/personagem.dart`; um mascote novo entra nos dois lados.
PERSONAGENS = ("cacau", "pita", "tex", "magno")


@dataclass(frozen=True, slots=True)
class FaixaDoMascote:
    """A faixa de encenacao de um personagem.

    Atributos:
        xp_min, xp_max: onde o XP dele cai, dentro dos 18–30 do desafio.
        fracao_tempo_min, fracao_tempo_max: que fatia da regua de tempo do
            desafio ele consome. ⚠️ **Nunca zero**: "nenhum instantaneo" e
            requisito, e um mascote com tempo 0 levaria a parcela cheia e
            fecharia o topo.
        tentativas: quantas tentativas ele "gastou".
    """

    xp_min: int
    xp_max: int
    fracao_tempo_min: float
    fracao_tempo_max: float
    tentativas: int


#: ⚠️ As faixas **se sobrepoem de proposito**. Se cada personagem tivesse uma
#: faixa isolada, a ordem do quadro seria fixa e a pessoa sempre cairia no mesmo
#: degrau — e "voce passou o Tex" nunca surpreenderia. Com sobreposicao, um
#: desafio pode ter o Tex acima do Magno, e isso e informacao: aquele desafio
#: **e estranho para o Magno**.
FAIXAS: Mapping[str, FaixaDoMascote] = {
    "cacau": FaixaDoMascote(
        xp_min=18, xp_max=22, fracao_tempo_min=0.70, fracao_tempo_max=0.95,
        tentativas=3,
    ),
    "pita": FaixaDoMascote(
        xp_min=20, xp_max=25, fracao_tempo_min=0.50, fracao_tempo_max=0.78,
        tentativas=2,
    ),
    "tex": FaixaDoMascote(
        xp_min=23, xp_max=28, fracao_tempo_min=0.30, fracao_tempo_max=0.58,
        tentativas=2,
    ),
    "magno": FaixaDoMascote(
        xp_min=26, xp_max=30, fracao_tempo_min=0.12, fracao_tempo_max=0.36,
        tentativas=1,
    ),
}


def _fracao_determinista(id_desafio: UUID, co_personagem: str, sal: str) -> float:
    """Um numero em [0,1), sempre o mesmo para a mesma entrada.

    Args:
        id_desafio: o desafio.
        co_personagem: o mascote.
        sal: que grandeza esta sendo sorteada (`"xp"`, `"tempo"`, …). ⚠️ **Sem
            o sal, XP e tempo sairiam correlacionados**: o mascote com XP no topo
            da faixa teria sempre o tempo no topo da dele, e o padrao apareceria
            para quem olhasse dois dias seguidos.

    Returns:
        A fracao.

    ⛔ **SHA-256, e nao `hash()`.** O `hash()` do Python e salgado por processo
    desde a 3.3: dois reinicios do servidor dariam numeros diferentes para o
    mesmo desafio, e o tempo do Magno mudaria no meio do dia.
    """
    semente = f"{id_desafio}:{co_personagem}:{sal}".encode("utf-8")
    digest = hashlib.sha256(semente).digest()
    # Os 8 primeiros bytes bastam: 2^64 valores distintos, e a divisao os traz
    # para [0,1) sem viés perceptivel.
    bruto = int.from_bytes(digest[:8], "big")
    return bruto / 2**64


@dataclass(frozen=True, slots=True)
class LinhaDoMascote:
    """Um mascote no quadro do dia.

    ⛔ `reacoes` e `pode_reagir` sao fixos, e nao parametros: mascote nao tem
    resolucao, e reacao aponta para resolucao (RF-DES-060c).
    """

    co_personagem: str
    nu_xp: int
    nu_tempo_ms: int
    nu_tentativas: int

    @property
    def sujeito(self) -> str:
        """O vocabulario do contrato do quadro."""
        return "mascote"


def linha_do_mascote(
    *,
    id_desafio: UUID,
    co_personagem: str,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    taxa_medida: Optional[float] = None,
) -> LinhaDoMascote:
    """Encena a linha de um mascote, deterministicamente.

    Args:
        id_desafio: o desafio — a semente de tudo.
        co_personagem: qual mascote.
        nu_tempo_piso_ms, nu_tempo_teto_ms: a regua de tempo **daquele desafio**.
            ⚠️ E ela que faz o tempo encenado ter escala: 40 segundos e rapido
            num desafio de damas e lento num de tres lances.
        taxa_medida: a fracao de execucoes em que aquele mascote resolveu
            (`desafio.tb002_medicao_regua`). `None` quando o job ainda nao mediu.

    Returns:
        A linha, pronta para o quadro.

    ⚠️ **A taxa medida desloca a faixa, e nao a substitui.** Ela e o unico numero
    real desta funcao: um desafio em que o Magno so resolve 4 de 20 lhe da XP no
    pe da faixa dele, porque aquele desafio **e duro para ele** — e isso foi
    medido.
    """
    faixa = FAIXAS.get(co_personagem)
    if faixa is None:
        raise ValueError(
            f"personagem desconhecido no quadro: {co_personagem!r}. ⚠️ Mascote "
            "novo entra em `FAIXAS`, ou nao aparece na regua."
        )

    sorteio_xp = _fracao_determinista(id_desafio, co_personagem, "xp")
    if taxa_medida is not None:
        # ⚠️ A media entre o sorteio e a taxa: o sorteio dá variedade entre dias,
        # a taxa ancora no que foi medido. Usar so a taxa faria o quadro repetir
        # o mesmo XP sempre que a medicao repetisse; usar so o sorteio jogaria a
        # medicao fora.
        sorteio_xp = (sorteio_xp + taxa_medida) / 2

    nu_xp = faixa.xp_min + round(sorteio_xp * (faixa.xp_max - faixa.xp_min))
    # ⚠️ A trava final: 18–30 e a faixa de **um** desafio, e o `ck001_xp` da
    # migracao a exige. Um arredondamento para fora seria recusado pelo banco se
    # esta linha algum dia fosse gravada.
    nu_xp = max(XP_PISO_POR_RESOLVER, min(XP_TETO_DO_DIA, nu_xp))

    sorteio_tempo = _fracao_determinista(id_desafio, co_personagem, "tempo")
    fracao = faixa.fracao_tempo_min + sorteio_tempo * (
        faixa.fracao_tempo_max - faixa.fracao_tempo_min
    )
    nu_tempo_ms = int(nu_tempo_teto_ms * fracao)
    # ⛔ **Nenhum instantaneo** (RF-DES-060b): o piso da regua do desafio e o
    # tempo do gabarito jogado direto, e ninguem resolve mais rapido que isso.
    nu_tempo_ms = max(nu_tempo_piso_ms, nu_tempo_ms)

    return LinhaDoMascote(
        co_personagem=co_personagem,
        nu_xp=nu_xp,
        nu_tempo_ms=nu_tempo_ms,
        nu_tentativas=faixa.tentativas,
    )


def linhas_dos_mascotes(
    *,
    id_desafio: UUID,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    co_personagem_do_dia: Optional[str] = None,
    taxas: Optional[Mapping[str, float]] = None,
) -> list[LinhaDoMascote]:
    """A escada do quadro, desde 00:00 UTC (RF-DES-060a).

    Args:
        co_personagem_do_dia: o adversario daquele desafio. ⛔ **Ele NAO entra na
            escada** (RF-DES-203): nao joga contra si mesmo, logo nao e regua
            naquele dia.

    Returns:
        As linhas, na ordem da escada.

    ⚠️ **SAO TRES, E NAO QUATRO, e a escada RODA JUNTO com o adversario**
    (RF-DES-203). Em dia de Magno a escada e Cacau · Pita · Tex, mais
    encorajadora; em dia de Cacau e Pita · Tex · Magno, mais dura.

    ⚠️ **Isto REESCREVE a leitura literal de RF-DES-060a** (*"os quatro estao
    no quadro"*), e a regra de precedencia da spec e explicita: onde os blocos
    discordarem, vale o **mais recente**. RF-DES-203 e de 04/09/2026.

    ⚠️ **A escada incompleta seria pior que escada nenhuma** — e por isso o
    parametro e opcional: sem adversario declarado, voltam os quatro. Um filtro
    que engolisse um nome desconhecido devolveria tres degraus quando deveria
    devolver quatro, e a pessoa leria *"passei todo mundo"* sem ter passado o que
    faltava aparecer.
    """
    taxas = taxas or {}
    escada = [nome for nome in PERSONAGENS if nome != co_personagem_do_dia]
    return [
        linha_do_mascote(
            id_desafio=id_desafio,
            co_personagem=nome,
            nu_tempo_piso_ms=nu_tempo_piso_ms,
            nu_tempo_teto_ms=nu_tempo_teto_ms,
            taxa_medida=taxas.get(nome),
        )
        for nome in escada
    ]


def taxas_das_medicoes(
    medicoes: Sequence[Mapping[str, object]],
) -> dict[str, float]:
    """`{personagem: taxa}` a partir das linhas de `vw002_medicao_regua`.

    ⚠️ A taxa e **calculada**, e nao lida de uma coluna — a mesma decisao de
    `MedicaoDaRegua.taxa`: guardar a divisao criaria um terceiro numero que pode
    discordar dos dois que a originaram.
    """
    taxas: dict[str, float] = {}
    for linha in medicoes:
        execucoes = int(linha["nu_execucoes"])  # type: ignore[arg-type]
        if execucoes > 0:
            taxas[str(linha["co_personagem"])] = (
                int(linha["nu_resolveu"]) / execucoes  # type: ignore[arg-type]
            )
    return taxas
