"""A notificacao do dia seguinte - *"3 pessoas reagiram ao seu desafio de ontem"*
(T079, RF-DES-074 a 074c).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO PROVA, EM TRES CAMADAS
═══════════════════════════════════════════════════════════════════════════

  1. **as contas puras** - o texto nos tres idiomas, qual dia e *"ontem"* para
     quem esta em cada fuso, a janela do meio-dia e o *"hoje / ontem /
     anteontem"* do titulo;
  2. **o servico**, com repositorio e enviador falsos - a vez de cada pessoa
     pelo fuso DELA, a ordem entre reservar, confirmar e enviar, o token morto e
     o que nao gasta a reserva;
  3. **o SQL**, por leitura de texto - que a visibilidade e a MESMA do quadro e
     que o fuso vem do aparelho usado por ultimo.

⚠️ **O duplo do repositorio HONRA os filtros que o SQL de verdade tem** (os dias
pedidos e a reserva ja gravada). A T078 aprendeu isso na pele: um duplo que
devolve tudo o que tem responde por perguntas que nao foram feitas, e um caso
passa com a regra errada.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from api.notificacoes.modelos import CategoriaNotif
from api.notificacoes.reacoes_do_desafio import (
    CATEGORIA_REACOES,
    FRASES,
    HORA_LOCAL_DO_ENVIO,
    QUANDO_POR_DIAS,
    SQL_DISPOSITIVOS,
    SQL_PENDENTES,
    SQL_RESERVAR,
    Aparelho,
    PessoaANotificar,
    ServicoNotificacaoDeReacao,
    TokenMorto,
    dados_do_push,
    deve_avisar_agora,
    dia_do_desafio_a_notificar,
    dia_local,
    dias_candidatos,
    na_janela_do_envio,
    quando_foi_resolvido,
    texto_da_notificacao,
)

# ═══════════════════════════════════════════════════════════════════════════
# Os instantes de referencia
# ═══════════════════════════════════════════════════════════════════════════

#: Um instante em que e **meio-dia em Brasilia** (UTC-3): 15:00 UTC.
#:
#: ⚠️ **Nao e `datetime.now()`.** Relogio injetado apontado para a data real nao
#: mede nada (`memory/data-de-teste-igual-a-de-hoje`): o caso passaria para
#: sempre, e a mutacao que trocasse a conta do dia sobreviveria.
MEIO_DIA_EM_BRASILIA = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)

#: O `dt_dia` que aquele instante notifica: 21/09, o dia **anterior** ao local.
DIA_ALVO_EM_BRASILIA = date(2026, 9, 21)

#: Uma resolucao das 15h de Brasilia de 21/09 - *"ontem"* ao meio-dia de 22/09.
RESOLVIDO_ONTEM_EM_BRASILIA = datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc)

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

    ⚠️ **Os `dias` filtram**, porque e isso que a consulta faz. Um duplo que
    ignora o filtro e a razao pela qual quatro mutacoes sobreviveram na T078: ele
    responde por linhas que a consulta nao teria trazido.

    ⚠️ **E os aparelhos NAO sao filtrados por fuso** - a consulta de verdade
    tambem nao filtra mais (decisao do dono, 13/10/2026).
    """

    def __init__(
        self,
        pendentes: Optional[list[PessoaANotificar]] = None,
        aparelhos: Optional[dict[UUID, list[Aparelho]]] = None,
        reservas: Optional[set[UUID]] = None,
        reservas_nao_vistas: Optional[set[UUID]] = None,
    ) -> None:
        self._pendentes = pendentes or []
        self._aparelhos = aparelhos or {}
        #: Resolucoes **ja** notificadas antes desta rodada (outra execucao).
        self.reservadas: set[UUID] = reservas or set()
        #: ⚠️ **A CORRIDA**: linhas gravadas pela outra execucao **depois** de
        #: esta ter lido os pendentes. A consulta nao as ve (a leitura ja
        #: passou), e quem as segura e o `ON CONFLICT` no momento de reservar -
        #: que e a unica defesa que existe contra duas execucoes ao mesmo tempo.
        self.reservadas.update(reservas_nao_vistas or set())
        self._invisiveis: set[UUID] = reservas_nao_vistas or set()
        #: O que esta rodada gravou.
        self.gravadas: list[ReservaFalsa] = []
        #: Tokens apagados da `tb005`.
        self.tokens_removidos: list[str] = []
        #: ⚠️ **A ORDEM das operacoes** - e o que prova que o envio nao
        #: acontece antes de a reserva estar confirmada.
        self.diario: list[str] = []
        #: Os dias que o servico pediu, chamada a chamada.
        self.dias_pedidos: list[list[date]] = []

    async def pendentes(self, dias: list[date]) -> list[PessoaANotificar]:
        self.diario.append("pendentes")
        self.dias_pedidos.append(list(dias))
        # ⚠️ O SQL de verdade so traz os dias pedidos e ja exclui quem tem linha
        # de notificacao (o `LEFT JOIN ... IS NULL`); o duplo faz o mesmo.
        return [
            p
            for p in self._pendentes
            if p.dt_dia in dias
            and (
                p.id_resolucao not in self.reservadas
                or p.id_resolucao in self._invisiveis
            )
        ]

    async def dispositivos(self, id_usuario: UUID) -> list[Aparelho]:
        self.diario.append("dispositivos")
        return list(self._aparelhos.get(id_usuario, []))

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
        # O `ON CONFLICT DO NOTHING`: quem chegou depois nao grava nada.
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

    ⚠️ Ele **nao monta mensagem do FCM nenhuma** - esse e o trabalho do
    enviador real, e quem o cobre e `test_enviador_real_*`. A licao de
    `memory/fonte-falsa-nao-tem-rota` vale aqui: o duplo nao prova a rota.
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


