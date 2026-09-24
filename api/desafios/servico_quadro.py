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
from decimal import Decimal
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
from api.desafios.publicacao import posicao_publicada
from api.nucleo.excecoes import ErroNaoAutorizado, ErroNaoEncontrado


def numero_para_o_json(valor: Any) -> Any:
    """O `Decimal` do banco como NUMERO do JSON; qualquer outro valor, intacto.

    ⚠️ **T085l, 24/09/2026 — o extrato do Raio-X ⛔ funcionou nunca no
    aparelho.** As colunas do extrato sao `NUMERIC` no banco
    (`desafio_dia.tb004_xp_desafio`: `vr_medida`, `vr_normalizado`, `vr_peso`,
    `vr_xp`), e o driver as entrega ao Python como `Decimal`. A rota do replay
    devolve um `dict` sem modelo, e o FastAPI (pydantic 2) escreve `Decimal`
    como **texto**: `{"vr_xp": "18.000"}`. O aplicativo exigia numero, descartou
    todas as parcelas, e o dono viu *"Total +0"*.

    ⚠️ **Inteiro quando o valor e inteiro** (`18.000` → `18`), e `float` quando
    nao e (`1.800` → `1.8`): e a forma que `contracts/raio-x.md` escreve, e um
    `2.0` onde a tela diz *"2 tentativas"* seria convite a um `2,0` no dia em
    que alguem formatar sem cuidado.

    ⚠️ `float` aqui ⛔ fere a regra do `Decimal` (`extrato_xp.py`): ela vale para
    o que **vai ao banco**, onde somas se acumulam. Isto e so a exibicao de um
    valor ja gravado com 3 casas, e o aplicativo refaz o rateio por conta propria.
    """
    if isinstance(valor, Decimal):
        # `to_integral_value()` e o proprio valor sem as casas decimais; se os
        # dois sao iguais, as casas eram todas zero (`18.000`).
        if valor == valor.to_integral_value():
            return int(valor)
        return float(valor)
    return valor


