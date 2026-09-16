"""O BOTAO QUE GERA DESAFIOS, do proprio painel de curadoria (T040c).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 16/09/2026, depois de eu entregar o lancador de linha de comando, o dono
respondeu:

> *"O comando `.venv\\Scripts\\python scripts\\rodar_job_local.py --dias 14` eu nao
> vou conseguir memorizar. Ele precisava estar dentro do painel de curadoria."*

⚠️ **E ele esta certo, e o motivo e o proprio desenho do painel.** A ferramenta
existe para ele *"abrir uma vez por dia"* e decidir; um passo que exige decorar
um caminho de venv e um nome de script nao e um passo da ferramenta, e sim um
imposto sobre usa-la.

═══════════════════════════════════════════════════════════════════════════
⛔ A TRAVA: EM PRODUCAO ESTE BOTAO NAO EXISTE
═══════════════════════════════════════════════════════════════════════════

O painel e servido pela API. ⛔ **Um botao que dispara vinte minutos de CPU dentro
do processo que atende o aplicativo e um risco que nao se corre por conveniencia**
— e o job foi feito para ser um container proprio, que sobe, trabalha e morre,
justamente para nao disputar recurso com quem esta jogando.

Entao o botao aparece **somente** quando `PAINEL_PODE_GERAR` esta ligada. O
`painel-local.cmd` a liga; o Railway nao. ⚠️ **Ausente, o botao nao e desenhado e
a rota recusa** — as duas coisas, porque esconder o botao sem fechar a rota e
segurança de fachada.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE UMA THREAD, E NAO `await`
═══════════════════════════════════════════════════════════════════════════

O job leva minutos (1.360 s para quatro dias, medido em 16/09/2026). ⛔ Nenhum
navegador espera isso, e segurar o request bloquearia o painel inteiro.

Entao a rota **dispara e volta na hora**, e a pagina passa a mostrar o estado da
execucao. ⚠️ **Thread, e nao `asyncio.create_task`:** o job e trabalho de CPU com
`asyncio.run` proprio la dentro; uma corrotina no mesmo laco travaria o servidor
por vinte minutos sem atender mais ninguem.

⚠️ **E o painel nao tem JavaScript** (decisao de `pagina.py`), entao nao ha
atualizacao automatica: a pagina diz que esta rodando, e o dono recarrega quando
quiser. Para uma tarefa de vinte minutos isso e suficiente, e mantem a
propriedade de que *"o que esta na tela e o que esta no banco"*.
"""

from __future__ import annotations

import os
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

#: A variavel que liga o botao. ⛔ Ausente = o botao nao existe e a rota recusa.
ENV_PODE_GERAR = "PAINEL_PODE_GERAR"

#: Quantos dias o botao oferece. ⚠️ Lista curta de propósito: um campo livre
#: convidaria a pedir 30 dias num clique, e o job leva minutos **por dia**.
DIAS_OFERECIDOS = (7, 14)


def pode_gerar() -> bool:
    """O botao esta ligado neste processo?

    ⚠️ Le o ambiente **a cada chamada**, e nao uma vez no import: assim um teste
    pode ligar e desligar com `monkeypatch`, e o valor nao fica preso ao momento
    em que o modulo foi carregado.
    """
    return os.environ.get(ENV_PODE_GERAR, "").strip() not in ("", "0", "false", "False")


@dataclass
class EstadoDaExecucao:
    """O que a ultima execucao disparada pelo painel esta fazendo.

    ⚠️ **Mora na memoria do processo, e isso basta.** O resultado de verdade do
    job esta no banco, e e a fila do painel que o mostra; isto aqui so responde
    *"ja acabou?"*. ⛔ Persisti-lo seria inventar uma tabela para um dado que
    perde o sentido quando o processo reinicia.
    """

    #: `None` enquanto nunca rodou nesta sessao.
    dh_inicio: Optional[datetime] = None
    dh_fim: Optional[datetime] = None
    nu_dias: Optional[int] = None
    codigo_de_saida: Optional[int] = None
    erro: Optional[str] = None
    _trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def rodando(self) -> bool:
        """Comecou e ainda nao terminou."""
        return self.dh_inicio is not None and self.dh_fim is None

    @property
    def resumo(self) -> str:
        """Uma linha para a pagina."""
        if self.dh_inicio is None:
            return "nunca executado nesta sessao"
        quando = self.dh_inicio.strftime("%H:%M:%S")
        if self.rodando:
            minutos = (datetime.now(timezone.utc) - self.dh_inicio).total_seconds() / 60
            return (
                f"rodando desde {quando} ({minutos:.0f} min) — "
                f"{self.nu_dias} dia(s). Recarregue a pagina para ver o fim."
            )
        if self.erro:
            return f"⛔ falhou as {quando}: {self.erro}"
        duracao = (self.dh_fim - self.dh_inicio).total_seconds() / 60  # type: ignore[operator]
        # ⚠️ O codigo de saida vem junto: `1` quer dizer *"fez, e algo divergiu"*
        # — um dia descoberto, por exemplo — e nao *"nao fez nada"*.
        return (
            f"terminou as {self.dh_fim.strftime('%H:%M:%S')} "  # type: ignore[union-attr]
            f"({duracao:.0f} min, {self.nu_dias} dia(s), saida "
            f"{self.codigo_de_saida})"
        )