def _pessoa(
    qt_pessoa: int = 3,
    *,
    dt_dia: date = DIA_ALVO_EM_BRASILIA,
    offset: int = -180,
    dh_resolucao: datetime = RESOLVIDO_ONTEM_EM_BRASILIA,
) -> PessoaANotificar:
    """Uma linha pendente com identificadores novos - por padrao, em Brasilia."""
    return PessoaANotificar(
        id_resolucao=uuid4(),
        id_usuario=uuid4(),
        id_desafio=uuid4(),
        qt_pessoa=qt_pessoa,
        dt_dia=dt_dia,
        dh_resolucao=dh_resolucao,
        nu_offset_minuto=offset,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. O texto
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
def test_o_texto_sai_nos_tres_idiomas(idioma: str) -> None:
    """Os tres idiomas do aplicativo respondem, e com o numero dentro."""
    titulo, corpo = texto_da_notificacao(3, idioma, "ontem")
    assert titulo == FRASES[idioma]["titulo_ontem"]
    assert "3" in corpo


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
def test_uma_pessoa_tem_frase_PROPRIA(idioma: str) -> None:
    """🔒 Singular e plural sao frases diferentes.

    ⚠️ *"1 pessoas reagiram"* e o tipo de erro que faz o produto parecer
    descuidado exatamente no momento bom - e nenhum teste de idioma pegaria,
    porque a chave existe nos tres.
    """
    _, uma = texto_da_notificacao(1, idioma, "ontem")
    _, varias = texto_da_notificacao(2, idioma, "ontem")
    assert uma != varias
    # ⚠️ **E nao basta serem diferentes**: com a condicao do singular trocada
    # por `quantas == 0`, uma pessoa cairia no plural e as duas frases continuariam
    # diferentes entre si (*"1 pessoas reagiram"* x *"2 pessoas reagiram"*). A
    # mutacao sobreviveu assim. Cada uma tem de ser **a sua**.
    assert uma == FRASES[idioma]["uma"]
    assert varias == FRASES[idioma]["varias"].format(quantas=2)
    assert "1" in uma
    # O plural nao pode ter ficado com o `{quantas}` sem substituir.
    assert "{quantas}" not in varias


def test_idioma_desconhecido_cai_no_INGLES() -> None:
    """Fallback igual ao do aplicativo - duas regras diferentes divergiriam."""
    titulo, corpo = texto_da_notificacao(4, "fr", "ontem")
    assert (titulo, corpo) == texto_da_notificacao(4, "en", "ontem")


def test_zero_reacao_NAO_gera_texto() -> None:
    """*"0 pessoas reagiram"* nao chega a ninguem.

    A guarda e a irma do `ck001_pessoa` da `0026`: se uma consulta mudada
    devolvesse zero, o banco recusaria a linha - e aqui a frase morre antes.
    """
    with pytest.raises(ValueError):
        texto_da_notificacao(0, "pt", "ontem")


def test_quando_DESCONHECIDO_e_erro_e_nao_titulo_vazio() -> None:
    """🔒 Um `quando` fora dos tres e defeito nosso, e tem de aparecer.

    ⚠️ Com um `.get(..., "")` no lugar do indice, a notificacao sairia com o
    titulo em branco - e o log diria sucesso. O `KeyError` vira falha da pessoa
    no relatorio do disparo.
    """
    with pytest.raises(KeyError):
        texto_da_notificacao(2, "pt", "semana passada")


@pytest.mark.parametrize(
    ("idioma", "uma", "duas"),
    [
        ("pt", "1 pessoa reagiu à sua solução.", "2 pessoas reagiram à sua solução."),
        ("en", "1 person reacted to your solution.", "2 people reacted to your solution."),
        ("es", "1 persona reaccionó a tu solución.", "2 personas reaccionaron a tu solución."),
    ],
)
def test_as_frases_saem_com_a_GRAFIA_certa(idioma: str, uma: str, duas: str) -> None:
    """🔒 O corpo que a pessoa le, letra por letra, com acento.

    ⚠️ **As frases esperadas estao escritas AQUI, e nao lidas de `FRASES`**: um
    caso que compara a funcao com a propria constante passa com qualquer texto
    dentro dela. Foi assim que *"reagiu a sua solucao"* e *"reacciono a tu
    solucion"* chegaram a producao (22/09 a 07/10/2026) com a suite verde.
    """
    assert texto_da_notificacao(1, idioma, "ontem")[1] == uma
    assert texto_da_notificacao(2, idioma, "ontem")[1] == duas


@pytest.mark.parametrize(
    ("idioma", "quando", "titulo"),
    [
        ("pt", "hoje", "O seu desafio resolvido hoje"),
        ("pt", "ontem", "O seu desafio resolvido ontem"),
        ("pt", "anteontem", "O seu desafio resolvido anteontem"),
        ("en", "hoje", "The challenge you solved today"),
        ("en", "ontem", "The challenge you solved yesterday"),
        ("en", "anteontem", "The challenge you solved the day before yesterday"),
        ("es", "hoje", "El desafío que resolviste hoy"),
        ("es", "ontem", "El desafío que resolviste ayer"),
        ("es", "anteontem", "El desafío que resolviste anteayer"),
    ],
)
def test_os_titulos_saem_com_a_GRAFIA_certa(
    idioma: str, quando: str, titulo: str
) -> None:
    """🔒 Os nove titulos (3 idiomas x 3 "quando"), escritos aqui por extenso.

    Mesma razao do caso do corpo: comparar com `FRASES` passaria com qualquer
    texto. E o titulo nao depende do numero - a pessoa le o mesmo com 1 ou 7.
    """
    assert texto_da_notificacao(1, idioma, quando)[0] == titulo
    assert texto_da_notificacao(7, idioma, quando)[0] == titulo


def test_cada_quando_tem_TITULO_nos_tres_idiomas() -> None:
    """Todo valor de `QUANDO_POR_DIAS` tem a sua chave em todos os idiomas."""
    for quando in QUANDO_POR_DIAS.values():
        for idioma in FRASES:
            assert f"titulo_{quando}" in FRASES[idioma], f"{idioma}.{quando}"


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


def test_a_janela_vai_das_11h30_as_14h30_LOCAIS() -> None:
    """🔒 A janela, pelas duas pontas e pelos vizinhos de uma hora.

    As 15:00 UTC, cada offset esta num horario local diferente. Entram:

      · -180 (Brasilia, 12:00), o caso comum;
      · -210 (Terra Nova, 11:30) - a tolerancia de antes, sem a qual os fusos de
        meia hora nunca seriam atendidos;
      · -120 (13:00) e -60 (14:00) - a repescagem de uma execucao pulada.

    E ficam de fora -240 (11:00, cedo demais) e 0 (15:00, tarde demais).
    """
    assert na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -180)
    assert na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -210)
    assert na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -120)
    assert na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -60)
    assert not na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -240)
    assert not na_janela_do_envio(MEIO_DIA_EM_BRASILIA, 0)
    assert not na_janela_do_envio(MEIO_DIA_EM_BRASILIA, 180)


