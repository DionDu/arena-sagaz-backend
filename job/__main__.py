"""Ponto de entrada do job em batch — o que `python -m job` executa (T049c).

═══════════════════════════════════════════════════════════════════════════
A SEQUENCIA, E POR QUE ELA E ESTA
═══════════════════════════════════════════════════════════════════════════

    1. expirar partidas paradas  →  fecha o que o aplicativo nunca fechou (T046)
    2. gravar o perfil vigente   →  ⛔ **antes de tudo**: a `fk001_perfil` recusa
                                    o primeiro desafio sem ele
    3. descobrir os dias a cobrir → a folga de 7 a 30 dias (T038)
    4. por dia descoberto:
         gerar  →  medir a regua  →  provar que a partida termina  →  gravar
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
    1  →  fez, e algo divergiu (dia descoberto, resolucao divergente)
    2  →  nem comecou (sem `DATABASE_URL`, banco fora, perfil nao gravou)

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

#: Quantos lances a busca tenta, na geracao e na medicao.
#:
#: ⚠️ **O mesmo numero nos dois**, e isso importa: medir com um teto maior que o
#: da geracao faria a regua resolver desafios que o gerador nao conseguiu montar,
#: e a taxa descreveria uma tarefa diferente da publicada.
MAXIMO_DE_LANCES = 12

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
    co_jogo = gerador_mod.escolher_jogo(dt_dia)
    janela = timedelta(days=JANELA_DO_RODIZIO_EM_DIAS)
    recentes = await repositorio.tipos_recentes(
        co_jogo=co_jogo, dt_inicio=dt_dia - janela, dt_fim=dt_dia + janela
    )

    co_tipo = gerador_mod.escolher_tipo(co_jogo, dt_dia, tipos_recentes=recentes)
    publicacao = editorial_mod.publicacao_de(co_tipo)

    candidatos = gerar(
        dt_dia,
        parametros=publicacao.parametros,
        quantos=1,
        tipos_recentes=recentes,
        maximo_de_lances=MAXIMO_DE_LANCES,
    )
    if not candidatos:
        return await _tentar_reprisar(
            sessao, dt_dia=dt_dia, relatorio=relatorio, porque=f"{co_tipo}: sem candidato"
        )

    candidato = candidatos[0]

    # ⚠️ **A posicao publicada e conferida antes de virar linha.** E este passo
    # que faz `vez_de` e `placar` valerem alguma coisa; sem ele seriam anotacao
    # decorativa, e um desafio com a vez errada passaria pelo banco e quebraria
    # no aparelho de quem o jogasse.
    posicao_mod.conferir(
        candidato.co_formato_posicao,
        candidato.js_posicao_inicial,
        co_modalidade=candidato.co_modalidade or "brasileira",
    )

    bancada = bancada_de(candidato)
    co_versao_perfil = perfil_mod.versao_vigente()
    co_versao_motor = gerador_mod.versao_do_motor_de(candidato.co_jogo)

    # ── A regua: os TRES mascotes que nao sao o adversario do dia ───────────
    medicoes = regua_mod.medir_candidato(
        co_personagem_do_dia=candidato.co_personagem,
        tentar=regua_mod.tentativa_com_motor(
            jogador=bancada.jogador,
            estado_inicial=bancada.estado_inicial,
            julgar=bancada.julgar,
            nu_semente=candidato.nu_semente,
            maximo_de_lances=MAXIMO_DE_LANCES,
        ),
        co_versao_perfil=co_versao_perfil,
        co_versao_motor=co_versao_motor,
        nu_execucoes=nu_execucoes_da_regua,
    )

    # ── A prova de que a partida chega ao fim (RF-DES-188) ──────────────────
    prova = terminal_mod.provar_termino(
        jogador=bancada.jogador,
        estado_inicial=bancada.estado_inicial,
        veredito_de=bancada.arbitro.veredito,
        nu_semente=candidato.nu_semente,
    )
    if not prova.tem_fim:
        # ⚠️ **Descartar por nao provar nao e provar que o jogo nao acaba**, e o
        # motivo diz isso. A distincao importa para quem investigar, meses depois,
        # uma fila que ficou curta.
        relatorio.descartados.append(f"{dt_dia}: {prova.de_descarte}")
        return await _tentar_reprisar(
            sessao, dt_dia=dt_dia, relatorio=relatorio, porque="termino nao provado"
        )

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

    # ── 4. Cobrir dia a dia ─────────────────────────────────────────────────
    for passo in plano:
        if not passo.precisa_gerar:
            continue
        try:
            motivo = await cobrir_um_dia(
                sessao,
                repositorio,
                dt_dia=passo.dt_dia,
                relatorio=relatorio,
                gerar=gerar,
                bancada_de=bancada_de,
                nu_execucoes_da_regua=nu_execucoes_da_regua,
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
