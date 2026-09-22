"""O disparo de hora em hora da notificacao de reacoes (T079).

    python -m api.notificacoes.disparo_de_reacoes

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ELE RODA NA IMAGEM DA **API**, E ⛔ NAO NA DO JOB
═══════════════════════════════════════════════════════════════════════════

O repositorio tem duas imagens: a da API (`Dockerfile`) e a do job em batch
(`Dockerfile.job`). Este disparo e o **quarto servico** do projeto no Railway
(depois do Postgres, da API e do job), com cron de hora em hora - mas ele reusa a
imagem da **API**, e as razoes sao as duas metades do mesmo argumento:

  ⛔ **A imagem do job ⛔ nao tem `firebase-admin`**, e isso esta escrito em voz
     alta em `requirements_job.txt`: *"quem autentica pessoa e a API. O job nao ve
     ninguem."* Botar a lib la para mandar push contrariaria a unica razao pela
     qual aquela lista e curta - e ela carrega 19,8 MB de `.tflite` e o runtime de
     inferencia, dos quais aqui ⛔ nao se usa uma linha.

  ✅ **A imagem da API ja tem tudo**: `firebase-admin` (ela verifica token desde a
     US2), o SQLAlchemy e o codigo de `api/`. O que muda e o **comando de
     partida**: em vez do `uvicorn`, um `python -m`.

⚠️ **E ele ⛔ nao e uma rota.** Uma rota administrativa precisaria de alguem que a
chamasse de hora em hora, e o Railway ⛔ nao tem cron de HTTP - so cron de
processo. Alem disso, uma requisicao HTTP com tempo de resposta ⛔ nao e o lugar de
um laco que pode falar com o FCM dezenas de vezes.

⛔ **`railway.notificacoes.json` e DOCUMENTACAO, e ⛔ nao configuracao.** O
Config-as-code do Railway foi **descontinuado** (*"services that have never used
Config as Code cannot opt in"*, e os arquivos existentes param em 2026-12-01) - a
licao que a T049d pagou em 16/09/2026, quando o `railway.job.json` salvo no campo
simplesmente ⛔ nao aparecia listado. O servico se configura **na UI**, e o arquivo
existe para dizer, versionado, o que tem de estar la; um teste o compara com o nome
deste modulo, para os dois ⛔ nao se separarem.

⚠️ **O passo que ⛔ nao da erro quando e esquecido:** sem o *Custom Start Command*
na UI, o servico sobe o `uvicorn` do `CMD` da imagem - uma **terceira API**, verde
e inutil, e ⛔ nenhuma notificacao sai. ⚠️ **Confira pelo ESTADO** (a linha nova em
`tb008_notificacao_reacao`, numa hora cheia), e ⛔ nunca pela tela de configuracao.

═══════════════════════════════════════════════════════════════════════════
⚠️ A CONVENCAO DE SAIDA - A MESMA DO JOB, E PELO MESMO MOTIVO
═══════════════════════════════════════════════════════════════════════════

    0  →  fez (inclusive *"⛔ nao havia ninguem para avisar"*, que e o comum)
    1  →  fez, e alguma pessoa falhou no meio
    2  →  nem comecou (sem `DATABASE_URL`, sem credencial do Firebase, banco fora)

⚠️ **`2` e reservado ao que aconteceu ANTES do trabalho.** Uma falha na pessoa 40,
com 39 notificacoes ja entregues, ⛔ nao e *"nem comecou"* - e 1, com o id da
resolucao no log.

⚠️ **E hora vazia e SUCESSO.** A maior parte das execucoes ⛔ nao acha ninguem: sao
38 fusos no mundo e um punhado deles tem gente. Um codigo de erro aqui encheria o
painel do Railway de vermelho e ensinaria a ignora-lo.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Optional

from api.notificacoes.reacoes_do_desafio import (
    RelatorioDoDisparo,
    RepositorioNotificacaoDeReacao,
    ServicoNotificacaoDeReacao,
    TokenMorto,
)

#: As tres saidas possiveis do processo - ver o cabecalho.
CODIGO_FEZ = 0
CODIGO_FALHOU_ALGUMA = 1
CODIGO_NEM_COMECOU = 2


def enviar_para_token(
    titulo: str,
    corpo: str,
    dados: dict[str, str],
    token: str,
) -> str:
    """Enviador REAL: manda a mensagem para **um** aparelho pelo token.

    Args:
        titulo: o titulo, ja no idioma do aparelho.
        corpo: o corpo, idem.
        dados: o `data` do push (o assunto, ⛔ nao a rota).
        token: o `co_token_fcm` daquele aparelho.

    Returns:
        O id da mensagem que o FCM devolveu.

    Raises:
        TokenMorto: quando o FCM diz que aquele aparelho ⛔ nao existe mais.

    ⚠️ **O import de `firebase_admin` e local**, como no broadcast: a lib pesada
    so e carregada quando um envio realmente acontece - e e isso que deixa os
    testes deste modulo rodarem sem ela instalada.

    ⚠️ **Duas excecoes viram [TokenMorto], e uma terceira ⛔ NAO.**

      · `UnregisteredError` - o aparelho desinstalou, limpou os dados ou girou o
        token. E o caso comum, medido em 2026-07-12.
      · `SenderIdMismatchError` - o token e de **outro projeto** do Firebase (um
        `des` que ficou gravado no banco do `prd`, por exemplo). Ele ⛔ nunca vai
        funcionar aqui, e mante-lo faria a pessoa gastar a reserva do dia por um
        token que ⛔ nao e nosso.
      · `InvalidArgumentError` ⛔ **fica de fora de proposito**: ela tambem
        aparece quando o **payload** esta errado, e apagar o token nesse caso
        esconderia um defeito NOSSO destruindo a base de tokens - um por hora,
        sem que nada denunciasse.
    """
    from firebase_admin import messaging

    from api.nucleo.seguranca_firebase import garantir_app_firebase

    app = garantir_app_firebase()

    # ⚠️ **`token=`, e ⛔ NAO `fid=`.** O `firebase-admin` 7.x avisa que
    # `Message.token` esta depreciado *"em favor de `fid`"* - e trocar os dois
    # seria um erro de identidade, ⛔ nao uma modernizacao:
    #
    #   · `co_token_fcm` da `tb005` e o **registration token**, o que o aplicativo
    #     obtem com `FirebaseMessaging.getToken()`;
    #   · `fid` e o **Firebase Installation ID**, outra identidade - que o
    #     aplicativo em campo ⛔ nem reporta.
    #
    # ⚠️ **A imagem instala a 6.9.0** (presa em `requirements_api.txt`), onde o
    # campo ⛔ nao esta depreciado; o aviso aparece so no venv da maquina, que tem
    # a 7.5.0. No dia em que a imagem subir para a 7.x e o campo for removido, a
    # mudanca e dos **dois lados** (o aplicativo passa a reportar o FID) - e isso
    # e tarefa propria, ⛔ nunca um `fid=token`.
    mensagem = messaging.Message(
        notification=messaging.Notification(title=titulo, body=corpo),
        # O FCM exige valores string no `data`; convertemos por garantia.
        data={k: str(v) for k, v in dados.items()},
        token=token,
    )
    try:
        return messaging.send(mensagem, app=app)
    except (messaging.UnregisteredError, messaging.SenderIdMismatchError) as erro:
        raise TokenMorto(str(erro)) from erro


async def disparar(agora_utc: Optional[datetime] = None) -> RelatorioDoDisparo:
    """Abre a sessao, monta o servico com o enviador real e faz a rodada.

    Args:
        agora_utc: o instante a considerar. ⚠️ **Parametro so para o dono poder
            rodar uma hora especifica na maquina dele**; em producao vem `None` e
            vale o relogio do servidor.

    Returns:
        O relatorio da rodada.
    """
    # Import local: `api.nucleo.banco` cria a engine na importacao, e ela exige
    # `DATABASE_URL`. Importando aqui, a falta da variavel vira erro dentro do
    # `main()`, que sabe sair com [CODIGO_NEM_COMECOU].
    from api.nucleo.banco import SessaoLocal

    instante = agora_utc or datetime.now(timezone.utc)
    async with SessaoLocal() as sessao:
        servico = ServicoNotificacaoDeReacao(
            repo=RepositorioNotificacaoDeReacao(sessao),
            enviador=enviar_para_token,
        )
        return await servico.disparar(instante)


def main() -> int:
    """Roda a rodada desta hora e devolve o codigo de saida."""
    try:
        relatorio = asyncio.run(disparar())
    except Exception as erro:  # noqa: BLE001 - aqui e a fronteira do processo
        # ⚠️ Qualquer estouro que chegue aqui aconteceu **antes** do trabalho
        # (configuracao, banco fora, credencial): as falhas por pessoa ⛔ nao
        # sobem - elas viram linha no relatorio.
        print(f"⛔ [reacoes] nem comecou: {erro}", file=sys.stderr)
        return CODIGO_NEM_COMECOU

    print(f"[reacoes] {relatorio.resumo()}")
    for falha in relatorio.falhas:
        print(f"⚠️ [reacoes] falhou: {falha}", file=sys.stderr)
    return CODIGO_FALHOU_ALGUMA if relatorio.falhas else CODIGO_FEZ


if __name__ == "__main__":
    # `sys.exit` com o codigo: e por ele que o Railway distingue as tres saidas.
    sys.exit(main())