def test_as_PONTAS_da_janela_minuto_a_minuto() -> None:
    """🔒 11:30 entra e 11:29 nao; 14:29 entra e 14:30 nao (fim aberto).

    ⚠️ **E o caso que segura a largura da janela.** Os vizinhos de uma hora do
    caso anterior nao distinguem *"fecha as 14:30"* de *"fecha as 14:59"*; so a
    borda de um minuto distingue.
    """
    em_brasilia = -180
    # 14:30 UTC = 11:30 em Brasilia; 17:29 UTC = 14:29.
    abre = datetime(2026, 9, 22, 14, 30, tzinfo=timezone.utc)
    fecha = datetime(2026, 9, 22, 17, 30, tzinfo=timezone.utc)
    um_minuto = timedelta(minutes=1)
    assert na_janela_do_envio(abre, em_brasilia)
    assert not na_janela_do_envio(abre - um_minuto, em_brasilia)
    assert na_janela_do_envio(fecha - um_minuto, em_brasilia)
    assert not na_janela_do_envio(fecha, em_brasilia)


@pytest.mark.parametrize("offset", [-600, -210, -180, 0, 330, 345, 540, 780, 840])
def test_cada_fuso_tem_TRES_chances_por_dia(offset: int) -> None:
    """🔒 O cron roda nas horas cheias UTC; cada fuso cai na janela tres vezes.

    ⚠️ **Tres, e nao uma**: e a repescagem. E **tres, e nao quatro**: uma
    quarta chance seria a janela larga demais, chegando perto do lembrete da
    chama das 19h (RF-DES-074b). Os fusos de meia hora (330, India) e de 45
    minutos (345, Nepal) entram na conta - sao eles que testam a tolerancia.

    O minuto `:02` imita o atraso real do Railway, que acorda o servico entre
    :00 e :05.
    """
    execucoes = [
        datetime(2026, 9, 22, 0, 2, tzinfo=timezone.utc) + timedelta(hours=h)
        for h in range(24)
    ]
    chances = [e for e in execucoes if na_janela_do_envio(e, offset)]
    assert len(chances) == 3


