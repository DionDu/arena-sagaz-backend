"""Ponto de entrada do job em batch — o que `python -m job` executa (T049c).

═══════════════════════════════════════════════════════════════════════════
A SEQUENCIA, E POR QUE ELA E ESTA
═══════════════════════════════════════════════════════════════════════════

    1. expirar partidas paradas  →  fecha o que o aplicativo nunca fechou (T046)
    2. gravar o perfil vigente   →  ⛔ **antes de tudo**: a `fk001_perfil` recusa
                                    o primeiro desafio sem ele
    3. descobrir os dias a cobrir → a folga de 7 a 30 dias (T038)
    4. por dia descoberto:
         gerar N candidatos  →  provar que a partida termina  →  medir a
         regua  →  escolher o que cai na BANDA  →  gravar
         (e, se nao der para gerar, **reprisar**)
    5. auditar as resolucoes pendentes (T043a)

⚠️ **A auditoria vem por ultimo de proposito.** Ela e a rotina mais cara e a
unica que pode ser adiada sem custo: uma resolucao auditada amanha continua
valendo hoje (⛔ vale o aplicativo — RF-DES-032). Gerar, nao: um dia descoberto
e um dia sem produto.

═══════════════════════════════════════════════════════════════════════════
⚠️ A CONVENCAO DE SAIDA — E POR QUE "TERMINOU BEM" NAO BASTA
═══════════════════════════════════════════════════════════════════════════

    0  →  fez
    1  →  fez, e algo QUEBROU (dia descoberto, resolucao divergente)
    2  →  nem comecou (sem `DATABASE_URL`, banco fora, perfil nao gravou)

⛔ **Calibracao fora da banda NAO e quebra**, e nao sai com 1 — ela e observacao
para a curadoria, e nada vai ao ar sem o dono aprovar. Medido em 10/09/2026:
seis dos sete dias de uma execucao saudavel ficavam fora da banda, e o painel
ficaria vermelho todo dia. Sinal que dispara sempre e sinal que ninguem le.

⛔ **Um job que "termina bem" sem gerar nada e indistinguivel, no painel do
Railway, de um job que funcionou** — e a fila de desafios secaria em silencio ate
alguem abrir o aplicativo e ver o dia vazio. E por isso que **dia descoberto sai
com 1**, mesmo que tudo o mais tenha corrido.

⚠️ **`2` e reservado ao que aconteceu ANTES do trabalho.** Um estouro no meio do
quarto dia, com tres ja publicados, nao e "nem comecou": ele vira dia descoberto,
o log diz qual foi o erro, e o codigo e 1. Confundir os dois faria alguem
reiniciar o job achando que nada tinha sido gravado.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nao aprova nada.** Tudo o que ele grava nasce `candidato` (RF-DES-012a);
quem aprova e o dono, no painel de curadoria.
⛔ **Nao fala HTTP.** Sem porta, sem rota, sem `healthcheckPath` — a conversa com
a API acontece pelo Postgres (RF-DES-011a).
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Optional, Sequence

from . import alvo_observado as alvo_mod
from . import auditoria as auditoria_mod
from . import editorial as editorial_mod
from . import estado_terminal as terminal_mod
from . import expirar_partidas as expiracao_mod
from . import gerador as gerador_mod
from . import gravacao as gravacao_mod
from . import medidas_de_saida as medidas_mod
from . import perfil as perfil_mod
from . import posicao_inicial as posicao_mod
from . import regua as regua_mod
from . import reprise as reprise_mod
from .banco import BancoNaoConfigurado, abrir_sessao
from .repositorio import RepositorioDoJob

#: As tres saidas possiveis do processo.
CODIGO_FEZ = 0
CODIGO_DIVERGIU = 1
CODIGO_NEM_COMECOU = 2

#: O teto de lances, quando o tipo nao pede outro.
#:
#: ⚠️ **Desde 10/09/2026 ele e POR TIPO**, e mora no editorial: os dois tipos de
#: Pontinhos falharam na primeira execucao real por motivos opostos, e um numero
#: global nao servia para os dois. Ver o comentario de
#: `editorial.MAXIMO_DE_LANCES_PADRAO`.
MAXIMO_DE_LANCES = editorial_mod.MAXIMO_DE_LANCES_PADRAO

#: Quanto tempo se supoe que uma pessoa leva por lance, em milissegundos.
#:
#: ⚠️ **Nao e chute: e o numero que reproduz o exemplo do `data-model.md`.** La, o
#: desafio de `nu_lances_solucao = 5` tem `nu_tempo_piso_ms = 30000` e
#: `nu_tempo_teto_ms = 180000` — e 30000/5 = 6000, com o teto saindo da folga de
#: 6x que `medidas_de_saida.regua_de_tempo` aplica. Derivar daqui mantem a regua
#: de tempo igual a que o dono pre-validou.
#:
#: ⚠️ **O piso e o tempo do GABARITO jogado direto**, e nao o tempo esperado de
#: quem resolve: ninguem resolve mais rapido que a propria solucao.
MILISSEGUNDOS_POR_LANCE_DO_GABARITO = 6_000

#: Quantos dias para tras e para frente o rodizio olha.
#:
#: ⚠️ **Os dois lados**, e o lado de frente e o que se esquece: a fila cobre ate
#: 30 dias a frente, e ignorar o que ja esta agendado publicaria o mesmo tipo duas
#: vezes na mesma semana.
JANELA_DO_RODIZIO_EM_DIAS = 30

#: Quantos candidatos gerar por dia, antes de escolher.
#:
#: ⚠️ **Um so nao serve, e a banda da regua e a razao.** Com um unico candidato a
#: medicao nao tem o que decidir: ou se publica o que veio, ou se deixa o dia
#: descoberto. Tres da chance de o proximo cair na banda, e o custo so aparece
#: quando o primeiro nao cai — a medicao para no primeiro que encaixa.
CANDIDATOS_POR_DIA = 3

#: Quantos dias de historico alimentam o alvo movel da regua.
#:
#: ⚠️ **Trinta dias, e nao "tudo"**: a dificuldade percebida muda com quem esta
#: jogando, e uma media de um ano atras descreveria outra base de jogadores.
JANELA_DA_TAXA_OBSERVADA_EM_DIAS = 30


# ═══════════════════════════════════════════════════════════════════════════
# O relatorio da execucao
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Relatorio:
    """O que esta execucao fez — e o que ela **nao** conseguiu fazer.

    ⚠️ **Os numeros sao separados de proposito.** *"Cobri 7 dias"* nao distingue
    "a fila ja estava cheia" de "gerei sete desafios", e as duas situacoes pedem
    reacoes opostas de quem le o log.
    """

    perfis_novos: int = 0
    partidas_expiradas: int = 0
    dias_no_plano: int = 0
    ja_publicados: int = 0
    gerados: int = 0
    reprisados: int = 0
    descartados: list[str] = field(default_factory=list)
    fora_da_banda: list[str] = field(default_factory=list)
    #: Candidatos recusados por **ja terem sido publicados** (T049i).
    #:
    #: ⛔ **A recusa nao pode sair calada.** Sem esta contagem, o dia em que os
    #: moldes se esgotarem pareceria um dia sem sorte: o log diria "sem
    #: candidato" e a reprise entraria, e ninguem saberia que a causa foi o
    #: acervo ter acabado, e nao o jogo ter ficado dificil.
    repetidos: list[str] = field(default_factory=list)
    nao_cobertos: list[str] = field(default_factory=list)
    auditoria: dict[str, int] = field(
        default_factory=lambda: {"conferem": 0, "divergentes": 0, "impossiveis": 0}
    )

    @property
    def codigo_de_saida(self) -> int:
        """`0` fez · `1` fez e algo divergiu.

        ⛔ **Dia descoberto sai com 1 mesmo que tudo o mais tenha corrido.** Um
        buraco na fila e o unico defeito deste job que o aplicativo mostra a
        pessoa, e ele precisa acender uma luz no painel.

        ⚠️ **`impossiveis` tambem conta.** Uma resolucao que a auditoria nao
        consegue reproduzir e sintoma de **desafio publicado quebrado**, e nao de
        alguem trapaceando — e ele continua no ar enquanto ninguem olhar.
        """
        if self.nao_cobertos:
            return CODIGO_DIVERGIU
        # ⛔ **`fora_da_banda` NAO entra aqui, e isso foi medido.** Ate 10/09/2026
        # ele saia com 1, e a primeira execucao completa mostrou o preco: **seis
        # dos sete dias** ficaram fora da banda numa execucao perfeitamente
        # saudavel. O painel do Railway ficaria vermelho todo dia.
        #
        # ⚠️ **Sinal que dispara sempre e sinal que ninguem le** — a mesma licao
        # que o projeto ja registrou sobre o `--reporter compact`: um portao que
        # acusa regressao inexistente e pior que nenhum, porque ensina a
        # ignora-lo. E o dia em que houver um buraco de verdade na fila, o
        # vermelho nao vai significar nada.
        #
        # ⚠️ **E os dois casos nao tem o mesmo peso:** dia descoberto e o app
        # mostrando dia vazio — quebra de produto. Fora da banda e um candidato
        # mais facil que o alvo entrando na fila de **curadoria**, e ⛔ nada vai
        # ao ar sem o dono aprovar (RF-DES-012a). E observacao, nao quebra.
        #
        # ⚠️ Ele continua gritando no log e no resumo: adiar a decisao de
        # calibracao (decisao do dono, 10/09/2026 — so da para julgar jogando) e
        # diferente de esconder o numero.
        if self.auditoria.get("divergentes", 0) or self.auditoria.get("impossiveis", 0):
            return CODIGO_DIVERGIU
        return CODIGO_FEZ

    def resumo(self) -> str:
        """A linha de log da execucao, para o painel do Railway."""
        linhas = [
            f"[job] perfil: {self.perfis_novos} linha(s) nova(s)",
            f"[job] expiracao: {self.partidas_expiradas} partida(s) fechada(s)",
            f"[job] fila: {self.dias_no_plano} dia(s) no plano, "
            f"{self.ja_publicados} ja publicado(s), {self.gerados} gerado(s), "
            f"{self.reprisados} reprisado(s)",
            f"[job] auditoria: {self.auditoria}",
        ]
        if self.descartados:
            linhas.append(f"[job] descartes: {self.descartados}")
        if self.repetidos:
            linhas.append(
                f"⚠️ [job] JA PUBLICADOS ANTES: {self.repetidos}. Recusados por "
                "repeticao (T049i). Se isto virar rotina, o acervo de posicoes "
                "daquele tipo esta se esgotando — e nao e falta de sorte."
            )
        if self.fora_da_banda:
            linhas.append(
                f"⚠️ [job] FORA DA BANDA: {self.fora_da_banda}. Publicados como "
                "candidato — a curadoria decide, mas a calibracao merece olhada."
            )
        if self.nao_cobertos:
            linhas.append(
                f"⛔ [job] DIAS SEM DESAFIO: {self.nao_cobertos}. A fila tem "
                "buraco, e o aplicativo vai mostrar dia vazio."
            )
        return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════════════════════
# Cobrir um dia
# ═══════════════════════════════════════════════════════════════════════════


async def cobrir_um_dia(
    sessao: Any,
    repositorio: RepositorioDoJob,
    *,
    dt_dia: date,
    relatorio: Relatorio,
    gerar: Callable[..., Sequence[Any]] = gerador_mod.gerar_candidatos,
    bancada_de: Callable[[Any], Any] = gerador_mod.bancada,
    nu_execucoes_da_regua: int = regua_mod.EXECUCOES_PADRAO,
    alvo: Optional[alvo_mod.Alvo] = None,
) -> Optional[str]:
    """Gera, mede e grava o desafio de um dia. Ou reprisa, se nao der.

    Args:
        sessao: a sessao do banco.
        repositorio: a camada de escrita.
        dt_dia: o dia a cobrir.
        relatorio: acumula o que aconteceu.
        gerar: a funcao de geracao. ⚠️ **Entra por parametro** para o teste poder
            exercitar o encadeamento sem rodar motor nenhum — a geracao de um
            candidato de damas leva ~30 segundos, e a suite inteira nao pode
            depender disso.
        bancada_de: como montar as pecas de medicao. ⚠️ **Pelo mesmo motivo**:
            com a bancada de verdade, medir a regua roda a CNN do Pontinhos tres
            vezes por execucao. O teste do ENCADEAMENTO nao pode custar isso — e
            quem prova que a bancada de verdade funciona e a T034, com geracao
            real.
        nu_execucoes_da_regua: quantas vezes cada mascote tenta.

    Returns:
        `None` quando o dia foi coberto; o motivo, quando nao foi.

    ⚠️ **A `tipos_recentes` e lida UMA VEZ e usada nas DUAS chamadas** —
    `escolher_tipo` aqui e `gerar_candidatos` la dentro. As duas sao funcoes puras
    da data, mas discordariam se a lista mudasse entre elas, e o desafio sairia
    gravado com os parametros de um tipo e a linha de chegada de outro. ⛔ Nada
    acusaria: as duas linhas seriam validas.
    """
    # ⚠️ Sem alvo declarado vale o FIXO (70-80%) — a mesma resposta que
    # `alvo_para_a_regua` da enquanto nao ha volume de resolucoes reais.
    alvo = alvo or alvo_mod.alvo_para_a_regua()

    co_jogo = gerador_mod.escolher_jogo(dt_dia)
    janela = timedelta(days=JANELA_DO_RODIZIO_EM_DIAS)
    recentes = await repositorio.tipos_recentes(
        co_jogo=co_jogo, dt_inicio=dt_dia - janela, dt_fim=dt_dia + janela
    )

    co_tipo = gerador_mod.escolher_tipo(co_jogo, dt_dia, tipos_recentes=recentes)

    # ── A VARIANTE DE PARAMETROS do dia (T049f) ─────────────────────────────
    #
    # ⚠️ **Prioridade do dono, 10/09/2026:** *"e muito importante que estes
    # parametros variem, senao os desafios viram pura repeticao"*. Ate 11/09 a
    # **posicao** variava e a **tarefa**, nao: todo `chegar_ao_placar` era "7
    # caixas".
    #
    # ⛔ **A conta mora em `gerador.escolher_variante`, junto dos dois digitos
    # irmaos do odometro** — e nao aqui. Espalhar os tres por arquivos diferentes
    # seria a receita para o quarto ficar em fase com um deles: o aviso sobre a
    # armadilha precisa estar ao lado de quem a repetiria.
    #
    # ⚠️ E `quantas_variantes` entra por parametro porque o gerador ⛔ **nao
    # conhece o editorial**: ele sabe montar candidatos, nao com que numeros eles
    # vao ao ar.
    variantes = editorial_mod.variantes_de(co_tipo)
    nu_variante = gerador_mod.escolher_variante(
        co_jogo, dt_dia, quantas_variantes=len(variantes)
    )
    publicacao = variantes[nu_variante]
    if len(variantes) > 1:
        print(
            f"[job] {dt_dia}: {co_tipo} variante {nu_variante + 1}/{len(variantes)} "
            f"— {dict(publicacao.parametros)}"
        )

    candidatos = gerar(
        dt_dia,
        parametros=publicacao.parametros,
        # ⚠️ **Mais de um, e e a banda que exige isso.** Com um candidato so, a
        # medicao da regua nao tem o que decidir: ou publica o que veio, ou deixa
        # o dia descoberto. Gerar tres da a chance de o proximo cair na banda.
        quantos=CANDIDATOS_POR_DIA,
        tipos_recentes=recentes,
        # ⚠️ **Os dois botoes vem do TIPO**, e nao de uma constante global — ver
        # `editorial.MAXIMO_DE_LANCES_PADRAO`. Um numero so nao servia: um tipo
        # falhava por falta de horizonte, o outro por falta de tabuleiro.
        maximo_de_lances=publicacao.nu_maximo_de_lances,
        lances_de_preparo=publicacao.nu_lances_de_preparo,
    )
    if not candidatos:
        return await _tentar_reprisar(
            sessao, dt_dia=dt_dia, relatorio=relatorio, porque=f"{co_tipo}: sem candidato"
        )

    co_versao_perfil = perfil_mod.versao_vigente()
    co_versao_motor = gerador_mod.versao_do_motor_de(candidatos[0].co_jogo)

    escolhido: Optional[tuple[Any, list[regua_mod.Medicao]]] = None
    reserva: Optional[tuple[float, Any, list[regua_mod.Medicao]]] = None

    for candidato in candidatos:
        # ── ⛔ JA FOI PUBLICADO? (T049i) ────────────────────────────────────
        #
        # ⚠️ **Primeiro de todos os passos, e o motivo e o preco.** Provar o
        # termino custa ate 200 lances e medir a regua custa `3 mascotes x 20
        # execucoes`; esta pergunta custa **um `SELECT` com `LIMIT 1`** numa
        # tabela que cresce uma linha por dia. Gastar a medicao inteira num
        # candidato que sera recusado no fim seria pagar o caro antes do barato.
        #
        # ⚠️ **Contra o historico inteiro** — ver `SQL_ASSINATURA_JA_PUBLICADA`.
        # `tipos_recentes` evita repetir o **tipo**; isto evita repetir o
        # **desafio**, que e outra coisa e ja escapou: a mesma FEN saiu duas
        # vezes em sete dias no `des`, com sementes diferentes.
        #
        # ⛔ **Recusar nao e "deixar o dia descoberto".** Sobram os outros
        # candidatos; e se nenhum servir, a reprise cobre o dia — e ela e
        # **copia com identificador proprio**, entao nao fere esta regra.
        id_anterior = await repositorio.assinatura_ja_publicada(
            co_tipo_desafio=candidato.receita.co_tipo_desafio,
            co_modalidade=candidato.co_modalidade,
            js_posicao_inicial=candidato.js_posicao_inicial,
            js_chegada=candidato.js_chegada,
        )
        if id_anterior is not None:
            relatorio.repetidos.append(
                f"{dt_dia}: {co_tipo} repetiria o desafio {id_anterior}"
            )
            print(
                f"⚠️ [job] {dt_dia}: candidato recusado — este desafio "
                f"({co_tipo}"
                + (f"/{candidato.co_modalidade}" if candidato.co_modalidade else "")
                + f") ja foi publicado como {id_anterior}. "
                "Um desafio vai ao ar uma vez so (T049i).",
                file=sys.stderr,
            )
            continue

        # ⚠️ **A posicao publicada e conferida antes de virar linha.** E este
        # passo que faz `vez_de` e `placar` valerem alguma coisa; sem ele seriam
        # anotacao decorativa, e um desafio com a vez errada passaria pelo banco
        # e quebraria no aparelho de quem o jogasse.
        posicao_mod.conferir(
            candidato.co_formato_posicao,
            candidato.js_posicao_inicial,
            co_modalidade=candidato.co_modalidade or "brasileira",
        )

        bancada = bancada_de(candidato)

        # ── A prova de que a partida chega ao fim (RF-DES-188) ──────────────
        #
        # ⚠️ **Vem ANTES da regua de proposito**: e a recusa mais barata (ate 200
        # lances a 0,5 s) e a mais dura (o candidato nao serve de jeito nenhum).
        # Medir a regua primeiro gastaria `3 mascotes x 20 execucoes` num
        # candidato que seria descartado logo depois.
        prova = terminal_mod.provar_termino(
            jogador=bancada.jogador,
            estado_inicial=bancada.estado_inicial,
            veredito_de=bancada.arbitro.veredito,
            nu_semente=candidato.nu_semente,
        )
        if not prova.tem_fim:
            # ⚠️ **Descartar por nao provar nao e provar que o jogo nao acaba**, e
            # o motivo diz isso. A distincao importa para quem investigar, meses
            # depois, uma fila que ficou curta.
            relatorio.descartados.append(f"{dt_dia}: {prova.de_descarte}")
            continue

        # ── A regua: os TRES mascotes que nao sao o adversario do dia ───────
        medicoes = regua_mod.medir_candidato(
            co_personagem_do_dia=candidato.co_personagem,
            tentar=regua_mod.tentativa_com_motor(
                jogador=bancada.jogador,
                estado_inicial=bancada.estado_inicial,
                julgar=bancada.julgar,
                nu_semente=candidato.nu_semente,
                # ⚠️ **O MESMO teto da geracao.** Medir com um teto maior faria
                # os mascotes resolverem desafios que o gerador nao conseguiu
                # montar, e a taxa descreveria outra tarefa.
                maximo_de_lances=publicacao.nu_maximo_de_lances,
            ),
            co_versao_perfil=co_versao_perfil,
            co_versao_motor=co_versao_motor,
            nu_execucoes=nu_execucoes_da_regua,
        )

        # ── ⚠️ A BANDA: e aqui que a medicao vira DECISAO ───────────────────
        #
        # ⛔ Ate 10/09/2026 este passo nao existia: a regua era medida, gravada e
        # **ignorada**. `dentro_da_banda` e `alvo_para_a_regua` eram chamadas so
        # pelos proprios testes — codigo morto —, e a primeira execucao real
        # publicou um desafio que os tres mascotes resolveram **20 de 20**.
        distancia = regua_mod.distancia_da_banda(
            medicoes, piso=alvo.piso, teto=alvo.teto
        )
        if distancia == 0.0:
            escolhido = (candidato, medicoes)
            break

        # ⚠️ Guarda o **menos pior** e continua. Sem isto, a unica resposta
        # possivel seria "nenhum serve", e o dia ficaria descoberto — que e o
        # unico defeito deste job que a pessoa ve na tela.
        if reserva is None or distancia < reserva[0]:
            reserva = (distancia, candidato, medicoes)

    if escolhido is None:
        if reserva is None:
            return await _tentar_reprisar(
                sessao,
                dt_dia=dt_dia,
                relatorio=relatorio,
                porque="nenhum candidato chegou a estado terminal",
            )
        # ⚠️ **Publica o menos pior, e GRITA.** A alternativa seria deixar o dia
        # vazio, e ⛔ isso e pior: tudo nasce `candidato` (RF-DES-012a), entao
        # nada disto vai ao ar sem o dono aprovar no painel. O que nao pode e a
        # calibracao escorregar **em silencio** — por isso a linha no log e a
        # contagem que leva a execucao a sair com 1.
        distancia, candidato, medicoes = reserva
        escolhido = (candidato, medicoes)
        relatorio.fora_da_banda.append(
            f"{dt_dia}: taxa media {distancia:.2f} fora da banda "
            f"[{alvo.piso:.2f}, {alvo.teto:.2f}] (alvo {alvo.co_origem})"
        )
        print(
            f"⚠️ [job] {dt_dia}: nenhum dos {len(candidatos)} candidatos caiu na "
            f"banda [{alvo.piso:.2f}, {alvo.teto:.2f}]. Publicando o mais "
            f"proximo (erro {distancia:.2f}) como CANDIDATO, para a curadoria "
            "decidir.",
            file=sys.stderr,
        )

    candidato, medicoes = escolhido

    # ── As medidas de saida e a regua de tempo ──────────────────────────────
    medidas = publicacao.medidas(publicacao.parametros)
    medidas_mod.conferir(medidas)

    piso, teto = medidas_mod.regua_de_tempo(
        nu_tempo_do_gabarito_ms=candidato.nu_lances_solucao
        * MILISSEGUNDOS_POR_LANCE_DO_GABARITO
    )

    linha = gravacao_mod.montar_linha(
        candidato,
        ic_chegada_encerra_partida=publicacao.ic_chegada_encerra_partida,
        nu_tempo_piso_ms=piso,
        nu_tempo_teto_ms=teto,
        co_versao_perfil=co_versao_perfil,
        co_versao_motor=co_versao_motor,
        co_versao_minima=publicacao.co_versao_minima,
        nu_teto_log=publicacao.nu_teto_log,
    )

    gravado = await repositorio.publicar_desafio(
        dt_dia=dt_dia, linha=linha, medicoes=medicoes, medidas=medidas
    )
    if gravado is None:
        # ⚠️ Outra execucao publicou este dia enquanto esta gerava. **Nao e
        # buraco na fila** — o dia esta coberto, so nao por este processo.
        relatorio.ja_publicados += 1
        return None

    relatorio.gerados += 1
    return None


async def _tentar_reprisar(
    sessao: Any, *, dt_dia: date, relatorio: Relatorio, porque: str
) -> Optional[str]:
    """A saida de emergencia: republicar um desafio antigo bem avaliado.

    ⚠️ **A reprise e COPIA, com identificador proprio** — um desafio e publicado
    uma vez so (determinacao do dono, 04/09/2026). Quem faz a copia e
    `job/reprise.py`; aqui so se decide **quando** recorrer a ela.

    Returns:
        `None` se a reprise cobriu o dia; o motivo, se nem ela conseguiu.
    """
    try:
        await reprise_mod.publicar_reprise(sessao, dt_dia=dt_dia)
    except reprise_mod.RepriseImpossivel as erro:
        return f"{porque}; e a reprise tambem nao: {erro}"
    relatorio.reprisados += 1
    return None


# ═══════════════════════════════════════════════════════════════════════════
# A execucao inteira
# ═══════════════════════════════════════════════════════════════════════════


async def executar(
    sessao: Any,
    *,
    dt_hoje: Optional[date] = None,
    gerar: Callable[..., Sequence[Any]] = gerador_mod.gerar_candidatos,
    bancada_de: Callable[[Any], Any] = gerador_mod.bancada,
    nu_execucoes_da_regua: int = regua_mod.EXECUCOES_PADRAO,
    alvo: Optional[alvo_mod.Alvo] = None,
) -> Relatorio:
    """Roda o job inteiro sobre uma sessao ja aberta.

    Args:
        sessao: a sessao do banco.
        dt_hoje: o dia da execucao. `None` usa a data de hoje — ⚠️ **em UTC**,
            que e o fuso do Railway, e e o mesmo que decide `dt_dia`.
        gerar: a funcao de geracao, injetavel para teste.
        nu_execucoes_da_regua: quantas vezes cada mascote tenta.

    Returns:
        O [Relatorio], **sempre** — inclusive quando dias falharam.

    Raises:
        Qualquer excecao dos tres primeiros passos (expirar, perfil, plano).
            ⚠️ Elas sao **"nem comecou"** de verdade: sem perfil gravado nenhum
            desafio entra, e sem plano nao ha o que cobrir.

    ⚠️ **O estouro de UM dia nao derruba os outros.** Ele vira dia descoberto com
    o motivo no log, e a execucao segue: seis dias publicados e um com defeito e
    muito melhor que sete dias sem nada porque o quarto tinha uma posicao torta.
    """
    dt_hoje = dt_hoje or date.today()
    relatorio = Relatorio()
    repositorio = RepositorioDoJob(sessao)

    # ── 1. Expirar o que o aplicativo nunca fechou ──────────────────────────
    fechadas = await expiracao_mod.expirar(sessao)
    relatorio.partidas_expiradas = len(fechadas)
    print(expiracao_mod.resumo(fechadas))

    # ── 2. O perfil, ANTES de qualquer desafio ──────────────────────────────
    relatorio.perfis_novos = await repositorio.garantir_perfil(
        perfil_mod.linhas_da_dimensao()
    )
    print(f"[job] perfil vigente: {perfil_mod.resumo()}")

    # ── 3. Que dias cobrir ──────────────────────────────────────────────────
    dias = gravacao_mod.dias_a_cobrir(dt_hoje=dt_hoje)
    publicados = await repositorio.dias_publicados(
        dt_inicio=dias[0], dt_fim=dias[-1]
    )
    plano = gravacao_mod.montar_plano(
        dt_hoje=dt_hoje, dias_ja_publicados=publicados
    )
    gravacao_mod.conferir_plano(plano)

    relatorio.dias_no_plano = len(plano)
    relatorio.ja_publicados = sum(1 for p in plano if p.ja_publicado)

    # ── 3b. O ALVO da regua, lido UMA VEZ para a execucao inteira ───────────
    #
    # ⚠️ **Uma leitura so, e nao uma por dia**: a taxa observada e a mesma para
    # todos os dias desta safra, e sete consultas dariam sete respostas iguais.
    #
    # ⚠️ **Sem volume ele devolve o alvo FIXO (70-80%)**, e isso nao e caso de
    # erro nem limitacao escondida: a taxa de doze pessoas nao diz nada sobre a
    # dificuldade de um desafio. E o que vai acontecer por muito tempo.
    if alvo is None:
        tentaram, resolveram = await repositorio.taxa_observada(
            dt_inicio=dt_hoje - timedelta(days=JANELA_DA_TAXA_OBSERVADA_EM_DIAS),
            dt_fim=dt_hoje,
        )
        alvo = alvo_mod.alvo_para_a_regua(
            nu_tentaram=tentaram, nu_resolveram=resolveram
        )
    print(
        f"[job] banda alvo da regua: [{alvo.piso:.2f}, {alvo.teto:.2f}] "
        f"({alvo.co_origem}, {alvo.nu_amostras} tentativa(s) de referencia)"
    )

    # ── 4. Cobrir dia a dia ─────────────────────────────────────────────────
    for numero, passo in enumerate(plano, start=1):
        if not passo.precisa_gerar:
            continue

        # ⚠️ **Uma linha ANTES de comecar o dia, e nao so depois.** Gerar e medir
        # um candidato leva minutos: sem este aviso, o log fica parado e um job
        # sadio fica indistinguivel de um pendurado. ⛔ E foi exatamente o que
        # aconteceu na primeira operacao real (10/09/2026) — o painel do Railway
        # mostrava a tela vazia enquanto o container trabalhava.
        print(
            f"[job] dia {numero}/{len(plano)} — {passo.dt_dia}: gerando e medindo…"
        )

        try:
            motivo = await cobrir_um_dia(
                sessao,
                repositorio,
                dt_dia=passo.dt_dia,
                relatorio=relatorio,
                gerar=gerar,
                bancada_de=bancada_de,
                nu_execucoes_da_regua=nu_execucoes_da_regua,
                alvo=alvo,
            )
        except Exception as erro:  # noqa: BLE001 - ver a docstring
            # ⚠️ **Amplo de proposito, e so aqui.** Este laco fala com dois
            # motores, com o juiz e com o banco; enumerar as excecoes deles seria
            # uma lista que envelhece, e a que faltasse derrubaria a execucao
            # inteira por causa de um dia.
            motivo = f"{type(erro).__name__}: {erro}"
            traceback.print_exc()

        if motivo:
            relatorio.nao_cobertos.append(f"{passo.dt_dia}: {motivo}")
            print(f"⛔ [job] {passo.dt_dia} sem desafio: {motivo}", file=sys.stderr)
        else:
            print(f"[job] dia {numero}/{len(plano)} — {passo.dt_dia}: pronto ✅")

    # ── 5. Auditar as resolucoes pendentes ──────────────────────────────────
    relatorio.auditoria = await auditoria_mod.auditar_lote(sessao)

    return relatorio


async def _executar_com_banco(dt_hoje: Optional[date] = None) -> Relatorio:
    """Abre a conexao, roda, e fecha a engine ao sair."""
    async with abrir_sessao() as sessao:
        return await executar(sessao, dt_hoje=dt_hoje)


def principal(dt_hoje: Optional[date] = None) -> int:
    """Roda o job e devolve o codigo de saida do processo.

    ⚠️ **Devolve numero, e nao chama `sys.exit`.** Funcao que encerra o processo
    derruba o pytest junto; quem sai e o `if __name__ == "__main__"` la embaixo.
    """
    try:
        relatorio = asyncio.run(_executar_com_banco(dt_hoje))
    except BancoNaoConfigurado as erro:
        # ⚠️ Sem `traceback`: a causa e uma Variable esquecida no console, e o
        # rastro de pilha so afogaria o recado que diz onde arrumar.
        print(f"⛔ [job] {erro}", file=sys.stderr)
        return CODIGO_NEM_COMECOU
    except Exception as erro:  # noqa: BLE001
        # Estouro nos tres primeiros passos — ver a docstring de [executar].
        print(
            f"⛔ [job] a execucao nem comecou: {type(erro).__name__}: {erro}",
            file=sys.stderr,
        )
        traceback.print_exc()
        return CODIGO_NEM_COMECOU

    print(relatorio.resumo())
    return relatorio.codigo_de_saida


if __name__ == "__main__":
    sys.exit(principal())
