"""O GERADOR DE CANDIDATOS a desafio do dia (RF-DES-010/011/201, T034).

═══════════════════════════════════════════════════════════════════════════
O QUE ELE FAZ, NA ORDEM
═══════════════════════════════════════════════════════════════════════════

    1. escolhe o JOGO       — rodizio por data
    2. escolhe o TIPO       — rodizio, sem repetir o do dia anterior
    3. escolhe o PERSONAGEM — o adversario do dia
    4. gera VARIOS candidatos, mede cada um e devolve os melhores

⚠️ **O nome do personagem entra no ENUNCIADO** — *"feche 4 caixas em 2 turnos
jogando contra a Pita"* —, e nao e enfeite: e ele que diz o **tamanho da tarefa**.
O mesmo objetivo contra a Cacau e contra o Magno sao dois desafios diferentes, e
quem le a frase precisa saber qual dos dois esta pegando.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS DUAS PORTAS QUE UM CANDIDATO PRECISA ATRAVESSAR
═══════════════════════════════════════════════════════════════════════════

    receita  → existe regra escrita para este tipo?      (`tipos_de_desafio.py`)
    vetor    → os dois lados leem essa regra igual?      (`contratos/…json`)

⛔ **Faltando qualquer uma, o tipo nao e publicavel.** Sao duas portas para a
mesma falha silenciosa, fechadas por caminhos diferentes: a receita garante que
existe regra; o vetor garante que Dart e Python concordam sobre ela.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao mede a dificuldade** — isso e a regua (T035), que roda os tres mascotes
que nao sao o adversario do dia.
⛔ **Nao grava** — isso e T038, e la mora a idempotencia.
⛔ **Nao aprova** — quem aprova e o dono, no painel de curadoria. Tudo o que sai
daqui nasce **candidato**.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from motores.damas.motor_damas import EstadoDamas, MotorDamas, estado_inicial
from motores.nucleo.orcamento import Orcamento
from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos import abertura_forcada
from motores.pontinhos import guloso as guloso_mod
from motores.pontinhos.motor_pontinhos import EstadoPontinhos
from motores.pontinhos.politica import JogadorPontinhos

from . import editorial as editorial_mod
from . import gabarito as gabarito_mod
from . import posicoes_de_autoplay_pontinhos as autoplay_mod
from . import posicao_inicial as posicao_mod
from . import semente as semente_mod
from .espelho_de_damas import com_as_brancas_a_jogar
from .moldes_de_damas import objetivo_no_primeiro_lance
from .perfil import NIVEL_POR_PERSONAGEM
from .tipos_de_desafio import Receita, receita_de, tipos_do_jogo

RAIZ = Path(__file__).resolve().parents[1]
VETORES = RAIZ / "contratos" / "vetores-verificacao-desafio.json"

#: Os jogos do rodizio, em ordem estavel.
#:
#: ⛔ **A velha NAO entra, e desde 10/09/2026 isso e decisao de PRODUTO, e nao
#: pendencia tecnica** (`DECISOES-do-dono.md` §8g): *"jogo da velha nao teremos
#: no desafio pois ele nao tem muita variacao. E um jogo chato, nao ha formas
#: diferentes de jogar para caber num desafio."*
#:
#: ⚠️ A diferenca importa para quem ler isto depois. Ate aquela data a ausencia
#: era falta de peca — sem medidor no juiz e sem vetores —, e parecia uma tarefa
#: esperando a vez. Agora ela **nao ganha** medidor nem vetores para este fim: o
#: esforco nao se justifica, e a T050(a) deixou de pedir "os tres jogos".
#:
#: ⚠️ Jogo NOVO continua entrando pela regra antiga: com medidor **e** vetores,
#: nunca com uma so das duas.
JOGOS_DO_RODIZIO = ("pontinhos", "damas")

#: Os quatro mascotes, na ordem da escada de dificuldade.
PERSONAGENS = ("cacau", "pita", "tex", "magno")

#: As modalidades que cada jogo rodizia. Tupla vazia = o jogo nao tem modalidade.
#:
#: ⚠️ **Decisao do dono, 10/09/2026: "quanto mais variado, melhor"** — e a medicao
#: apoiou. Os quatro regulamentos rodam nos MESMOS moldes (todos sao damas de 32
#: casas; o que muda sao as regras, nao o tabuleiro), e a taxa de geracao melhora:
#: dos 8 moldes de hoje, brasileira resolveu 4, anglo 5, **portuguesa 7** e casa 4.
#: Rodiziar nao so quadruplica a variedade — alivia o gargalo que e achar
#: candidato.
#:
#: ⚠️ **`casa` nao e regulamento de federacao**: e a variante do proprio projeto —
#: brasileiras sem a Lei da Maioria, *"como a maior parte das pessoas joga em casa
#: no Brasil"*. Para o Desafio do Dia ela pode ser a **mais** familiar, e nao a
#: menos.
#:
#: ⛔ **E a modalidade PRECISA aparecer no enunciado.** Sem isso, quem so joga
#: brasileira receberia regras anglo — pedra sem captura para tras, coroacao
#: encerrando o lance, **as pretas comecando** — e concluiria que o aplicativo
#: esta quebrado. E por isso que ela entra em `js_objetivo`.
MODALIDADES_POR_JOGO: dict[str, tuple[str, ...]] = {
    "pontinhos": (),
    "damas": ("brasileira", "anglo", "portuguesa", "casa"),
}

#: O ORCAMENTO de busca por lance, na geracao.
#:
#: ⚠️ **Sem teto, a geracao nao termina.** O Sagaz das damas busca ate onde o
#: contrato do nivel permitir, e o contrato foi calibrado para o APARELHO de
#: alguem esperando ~0,8 s por lance — no job sao dezenas de candidatos x varios
#: lances cada, e a conta estoura. Medido em 09/09/2026: sem orcamento, uma unica
#: geracao de damas passou de 6 minutos sem terminar.
#:
#: ⚠️ E o teto do orcamento **nao substitui** o do contrato: o motor usa o
#: **menor** dos dois. O contrato define o *nivel*; este aqui protege o *job*.
#:
#: ⚠️ O preco, dito em voz alta: com teto baixo o Sagaz joga um pouco pior, e o
#: gabarito pode nao ser a solucao mais curta. Isso e aceitavel — o gabarito
#: prova que o desafio TEM solucao (RF-DES-196), e nao que aquela e a melhor.
NOS_POR_LANCE_NA_GERACAO = 60_000
SEGUNDOS_POR_LANCE_NA_GERACAO = 2.0

#: A data de referencia do rodizio. Qualquer data serve; o que nao pode e mudar
#: depois, porque isso deslocaria o rodizio inteiro de um dia para o outro.
EPOCA_DO_RODIZIO = date(2026, 1, 1)


class SemCandidato(RuntimeError):
    """Nenhum candidato sobreviveu as tentativas.

    ⚠️ **Nao e falha do job — e resposta.** Acontece quando o tipo do dia e duro
    de gerar; quem chama tenta outro tipo, ou deixa a fila mais curta e avisa (o
    aviso de fila curta e T040).
    """


@dataclass(frozen=True, slots=True)
class Candidato:
    """Um desafio recem-gerado, ainda **nao medido e nao aprovado**.

    Atributos:
        co_jogo, co_variante, co_modalidade: onde ele se joga.
        co_formato_posicao, js_posicao_inicial: de onde se parte.
        receita: o tipo, ja resolvido.
        js_chegada: a linha de chegada montada pela receita.
        js_objetivo: os valores da frase.
        co_personagem: o adversario do dia.
        nu_semente: a semente publicada.
        js_solucao: o gabarito.
        nu_lances_solucao: o tamanho dele, que vira coluna.
        parametros: os numeros **efetivamente usados** para montar a chegada.
    """

    co_jogo: str
    co_variante: str
    co_modalidade: str | None
    co_formato_posicao: str
    js_posicao_inicial: dict[str, Any]
    receita: Receita
    js_chegada: dict[str, Any]
    js_objetivo: dict[str, Any]
    co_personagem: str
    nu_semente: int
    js_solucao: dict[str, Any]
    nu_lances_solucao: int

    #: Os parametros **desta** posicao, e nao os do editorial.
    #:
    #: ⛔ **Existe porque nem todo alvo vem do editorial.** Em `acima_do_guloso`
    #: o numero e calculado a partir da posicao (`G + k`), e quem publica as
    #: medidas de saida precisa do numero **publicado** para montar o `vr_max`:
    #: usar os parametros do editorial daria `KeyError: 'caixas'`, e um `vr_max`
    #: fixo pagaria nota cheia por um alvo diferente do que a frase pediu.
    #:
    #: ⚠️ Para os tipos de alvo fixo e simplesmente uma copia do que veio do
    #: editorial — de proposito: assim quem consome nao precisa saber de qual
    #: familia o tipo e.
    #:
    #: ⛔ **Sem valor padrao**, de proposito. Um `{}` aqui faria um candidato
    #: construido sem parametros chegar intacto ate a hora de publicar e estourar
    #: la com `KeyError: 'caixas'` — depois de gerado, medido e aprovado. Sem
    #: padrao, quem esquecer descobre na construcao.
    parametros: Mapping[str, Any]

    de_diagnostico: list[str] = field(default_factory=list, compare=False)

    #: A posicao de partida **como objeto do motor**, e nao como JSON.
    #:
    #: ⚠️ Ela existe porque os dois passos seguintes — medir a regua (T035) e
    #: provar que a partida termina (T036) — precisam **jogar de novo a partir
    #: dali**, e reconstruir o estado a partir de `js_posicao_inicial` seria uma
    #: segunda travessia do mesmo caminho, capaz de discordar da primeira.
    #:
    #: ⛔ **Isto NAO dispensa `posicao_inicial.conferir()`**: quem prova que o
    #: JSON publicado reproduz esta posicao e ele, e o `principal()` o chama
    #: antes de gravar. Sem essa conferencia, `vez_de` e `placar` seriam
    #: anotacao decorativa.
    #:
    #: `compare=False` porque dois candidatos iguais continuam iguais mesmo que
    #: so um carregue o estado; `repr=False` porque o tabuleiro inteiro num log
    #: de erro esconderia a mensagem.
    estado_inicial: Any = field(default=None, compare=False, repr=False)


# ═══════════════════════════════════════════════════════════════════════════
# 1. As tres escolhas do dia
# ═══════════════════════════════════════════════════════════════════════════


def escolher_jogo(dt_dia: date) -> str:
    """O jogo do dia, por rodizio simples sobre a data.

    ⚠️ **Deterministico, e nao sorteado**: assim duas execucoes do job para o
    mesmo dia escolhem o mesmo jogo, e a idempotencia de T038 nao depende de
    sorte. E, como efeito colateral util, a fila fica previsivel para quem
    acompanha a curadoria.
    """
    dias = (dt_dia - EPOCA_DO_RODIZIO).days
    return JOGOS_DO_RODIZIO[dias % len(JOGOS_DO_RODIZIO)]


def escolher_tipo(co_jogo: str, dt_dia: date, *, tipos_recentes: Sequence[str] = ()) -> str:
    """O tipo do dia, sem repetir os recentes.

    Args:
        tipos_recentes: os tipos ja publicados nos ultimos dias daquele jogo.

    ⚠️ **O rodizio existe para o dia nao parecer o de ontem.** Dois desafios
    seguidos de *"feche N caixas"* fazem a coisa toda parecer uma tarefa so, e a
    razao de o desafio ser diario e justamente a variedade.

    ⚠️ Se todos os tipos forem recentes, o rodizio **ignora a restricao** em vez
    de falhar: um jogo com poucos tipos publicaveis (hoje, dois por jogo) nao
    pode ficar sem desafio por causa de uma regra de variedade.
    """
    disponiveis = tipos_do_jogo(co_jogo)
    if not disponiveis:
        raise SemCandidato(
            f"o jogo {co_jogo!r} nao tem tipo publicavel. ⛔ Tipo entra com "
            "receita E vetor, nunca com uma so das duas."
        )

    frescos = [t for t in disponiveis if t not in tipos_recentes] or disponiveis
    dias = (dt_dia - EPOCA_DO_RODIZIO).days

    # ⛔ **A conta e sobre a VEZ daquele jogo, e nao sobre o dia** — e a
    # diferenca entre um rodizio que roda e um que fica parado.
    #
    # ⚠️ **O defeito, medido na primeira execucao real (10/09/2026):** `dias % 2`
    # escolhia o jogo, e `dias % 2` escolhia o tipo. Um jogo so aparece numa das
    # duas paridades de `dias`, entao, para ele, `dias % 2` e **constante** — os
    # dois rodizios ficavam travados em fase. Sete dias seguidos escolheram
    # `pontinhos_chegar_ao_placar` e `damas_coroar`, e os outros dois tipos
    # publicaveis nunca sairiam.
    #
    # ⚠️ E ele era quase invisivel: `tipos_recentes` mascarava metade do sintoma,
    # trocando o tipo **so depois** de um dia ter publicado. Nos dias em que a
    # geracao falhava, nada entrava na lista de recentes e o mesmo tipo quebrado
    # voltava no dia seguinte — quatro vezes seguidas.
    #
    # `dias // len(JOGOS_DO_RODIZIO)` conta quantas vezes o rodizio ja deu a volta,
    # e essa contagem avanca **a cada aparicao** do jogo, e nao a cada dia.
    vez_do_jogo = dias // len(JOGOS_DO_RODIZIO)
    return frescos[vez_do_jogo % len(frescos)]


def escolher_modalidade(co_jogo: str, dt_dia: date) -> str | None:
    """A modalidade do dia, ou `None` para jogo que nao tem.

    ⛔ **O contador NAO pode ser o mesmo do tipo, e essa e a licao de 10/09/2026.**
    Se a modalidade usasse `vez_do_jogo % 4` enquanto o tipo usa
    `vez_do_jogo % 2`, os dois andariam juntos: o tipo par so apareceria com as
    modalidades pares, e **metade das combinacoes nunca sairia**. E exatamente o
    travamento em fase que fez o Pontinhos publicar o mesmo tipo quatro dias
    seguidos, so que mais dificil de enxergar.

    A modalidade anda **um passo a cada volta completa dos tipos** — um
    odometro: o digito da direita (o tipo) gira rapido, o da esquerda (a
    modalidade) gira quando o da direita completa a volta. Assim as `tipos x
    modalidades` combinacoes saem todas.
    """
    modalidades = MODALIDADES_POR_JOGO.get(co_jogo, ())
    if not modalidades:
        return None

    dias = (dt_dia - EPOCA_DO_RODIZIO).days
    vez_do_jogo = dias // len(JOGOS_DO_RODIZIO)
    # ⚠️ Conta os tipos **publicaveis**, e nao os `frescos` de `escolher_tipo`:
    # `tipos_recentes` varia com o que ja foi publicado, e uma modalidade que
    # dependesse disso mudaria de dono conforme a fila — deixando de ser
    # reproduzivel, que e o que a idempotencia de T038 precisa.
    quantos_tipos = max(1, len(tipos_do_jogo(co_jogo)))
    return modalidades[(vez_do_jogo // quantos_tipos) % len(modalidades)]


def escolher_variante(co_jogo: str, dt_dia: date, *, quantas_variantes: int) -> int:
    """Qual VARIANTE de parametros aquele tipo usa hoje (T049f).

    Args:
        co_jogo: o jogo do dia.
        dt_dia: a data.
        quantas_variantes: quantas o tipo tem, hoje. ⛔ **Entra por parametro, e
            nao e lido do editorial aqui**: este modulo nao conhece o editorial —
            se conhecesse, o gerador passaria a depender de com que numeros as
            coisas vao ao ar, que e exatamente a fronteira que `editorial.py`
            existe para desenhar.

    Returns:
        O indice da variante, de `0` a `quantas_variantes - 1`.

    ⚠️ **Prioridade do dono, 10/09/2026:** *"e muito importante que estes
    parametros variem, senao os desafios viram pura repeticao"*. A **posicao**
    variava; a **tarefa**, nao — todo `chegar_ao_placar` era "7 caixas".

    ⛔ **ESTE E O TERCEIRO DIGITO DO ODOMETRO, E A ARMADILHA JA PEGOU DUAS
    VEZES.** Se a variante usasse o contador do tipo (`vez_do_jogo`) ou o da
    modalidade (`vez_do_jogo // quantos_tipos`), ela andaria **em fase** com
    aquele digito, e uma fatia das combinacoes nunca sairia:

        10/09/2026, 1ª vez: `dias % 2` escolhia o jogo **e** o tipo. Um jogo so
        aparece numa das paridades de `dias`, entao `dias % 2` era **constante**
        para ele — sete dias seguidos com o mesmo tipo, e os outros nunca.

        10/09/2026, 2ª vez: a modalidade quase usou `vez_do_jogo % 4` enquanto o
        tipo usava `vez_do_jogo % 2` — o tipo par so sairia com as modalidades
        pares, e **metade** das combinacoes nunca apareceria. ⚠️ E este seria
        **pior de enxergar**: a fila *pareceria* variada, com tipos alternando e
        modalidades alternando, e so uma contagem revelaria os pares ausentes.

    A regra do odometro: o digito da direita gira rapido; o da esquerda gira
    quando o da direita **completa a volta**. Entao a variante divide pelo
    produto dos dois digitos a sua direita — tipos x modalidades.

    ⚠️ **E o divisor usa os tipos PUBLICAVEIS, nao os `frescos`.** `escolher_tipo`
    filtra por `tipos_recentes`, que varia com o que ja foi publicado; um divisor
    que dependesse disso deixaria de ser reproduzivel, e a idempotencia de T038
    precisa que ele seja. E a mesma escolha que `escolher_modalidade` ja faz.

    ⚠️ **Cobertura, com contagens diferentes por tipo:** fixados o tipo e a
    modalidade, `vez_do_jogo` avanca de `quantos_tipos x quantas_modalidades` em
    `quantos_tipos x quantas_modalidades` — logo o quociente avanca de 1 em 1, e
    o resto passa por **todas** as variantes daquele tipo, quantas quer que sejam.
    """
    if quantas_variantes <= 1:
        # ⚠️ Um tipo com uma variante so nao precisa de conta nenhuma — e e o
        # caso das damas hoje, enquanto as candidatas nao forem medidas.
        return 0

    dias = (dt_dia - EPOCA_DO_RODIZIO).days
    vez_do_jogo = dias // len(JOGOS_DO_RODIZIO)

    quantos_tipos = max(1, len(tipos_do_jogo(co_jogo)))
    # ⚠️ `max(1, ...)` porque o Pontinhos **nao tem modalidade**, e a tupla vazia
    # daria divisao por zero. Para ele o odometro tem dois digitos, e a variante
    # anda a cada volta completa dos tipos.
    quantas_modalidades = max(1, len(MODALIDADES_POR_JOGO.get(co_jogo, ())))

    return (vez_do_jogo // (quantos_tipos * quantas_modalidades)) % quantas_variantes


def escolher_personagem(dt_dia: date) -> str:
    """O adversario do dia, por rodizio.

    ⚠️ **O personagem e o nivel**, e por isso ele entra na frase: *"contra a
    Cacau"* e *"contra o Magno"* sao tarefas de tamanhos diferentes, mesmo com o
    objetivo identico.
    """
    dias = (dt_dia - EPOCA_DO_RODIZIO).days
    return PERSONAGENS[dias % len(PERSONAGENS)]


def nivel_do_personagem(co_personagem: str) -> NivelDeMotor:
    """Traduz o mascote no degrau de dificuldade do motor.

    ⚠️ **Sagaz e o nome do DEGRAU; Magno e o nome do PERSONAGEM.** Os dois
    vocabularios convivem no projeto desde as damas, e trocar um pelo outro e o
    engano mais comum de quem chega.
    """
    escada = {
        "cacau": NivelDeMotor.CACAU,
        "pita": NivelDeMotor.PITA,
        "tex": NivelDeMotor.TEX,
        "magno": NivelDeMotor.SAGAZ,
    }
    if co_personagem not in escada:
        raise ValueError(f"personagem desconhecido: {co_personagem!r}")
    return escada[co_personagem]


# ═══════════════════════════════════════════════════════════════════════════
# 2. A porta dos vetores
# ═══════════════════════════════════════════════════════════════════════════


def tipos_com_vetor() -> set[str]:
    """Os tipos que tem vetor de verificacao no disco.

    ⛔ **Tipo sem vetor nao e publicavel** (regra 2 do contrato). Sem vetor, a
    divergencia que RF-DES-127 preve nasce **calada**: o aplicativo julga de um
    jeito, o servidor de outro, e a unica pista seria o alerta de divergencia —
    que so aparece depois de alguem jogar.
    """
    if not VETORES.is_file():
        # ⚠️ Ausencia do arquivo e ZERO tipos publicaveis, e nao "publique tudo".
        # O silencio precisa custar caro do lado seguro.
        return set()
    documento = json.loads(VETORES.read_text(encoding="utf-8"))
    return {v["co_tipo_desafio"] for v in documento["vetores"]}


def exigir_vetor(co_tipo_desafio: str) -> None:
    """Falha alto se o tipo nao tiver vetor."""
    if co_tipo_desafio not in tipos_com_vetor():
        raise SemCandidato(
            f"o tipo {co_tipo_desafio!r} nao tem vetor de verificacao. ⛔ Sem "
            "vetor, uma divergencia entre o julgamento do aplicativo e o do "
            "servidor nasce calada. Escreva o vetor primeiro."
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. A geracao
# ═══════════════════════════════════════════════════════════════════════════


def _preparar_pontinhos(sorteio: random.Random, lances_de_preparo: int) -> EstadoPontinhos:
    """A posicao de partida do Pontinhos: uma posicao REAL de autoplay.

    Args:
        sorteio: o `random.Random` ja semeado pelo dia — e ele que escolhe qual
            das centenas de milhares de posicoes daquela fase sai hoje.
        lances_de_preparo: quantos tracos a posicao deve ter marcados.

    ⚠️ **Ate 11/09/2026 esta funcao sorteava os tracos as cegas**, e o comentario
    que a justificava dizia que *"uma partida bem jogada dos dois lados converge
    para posicoes parecidas; o acaso e o que da variedade a fila"*.

    ⛔ **E o mesmo argumento que o projeto ja testou e DESCARTOU no treino da
    CNN**: o dataset de tabuleiros aleatorios deu uma rede ruim, porque dois
    jogadores quase nunca chegam aqueles estados — foi por isso que se passou ao
    autoplay de minimax, e a rede melhorou muito.

    ⚠️ E aqui a consequencia de reintroduzi-lo e **concreta**: o gabarito deste
    desafio e produzido logo abaixo, por `_resolver`, **pela propria CNN** (o
    backend roda o mesmo `.tflite` do aplicativo — e o portao T001 existe para
    provar que os dois runtimes concordam). Uma posicao fora da distribuicao de
    treino produz uma solucao de referencia subotima, a regua mede a coisa
    errada, e ⛔ **nada no log denuncia**.

    ⚠️ **O placar inicial continua 0-0, e agora por construcao e nao por
    cuidado.** A versao anterior precisava recusar, lance a lance, todo traco que
    fechasse caixa; o acervo so guarda posicoes que ja nasceram sem caixa
    fechada, porque e nelas — e so nelas — que um conjunto de tracos volta a ser
    uma sequencia de lances (a posse de caixa e historico, e os NPZ nao a
    guardam). O porque inteiro esta em `posicoes_de_autoplay_pontinhos.py`.
    """
    return EstadoPontinhos(
        lances=autoplay_mod.sortear(sorteio, nu_tracos=lances_de_preparo)
    )


#: Quem sabe recusar um desafio por erro do adversario, **por jogo**.
#:
#: ⚠️ **E um registro, e nao um `if co_jogo == ...` no meio do laco**, por dois
#: motivos. O primeiro e que a pergunta nao e a mesma em todo jogo: nos Pontinhos
#: "entregar" tem significado exato (a cadeia que o outro leva de graca); nas
#: damas, nao ha equivalente — um lance ruim ali e uma **avaliacao**, e avaliar
#: exige busca e vira opiniao. O segundo e que um jogo que nao esta aqui **nao e
#: recusado**, e isso fica visivel: a ausencia da chave e a declaracao de que
#: aquele jogo ainda nao tem a regra, em vez de um `else` silencioso.
RECUSA_POR_JOGO = {"pontinhos": abertura_forcada.dependeu_de_erro}


def motivo_de_erro_do_adversario(
    co_jogo: str,
    arbitro,
    inicial,
    fita: list[dict[str, Any]],
    jogador: int,
) -> str | None:
    """Este desafio so existe porque o adversario jogou mal? Diz por que.

    Args:
        co_jogo: qual jogo — decide se ha regra para aplicar.
        arbitro: o motor daquele jogo (aqui so as regras sao usadas).
        inicial: a posicao de partida do desafio.
        fita: os passos do gabarito.
        jogador: quem resolve o desafio.

    Returns:
        A frase do motivo, ou `None` quando o desafio esta de pe — inclusive
        quando o jogo ainda nao tem regra.

    ⚠️ **Nao levanta excecao quando o jogo nao esta no registro**, de proposito: a
    regra e um filtro de qualidade, e um jogo novo entrando na Arena nao pode
    deixar de gerar desafio por falta dela. ⛔ Mas tambem nao finge que filtrou —
    e por isso que o registro fica logo acima, visivel, com o comentario dizendo
    quem esta de fora.
    """
    regra = RECUSA_POR_JOGO.get(co_jogo)
    if regra is None:
        return None
    # ⚠️ **Jogador e arbitro nao sao a mesma coisa.** Nas damas o `MotorDamas` e
    # os dois; no Pontinhos quem joga e a POLITICA (`JogadorPontinhos`), que sabe
    # `decidir` e nao sabe `aplicar`. ⛔ Passar o jogador aqui quebrou com
    # `'JogadorPontinhos' object has no attribute 'aplicar'` em 11/09/2026 — e
    # quebrou **calado**, porque a excecao subia dentro do laco de tentativas e
    # o dia simplesmente saia sem candidato.
    return regra(getattr(arbitro, "arbitro", arbitro), inicial, fita, jogador)


def _resolver(
    jogador,
    estado,
    *,
    nivel: NivelDeMotor,
    nivel_do_adversario: NivelDeMotor,
    nu_semente: int,
    maximo_de_lances: int,
    julgar,
) -> tuple[list[dict[str, Any]], int] | None:
    """Joga ate `maximo_de_lances` procurando cumprir a linha de chegada.

    Devolve `(fita, lance_chave)` quando encontra, ou `None`.

    ⚠️ **Quem procura a solucao e o SAGAZ** (RF-DES-019a): e o melhor caminho
    que existe, e o unico nivel sem `epsilon`.

    ⛔ **Mas o outro lado e o ADVERSARIO DO DIA, e nao o Sagaz.** Ate 11/09/2026
    os dois lados jogavam Sagaz, e a consequencia era que o gabarito **nao se
    reproduzia no aparelho**: o desafio publica `co_personagem` (a Pita, por
    exemplo) como adversario, e uma Pita nao responde o que um Sagaz responderia.
    Quem seguisse a solucao de referencia lance a lance veria o adversario fazer
    outra coisa no segundo lance.

    ⚠️ Foi o dono quem levantou a duvida, olhando o painel: *"e garantido que o
    adversario fara os lances que estao postos no gabarito caso o humano jogue as
    mesmas jogadas do gabarito no seu turno?"*. Antes desta correcao a resposta
    era **nao**, exceto nos dias do Magno.

    ⚠️ **Agora e sim**, e o que garante isso e a semente: ela e publicada
    (RF-DES-206) e derivada por lance, entao o mesmo nivel com a mesma semente
    escolhe o mesmo lance — mesmo nos niveis que erram de proposito.
    """
    fita: list[dict[str, Any]] = []
    atual = estado

    # ⚠️ Quem resolve o desafio e quem joga **primeiro** — a mesma definicao que
    # `julgar(..., jogador=js_posicao["vez_de"])` usa.
    vez_do_solucionador = estado.vez_de

    for numero in range(1, maximo_de_lances + 1):
        # ⚠️ Um orcamento NOVO a cada lance. `para_o_proximo_lance()` existe para
        # isto: zerar o contador a mao e o que transformaria, em silencio, um
        # teto de partida num teto de lance — ou o contrario.
        orcamento = Orcamento(
            nos_maximos=NOS_POR_LANCE_NA_GERACAO,
            segundos_maximos=SEGUNDOS_POR_LANCE_NA_GERACAO,
        ).iniciar()
        nivel_do_lance = (
            nivel if atual.vez_de == vez_do_solucionador else nivel_do_adversario
        )
        co_acao: str | None = None
        try:
            # ⚠️ **`decidir` devolve o lance E o motivo**; nem todo motor o tem
            # (o das damas nao), e por isso a escolha e por capacidade, e nao
            # por nome de jogo — um `if co_jogo == "pontinhos"` aqui teria de ser
            # lembrado no dia em que o motor das damas ganhasse o mesmo metodo.
            if hasattr(jogador, "decidir"):
                # ⚠️ **`decidir` nao recebe orcamento, e nao e esquecimento:**
                # no Pontinhos a escolha e uma inferencia da CNN, que nao tem no
                # para contar. O orcamento acima serve a busca das damas.
                decisao = jogador.decidir(
                    atual,
                    nivel_do_lance,
                    semente=semente_mod.semente_do_lance(nu_semente, numero),
                )
                lance, co_acao = decisao.lance, decisao.co_acao
            else:
                lance = jogador.escolher_lance(
                    atual,
                    nivel_do_lance,
                    limite=orcamento,
                    semente=semente_mod.semente_do_lance(nu_semente, numero),
                )
        except ValueError:
            # A partida acabou antes de o objetivo cair.
            return None

        passo: dict[str, Any] = {
            "n": numero,
            "jogador": atual.vez_de,
            "lance": lance,
        }
        if co_acao:
            # ── ⚠️ ESTE LANCE FOI UM ERRO DE PROPOSITO? ──────────────────────
            #
            # Os tres primeiros niveis jogam fora do melhor lance com uma certa
            # probabilidade (`epsilon`: 0,80 na Cacau, 0,50 na Pita, **0,14 no
            # Tex**). Quando isso acontece, o `co_acao` do lance sai como
            # `cnn_epsilon_aleatorio`.
            #
            # ⚠️ **Sem esta marca, a curadoria nao tem como saber.** O dono olhou
            # um gabarito e escreveu: *"este desafio depende do Tex fazer uma
            # jogada muito ruim e ate mesmo improvavel (...) nao entra na minha
            # cabeca como pode ter feito esta escolha"*. Entrava: era o epsilon.
            # ⛔ Um desafio cuja solucao **so** existe porque o adversario errou
            # e fragil, e agora da para ver isso no cartao.
            passo["co_acao"] = co_acao
        atual = (
            jogador.aplicar(atual, lance)
            if hasattr(jogador, "aplicar")
            else atual.com_lance(lance)
        )

        # ── ⚠️ A POSICAO DEPOIS DO LANCE, quando o jogo tem uma ──────────────
        #
        # ⚠️ **Nas damas a fita de lances NAO se le sozinha.** `21x30x23` diz o
        # que aconteceu para quem ja tem o tabuleiro na cabeca; para o painel de
        # curadoria (e para o dono) e uma linha de numeros. Guardar a FEN de cada
        # passo permite **desenhar** a solucao lance a lance, e e o que torna a
        # curadoria possivel sem jogar (pedido do dono, 11/09/2026).
        #
        # ⛔ **Quem grava a posicao e quem TEM o motor.** A imagem da API nao
        # importa `motores.damas` (ela nao instala numpy, e nao vai instalar por
        # causa de uma pagina interna), entao o painel nao pode reconstruir a
        # sequencia — e, se pudesse, seria uma **segunda implementacao das
        # regras**, que e o defeito que este projeto mais persegue.
        #
        # ⚠️ **No Pontinhos nao ha o que gravar, e nao e esquecimento:** a posicao
        # de la **e** a lista de lances (`co_formato_posicao = sequencia_lances`),
        # entao o painel monta cada quadro concatenando — sem aplicar regra
        # nenhuma. O `getattr` cobre os dois casos sem um `if` por jogo.
        fen_depois = getattr(atual, "fen", None)
        if fen_depois:
            passo["fen"] = fen_depois

        fita.append(passo)

        julgamento = julgar(fita)
        if julgamento.cumpriu:
            return fita, julgamento.nu_lance_cumpre_desafio or numero

    return None


def gerar_candidatos(
    dt_dia: date,
    *,
    parametros: Mapping[str, Any],
    quantos: int = 3,
    tipos_recentes: Sequence[str] = (),
    tentativas_por_candidato: int = 6,
    lances_de_preparo: int = 8,
    maximo_de_lances: int = 12,
) -> list[Candidato]:
    """Gera candidatos para um dia.

    Args:
        dt_dia: o dia a cobrir. E ele que decide jogo, tipo e personagem.
        parametros: os numeros do tipo (`{"caixas": 4, "turnos": 2}`).
            ⚠️ **Parametro e dado, nao codigo** (SC-027): trocar 4 por 6 nao toca
            `.arb`, nao toca codigo e nao muda `co_versao_minima`.
        quantos: quantos candidatos devolver, no maximo.
        tipos_recentes: para o rodizio nao repetir.
        tentativas_por_candidato: quantas posicoes de partida tentar por
            candidato antes de desistir.
        lances_de_preparo: o tamanho da posicao de partida. ⚠️ **Ele quer
            dizer coisas diferentes nos dois jogos**: no Pontinhos e quantos
            **tracos** a posicao de autoplay tem marcados (T049h); nas damas
            e quantos lances de variacao se joga a partir do molde. Os dois
            saem do mesmo `nu_lances_de_preparo` do editorial porque os tipos
            de um jogo nunca veem o do outro.
        maximo_de_lances: o teto da busca por solucao.

    Returns:
        Os candidatos encontrados. Pode vir menos que `quantos` — e pode vir
        vazio, e ai quem chama decide.

    ⚠️ **Todo candidato sai com gabarito**, e isso e a prova de que ele tem
    solucao. Um desafio sem solucao conhecida nao e publicado (RF-DES-196).
    """
    # ⚠️ Importado aqui, e nao no topo, para manter `motores.juiz` fora da
    # superficie deste modulo: quem le o gerador nao precisa saber julgar.
    from motores.juiz import julgar_desafio

    co_jogo = escolher_jogo(dt_dia)
    co_tipo = escolher_tipo(co_jogo, dt_dia, tipos_recentes=tipos_recentes)
    receita = receita_de(co_tipo)
    exigir_vetor(co_tipo)

    co_personagem = escolher_personagem(dt_dia)

    # ── ⚠️ O PARAMETRO PODE DEPENDER DA POSICAO (`acima_do_guloso`) ──────────
    #
    # Decisao do dono, 11/09/2026 (forma "a"): o editorial publica *"supere o
    # guloso em N"*, e o numero absoluto do enunciado sai **de cada posicao**.
    #
    # ⚠️ Por isso a chegada e o enunciado **nao podem mais ser montados uma vez
    # so, aqui fora**: eles passam a ser montados dentro do laco, depois de a
    # posicao existir. Para os tipos de parametro fixo nada muda — a conta e a
    # mesma em toda tentativa.
    #
    # ⛔ **O `montar()` da receita continua recebendo `caixas`**, e isso e de
    # proposito: mexer no contrato da receita obrigaria a refazer os vetores de
    # verificacao e a cópia do app. Quem traduz `acima_do_guloso` em `caixas` e o
    # gerador, que e quem tem a posicao.
    depende_da_posicao = editorial_mod.alvo_sai_da_posicao(parametros)

    # ⛔ **E quando o alvo sai da posicao, a recusa por erro do adversario SAI DE
    # CENA** (decisao do dono, 12/09/2026).
    #
    # ⚠️ **Nao e um afrouxamento: e que a conta ja cancela o erro.** O numero
    # publicado e `G + k`, e `G` — o que um jogador que nunca recusa uma caixa
    # faria — e medido **na mesma posicao, contra o mesmo personagem**. Se ele
    # entrega uma cadeia de graca, ela entra nos dois lados: o guloso tambem a
    # pega, `G` sobe junto, e o alvo sobe com ele. O desafio continua cobrando a
    # mesma habilidade que cobraria contra um adversario perfeito.
    #
    # ⛔ **E sem isto a variante nao existe.** Medido em 12/09/2026, lado a lado:
    # com a regra ligada, `acima_do_guloso` deu **pior dia 0** (dia descoberto na
    # fila); desligada, **pior dia 3**, o maximo. A regra continua valendo para os
    # tipos de alvo fixo (*"feche 4 caixas"*), onde o erro do personagem entrega
    # o desafio de graca e nao ha nada do outro lado da conta para compensar.
    objetivo_cancela_o_erro = depende_da_posicao

    encontrados: list[Candidato] = []

    for tentativa in range(tentativas_por_candidato * quantos):
        if len(encontrados) >= quantos:
            break

        # A semente do CANDIDATO — derivada do dia e da tentativa, para que duas
        # execucoes do job no mesmo dia gerem a mesma fila.
        nu_semente = semente_mod.sortear(
            id_desafio=f"{dt_dia.isoformat()}:{co_tipo}:{tentativa}"
        )
        sorteio = random.Random(nu_semente)

        if co_jogo == "pontinhos":
            base = _preparar_pontinhos(sorteio, lances_de_preparo)
            js_posicao = posicao_mod.do_pontinhos(list(base.lances))
            jogador = JogadorPontinhos()
            co_modalidade = None
            co_variante = "pequeno"
        else:
            co_modalidade = escolher_modalidade(co_jogo, dt_dia) or "brasileira"
            base = _preparar_damas(
                sorteio,
                lances_de_preparo,
                moldes=receita.moldes,
                co_modalidade=co_modalidade,
            )
            # ── ⛔ ESTA POSICAO SE RESOLVE NO PRIMEIRO TOQUE? ────────────
            #
            # ⚠️ **A pergunta e sobre o que VAI AO AR, e nao sobre o molde.** Os
            # moldes ja foram peneirados (T049g), mas o que se publica e o molde
            # **mais um lance de variacao** — e um lance basta para armar uma
            # cadeia de captura que o molde nao tinha.
            #
            # ⛔ Foi assim que `72542794` foi publicado em 11/09/2026, ja com os
            # moldes limpos: `B:W25,26,29:B16,17,18,21`, solucao `21x30x23`,
            # **um lance**. E a regua nao acusa — ela mediu tres mascotes
            # resolvendo 20 de 20, que e o que se espera de um desafio banal.
            #
            # ⚠️ **E a variacao troca o lado**: o molde tem as brancas a jogar, a
            # posicao publicada tem as pretas, e e com elas que a pessoa resolve.
            # Por isso `objetivo_no_primeiro_lance` pergunta por **quem esta a
            # jogar** na FEN que recebe, e nao por uma cor fixa.
            #
            # ⛔ **Descartar aqui nao deixa o dia descoberto**: o laco continua, e
            # ha `tentativas_por_candidato * quantos` posicoes para tentar.
            de_cara = objetivo_no_primeiro_lance(base.fen, co_tipo, co_modalidade)
            if de_cara is not None:
                print(
                    f"⚠️ [job] {dt_dia}: posicao descartada — o objetivo cai no "
                    f"lance 1 ({co_modalidade}: {de_cara}). FEN {base.fen}"
                )
                continue

            js_posicao = posicao_mod.das_damas(base.fen, co_modalidade=co_modalidade)
            # ⛔ **O motor PRECISA nascer com a modalidade do dia.** `MotorDamas()`
            # tem `brasileira` por padrao, e um esquecimento aqui faria o gabarito
            # ser buscado por um regulamento enquanto o desafio publicado diz
            # outro — ⚠️ **sem erro nenhum**: os dois lados seriam internamente
            # coerentes, e a solucao so seria recusada no aparelho de quem
            # jogasse. E a mesma classe do defeito do `uid` do Firebase.
            jogador = MotorDamas(co_modalidade)
            # ⚠️ **`co_variante` das damas E a modalidade**, e nao um rotulo fixo.
            # O `data-model.md` diz que esta coluna usa *"o mesmo vocabulario de
            # `partida.tb001`"*, e la o aplicativo grava exatamente isso
            # (`coVariante: widget.config.modalidade`); a migracao `0012` afirma
            # o mesmo com todas as letras: *"a modalidade JA esta gravada na
            # partida (`co_variante`)"*.
            #
            # ⛔ Ate 10/09/2026 aqui havia `"brasileiras"` fixo. Enquanto so
            # existia um regulamento, a mentira era invisivel; no instante em que
            # a modalidade passou a rodiziar, o desafio saiu dizendo
            # `variante: brasileiras` ao lado de `modalidade: casa` — e um `JOIN`
            # com o log de partidas nunca casaria.
            co_variante = co_modalidade

        # ⚠️ **ONDE e COMO se joga entram no enunciado, e por FORA da receita.**
        # Decisao do dono, 10/09/2026: *"precisamos colocar a modalidade no campo
        # (…) nos pontinhos hoje temos apenas 4x3, mas no futuro teremos outros"*.
        #
        # ⛔ **Por fora, e nao dentro de `valores_da_frase`**, e a razao e
        # estrutural: modalidade e variante nao sao conhecimento do TIPO — sao
        # fatos do candidato. Se cada receita tivesse de lembrar de inclui-las, a
        # primeira que esquecesse publicaria uma frase sem dizer por quais regras
        # se joga, e ⚠️ **nada acusaria** — a frase sairia bem formada, so que
        # incompleta.
        #
        # `modalidade` so entra quando existe: o Pontinhos nao tem uma, e uma
        # chave nula num espaco de frase renderiza "null" na tela de alguem.
        # ── A chegada e o enunciado, agora por POSICAO ───────────────────────
        #
        # ⚠️ **`G` e medido contra o PERSONAGEM DO DIA**, e nao contra o Magno: o
        # adversario publicado pode ser a Cacau, que erra de proposito em 80% dos
        # lances, e um numero medido contra outro adversario descreveria uma
        # partida diferente da que vai ao ar.
        if depende_da_posicao:
            guloso = guloso_mod.caixas_do_guloso(
                jogador,
                getattr(jogador, "arbitro", jogador),
                base,
                js_posicao["vez_de"],
                nivel=NivelDeMotor.SAGAZ,
                nivel_do_adversario=NIVEL_POR_PERSONAGEM[co_personagem],
                semente_do_lance=semente_mod.semente_do_lance,
                nu_semente=nu_semente,
            )
            parametros_daqui = editorial_mod.parametros_efetivos(
                parametros, guloso=guloso
            )
        else:
            parametros_daqui = dict(parametros)

        js_chegada = receita.montar(parametros_daqui)
        js_objetivo = {
            **receita.valores_da_frase(parametros_daqui, co_personagem),
            "variante": co_variante,
        }
        if co_modalidade:
            js_objetivo["modalidade"] = co_modalidade

        def julgar(fita: list[dict[str, Any]]):
            return julgar_desafio(
                co_jogo=co_jogo,
                js_posicao_inicial=js_posicao,
                js_chegada=js_chegada,
                fita=fita,
                jogador=js_posicao["vez_de"],
                co_modalidade=co_modalidade or "brasileira",
            )

        achado = _resolver(
            jogador,
            base,
            nivel=NivelDeMotor.SAGAZ,
            nivel_do_adversario=NIVEL_POR_PERSONAGEM[co_personagem],
            nu_semente=nu_semente,
            maximo_de_lances=maximo_de_lances,
            julgar=julgar,
        )
        if achado is None:
            continue

        fita, lance_chave = achado

        # ── ⛔ O DESAFIO NAO PODE DEPENDER DE O ADVERSARIO JOGAR MAL ──────────
        #
        # Regra do dono, 11/09/2026: *"o problema nao e o adversario abrir a
        # cadeia, o problema e quando ele abre a cadeia sendo que ha diversos
        # outros tracos que nem entregariam caixa de graca"*.
        #
        # ⚠️ **Isto e diferente do `co_acao = cnn_epsilon_aleatorio`**, que marca
        # o erro **declarado** (o sorteio do nivel). Aqui o adversario jogou o que
        # considerou o melhor lance e ainda assim entregou a cadeia tendo saida —
        # foi o caso do `V_1_4` do desafio `d5af2ae1`, em que `V_7_0` e `H_8_1`
        # entregavam zero e a rede escolheu um que entregava seis.
        #
        # ⛔ **Um desafio assim some no dia em que o motor melhorar**, e ate la
        # ensina a esperar um erro que nao vem.
        # ⛔ **Descartar aqui nao deixa o dia descoberto**: o laco continua, e ha
        # `tentativas_por_candidato * quantos` posicoes para tentar — o mesmo
        # raciocinio da recusa por objetivo no lance 1, logo acima.
        recusa = (
            None
            if objetivo_cancela_o_erro
            else motivo_de_erro_do_adversario(
                co_jogo, jogador, base, fita, js_posicao["vez_de"]
            )
        )
        if recusa is not None:
            print(
                f"⚠️ [job] {dt_dia}: candidato descartado — o desafio depende de "
                f"um erro do adversario: {recusa}"
            )
            continue

        js_solucao = gabarito_mod.montar(fita, lance_chave=lance_chave)

        encontrados.append(
            Candidato(
                co_jogo=co_jogo,
                co_variante=co_variante,
                co_modalidade=co_modalidade,
                co_formato_posicao=posicao_mod.formato_do_jogo(co_jogo),
                js_posicao_inicial=js_posicao,
                receita=receita,
                js_chegada=js_chegada,
                js_objetivo=js_objetivo,
                parametros=parametros_daqui,
                co_personagem=co_personagem,
                nu_semente=nu_semente,
                js_solucao=js_solucao,
                nu_lances_solucao=gabarito_mod.nu_lances_solucao(js_solucao),
                de_diagnostico=[f"tentativa {tentativa}"],
                estado_inicial=base,
            )
        )

    return encontrados


def _preparar_damas(
    sorteio: random.Random,
    lances_de_preparo: int,
    *,
    moldes: Sequence[str] = (),
    co_modalidade: str = "brasileira",
) -> EstadoDamas:
    """A posicao de partida das damas: de um MOLDE, ou da abertura.

    ⚠️ **Com molde, o preparo e curto de proposito.** O molde ja e a posicao
    interessante; os poucos lances aleatorios existem so para variar, e cada lance
    a mais aumenta a chance de destruir o objetivo que o molde preparava.

    ⚠️ **Sem molde, joga-se a abertura inteira** — e isso quase nunca produz um
    final. Medido em 09/09/2026: gerar *"coroe uma dama em 6 lances"* a partir de
    40 lances aleatorios deu **zero** candidatos em 35 segundos. E por isso que os
    tipos de damas tem molde, e nao por gosto.
    """
    # ⚠️ O preparo joga lances legais, e "legal" depende do regulamento — uma
    # variacao jogada pelas regras erradas produziria uma posicao que o desafio
    # publicado considera impossivel de alcancar.
    motor = MotorDamas(co_modalidade)

    if moldes:
        estado = EstadoDamas(
            co_modalidade=co_modalidade, fen_inicial=sorteio.choice(list(moldes))
        )
        # ── ⚠️ UM LANCE DE VARIACAO, E O ESPELHO CUIDA DO LADO ───────────
        #
        # ⛔ **Esta linha ja foi `2`, por algumas horas de 11/09/2026, e foi um
        # erro caro.** O raciocinio era certo pela metade: o molde tem as brancas
        # a jogar, cada lance troca o lado, e com um numero impar deles quem
        # resolve o desafio acaba sendo as pretas — contra a regra canonica do
        # projeto (*"o humano e o Jogador 1, azul"*).
        #
        # ⛔ **So que dois lances CONSOMEM a distancia ate o objetivo.** Os moldes
        # foram cacados como posicoes a ~3 lances do alvo; gastar dois em
        # variacao deixa o desafio a um lance. O resultado, medido na execucao
        # seguinte: `damas_capturar_multipla` descartou nove posicoes por
        # *"objetivo no lance 1"* e **2026-09-11 ficou sem desafio**; e os tres
        # desafios de damas que sairam tinham `nu_lances_solucao = 3`, sobre os
        # quais o dono escreveu *"o usuario entra pra resolver um desafio e nao
        # joga praticamente nada"*.
        #
        # ✅ **O espelho resolve as duas coisas de uma vez** (ver
        # `job/espelho_de_damas.py`): varia-se **um** lance — que preserva a
        # distancia — e gira-se o tabuleiro 180 graus trocando as cores, o que
        # devolve a mesma tarefa com as **brancas** a jogar.
        variacao = min(1, max(0, lances_de_preparo // 8))
    else:
        estado = estado_inicial(co_modalidade)
        variacao = lances_de_preparo

    for _ in range(variacao):
        legais = motor.lances_legais(estado)
        if not legais:
            break
        estado = motor.aplicar(estado, sorteio.choice(legais))

    # ── ⚠️ O ESPELHO: quem resolve o desafio e sempre o JOGADOR 1 ───────────
    #
    # Depois de um numero impar de lances, quem joga sao as pretas — e a pessoa
    # nao pode ser o jogador 2 (`CLAUDE.md`: *"o humano e o Jogador 1, azul"*).
    # ⚠️ Espelhar e a **mesma tarefa vista do outro lado**, e nao uma posicao
    # nova: as damas sao simetricas sob rotacao de 180 graus com troca de cor, e
    # ha cadeado comparando os lances legais dos dois lados nas quatro
    # modalidades.
    #
    # ⛔ **Nao se resolve isto variando um numero par de lances** — ja foi
    # tentado, no mesmo dia: dois lances consomem a distancia ate o objetivo e
    # deixam o desafio banal (ou impossivel de gerar).
    return EstadoDamas(
        co_modalidade=co_modalidade, fen_inicial=com_as_brancas_a_jogar(estado.fen)
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. A bancada: com que pecas se MEDE um candidato
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Os tres passos seguintes precisam do mesmo ferramental que a geracao
# usou**, e montá-lo de novo la fora seria a segunda fonte da verdade: a regua
# mediria com um jogador e o candidato teria sido achado com outro, e a taxa
# "14 de 20" passaria a descrever um adversario que ninguem enfrenta.
#
# ⛔ E ha um detalhe que so quem escreveu o gerador sabe: **o jogador e o arbitro
# nem sempre sao o mesmo objeto**. Nas damas, `MotorDamas` faz as duas coisas; no
# Pontinhos, quem escolhe lance e `JogadorPontinhos` (que nao tem `aplicar` nem
# `veredito`) e quem arbitra e `MotorPontinhos`. Deixar isso para o chamador
# adivinhar seria plantar um `AttributeError` no meio da medicao.


@dataclass(frozen=True, slots=True)
class Bancada:
    """As pecas para medir um candidato, ja montadas para o jogo dele.

    Atributos:
        jogador: quem escolhe lance (`escolher_lance`).
        arbitro: quem diz se a partida acabou (`veredito`) e aplica lance.
        estado_inicial: a posicao de partida do candidato.
        julgar: `(fita) -> Julgamento`, com a linha de chegada daquele desafio.
    """

    jogador: Any
    arbitro: Any
    estado_inicial: Any
    julgar: Any


def bancada(candidato: Candidato) -> Bancada:
    """Monta a bancada de medicao daquele candidato.

    Raises:
        SemCandidato: quando o candidato veio sem `estado_inicial` — o que so
            acontece se alguem o construiu a mao. ⚠️ **Falhar aqui e melhor que
            reconstruir a posicao**: uma reconstrucao silenciosa mediria a partir
            de um tabuleiro que pode nao ser o que foi gerado.
    """
    from motores.juiz import julgar_desafio
    from motores.pontinhos.motor_pontinhos import MotorPontinhos

    if candidato.estado_inicial is None:
        raise SemCandidato(
            "o candidato nao carrega `estado_inicial`, e sem ele nao ha de onde "
            "medir a regua nem provar o termino. ⛔ Reconstruir a posicao aqui "
            "seria uma segunda travessia do mesmo caminho."
        )

    if candidato.co_jogo == "pontinhos":
        jogador: Any = JogadorPontinhos()
        arbitro: Any = MotorPontinhos()
    else:
        # Nas damas o mesmo objeto joga e arbitra — e isso e do motor, nao uma
        # escolha daqui.
        # ⛔ **Com a modalidade do candidato.** Medir a regua com outro
        # regulamento daria uma taxa que descreve um jogo que ninguem vai jogar.
        jogador = arbitro = MotorDamas(candidato.co_modalidade or "brasileira")

    def julgar(fita: list[dict[str, Any]]):
        """Julga a fita contra a linha de chegada **deste** candidato."""
        return julgar_desafio(
            co_jogo=candidato.co_jogo,
            js_posicao_inicial=candidato.js_posicao_inicial,
            js_chegada=candidato.js_chegada,
            fita=fita,
            jogador=candidato.js_posicao_inicial["vez_de"],
            co_modalidade=candidato.co_modalidade or "brasileira",
        )

    return Bancada(
        jogador=jogador,
        arbitro=arbitro,
        estado_inicial=candidato.estado_inicial,
        julgar=julgar,
    )


def versao_do_motor_de(co_jogo: str) -> str:
    """O `co_versao_motor` daquele jogo, para o carimbo da medicao.

    ⚠️ **Deriva dos hashes do espelho do laboratorio**, e nao de um numero escrito
    a mao — a mesma disciplina de `co_versao_perfil`. Trocar a `.tflite` e
    esquecer de subir a versao deixaria medicoes novas indistinguiveis das velhas
    no banco, e *"a Pita resolveu 14 de 20"* perderia a regua.

    Raises:
        SemCandidato: para jogo fora do rodizio. ⚠️ **Falhar aqui e melhor que
        devolver um texto generico**: um carimbo `desconhecido` gravado passaria
        pelo `VARCHAR(40)` e so seria notado meses depois, ao tentar explicar uma
        medicao.
    """
    from motores.damas.motor_damas import versao_do_motor as versao_das_damas
    from motores.pontinhos.motor_pontinhos import (
        versao_do_motor as versao_do_pontinhos,
    )

    if co_jogo == "pontinhos":
        return versao_do_pontinhos()
    if co_jogo == "damas":
        return versao_das_damas()
    raise SemCandidato(
        f"o jogo {co_jogo!r} nao esta no rodizio e nao tem versao de motor a "
        f"carimbar. Os do rodizio sao {JOGOS_DO_RODIZIO}."
    )