def test_a_hora_alvo_e_MEIO_DIA_e_nao_19h() -> None:
    """🔒 RF-DES-074b: as 19h ela chegaria junto do lembrete da chama.

    ⚠️ O numero entra **escrito** aqui, e nao lido da constante: ler
    `HORA_LOCAL_DO_ENVIO` para conferi-la faria o caso passar com qualquer valor
    (`memory/teste-nao-se-mede-pela-propria-regua`). O 12 e decisao de produto, e
    o cadeado e contra troca-lo sem pensar.
    """
    assert HORA_LOCAL_DO_ENVIO == 12
    # E a janela de fato cai ao meio-dia: 15:00 UTC atende UTC-3.
    assert na_janela_do_envio(MEIO_DIA_EM_BRASILIA, -180)
    # As 22:00 UTC, UTC-3 esta as 19h - e nao e atendido.
    assert not na_janela_do_envio(
        datetime(2026, 9, 22, 22, 0, tzinfo=timezone.utc), -180
    )


def test_os_dias_candidatos_cobrem_TODOS_os_fusos() -> None:
    """🔒 Todo fuso que a API aceita acha o seu *"ontem"* entre os candidatos.

    ⚠️ Se a lista ficasse curta, a pessoa da ponta do mundo nunca apareceria na
    consulta - sem erro nenhum, porque a hora dela simplesmente ficaria vazia.
    Por isso o caso varre as 24 horas de um dia e os offsets de -840 a +840.
    """
    for hora in range(24):
        agora = datetime(2026, 9, 22, hora, 2, tzinfo=timezone.utc)
        dias = dias_candidatos(agora)
        for offset in range(-840, 841, 15):
            assert dia_do_desafio_a_notificar(agora, offset) in dias


def test_a_MESMA_hora_pode_ter_DOIS_dias_alvo() -> None:
    """🔒 O mundo tem **26 horas de fusos** - e por isso a vez e por pessoa.

    Às 23:00 UTC de 22/09, dois offsets marcam meio-dia em **dias diferentes**:

      · UTC+13 esta as 12:00 de **23/09**  ->  dia alvo 22/09
      · UTC-11 esta as 12:00 de **22/09**  ->  dia alvo 21/09

    Os dois dias vem na mesma consulta, e cada pessoa so pode receber o **seu**.
    ⚠️ **As duas trocas tem de falhar**: se uma delas passasse, a pessoa de
    UTC-11 receberia o numero do desafio de outro dia, e a notificacao sairia
    igual - sem erro nenhum.
    """
    instante = datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc)
    assert date(2026, 9, 21) in dias_candidatos(instante)
    assert date(2026, 9, 22) in dias_candidatos(instante)

    assert deve_avisar_agora(instante, 780, date(2026, 9, 22))
    assert deve_avisar_agora(instante, -660, date(2026, 9, 21))
    # As trocas.
    assert not deve_avisar_agora(instante, 780, date(2026, 9, 21))
    assert not deve_avisar_agora(instante, -660, date(2026, 9, 22))


def test_fora_da_janela_NAO_e_a_vez_mesmo_no_dia_certo() -> None:
    """A outra metade de `deve_avisar_agora`: o dia certo nao basta."""
    # 22:00 UTC = 19h em Brasilia; o dia alvo ainda e 21/09, mas a hora passou.
    tarde = datetime(2026, 9, 22, 22, 0, tzinfo=timezone.utc)
    assert dia_do_desafio_a_notificar(tarde, -180) == DIA_ALVO_EM_BRASILIA
    assert not deve_avisar_agora(tarde, -180, DIA_ALVO_EM_BRASILIA)


# ── O "hoje / ontem / anteontem" do titulo ──────────────────────────────────


def test_resolveu_DEPOIS_das_21h_em_Brasilia_e_ANTEONTEM() -> None:
    """🔒 O caso que pediu esta regra (13/10/2026), com as datas reais.

    O dono resolveu as 23:48 de 12/10 em Brasilia - 02:48 UTC de **13/10**, ou
    seja, o desafio de 13/10. O aviso sai ao meio-dia de **14/10**. Para ele
    foi **anteontem**, e o titulo antigo dizia *"ontem"*.
    """
    resolucao = datetime(2026, 10, 13, 2, 48, tzinfo=timezone.utc)
    meio_dia_de_14 = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)

    assert deve_avisar_agora(meio_dia_de_14, -180, date(2026, 10, 13))
    assert quando_foi_resolvido(meio_dia_de_14, -180, resolucao) == "anteontem"


def test_resolveu_ANTES_das_21h_em_Brasilia_e_ONTEM() -> None:
    """O caso comum: resolveu as 15h de 21/09, le ao meio-dia de 22/09."""
    assert (
        quando_foi_resolvido(MEIO_DIA_EM_BRASILIA, -180, RESOLVIDO_ONTEM_EM_BRASILIA)
        == "ontem"
    )


