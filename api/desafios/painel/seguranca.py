"""QUEM PODE ENTRAR NO PAINEL (RF-DES-012e).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE NAO E O LOGIN DO APLICATIVO
═══════════════════════════════════════════════════════════════════════════

O projeto **nao tem papeis** (nao existe "usuario administrador" no banco), e
inventar um so para esta pagina significaria uma coluna nova em `conta`, uma
migracao em schema **de producao** e uma superficie de escalonamento de
privilegio — tudo para um painel que uma pessoa so abre.

O caminho ja trilhado neste repositorio e o **segredo compartilhado**: e o que
`POST /v1/notificacoes/broadcast` faz desde a spec 006, com o cabecalho
`X-Admin-Token`. Aqui vale o mesmo principio, com **um segredo proprio** — quem
puder disparar notificacao para toda a base nao deveria, pelo mesmo token, poder
aprovar conteudo (e vice-versa).

═══════════════════════════════════════════════════════════════════════════
⚠️ E POR QUE HA UM COOKIE, ALEM DO CABECALHO
═══════════════════════════════════════════════════════════════════════════

Cabecalho e otimo para `curl` e para teste; **navegador nao manda cabecalho
proprio** ao seguir um link. Sem cookie, cada clique no painel exigiria o dono
colar o token de novo — e a saida obvia (`?token=` em toda URL) deixaria o
segredo em **todo** link, em todo histórico e em todo `Referer`.

O desenho e o mais simples que resolve os dois:

  1. a primeira visita chega com `?token=<segredo>`;
  2. o servidor confere, grava o cookie `HttpOnly` e **redireciona para a mesma
     URL sem o token** — a barra de enderecos fica limpa a partir do 1o quadro;
  3. dali em diante o cookie autentica.

⚠️ `HttpOnly` (JavaScript nao le), `SameSite=strict` (nao viaja em requisicao
disparada por outro site) e `Secure` **em producao** (so por HTTPS). Em
desenvolvimento o `Secure` sai, porque `http://localhost` nao e HTTPS e o cookie
seria descartado sem aviso nenhum.

═══════════════════════════════════════════════════════════════════════════
⛔ SEM SEGREDO CONFIGURADO, O PAINEL NAO EXISTE
═══════════════════════════════════════════════════════════════════════════

`PAINEL_CURADORIA_TOKEN` vazio **desabilita** a pagina inteira (401), e esse e o
default. E a mesma escolha do broadcast, pelo mesmo motivo: um painel que abre
sozinho quando alguem esquece de configurar a variavel e pior que um painel que
nao abre — o primeiro falha em silencio, o segundo falha alto.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Cookie, Header, Query

from api.configuracao import configuracoes
from api.nucleo.excecoes import ErroNaoAutorizado

#: Nome do cookie que guarda o segredo depois da primeira visita.
#:
#: ⚠️ O prefixo `__Host-` **nao** e usado de proposito: ele exige `Secure`, e em
#: desenvolvimento (`http://localhost`) o navegador descartaria o cookie sem
#: dizer nada — o painel simplesmente nao logaria, e a causa seria invisivel.
NOME_DO_COOKIE = "painel_curadoria"

#: Quanto tempo o cookie vale, em segundos (12 horas).
#:
#: ⚠️ Nao e "para sempre": o painel e uma ferramenta de sessao de trabalho, e um
#: cookie eterno num navegador emprestado seria uma credencial esquecida.
VALIDADE_DO_COOKIE_S = 12 * 60 * 60


class PainelDesabilitado(ErroNaoAutorizado):
    """Nao ha `PAINEL_CURADORIA_TOKEN` configurado — a pagina nao existe.

    Erro proprio (e nao um 401 generico) porque as duas causas pedem acoes
    diferentes de quem esta lendo o log: *"configure a variavel no Railway"* nao
    se parece nem um pouco com *"alguem tentou entrar com o token errado"*.
    """

    def __init__(self) -> None:
        super().__init__(
            "Painel de curadoria desabilitado (sem PAINEL_CURADORIA_TOKEN).",
            "painel_desabilitado",
        )


def segredo_configurado() -> str:
    """O segredo do painel, ja sem espacos em volta.

    Returns:
        O segredo.

    Raises:
        PainelDesabilitado: quando a variavel nao esta configurada.
    """
    segredo = (configuracoes.PAINEL_CURADORIA_TOKEN or "").strip()
    if not segredo:
        raise PainelDesabilitado()
    return segredo


def _confere(candidato: Optional[str], segredo: str) -> bool:
    """O valor apresentado e o segredo?

    ⚠️ `secrets.compare_digest` compara em **tempo constante**: um `==` comum
    volta mais rapido quando o primeiro caractere ja difere, e isso, medido
    muitas vezes, entrega o segredo caractere a caractere. E a mesma protecao que
    `exigir_admin` usa no broadcast (MEL-02).
    """
    if not candidato:
        return False
    return secrets.compare_digest(candidato.strip(), segredo)


def exigir_curador(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    token: Optional[str] = Query(default=None),
    painel_curadoria: Optional[str] = Cookie(default=None),
) -> bool:
    """Autoriza a visita, por qualquer um dos tres caminhos.

    Args:
        x_admin_token: o cabecalho — e o caminho de `curl` e dos testes.
        token: a query string — e o caminho da **primeira** visita no navegador.
        painel_curadoria: o cookie — e o caminho de todas as visitas seguintes.

    Returns:
        `True` quando a autorizacao veio **pela query string**, e portanto a rota
        precisa gravar o cookie e redirecionar para a URL limpa. `False` quando
        veio pelo cookie ou pelo cabecalho, e nao ha nada a fazer.

    Raises:
        PainelDesabilitado: sem segredo configurado.
        ErroNaoAutorizado: com segredo configurado e credencial errada.

    ⚠️ **O retorno e um booleano com significado, e nao um "deu certo"** — se
    fosse so sucesso, a rota nao teria como saber que precisa limpar a URL, e o
    token ficaria no historico do navegador para sempre.
    """
    segredo = segredo_configurado()

    if _confere(x_admin_token, segredo) or _confere(painel_curadoria, segredo):
        return False
    if _confere(token, segredo):
        return True

    raise ErroNaoAutorizado(
        "Token do painel de curadoria invalido.", "painel_token_invalido"
    )


def cookie_seguro() -> bool:
    """O cookie deve exigir HTTPS?

    Em producao, sim. Em desenvolvimento, nao — `http://localhost` nao e HTTPS, e
    um cookie `Secure` ali seria descartado pelo navegador **sem mensagem
    nenhuma**, deixando o painel num laco de redirecionamento inexplicavel.
    """
    return configuracoes.eh_producao
