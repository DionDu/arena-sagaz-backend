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
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from api.desafios.painel.repositorio import RepositorioPainel
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
    """As tres acoes do painel, com as regras aplicadas antes do banco."""

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

    async def descartar(self, id_desafio: UUID, *, motivo: str) -> ResultadoDaAcao:
        """Descarta com motivo, e **tira do calendario** se estava agendado.

        Raises:
            ErroNegocio: quando o motivo veio vazio (RF-DES-012c).
        """
        motivo = (motivo or "").strip()
        if not motivo:
            raise ErroNegocio(
                "Descartar exige um motivo: e ele que ensina o gerador a nao "
                "repetir a familia de posicao que saiu ruim.",
                "motivo_ausente",
                status_http=400,
            )
        motivo = motivo[:MAX_MOTIVO]

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
            ErroNegocio: dia no passado, longe demais, ou desafio nao aprovado.

        ⚠️ **Hoje e aceito.** Agendar para o proprio dia e exatamente o que a fila
        curta exige quando o dono chega tarde — recusar seria transformar um
        atraso de operacao num dia vazio.
        """
        if dt_dia < dt_hoje:
            raise ErroNegocio(
                f"{dt_dia} ja passou. O desafio de um dia encerrado nao seria "
                "servido a ninguem.",
                "dia_no_passado",
                status_http=400,
            )
        if (dt_dia - dt_hoje).days > DIAS_MAXIMOS_A_FRENTE:
            raise ErroNegocio(
                f"{dt_dia} esta a mais de {DIAS_MAXIMOS_A_FRENTE} dias. Aprovar "
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

        mudou = await self.repo.agendar(id_desafio, dt_dia=dt_dia)
        await self.repo.confirmar()
        return ResultadoDaAcao(
            mudou=mudou, mensagem=f"Desafio agendado para {dt_dia.isoformat()}."
        )

    async def desagendar(self, id_desafio: UUID) -> ResultadoDaAcao:
        """Tira o desafio do calendario, mantendo a aprovacao.

        ⚠️ E o passo que **libera um dia ocupado**: sem ele, trocar dois desafios
        de data seria impossivel, porque `un001_dia` recusa o segundo enquanto o
        primeiro nao sai.
        """
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