def test_em_UTC_MAIS_13_pode_ser_HOJE() -> None:
    """A ponta leste: o dia UTC 22/09 comeca as 13:00 locais de 22/09.

    Quem resolve as 13:30 UTC de 22/09 esta as 02:30 de **23/09**, e e avisado
    ao meio-dia de 23/09 (23:00 UTC de 22/09): resolveu **hoje**.
    """
    resolucao = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)
    meio_dia_local = datetime(2026, 9, 22, 23, 0, tzinfo=timezone.utc)
    assert quando_foi_resolvido(meio_dia_local, 780, resolucao) == "hoje"


def test_o_quando_e_PRESO_nas_pontas() -> None:
    """Fora de 0 a 2 dias vira o titulo mais proximo, e nao uma excecao.

    ⚠️ Pela construcao do disparo isso nao acontece; o prendedor e para uma
    resolucao corrigida a mao nao custar a notificacao.
    """
    agora = MEIO_DIA_EM_BRASILIA
    cinco_dias_antes = agora - timedelta(days=5)
    amanha = agora + timedelta(days=1)
    assert quando_foi_resolvido(agora, -180, cinco_dias_antes) == "anteontem"
    assert quando_foi_resolvido(agora, -180, amanha) == "hoje"


def test_instante_em_OUTRO_fuso_e_convertido_antes_da_conta() -> None:
    """🔒 O mesmo instante, escrito em UTC ou em -03:00, da o mesmo dia.

    ⚠️ Somar o offset a um horario que nao esta em UTC daria a data errada,
    calada. O `asyncpg` devolve em UTC hoje; o caso e para o dia em que nao
    devolver. E o instante **sem fuso** e lido como UTC.
    """
    em_utc = datetime(2026, 10, 13, 2, 48, tzinfo=timezone.utc)
    em_brasilia = em_utc.astimezone(timezone(timedelta(hours=-3)))
    sem_fuso = em_utc.replace(tzinfo=None)

    assert dia_local(em_brasilia, -180) == dia_local(em_utc, -180)
    assert dia_local(sem_fuso, -180) == dia_local(em_utc, -180)
    assert dia_local(em_utc, -180) == date(2026, 10, 12)


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
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 1
    assert relatorio.aparelhos == 1
    assert relatorio.pendentes == 1
    assert relatorio.offsets == [-180]
    assert len(enviador.envios) == 1
    titulo, corpo, dados, token = enviador.envios[0]
    assert token == "tok-1"
    assert titulo == "O seu desafio resolvido ontem"
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
async def test_aparelho_ESQUECIDO_noutro_fuso_nao_rouba_o_aviso() -> None:
    """🔒 O defeito de 10 a 13/10/2026, reproduzido.

    O dono usa um iPhone em Brasilia e tinha um Android de teste esquecido desde
    02/09, com o relogio em GMT. Na regra antiga, as 12:00 UTC (meio-dia do
    Android) o aviso saia so para o Android e a reserva era gravada; as 15:00
    UTC o iPhone nem era tentado. Por tres dias o aviso foi para a gaveta.

    Agora o fuso e o da **pessoa** (o do aparelho usado por ultimo, -180):

      · as 12:00 UTC (9h em Brasilia) ela **aguarda**, e nada e reservado;
      · as 15:00 UTC sai o aviso, para **os dois** aparelhos.
    """
    pessoa = _pessoa(offset=-180)
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={
            pessoa.id_usuario: [
                Aparelho("tok-iphone", "pt"),
                Aparelho("tok-android-gmt", "en"),
            ]
        },
    )
    enviador = EnviadorFalso()
    servico = _servico(repo, enviador)

    # 12:00 UTC: meio-dia do Android, 9h da pessoa.
    as_9h = await servico.disparar(datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc))
    assert as_9h.aguardando == 1
    assert as_9h.enviadas == 0
    assert repo.gravadas == []
    assert "reservar" not in repo.diario

    # 15:00 UTC: meio-dia da pessoa.
    ao_meio_dia = await servico.disparar(MEIO_DIA_EM_BRASILIA)
    assert ao_meio_dia.enviadas == 1
    assert ao_meio_dia.aparelhos == 2
    assert {t for _, _, _, t in enviador.envios} == {"tok-iphone", "tok-android-gmt"}
    assert repo.gravadas[0].nu_offset_minuto == -180
    assert repo.gravadas[0].qt_dispositivo == 2


@pytest.mark.asyncio
async def test_a_hora_PULADA_e_repescada_na_seguinte() -> None:
    """Se o cron nao rodou ao meio-dia, a execucao das 13h ainda avisa."""
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
    )
    enviador = EnviadorFalso()

    # 16:00 UTC = 13h em Brasilia; nenhuma execucao rodou ao meio-dia.
    relatorio = await _servico(repo, enviador).disparar(
        datetime(2026, 9, 22, 16, 0, tzinfo=timezone.utc)
    )

    assert relatorio.enviadas == 1
    # E o titulo continua *"ontem"*: a hora mudou, o dia nao.
    assert enviador.envios[0][0] == "O seu desafio resolvido ontem"


