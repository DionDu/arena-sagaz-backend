"""O MERGE DO CONVIDADO NO DESAFIO (T079a) — medido contra o `des`, sem deixar rastro.

═══════════════════════════════════════════════════════════════════════════
O QUE A US12 PROMETE, E POR QUE SO O SERVIDOR RESPONDE
═══════════════════════════════════════════════════════════════════════════

O Independent Test da US12 diz: *"resolver 5 desafios como convidado, fazer login
e conferir que os 5 apareceram na conta, uma vez so"*. O aplicativo sabe o que
**mandou**; so o banco sabe o que **ficou** — e "uma vez so" e pergunta de
constraint, que dubles de SQL (`tests/unitarios/fakes_desafio.py`) nao respondem.

═══════════════════════════════════════════════════════════════════════════
⚠️ COMO A MIGRACAO ACONTECE — E POR QUE NAO HA TABELA DE LOTE AQUI
═══════════════════════════════════════════════════════════════════════════

A rota da resolucao **exige conta** (T043): o convidado joga e ve o quadro, mas o
envio dele ⛔ nao sobe enquanto ele e convidado. Ele fica na **fila do aparelho**
(`sync_outbox`) — junto com a partida de desafio que ele aponta — e sobe **depois
do login**, com o token da conta nova. E exatamente assim que as partidas comuns
do convidado migram desde a spec 006: o dono de tudo o que chega e sempre o
`id_usuario` **do token**, e nunca um valor do corpo.

Por isso o servidor ⛔ nao guarda nada "do convidado" para juntar depois, e a
idempotencia nao precisa do lote: ela ja e a chave natural `(dia, pessoa)` da
resolucao (`uq` de `tb003_resolucao`), o `id_partida UNIQUE` da tentativa e o
`co_evento` da partida. O `LoteConvidado` continua fazendo o que fazia — a
progressao que ⛔ nao vira evento (chama e conquistas) sobe pelo
`/v1/sincronizacao/merge-convidado`, idempotente pelo `co_lote_migracao`.

⚠️ **E o campo `origem` do envio e so aceito, nunca lido.** Quem decide o dono e o
token; ler o `lote` do corpo daria a quem monta o corpo o poder de escolher em
nome de quem a resolucao entra.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE FAZ
═══════════════════════════════════════════════════════════════════════════

Sobe o **aplicativo de verdade** (`api.main:app`) em memoria, por `ASGITransport`,
falando com o `des` — igual a `conferir_portao_t050.py`. E reproduz o que o
aparelho faz quando o convidado entra:

  1. ⚠️ **a conta nasce** (`POST /v1/conta/sessao`), como no primeiro login;
  2. **uma resolucao sobe ANTES da partida dela** — a fila nao garante ordem, e
     o servidor tem de **segurar** (409), nunca recusar;
  3. o **merge da progressao** (`/merge-convidado`), com o lote do convidado;
  4. as **cinco partidas** de desafio pelo lote de eventos — de **cinco dias
     diferentes**, os passados incluidos: o convidado resolveu ao longo da
     semana e so entrou hoje;
  5. as **cinco resolucoes**;
  6. ⚠️ **o login de novo**: tudo reenviado, o merge inclusive.

E confere no banco — pela mesma transacao — que ha **cinco** resolucoes, cinco
tentativas, cinco partidas e o extrato **uma vez so**; que o resumo do mes e o
quadro de cada dia enxergam a conta; e que um dia que a conta ⛔ ja tinha
resolvido em outro aparelho **mantem a primeira resolucao** (RF-DES-004a).

═══════════════════════════════════════════════════════════════════════════
⛔ E NAO DEIXA NADA NO `des`
═══════════════════════════════════════════════════════════════════════════

Tudo roda numa **transacao unica**, desfeita no fim com `ROLLBACK`. As rotas
continuam dando `commit` — mas a sessao de cada requisicao nasce com
`join_transaction_mode="create_savepoint"`, e o `commit` dela so fecha um
*savepoint* dentro da transacao do script. A ultima condicao confere, por uma
**conexao nova**, que a conta criada nao existe mais.

⚠️ **O que se substitui e so a verificacao do token do Firebase**, como no portao
— a assinatura e do Firebase, e nao deste servidor. O dono de cada requisicao
continua sendo resolvido no banco, pelo `co_identidade_externa`.

⛔ **So no `des`.** A URL vem de `DATABASE_URL_DES` no catalogo fora do Git, e o
script pergunta a `identificar_banco.py` se host e porta sao mesmo os do `des`
antes de abrir a transacao. ⛔ Nunca imprime a URL nem a senha.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_merge_convidado_t079a.py

Leva menos de um minuto. Saida: um relatorio por condicao, com o numero de onde
cada veredito saiu, e codigo de saida 0 so quando todas fecham.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

# `parents[1]` e a raiz do backend: e dela que `api` e `scripts` sao importaveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Reuso, e nao copia: a leitura do catalogo, os cabecalhos e o relatorio sao os
# do portao; o nome do ambiente e o de `identificar_banco.py`. Dois lugares para
# decidir "qual banco e este" acabariam discordando um dia.
from scripts.conferir_portao_t050 import (  # noqa: E402
    CABECALHOS,
    Relatorio,
    url_do_des,
)
from scripts.identificar_banco import _nomear_ambiente  # noqa: E402

#: Quantos desafios o convidado resolveu — o numero do Independent Test.
QUANTOS = 5

#: A pontuacao que o convidado mandou em cada resolucao. ⚠️ Diferente de
#: [PONTUACAO_DA_CONTA] de proposito: e o que deixa ver QUAL das duas ficou.
PONTUACAO_DO_CONVIDADO = 26

#: A pontuacao da resolucao que a conta ja tinha feito em outro aparelho.
PONTUACAO_DA_CONTA = 20

#: Os nomes das condicoes — escritos uma vez, para o texto nao divergir.
C_CONTA = "(a) o convidado entra, e a conta nasce"
C_ORDEM = "(b) a fila do aparelho sobe fora de ordem, e nada se perde"
C_CONTA_VE = "(c) os desafios do convidado aparecem na conta"
C_REPETE = "(d) repetir o login nao duplica nada"
C_PRIMEIRA = "(e) o dia que a conta ja tinha resolvido mantem a primeira"
C_RASTRO = "(f) nada ficou no `des`"


# ═══════════════════════════════════════════════════════════════════════════
# O QUE O APARELHO MANDA
# ═══════════════════════════════════════════════════════════════════════════
#
# Os dois corpos abaixo sao os que o aplicativo monta: a partida em
# `servico_log_partida.dart` (`_montarPayload`) e a resolucao em
# `outbox_desafio.dart` (`enfileirar`). Os campos que o servidor ⛔ nao le para
# esta conferencia (lances, extensao por jogo) ficam de fora.


def instante_no_dia(dia: date, agora: datetime) -> datetime:
    """O meio-dia UTC de [dia] — ou um minuto atras, se o dia e hoje.

    ⚠️ Hoje as 00:30 UTC o meio-dia ainda nao chegou, e uma partida "do futuro"
    mediria outra coisa. Um minuto atras e sempre um instante que ja existiu.
    """
    meio_dia = datetime.combine(dia, time(12, 0), tzinfo=timezone.utc)
    return min(meio_dia, agora - timedelta(minutes=1))


def evento_de_partida(
    *, co_evento: str, dia: dict[str, Any], lote: str, inicio: datetime
) -> dict[str, Any]:
    """O evento da partida de desafio, como o outbox o manda.

    ⚠️ `co_lote_migracao` vai preenchido: a partida foi jogada como convidado, e
    o aplicativo carimba o lote nela desde a spec 006. O servidor o guarda, mas o
    dono continua sendo o do token.
    """
    return {
        "co_evento": co_evento,
        "co_tipo": "partida",
        "payload": {
            "partida": {
                "id_partida": str(uuid.uuid4()),
                "co_jogo": dia["co_jogo"],
                "co_variante": dia["co_variante"],
                # ⚠️ `co_modo='desafio'` e `ic_pontua=False`: a resolucao E uma
                # partida (RF-DES-186), e ela ⛔ nao passa pelo XP de partida.
                "co_modo": "desafio",
                "nu_placar_j1": 1,
                "nu_placar_j2": 0,
                "ic_pontua": False,
                "co_status": "concluida",
                "co_lote_migracao": lote,
                "dh_inicio": inicio.isoformat(),
                "dh_fim": (inicio + timedelta(minutes=2)).isoformat(),
                "nu_offset_minuto_j1": -180,
            },
            "jogadas": [],
            "xp": [],
        },
    }


def envio_de_resolucao(
    *,
    dia: dict[str, Any],
    co_evento_partida: str,
    pontuacao: int,
    resolvido_em: datetime,
    origem: dict[str, Any],
) -> dict[str, Any]:
    """O corpo de `POST /v1/desafios/{id}/resolucao`, como o outbox o manda."""
    return {
        "id_desafio_dia": str(dia["id_desafio_dia"]),
        "veredito": "resolvido",
        "tentativas": 1,
        "tempo_ms": 48210,
        "dicas_usadas": 0,
        "qualidade": 0.7325,
        "pontuacao": pontuacao,
        "co_evento_partida": co_evento_partida,
        "nu_lance_cumpre_desafio": 1,
        # ⛔ MEDIDAS, nunca XP (RF-DES-170). As do desafio vem de
        # [medidas_do_desafio]; as duas de sessao, daqui.
        "feitos": [
            *dia["feitos"],
            {"chave": "tempo_ate_resolver", "valor": 48210},
            {"chave": "tentativas", "valor": 1},
        ],
        "versao_catalogo_feitos": 1,
        "resolvido_em": resolvido_em.isoformat(),
        "origem": origem,
    }


# ═══════════════════════════════════════════════════════════════════════════
# O QUE SE LE DE VOLTA
# ═══════════════════════════════════════════════════════════════════════════

#: Quanto a conta tem em cada tabela que o envio escreve. ⚠️ Pelas VIEWs, como
#: toda leitura do projeto — e cada contagem e da CONTA, nunca do banco inteiro,
#: senao a atividade de outra pessoa no `des` mudaria o resultado.
SQL_CONTAGENS = """
SELECT
  (SELECT count(*) FROM desafio_dia.vw003_resolucao WHERE id_usuario = :u)
      AS resolucoes,
  (SELECT count(*) FROM desafio_dia.vw002_tentativa WHERE id_usuario = :u)
      AS tentativas,
  (SELECT count(*) FROM desafio_dia.vw004_xp_desafio WHERE id_usuario = :u)
      AS parcelas,
  (SELECT count(*) FROM partida.vw001_partida
    WHERE id_usuario = :u AND co_modo = 'desafio')
      AS partidas
