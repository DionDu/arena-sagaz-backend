"""Serviço de notificações — regra de negócio do **broadcast** (envio a todos).

Estratégia escolhida: **tópico do FCM**. Cada aparelho do app se inscreve no
tópico `"todos"` (lado cliente, no Flutter); aqui o servidor envia UMA mensagem
para esse tópico e o FCM entrega a todos os inscritos. Vantagem: **não precisamos
guardar tokens de dispositivo no banco** (logo, sem mudança de schema) para o
caso "avisar todo mundo".

Para os testes não dependerem do `firebase_admin` (que pode não estar instalado
no ambiente local), o "enviador" é **injetável**: o serviço recebe uma função que
faz o envio. Em produção injetamos [enviar_fcm_topico] (real); nos testes, um
fake que só registra a chamada.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from api.notificacoes.modelos import BroadcastResposta

# Tópico em que TODOS os aparelhos se inscrevem (espelha o `topicoTodos` do app).
TOPICO_TODOS = "todos"

# ── Tópicos POR IDIOMA ────────────────────────────────────────────────────
#
# Desde 02/09/2026 cada aparelho também se inscreve num tópico do idioma em que
# o app está: `todos_pt`, `todos_en`, `todos_es`. Quem faz a inscrição (e a
# DESinscrição do idioma anterior) é o app, em
# `lib/core/notificacoes/topico_de_idioma.dart`.
#
# Por que existe: o broadcast sempre foi um tópico só, então todo aviso saía num
# idioma só - o mesmo texto para quem lê o app em português, inglês ou espanhol.
# Com os tópicos por idioma, avisar em três idiomas é disparar três vezes, cada
# uma com o seu texto, e continua sem guardar token de aparelho no banco.
#
# ⚠️ O nome tem de bater EXATAMENTE com o do app. O FCM não acusa envio para um
# tópico sem inscritos: a chamada volta com sucesso e um id de mensagem, e a
# notificação simplesmente não chega a ninguém.
PREFIXO_TOPICO_IDIOMA = "todos_"

# Os idiomas que o app publica. Espelha o `supportedLocales` do Flutter; um
# idioma novo entra aqui e no app na mesma mudança.
IDIOMAS_COM_TOPICO = ("pt", "en", "es")


def topico_do_idioma(idioma: str) -> str:
    """O tópico do [idioma] (`pt` -> `todos_pt`)."""
    return f"{PREFIXO_TOPICO_IDIOMA}{idioma}"


# ── Tópicos POR FUSO ──────────────────────────────────────────────────────
#
# `fuso_utc_menos_3`, `fuso_utc_0`, `fuso_utc_mais_5_30`. Quem inscreve o
# aparelho é o app (`lib/core/notificacoes/topico_de_fuso.dart`), a partir do
# mesmo offset que já vai no registro do dispositivo.
#
# **Para que servem.** Um tópico entrega NA HORA da chamada: um aviso disparado
# às 16h do Brasil chega às 4h da manhã de quem está no Japão. Cruzando idioma
# com fuso dá para falar só com quem está numa hora decente.
#
# ⚠️ **Por que o nome não é `fuso_+3`.** O FCM só aceita `[a-zA-Z0-9-_.~%]` em
# nome de tópico: o `-` passa, o `+` **não**. A família ficaria torta, com sinal
# no negativo e sem sinal no positivo. E nem todo fuso é hora inteira (Índia
# +5:30, Nepal +5:45, Chatham +12:45), então o sufixo de minutos é obrigatório.
#
# ⚠️ **Esta conta existe nos DOIS lados** - aqui e no Dart. Se as duas se
# separarem, o app assina um tópico e o servidor publica noutro: ninguém recebe,
# e o FCM devolve sucesso com id de mensagem. Os testes dos dois lados usam a
# MESMA tabela de exemplos.
PREFIXO_TOPICO_FUSO = "fuso_utc"

# Os offsets em uso no mundo, em minutos, do oeste para o leste.
#
# É **a lista que o job vai percorrer**: o desenho que o dono descreveu em
# 02/09/2026 é uma rotina que passa pelos fusos e dispara o push conforme chega
# a hora escolhida em cada um. Ver [fusos_na_hora_local], que é a conta que ela
# precisa.
#
# ⚠️ Nem todo offset daqui tem gente, e **tópico vazio aceita envio com
# sucesso** (id de mensagem e tudo). Isso é esperado: o job varre a lista e a
# maior parte dos disparos não encontra ninguém, sem erro nenhum.
#
# ⚠️ Esta lista **não valida** o que o aparelho reporta. Quem manda é o relógio
# do aparelho; um offset esquisito (relógio no manual) gera um tópico que o job
# nunca visita, e isso é preferível a o app falhar por causa de uma lista.
OFFSETS_DE_FUSO = (
    -720, -660, -600, -570, -540, -480, -420, -360, -300, -240,
    -210, -180, -120, -60, 0, 60, 120, 180, 210, 240,
    270, 300, 330, 345, 360, 390, 420, 480, 525, 540,
    570, 600, 630, 660, 720, 765, 780, 840,
)


def topico_do_fuso(offset_minuto: int) -> str:
    """O tópico do fuso cujo offset em relação ao UTC é [offset_minuto].

        0  -> fuso_utc_0
     -180  -> fuso_utc_menos_3
      330  -> fuso_utc_mais_5_30
     -210  -> fuso_utc_menos_3_30
    """
    if offset_minuto == 0:
        return f"{PREFIXO_TOPICO_FUSO}_0"

    # O sinal vira palavra (o `+` é proibido em tópico); o valor vira número.
    sinal = "menos" if offset_minuto < 0 else "mais"
    total = abs(offset_minuto)
    horas, minutos = divmod(total, 60)
    # Hora cheia não leva sufixo de minuto: `..._3`, e não `..._3_0`.
    sufixo = f"{horas}" if minutos == 0 else f"{horas}_{minutos}"
    return f"{PREFIXO_TOPICO_FUSO}_{sinal}_{sufixo}"


def fusos_na_hora_local(
    hora: int,
    agora_utc: datetime,
    minuto: int = 0,
    tolerancia_minutos: int = 30,
) -> list[int]:
    """Os offsets em que o relógio local marca [hora]:[minuto] **agora**.

    É a conta que o job de campanha precisa: rodando de tempos em tempos, ele
    pergunta "para quem são 20h neste momento?" e dispara para os tópicos
    devolvidos aqui. A hora é **parâmetro**, não constante - 20h foi só o
    exemplo do dono; serve qualquer horário, inclusive com minutos.

    [tolerancia_minutos] é a metade da janela aceita, e tem de casar com a
    frequência do job: rodando de hora em hora, 30 minutos cobre o dia inteiro
    sem repetir nem deixar buraco. Um job de 15 em 15 minutos usaria 7.

    ⚠️ **Sem tolerância, este mecanismo não funciona.** Os fusos de meia hora
    (Índia, Nepal, Terra Nova, Chatham) nunca marcam a hora cheia no mesmo
    instante que os demais; um job de hora em hora simplesmente **nunca**
    encontraria essas pessoas, e ninguém notaria - o disparo daria sucesso todas
    as vezes, para os outros.

    ⚠️ **E a janela é SEMIABERTA**: inclui o limite de baixo e exclui o de cima.
    Com ela fechada dos dois lados, um fuso de meia hora fica exatamente na
    borda de DUAS janelas consecutivas (a -30 de uma e a +30 da seguinte) e o
    job entrega o mesmo push duas vezes. Isso não é hipótese: o teste
    `test_a_janela_do_job_cobre_o_dia_sem_repetir` pegou oito fusos repetidos na
    primeira versão desta função, em 02/09/2026, antes de o job existir.
    """
    alvo = hora * 60 + minuto
    minutos_utc = agora_utc.hour * 60 + agora_utc.minute
    dia = 24 * 60
    encontrados = []
    for offset in OFFSETS_DE_FUSO:
        # O relógio local é o UTC deslocado pelo offset, dentro das 24 h.
        local = (minutos_utc + offset) % dia
        # A diferença COM SINAL no círculo do dia, em (-720, +720]. O círculo
        # importa: 23h59 e 00h01 estão a 2 minutos, e uma subtração simples
        # diria 1438.
        delta = (local - alvo + dia // 2) % dia - dia // 2
        if -tolerancia_minutos <= delta < tolerancia_minutos:
            encontrados.append(offset)
    return encontrados


# ── Tópicos POR PLATAFORMA ────────────────────────────────────────────────
#
# `plataforma_android` e `plataforma_ios`, para o aviso que só vale numa loja.
#
# ⚠️ Esta família é **diferente** das outras duas: não é exclusiva. Idioma e
# fuso são um de cada vez; aqui não há do que sair, e a mesma PESSOA pode estar
# nos dois se tiver os dois aparelhos - o tópico é do aparelho.
PREFIXO_TOPICO_PLATAFORMA = "plataforma_"

# Os mesmos códigos que o app já usa em `sg_plataforma` no registro do
# dispositivo - um vocabulário só para a mesma coisa.
PLATAFORMAS_COM_TOPICO = ("android", "ios")


def topico_da_plataforma(plataforma: str) -> str:
    """O tópico da [plataforma] (`ios` -> `plataforma_ios`)."""
    return f"{PREFIXO_TOPICO_PLATAFORMA}{plataforma}"


# ── A COMBINAÇÃO de tópicos ───────────────────────────────────────────────
#
# O FCM entrega para um tópico (`topic=`) **ou** para uma expressão sobre
# tópicos (`condition=`), nunca para os dois campos ao mesmo tempo.
#
# ⚠️ **Máximo de 5 tópicos por expressão** - é limite do FCM, não escolha nossa.
MAXIMO_DE_TOPICOS_NA_CONDICAO = 5


def montar_condicao(topicos: list[str]) -> str:
    """Monta a expressão que o FCM entende, exigindo TODOS os [topicos].

    `["todos_pt", "fuso_utc_menos_3"]` vira
    `'todos_pt' in topics && 'fuso_utc_menos_3' in topics`.

    Só recebe quem está em **todos** eles. A linguagem do FCM também tem `||` e
    parênteses; aqui só o `&&` é gerado, porque "quem está nos dois" é o que a
    segmentação pede - a união é a mesma coisa que dois envios.
    """
    if len(topicos) > MAXIMO_DE_TOPICOS_NA_CONDICAO:
        raise ValueError(
            f"O FCM aceita no máximo {MAXIMO_DE_TOPICOS_NA_CONDICAO} tópicos "
            f"por condição; vieram {len(topicos)}."
        )
    return " && ".join(f"'{t}' in topics" for t in topicos)


# Assinatura do "enviador": (titulo, corpo, dados, topico, condicao) -> id.
# Exatamente um entre `topico` e `condicao` vem preenchido.
EnviadorFcm = Callable[
    [str, str, Optional[dict[str, str]], Optional[str], Optional[str]], str
]


class ServicoNotificacoes:
    """Orquestra o disparo de notificações. Fino de propósito: a regra é só
    "montar e enviar"; o COMO enviar fica no [EnviadorFcm] injetado."""

    def __init__(self, enviador: EnviadorFcm):
        self._enviador = enviador

    def enviar_broadcast(
        self,
        titulo: str,
        corpo: str,
        dados: Optional[dict[str, str]] = None,
        topico: Optional[str] = None,
        idioma: Optional[str] = None,
        fuso: Optional[int] = None,
        plataforma: Optional[str] = None,
        topicos: Optional[list[str]] = None,
    ) -> BroadcastResposta:
        """Envia a mensagem e devolve o id, com o destino que foi usado.

        Os critérios se **somam**, e quem estiver em todos recebe:

        * nada preenchido -> `todos`, o app inteiro, como sempre foi;
        * um só critério -> aquele tópico (`topic=`), que é o caminho mais
          direto e o que o FCM prefere;
        * dois ou mais -> uma condição (`condition=`), com `&&`.

        [topicos] aceita tópicos que não vêm de um critério fechado (`novidades`,
        `promocoes`), para cruzar com os demais.

        ⚠️ Combinar mais de 5 tópicos levanta `ValueError` - é limite do FCM.
        """
        alvos: list[str] = []
        if topico:
            alvos.append(topico)
        if idioma:
            alvos.append(topico_do_idioma(idioma))
        if fuso is not None:
            alvos.append(topico_do_fuso(fuso))
        if plataforma:
            alvos.append(topico_da_plataforma(plataforma))
        alvos.extend(topicos or [])

        # Nenhum critério: o comportamento de sempre.
        if not alvos:
            alvos = [TOPICO_TODOS]

        # `dict.fromkeys` remove repetido MANTENDO a ordem - um `set` daria uma
        # condição em ordem imprevisível, e a resposta ficaria difícil de
        # conferir de um envio para o outro.
        alvos = list(dict.fromkeys(alvos))

        if len(alvos) == 1:
            id_mensagem = self._enviador(titulo, corpo, dados, alvos[0], None)
            return BroadcastResposta(id_mensagem=id_mensagem, topico=alvos[0])

        condicao = montar_condicao(alvos)
        id_mensagem = self._enviador(titulo, corpo, dados, None, condicao)
        return BroadcastResposta(id_mensagem=id_mensagem, condicao=condicao)


def enviar_fcm_topico(
    titulo: str,
    corpo: str,
    dados: Optional[dict[str, str]],
    topico: Optional[str] = None,
    condicao: Optional[str] = None,
) -> str:
    """Enviador REAL: usa o Firebase Admin SDK para mandar a um tópico **ou** a
    uma combinação deles.

    O import de `firebase_admin` é **local** (dentro da função) para a app
    conseguir ser importada/testada sem a lib pesada — ela só é carregada quando
    um broadcast é realmente disparado.

    ⚠️ `topic` e `condition` são **mutuamente exclusivos** no FCM: mandar os
    dois é erro da biblioteca. Por isso o `Message` é montado com um ou com o
    outro, e nunca com os dois campos presentes.
    """
    from firebase_admin import messaging

    from api.nucleo.seguranca_firebase import garantir_app_firebase

    if bool(topico) == bool(condicao):
        raise ValueError("Informe exatamente um entre `topico` e `condicao`.")

    app = garantir_app_firebase()
    mensagem = messaging.Message(
        notification=messaging.Notification(title=titulo, body=corpo),
        # O FCM exige valores string no `data`; convertemos por garantia.
        data={k: str(v) for k, v in (dados or {}).items()},
        topic=topico,
        condition=condicao,
    )
    return messaging.send(mensagem, app=app)