@pytest.mark.asyncio
async def test_o_titulo_diz_ANTEONTEM_para_quem_resolveu_depois_das_21h() -> None:
    """🔒 O caso do dono, de ponta a ponta pelo servico (ver o caso puro)."""
    pessoa = _pessoa(
        dt_dia=date(2026, 10, 13),
        dh_resolucao=datetime(2026, 10, 13, 2, 48, tzinfo=timezone.utc),
    )
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
    )
    enviador = EnviadorFalso()

    await _servico(repo, enviador).disparar(
        datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
    )

    assert enviador.envios[0][0] == "O seu desafio resolvido anteontem"


@pytest.mark.asyncio
async def test_a_reserva_e_CONFIRMADA_antes_do_envio() -> None:
    """🔒 A ordem: `reservar` -> `confirmar` -> enviar.

    ⚠️ **Uma reserva ainda dentro da transacao nao impede nada**: a outra
    execucao nao a ve. Enviar antes de confirmar abriria a janela em que as
    duas mandam a mesma notificacao - e o log das duas diria sucesso.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
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

    ⚠️ O idioma e do **aparelho** (`co_idioma` da `tb005`), e nao da conta -
    quem usa o telefone em portugues e o tablet em ingles le cada um no seu.
    """
    pessoa = _pessoa(qt_pessoa=2)
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={
            pessoa.id_usuario: [
                Aparelho("tok-pt", "pt"),
                Aparelho("tok-en", "en"),
            ]
        },
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    # UMA notificacao (uma pessoa), DOIS aparelhos.
    assert relatorio.enviadas == 1
    assert relatorio.aparelhos == 2
    corpos = {token: corpo for _, corpo, _, token in enviador.envios}
    assert corpos["tok-pt"] == FRASES["pt"]["varias"].format(quantas=2)
    assert corpos["tok-en"] == FRASES["en"]["varias"].format(quantas=2)