"""


async def contagens(conexao, id_usuario: Any) -> dict[str, int]:
    """As quatro contagens da conta, como dicionario."""
    from sqlalchemy import text

    linha = (
        (await conexao.execute(text(SQL_CONTAGENS), {"u": id_usuario}))
        .mappings()
        .one()
    )
    return {chave: int(valor) for chave, valor in linha.items()}


#: A fracao cujo denominador ⛔ nao existe no catalogo de feitos.
#:
#: ⚠️ **Defeito do job, achado por este script em 22/09/2026**, e ⛔ fora da
#: migracao: o editorial publica `lances_do_jogador` como `fracao` sobre
#: `lances_da_solucao`, que nao e medida da partida (e o tamanho do gabarito).
#: O servidor recusa a chave (`feito_desconhecido`) se ela vier, e recusa a
#: resolucao (`medida_invalida`) se ela faltar - e o aplicativo tambem nao
#: consegue calcular `Q`. Um desafio assim ⛔ nao tem resolucao possivel, de
#: conta ou de convidado.
SQL_FRACAO_SEM_DENOMINADOR = """
EXISTS (SELECT 1 FROM desafio.vw003_feito_desafio f
         WHERE f.id_desafio = d.id_desafio
           AND f.co_normalizacao = 'fracao'
           AND NOT EXISTS (SELECT 1 FROM desafio.vw902_catalogo_feito c
                            WHERE c.co_feito = f.co_sobre))
