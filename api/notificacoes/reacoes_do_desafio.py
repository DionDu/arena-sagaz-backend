"""A notificacao do dia seguinte - *"3 pessoas reagiram ao seu desafio de ontem"*
(T079, RF-DES-074 a 074c).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ELA ⛔ NAO PEGA CARONA NO LEMBRETE DAS 19h
═══════════════════════════════════════════════════════════════════════════

O lembrete da chama e **LOCAL**: ele e agendado dentro do aparelho
(`lembrete_sequencia_local.dart`), e o servidor ⛔ nao tem como pendurar nada
nele. Esta notificacao nasce de um fato que so o servidor conhece - alguem reagiu
- entao ela e **push do servidor**, necessariamente.

⚠️ **E ⛔ nao pode ser broadcast por topico.** Topico entrega a todos os
inscritos; esta frase e dirigida a **uma** pessoa e traz o numero **dela**. Sai
pelo **token** da `conta.tb005_dispositivo_notificacao` - e e o **primeiro envio
direcionado** do projeto: ate aqui, todo push do servidor era topico.

⚠️ **Meio-dia, e ⛔ nao 19h** (RF-DES-074b): as 19h ela chegaria junto do lembrete
da chama, e duas notificacoes no mesmo minuto gastam as duas.

═══════════════════════════════════════════════════════════════════════════
⚠️ O MEIO-DIA E O DE QUEM RECEBE - E ISSO MUDA QUAL E "ONTEM"
═══════════════════════════════════════════════════════════════════════════

RF-DES-074c: cada pessoa e notificada ao meio-dia **do seu proprio fuso**. Quem
esta em Lisboa recebe quatro horas antes de quem esta em Sao Paulo. O disparo roda
de hora em hora e atende os fusos em que **ja e meio-dia**, pela mesma
`fusos_na_hora_local()` que o broadcast usa.

⚠️ **E aqui esta a armadilha que quase passou.** O desafio e do dia **UTC**
(RF-DES-007), mas *"ontem"* e do calendario de **quem le a frase**. Usar
`hoje_utc - 1` parece equivalente e ⛔ nao e:

    Em UTC+13, o meio-dia local de 5/out acontece as **23:00 UTC de 4/out**.
    `hoje_utc - 1` daria **3/out** - um desafio de anteontem para ela, enquanto
    o de 4/out, que ela acabou de jogar, ⛔ nunca seria notificado.

Entao o dia alvo e **o dia local da pessoa menos um**, calculado por offset -
[dia_do_desafio_a_notificar]. Em UTC+13 isso da o dia UTC **corrente**, e esta
certo: ela resolveu o desafio de 4/out na noite local de 4/out, que comecou as
13:00 locais.

⚠️ **Consequencia aceita:** nesse fuso o dia UTC ainda esta correndo quando a
notificacao sai, e quem esta a oeste ainda vai reagir depois. Essas reacoes ⛔ nao
geram uma segunda notificacao (RF-DES-074b) - e por isso `qt_pessoa` fica
gravado: e ele que explica *"a notificacao disse 3 e o quadro mostra 7"*.

═══════════════════════════════════════════════════════════════════════════
⚠️ UMA POR DESAFIO, E QUEM GARANTE E O BANCO
═══════════════════════════════════════════════════════════════════════════

O teto mora em `un001_notificacao_reacao UNIQUE (id_resolucao)`: o disparo
**reserva** com `INSERT ... ON CONFLICT DO NOTHING` e ⛔ so envia se a linha foi
dele. Duas execucoes ao mesmo tempo - o cron e o dono rodando na maquina dele -
passariam juntas por qualquer `if` em memoria.

⚠️ **A reserva vem ANTES do envio**, com preco: FCM fora do ar naquela hora e a
pessoa perde a notificacao daquele dia. O contrario arriscaria **duas**, e *"uma
por desafio"* e requisito escrito; *"chega sempre"* ⛔ nao e.

⚠️ **Mas se NENHUM aparelho aceitou, a reserva e DESFEITA.** Token morto e o caso
comum (reinstalar o aplicativo gira o token), e uma reserva queimada ali seria a
chance do dia gasta sem ninguem receber. E o mesmo instante em que o token morto
sai da `tb005` - a faxina que `scripts/faxina_tokens_fcm.py` fazia a mao.

═══════════════════════════════════════════════════════════════════════════
⚠️ O TEXTO E TEXTO, E ⛔ NAO EMOTICON
═══════════════════════════════════════════════════════════════════════════

A T078 aprendeu isto na barra do quadro: emoticon lido em voz alta sai com o nome
tecnico do sistema (*"face with open mouth"*). Numa notificacao o leitor de tela
le exatamente o titulo e o corpo - entao o numero e o assunto vao **escritos**, e
⛔ nenhum emoticon carrega significado aqui.

⚠️ **E a frase ⛔ nao nomeia o tipo de reacao.** RF-DES-074 escreve *"3 pessoas
aplaudiram"* como exemplo, e o exemplo e o caso comum (palmas); mas dizer
*"aplaudiram"* quando as tres reacoes foram 🔥 seria falso, e conjugar um verbo
por tipo exigiria 5 tipos x 3 idiomas x singular/plural - com uma reacao nova no
banco caindo num vazio. *"Reagiram"* e verdade em todos os casos, hoje e depois.

⚠️ **O idioma e o do APARELHO** (`co_idioma` da `tb005`), e ⛔ nao o da conta: dois
aparelhos da mesma pessoa em idiomas diferentes recebem cada um no seu. Idioma que
⛔ nao conhecemos cai no ingles, que e o mesmo fallback do aplicativo.

═══════════════════════════════════════════════════════════════════════════
⚠️ O `data` LEVA O ASSUNTO, E ⛔ NAO A ROTA
═══════════════════════════════════════════════════════════════════════════

RF-DES-109 diz que o toque abre **o quadro daquele dia**, ⛔ nao a Home. O
aplicativo navega por `data['rota']` - e e justamente por isso que o servidor ⛔
**nao** manda rota: o aplicativo em campo fica congelado no aparelho, e uma rota
que a versao instalada ⛔ nao registrou cai na tela de erro do `go_router`.

O servidor manda **de que se trata** (`tipo`, `id_desafio`), e quem escolhe a tela
e quem tem as telas. E a mesma fronteira do Bloco Y: publica-se **dado**, ⛔ nunca
navegacao no aparelho dos outros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    TB_NOTIFICACAO_REACAO,
    VW_DESAFIO_DIA,
    VW_NOTIFICACAO_REACAO,
    VW_REACAO,
    VW_RESOLUCAO,
)
from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO
from api.notificacoes.servico import fusos_na_hora_local

# ═══════════════════════════════════════════════════════════════════════════
# 1. As constantes da regra
# ═══════════════════════════════════════════════════════════════════════════

#: A categoria de preferencia desta notificacao (`tb006_preferencia_notificacao`).
#:
#: ⚠️ **Categoria NOVA, e ⛔ nao `lembrete`** (RF-DES-074b). Quem desliga o
#: lembrete da chama esta dizendo *"nao me cutuque para jogar"*; quem recebeu
#: aplausos ⛔ nao pediu para ser cutucado - foi outra pessoa que fez algo. Juntar
#: as duas faria uma escolha desligar a outra sem que ninguem tivesse pedido.
#:
#: ⚠️ A coluna e `VARCHAR(20)` **sem `CHECK`**, entao o codigo novo ⛔ nao exige
#: migracao. A **linha na tela** do aplicativo entrou com a T079b (22/09/2026);
#: nas versoes anteriores do app ela ⛔ nao existe, e a ausencia de linha ⛔ nao
#: silencia ninguem: sem registro na tabela, vale ligado.
#:
#: ⚠️ **O aplicativo compara este valor** (e o de [TIPO_DO_PUSH]) num teste que
#: le este arquivo: `arena-sagaz-frontend/test/core/notificacoes/
#: destino_do_toque_test.dart`. Mudou aqui, muda la.
CATEGORIA_REACOES = "reacoes"

#: A hora **local** em que a notificacao sai (RF-DES-074b).
HORA_LOCAL_DO_ENVIO = 12

#: A metade da janela aceita, em minutos.
#:
#: ⚠️ **Tem de casar com a frequencia do cron**, que e de hora em hora: 30 minutos
#: cobrem o dia inteiro sem repetir nem deixar buraco. ⛔ E sem ela os fusos de
#: meia hora (India, Nepal, Terra Nova, Chatham) ⛔ nunca seriam atendidos - ver a
#: docstring de `fusos_na_hora_local`.
TOLERANCIA_EM_MINUTOS = 30

#: O idioma de reserva, quando o aparelho reporta um que ⛔ nao publicamos.
#:
#: ⚠️ **Ingles, igual ao aplicativo** (`supportedLocales` resolve para `en`
#: quando nada casa). Duas regras de fallback diferentes fariam a notificacao
#: chegar num idioma e o aplicativo abrir noutro.
IDIOMA_DE_RESERVA = "en"

#: O que o `data` do push diz que isto e - o aplicativo escolhe a tela por aqui
#: (`rotaDoToque`, em `lib/core/notificacoes/destino_do_toque.dart`).
TIPO_DO_PUSH = "reacao_desafio"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O texto - funcoes puras, nos tres idiomas
# ═══════════════════════════════════════════════════════════════════════════

#: Titulo e corpo, por idioma. `{quantas}` e o unico substituivel.
#:
#: ⚠️ **Duas formas, e ⛔ nao uma com "(s)"**: *"1 pessoas reagiram"* e o tipo de
#: frase que faz o produto parecer descuidado justamente no momento bom.
#:
#: ⚠️ **Hifen comum, ⛔ nunca travessao longo** - a mesma regra dos `.arb` do
#: aplicativo (decisao do dono, 19/08/2026). O texto aqui e lido pela pessoa
#: exatamente como os de la.
FRASES: dict[str, dict[str, str]] = {
    "pt": {
        "titulo": "O seu desafio de ontem",
        "uma": "1 pessoa reagiu a sua solucao.",
        "varias": "{quantas} pessoas reagiram a sua solucao.",
    },
    "en": {
        "titulo": "Your challenge from yesterday",
        "uma": "1 person reacted to your solution.",
        "varias": "{quantas} people reacted to your solution.",
    },
    "es": {
        "titulo": "Tu desafio de ayer",
        "uma": "1 persona reacciono a tu solucion.",
        "varias": "{quantas} personas reaccionaron a tu solucion.",
    },
}


def texto_da_notificacao(quantas: int, idioma: str) -> tuple[str, str]:
    """O `(titulo, corpo)` da notificacao, no idioma do aparelho.

    Args:
        quantas: quantas **pessoas** reagiram. ⚠️ Pessoas, ⛔ nao toques: a troca
            de reacao e um `UPDATE` na mesma linha (`un001_reacao`), entao contar
            linhas e contar gente.
        idioma: o `co_idioma` do aparelho (`pt`, `en`, `es`). Desconhecido cai em
            [IDIOMA_DE_RESERVA].

    Returns:
        O par pronto para o FCM.

    Raises:
        ValueError: se [quantas] ⛔ nao for positivo. ⛔ **Notificacao de zero
            reacao ⛔ nao existe** - e o `ck001_pessoa` da `0026` diz o mesmo do
            lado do banco. Levantar aqui e o que impede um *"0 pessoas
            reagiram"* de chegar a alguem por causa de uma consulta mudada.
    """
    if quantas < 1:
        raise ValueError(
            f"notificacao de reacao com quantas={quantas}: ⛔ nao se avisa "
            "ninguem sobre zero reacao."
        )
    frases = FRASES.get(idioma) or FRASES[IDIOMA_DE_RESERVA]
    if quantas == 1:
        return frases["titulo"], frases["uma"]
    return frases["titulo"], frases["varias"].format(quantas=quantas)


def dados_do_push(id_desafio: UUID, quantas: int) -> dict[str, str]:
    """O `data` que viaja junto - o **assunto**, e ⛔ nao a rota.

    Ver o cabecalho: rota e vocabulario do aplicativo, e uma que a versao
    instalada ⛔ nao conheca cairia na tela de erro do `go_router`. O FCM exige
    valores string, entao tudo sai convertido.
    """
    return {
        "tipo": TIPO_DO_PUSH,
        "id_desafio": str(id_desafio),
        "qt_pessoa": str(quantas),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. A conta do "ontem de quem recebe"
# ═══════════════════════════════════════════════════════════════════════════


def offsets_ao_meio_dia(agora_utc: datetime) -> list[int]:
    """Os offsets em que o relogio local marca ~12h **neste instante**.

    Reusa `fusos_na_hora_local`, que o broadcast por fuso ja usava - a mesma
    conta, uma implementacao so. Duas discordariam no primeiro fuso de meia hora.
    """
    return fusos_na_hora_local(
        HORA_LOCAL_DO_ENVIO,
        agora_utc,
        tolerancia_minutos=TOLERANCIA_EM_MINUTOS,
    )


def dia_local(agora_utc: datetime, offset_minuto: int) -> date:
    """A data que o calendario **daquele fuso** mostra neste instante."""
    return (agora_utc + timedelta(minutes=offset_minuto)).date()


def dia_do_desafio_a_notificar(agora_utc: datetime, offset_minuto: int) -> date:
    """Qual `dt_dia` e *"ontem"* para quem esta naquele fuso.

    ⚠️ **E o dia LOCAL menos um, e ⛔ nao `hoje_utc - 1`** - ver o cabecalho: em
    UTC+13 as duas contas dao dias diferentes, e a segunda deixaria o desafio que
    a pessoa acabou de jogar sem notificacao nenhuma.
    """
    return dia_local(agora_utc, offset_minuto) - timedelta(days=1)


def grupos_por_dia_alvo(agora_utc: datetime) -> dict[date, list[int]]:
    """`{dia alvo: [offsets]}` para este instante.

    ⚠️ **Agrupado, e ⛔ nao um dia so para a lista inteira** - e ⛔ isto ⛔ nao e
    zelo teorico: **o mundo tem 26 horas de fusos**, entao ha instantes em que
    dois offsets marcam meio-dia em **dias diferentes**.

        As 23:00 UTC de 22/09:
          · UTC+13 marca 12:00 de **23/09**  →  dia alvo 22/09
          · UTC-11 marca 12:00 de **22/09**  →  dia alvo 21/09

    Os dois estao na mesma janela, e cada um precisa do **seu** dia. Calcular o
    dia uma vez (por exemplo pelo offset 0) mandaria a metade deles o numero de
    outro desafio - e ⛔ sem erro nenhum, porque a notificacao sai igual.

    ⚠️ **Eu escrevi o contrario aqui na primeira versao** (*"com a hora alvo em 12h
    todos caem no mesmo dia"*), e a prova por mutacao mostrou que ⛔ nao: a
    mutacao que trocava o offset pelo 0 **sobreviveu**, porque ⛔ nenhum caso
    olhava um instante com dois dias na janela.
    """
    grupos: dict[date, list[int]] = {}
    for offset in offsets_ao_meio_dia(agora_utc):
        grupos.setdefault(
            dia_do_desafio_a_notificar(agora_utc, offset), []
        ).append(offset)
    return grupos


# ═══════════════════════════════════════════════════════════════════════════
# 4. O envio - injetado, como no broadcast
# ═══════════════════════════════════════════════════════════════════════════


class TokenMorto(Exception):
    """O aparelho daquele token ⛔ nao existe mais (FCM `UNREGISTERED`).

    ⚠️ **Ela existe para este modulo ⛔ nao importar `firebase_admin`.** Quem
    converte a excecao da biblioteca e o enviador real
    (`disparo_de_reacoes.enviar_para_token`); aqui dentro so ha a nossa, e e por
    isso que o servico inteiro roda em teste sem a lib pesada.
    """


#: Assinatura do enviador: `(titulo, corpo, dados, token) -> id da mensagem`.
#:
#: ⚠️ **Um token por chamada, e ⛔ nao uma lista.** O FCM tem envio em lote, mas
#: aqui cada aparelho leva um texto **no idioma dele** - o lote obrigaria a
#: agrupar por idioma antes, e a economia seria de uma chamada por pessoa.
#:
#: ⚠️ **Sincrono de proposito**, dentro de um servico `async`: o `messaging.send`
#: do `firebase_admin` bloqueia, e ⛔ nao ha versao assincrona dele. Aqui isso ⛔
#: nao custa nada - quem roda este servico e um processo de **cron**, e ⛔ nao ha
#: requisicao de ninguem esperando. Num caminho da API a mesma chamada prenderia
#: o laco de eventos.
EnviadorPorToken = Callable[[str, str, dict[str, str], str], str]


# ═══════════════════════════════════════════════════════════════════════════
# 5. As consultas
# ═══════════════════════════════════════════════════════════════════════════

#: Quem recebeu reacao no desafio daquele dia e ainda ⛔ nao foi avisado.
#:
#: ⚠️ **A visibilidade e a MESMA do quadro**, pela constante compartilhada: quem
#: desligou `ic_visivel_placar` saiu do quadro (RF-DES-077), e avisa-la de uma
#: contagem que ela ⛔ nao consegue ver seria contar em segredo - a T078 decidiu
#: o mesmo do lado da tela.
#:
#: ⚠️ **A preferencia entra por `NOT EXISTS`, e ⛔ nao por `JOIN`**: a
#: `tb006_preferencia_notificacao` so tem linha para quem **mexeu** no
#: interruptor. Um `JOIN` exigiria linha e silenciaria todo mundo que nunca
#: abriu a tela de notificacoes - o padrao e ligado.
#:
#: ⚠️ **`LEFT JOIN` na reserva e `IS NULL`**: e a metade da regra de *"uma por
#: desafio"* que sobrevive entre execucoes. A outra metade e o `UNIQUE`, e ela
#: existe porque esta ⛔ nao aguenta duas execucoes ao mesmo tempo.
SQL_PENDENTES = f"""
SELECT r.id_resolucao,
       r.id_usuario,
       d.id_desafio,
       COUNT(x.id_reacao) AS qt_pessoa
  FROM {VW_RESOLUCAO} r
  JOIN {VW_DESAFIO_DIA} d
    ON d.id_desafio_dia = r.id_desafio_dia
  JOIN {VW_REACAO} x
    ON x.id_resolucao = r.id_resolucao
  JOIN conta.tb001_usuario u
    ON u.id_usuario = r.id_usuario
  LEFT JOIN progressao.tb001_progressao_usuario g
    ON g.id_usuario = r.id_usuario
  LEFT JOIN {VW_NOTIFICACAO_REACAO} n
    ON n.id_resolucao = r.id_resolucao
 WHERE d.dt_dia = :dt_dia
   AND n.id_notificacao_reacao IS NULL
   AND {CLAUSULA_APARECE_EM_PUBLICO}
   AND NOT EXISTS (
         SELECT 1
           FROM conta.vw006_preferencia_notificacao p
          WHERE p.id_usuario = r.id_usuario
            AND p.co_categoria = :categoria
            AND NOT p.ic_ativo
       )
 GROUP BY r.id_resolucao, r.id_usuario, d.id_desafio
 ORDER BY r.id_resolucao
"""

#: Os aparelhos daquela pessoa **cujo relogio esta na janela**.
#:
#: ⚠️ **Filtrado pelo offset, e ⛔ nao todos os aparelhos dela.** Quem recebe e o
#: aparelho, e o meio-dia e o do relogio dele (RF-DES-074c): mandar para o
#: aparelho que ficou noutro fuso e acordar a pessoa de madrugada no tablet.
#:
#: ⚠️ **`id_usuario` casa por igualdade simples de proposito** - o token de
#: convidado tem `id_usuario` nulo, e convidado ⛔ nao tem resolucao nem linha no
#: quadro (RF-DES-084), entao ⛔ nao ha o que notificar.
#:
#: ⚠️ **Ordenado por `dh_atualizacao DESC`**: o primeiro e o aparelho em uso, e e
#: o offset dele que vai para o registro do envio.
SQL_DISPOSITIVOS = """
SELECT co_token_fcm, co_idioma, nu_offset_minuto
  FROM conta.vw005_dispositivo_notificacao
 WHERE id_usuario = :id_usuario
   AND nu_offset_minuto = ANY(:offsets)
 ORDER BY dh_atualizacao DESC
"""

#: A reserva. ⚠️ **`DO NOTHING` aqui e o certo**, ao contrario do ingestor da
#: `0006`: ⛔ nao ha nada a atualizar numa notificacao que ja saiu, e o que o
#: conflito significa e *"outra execucao chegou antes"*.
SQL_RESERVAR = f"""
INSERT INTO {TB_NOTIFICACAO_REACAO}
    (id_resolucao, qt_pessoa, nu_offset_minuto, qt_dispositivo, dh_envio)
VALUES (:id_resolucao, :qt_pessoa, :nu_offset_minuto, :qt_dispositivo, :dh_envio)
ON CONFLICT (id_resolucao) DO NOTHING
"""

#: Devolve a chance do dia quando **nenhum** aparelho aceitou a mensagem.
SQL_DESFAZER_RESERVA = f"""
DELETE FROM {TB_NOTIFICACAO_REACAO}
 WHERE id_resolucao = :id_resolucao
"""

#: Tira da base o token de um aparelho que ⛔ nao existe mais.
#:
#: ⚠️ **Sem filtro de dono, e de proposito**: quem manda e a resposta do FCM, que
#: e sobre o **token**. E a faxina que `scripts/faxina_tokens_fcm.py` fazia a mao
#: - com a diferenca de que agora ela acontece no instante em que se descobre.
SQL_REMOVER_TOKEN = """
DELETE FROM conta.tb005_dispositivo_notificacao
 WHERE co_token_fcm = :token
"""


@dataclass(frozen=True)
class PessoaANotificar:
    """Uma linha pendente: quem, de que desafio, e quantas pessoas reagiram."""

    id_resolucao: UUID
    id_usuario: UUID
    id_desafio: UUID
    qt_pessoa: int


@dataclass(frozen=True)
class Aparelho:
    """Um token na janela, com o idioma em que ele quer ler."""

    token: str
    idioma: str
    offset_minuto: int


class RepositorioNotificacaoDeReacao:
    """As idas ao banco do disparo. ⛔ ⛔ Nao decide nada."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def pendentes(self, dt_dia: date) -> list[PessoaANotificar]:
        """Quem recebeu reacao naquele dia e ainda ⛔ nao foi avisado."""
        resultado = await self.sessao.execute(
            text(SQL_PENDENTES),
            {"dt_dia": dt_dia, "categoria": CATEGORIA_REACOES},
        )
        return [
            PessoaANotificar(
                id_resolucao=linha["id_resolucao"],
                id_usuario=linha["id_usuario"],
                id_desafio=linha["id_desafio"],
                qt_pessoa=int(linha["qt_pessoa"]),
            )
            for linha in resultado.mappings().all()
        ]

    async def dispositivos(
        self, id_usuario: UUID, offsets: list[int]
    ) -> list[Aparelho]:
        """Os aparelhos daquela pessoa que estao na janela do meio-dia."""
        resultado = await self.sessao.execute(
            text(SQL_DISPOSITIVOS),
            {"id_usuario": id_usuario, "offsets": offsets},
        )
        return [
            Aparelho(
                token=linha["co_token_fcm"],
                idioma=linha["co_idioma"],
                offset_minuto=int(linha["nu_offset_minuto"]),
            )
            for linha in resultado.mappings().all()
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
        """Tenta reservar o direito de enviar. `False` = outra execucao chegou antes.

        ⚠️ **O `rowcount` e a resposta**, e ⛔ nao uma consulta antes do `INSERT`:
        entre a pergunta e a escrita, a outra execucao caberia inteira.
        """
        resultado = await self.sessao.execute(
            text(SQL_RESERVAR),
            {
                "id_resolucao": id_resolucao,
                "qt_pessoa": qt_pessoa,
                "nu_offset_minuto": nu_offset_minuto,
                "qt_dispositivo": qt_dispositivo,
                "dh_envio": dh_envio,
            },
        )
        return bool(resultado.rowcount)

    async def desfazer_reserva(self, id_resolucao: UUID) -> None:
        """Devolve a chance do dia - so quando **nenhum** aparelho aceitou."""
        await self.sessao.execute(
            text(SQL_DESFAZER_RESERVA), {"id_resolucao": id_resolucao}
        )

    async def remover_token(self, token: str) -> None:
        """Apaga da base o token de um aparelho que ⛔ nao existe mais."""
        await self.sessao.execute(text(SQL_REMOVER_TOKEN), {"token": token})

    async def confirmar(self) -> None:
        """Fecha a transacao.

        ⚠️ **O `commit` e por PESSOA, e ⛔ nao um no fim de tudo.** A reserva so
        vale contra outra execucao depois de confirmada; guardar tudo para o fim
        faria as duas enviarem em paralelo por uma hora inteira. E uma falha na
        pessoa 40 ⛔ nao apaga as 39 notificacoes que ja sairam.
        """
        await self.sessao.commit()

    async def desfazer(self) -> None:
        """Descarta o que esta pendente nesta pessoa (erro no meio do caminho)."""
        await self.sessao.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 6. O relatorio
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RelatorioDoDisparo:
    """O que esta execucao fez - e o que ela ⛔ nao conseguiu fazer.

    ⚠️ **Os numeros sao separados de proposito**, como no relatorio do job:
    *"atendi 3"* ⛔ nao distingue *"so havia 3"* de *"havia 40 e 37 falharam"*, e
    as duas situacoes pedem reacoes opostas de quem le o log.
    """

    #: Os fusos em que era meio-dia neste instante.
    offsets: list[int] = field(default_factory=list)

    #: `{dia alvo: quantas pessoas pendentes}` - o que a consulta achou.
    pendentes_por_dia: dict[str, int] = field(default_factory=dict)

    #: Notificacoes efetivamente aceitas pelo FCM (pessoas, ⛔ nao aparelhos).
    enviadas: int = 0

    #: Aparelhos que receberam - maior que [enviadas] quando alguem tem dois.
    aparelhos: int = 0

    #: Pendentes sem nenhum aparelho na janela. ⚠️ ⛔ **Nao gasta a reserva.**
    sem_aparelho: int = 0

    #: Reservas perdidas para outra execucao (o `UNIQUE` funcionando).
    ja_notificadas: int = 0

    #: Tokens mortos apagados da `tb005` no caminho.
    tokens_removidos: int = 0

    #: Pessoas em que **nenhum** aparelho aceitou - a reserva foi desfeita.
    nenhum_aceitou: int = 0

    #: Erros inesperados, por pessoa. ⚠️ Um deles ⛔ nao derruba o resto.
    falhas: list[str] = field(default_factory=list)

    def resumo(self) -> str:
        """Uma linha para o log do Railway."""
        return (
            f"fusos={self.offsets} pendentes={sum(self.pendentes_por_dia.values())} "
            f"enviadas={self.enviadas} aparelhos={self.aparelhos} "
            f"sem_aparelho={self.sem_aparelho} ja_notificadas={self.ja_notificadas} "
            f"tokens_removidos={self.tokens_removidos} "
            f"nenhum_aceitou={self.nenhum_aceitou} falhas={len(self.falhas)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 7. O servico
# ═══════════════════════════════════════════════════════════════════════════


class ServicoNotificacaoDeReacao:
    """Avisa quem recebeu reacao ontem - uma vez, ao meio-dia dela."""

    def __init__(
        self,
        repo: RepositorioNotificacaoDeReacao,
        enviador: EnviadorPorToken,
    ) -> None:
        self.repo = repo
        self._enviador = enviador

    async def disparar(self, agora_utc: datetime) -> RelatorioDoDisparo:
        """Faz a rodada deste instante e devolve o relatorio.

        Args:
            agora_utc: o instante do servidor, em UTC. ⚠️ **Parametro, e ⛔ nao
                `datetime.now()` aqui dentro**: um relogio interno tornaria a
                janela dos fusos impossivel de testar, e e justamente a conta que
                erra silenciosamente.

        Returns:
            O [RelatorioDoDisparo] - ⛔ nunca uma excecao por causa de **uma**
            pessoa. Uma linha ruim (token esquisito, resposta estranha do FCM) ⛔
            nao pode cancelar as outras 39 notificacoes da hora.
        """
        relatorio = RelatorioDoDisparo()
        for dia_alvo, offsets in grupos_por_dia_alvo(agora_utc).items():
            relatorio.offsets.extend(offsets)
            pendentes = await self.repo.pendentes(dia_alvo)
            relatorio.pendentes_por_dia[dia_alvo.isoformat()] = len(pendentes)
            for pessoa in pendentes:
                await self._uma_pessoa(pessoa, offsets, agora_utc, relatorio)
        return relatorio

    async def _uma_pessoa(
        self,
        pessoa: PessoaANotificar,
        offsets: list[int],
        agora_utc: datetime,
        relatorio: RelatorioDoDisparo,
    ) -> None:
        """Reserva, envia e conta - para uma pessoa, na ordem que importa."""
        try:
            aparelhos = await self.repo.dispositivos(pessoa.id_usuario, offsets)

            # ⛔ Sem aparelho na janela ⛔ nao se reserva: a linha queimaria a
            # unica chance daquele dia sem ninguem receber nada.
            if not aparelhos:
                relatorio.sem_aparelho += 1
                return

            reservou = await self.repo.reservar(
                id_resolucao=pessoa.id_resolucao,
                qt_pessoa=pessoa.qt_pessoa,
                # ⚠️ O offset do aparelho **em uso** (o primeiro da ordem por
                # `dh_atualizacao DESC`) - e a conta do meio-dia que valeu.
                nu_offset_minuto=aparelhos[0].offset_minuto,
                qt_dispositivo=len(aparelhos),
                dh_envio=agora_utc,
            )
            if not reservou:
                relatorio.ja_notificadas += 1
                await self.repo.desfazer()
                return

            # ⚠️ **Confirma a reserva ANTES de enviar.** Uma reserva ainda na
            # transacao ⛔ nao impede nada: outra execucao ⛔ nao a ve.
            await self.repo.confirmar()

            aceitos = await self._entregar(pessoa, aparelhos, relatorio)

            if aceitos:
                relatorio.enviadas += 1
                relatorio.aparelhos += aceitos
            else:
                # Todos os aparelhos estavam mortos: devolve a chance do dia.
                relatorio.nenhum_aceitou += 1
                await self.repo.desfazer_reserva(pessoa.id_resolucao)

            await self.repo.confirmar()
        except Exception as erro:  # noqa: BLE001 - uma pessoa ⛔ nao derruba a hora
            relatorio.falhas.append(f"{pessoa.id_resolucao}: {erro}")
            await self.repo.desfazer()

    async def _entregar(
        self,
        pessoa: PessoaANotificar,
        aparelhos: list[Aparelho],
        relatorio: RelatorioDoDisparo,
    ) -> int:
        """Manda a mensagem a cada aparelho e devolve quantos aceitaram.

        ⚠️ **Token morto sai da base no mesmo instante** - e a faxina que o
        script fazia a mao, agora no unico momento em que a informacao existe.
        """
        aceitos = 0
        for aparelho in aparelhos:
            titulo, corpo = texto_da_notificacao(pessoa.qt_pessoa, aparelho.idioma)
            try:
                self._enviador(
                    titulo,
                    corpo,
                    dados_do_push(pessoa.id_desafio, pessoa.qt_pessoa),
                    aparelho.token,
                )
                aceitos += 1
            except TokenMorto:
                await self.repo.remover_token(aparelho.token)
                relatorio.tokens_removidos += 1
        return aceitos
