"""A notificacao do dia seguinte - *"3 pessoas reagiram ao seu desafio de ontem"*
(T079, RF-DES-074 a 074c).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO PROVA, EM TRES CAMADAS
═══════════════════════════════════════════════════════════════════════════

  1. **as contas puras** - o texto nos tres idiomas e, sobretudo, qual dia e
     *"ontem"* para quem esta em cada fuso;
  2. **o servico**, com repositorio e enviador falsos - a ordem entre reservar,
     confirmar e enviar, o token morto e o que ⛔ nao gasta a reserva;
  3. **o SQL**, por leitura de texto - que a visibilidade e a MESMA do quadro e
     que o filtro de fuso ⛔ nao saiu.

⚠️ **O duplo do repositorio HONRA os filtros que o SQL de verdade tem** (o dia e a
lista de offsets). A T078 aprendeu isso na pele: um duplo que devolve tudo o que
tem responde por perguntas que ⛔ nao foram feitas, e um caso passa com a regra
errada.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from api.notificacoes.modelos import CategoriaNotif
from api.notificacoes.reacoes_do_desafio import (
    CATEGORIA_REACOES,
    FRASES,
    HORA_LOCAL_DO_ENVIO,
    SQL_DISPOSITIVOS,
    SQL_PENDENTES,
    SQL_RESERVAR,
    Aparelho,
    PessoaANotificar,
    ServicoNotificacaoDeReacao,
    TokenMorto,
    dados_do_push,
    dia_do_desafio_a_notificar,
    dia_local,
    grupos_por_dia_alvo,
    offsets_ao_meio_dia,
    texto_da_notificacao,
)

# ═══════════════════════════════════════════════════════════════════════════
# Os duplos
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReservaFalsa:
    """Uma linha de `tb008_notificacao_reacao` como o duplo a guarda."""

    id_resolucao: UUID
    qt_pessoa: int
    nu_offset_minuto: int
    qt_dispositivo: int
    dh_envio: Any


class RepoFalso:
    """Repositorio em memoria - e ele **aplica os filtros do SQL de verdade**.

    ⚠️ **O `dia` e os `offsets` filtram**, porque e isso que as consultas fazem.
    Um duplo que ignora o filtro e a razao pela qual quatro mutacoes sobreviveram
    na T078: ele responde por linhas que a consulta ⛔ nao teria trazido.
    """

    def __init__(
        self,
        pendentes_por_dia: Optional[dict[date, list[PessoaANotificar]]] = None,
        aparelhos: Optional[dict[UUID, list[Aparelho]]] = None,
        reservas: Optional[set[UUID]] = None,
        reservas_nao_vistas: Optional[set[UUID]] = None,
    ) -> None:
        self._pendentes = pendentes_por_dia or {}
        self._aparelhos = aparelhos or {}
        #: Resolucoes **ja** notificadas antes desta rodada (outra execucao).
        self.reservadas: set[UUID] = reservas or set()
        #: ⚠️ **A CORRIDA**: linhas gravadas pela outra execucao **depois** de
        #: esta ter lido os pendentes. A consulta ⛔ nao as ve (a leitura ja
        #: passou), e quem as segura e o `ON CONFLICT` no momento de reservar -
        #: que e a unica defesa que existe contra duas execucoes ao mesmo tempo.
        self.reservadas.update(reservas_nao_vistas or set())
        self._invisiveis: set[UUID] = reservas_nao_vistas or set()
        #: O que esta rodada gravou.
        self.gravadas: list[ReservaFalsa] = []
        #: Tokens apagados da `tb005`.
        self.tokens_removidos: list[str] = []
        #: ⚠️ **A ORDEM das operacoes** - e o que prova que o envio ⛔ nao
        #: acontece antes de a reserva estar confirmada.
        self.diario: list[str] = []

    async def pendentes(self, dt_dia: date) -> list[PessoaANotificar]:
        self.diario.append(f"pendentes({dt_dia.isoformat()})")
        # ⚠️ O SQL de verdade ja exclui quem tem linha de notificacao (o
        # `LEFT JOIN ... IS NULL`); o duplo faz o mesmo.
        return [
            p
            for p in self._pendentes.get(dt_dia, [])
            if p.id_resolucao not in self.reservadas
            or p.id_resolucao in self._invisiveis
        ]

    async def dispositivos(
        self, id_usuario: UUID, offsets: list[int]
    ) -> list[Aparelho]:
        self.diario.append("dispositivos")
        return [
            a
            for a in self._aparelhos.get(id_usuario, [])
            if a.offset_minuto in offsets
        ]

    async def reservar(
        self,
        *,
        id_resolucao: UUID,
        qt_pessoa: int,
        nu_offset_minuto: int,
        qt_dispositivo: int,
        dh_envio: Any,
    ) -> bool:
        self.diario.append("reservar")
        # O `ON CONFLICT DO NOTHING`: quem chegou depois ⛔ nao grava nada.
        if id_resolucao in self.reservadas:
            return False
        self.reservadas.add(id_resolucao)
        self.gravadas.append(
            ReservaFalsa(
                id_resolucao=id_resolucao,
                qt_pessoa=qt_pessoa,
                nu_offset_minuto=nu_offset_minuto,
                qt_dispositivo=qt_dispositivo,
                dh_envio=dh_envio,
            )
        )
        return True

    async def desfazer_reserva(self, id_resolucao: UUID) -> None:
        self.diario.append("desfazer_reserva")
        self.reservadas.discard(id_resolucao)
        self.gravadas = [g for g in self.gravadas if g.id_resolucao != id_resolucao]

    async def remover_token(self, token: str) -> None:
        self.diario.append("remover_token")
        self.tokens_removidos.append(token)

    async def confirmar(self) -> None:
        self.diario.append("confirmar")

    async def desfazer(self) -> None:
        self.diario.append("rollback")


@dataclass
class EnviadorFalso:
    """Anota cada envio; `mortos` finge o `UNREGISTERED` do FCM.

    ⚠️ Ele **⛔ nao monta mensagem do FCM nenhuma** - esse e o trabalho do
    enviador real, e quem o cobre e `test_enviador_real_*`. A licao de
    `memory/fonte-falsa-nao-tem-rota` vale aqui: o duplo ⛔ nao prova a rota.
    """

    mortos: set[str] = field(default_factory=set)
    explode: set[str] = field(default_factory=set)
    envios: list[tuple[str, str, dict[str, str], str]] = field(
        default_factory=list
    )

    def __call__(
        self, titulo: str, corpo: str, dados: dict[str, str], token: str
    ) -> str:
        if token in self.explode:
            raise RuntimeError("o FCM respondeu algo inesperado")
        if token in self.mortos:
            raise TokenMorto(token)
        self.envios.append((titulo, corpo, dados, token))
        return f"id-{len(self.envios)}"


def _pessoa(qt_pessoa: int = 3) -> PessoaANotificar:
    """Uma linha pendente com identificadores novos."""
    return PessoaANotificar(
        id_resolucao=uuid4(),
        id_usuario=uuid4(),
        id_desafio=uuid4(),
        qt_pessoa=qt_pessoa,
    )


#: Um instante em que e **meio-dia em Brasilia** (UTC-3): 15:00 UTC.
#:
#: ⚠️ **⛔ Nao e `datetime.now()`.** Relogio injetado apontado para a data real ⛔
#: nao mede nada (`memory/data-de-teste-igual-a-de-hoje`): o caso passaria para
#: sempre, e a mutacao que trocasse a conta do dia sobreviveria.
MEIO_DIA_EM_BRASILIA = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)

#: O `dt_dia` que aquele instante notifica: 21/09, o dia **anterior** ao local.
DIA_ALVO_EM_BRASILIA = date(2026, 9, 21)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O texto
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
def test_o_texto_sai_nos_tres_idiomas(idioma: str) -> None:
    """Os tres idiomas do aplicativo respondem, e com o numero dentro."""
    titulo, corpo = texto_da_notificacao(3, idioma)
    assert titulo == FRASES[idioma]["titulo"]
    assert "3" in corpo


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
def test_uma_pessoa_tem_frase_PROPRIA(idioma: str) -> None:
    """🔒 Singular e plural sao frases diferentes.

    ⚠️ *"1 pessoas reagiram"* e o tipo de erro que faz o produto parecer
    descuidado exatamente no momento bom - e ⛔ nenhum teste de idioma pegaria,
    porque a chave existe nos tres.
    """
    _, uma = texto_da_notificacao(1, idioma)
    _, varias = texto_da_notificacao(2, idioma)
    assert uma != varias
    # ⚠️ **E ⛔ nao basta serem diferentes**: com a condicao do singular trocada
    # por `quantas == 0`, uma pessoa cairia no plural e as duas frases continuariam
    # diferentes entre si (*"1 pessoas reagiram"* × *"2 pessoas reagiram"*). A
    # mutacao sobreviveu assim. Cada uma tem de ser **a sua**.
    assert uma == FRASES[idioma]["uma"]
    assert varias == FRASES[idioma]["varias"].format(quantas=2)
    assert "1" in uma
    # ⛔ O plural ⛔ nao pode ter ficado com o `{quantas}` sem substituir.
    assert "{quantas}" not in varias


def test_idioma_desconhecido_cai_no_INGLES() -> None:
    """Fallback igual ao do aplicativo - duas regras diferentes divergiriam."""
    titulo, corpo = texto_da_notificacao(4, "fr")
    assert (titulo, corpo) == texto_da_notificacao(4, "en")


def test_zero_reacao_NAO_gera_texto() -> None:
    """⛔ *"0 pessoas reagiram"* ⛔ nao chega a ninguem.

    A guarda e a irma do `ck001_pessoa` da `0026`: se uma consulta mudada
    devolvesse zero, o banco recusaria a linha - e aqui a frase morre antes.
    """
    with pytest.raises(ValueError):
        texto_da_notificacao(0, "pt")


def test_nenhuma_frase_usa_travessao_longo() -> None:
    """🔒 A mesma regra dos `.arb` (decisao do dono, 19/08/2026).

    O texto daqui e lido pela pessoa exatamente como os de la, e o cadeado do
    aplicativo ⛔ nao alcanca o servidor.
    """
    for idioma, frases in FRASES.items():
        for chave, frase in frases.items():
            assert "—" not in frase, f"{idioma}.{chave}"
            assert "–" not in frase, f"{idioma}.{chave}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O `data` do push
# ═══════════════════════════════════════════════════════════════════════════


def test_o_push_leva_o_ASSUNTO_e_nao_a_rota() -> None:
    """🔒 ⛔ **Nenhuma chave `rota`** no `data` (RF-DES-109 pelo lado certo).

    O aplicativo navega por `data['rota']`, e uma rota que a versao instalada ⛔
    nao registrou cai na tela de erro do `go_router`. O servidor manda de que se
    trata; quem tem as telas escolhe a tela.
    """
    id_desafio = uuid4()
    dados = dados_do_push(id_desafio, 3)
    assert "rota" not in dados
    assert dados["tipo"] == "reacao_desafio"
    assert dados["id_desafio"] == str(id_desafio)
    # O FCM so aceita string no `data`.
    assert all(isinstance(v, str) for v in dados.values())


# ═══════════════════════════════════════════════════════════════════════════
# 3. Qual dia e "ontem" - a conta que erra calada
# ═══════════════════════════════════════════════════════════════════════════


def test_em_brasilia_ontem_e_o_dia_anterior() -> None:
    """O caso comum: 12h locais de 22/09 notificam o desafio de 21/09."""
    assert dia_local(MEIO_DIA_EM_BRASILIA, -180) == date(2026, 9, 22)
    assert (
        dia_do_desafio_a_notificar(MEIO_DIA_EM_BRASILIA, -180)
        == DIA_ALVO_EM_BRASILIA
    )


def test_em_UTC_MAIS_13_o_dia_alvo_e_o_dia_utc_CORRENTE() -> None:
    """🔒 A armadilha do `hoje_utc - 1`, e a razao de a conta ser local.

    Em UTC+13 o meio-dia local de 23/09 acontece as **23:00 UTC de 22/09**:

      · a conta certa (dia local - 1) da **22/09**, o desafio que a pessoa
        acabou de jogar - e que em UTC ainda esta correndo;
      · `hoje_utc - 1` daria **21/09**, um desafio de anteontem para ela, e o de
        22/09 ⛔ nunca seria notificado.

    ⚠️ E ⛔ nenhum erro apareceria: a notificacao sairia, com o numero de outro
    dia.
    """
    instante = datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc)
    assert dia_local(instante, 780) == date(2026, 9, 23)
    assert dia_do_desafio_a_notificar(instante, 780) == date(2026, 9, 22)
    # ⚠️ O que a conta ingenua daria: `hoje_utc - 1` = 21/09, um dia antes do
    # certo. As duas ⛔ nao coincidem, e e por isso que o caso existe.
    from datetime import timedelta

    conta_ingenua = instante.date() - timedelta(days=1)
    assert conta_ingenua == date(2026, 9, 21)
    assert conta_ingenua != dia_do_desafio_a_notificar(instante, 780)


def test_em_UTC_MENOS_11_a_conta_tambem_fecha() -> None:
    """A outra ponta do mundo: 12h locais de 22/09 = 23:00 UTC de 22/09."""
    instante = datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc)
    assert dia_local(instante, -660) == date(2026, 9, 22)
    assert dia_do_desafio_a_notificar(instante, -660) == date(2026, 9, 21)


def test_a_janela_pega_o_fuso_certo_e_os_de_MEIA_HORA() -> None:
    """Os offsets atendidos as 15:00 UTC sao os de ~12h locais.

    ⚠️ **O fuso de meia hora e o que denuncia a falta de tolerancia**: Terra Nova
    (-210) marca 11:30 quando Brasilia marca 12:00, e sem a janela de 30 minutos
    ⛔ nunca seria atendido - sem erro nenhum, para sempre.
    """
    offsets = offsets_ao_meio_dia(MEIO_DIA_EM_BRASILIA)
    assert -180 in offsets
    assert -210 in offsets
    # ⛔ E ⛔ nao pega quem esta longe do meio-dia.
    assert 0 not in offsets
    assert 180 not in offsets
    # ⚠️ **O vizinho de UMA hora e o que mede a largura da janela.** Com tres
    # horas de diferenca qualquer tolerancia plausivel exclui; foi por isso que a
    # mutacao que abria a janela para 90 minutos **sobreviveu**. UTC-2 marca 13h
    # neste instante, e ⛔ nao pode ser atendido.
    assert -120 not in offsets
    assert -240 not in offsets


def test_a_hora_alvo_e_MEIO_DIA_e_nao_19h() -> None:
    """🔒 RF-DES-074b: as 19h ela chegaria junto do lembrete da chama.

    ⚠️ O numero entra **escrito** aqui, e ⛔ nao lido da constante: ler
    `HORA_LOCAL_DO_ENVIO` para conferi-la faria o caso passar com qualquer valor
    (`memory/teste-nao-se-mede-pela-propria-regua`). O 12 e decisao de produto, e
    o cadeado e contra troca-lo sem pensar.
    """
    assert HORA_LOCAL_DO_ENVIO == 12
    # E a janela de fato cai ao meio-dia: 15:00 UTC atende UTC-3.
    assert -180 in offsets_ao_meio_dia(MEIO_DIA_EM_BRASILIA)
    # ⛔ As 22:00 UTC, UTC-3 esta as 19h - e ⛔ nao e atendido.
    assert -180 not in offsets_ao_meio_dia(
        datetime(2026, 9, 22, 22, 0, tzinfo=timezone.utc)
    )


def test_os_grupos_saem_por_dia_alvo() -> None:
    """Cada offset entra debaixo do **seu** dia alvo."""
    grupos = grupos_por_dia_alvo(MEIO_DIA_EM_BRASILIA)
    assert list(grupos) == [DIA_ALVO_EM_BRASILIA]
    assert sorted(grupos[DIA_ALVO_EM_BRASILIA]) == sorted(
        offsets_ao_meio_dia(MEIO_DIA_EM_BRASILIA)
    )


def test_a_MESMA_janela_pode_ter_DOIS_dias_alvo() -> None:
    """🔒 O mundo tem **26 horas de fusos** - e por isso o agrupamento existe.

    Às 23:00 UTC de 22/09, dois offsets marcam meio-dia em **dias diferentes**:

      · UTC+13 esta as 12:00 de **23/09**  →  dia alvo 22/09
      · UTC-11 esta as 12:00 de **22/09**  →  dia alvo 21/09

    ⚠️ **Este caso nasceu de uma mutacao que sobreviveu**: trocar o offset por `0`
    no calculo do dia deixava a suite verde, porque ⛔ nenhum caso olhava um
    instante com dois dias na janela. E o comentario da funcao afirmava, errado,
    que com o alvo em 12h isso ⛔ nao acontecia.
    """
    instante = datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc)
    grupos = grupos_por_dia_alvo(instante)

    assert 780 in offsets_ao_meio_dia(instante)
    assert -660 in offsets_ao_meio_dia(instante)
    # ⛔ ⛔ Nao e um grupo so.
    assert len(grupos) >= 2
    assert 780 in grupos[date(2026, 9, 22)]
    assert -660 in grupos[date(2026, 9, 21)]


# ═══════════════════════════════════════════════════════════════════════════
# 4. O servico
# ═══════════════════════════════════════════════════════════════════════════


def _servico(repo: RepoFalso, enviador: EnviadorFalso) -> ServicoNotificacaoDeReacao:
    return ServicoNotificacaoDeReacao(repo=repo, enviador=enviador)


@pytest.mark.asyncio
async def test_o_caminho_comum_avisa_uma_vez_e_grava_o_retrato() -> None:
    """Uma pessoa, um aparelho: sai uma notificacao, e a linha guarda o retrato."""
    pessoa = _pessoa(qt_pessoa=3)
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt", -180)]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 1
    assert relatorio.aparelhos == 1
    assert len(enviador.envios) == 1
    titulo, corpo, dados, token = enviador.envios[0]
    assert token == "tok-1"
    assert "3" in corpo
    assert dados["id_desafio"] == str(pessoa.id_desafio)
    # O retrato do envio, que e o que explica a diferenca com o quadro depois.
    assert len(repo.gravadas) == 1
    gravada = repo.gravadas[0]
    assert gravada.qt_pessoa == 3
    assert gravada.nu_offset_minuto == -180
    assert gravada.qt_dispositivo == 1
    assert gravada.dh_envio == MEIO_DIA_EM_BRASILIA


@pytest.mark.asyncio
async def test_a_reserva_e_CONFIRMADA_antes_do_envio() -> None:
    """🔒 A ordem: `reservar` → `confirmar` → enviar.

    ⚠️ **Uma reserva ainda dentro da transacao ⛔ nao impede nada**: a outra
    execucao ⛔ nao a ve. Enviar antes de confirmar abriria a janela em que as
    duas mandam a mesma notificacao - e o log das duas diria sucesso.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt", -180)]},
    )
    enviador = EnviadorFalso()

    # O enviador anota no MESMO diario, para a ordem ser comparavel.
    def enviar(titulo, corpo, dados, token):  # type: ignore[no-untyped-def]
        repo.diario.append("enviar")
        return enviador(titulo, corpo, dados, token)

    await ServicoNotificacaoDeReacao(repo=repo, enviador=enviar).disparar(
        MEIO_DIA_EM_BRASILIA
    )

    assert repo.diario.index("reservar") < repo.diario.index("confirmar")
    assert repo.diario.index("confirmar") < repo.diario.index("enviar")


