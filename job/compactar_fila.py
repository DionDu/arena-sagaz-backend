"""COMPACTAR A FILA: o desafio aprovado que esta longe desce para o buraco perto.

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 16/09/2026 o dono descreveu o sintoma depois de curar a fila no painel:

> *"os desafios do painel de curadoria saem carimbados com uma data que entrarao
> no App. Se eu rejeitar o desafio de amanha e depois de amanha, nenhum outro
> desafio ja aprovado passa a ocupar o 'buraco' que ficou. Seria interessante que
> os desafios aprovados preenchessem buracos das datas mais recentes mantendo a
> variabilidade, sem repetir desafios muito semelhantes em dias consecutivos."*

⚠️ **O job JA regenera o buraco** — quando ele acorda, o dia descartado volta a
ser um dia a cobrir, e ele gera outro candidato ali. ⛔ **Mas ele acorda uma vez
por dia, de madrugada.** Se o dono reprova o desafio de amanha as dez da noite, o
buraco fica aberto ate a proxima execucao — e nesse meio-tempo ha um desafio
**ja aprovado** parado em D+5, que resolveria o problema agora.

⚠️ **E compactar e mais barato que gerar.** Cada dia gerado custa minutos de
Railway (medido em 16/09: 1.024 s num unico `damas_sobreviver`); mover uma linha
custa um `UPDATE`. Puxar o de D+5 para D+1 troca uma geracao cara por uma
gravacao barata, e o buraco que sobra em D+5 e o menos urgente que existe.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MODULO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao move o que nao esta aprovado.** Um `candidato` pode ser reprovado amanha;
move-lo para a frente da fila so adianta o problema. ⚠️ E um `descartado` nao e
um desafio, e um buraco com linha.

⛔ **Nao move para a FRENTE.** Um desafio so anda em direcao a hoje. Empurrar um
dia para depois adiaria conteudo ja aprovado sem ninguem pedir.

⛔ **Nao toca em dia que ja passou.** Desafio publicado e imutavel (*"um desafio e
publicado uma vez so"*), e reescrever a data de um dia vivido apagaria a historia
de quem o resolveu.

⛔ **Nao decide sozinho o que e "semelhante".** Quem decide e
`job/vizinhanca.py`, a mesma regra que a geracao usa.

⚠️ **E a regra MUDOU em 02/10/2026.** Ate ali semelhante era so **o mesmo tipo**,
e este cabecalho dizia que proibir o mesmo jogo *"tornaria quase toda
compactacao impossivel"*. Era verdade quando so o que o dono aprovava a mao
podia descer. ⚠️ **Com os desafios nascendo pre-aprovados** (decisao do dono,
`DECISOES-do-dono.md` §8zk do app), a fila inteira e doadora, e o dono pediu
explicitamente: *"sempre precisa garantir a alternancia de jogos/modalidades/
personagens do desafio de um dia para o outro"*. Agora conflitam, entre dias
consecutivos: o mesmo **jogo**, o mesmo **personagem**, a mesma **modalidade**
e o mesmo **tipo**.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional, Sequence

from .vizinhanca import Ocupante, Vizinhanca


@dataclass(frozen=True)
class LinhaDaFila:
    """Um dia da fila, como o banco o conhece.

    Atributos:
        dt_dia: a data em que este desafio entraria no aplicativo.
        id_desafio_dia: a chave da linha de `desafio_dia.tb001_desafio_dia`.
        co_tipo_desafio: o tipo, que e o insumo da variabilidade.
        co_curadoria: `aprovado` · `candidato` · `descartado`.
        co_jogo, co_modalidade, co_personagem: o resto do que a alternancia
            compara (02/10/2026). ⚠️ `None` desliga **aquela** comparacao, e nao
            a regra inteira — ver `vizinhanca.conflita`.
    """

    dt_dia: date
    id_desafio_dia: object
    co_tipo_desafio: str
    co_curadoria: str
    co_jogo: Optional[str] = None
    co_modalidade: Optional[str] = None
    co_personagem: Optional[str] = None

    def ocupante(self) -> Ocupante:
        """O desafio desta linha, no vocabulario da regra de vizinhanca."""
        return Ocupante(
            co_jogo=self.co_jogo,
            co_personagem=self.co_personagem,
            co_modalidade=self.co_modalidade,
            co_tipo_desafio=self.co_tipo_desafio,
        )


@dataclass(frozen=True)
class Mudanca:
    """Um desafio que desce de `dt_de` para `dt_para`."""

    id_desafio_dia: object
    co_tipo_desafio: str
    dt_de: date
    dt_para: date

    def __str__(self) -> str:
        return f"{self.co_tipo_desafio} {self.dt_de} → {self.dt_para}"


#: Que estados de curadoria contam como "o dia esta resolvido".
#:
#: ⚠️ **`candidato` conta, e isso e deliberado.** Um dia com candidato nao e um
#: buraco: ele tem conteudo esperando o dono decidir. ⛔ Compactar por cima dele
#: apagaria uma decisao que ainda nao foi tomada.
OCUPAM_O_DIA = frozenset({"aprovado", "candidato"})

#: Que estados podem ser MOVIDOS para preencher um buraco.
#:
#: ⛔ **So o aprovado.** Ver o cabecalho: mover um candidato adianta o problema.
PODEM_DESCER = frozenset({"aprovado"})


def _vizinhos(dia: date, por_dia: dict[date, Ocupante]) -> Vizinhanca:
    """Os desafios do dia anterior e do seguinte, quando existem."""
    um_dia = timedelta(days=1)
    return Vizinhanca(
        anterior=por_dia.get(dia - um_dia), seguinte=por_dia.get(dia + um_dia)
    )


def remanejar(
    fila: Sequence[LinhaDaFila],
    *,
    dias_do_plano: Iterable[date],
    dt_hoje: date,
) -> list[Mudanca]:
    """Que desafios aprovados devem descer, e para onde.

    Args:
        fila: as linhas que existem hoje em `desafio_dia`, em qualquer ordem.
        dias_do_plano: os dias que esta execucao cobre (de hoje em diante).
        dt_hoje: o dia da execucao. ⛔ Nada anterior a ele e tocado.

    Returns:
        As mudancas, na ordem em que devem ser aplicadas. Lista vazia quando nao
        ha buraco ou nao ha doador elegivel.

    ⚠️ **O doador vem sempre do dia MAIS DISTANTE**, e nao do mais proximo. As
    duas escolhas preenchem o buraco; a diferenca esta em **onde fica o buraco
    novo**. Puxando do fim da fila, ele sobra no dia menos urgente que existe — e
    a proxima execucao do job tem uma noite inteira para cobri-lo.

    ⚠️ **A vizinhanca e recalculada a cada movimento**, e nao uma vez no inicio.
    Uma decisao muda os vizinhos da seguinte: sem isso, duas mudancas na mesma
    execucao poderiam colocar dois `damas_coroar` lado a lado, que e exatamente o
    que o criterio proibe.
    """
    dias = sorted(set(dias_do_plano))
    if not dias:
        return []

    # ⛔ Nada antes de hoje entra na conta, nem como buraco nem como doador.
    ocupados: dict[date, Ocupante] = {
        linha.dt_dia: linha.ocupante()
        for linha in fila
        if linha.co_curadoria in OCUPAM_O_DIA
    }
    doadores: dict[date, LinhaDaFila] = {
        linha.dt_dia: linha
        for linha in fila
        if linha.co_curadoria in PODEM_DESCER and linha.dt_dia > dt_hoje
    }

    buracos = [dia for dia in dias if dia >= dt_hoje and dia not in ocupados]

    mudancas: list[Mudanca] = []
    for buraco in buracos:
        # Do dia mais distante para o mais proximo, e sempre depois do buraco.
        for dt_doador in sorted(doadores, reverse=True):
            if dt_doador <= buraco:
                # ⚠️ Esgotou: os doadores restantes estao todos ANTES do buraco,
                # e mover para a frente e proibido. Os buracos seguintes sao
                # ainda mais tarde, entao nada mais sera encontrado.
                break
            doador = doadores[dt_doador]
            # ⚠️ O doador sai do lugar dele ANTES de ser comparado: quando o
            # buraco e vizinho do proprio doador (D+1 vazio, doador em D+2), ele
            # conflitaria consigo mesmo e nunca desceria um dia.
            sem_o_doador = {d: o for d, o in ocupados.items() if d != dt_doador}
            if not _vizinhos(buraco, sem_o_doador).aceita(doador.ocupante()):
                # Parecido demais com um vizinho do buraco (jogo, personagem,
                # modalidade ou tipo) — tenta o proximo doador.
                continue

            mudancas.append(
                Mudanca(
                    id_desafio_dia=doador.id_desafio_dia,
                    co_tipo_desafio=doador.co_tipo_desafio,
                    dt_de=dt_doador,
                    dt_para=buraco,
                )
            )
            # ⚠️ O estado anda junto: o buraco fecha e o dia do doador abre.
            ocupados[buraco] = doador.ocupante()
            del ocupados[dt_doador]
            del doadores[dt_doador]
            break

    return mudancas


def resumo(mudancas: Sequence[Mudanca]) -> str:
    """As mudancas em uma linha, para o log."""
    if not mudancas:
        return "nenhuma"
    return " · ".join(str(m) for m in mudancas)
