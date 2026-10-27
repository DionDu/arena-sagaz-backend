"""AS REGRAS DA CURADORIA — o que o painel deixa e o que nao deixa (T039).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTAS REGRAS NAO MORAM NO HTML
═══════════════════════════════════════════════════════════════════════════

Seria natural desabilitar o botao "agendar" nas linhas ainda nao aprovadas e
declarar o problema resolvido. Mas **um botao desabilitado e uma decoracao**: o
formulario continua existindo, e um `curl` — ou uma aba aberta antes de a linha
mudar de estado — passa direto por ele.

A regra vive aqui, e o HTML apenas **espelha** o que ela ja decidiu. Quando os
dois discordarem, quem manda e este arquivo.

═══════════════════════════════════════════════════════════════════════════
AS TRES REGRAS, E O QUE CADA UMA IMPEDE
═══════════════════════════════════════════════════════════════════════════

1. **Descartar exige motivo** (RF-DES-012c). O `CHECK` `ck004_motivo` da migracao
   `0018` ja o exige — mas um erro de constraint chega como 500, e a pessoa que
   esqueceu o campo merece ler *"escreva o motivo"*, nao *"internal server
   error"*. ⚠️ **A checagem daqui nao substitui a do banco**: ela a antecipa.
2. **So aprovado vai ao calendario** (RF-DES-012a). Agendar um candidato criaria
   um dia que o endpoint nao serve (ele filtra por `aprovado`), e o efeito seria
   um dia **em branco** no aplicativo — o pior dos resultados, porque nada
   acusa.
3. **Descartar tira do calendario.** Um descartado agendado e a mesma armadilha
   do item 2, chegando pelo outro lado: o dia continua ocupado (`un001_dia`
   impede outro desafio de entrar) e nada e servido.
4. ⛔ **O que ja esta nos aparelhos nao sai do dia dele** (07/10/2026). O app
   guarda hoje e os proximos dias para jogar sem rede; descartar ou mover um
   desses faria o resultado de quem jogou sem rede ser recusado, ou cair no
   quadro de outro dia. A regra e o porque estao em `api/desafios/janela_baixada.py`.

═══════════════════════════════════════════════════════════════════════════
AS TRES ACOES DE 27/10/2026 (pedido do dono)
═══════════════════════════════════════════════════════════════════════════

5. **Inverter duas datas.** Ate aqui, adiantar um bom desafio do futuro exigia
   tirar o mais proximo do calendario - e ele se perdia, em vez de ir para o
   dia que vagou. Agora os dois trocam de dia. Vale no `prd`, com as travas de
   cima para OS DOIS desafios (cada um sai do seu dia).
6. **Esvaziar daqui em diante.** Descarta (⛔ nao apaga) todo desafio a partir
   do primeiro dia destravado, para a proxima geracao preencher. Vale no `prd`,
   so depois da janela baixada.
7. ⛔ **Limpar as resolucoes de um dia: so no modo de teste**
   (`modo_de_teste.py`). E o unico ponto do painel que APAGA, e por isso so
   existe no `des`. No modo de teste, a regra 4 tambem cai para inverter e
   esvaziar; ⛔ a regra do dia ja PASSADO nunca cai.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from typing import Optional

from api.desafios.janela_baixada import DIAS_DE_CACHE, na_janela_baixada
from api.desafios.painel.datas import data_br
from api.desafios.painel.repositorio import RepositorioPainel, VinculoDoDia
from api.nucleo.excecoes import ErroNegocio

#: Tamanho maximo do motivo de descarte.
#:
#: ⚠️ A coluna e `TEXT` (sem limite no banco); o limite e de **produto**: o motivo
#: e uma frase que ensina o gerador, e nao um relatorio. Cortar aqui evita que um
#: `POST` mal-intencionado encha a tabela.
MAX_MOTIVO = 500

#: Quantos dias a frente o painel aceita agendar.
#:
#: ⚠️ E o mesmo teto de `job/gravacao.py` (`DIAS_MAXIMOS = 30`), e pelo mesmo
#: motivo, dito em RF-DES-012: gerar — ou agendar — com muita antecedencia faz o
#: dono aprovar conteudo que so vai ao ar dali a meses, sem saber o que estara
#: publicado junto.
DIAS_MAXIMOS_A_FRENTE = 30


def _motivo_valido(motivo: Optional[str]) -> str:
    """O motivo de descarte, aparado e cortado em [MAX_MOTIVO].

    ⚠️ Uma funcao so para o descarte de um desafio e o esvaziamento do
    calendario: os dois gravam no mesmo `de_motivo_descarte`, sob o mesmo
    `CHECK`.

    Raises:
        ErroNegocio: motivo vazio (RF-DES-012c).
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroNegocio(
            "Descartar exige um motivo: e ele que ensina o gerador a nao "
            "repetir a familia de posicao que saiu ruim.",
            "motivo_ausente",
            status_http=400,
        )
    return motivo[:MAX_MOTIVO]