@pytest.mark.asyncio
async def test_cada_aparelho_le_no_SEU_idioma() -> None:
    """Dois aparelhos da mesma pessoa, idiomas diferentes, textos diferentes.

    ⚠️ O idioma e do **aparelho** (`co_idioma` da `tb005`), e ⛔ nao da conta -
    quem usa o telefone em portugues e o tablet em ingles le cada um no seu.
    """
    pessoa = _pessoa(qt_pessoa=2)
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={
            pessoa.id_usuario: [
                Aparelho("tok-pt", "pt", -180),
                Aparelho("tok-en", "en", -180),
            ]
        },
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    # UMA notificacao (uma pessoa), DOIS aparelhos.
    assert relatorio.enviadas == 1
    assert relatorio.aparelhos == 2
    corpos = {token: corpo for _, corpo, _, token in enviador.envios}
    assert corpos["tok-pt"] != corpos["tok-en"]
    assert corpos["tok-pt"] == FRASES["pt"]["varias"].format(quantas=2)
    assert corpos["tok-en"] == FRASES["en"]["varias"].format(quantas=2)


@pytest.mark.asyncio
async def test_o_offset_gravado_e_o_do_aparelho_EM_USO() -> None:
    """🔒 Dois aparelhos, dois fusos na janela: vale o **primeiro** da ordem.

    ⚠️ A consulta ordena por `dh_atualizacao DESC`, entao `aparelhos[0]` e o
    aparelho que a pessoa usou por ultimo - o telefone, e ⛔ nao o tablet
    esquecido numa gaveta noutro fuso. O `nu_offset_minuto` existe para se
    reconferir a conta do meio-dia; gravar o do aparelho parado responderia pela
    conta errada.

    ⚠️ **Este caso nasceu de uma mutacao que sobreviveu** (`aparelhos[-1]`): com um
    aparelho so, o primeiro e o ultimo sao o mesmo - a funcao estava certa por
    acidente (`memory/funcao-certa-por-acidente`).
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={
            pessoa.id_usuario: [
                # O duplo devolve na ordem em que estao, como o `ORDER BY` faria.
                Aparelho("tok-telefone", "pt", -180),
                Aparelho("tok-tablet", "pt", -210),
            ]
        },
    )
    enviador = EnviadorFalso()

    await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert repo.gravadas[0].nu_offset_minuto == -180


@pytest.mark.asyncio
async def test_quem_JA_foi_avisado_nao_e_avisado_de_novo() -> None:
    """🔒 O teto de uma por desafio (RF-DES-074b), pela reserva perdida.

    ⚠️ Aqui a linha **aparece** como pendente (o cenario e a corrida entre duas
    execucoes: as duas leram antes de qualquer uma gravar), e quem a segura e o
    `ON CONFLICT DO NOTHING`.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt", -180)]},
        # A outra execucao gravou DEPOIS de esta ler os pendentes: a linha ainda
        # aparece na consulta, e quem a segura e o `ON CONFLICT`.
        reservas_nao_vistas={pessoa.id_resolucao},
    )
    enviador = EnviadorFalso()

    # ⚠️ O cenario so vale se a linha **chegou** ao servico: sem isto, o caso
    # provaria a consulta (que e o outro teste) e ⛔ nao a reserva perdida.
    assert await repo.pendentes(DIA_ALVO_EM_BRASILIA) == [pessoa]

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.ja_notificadas == 1
    assert relatorio.enviadas == 0
    assert enviador.envios == []