#: O estado da execucao deste processo. Um so, porque o job tambem e um so.
#:
#: ⛔ **Duas execucoes ao mesmo tempo escreveriam nos mesmos dias**, e a segunda
#: perderia tudo no `un001_dia` depois de gastar os minutos caros. `disparar`
#: recusa enquanto a anterior nao termina.
ESTADO = EstadoDaExecucao()


class JaEstaRodando(RuntimeError):
    """Uma execucao ja esta em andamento neste processo."""


class GeracaoDesligada(RuntimeError):
    """`PAINEL_PODE_GERAR` nao esta ligada neste processo."""


def _rodar(nu_dias: int, principal: Callable[[], int]) -> None:
    """O corpo da thread: roda o job e anota o desfecho.

    ⚠️ **Captura tudo**, e nao so `Exception`: uma thread que morre com o erro
    preso nela deixaria o painel dizendo *"rodando"* para sempre, e o dono
    esperaria por algo que ja acabou.
    """
    try:
        ESTADO.codigo_de_saida = principal()
    except BaseException as erro:  # noqa: BLE001
        ESTADO.erro = f"{type(erro).__name__}: {erro}"
        traceback.print_exc()
    finally:
        ESTADO.dh_fim = datetime.now(timezone.utc)


def disparar(nu_dias: int, *, principal: Optional[Callable[[], int]] = None) -> None:
    """Comeca uma execucao do job em segundo plano.

    Args:
        nu_dias: quantos dias cobrir.
        principal: a funcao a chamar; o padrao e a do job de verdade.
            ⚠️ Injetavel para teste — sem isso, provar a regra de *"uma de cada
            vez"* exigiria rodar o job inteiro.

    Raises:
        GeracaoDesligada: `PAINEL_PODE_GERAR` ausente.
        JaEstaRodando: ha execucao em andamento.
    """
    if not pode_gerar():
        raise GeracaoDesligada(
            f"{ENV_PODE_GERAR} nao esta ligada neste processo — "
            "o botao de gerar so existe no painel local."
        )

    with ESTADO._trava:
        if ESTADO.rodando:
            raise JaEstaRodando(ESTADO.resumo)
        ESTADO.dh_inicio = datetime.now(timezone.utc)
        ESTADO.dh_fim = None
        ESTADO.nu_dias = nu_dias
        ESTADO.codigo_de_saida = None
        ESTADO.erro = None

    alvo = principal or _principal_do_job(nu_dias)
    # ⚠️ `daemon=True`: fechar o servidor nao fica preso esperando o job. O
    # trabalho ja gravado no banco continua valendo — cada dia e uma transacao.
    threading.Thread(target=_rodar, args=(nu_dias, alvo), daemon=True).start()


def _principal_do_job(nu_dias: int) -> Callable[[], int]:
    """A funcao que roda o job de verdade, com a fila esticada.

    ⚠️ **Importado aqui dentro**, e nao no topo: o `job` puxa os motores e o
    runtime de inferencia, e a API nao precisa de nada disso para servir o
    aplicativo. Importar no topo faria todo processo da API carregar o
    laboratorio inteiro para oferecer um botao que quase sempre esta desligado.
    """

    def executar() -> int:
        from job.__main__ import ENV_DIAS_A_COBRIR, principal

        os.environ[ENV_DIAS_A_COBRIR] = str(nu_dias)
        return principal()

    return executar