def _linha_para_o_json(linha: dict[str, Any]) -> dict[str, Any]:
    """Uma linha do banco com os `Decimal` convertidos (ver acima)."""
    return {chave: numero_para_o_json(v) for chave, v in linha.items()}


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
        ids_das_linhas = [linha["id_resolucao"] for linha in gente]
        reacoes = await self.repo.reacoes(ids_das_linhas)
        # ⚠️ **Qual e a MINHA** em cada linha (T077) - o Design destaca o chip
        # e a escolha no seletor, e isso ⛔ nao se deduz da contagem.
        minhas = await self.repo.minhas_reacoes(ids_das_linhas, id_usuario)
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
                # ⛔ Mascote ⛔ nao recebe reacao, entao ⛔ nunca ha uma minha
                # nele. O campo vem assim mesmo: uma linha com forma
                # diferente obrigaria a tela a olhar o sujeito antes de ler.
                "minha_reacao": None,
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
                # ⛔ `None` quando eu ⛔ nao reagi **e** quando sou convidado -
                # sao a mesma coisa para a tela: nada em destaque.
                "minha_reacao": minhas.get(linha["id_resolucao"]),
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
                    # ⚠️ **As reacoes que EU recebi** — o Design as desenha na
                    # barra ancorada, e ⛔ nao tocaveis: ninguem reage a si mesmo,
                    # mas ver quem aplaudiu voce e metade da graca de reagir.
                    #
                    # ⚠️ **Sai do mesmo mapa das linhas**, e ⛔ nao de uma segunda
                    # consulta: a propria linha ja esta em `gente` no caso comum.
                    # ⛔ **E quem se escondeu ⛔ nao aparece nele** — a linha dele
                    # ⛔ nao passou pela clausula de publico, entao a chave falta e
                    # a barra vem sem pilha. E o certo: quem sai do quadro sai
                    # inclusive da contagem que se ve (RF-DES-077).
                    "reacoes": reacoes.get(propria["id_resolucao"]) or None,
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
            # ⚠️ **O que a tela pode OFERECER hoje** (T078) — o catalogo ativo.
            # Sem ele, desativar uma reacao ⛔ nao teria efeito enquanto houvesse
            # aplicativo em campo: o botao continuaria la, e cada toque levaria
            # 400 da propria rota de reagir.
            "reacoes_oferecidas": await self.repo.reacoes_oferecidas(),
        }


    @staticmethod
    def _de_onde_se_parte(contexto: ContextoDoQuadro) -> dict[str, Any]:
        """O jogo, o regulamento e a posicao inicial — os campos do replay.

        ⚠️ **Escrito uma vez porque os DOIS ramos o servem**: quem jogou e o
        gabarito comecam da mesma posicao, e e isso que permite comparar os dois
        no seletor do Raio-X. Montar o dicionario duas vezes faria o gabarito
        perder um campo no dia em que um quinto entrasse — e a tela do gabarito e
        a que ⛔ menos tem quem reclame, porque so abre em D+1.

        ⚠️ **A modalidade viaja AQUI, e ⛔ nao como parametro da tela** (mudou em
        18/09/2026). Quem abre o Raio-X por uma linha do quadro ⛔ nunca teve o
        desafio em maos, e quem o abre pelo historico esta olhando um dia que ja
        passou: a tela mostrava a pilula do regulamento so quando a pessoa vinha
        da tela de resultado, e ⛔ nada denunciava as outras duas portas. Um lance
        que parece ilegal na brasileira e legal na casa (decisao §8g do dono).
        """
        tabuleiro, posicao = posicao_publicada(
            contexto.co_formato_posicao, contexto.js_posicao_inicial
        )
        return {
            "jogo": contexto.co_jogo,
            "modalidade": contexto.co_modalidade,
            # ⚠️ **O adversario daquele dia, pelo mesmo motivo da modalidade**
            # (T085m, 24/09/2026). O replay do Pontinhos escreve nas caixas
            # fechadas as iniciais de quem as fechou, como a partida escreveu;
            # sem o personagem, as caixas dele sairiam mudas - e o quadro e o
            # historico, duas das portas do Raio-X, ⛔ tem o desafio em maos.
            # ⚠️ Campo ADITIVO: aplicativo antigo o ignora.
            "personagem": contexto.co_personagem_do_dia,
            # ⚠️ **A MESMA forma do desafio publicado**, e ⛔ nao uma reduzida
            # para esta rota: `formato_posicao` diz qual dos dois veio, e o
            # aplicativo ja sabe ler exatamente este par. Uma forma propria aqui
            # obrigaria o aplicativo a ter um segundo leitor de posicao inicial.
            "formato_posicao": contexto.co_formato_posicao,
            "tabuleiro": tabuleiro,
            "posicao": posicao,
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
                # ⚠️ **O gabarito viajava SEM JOGO ate 18/09/2026** — e com ele
                # uma lista de lances que ⛔ ninguem sabia desenhar: nem qual
                # tabuleiro montar, nem por qual regulamento ler um lance. A
                # ausencia ⛔ nao aparecia porque ⛔ nao havia player.
                **self._de_onde_se_parte(contexto),
                "lances": gabarito["js_solucao"],
                "nu_lances": gabarito["nu_lances_solucao"],
                # ⚠️ **A solucao de referencia nao tem "lance do objetivo"**: ela
                # E o caminho ate ele, e o ultimo lance dela e o que cumpre. Um
                # numero aqui seria a estrela desenhada sempre no fim, dizendo
                # como fato o que e definicao.
                "nu_lance_objetivo": None,
                "nu_primeiro_lance": 1,
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

        # ⚠️ **A numeracao dos lances E o dado de truncamento** (RF-DES-039).
        # O teto corta o **comeco** da partida, e a numeracao ⛔ nao se refaz: o
        # primeiro lance guardado carrega o `nu_ordem` original. Entao
        # `nu_primeiro_lance > 1` **e** o truncamento, e o ultimo `nu_ordem` e o
        # tamanho da partida inteira — sem coluna nova e sem migracao.
        #
        # ⛔ **Uma coluna `ic_truncado` seria uma segunda fonte para o mesmo
        # fato**, e as duas discordariam em silencio no dia em que uma delas
        # fosse gravada errada. O log e append-only (`0006`); ele ja sabe.
        nu_primeiro = lances[0]["nu_ordem"] if lances else None
        nu_ultimo = lances[-1]["nu_ordem"] if lances else None

        return {
            "sujeito": sujeito,
            # ⚠️ **O jogo passou a sair do DESAFIO** (T074a), e ⛔ nao mais de
            # `partida.vw001_partida`: sao a mesma coisa, e duas fontes para um
            # fato so discordam em silencio — no dia em que discordassem, a tela
            # desenharia o tabuleiro de um jogo com os lances de outro.
            **self._de_onde_se_parte(contexto),
            "lances": lances,
            # O tamanho da partida INTEIRA, e nao quantos lances vieram: com o
            # comeco cortado, os dois numeros sao diferentes, e e o primeiro que
            # a barra do replay precisa para dizer *"lance 19 de 24"*.
            "nu_lances": nu_ultimo,
            "nu_primeiro_lance": nu_primeiro,
            # ⚠️ **O instante em que o objetivo caiu** (RF-DES-213/214): e o
            # `nu_ordem` da jogada, e e ele que a estrela da barra marca. Vem
            # `None` de quem tentou e ⛔ nao cumpriu.
            "nu_lance_objetivo": linha["nu_lance_cumpre_desafio"],
            # ⚠️ **O extrato vem INTEIRO no Raio-X**, e so as linhas que pontuaram
            # na tela de resultado (RF-DES-177): e o **mesmo dado** nos dois
            # lugares, e nao uma segunda lista escrita para a tela.
            #
            # ⚠️ **E sai como NUMERO** (T085l): as colunas sao `NUMERIC`, e sem
            # a conversao o JSON as levaria como texto — ver
            # `numero_para_o_json`.
            "extrato": [
                _linha_para_o_json(parcela)
                for parcela in await self.repo.extrato(linha["id_resolucao"])
            ],
            # ⚠️ O teto de log **trunca**, nunca invalida (RF-DES-039): o replay
            # diz honestamente que esta truncado, e o veredito que a pessoa viu
            # permanece.
            "truncado": nu_primeiro is not None and nu_primeiro > 1,
        }