@pytest.mark.asyncio
async def test_reacao_TARDIA_nao_gera_uma_segunda() -> None:
    """🔒 A consulta ⛔ nao traz quem ja tem linha de notificacao.

    ⚠️ E o caso que a tabela existe para cobrir: mais gente reagiu depois do
    envio, e a contagem mudou. ⛔ **⛔ Nao se compara numero** - se comparasse,
    cada pessoa nova renderia uma notificacao.
    """
    pessoa = _pessoa(qt_pessoa=3)
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt", -180)]},
        reservas={pessoa.id_resolucao},
    )
    enviador = EnviadorFalso()

    # A rodada seguinte ve a MESMA pessoa com mais reacoes...
    maior = PessoaANotificar(
        id_resolucao=pessoa.id_resolucao,
        id_usuario=pessoa.id_usuario,
        id_desafio=pessoa.id_desafio,
        qt_pessoa=7,
    )
    repo._pendentes[DIA_ALVO_EM_BRASILIA] = [maior]  # noqa: SLF001 - duplo

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 0
    assert enviador.envios == []


@pytest.mark.asyncio
async def test_sem_aparelho_na_janela_a_reserva_NAO_e_gasta() -> None:
    """⛔ ⛔ Nao se queima a chance do dia de quem ⛔ nao tem onde receber.

    ⚠️ O aparelho existe, mas esta **noutro fuso** - la ⛔ nao e meio-dia. Se a
    reserva fosse gravada agora, a hora em que o relogio dele chegasse ao
    meio-dia encontraria a linha pronta e ⛔ nao enviaria nada.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        # +180: do outro lado do mundo em relacao a janela de -180/-210.
        aparelhos={pessoa.id_usuario: [Aparelho("tok-longe", "pt", 180)]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.sem_aparelho == 1
    assert relatorio.enviadas == 0
    assert repo.gravadas == []
    assert "reservar" not in repo.diario


@pytest.mark.asyncio
async def test_token_MORTO_sai_da_base_e_devolve_a_chance() -> None:
    """Token morto e o caso comum - e ele ⛔ nao pode gastar o dia da pessoa.

    ⚠️ **Duas coisas num caso so, e elas sao inseparaveis:** o token sai da
    `tb005` (a faxina que o script fazia a mao) e a reserva e **desfeita**, porque
    ninguem recebeu nada. Sem a segunda metade, reinstalar o aplicativo custaria a
    notificacao daquele dia.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-morto", "pt", -180)]},
    )
    enviador = EnviadorFalso(mortos={"tok-morto"})

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.tokens_removidos == 1
    assert repo.tokens_removidos == ["tok-morto"]
    assert relatorio.nenhum_aceitou == 1
    assert relatorio.enviadas == 0
    # A chance voltou: ⛔ nao sobrou linha nenhuma.
    assert repo.gravadas == []
    assert pessoa.id_resolucao not in repo.reservadas