@dataclass(frozen=True, slots=True)
class ResultadoDaAcao:
    """O que aconteceu, em forma de frase para a tela.

    ⚠️ `mudou=False` **nao e erro**: clicar duas vezes em "aprovar" e coisa
    rotineira, e tratar o segundo clique como falha ensinaria o dono a
    desconfiar de mensagem vermelha que nao significa nada.
    """

    mudou: bool
    mensagem: str


class ServicoCuradoria:
    """As acoes do painel, com as regras aplicadas antes do banco."""

    def __init__(self, repo: RepositorioPainel) -> None:
        self.repo = repo

    async def aprovar(self, id_desafio: UUID) -> ResultadoDaAcao:
        """Aprova o desafio — e so a partir daqui ele pode ir ao ar."""
        mudou = await self.repo.aprovar(id_desafio)
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=mudou,
            mensagem=(
                "Desafio aprovado." if mudou else "Este desafio ja estava aprovado."
            ),
        )

    async def aprovar_candidatos(self) -> ResultadoDaAcao:
        """Aprova de uma vez os candidatos que sobraram de antes de 02/10/2026.

        ⚠️ **E a ponte da transicao para a pre-aprovacao**: desde aquele dia o job
        so grava `aprovado`, e os candidatos antigos ficariam ocupando dias sem
        ir ao ar ate alguem clicar um a um.
        """
        quantos = await self.repo.aprovar_candidatos()
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=quantos > 0,
            mensagem=(
                f"{quantos} candidato(s) aprovado(s)."
                if quantos
                else "Nao havia candidato esperando."
            ),
        )

    async def _exigir_dia_nao_jogado(
        self, id_desafio: UUID, dt_hoje: date, *, ato: str
    ) -> None:
        """Recusa mexer no dia de um desafio que ja foi jogado (02/10/2026).

        ⚠️ **O calendario do painel de gestao abre QUALQUER dia**, inclusive os
        que ja foram ao ar — e as tres acoes que mexem no vinculo do dia
        (descartar, trocar a data, tirar do calendario) passaram a estar a um
        clique de um dia vivido:

          · **descartar e tirar do calendario** apagam o vinculo, e
            `tb002_tentativa` aponta para ele sem `ON DELETE`: o banco recusaria,
            e o dono leria um erro 500;
          · ⛔ **trocar a data e pior, porque o banco ACEITA**: o `UPDATE` move o
            vinculo, e as tentativas de quem jogou passam a pertencer a outro
            dia — o historico de cada pessoa mudaria de data sem nada acusar.

        Raises:
            ErroNegocio: o dia ja passou, ou ja tem tentativa hoje.
        """
        situacao = await self.repo.situacao_no_calendario(id_desafio)
        if situacao is None:
            return
        dt_dia, qt_tentativas = situacao
        if dt_dia < dt_hoje:
            raise ErroNegocio(
                f"O desafio de {data_br(dt_dia)} ja foi ao ar. Nao da para "
                f"{ato} um dia que passou: ele e a historia de quem jogou.",
                "dia_ja_jogado",
                status_http=400,
            )
        if qt_tentativas:
            raise ErroNegocio(
                f"{qt_tentativas} tentativa(s) ja foram feitas neste desafio hoje. "
                f"Nao da para {ato} agora: tiraria o dia de quem esta jogando.",
                "dia_ja_jogado",
                status_http=400,
            )

    async def _exigir_fora_da_janela_baixada(
        self, id_desafio: UUID, dt_hoje: date, *, ato: str
    ) -> None:
        """Recusa tirar do dia um desafio que ja pode estar num aparelho (07/10/2026).

        ⚠️ **A guarda de cima nao pega este caso**: ela conta as tentativas que o
        SERVIDOR tem, e as de quem resolveu sem rede ainda estao no aparelho.
        Descartar faria o envio dela voltar recusado (o vinculo do dia sumiu);
        trocar a data a poria no quadro de um dia que ela nao jogou. Nos dois casos,
        sem nada avisar. O porque inteiro esta em `api/desafios/janela_baixada.py`.

        ⚠️ **So a ORIGEM e conferida.** Por um desafio de fora num dia VAZIO da
        janela continua permitido: ninguem tem aquele dia guardado, e recusar
        deixaria o dia em branco no aplicativo.

        Raises:
            ErroNegocio: o desafio esta num dia entre hoje e o fim da janela.
        """
        situacao = await self.repo.situacao_no_calendario(id_desafio)
        if situacao is None:
            # Sem dia, nao esta em aparelho nenhum: o `/proximos` so entrega o
            # que tem data.
            return
        dt_dia, _ = situacao
        dt_fim = await self.repo.fim_da_janela_baixada(dt_hoje)
        if na_janela_baixada(dt_dia, dt_hoje=dt_hoje, dt_fim=dt_fim):
            raise ErroNegocio(
                f"O desafio de {data_br(dt_dia)} ja pode estar guardado nos "
                f"aparelhos: o app baixa hoje e os {DIAS_DE_CACHE} proximos dias "
                f"para jogar sem rede. Nao da para {ato} ele - quem o resolvesse "
                "sem rede perderia o resultado, ou entraria no quadro de outro "
                f"dia. A curadoria vale de {data_br(dt_fim + timedelta(days=1))} "
                "em diante.",
                "dia_ja_baixado",
                status_http=400,
            )

    async def descartar(
        self, id_desafio: UUID, *, motivo: str, dt_hoje: date
    ) -> ResultadoDaAcao:
        """Descarta com motivo, e **tira do calendario** se estava agendado.

        ⚠️ Desde 02/10/2026 o desafio nasce aprovado, e e ESTE o ato de
        curadoria: o dia vira buraco, e a proxima geracao o tapa primeiro.

        Args:
            dt_hoje: o dia corrente em UTC. Recusa o descarte de um dia ja jogado
                e o de um dia que ja esta nos aparelhos (ver o bloco abaixo).
                ⚠️ Obrigatorio desde 07/10/2026: opcional, um chamador que o
                esquecesse passaria pelas duas guardas sem nada acusar.

        Raises:
            ErroNegocio: motivo vazio (RF-DES-012c), dia ja jogado, ou dia ja
                baixado.
        """
        motivo = _motivo_valido(motivo)

        # ⛔ Dia ja jogado nao se descarta (ver `_exigir_dia_nao_jogado`), nem o
        # que ja esta nos aparelhos (ver `_exigir_fora_da_janela_baixada`).
        await self._exigir_dia_nao_jogado(id_desafio, dt_hoje, ato="descartar")
        await self._exigir_fora_da_janela_baixada(id_desafio, dt_hoje, ato="descartar")

        # ⚠️ A ORDEM IMPORTA: desagendar primeiro deixaria uma janela em que o dia
        # esta livre e o desafio ainda aprovado. Descartar primeiro fecha a porta
        # antes de abrir o dia.
        mudou = await self.repo.descartar(id_desafio, de_motivo=motivo)
        if not mudou:
            raise ErroNegocio(
                "Desafio nao encontrado.", "desafio_inexistente", status_http=404
            )
        saiu_do_calendario = await self.repo.desagendar(id_desafio)
        await self.repo.confirmar()

        return ResultadoDaAcao(
            mudou=True,
            mensagem=(
                "Desafio descartado (a linha continua no banco, com o motivo)."
                + (" O dia dele voltou a ficar livre." if saiu_do_calendario else "")
            ),
        )

    async def agendar(
        self, id_desafio: UUID, *, dt_dia: date, dt_hoje: date
    ) -> ResultadoDaAcao:
        """Poe o desafio num dia, ou o move para outro.

        Args:
            id_desafio: qual desafio.
            dt_dia: o dia de destino.
            dt_hoje: o dia corrente **em UTC** — parametro, e nao `date.today()`
                lido aqui dentro, para que o teste possa fixa-lo sem congelar o
                relogio do processo inteiro.

        Raises:
            ErroNegocio: dia no passado, longe demais, desafio nao aprovado, ou
                desafio que ja esta nos aparelhos (a ORIGEM; o destino vazio
                dentro da janela continua aceito - ver
                `_exigir_fora_da_janela_baixada`).

        ⚠️ **Hoje e aceito.** Agendar para o proprio dia e exatamente o que a fila
        curta exige quando o dono chega tarde — recusar seria transformar um
        atraso de operacao num dia vazio.
        """
        if dt_dia < dt_hoje:
            raise ErroNegocio(
                f"{data_br(dt_dia)} ja passou. O desafio de um dia encerrado nao seria "
                "servido a ninguem.",
                "dia_no_passado",
                status_http=400,
            )
        if (dt_dia - dt_hoje).days > DIAS_MAXIMOS_A_FRENTE:
            raise ErroNegocio(
                f"{data_br(dt_dia)} esta a mais de {DIAS_MAXIMOS_A_FRENTE} dias. Aprovar "
                "conteudo para daqui a meses e decidir sem saber o que estara "
                "publicado junto.",
                "dia_longe_demais",
                status_http=400,
            )

        # ⚠️ Le a fila em vez de confiar no formulario: o estado de curadoria pode
        # ter mudado desde que a pagina foi desenhada.
        fila = await self.repo.fila(estados=("candidato", "aprovado", "descartado"))
        alvo = next((d for d in fila if d.id_desafio == id_desafio), None)
        if alvo is None:
            raise ErroNegocio(
                "Desafio nao encontrado.", "desafio_inexistente", status_http=404
            )
        if alvo.co_curadoria != "aprovado":
            raise ErroNegocio(
                "So desafio APROVADO entra no calendario. Um candidato agendado "
                "criaria um dia que o endpoint nao serve — e o aplicativo abriria "
                "com o dia em branco, sem nada acusar.",
                "desafio_nao_aprovado",
                status_http=400,
            )

        # ⛔ Trocar a data de um dia jogado moveria as tentativas junto.
        await self._exigir_dia_nao_jogado(id_desafio, dt_hoje, ato="trocar a data de")
        # ⛔ E o que ja esta nos aparelhos nao muda de dia: o envio de quem jogou
        # sem rede seria ACEITO, no quadro do dia novo.
        await self._exigir_fora_da_janela_baixada(
            id_desafio, dt_hoje, ato="trocar a data de"
        )

        mudou = await self.repo.agendar(id_desafio, dt_dia=dt_dia)
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=mudou, mensagem=f"Desafio agendado para {data_br(dt_dia)}."
        )

    async def desagendar(self, id_desafio: UUID, *, dt_hoje: date) -> ResultadoDaAcao:
        """Tira o desafio do calendario, mantendo a aprovacao.

        ⚠️ E o passo que **libera um dia ocupado**: sem ele, trocar dois desafios
        de data seria impossivel, porque `un001_dia` recusa o segundo enquanto o
        primeiro nao sai.

        Args:
            dt_hoje: o dia corrente em UTC. Um dia ja jogado e recusado, e um dia
                que ja esta nos aparelhos tambem. ⚠️ Obrigatorio desde 07/10/2026,
                pelo mesmo motivo de `descartar`.
        """
        await self._exigir_dia_nao_jogado(id_desafio, dt_hoje, ato="tirar do calendario")
        await self._exigir_fora_da_janela_baixada(
            id_desafio, dt_hoje, ato="tirar do calendario"
        )
        mudou = await self.repo.desagendar(id_desafio)
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=mudou,
            mensagem=(
                "Desafio tirado do calendario (segue aprovado, sem data)."
                if mudou
                else "Este desafio ja estava sem data."
            ),
        )

    # ── As acoes de 27/10/2026 ──────────────────────────────────────────────

    async def inverter_dias(
        self,
        id_desafio: UUID,
        *,
        dt_destino: date,
        dt_hoje: date,
        modo_de_teste: bool = False,
    ) -> ResultadoDaAcao:
        """Troca o dia do desafio com o do desafio que mora em [dt_destino].

        ⚠️ **Os dois saem do seu dia**, e por isso as travas valem para os DOIS:
        nenhum pode ter ido ao ar (dia passado, ou hoje com tentativa), e,
        fora do modo de teste, nenhum pode estar na janela baixada. ⚠️ Os dois
        precisam estar aprovados: um candidato ou descartado que fosse parar
        num dia seria um dia que o endpoint nao serve.

        Args:
            dt_destino: o dia do OUTRO desafio. ⚠️ Dia vazio e recusado: para
                ele, o caminho e "Trocar a data" ([agendar]).
            modo_de_teste: o painel do `des` (`modo_de_teste.py`). Libera a
                janela baixada; ⛔ nao libera dia passado nem dia com tentativa
                (no `des`, limpe as resolucoes primeiro).

        Raises:
            ErroNegocio: o que cada trava acima recusa, ou a troca que parou no
                meio porque outra aba mexeu num dos dois.
        """
        a = await self.repo.vinculo_do_desafio(id_desafio)
        if a is None:
            raise ErroNegocio(
                "Este desafio esta sem data: para por-lhe um dia, use Agendar.",
                "desafio_sem_dia",
                status_http=400,
            )
        if dt_destino == a.dt_dia:
            raise ErroNegocio(
                f"O desafio ja mora em {data_br(dt_destino)}.",
                "mesmo_dia",
                status_http=400,
            )
        if dt_destino < dt_hoje:
            raise ErroNegocio(
                f"{data_br(dt_destino)} ja passou: o desafio de la e a historia "
                "de quem jogou.",
                "dia_no_passado",
                status_http=400,
            )
        if (dt_destino - dt_hoje).days > DIAS_MAXIMOS_A_FRENTE:
            raise ErroNegocio(
                f"{data_br(dt_destino)} esta a mais de {DIAS_MAXIMOS_A_FRENTE} dias.",
                "dia_longe_demais",
                status_http=400,
            )
        no_destino = await self.repo.vinculos(dt_de=dt_destino, dt_ate=dt_destino)
        if not no_destino:
            raise ErroNegocio(
                f"{data_br(dt_destino)} esta vazio: nao ha com quem trocar. Para "
                "mover o desafio para um dia vazio, use Trocar a data.",
                "dia_vazio",
                status_http=400,
            )
        b = no_destino[0]

        dt_fim_janela = (
            None if modo_de_teste else await self.repo.fim_da_janela_baixada(dt_hoje)
        )
        for vinculo in (a, b):
            self._exigir_que_pode_sair_do_dia(
                vinculo,
                dt_hoje=dt_hoje,
                dt_fim_janela=dt_fim_janela,
                modo_de_teste=modo_de_teste,
            )

        if not await self.repo.inverter_dias(a, b):
            # ⛔ Algum passo nao achou a linha: os que deram certo nao ficam.
            await self.repo.desfazer()
            raise ErroNegocio(
                "Um dos dois desafios mudou de dia enquanto a pagina estava "
                "aberta. Nada foi trocado; recarregue e tente de novo.",
                "troca_interrompida",
                status_http=409,
            )
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=True,
            mensagem=(
                f"Trocados: o desafio de {data_br(a.dt_dia)} foi para "
                f"{data_br(b.dt_dia)}, e o de {data_br(b.dt_dia)} veio para "
                f"{data_br(a.dt_dia)}."
            ),
        )

    @staticmethod
    def _exigir_que_pode_sair_do_dia(
        vinculo: VinculoDoDia,
        *,
        dt_hoje: date,
        dt_fim_janela: Optional[date],
        modo_de_teste: bool,
    ) -> None:
        """As travas de UM dos desafios de uma troca (ver [inverter_dias]).

        Args:
            dt_fim_janela: o fim da janela baixada; `None` no modo de teste,
                em que ela nao vale.
        """
        dia = data_br(vinculo.dt_dia)
        if vinculo.dt_dia < dt_hoje:
            raise ErroNegocio(
                f"O desafio de {dia} ja foi ao ar: ele e a historia de quem jogou.",
                "dia_ja_jogado",
                status_http=400,
            )
        if vinculo.qt_tentativas:
            raise ErroNegocio(
                f"O desafio de {dia} ja tem {vinculo.qt_tentativas} tentativa(s)."
                + (
                    " Limpe as resolucoes dele antes de troca-lo de dia."
                    if modo_de_teste
                    else " Ele nao sai do dia: tiraria o dia de quem esta jogando."
                ),
                "dia_ja_jogado",
                status_http=400,
            )
        if vinculo.co_curadoria != "aprovado":
            raise ErroNegocio(
                f"O desafio de {dia} nao esta aprovado: so aprovado vai a um dia.",
                "desafio_nao_aprovado",
                status_http=400,
            )
        if dt_fim_janela is not None and na_janela_baixada(
            vinculo.dt_dia, dt_hoje=dt_hoje, dt_fim=dt_fim_janela
        ):
            raise ErroNegocio(
                f"O desafio de {dia} ja pode estar guardado nos aparelhos (o app "
                f"baixa hoje e os {DIAS_DE_CACHE} proximos dias). A troca vale de "
                f"{data_br(dt_fim_janela + timedelta(days=1))} em diante.",
                "dia_ja_baixado",
                status_http=400,
            )

    async def limpar_resolucoes(
        self, id_desafio: UUID, *, dt_hoje: date, modo_de_teste: bool
    ) -> ResultadoDaAcao:
        """⛔ Apaga as tentativas e resolucoes de TODAS as pessoas no dia do desafio.

        So no modo de teste: e o unico ponto do painel que apaga dado de
        alguem. ⛔ Dia ja passado nunca e limpo, nem no `des`.

        ⚠️ **O XP que ja entrou na conta de cada pessoa NAO volta**
        (`progressao.tb001_progressao_usuario`): ele e um total, sem extrato por
        dia de onde se possa subtrair. No `des` isso so infla o XP de quem
        testa.

        Raises:
            ErroNegocio: modo de teste desligado, desafio sem dia, ou dia passado.
        """
        if not modo_de_teste:
            raise ErroNegocio(
                "Limpar resolucoes so existe no modo de teste do painel (banco des).",
                "modo_de_teste_desligado",
                status_http=403,
            )
        vinculo = await self.repo.vinculo_do_desafio(id_desafio)
        if vinculo is None:
            raise ErroNegocio(
                "Este desafio esta sem data: nao ha resolucao para limpar.",
                "desafio_sem_dia",
                status_http=400,
            )
        if vinculo.dt_dia < dt_hoje:
            raise ErroNegocio(
                f"O desafio de {data_br(vinculo.dt_dia)} ja foi ao ar. Dia passado "
                "nao se limpa, nem no modo de teste.",
                "dia_ja_jogado",
                status_http=400,
            )
        contagem = await self.repo.apagar_resolucoes(vinculo.id_desafio_dia)
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=any(contagem.values()),
            mensagem=(
                f"Dia {data_br(vinculo.dt_dia)} limpo: "
                f"{contagem.get('tentativas', 0)} tentativa(s), "
                f"{contagem.get('resolucoes', 0)} resolucao(oes) e "
                f"{contagem.get('xp', 0)} linha(s) de XP apagadas (as reacoes e "
                "as dicas foram junto). O XP ja somado nas contas fica."
            ),
        )

    async def esvaziar(
        self,
        *,
        dt_hoje: date,
        motivo: str,
        confirmado: bool,
        modo_de_teste: bool = False,
    ) -> ResultadoDaAcao:
        """Descarta (⛔ nao apaga) todo desafio do primeiro dia destravado em diante.

        Fora do modo de teste, o primeiro dia destravado e o seguinte ao fim da
        janela baixada. No modo de teste e HOJE, e as resolucoes de cada dia
        sao limpas antes (sem isso o banco recusaria tirar o vinculo).

        Args:
            motivo: o motivo gravado em cada descarte (obrigatorio, RF-DES-012c).
            confirmado: a caixa "entendi" do formulario. ⚠️ A regra mora aqui, e
                nao so no `required` do HTML: um `curl` passa pelo HTML.

        Raises:
            ErroNegocio: sem confirmacao ou sem motivo.
        """
        if not confirmado:
            raise ErroNegocio(
                "Marque a confirmacao: esvaziar descarta todos os desafios do "
                "periodo de uma vez.",
                "sem_confirmacao",
                status_http=400,
            )
        motivo = _motivo_valido(motivo)

        if modo_de_teste:
            dt_de = dt_hoje
        else:
            dt_de = await self.repo.fim_da_janela_baixada(dt_hoje) + timedelta(days=1)

        vinculos = await self.repo.vinculos(dt_de=dt_de)
        # ⛔ Fora do modo de teste, depois da janela, nao ha tentativa. Se houver,
        # algo esta errado no calendario, e parar ANTES de escrever e o certo.
        com_tentativa = [v for v in vinculos if v.qt_tentativas]
        if com_tentativa and not modo_de_teste:
            raise ErroNegocio(
                f"O desafio de {data_br(com_tentativa[0].dt_dia)} tem tentativa e "
                "esta depois da janela baixada. Nada foi esvaziado.",
                "dia_ja_jogado",
                status_http=409,
            )
        for vinculo in vinculos:
            if modo_de_teste:
                # ⚠️ Antes de tirar o vinculo: as tentativas e os "impedido"
                # apontam para ele sem `CASCADE`.
                await self.repo.apagar_resolucoes(vinculo.id_desafio_dia)
            # Um descartado que ainda tinha dia (anterior a 02/10/2026) so sai do
            # dia: descarta-lo de novo trocaria o motivo antigo pelo de hoje.
            if vinculo.co_curadoria != "descartado":
                await self.repo.descartar(vinculo.id_desafio, de_motivo=motivo)
            await self.repo.desagendar(vinculo.id_desafio)
        await self.repo.confirmar()

        if not vinculos:
            return ResultadoDaAcao(
                mudou=False,
                mensagem=f"Nada a esvaziar de {data_br(dt_de)} em diante.",
            )
        return ResultadoDaAcao(
            mudou=True,
            mensagem=(
                f"{len(vinculos)} desafio(s) descartado(s), de {data_br(dt_de)} "
                "em diante (as linhas continuam no banco, com o motivo). Os dias "
                "ficaram livres para a proxima geracao."
            ),
        )