@pytest.mark.asyncio
async def test_o_offset_gravado_e_o_da_PESSOA() -> None:
    """🔒 O `nu_offset_minuto` gravado e o fuso que decidiu a hora.

    Ele existe para se reconferir a conta do meio-dia depois. Uma pessoa em
    Terra Nova (-210) e avisada as 15:00 UTC (11:30 dela), e o registro tem de
    dizer -210 - e nao o -180 de quem divide a mesma execucao.
    """
    em_brasilia = _pessoa(offset=-180)
    em_terra_nova = _pessoa(offset=-210)
    repo = RepoFalso(
        pendentes=[em_brasilia, em_terra_nova],
        aparelhos={
            em_brasilia.id_usuario: [Aparelho("tok-br", "pt")],
            em_terra_nova.id_usuario: [Aparelho("tok-tn", "en")],
        },
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    por_resolucao = {g.id_resolucao: g.nu_offset_minuto for g in repo.gravadas}
    assert por_resolucao[em_brasilia.id_resolucao] == -180
    assert por_resolucao[em_terra_nova.id_resolucao] == -210
    assert sorted(relatorio.offsets) == [-210, -180]


@pytest.mark.asyncio
async def test_fora_da_vez_a_pessoa_AGUARDA_sem_gastar_nada() -> None:
    """Pendente cujo meio-dia ainda nao chegou: nem aparelho e consultado.

    ⚠️ **Nao e erro e nao gasta a reserva**: e quem a proxima hora atende. O
    relatorio conta a parte (`aguardando`), para a linha do log nao confundir
    *"ninguem para avisar"* com *"gente esperando a hora dela"*.
    """
    pessoa = _pessoa(offset=180)
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-longe", "pt")]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.aguardando == 1
    assert relatorio.pendentes == 0
    assert enviador.envios == []
    assert "dispositivos" not in repo.diario
    assert "reservar" not in repo.diario


@pytest.mark.asyncio
async def test_quem_JA_foi_avisado_nao_e_avisado_de_novo() -> None:
    """🔒 O teto de uma por desafio (RF-DES-074b), pela reserva perdida.

    ⚠️ Aqui a linha **aparece** como pendente (o cenario e a corrida entre duas
    execucoes: as duas leram antes de qualquer uma gravar), e quem a segura e o
    `ON CONFLICT DO NOTHING`.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
        # A outra execucao gravou DEPOIS de esta ler os pendentes: a linha ainda
        # aparece na consulta, e quem a segura e o `ON CONFLICT`.
        reservas_nao_vistas={pessoa.id_resolucao},
    )
    enviador = EnviadorFalso()

    # ⚠️ O cenario so vale se a linha **chegou** ao servico: sem isto, o caso
    # provaria a consulta (que e o outro teste) e nao a reserva perdida.
    assert await repo.pendentes([DIA_ALVO_EM_BRASILIA]) == [pessoa]

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.ja_notificadas == 1
    assert relatorio.enviadas == 0
    assert enviador.envios == []


@pytest.mark.asyncio
async def test_reacao_TARDIA_nao_gera_uma_segunda() -> None:
    """🔒 A consulta nao traz quem ja tem linha de notificacao.

    ⚠️ E o caso que a tabela existe para cobrir: mais gente reagiu depois do
    envio, e a contagem mudou. **Nao se compara numero** - se comparasse, cada
    pessoa nova renderia uma notificacao.
    """
    pessoa = _pessoa(qt_pessoa=3)
    # A rodada seguinte ve a MESMA pessoa com mais reacoes...
    maior = replace(pessoa, qt_pessoa=7)
    repo = RepoFalso(
        pendentes=[maior],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
        reservas={pessoa.id_resolucao},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 0
    assert enviador.envios == []


@pytest.mark.asyncio
async def test_sem_aparelho_nenhum_a_reserva_NAO_e_gasta() -> None:
    """Nao se queima a chance do dia de quem nao tem onde receber.

    A consulta de pendentes ja exige um aparelho com fuso; este caso cobre o
    token apagado entre as duas consultas (o FCM o recusou para outra pessoa da
    mesma conta, por exemplo).
    """
    pessoa = _pessoa()
    repo = RepoFalso(pendentes=[pessoa], aparelhos={})
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.sem_aparelho == 1
    assert relatorio.enviadas == 0
    assert repo.gravadas == []
    assert "reservar" not in repo.diario


@pytest.mark.asyncio
async def test_token_MORTO_sai_da_base_e_devolve_a_chance() -> None:
    """Token morto e o caso comum - e ele nao pode gastar o dia da pessoa.

    ⚠️ **Duas coisas num caso so, e elas sao inseparaveis:** o token sai da
    `tb005` (a faxina que o script fazia a mao) e a reserva e **desfeita**, porque
    ninguem recebeu nada. Sem a segunda metade, reinstalar o aplicativo custaria a
    notificacao daquele dia.
    """
    pessoa = _pessoa()
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-morto", "pt")]},
    )
    enviador = EnviadorFalso(mortos={"tok-morto"})

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.tokens_removidos == 1
    assert repo.tokens_removidos == ["tok-morto"]
    assert relatorio.nenhum_aceitou == 1
    assert relatorio.enviadas == 0
    # A chance voltou: nao sobrou linha nenhuma.
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
        pendentes=[pessoa],
        aparelhos={
            pessoa.id_usuario: [
                Aparelho("tok-morto", "pt"),
                Aparelho("tok-vivo", "pt"),
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
    # ⚠️ `qt_dispositivo` e o que foi **enderecado** (2), e nao o que aceitou.
    assert repo.gravadas[0].qt_dispositivo == 2


@pytest.mark.asyncio
async def test_uma_pessoa_ruim_NAO_derruba_as_outras() -> None:
    """Um estouro inesperado vira linha no relatorio, e a hora continua.

    ⚠️ Sem isso, um token esquisito no meio da lista cancelaria as notificacoes
    de todo mundo que viesse depois.
    """
    ruim, boa = _pessoa(), _pessoa()
    repo = RepoFalso(
        pendentes=[ruim, boa],
        aparelhos={
            ruim.id_usuario: [Aparelho("tok-explode", "pt")],
            boa.id_usuario: [Aparelho("tok-boa", "pt")],
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
    """A maior parte das execucoes nao acha ninguem, e isso nao e erro."""
    repo = RepoFalso()
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert relatorio.enviadas == 0
    assert relatorio.pendentes == 0
    assert relatorio.falhas == []
    assert enviador.envios == []
    # ⚠️ Mas ela **olhou**: os dias consultados aparecem no relatorio.
    assert DIA_ALVO_EM_BRASILIA.isoformat() in relatorio.dias


@pytest.mark.asyncio
async def test_o_servico_pede_os_dias_CANDIDATOS_numa_consulta_so() -> None:
    """🔒 Uma ida ao banco por hora, com todos os dias que algum fuso quer."""
    repo = RepoFalso()

    await _servico(repo, EnviadorFalso()).disparar(MEIO_DIA_EM_BRASILIA)

    assert repo.dias_pedidos == [dias_candidatos(MEIO_DIA_EM_BRASILIA)]


@pytest.mark.asyncio
async def test_o_dia_ERRADO_para_a_pessoa_nao_e_avisado() -> None:
    """🔒 A pessoa vem na consulta, mas o desafio nao e o *"ontem"* DELA.

    Ao meio-dia de 22/09 em Brasilia o *"ontem"* e 21/09. O desafio de 22/09
    tambem esta entre os candidatos (e o *"ontem"* de quem esta muito a leste) -
    e para esta pessoa ele tem de esperar o dia seguinte.
    """
    pessoa = _pessoa(dt_dia=date(2026, 9, 22))
    repo = RepoFalso(
        pendentes=[pessoa],
        aparelhos={pessoa.id_usuario: [Aparelho("tok-1", "pt")]},
    )
    enviador = EnviadorFalso()

    relatorio = await _servico(repo, enviador).disparar(MEIO_DIA_EM_BRASILIA)

    assert date(2026, 9, 22) in repo.dias_pedidos[0]
    assert relatorio.aguardando == 1
    assert relatorio.enviadas == 0


def test_o_resumo_do_log_tem_os_campos_NOVOS() -> None:
    """A linha do Railway diz os dias, os fusos e quem aguarda."""
    from api.notificacoes.reacoes_do_desafio import RelatorioDoDisparo

    relatorio = RelatorioDoDisparo(
        dias=["2026-09-21"], offsets=[-180, -210], pendentes=2, aguardando=5
    )
    linha = relatorio.resumo()
    assert "dias=['2026-09-21']" in linha
    assert "fusos=[-210, -180]" in linha
    assert "pendentes=2" in linha
    assert "aguardando=5" in linha


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


def test_a_consulta_de_aparelhos_NAO_filtra_pelo_fuso() -> None:
    """🔒 Na hora da pessoa, TODOS os aparelhos dela recebem.

    ⚠️ O filtro por fuso de cada aparelho era o defeito: com a reserva uma por
    resolucao, o primeiro relogio a chegar ao meio-dia gastava o aviso dos
    outros (13/10/2026).
    """
    assert "nu_offset_minuto" not in SQL_DISPOSITIVOS
    assert "id_usuario = :id_usuario" in SQL_DISPOSITIVOS


def test_o_fuso_e_o_do_aparelho_usado_POR_ULTIMO() -> None:
    """🔒 Uma linha por pessoa, a mais recente, e so entre quem informou fuso."""
    assert "DISTINCT ON (id_usuario)" in SQL_PENDENTES
    assert "ORDER BY id_usuario, dh_atualizacao DESC" in SQL_PENDENTES
    assert "nu_offset_minuto IS NOT NULL" in SQL_PENDENTES
    assert "JOIN fuso_atual f" in SQL_PENDENTES


def test_a_consulta_traz_TODOS_os_dias_candidatos() -> None:
    """Uma lista de dias, e nao um dia so - ver `dias_candidatos`."""
    assert "d.dt_dia = ANY(:dias)" in SQL_PENDENTES
    assert ":dt_dia" not in SQL_PENDENTES


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
async def test_a_consulta_real_leva_os_DIAS_e_a_CATEGORIA() -> None:
    """🔒 O `:categoria` sai da constante, e os dias viajam como lista.

    ⚠️ Um parametro nomeado que nao recebe valor levanta erro **no banco**, e
    nao aqui - ou seja, so na primeira execucao real, de hora em hora, num
    processo que ninguem esta olhando.
    """
    sessao = SessaoFalsa(ResultadoFalso(linhas=[]))
    dias = [date(2026, 9, 21), date(2026, 9, 22)]

    await _repo_real(sessao).pendentes(dias)

    _, parametros = sessao.chamadas[0]
    assert parametros["dias"] == dias
    assert parametros["categoria"] == CATEGORIA_REACOES


@pytest.mark.asyncio
async def test_a_consulta_real_monta_a_pessoa_com_FUSO_DIA_e_RESOLUCAO() -> None:
    """As tres colunas novas chegam a `PessoaANotificar` com o nome certo."""
    linha = {
        "id_resolucao": uuid4(),
        "id_usuario": uuid4(),
        "id_desafio": uuid4(),
        "qt_pessoa": 3,
        "dt_dia": DIA_ALVO_EM_BRASILIA,
        "dh_resolucao": RESOLVIDO_ONTEM_EM_BRASILIA,
        "nu_offset_minuto": -180,
    }
    sessao = SessaoFalsa(ResultadoFalso(linhas=[linha]))

    [pessoa] = await _repo_real(sessao).pendentes([DIA_ALVO_EM_BRASILIA])

    assert pessoa.dt_dia == DIA_ALVO_EM_BRASILIA
    assert pessoa.dh_resolucao == RESOLVIDO_ONTEM_EM_BRASILIA
    assert pessoa.nu_offset_minuto == -180
    assert pessoa.qt_pessoa == 3


@pytest.mark.asyncio
async def test_a_consulta_real_de_aparelhos_leva_so_a_PESSOA() -> None:
    """Sem lista de offsets: a consulta so precisa saber de quem e."""
    sessao = SessaoFalsa(
        ResultadoFalso(linhas=[{"co_token_fcm": "tok-1", "co_idioma": "pt"}])
    )
    id_usuario = uuid4()

    aparelhos = await _repo_real(sessao).dispositivos(id_usuario)

    _, parametros = sessao.chamadas[0]
    assert parametros == {"id_usuario": id_usuario}
    assert aparelhos == [Aparelho(token="tok-1", idioma="pt")]