@pytest.mark.asyncio
async def test_um_aparelho_morto_entre_dois_NAO_desfaz_a_reserva() -> None:
    """🔒 A outra metade: alguem recebeu, entao a notificacao **saiu**.

    ⚠️ Este caso separa as duas defesas (`memory/duas-guardas-para-a-mesma-coisa`):
    sem ele, um "desfaz sempre que houver token morto" passaria - e a pessoa com
    dois aparelhos receberia de novo na proxima execucao.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [pessoa]},
        aparelhos={
            pessoa.id_usuario: [
                Aparelho("tok-morto", "pt", -180),
                Aparelho("tok-vivo", "pt", -180),
            ]
        },
    )
    enviador = EnviadorFalso(mortos={"tok-morto"})

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 1
    assert relatorio.aparelhos == 1
    assert relatorio.tokens_removidos == 1
    assert relatorio.nenhum_aceitou == 0
    assert len(repo.gravadas) == 1
    # ⚠️ `qt_dispositivo` e o que foi **enderecado** (2), e ⛔ nao o que aceitou.
    assert repo.gravadas[0].qt_dispositivo == 2


@pytest.mark.asyncio
async def test_uma_pessoa_ruim_NAO_derruba_as_outras() -> None:
    """Um estouro inesperado vira linha no relatorio, e a hora continua.

    ⚠️ Sem isso, um token esquisito no meio da lista cancelaria as notificacoes
    de todo mundo que viesse depois - e a proxima execucao ⛔ nao as recuperaria,
    porque a janela do meio-dia daquelas pessoas ja teria passado.
    """
    ruim, boa = _pessoa(), _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={DIA_ALVO_EM_BRASILIA: [ruim, boa]},
        aparelhos={
            ruim.id_usuario: [Aparelho("tok-explode", "pt", -180)],
            boa.id_usuario: [Aparelho("tok-boa", "pt", -180)],
        },
    )
    enviador = EnviadorFalso(explode={"tok-explode"})

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert len(relatorio.falhas) == 1
    assert str(ruim.id_resolucao) in relatorio.falhas[0]
    assert relatorio.enviadas == 1
    assert [t for _, _, _, t in enviador.envios] == ["tok-boa"]


@pytest.mark.asyncio
async def test_hora_sem_ninguem_e_sucesso_silencioso() -> None:
    """A maior parte das execucoes ⛔ nao acha ninguem, e isso ⛔ nao e erro."""
    repo = RepoFalso()
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 0
    assert relatorio.falhas == []
    assert enviador.envios == []
    # ⚠️ Mas ela **olhou**: o dia alvo aparece no relatorio, e ⛔ nao um vazio.
    assert relatorio.pendentes_por_dia == {DIA_ALVO_EM_BRASILIA.isoformat(): 0}


@pytest.mark.asyncio
async def test_o_dia_ERRADO_nao_traz_ninguem() -> None:
    """🔒 O duplo honra o filtro de dia - e e ele que prova a conta do "ontem".

    A pessoa esta pendente em **21/09**; se o servico pedisse o dia de hoje (ou
    `hoje_utc - 1` de outro fuso), este caso encontraria a lista vazia.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes_por_dia={date(2026, 9, 20): [pessoa]},
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt", -180)]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 0
    assert f"pendentes({DIA_ALVO_EM_BRASILIA.isoformat()})" in repo.diario


