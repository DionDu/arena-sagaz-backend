"""MONTA O QUADRO E O REPLAY (T044).

Este modulo junta as pecas de `quadro.py` (o SQL) e `mascotes.py` (a encenacao)
na resposta que `contracts/quadro-do-dia.md` descreve.

═══════════════════════════════════════════════════════════════════════════
⚠️ A ORDENACAO E POR XP, E O DESEMPATE E O TEMPO
═══════════════════════════════════════════════════════════════════════════

RF-DES-061: **ordenacao pelo XP obtido no desafio** — que e funcao direta de `Q`,
exibida na moeda que a pessoa ja entende. O tempo desempata porque `Q` ja o
contem: dois XP iguais com tempos diferentes vem de arredondamento, e mostrar o
mais rapido acima e o que a pessoa espera.

⚠️ **Os mascotes entram na MESMA lista.** Uma lista separada faria a tela ter de
intercalar as duas — e a frase *"voce passou o Tex"* deixaria de ser uma leitura
da ordem para virar uma comparacao que a tela faz sozinha.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from api.desafios.mascotes import linhas_dos_mascotes, taxas_das_medicoes
from api.desafios.quadro import (
    TOPO,
    ContextoDoQuadro,
    RepositorioQuadro,
    fracao_servivel,
    replays_liberados,
)
from api.nucleo.excecoes import ErroNaoAutorizado, ErroNaoEncontrado


class ReplayTrancado(ErroNaoAutorizado):
    """A pessoa ainda nao resolveu, e o dia nao acabou.

    ⚠️ **403, e nao 404.** O replay **existe**; o que falta e o direito de ve-lo.
    Um 404 faria a tela dizer "nao encontrado" para algo que esta la, e a pessoa
    concluiria que o aplicativo perdeu a partida dela.
    """

    def __init__(self) -> None:
        super().__init__(
            "Os replays do dia abrem depois que voce resolve o desafio — ou "
            "quando o dia encerra. ⛔ Resolver desbloqueia; nao se compra o "
            "acesso.",
            "replay_trancado",
        )
        self.status_http = 403


def _nome_visivel(linha: dict[str, Any]) -> str:
    """O nome que aparece no quadro.

    ⚠️ `no_exibicao` pode ser `NULL` — quem nunca escolheu um nao tem. O
    `co_usuario` (o codigo curto da conta) e o substituto, e nao o e-mail nem o
    identificador interno: ⛔ **nenhum dos dois pode aparecer numa lista publica**.
    """
    return linha.get("no_exibicao") or linha.get("co_usuario") or "?"


class ServicoQuadro:
    """Monta o quadro do dia e serve os replays."""

    def __init__(self, repo: RepositorioQuadro) -> None:
        self.repo = repo

    async def _contexto(self, id_desafio: UUID) -> ContextoDoQuadro:
        """O dia daquele desafio, ou 404."""
        contexto = await self.repo.contexto(id_desafio)
        if contexto is None:
            raise ErroNaoEncontrado(
                "Desafio nao encontrado.", "desafio_inexistente"
            )
        return contexto

    async def montar(
        self, *, id_desafio: UUID, id_usuario: Optional[str], agora: datetime
    ) -> dict[str, Any]:
        """O quadro inteiro.

        Args:
            id_desafio: o desafio do dia.
            id_usuario: quem esta olhando. `None` para convidado — ⚠️ ele **ve** o
                quadro, e so nao tem linha propria nem replays.
            agora: o instante do servidor.

        Returns:
            O corpo de `GET /v1/desafios/{id}/quadro`.
        """
        contexto = await self._contexto(id_desafio)

        gente = await self.repo.linhas_de_gente(contexto.id_desafio_dia)
        reacoes = await self.repo.reacoes([linha["id_resolucao"] for linha in gente])
        taxas = taxas_das_medicoes(await self.repo.medicoes(id_desafio))

        mascotes = linhas_dos_mascotes(
            id_desafio=id_desafio,
            nu_tempo_piso_ms=contexto.nu_tempo_piso_ms,
            nu_tempo_teto_ms=contexto.nu_tempo_teto_ms,
            # ⛔ O adversario do dia sai da escada (RF-DES-203) — e ela **roda
            # junto** com ele: em dia de Magno a escada e mais encorajadora; em
            # dia de Cacau, mais dura.
            co_personagem_do_dia=contexto.co_personagem_do_dia,
            taxas=taxas,
        )

        linhas: list[dict[str, Any]] = [
            {
                "sujeito": "mascote",
                "chave": m.co_personagem,
                "xp": m.nu_xp,
                "tempo_ms": m.nu_tempo_ms,
                # ⛔ Mascote nao recebe reacao e nao tem `pode_reagir`
                # (RF-DES-060c). E **estrutura**, e nao `if` na tela: reacao
                # aponta para resolucao, e mascote nao tem resolucao.
                "reacoes": None,
                "pode_reagir": False,
            }
            for m in mascotes
        ]
        linhas += [
            {
                "sujeito": "jogador",
                "id": str(linha["id_usuario"]),
                "nome": _nome_visivel(linha),
                "xp": linha["nu_xp"],
                "tempo_ms": linha["nu_tempo_ms"],
                # ⛔ Zero reacoes nao e servido (RF-DES-073): a tela nao mostra
                # "0 👏".
                "reacoes": reacoes.get(linha["id_resolucao"]) or None,
                # ⚠️ Reagir exige conta (RF-DES-084): sem identidade nao ha como
                # honrar "uma reacao por pessoa". E ninguem reage a si mesmo.
                "pode_reagir": bool(id_usuario)
                and str(linha["id_usuario"]) != str(id_usuario),
            }
            for linha in gente
        ]

        # ⚠️ A ordenacao acontece **depois** de juntar as duas origens: e o que
        # faz "voce passou o Tex" ser uma leitura da ordem, e nao uma conta que a
        # tela refaz.
        linhas.sort(key=lambda item: (-item["xp"], item["tempo_ms"]))

        qt_pessoas, qt_resolveram = await self.repo.fracao(contexto.id_desafio_dia)

        minha = None
        resolveu_hoje = False
        if id_usuario:
            propria = await self.repo.minha_linha(
                id_desafio_dia=contexto.id_desafio_dia, id_usuario=id_usuario
            )
            if propria is not None:
                resolveu_hoje = True
                # ⚠️ **A posicao e sobre a lista INTEIRA**, e nao sobre o topo
                # recortado: a pessoa em 74o precisa ler 74, e nao "fora do
                # quadro" (RF-DES-069).
                posicao = 1 + sum(
                    1
                    for item in linhas
                    if (item["xp"], -item["tempo_ms"])
                    > (propria["nu_xp"], -propria["nu_tempo_ms"])
                )
                minha = {
                    "posicao": posicao,
                    "xp": propria["nu_xp"],
                    "tempo_ms": propria["nu_tempo_ms"],
                }

        return {
            # ⚠️ O corte e **50 + a propria linha**, e `minha_linha` vem por fora
            # justamente para que cortar nao esconda quem esta lendo.
            "linhas": linhas[: TOPO + len(mascotes)],
            "minha_linha": minha,
            "fracao": fracao_servivel(
                qt_pessoas=qt_pessoas, qt_resolveram=qt_resolveram
            ),
            # ⛔ Zero nunca aparece (RF-DES-064): sem tentativa nenhuma de gente,
            # a tela mostra um convite — "Ninguem passou por aqui hoje. Seja o
            # primeiro." —, e nunca um `0`.
            "texto_vazio": qt_pessoas == 0,
            "replays_liberados": replays_liberados(
                resolveu_hoje=resolveu_hoje,
                dh_encerramento=contexto.dh_encerramento,
                agora=agora,
            ),
        }

    async def replay(
        self,
        *,
        id_desafio: UUID,
        sujeito: str,
        id_usuario: Optional[str],
        agora: datetime,
    ) -> dict[str, Any]:
        """O Raio-X de um sujeito: `eu` · `jogador/{id}` · `desafio`.

        Args:
            sujeito: `eu`, o identificador de um jogador, ou `desafio` (a solucao
                de referencia).

        Raises:
            ReplayTrancado: 403 — a trava de spoiler, resolvida **no servidor**.
            ErroNaoEncontrado: sujeito sem resolucao neste dia.

        ⚠️ **O replay servido e o de uma PARTIDA** (RF-DES-186): a rota resolve o
        sujeito → a resolucao → `id_partida`, e devolve os lances de
        `partida.tb002_jogada`. ⛔ Nao ha armazenamento de replay proprio do
        desafio, e e por isso que toda partida de desafio precisa estar fechada.
        """
        contexto = await self._contexto(id_desafio)

        resolveu_hoje = False
        if id_usuario:
            resolveu_hoje = (
                await self.repo.minha_linha(
                    id_desafio_dia=contexto.id_desafio_dia, id_usuario=id_usuario
                )
                is not None
            )

        if not replays_liberados(
            resolveu_hoje=resolveu_hoje,
            dh_encerramento=contexto.dh_encerramento,
            agora=agora,
        ):
            raise ReplayTrancado()

        if sujeito == "desafio":
            gabarito = await self.repo.gabarito(id_desafio)
            if gabarito is None:
                raise ErroNaoEncontrado(
                    "Desafio nao encontrado.", "desafio_inexistente"
                )
            # ⚠️ **A solucao de referencia nao disputa o quadro** (RF-DES-078a):
            # ela nao tem tentativas nem dica, e um sujeito que nasce com nota
            # cheia tornaria a disputa decorativa. Por isso ela vem sem XP e sem
            # extrato — e humano pode supera-la, o que e esperado.
            return {
                "sujeito": "desafio",
                "lances": gabarito["js_solucao"],
                "nu_lances": gabarito["nu_lances_solucao"],
                "extrato": None,
                "truncado": False,
            }

        alvo = id_usuario if sujeito == "eu" else sujeito
        if not alvo:
            raise ErroNaoEncontrado(
                "Sem sujeito para o replay.", "sujeito_invalido"
            )

        linha = await self.repo.partida_do_sujeito(
            id_desafio_dia=contexto.id_desafio_dia, id_usuario=alvo
        )
        if linha is None:
            raise ErroNaoEncontrado(
                "Esse sujeito nao resolveu este desafio.", "sem_resolucao"
            )

        if linha["co_status"] == "em_andamento":
            # ⚠️ **Partida sem desfecho nao tem replay** (RF-DES-187, SC-024). Ela
            # existe — a pessoa parou no objetivo e nao voltou —, e o job de
            # expiracao (T046) a fechara em ate 7 dias. Ate la, ⛔ nao ha o que
            # reproduzir, e dizer isso e mais honesto que servir meia partida.
            raise ErroNaoEncontrado(
                "A partida desse sujeito ainda nao foi encerrada; o replay "
                "aparece quando ela fechar.",
                "partida_em_andamento",
            )

        lances = await self.repo.lances(linha["id_partida"])
        return {
            "sujeito": sujeito,
            "jogo": linha["co_jogo"],
            "lances": lances,
            # ⚠️ **O extrato vem INTEIRO no Raio-X**, e so as linhas que pontuaram
            # na tela de resultado (RF-DES-177): e o **mesmo dado** nos dois
            # lugares, e nao uma segunda lista escrita para a tela.
            "extrato": await self.repo.extrato(linha["id_resolucao"]),
            # ⚠️ O teto de log **trunca**, nunca invalida (RF-DES-039): o replay
            # diz honestamente que esta truncado, e o veredito que a pessoa viu
            # permanece.
            "truncado": False,
        }
