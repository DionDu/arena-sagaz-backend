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

# Assinatura do "enviador": (titulo, corpo, dados, topico) -> id_da_mensagem.
EnviadorFcm = Callable[[str, str, Optional[dict[str, str]], str], str]


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
        topico: str = TOPICO_TODOS,
        idioma: Optional[str] = None,
    ) -> BroadcastResposta:
        """Envia a mensagem e devolve o id.

        Quando [idioma] vem preenchido, o destino é o tópico daquele idioma
        (`todos_pt`), e só quem lê o app naquele idioma recebe. Sem ele, o
        destino é [topico] - por padrão, o `todos` de sempre.
        """
        destino = topico_do_idioma(idioma) if idioma else topico
        id_mensagem = self._enviador(titulo, corpo, dados, destino)
        return BroadcastResposta(id_mensagem=id_mensagem, topico=destino)


def enviar_fcm_topico(
    titulo: str,
    corpo: str,
    dados: Optional[dict[str, str]],
    topico: str,
) -> str:
    """Enviador REAL: usa o Firebase Admin SDK para mandar a um tópico.

    O import de `firebase_admin` é **local** (dentro da função) para a app
    conseguir ser importada/testada sem a lib pesada — ela só é carregada quando
    um broadcast é realmente disparado.
    """
    from firebase_admin import messaging

    from api.nucleo.seguranca_firebase import garantir_app_firebase

    app = garantir_app_firebase()
    mensagem = messaging.Message(
        notification=messaging.Notification(title=titulo, body=corpo),
        # O FCM exige valores string no `data`; convertemos por garantia.
        data={k: str(v) for k, v in (dados or {}).items()},
        topic=topico,
    )
    return messaging.send(mensagem, app=app)