# ═══════════════════════════════════════════════════════════════════════════
# 5. O SQL - por leitura de texto
# ═══════════════════════════════════════════════════════════════════════════


def test_a_visibilidade_e_a_MESMA_do_quadro() -> None:
    """🔒 A consulta usa a constante compartilhada, e ⛔ nao uma copia.

    ⚠️ Quem desligou a visibilidade saiu do quadro (RF-DES-077) e ⛔ nao le a
    propria contagem (T078). Avisa-la por push seria contar em segredo - e duas
    definicoes de *"aparece em publico"* divergiriam, com a mais frouxa mandando.
    """
    from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO

    assert CLAUSULA_APARECE_EM_PUBLICO in SQL_PENDENTES
    # O `LEFT JOIN` na progressao, que a clausula exige (alias `g`).
    assert "LEFT JOIN progressao.tb001_progressao_usuario g" in SQL_PENDENTES


def test_a_preferencia_entra_por_NOT_EXISTS() -> None:
    """🔒 Quem nunca abriu a tela de notificacoes continua recebendo.

    ⚠️ Com um `JOIN`, so quem tem linha na `tb006` seria notificado - e a tabela
    so ganha linha quando alguem **mexe** no interruptor. O padrao e ligado, e um
    `JOIN` silenciaria a maioria sem erro nenhum.
    """
    assert "NOT EXISTS" in SQL_PENDENTES
    assert "vw006_preferencia_notificacao" in SQL_PENDENTES
    assert "NOT p.ic_ativo" in SQL_PENDENTES


def test_a_categoria_e_PROPRIA_e_esta_no_vocabulario_da_api() -> None:
    """🔒 `reacoes`, e ⛔ nao `lembrete` (RF-DES-074b).

    E ela tem de existir no `Literal` que a rota de preferencias aceita - senao o
    aplicativo ⛔ nao teria como desligar o que o servidor consulta.
    """
    assert CATEGORIA_REACOES == "reacoes"
    assert CATEGORIA_REACOES in CategoriaNotif.__args__  # type: ignore[attr-defined]
    assert "lembrete" != CATEGORIA_REACOES


def test_quem_JA_tem_notificacao_sai_da_consulta() -> None:
    """🔒 A metade da regra que sobrevive entre execucoes."""
    assert "vw008_notificacao_reacao" in SQL_PENDENTES
    assert "n.id_notificacao_reacao IS NULL" in SQL_PENDENTES


def test_a_consulta_de_aparelhos_FILTRA_pelo_fuso() -> None:
    """🔒 Sem o filtro, o aparelho de outro fuso e acordado de madrugada.

    ⚠️ E o defeito que a RF-DES-074c nomeia, na sua forma menor: a pessoa certa,
    o aparelho errado.
    """
    assert "nu_offset_minuto = ANY(:offsets)" in SQL_DISPOSITIVOS
    # E a ordem que faz `aparelhos[0]` ser o aparelho em uso.
    assert "ORDER BY dh_atualizacao DESC" in SQL_DISPOSITIVOS


def test_a_reserva_e_um_INSERT_que_nao_atualiza_nada() -> None:
    """🔒 `DO NOTHING`, e ⛔ nao `DO UPDATE`.

    ⚠️ Aqui o `DO NOTHING` e o certo - ao contrario do ingestor da `0006`, em que
    ele descartava envio em silencio. ⛔ ⛔ Nao ha nada a atualizar numa
    notificacao que ja saiu, e o conflito significa *"outra execucao chegou
    antes"*.
    """
    assert "ON CONFLICT (id_resolucao) DO NOTHING" in SQL_RESERVAR
    assert "DO UPDATE" not in SQL_RESERVAR


def test_a_contagem_vem_das_REACOES_e_nao_de_outra_tabela() -> None:
    """A frase conta **pessoas**, e cada linha de `tb006_reacao` e uma pessoa."""
    assert "vw006_reacao" in SQL_PENDENTES
    assert "COUNT(x.id_reacao) AS qt_pessoa" in SQL_PENDENTES


# ═══════════════════════════════════════════════════════════════════════════
# 5b. A migracao 0026 - o que o `data-model.md` ⛔ nao confere
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ `test_migracao_bate_com_data_model` compara colunas, constraints e indices
# com o documento - mas ⛔ **nao** le o conteudo dos `CHECK` nem o corpo das
# VIEWs. As duas mutacoes abaixo sobreviveram por esse buraco.