"""


async def escolher_dias(conexao, hoje: date) -> list[dict[str, Any]]:
    """Ate [QUANTOS] dias mais recentes que ja comecaram, e que da para resolver.

    ⚠️ **Da para resolver** quer dizer: tem regua de tempo, tem ao menos um peso,
    e ⛔ nenhuma fracao aponta para um denominador fora do catalogo
    ([SQL_FRACAO_SEM_DENOMINADOR]). Sem isso o envio e recusado por outro motivo,
    e o script mediria esse motivo em vez da migracao.
    """
    from sqlalchemy import text

    linhas = (
        await conexao.execute(
            text(
                f"""
                SELECT d.dt_dia, d.id_desafio_dia, d.id_desafio,
                       v.co_jogo, v.co_variante
                  FROM desafio_dia.vw001_desafio_dia d
                  JOIN desafio.vw001_desafio v ON v.id_desafio = d.id_desafio
                 WHERE d.dt_dia <= :hoje
                   AND v.nu_tempo_piso_ms IS NOT NULL
                   AND v.nu_tempo_teto_ms IS NOT NULL
                   AND EXISTS (SELECT 1 FROM desafio.vw003_feito_desafio f
                                WHERE f.id_desafio = d.id_desafio)
                   AND NOT {SQL_FRACAO_SEM_DENOMINADOR}
                 ORDER BY d.dt_dia DESC
                 LIMIT :quantos
                """
            ),
            {"hoje": hoje, "quantos": QUANTOS},
        )
    ).mappings().all()
    dias = [dict(linha) for linha in linhas]
    for dia in dias:
        dia["feitos"] = await medidas_do_desafio(conexao, dia["id_desafio"])
    return dias


async def medidas_do_desafio(conexao, id_desafio: Any) -> list[dict[str, Any]]:
    """Uma medida para cada feito que o desafio pesa - e o denominador de cada fracao.

    ⚠️ **O aplicativo manda o extrato inteiro** (T056), e o servidor recusa o que
    falta: uma normalizacao `fracao` sem a medida de `co_sobre` nao tem
    denominador (`medida_invalida`). Mandar so as medidas de sessao, como o
    portao faz, passa num desafio sem fracao e falha nos outros - foi o que a
    primeira execucao deste script mostrou, em 22/09/2026.

    Os valores (1 para a medida, 2 para o denominador) ⛔ nao importam aqui: o
    que se mede e se a resolucao migra, e nao quanto ela vale.
    """
    from sqlalchemy import text

    pesos = (
        await conexao.execute(
            text(
                "SELECT co_feito, co_sobre FROM desafio.vw003_feito_desafio "
                " WHERE id_desafio = :d"
            ),
            {"d": id_desafio},
        )
    ).mappings().all()
    # As duas de sessao entram em [envio_de_resolucao]; aqui ficam de fora, para
    # a mesma chave nao ir duas vezes.
    sessao = {"tempo_ate_resolver", "tentativas", "dicas_usadas"}
    medidas: dict[str, int] = {}
    for peso in pesos:
        if peso["co_feito"] not in sessao:
            medidas[peso["co_feito"]] = 1
        if peso["co_sobre"] and peso["co_sobre"] not in sessao:
            medidas[peso["co_sobre"]] = 2
    return [{"chave": chave, "valor": valor} for chave, valor in medidas.items()]


# ═══════════════════════════════════════════════════════════════════════════
# A CONFERENCIA
# ═══════════════════════════════════════════════════════════════════════════


async def conferir() -> int:
    """Roda as seis condicoes e devolve o codigo de saida."""
    url = url_do_des()

    # ⛔ A trava, ANTES de qualquer import que crie o motor: host e porta tem de
    # ser os do `des` no catalogo. O nome do banco nao serve — os dois se chamam
    # `railway`.
    ambiente, explicacao = _nomear_ambiente(url)
    if ambiente != "DES":
        raise SystemExit(f"⛔ o banco nao e o `des` ({ambiente}: {explicacao}).")
    print(f"banco: DES ({explicacao})")

    # ⚠️ A URL tem de estar no ambiente ANTES de `api.main` ser importado: o motor
    # do SQLAlchemy nasce no import de `api.nucleo.banco`, lendo-a uma vez so.
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.main import app
    from api.nucleo.banco import engine as motor
    from api.nucleo.banco import obter_sessao
    from api.nucleo.dependencias import usuario_atual
    from api.nucleo.seguranca_firebase import IdentidadeFirebase

    relatorio = Relatorio()
    # Um uid que nenhuma conta real tem: e ele que a condicao (f) procura depois.
    uid = f"t079a-{uuid.uuid4()}"
    agora = datetime.now(timezone.utc)

    async with motor.connect() as conexao:
        # ⚠️ A transacao do SCRIPT. Tudo o que as rotas gravarem mora dentro
        # dela, e o `rollback` do `finally` desfaz tudo de uma vez.
        transacao = await conexao.begin()

        async def sessao_dentro_da_transacao():
            """A sessao de cada requisicao, presa a transacao do script.

            `join_transaction_mode="create_savepoint"`: o `commit()` da rota vira
            "libera o savepoint", e o `rollback()` dela, "volta ao savepoint" —
            a transacao de fora continua aberta, e so o script a encerra.
            """
            async with AsyncSession(
                bind=conexao,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as sessao:
                yield sessao

        app.dependency_overrides[obter_sessao] = sessao_dentro_da_transacao
        # ⚠️ So a verificacao do token e substituida; o dono continua sendo
        # resolvido no banco pelo `co_identidade_externa`.
        app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
            uid=uid, provedor="google.com", nome="Convidado T079a"
        )
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://t079a",
                headers=CABECALHOS,
            ) as cliente:
                await _migrar(cliente, conexao, relatorio, uid=uid, agora=agora)
        finally:
            app.dependency_overrides.pop(obter_sessao, None)
            app.dependency_overrides.pop(usuario_atual, None)
            await transacao.rollback()

    # ── (f) Nada ficou ──────────────────────────────────────────────────────
    #
    # ⚠️ Por uma CONEXAO NOVA: a de cima enxergaria a propria transacao, e a
    # pergunta e o que o resto do mundo ve.
    async with motor.connect() as outra:
        sobrou = (
            await outra.execute(
                text(
                    "SELECT count(*) FROM conta.vw001_usuario "
                    " WHERE co_identidade_externa = :uid"
                ),
                {"uid": uid},
            )
        ).scalar_one()
    relatorio.anotar(
        C_RASTRO,
        sobrou == 0,
        "depois do ROLLBACK a conta criada nao existe (0 linhas) - e, sem ela, "
        "nada que apontava para ela"
        if sobrou == 0
        else f"⛔ a conta do script continua no `des` ({sobrou} linha)",
    )

    await motor.dispose()
    return 0 if relatorio.imprimir() else 1


async def _migrar(cliente, conexao, relatorio: Relatorio, *, uid: str, agora) -> None:
    """O login do convidado, do primeiro envio ao reenvio. Condicoes (a) a (e)."""
    from sqlalchemy import text

    # ── (a) A conta nasce ────────────────────────────────────────────────────
    r = await cliente.post(
        "/v1/conta/sessao",
        json={
            "no_exibicao": "Convidado T079a",
            "ic_idade_minima_declarada": True,
            "co_idioma_preferido": "pt",
        },
    )
    id_usuario = (
        await conexao.execute(
            text(
                "SELECT id_usuario FROM conta.vw001_usuario "
                " WHERE co_identidade_externa = :uid"
            ),
            {"uid": uid},
        )
    ).scalar()
    relatorio.anotar(
        C_CONTA,
        r.status_code == 200 and id_usuario is not None,
        f"POST /v1/conta/sessao → {r.status_code}, e a conta esta no banco"
        if id_usuario is not None
        else f"⛔ a conta nao nasceu: {r.status_code} {r.text[:200]}",
    )
    if id_usuario is None:
        return

    dias = await escolher_dias(conexao, agora.date())
    # ⚠️ Dois e o minimo que mede alguma coisa: um dia para a conta ja ter
    # resolvido (condicao (e)) e ao menos um que so o convidado resolveu.
    relatorio.anotar(
        C_CONTA,
        len(dias) >= 2,
        f"{len(dias)} de {QUANTOS} dias com desafio resolvivel no `des`, de "
        f"{dias[-1]['dt_dia']} a {dias[0]['dt_dia']}"
        if dias
        else "⛔ o `des` nao tem desafio resolvivel",
    )
    # ⚠️ Os dias pulados sao DITOS, nunca escondidos: sem esta linha o script
    # passaria em silencio sobre um desafio que ninguem consegue resolver.
    pulados = (
        await conexao.execute(
            text(
                "SELECT d.dt_dia FROM desafio_dia.vw001_desafio_dia d "
                f" WHERE d.dt_dia <= :hoje AND {SQL_FRACAO_SEM_DENOMINADOR} "
                " ORDER BY d.dt_dia"
            ),
            {"hoje": agora.date()},
        )
    ).scalars().all()
    if pulados:
        relatorio.anotar(
            C_CONTA,
            True,
            f"⚠️ {len(pulados)} dia(s) pulado(s), sem resolucao possivel para "
            f"NINGUEM (fracao sobre medida fora do catalogo - defeito do job, "
            f"fora da T079a): {', '.join(str(d) for d in pulados)}",
        )
    if len(dias) < 2:
        return

    # O lote do convidado — o mesmo UUID que o `LoteConvidado` guarda no aparelho.
    lote = str(uuid.uuid4())
    origem = {"tipo": "convidado", "lote": lote}

    # ⚠️ O dia MAIS ANTIGO fica para a condicao (e): a conta o resolve "em outro
    # aparelho" antes da migracao. Os outros sao do convidado.
    dia_da_conta, dias_do_convidado = dias[-1], dias[:-1]
    await _conta_ja_resolveu(cliente, relatorio, dia_da_conta, agora)

    partidas: list[dict[str, Any]] = []
    envios: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for dia in dias:  # ⚠️ inclui o da conta: o convidado tambem o resolveu
        inicio = instante_no_dia(dia["dt_dia"], agora)
        co_evento = str(uuid.uuid4())
        partidas.append(
            evento_de_partida(co_evento=co_evento, dia=dia, lote=lote, inicio=inicio)
        )
        envios.append(
            (
                dia,
                envio_de_resolucao(
                    dia=dia,
                    co_evento_partida=co_evento,
                    pontuacao=PONTUACAO_DO_CONVIDADO,
                    resolvido_em=inicio + timedelta(minutes=2),
                    origem=origem,
                ),
            )
        )

    antes = await contagens(conexao, id_usuario)

    # ── (b) Fora de ordem ────────────────────────────────────────────────────
    #
    # ⚠️ A resolucao do dia mais recente sobe ANTES da partida dela. A fila do
    # aparelho nao garante a ordem, e a resposta certa e SEGURAR (409): o
    # aplicativo reenvia. Um 400 aqui expurgaria a resolucao da fila.
    dia0, envio0 = envios[0]
    r = await cliente.post(f"/v1/desafios/{dia0['id_desafio']}/resolucao", json=envio0)
    relatorio.anotar(
        C_ORDEM,
        r.status_code == 409,
        "a resolucao que chegou antes da partida foi SEGURADA (409), e nao recusada"
        if r.status_code == 409
        else f"⛔ esperava 409, veio {r.status_code} {r.text[:200]}",
    )

    # O merge da progressao: a parte do login que ja existia (spec 006).
    r = await cliente.post(
        "/v1/sincronizacao/merge-convidado",
        json={
            "co_lote_migracao": lote,
            "progressao_convidado": {
                "nu_xp_total": 0,
                "nu_partidas": 0,
                "nu_vitorias": 0,
                "nu_derrotas": 0,
                "nu_empates": 0,
                "nu_sequencia_atual": len(dias),
                "conquistas": [],
            },
        },
    )
    aplicado_1 = r.json().get("aplicado") if r.status_code == 200 else None
    relatorio.anotar(
        C_ORDEM,
        aplicado_1 is True,
        "o merge da progressao aplicou o lote do convidado (aplicado=true)"
        if aplicado_1 is True
        else f"⛔ merge-convidado: {r.status_code} {r.text[:200]}",
    )

    r = await cliente.post("/v1/sincronizacao/eventos", json={"eventos": partidas})
    aceitos = set(r.json().get("aceitos", [])) if r.status_code == 200 else set()
    esperados = {p["co_evento"] for p in partidas}
    relatorio.anotar(
        C_ORDEM,
        aceitos == esperados,
        f"as {len(partidas)} partidas de desafio subiram pelo lote de eventos, "
        "de dias diferentes"
        if aceitos == esperados
        else f"⛔ partidas aceitas: {len(aceitos)} de {len(esperados)} "
        f"({r.status_code} {r.text[:200]})",
    )

    ids_primeira_vez: dict[str, Any] = {}
    for dia, envio in envios:
        r = await cliente.post(f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio)
        corpo = r.json() if r.status_code == 200 else {}
        ids_primeira_vez[str(dia["id_desafio"])] = corpo.get("id_resolucao")
        eh_da_conta = dia is dia_da_conta
        # ⚠️ O dia da conta responde `ja_existia: true` ja na PRIMEIRA vez: a
        # resolucao do outro aparelho chegou antes. Os outros sao novos.
        esperado = eh_da_conta
        ok = corpo.get("aceita") is True and corpo.get("ja_existia") is esperado
        relatorio.anotar(
            C_ORDEM,
            ok,
            f"{dia['dt_dia']}: aceita, ja_existia={corpo.get('ja_existia')}"
            + (" (a conta ja tinha este dia)" if eh_da_conta else "")
            if ok
            else f"⛔ {dia['dt_dia']}: {r.status_code} {r.text[:200]}",
        )

    depois = await contagens(conexao, id_usuario)

    # ── (c) A conta enxerga ──────────────────────────────────────────────────
    #
    # ⚠️ Contra o ANTES, e nao contra zero: a conta ja tinha um dia (o da
    # condicao (e)). O que se mede e o que a migracao acrescentou.
    novos = len(dias_do_convidado)
    ganho = {chave: depois[chave] - antes[chave] for chave in depois}
    relatorio.anotar(
        C_CONTA_VE,
        ganho["resolucoes"] == novos,
        f"resolucoes da conta: {antes['resolucoes']} → {depois['resolucoes']} "
        f"(+{ganho['resolucoes']}, esperado +{novos})",
    )
    # ⚠️ Tentativas e partidas crescem pelos CINCO dias, e nao pelos quatro: o
    # convidado tambem jogou o dia que a conta ja tinha. A partida e a tentativa
    # dele existem; o que ⛔ nao existe e uma segunda resolucao.
    relatorio.anotar(
        C_CONTA_VE,
        ganho["tentativas"] == len(dias) and ganho["partidas"] == len(dias),
        f"tentativas +{ganho['tentativas']} e partidas de desafio "
        f"+{ganho['partidas']} (esperado +{len(dias)} cada)",
    )
    relatorio.anotar(
        C_CONTA_VE,
        ganho["parcelas"] > 0,
        f"o extrato ganhou {ganho['parcelas']} parcelas "
        f"({ganho['parcelas'] / max(novos, 1):.0f} por resolucao nova)",
    )

    r = await cliente.get("/v1/desafios/meu-mes")
    mes = r.json() if r.status_code == 200 else {}
    resolvidos_no_mes = {
        d.get("dia") for d in mes.get("dias", []) if d.get("resolvido")
    }
    do_mes = {
        str(d["dt_dia"])
        for d in dias
        if (d["dt_dia"].year, d["dt_dia"].month) == (agora.year, agora.month)
    }
    relatorio.anotar(
        C_CONTA_VE,
        r.status_code == 200 and do_mes <= resolvidos_no_mes,
        f"o resumo do mes marca como resolvidos os {len(do_mes)} dias deste mes "
        f"(total do mes: {mes.get('resolvidos')})"
        if do_mes <= resolvidos_no_mes
        else f"⛔ meu-mes: faltam {sorted(do_mes - resolvidos_no_mes)} "
        f"({r.status_code})",
    )

    # O quadro PUBLICO de cada dia: sem `Authorization`, como o de qualquer um.
    fora_do_quadro = []
    for dia in dias:
        r = await cliente.get(f"/v1/desafios/{dia['id_desafio']}/quadro")
        linhas = r.json().get("linhas", []) if r.status_code == 200 else []
        if not any(
            linha.get("sujeito") == "jogador"
            and str(linha.get("id")) == str(id_usuario)
            for linha in linhas
        ):
            fora_do_quadro.append(str(dia["dt_dia"]))
    relatorio.anotar(
        C_CONTA_VE,
        not fora_do_quadro,
        f"a conta aparece no quadro publico dos {len(dias)} dias, os passados "
        "inclusive"
        if not fora_do_quadro
        else f"⛔ a conta nao aparece no quadro de {fora_do_quadro}",
    )

    # ── (d) O login de novo ──────────────────────────────────────────────────
    #
    # ⚠️ Tudo outra vez, na mesma ordem: e o que o aparelho faz quando o primeiro
    # envio morreu no meio, ou quando a pessoa sai e entra de novo antes de a
    # fila ser podada.
    r = await cliente.post(
        "/v1/sincronizacao/merge-convidado",
        json={
            "co_lote_migracao": lote,
            "progressao_convidado": {
                "nu_xp_total": 0,
                "nu_partidas": 0,
                "nu_vitorias": 0,
                "nu_derrotas": 0,
                "nu_empates": 0,
                "nu_sequencia_atual": len(dias),
                "conquistas": [],
            },
        },
    )
    aplicado_2 = r.json().get("aplicado") if r.status_code == 200 else None
    relatorio.anotar(
        C_REPETE,
        aplicado_2 is False,
        "o merge do mesmo lote nao aplicou de novo (aplicado=false)"
        if aplicado_2 is False
        else f"⛔ merge repetido: {r.status_code} aplicado={aplicado_2}",
    )

    r = await cliente.post("/v1/sincronizacao/eventos", json={"eventos": partidas})
    ignorados = set(r.json().get("ignorados", [])) if r.status_code == 200 else set()
    relatorio.anotar(
        C_REPETE,
        ignorados == esperados,
        f"as {len(partidas)} partidas reenviadas voltaram como `ignorados`"
        if ignorados == esperados
        else f"⛔ partidas reenviadas: {len(ignorados)} ignoradas de "
        f"{len(esperados)} ({r.status_code})",
    )

    mudaram = []
    for dia, envio in envios:
        r = await cliente.post(f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio)
        corpo = r.json() if r.status_code == 200 else {}
        if not (
            corpo.get("ja_existia") is True
            and corpo.get("id_resolucao") == ids_primeira_vez[str(dia["id_desafio"])]
        ):
            mudaram.append(f"{dia['dt_dia']} ({r.status_code})")
    relatorio.anotar(
        C_REPETE,
        not mudaram,
        f"as {len(envios)} resolucoes reenviadas devolveram a MESMA resolucao "
        "(ja_existia=true)"
        if not mudaram
        else f"⛔ reenvio mudou a resposta em {mudaram}",
    )

    final = await contagens(conexao, id_usuario)
    relatorio.anotar(
        C_REPETE,
        final == depois,
        f"nenhuma linha nova: {final}"
        if final == depois
        else f"⛔ o reenvio mudou as contagens: {depois} → {final}",
    )

    # ── (e) A primeira resolucao vale ────────────────────────────────────────
    nu_xp = (
        await conexao.execute(
            text(
                "SELECT nu_xp FROM desafio_dia.vw003_resolucao "
                " WHERE id_usuario = :u AND id_desafio_dia = :d"
            ),
            {"u": id_usuario, "d": dia_da_conta["id_desafio_dia"]},
        )
    ).scalars().all()
    relatorio.anotar(
        C_PRIMEIRA,
        list(nu_xp) == [PONTUACAO_DA_CONTA],
        f"{dia_da_conta['dt_dia']}: uma resolucao so, com a pontuacao da conta "
        f"({PONTUACAO_DA_CONTA}), e nao a do convidado ({PONTUACAO_DO_CONVIDADO})"
        if list(nu_xp) == [PONTUACAO_DA_CONTA]
        else f"⛔ {dia_da_conta['dt_dia']}: pontuacoes gravadas {list(nu_xp)}",
    )


async def _conta_ja_resolveu(cliente, relatorio: Relatorio, dia, agora) -> None:
    """A conta resolve [dia] "em outro aparelho", antes de a migracao chegar.

    ⚠️ E o caso de quem ja tinha conta, jogou como convidado num aparelho novo e
    so entrou depois. RF-DES-004a: a primeira resolucao e a que vale.
    """
    inicio = instante_no_dia(dia["dt_dia"], agora) - timedelta(minutes=30)
    co_evento = str(uuid.uuid4())
    evento = evento_de_partida(
        co_evento=co_evento, dia=dia, lote=str(uuid.uuid4()), inicio=inicio
    )
    # Do outro aparelho a partida nao e de convidado: sem lote.
    evento["payload"]["partida"]["co_lote_migracao"] = None
    r1 = await cliente.post("/v1/sincronizacao/eventos", json={"eventos": [evento]})
    r2 = await cliente.post(
        f"/v1/desafios/{dia['id_desafio']}/resolucao",
        json=envio_de_resolucao(
            dia=dia,
            co_evento_partida=co_evento,
            pontuacao=PONTUACAO_DA_CONTA,
            resolvido_em=inicio + timedelta(minutes=2),
            origem={"tipo": "conta"},
        ),
    )
    ok = r1.status_code == 200 and r2.status_code == 200 and not r2.json().get(
        "ja_existia"
    )
    relatorio.anotar(
        C_PRIMEIRA,
        ok,
        f"{dia['dt_dia']}: a conta resolveu em outro aparelho, com "
        f"{PONTUACAO_DA_CONTA} pontos, antes da migracao"
        if ok
        else f"⛔ a resolucao previa da conta falhou: {r1.status_code} / "
        f"{r2.status_code} {r2.text[:200]}",
    )


def main() -> int:
    """Ponto de entrada."""
    return asyncio.run(conferir())


if __name__ == "__main__":
    raise SystemExit(main())
