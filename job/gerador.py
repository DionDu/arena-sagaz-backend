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
from motores.pontinhos.motor_pontinhos import EstadoPontinhos
from motores.pontinhos.politica import JogadorPontinhos

from . import gabarito as gabarito_mod
from . import posicao_inicial as posicao_mod
from . import semente as semente_mod
from .tipos_de_desafio import Receita, receita_de, tipos_do_jogo

RAIZ = Path(__file__).resolve().parents[1]
VETORES = RAIZ / "contratos" / "vetores-verificacao-desafio.json"

#: Os jogos do rodizio, em ordem estavel.
#:
#: ⚠️ A velha **nao esta aqui**, e e decisao: ela nao tem medidor no juiz nem
#: vetores. Jogo entra no rodizio quando tem os dois, nunca antes.
JOGOS_DO_RODIZIO = ("pontinhos", "damas")

#: Os quatro mascotes, na ordem da escada de dificuldade.
PERSONAGENS = ("cacau", "pita", "tex", "magno")

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
    de_diagnostico: list[str] = field(default_factory=list, compare=False)


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
    return frescos[dias % len(frescos)]


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
    """Joga alguns lances aleatorios para sair do tabuleiro vazio.

    ⚠️ **Aleatorio, e nao "a melhor jogada"**: a posicao inicial de um desafio
    precisa ser *interessante*, e uma partida bem jogada dos dois lados converge
    para posicoes parecidas. O acaso e o que da variedade a fila.

    ⚠️ **E ele evita fechar caixa de proposito**: uma preparacao que ja fechou
    caixas entrega placar inicial diferente de zero, e a frase do desafio teria
    de explicar de onde veio aquele placar.
    """
    estado = EstadoPontinhos()
    for _ in range(lances_de_preparo):
        opcoes = [
            lance
            for lance in estado.tabuleiro.tracos_disponiveis()
            if _nao_fecha_caixa(estado, lance)
        ]
        if not opcoes:
            break
        estado = estado.com_lance(sorteio.choice(opcoes))
    return estado


def _nao_fecha_caixa(estado: EstadoPontinhos, lance: str) -> bool:
    """O traco fecharia alguma caixa?

    Pergunta ao motor aplicando o lance num estado descartavel: a regra de
    fechamento mora la, e reimplementa-la aqui criaria a segunda fonte da verdade
    que este projeto passa o tempo todo evitando.
    """
    antes = estado.placar
    depois = estado.com_lance(lance).placar
    return antes == depois


def _resolver(
    jogador,
    estado,
    *,
    nivel: NivelDeMotor,
    nu_semente: int,
    maximo_de_lances: int,
    julgar,
) -> tuple[list[dict[str, Any]], int] | None:
    """Joga ate `maximo_de_lances` procurando cumprir a linha de chegada.

    Devolve `(fita, lance_chave)` quando encontra, ou `None`.

    ⚠️ **Quem joga e o SAGAZ** (RF-DES-019a): e o unico nivel reproduzivel — os
    outros tres tem `epsilon` e jogam errado de proposito, com sorteio. Um
    gabarito gerado pela Cacau seria diferente a cada execucao, e "a solucao de
    referencia" deixaria de ser referencia.
    """
    fita: list[dict[str, Any]] = []
    atual = estado

    for numero in range(1, maximo_de_lances + 1):
        # ⚠️ Um orcamento NOVO a cada lance. `para_o_proximo_lance()` existe para
        # isto: zerar o contador a mao e o que transformaria, em silencio, um
        # teto de partida num teto de lance — ou o contrario.
        orcamento = Orcamento(
            nos_maximos=NOS_POR_LANCE_NA_GERACAO,
            segundos_maximos=SEGUNDOS_POR_LANCE_NA_GERACAO,
        ).iniciar()
        try:
            lance = jogador.escolher_lance(
                atual,
                nivel,
                limite=orcamento,
                semente=semente_mod.semente_do_lance(nu_semente, numero),
            )
        except ValueError:
            # A partida acabou antes de o objetivo cair.
            return None

        fita.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = jogador.aplicar(atual, lance) if hasattr(jogador, "aplicar") else atual.com_lance(lance)

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
        lances_de_preparo: quantos lances jogar para sair da posicao inicial.
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
    js_chegada = receita.montar(parametros)
    js_objetivo = receita.valores_da_frase(parametros, co_personagem)

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
            base = _preparar_damas(
                sorteio, lances_de_preparo, moldes=receita.moldes
            )
            js_posicao = posicao_mod.das_damas(base.fen)
            jogador = MotorDamas()
            co_modalidade = "brasileira"
            co_variante = "brasileiras"

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
            nu_semente=nu_semente,
            maximo_de_lances=maximo_de_lances,
            julgar=julgar,
        )
        if achado is None:
            continue

        fita, lance_chave = achado
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
                co_personagem=co_personagem,
                nu_semente=nu_semente,
                js_solucao=js_solucao,
                nu_lances_solucao=gabarito_mod.nu_lances_solucao(js_solucao),
                de_diagnostico=[f"tentativa {tentativa}"],
            )
        )

    return encontrados


def _preparar_damas(
    sorteio: random.Random,
    lances_de_preparo: int,
    *,
    moldes: Sequence[str] = (),
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
    motor = MotorDamas()

    if moldes:
        estado = EstadoDamas(
            co_modalidade="brasileira", fen_inicial=sorteio.choice(list(moldes))
        )
        # No maximo dois lances de variacao — e so quando ainda ha o que jogar.
        variacao = min(2, max(0, lances_de_preparo // 8))
    else:
        estado = estado_inicial()
        variacao = lances_de_preparo

    for _ in range(variacao):
        legais = motor.lances_legais(estado)
        if not legais:
            break
        estado = motor.aplicar(estado, sorteio.choice(legais))
    return estado