def _migracao_0026() -> str:
    """O **SQL** da migracao que cria a tabela do teto, sem comentario nenhum.

    ⚠️ **Le pelos helpers compartilhados**, e ⛔ nao pelo texto cru do arquivo:
    `sql_da_migracao` recorta as strings passadas a `op.execute` (⛔ fora ficam as
    docstrings e os comentarios de Python) e `sem_comentarios_sql` tira os `--` de
    dentro do SQL. Lendo o arquivo cru, o caso do `SELECT *` **reprovava por causa
    do proprio comentario que explica por que ⛔ nao se usa `SELECT *`**.
    """
    from pathlib import Path

    from tests.unitarios.leitura_de_migracao import (
        sem_comentarios_sql,
        sql_da_migracao,
    )

    raiz = Path(__file__).resolve().parents[2]
    return sem_comentarios_sql(
        sql_da_migracao(
            raiz / "migrations" / "versions" / "0026_notificacao_de_reacao.py"
        )
    )


def test_o_banco_tambem_recusa_notificacao_de_ZERO_reacao() -> None:
    """🔒 `qt_pessoa > 0`, e ⛔ nao `>= 0`.

    ⚠️ E o irmao do `ValueError` de [texto_da_notificacao], e os dois precisam
    existir: o Python impede a **frase**, e o `CHECK` impede a **linha**. Uma
    linha com zero seria a prova de um envio que ⛔ nao devia ter saido - e ela
    ainda gastaria a reserva daquele dia.
    """
    assert "CONSTRAINT ck001_pessoa CHECK (qt_pessoa > 0)" in _migracao_0026()


def test_a_VIEW_da_0026_nomeia_as_colunas_uma_a_uma() -> None:
    """🔒 ⛔ Nenhum `SELECT *` - a licao da `0017`.

    ⚠️ Uma VIEW criada com `*` **congela** a lista de colunas no instante da
    criacao: coluna acrescentada depois ⛔ nao aparece nela, e ⛔ nada avisa. Foi
    exatamente o que aconteceu com a `vw005_dispositivo_notificacao`, que precisou
    ser recriada na `0006` para o `nu_offset_minuto` existir - o mesmo campo de
    que este disparo depende.
    """
    fonte = _migracao_0026()
    assert "CREATE VIEW desafio_dia.vw008_notificacao_reacao" in fonte
    assert "SELECT *" not in fonte
    for coluna in (
        "id_notificacao_reacao",
        "id_resolucao",
        "qt_pessoa",
        "nu_offset_minuto",
        "qt_dispositivo",
        "dh_envio",
        "dh_registro",
    ):
        assert coluna in fonte.split("CREATE VIEW", 1)[1]


# ═══════════════════════════════════════════════════════════════════════════
# 6. O ponto de entrada
# ═══════════════════════════════════════════════════════════════════════════


def test_o_processo_sai_com_ZERO_quando_fez(monkeypatch) -> None:
    """Hora vazia tambem e sucesso - ver o cabecalho do disparo."""
    from api.notificacoes import disparo_de_reacoes as disparo

    async def falso(agora_utc=None):  # type: ignore[no-untyped-def]
        return disparo.RelatorioDoDisparo()

    monkeypatch.setattr(disparo, "disparar", falso)
    assert disparo.main() == disparo.CODIGO_FEZ


def test_o_processo_sai_com_UM_quando_alguma_pessoa_falhou(monkeypatch) -> None:
    """Falha por pessoa e `1`, e ⛔ nao `2`: o trabalho **comecou**."""
    from api.notificacoes import disparo_de_reacoes as disparo

    async def falso(agora_utc=None):  # type: ignore[no-untyped-def]
        relatorio = disparo.RelatorioDoDisparo()
        relatorio.enviadas = 39
        relatorio.falhas.append("resolucao-x: deu errado")
        return relatorio

    monkeypatch.setattr(disparo, "disparar", falso)
    assert disparo.main() == disparo.CODIGO_FALHOU_ALGUMA


def test_o_processo_sai_com_DOIS_quando_nem_comecou(monkeypatch) -> None:
    """Sem banco, sem credencial: `2`.

    ⚠️ A distincao existe para ninguem reiniciar o processo achando que nada foi
    enviado quando 39 pessoas ja receberam.
    """
    from api.notificacoes import disparo_de_reacoes as disparo

    async def explode(agora_utc=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("DATABASE_URL ausente")

    monkeypatch.setattr(disparo, "disparar", explode)
    assert disparo.main() == disparo.CODIGO_NEM_COMECOU


@pytest.fixture
def espiao_do_banco(monkeypatch):
    """Troca a `SessaoLocal` real por uma que so ANOTA que foi aberta e para.

    ⚠️ Ela levanta [BancoAberto] em vez de conectar: o que estes casos medem e
    **se** o disparo chegou ao banco, e ⛔ nunca o que ele faria la dentro.
    """
    import api.nucleo.banco as banco

    aberturas: list[str] = []

    def sessao_espia():  # type: ignore[no-untyped-def]
        aberturas.append("abriu")
        raise BancoAberto()

    monkeypatch.setattr(banco, "SessaoLocal", sessao_espia)
    return aberturas


class BancoAberto(Exception):
    """Sinal do [espiao_do_banco]: o disparo tentou abrir a sessao."""


def test_SEM_credencial_o_disparo_sai_com_DOIS_e_NEM_ABRE_o_banco(
    monkeypatch, espiao_do_banco
) -> None:
    """🔒 Credencial esquecida e **2** desde a primeira hora, e ⛔ nenhuma reserva.

    ⚠️ **O defeito que este caso trava (achado em 22/09/2026):** a credencial so
    era lida dentro do envio de cada pessoa, e ali a reserva da `tb008` ja estava
    confirmada. Cada pessoa da hora perdia o aviso do dia, a saida era **1** e, na
    hora vazia, **0** - o servico mal configurado passava por saudavel.

    ⚠️ **"Nem abre o banco" e a prova de que nada foi reservado**: sem sessao ⛔
    nao ha `INSERT` possivel.
    """
    from api.configuracao import configuracoes
    from api.notificacoes import disparo_de_reacoes as disparo

    monkeypatch.setattr(configuracoes, "FIREBASE_CREDENTIALS", "")

    assert disparo.main() == disparo.CODIGO_NEM_COMECOU
    assert espiao_do_banco == []


def test_a_mensagem_de_credencial_ausente_NOMEIA_a_variavel(monkeypatch) -> None:
    """O log do Railway precisa dizer o que fazer, e ⛔ nao o recado da API.

    ⚠️ A mensagem original (*"Verificacao de identidade indisponivel"*) foi
    escrita para responder 401 sem vazar infra; num servico de cron ela manda
    procurar o defeito no lugar errado.
    """
    from api.configuracao import configuracoes
    from api.notificacoes import disparo_de_reacoes as disparo

    monkeypatch.setattr(configuracoes, "FIREBASE_CREDENTIALS", "")

    with pytest.raises(RuntimeError, match="FIREBASE_CREDENTIALS"):
        disparo.conferir_credencial_do_firebase()


def test_COM_credencial_o_disparo_SEGUE_para_o_banco(
    monkeypatch, espiao_do_banco
) -> None:
    """O controle do caso acima: a conferencia ⛔ nao pode barrar o caminho bom.

    ⚠️ Sem este caso, uma conferencia que recusasse **sempre** passaria no de
    cima - e nenhuma notificacao sairia nunca, com saida 2 toda hora.
    """
    from api.notificacoes import disparo_de_reacoes as disparo

    monkeypatch.setattr(
        "api.nucleo.seguranca_firebase.garantir_app_firebase",
        lambda: "app-falso",
    )

    with pytest.raises(BancoAberto):
        asyncio.run(disparo.disparar())
    assert espiao_do_banco == ["abriu"]


def test_o_disparo_roda_de_HORA_em_hora_no_railway() -> None:
    """🔒 O cron do servico novo, e a imagem que ele reusa.

    ⚠️ **A frequencia e a tolerancia sao uma coisa so**: a janela de 30 minutos de
    `TOLERANCIA_EM_MINUTOS` cobre o dia sem buraco **porque** o cron e de hora em
    hora. Trocar um sem o outro deixaria fusos sem atendimento (cron mais raro) ou
    entregaria duas vezes (janela larga demais).

    ⚠️ E a imagem e a da **API**, ⛔ nao a do job: e ela que tem `firebase-admin`.
    """
    import json
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    config = json.loads(
        (raiz / "railway.notificacoes.json").read_text(encoding="utf-8")
    )
    assert config["deploy"]["cronSchedule"] == "0 * * * *"
    assert config["build"]["dockerfilePath"] == "Dockerfile"
    assert (
        config["deploy"]["startCommand"]
        == "python -m api.notificacoes.disparo_de_reacoes"
    )
    # ⛔ Terminar e sucesso: ⛔ nao ha nada a reiniciar.
    assert config["deploy"]["restartPolicyType"] == "NEVER"


# ═══════════════════════════════════════════════════════════════════════════
# 7. O ENVIADOR REAL - o duplo nunca monta mensagem do FCM
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Estes casos existem por causa da licao da T078**
# (`memory/fonte-falsa-nao-tem-rota`): quatro mutacoes sobreviveram la porque o
# duplo devolvia o corpo direto e ⛔ nunca montava a requisicao. Aqui e o mesmo
# risco: trocar `token=token` por outra coisa, ou esquecer a conversao do `data`,
# deixaria a suite **inteira** verde e apareceria so no aparelho.


@pytest.fixture
def fcm_espiao(monkeypatch):
    """Troca o `messaging.send` por um espiao e dispensa a credencial.

    ⚠️ **As excecoes continuam sendo as DE VERDADE** (`messaging.UnregisteredError`
    e irmas): e a conversao delas que esta sob teste, e uma excecao inventada aqui
    provaria apenas que o `except` pega o que eu escolhi que ele pegasse.
    """
    from firebase_admin import messaging

    from api.notificacoes import disparo_de_reacoes as disparo

    enviadas: list[Any] = []
    erro_a_levantar: dict[str, Optional[BaseException]] = {"erro": None}

    def send_falso(mensagem, app=None, dry_run=False):  # type: ignore[no-untyped-def]
        if erro_a_levantar["erro"] is not None:
            raise erro_a_levantar["erro"]
        enviadas.append(mensagem)
        return "id-do-fcm"

    monkeypatch.setattr(messaging, "send", send_falso)
    monkeypatch.setattr(
        "api.nucleo.seguranca_firebase.garantir_app_firebase",
        lambda: "app-falso",
    )
    return disparo, enviadas, erro_a_levantar


def test_o_enviador_real_monta_a_mensagem_PARA_O_TOKEN(fcm_espiao) -> None:
    """🔒 Titulo, corpo, `data` e - sobretudo - o **token** chegam ao FCM.

    ⚠️ `token=` e o que faz deste o primeiro envio **direcionado** do projeto.
    Com `topic=` no lugar dele a mensagem iria para todos os inscritos, e o texto
    diria a cada um o numero de outra pessoa.
    """
    disparo, enviadas, _ = fcm_espiao

    id_mensagem = disparo.enviar_para_token(
        "O seu desafio de ontem",
        "3 pessoas reagiram a sua solucao.",
        {"tipo": "reacao_desafio", "qt_pessoa": "3"},
        "tok-real",
    )

    assert id_mensagem == "id-do-fcm"
    assert len(enviadas) == 1
    mensagem = enviadas[0]
    assert mensagem.token == "tok-real"
    # ⛔ Nem topico nem condicao: isto ⛔ nao e broadcast.
    assert mensagem.topic is None
    assert mensagem.condition is None
    # ⚠️ E ⛔ nao e `fid`: o `firebase-admin` 7.x sugere trocar `token` por `fid`,
    # mas o que a `tb005` guarda e o **registration token**, e ⛔ nao o Firebase
    # Installation ID - que o aplicativo nem reporta. Ver o comentario no
    # enviador real.
    assert getattr(mensagem, "fid", None) is None
    assert mensagem.notification.title == "O seu desafio de ontem"
    assert mensagem.notification.body == "3 pessoas reagiram a sua solucao."
    # O FCM so aceita string no `data`.
    assert mensagem.data == {"tipo": "reacao_desafio", "qt_pessoa": "3"}
    assert all(isinstance(v, str) for v in mensagem.data.values())


def test_o_enviador_real_CONVERTE_o_data_para_string(fcm_espiao) -> None:
    """🔒 O FCM recusa `data` com valor que ⛔ nao seja string.

    ⚠️ **Este caso nasceu de uma mutacao que sobreviveu**: trocar
    `{k: str(v) ...}` por `data=dados` deixava a suite verde, porque todo caso
    passava dicionario ja de strings. A conversao e um **cinto** - quem monta o
    `data` hoje ja converte -, e cinto so se prova com o valor que ele existe para
    pegar.
    """
    disparo, enviadas, _ = fcm_espiao

    disparo.enviar_para_token("t", "c", {"qt_pessoa": 3}, "tok-real")

    assert enviadas[0].data == {"qt_pessoa": "3"}


def test_token_nao_registrado_vira_TokenMorto(fcm_espiao) -> None:
    """O caso comum: reinstalar o aplicativo gira o token."""
    from firebase_admin import messaging

    disparo, _, erro = fcm_espiao
    erro["erro"] = messaging.UnregisteredError("esse aparelho nao existe mais")

    with pytest.raises(TokenMorto):
        disparo.enviar_para_token("t", "c", {}, "tok-morto")


def test_token_de_OUTRO_projeto_tambem_vira_TokenMorto(fcm_espiao) -> None:
    """Um token do `des` gravado no banco do `prd` ⛔ nunca vai funcionar aqui.

    ⚠️ Sem isto, aquela pessoa gastaria a reserva do dia todos os dias por um
    token que ⛔ nao e nosso - e o log diria *"enviado"*.
    """
    from firebase_admin import messaging

    disparo, _, erro = fcm_espiao
    erro["erro"] = messaging.SenderIdMismatchError("token de outro remetente")

    with pytest.raises(TokenMorto):
        disparo.enviar_para_token("t", "c", {}, "tok-de-outro")


def test_argumento_INVALIDO_nao_apaga_token_nenhum(fcm_espiao) -> None:
    """🔒 `InvalidArgumentError` ⛔ **NAO** e token morto, e a distincao e o caso.

    ⚠️ Ela tambem aparece quando o **payload** esta errado - e ai apagar o token
    destruiria a base de tokens por um defeito NOSSO, um por hora, sem que nada
    denunciasse. O erro sobe como esta, cai em `falhas` e o log mostra qual foi.
    """
    from firebase_admin import exceptions as fb_exc

    disparo, _, erro = fcm_espiao
    erro["erro"] = fb_exc.InvalidArgumentError("payload invalido")

    with pytest.raises(fb_exc.InvalidArgumentError):
        disparo.enviar_para_token("t", "c", {}, "tok-bom")


# ═══════════════════════════════════════════════════════════════════════════
# 8. O REPOSITORIO REAL - o duplo do servico nao passa por aqui
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Estes casos existem porque uma mutacao sobreviveu a tudo o que estava
# escrito:** trocar `return bool(resultado.rowcount)` por `return True` deixava a
# suite **inteira** verde. O `RepoFalso` implementa a sua propria reserva - ele
# ⛔ nunca executa este metodo -, e ⛔ nao ha banco em teste unitario.
#
# ⚠️ E o defeito seria o pior possivel: **toda** execucao acharia que reservou, e
# duas rodadas simultaneas mandariam a mesma notificacao duas vezes - justamente o
# que o `UNIQUE` existe para impedir. O log das duas diria sucesso.
#
# A licao e a de `memory/fonte-falsa-nao-tem-rota`, na sua outra ponta: o duplo
# ⛔ nao prova o codigo que ele substitui.


class ResultadoFalso:
    """O que o SQLAlchemy devolve de um `execute`, no que este codigo usa."""

    def __init__(self, rowcount: int = 0, linhas: Optional[list[dict]] = None):
        self.rowcount = rowcount
        self._linhas = linhas or []

    def mappings(self):  # type: ignore[no-untyped-def]
        return self

    def all(self):  # type: ignore[no-untyped-def]
        return self._linhas


class SessaoFalsa:
    """Uma `AsyncSession` de mentira que **anota o SQL e os parametros**."""

    def __init__(self, resultado: Optional[ResultadoFalso] = None):
        self.resultado = resultado or ResultadoFalso()
        self.chamadas: list[tuple[str, dict]] = []

    async def execute(self, sql, parametros=None):  # type: ignore[no-untyped-def]
        self.chamadas.append((str(sql), parametros or {}))
        return self.resultado

    async def commit(self) -> None:
        self.chamadas.append(("COMMIT", {}))

    async def rollback(self) -> None:
        self.chamadas.append(("ROLLBACK", {}))


def _repo_real(sessao: SessaoFalsa):  # type: ignore[no-untyped-def]
    from api.notificacoes.reacoes_do_desafio import RepositorioNotificacaoDeReacao

    return RepositorioNotificacaoDeReacao(sessao)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_a_reserva_real_devolve_FALSO_quando_nada_foi_inserido() -> None:
    """🔒 `rowcount == 0` significa *"outra execucao chegou antes"*.

    ⚠️ **E o unico sinal que existe.** O `ON CONFLICT DO NOTHING` ⛔ nao levanta
    erro e ⛔ nao devolve linha: sem ler o `rowcount`, o conflito e
    indistinguivel de uma insercao bem-sucedida.
    """
    sessao = SessaoFalsa(ResultadoFalso(rowcount=0))

    reservou = await _repo_real(sessao).reservar(
        id_resolucao=uuid4(),
        qt_pessoa=3,
        nu_offset_minuto=-180,
        qt_dispositivo=1,
        dh_envio=MEIO_DIA_EM_BRASILIA,
    )

    assert reservou is False


@pytest.mark.asyncio
async def test_a_reserva_real_devolve_VERDADE_quando_gravou() -> None:
    """A outra metade - e ela e o que impede *"nunca reserva"* de passar."""
    sessao = SessaoFalsa(ResultadoFalso(rowcount=1))

    reservou = await _repo_real(sessao).reservar(
        id_resolucao=uuid4(),
        qt_pessoa=3,
        nu_offset_minuto=-180,
        qt_dispositivo=1,
        dh_envio=MEIO_DIA_EM_BRASILIA,
    )

    assert reservou is True
    # ⚠️ E os cinco valores do retrato chegaram ao SQL, com os nomes que ele usa.
    _, parametros = sessao.chamadas[0]
    assert parametros["qt_pessoa"] == 3
    assert parametros["nu_offset_minuto"] == -180
    assert parametros["qt_dispositivo"] == 1
    assert parametros["dh_envio"] == MEIO_DIA_EM_BRASILIA


@pytest.mark.asyncio
async def test_a_consulta_real_leva_o_dia_e_a_CATEGORIA() -> None:
    """🔒 O `:categoria` sai da constante, e ⛔ não fica sem valor.

    ⚠️ Um parametro nomeado que ⛔ nao recebe valor levanta erro **no banco**, e
    ⛔ nao aqui - ou seja, so na primeira execucao real, de hora em hora, num
    processo que ninguem esta olhando.
    """
    sessao = SessaoFalsa(ResultadoFalso(linhas=[]))

    await _repo_real(sessao).pendentes(DIA_ALVO_EM_BRASILIA)

    _, parametros = sessao.chamadas[0]
    assert parametros["dt_dia"] == DIA_ALVO_EM_BRASILIA
    assert parametros["categoria"] == CATEGORIA_REACOES


@pytest.mark.asyncio
async def test_a_consulta_real_de_aparelhos_leva_a_LISTA_de_offsets() -> None:
    """A lista viaja como parametro - ⛔ nunca interpolada no texto do SQL."""
    sessao = SessaoFalsa(ResultadoFalso(linhas=[]))
    id_usuario = uuid4()

    await _repo_real(sessao).dispositivos(id_usuario, [-180, -210])

    _, parametros = sessao.chamadas[0]
    assert parametros["id_usuario"] == id_usuario
    assert parametros["offsets"] == [-180, -210]
