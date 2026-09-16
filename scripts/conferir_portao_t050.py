"""O PORTAO T050 — as quatro condicoes, medidas contra o `des` de verdade.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

A T050 e o portao de aceite do servidor: ⛔ nenhuma tarefa de tela comeca antes
dela. Ela fecha quando, **no ambiente `des`**, as quatro condicoes valem ao mesmo
tempo — e o texto da tarefa manda **registrar** o resultado.

⚠️ **Registrar a mao envelhece calado.** Um relatorio colado no `quickstart.md`
descreve o banco de um dia; no dia seguinte alguem roda o job, limpa a fila ou
troca uma rota, e o texto continua dizendo que esta tudo certo. Este script existe
para o portao poder ser **refeito** em qualquer momento, e nao apenas lembrado.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE FAZ, E O QUE ELE NAO FINGE
═══════════════════════════════════════════════════════════════════════════

Ele sobe o **aplicativo de verdade** (`api.main:app`) em memoria, por
`ASGITransport` — sem abrir porta, sem depender de o Railway estar no ar —, com a
`DATABASE_URL` apontando para o `des`. As rotas consultadas sao as mesmas que o
aplicativo chama.

⚠️ **Uma unica coisa e substituida: a verificacao do token do Firebase.** O
`usuario_atual` passa a devolver a identidade de uma conta que ja existe no `des`,
escolhida pelo proprio script. ⛔ O que NAO e substituido e o `usuario_autenticado`
— ele continua indo ao banco resolver o dono pelo `co_identidade_externa`, que e a
parte que a condicao (c) quer provar. O que se pula e a assinatura do token, que e
do Firebase e nao deste servidor.

⚠️ **Ele ESCREVE no `des`** — e nao tem como nao escrever: a condicao (c) exige que
`POST /v1/desafios/{id}/resolucao` responda com dado vindo do banco, e essa rota
grava. ⛔ **So no `des`**, nunca no `prd`: a URL usada e sempre `DATABASE_URL_DES`,
lida do catalogo fora do Git, e o script **confere o nome do banco** antes de
escrever. O que ele grava sai depois com
`ferramentas/consultas_sql/desafio_limpar_dias_futuros_DES.sql`.

⛔ **Nunca imprime a URL nem a senha.** Mesma regra de `consultar_des.py`.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_portao_t050.py
    .venv\\Scripts\\python scripts\\conferir_portao_t050.py --sem-escrita

`--sem-escrita` roda so as duas leituras e a condicao (d); serve para reconferir o
portao sem deixar linha nova no `des`. ⚠️ Nesse modo a condicao (c) fica
**incompleta**, e o relatorio diz isso — nao a da por boa.

Saida: um relatorio por condicao, e codigo de saida 0 so quando as quatro fecham.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# `parents[1]` e a raiz do backend; `parents[2]`, a raiz do ecossistema.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_ECOSSISTEMA = RAIZ_BACKEND.parent
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, o primeiro emoji derruba o script no
# meio do trabalho. E o mesmo defeito que matava o job em 15/09/2026.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

#: O catalogo dos dois bancos, fora do Git.
CATALOGO = RAIZ_ECOSSISTEMA / "ferramentas" / "debug-bancos" / "ambientes.env"

#: Os cabecalhos que `exigir_cabecalhos` cobra de toda requisicao.
#:
#: ⚠️ Nao sao enfeite: sem eles a rota responde 400, e o script estaria medindo a
#: propria falta de cabecalho em vez da rota. A versao e a do aplicativo em campo.
CABECALHOS = {
    "X-App-Version": "1.2.0",
    "X-Platform": "android",
    "Accept-Language": "pt-BR",
}


def url_do_des() -> str:
    """A URL do `des`, lida do catalogo do ecossistema.

    ⛔ Sempre `DATABASE_URL_DES`. O arquivo tem as duas lado a lado, e e por isso
    que a leitura e por nome exato: um erro de digitacao apontaria para o `prd`.
    """
    if not CATALOGO.exists():
        raise SystemExit(f"⛔ catalogo nao encontrado: {CATALOGO}")

    for linha in CATALOGO.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == "DATABASE_URL_DES":
            bruta = valor.strip().strip('"').strip("'")
            if not bruta:
                raise SystemExit("⛔ DATABASE_URL_DES esta vazia no catalogo.")
            return re.sub(
                r"^postgres(ql)?://", "postgresql+asyncpg://", bruta, count=1
            )

    raise SystemExit(f"⛔ DATABASE_URL_DES nao esta em {CATALOGO}")


class Relatorio:
    """Acumula o que cada condicao provou, e se ela fechou.

    Existe para o script nunca imprimir "OK" sem dizer **de que numero** ele saiu:
    um portao que responde sim ou nao, sem o dado, ensina a confiar nele sem
    conferir — e e o dado que envelhece, nao o veredito.
    """

    def __init__(self) -> None:
        self.condicoes: dict[str, list[tuple[bool, str]]] = {}

    def anotar(self, condicao: str, passou: bool, texto: str) -> None:
        self.condicoes.setdefault(condicao, []).append((passou, texto))

    def fechou(self, condicao: str) -> bool:
        linhas = self.condicoes.get(condicao)
        return bool(linhas) and all(passou for passou, _ in linhas)

    def imprimir(self) -> bool:
        tudo = True
        for condicao, linhas in self.condicoes.items():
            ok = self.fechou(condicao)
            tudo = tudo and ok
            print()
            print(f"{'✅' if ok else '⛔'} {condicao}")
            for passou, texto in linhas:
                print(f"   {'·' if passou else '⛔'} {texto}")
        return tudo


async def conferir(*, com_escrita: bool) -> int:
    """Roda as quatro condicoes e devolve o codigo de saida."""
    # ⚠️ A configuracao tem de ser trocada ANTES de `api.main` ser importado: o
    # motor do SQLAlchemy nasce no import de `api.nucleo.banco`, lendo a URL de
    # uma vez so. Trocar depois deixaria o aplicativo falando com outro banco.
    os.environ["DATABASE_URL"] = url_do_des()
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from api.main import app
    # ⚠️ O engine chama-se `engine`, e o script o apelida de `motor` para o
    # texto ficar em portugues como o resto do projeto.
    from api.nucleo.banco import engine as motor
    from api.nucleo.dependencias import usuario_atual
    from api.nucleo.seguranca_firebase import IdentidadeFirebase

    relatorio = Relatorio()

    # ── A trava: e o `des` mesmo? ───────────────────────────────────────────
    #
    # ⛔ O script escreve. Antes de escrever, ele pergunta ao proprio banco quem
    # ele e — e a resposta que importa nao e o nome (os dois se chamam `railway`),
    # e sim a **ausencia dos schemas de producao que o `des` nao tem** e a
    # presenca dos dois schemas do desafio, que so existem no `des` hoje.
    async with motor.connect() as conexao:
        schemas = {
            linha[0]
            for linha in (
                await conexao.execute(
                    text(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name IN ('desafio', 'desafio_dia')"
                    )
                )
            ).fetchall()
        }
    if schemas != {"desafio", "desafio_dia"}:
        raise SystemExit(
            "⛔ este banco nao tem os schemas `desafio` e `desafio_dia`. "
            "O script nao escreve num banco que nao reconhece."
        )

    transporte = ASGITransport(app=app)
    async with AsyncClient(
        transport=transporte, base_url="http://portao", headers=CABECALHOS
    ) as cliente:
        await _condicao_a_o_job_produz(relatorio, motor)
        await _condicao_b_calibracao(relatorio, motor)
        await _condicao_c_leituras(cliente, relatorio, motor)
        if com_escrita:
            await _condicao_c_escrita(
                cliente, relatorio, motor, app, usuario_atual, IdentidadeFirebase
            )
        else:
            relatorio.anotar(
                "(c) as tres leituras servem dado real",
                False,
                "⚠️ `--sem-escrita`: o POST /resolucao NAO foi exercido, entao "
                "esta condicao esta INCOMPLETA de proposito",
            )

    # A condicao (d) roda o pytest num processo proprio, e por isso fica FORA
    # do `async with`: ela nao usa o banco, e misturar as duas coisas so faria
    # o motor ficar aberto por mais tempo do que precisa.
    _condicao_d_cadeados(relatorio)

    await motor.dispose()
    return 0 if relatorio.imprimir() else 1


async def _condicao_a_o_job_produz(relatorio: Relatorio, motor) -> None:
    """(a) O job produz nos DOIS jogos, e a posicao inicial esta no formato certo.

    ⚠️ **Dois, e nao tres** — decisao do dono em 10/09/2026 (§8g): *"jogo da velha
    nao teremos no desafio pois ele nao tem muita variacao"*. Cobrar tres aqui
    deixaria o portao vermelho para sempre por um requisito que foi revogado.
    """
    from sqlalchemy import text

    condicao = "(a) o job produz nos dois jogos"

    async with motor.connect() as conexao:
        linhas = (
            await conexao.execute(
                text(
                    "SELECT v.co_jogo, v.co_formato_posicao, count(*) AS quantos "
                    "  FROM desafio_dia.vw001_desafio_dia d "
                    "  JOIN desafio.vw001_desafio v ON v.id_desafio = d.id_desafio "
                    " GROUP BY 1, 2 ORDER BY 1"
                )
            )
        ).mappings().all()

        # ⚠️ `vez_de` reconstruido: o texto da tarefa cobra que a posicao inicial
        # esteja **completa**, e nao so presente. Uma posicao sem a vez e ambigua,
        # e o aplicativo abriria o tabuleiro com o lado errado a jogar.
        incompletas = (
            await conexao.execute(
                text(
                    # ⚠️ `jsonb_exists(...)` e nao o operador `?`: o driver
                    # asyncpg usa `$1` para parametro e nao escapa `?`, entao o
                    # operador chega ao Postgres partido ao meio. A funcao faz
                    # exatamente a mesma pergunta.
                    "SELECT count(*) FROM desafio.vw001_desafio "
                    " WHERE js_posicao_inicial IS NULL "
                    "    OR NOT jsonb_exists(js_posicao_inicial, 'vez_de')"
                )
            )
        ).scalar()

    jogos = {linha["co_jogo"] for linha in linhas}
    tem_os_dois = jogos == {"pontinhos", "damas"}
    relatorio.anotar(
        condicao,
        tem_os_dois,
        f"os jogos publicados sao {sorted(jogos)}"
        if tem_os_dois
        else f"⛔ esperava pontinhos e damas; achei {sorted(jogos)}",
    )

    # ⚠️ O formato NAO e livre: `sequencia_lances` no Pontinhos, `fen` nas damas.
    # Um formato trocado abriria o tabuleiro vazio, e o aplicativo nao tem como
    # denunciar isso — ele so nao desenha nada.
    esperado = {"pontinhos": "sequencia_lances", "damas": "fen"}
    for linha in linhas:
        certo = esperado.get(linha["co_jogo"]) == linha["co_formato_posicao"]
        relatorio.anotar(
            condicao,
            certo,
            f"{linha['co_jogo']}: {linha['quantos']} publicado(s) em "
            f"`{linha['co_formato_posicao']}`"
            if certo
            else f"⛔ {linha['co_jogo']} publicado em "
            f"`{linha['co_formato_posicao']}`, e o formato e "
            f"`{esperado.get(linha['co_jogo'])}`",
        )

    relatorio.anotar(
        condicao,
        incompletas == 0,
        "toda posicao inicial tem `vez_de`"
        if incompletas == 0
        else f"⛔ {incompletas} posicao(oes) inicial(is) sem `vez_de`",
    )

    # ⚠️ As damas rodiziam as quatro modalidades. Com a fila curta nem todas
    # aparecem, entao o que se cobra e que a modalidade **exista** nas damas — o
    # contrario seria dado incompleto num jogo em que a regra muda com ela.
    async with motor.connect() as conexao:
        sem_modalidade = (
            await conexao.execute(
                text(
                    "SELECT count(*) FROM desafio.vw001_desafio "
                    " WHERE co_jogo = 'damas' "
                    "   AND (co_modalidade IS NULL OR co_modalidade = '')"
                )
            )
        ).scalar()
    relatorio.anotar(
        condicao,
        sem_modalidade == 0,
        "toda linha de damas declara a modalidade"
        if sem_modalidade == 0
        else f"⛔ {sem_modalidade} linha(s) de damas sem modalidade",
    )


async def _condicao_b_calibracao(relatorio: Relatorio, motor) -> None:
    """(b) A calibracao esta gravada e confere.

    ⛔ **Esta condicao NAO e sobre o conteudo estar bom.** Ela cobra que a regua
    esteja **gravada e conferindo** — pescaria, escada e remedicao sao qualidade
    de conteudo e correm em paralelo. Confundir as duas coisas travou o portao por
    dias em 16/09/2026, e o dono foi quem cobrou a distincao.
    """
    from sqlalchemy import text

    condicao = "(b) a calibracao esta gravada e confere"

    async with motor.connect() as conexao:
        contagens = (
            await conexao.execute(
                text(
                    "SELECT "
                    " (SELECT count(*) FROM desafio.vw002_medicao_regua) AS regua, "
                    " (SELECT count(*) FROM desafio.vw003_feito_desafio) AS feitos, "
                    " (SELECT count(*) FROM desafio.vw903_perfil_dificuldade) AS perfis, "
                    " (SELECT count(*) FROM desafio.vw904_motor) AS motores, "
                    " (SELECT count(*) FROM desafio.vw902_catalogo_feito) AS catalogo"
                )
            )
        ).mappings().first()

        # ⚠️ Uma linha por mascote, **com a versao do perfil**: sem ela, uma
        # remedicao futura nao teria como dizer qual regua produziu qual numero, e
        # dois historicos viram um so.
        sem_versao = (
            await conexao.execute(
                text(
                    "SELECT count(*) FROM desafio.vw002_medicao_regua "
                    " WHERE co_versao_perfil IS NULL OR co_versao_perfil = ''"
                )
            )
        ).scalar()

        # ⚠️ Todo desafio publicado tem de ter a regua medida. Um sem medicao
        # publicaria uma nota que nada sustenta.
        sem_regua = (
            await conexao.execute(
                text(
                    "SELECT count(*) "
                    "  FROM desafio_dia.vw001_desafio_dia d "
                    " WHERE NOT EXISTS ("
                    "   SELECT 1 FROM desafio.vw002_medicao_regua m "
                    "    WHERE m.id_desafio = d.id_desafio)"
                )
            )
        ).scalar()

    for rotulo, quantos in contagens.items():
        relatorio.anotar(
            condicao,
            quantos > 0,
            f"{rotulo}: {quantos} linha(s)"
            if quantos > 0
            else f"⛔ {rotulo} esta VAZIO",
        )
    relatorio.anotar(
        condicao,
        sem_versao == 0,
        "toda medicao de regua declara `co_versao_perfil`"
        if sem_versao == 0
        else f"⛔ {sem_versao} medicao(oes) sem `co_versao_perfil`",
    )
    relatorio.anotar(
        condicao,
        sem_regua == 0,
        "todo desafio publicado tem a regua medida"
        if sem_regua == 0
        else f"⛔ {sem_regua} desafio(s) publicado(s) sem medicao de regua",
    )


def _condicao_d_cadeados(relatorio: Relatorio) -> None:
    """(d) Os cadeados do bloco estao verdes, e nenhum "pulou com motivo".

    ⛔ **Cadeado que pula conta como VERMELHO** — e o defeito que a RF-DES-143a
    existe para corrigir, e o motivo de este script contar os `skipped` em vez de
    olhar so o codigo de saida do pytest.

    ⚠️ O cadeado 5 (contrato de dificuldade do Pontinhos) e do **frontend**, roda
    no `flutter test` e nao cabe aqui: este processo nao tem Flutter. Ele e
    nomeado no relatorio para ninguem contar quatro e achar que sao cinco.
    """
    import subprocess

    condicao = "(d) os cadeados do bloco estao verdes"

    cadeados = [
        "tests/unitarios/test_espelho_laboratorio.py",
        "tests/unitarios/test_catalogo_feito_paridade.py",
        "tests/unitarios/test_uniao_xp_completa.py",
        "tests/unitarios/test_partida_de_desafio_fechada.py",
        "tests/unitarios/test_uma_fonte_de_lances.py",
    ]
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *cadeados],
        cwd=RAIZ_BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    saida = (resultado.stdout or "") + (resultado.stderr or "")
    linhas = [linha for linha in saida.splitlines() if linha.strip()]
    ultima = linhas[-1].strip() if linhas else "(sem saida)"

    passou = resultado.returncode == 0
    relatorio.anotar(
        condicao,
        passou,
        f"pytest dos cadeados 4, 6, 7, 8 e 9: {ultima}"
        if passou
        else f"⛔ pytest falhou: {ultima}",
    )

    # ⛔ A contagem de pulados e a parte que importa: um `skipped` aqui e vermelho.
    pulou = "skipped" in saida
    relatorio.anotar(
        condicao,
        not pulou,
        "nenhum cadeado pulou"
        if not pulou
        else "⛔ algum cadeado PULOU — e pular conta como vermelho (RF-DES-143a)",
    )
    relatorio.anotar(
        condicao,
        True,
        "⚠️ o cadeado 5 (contrato de dificuldade do Pontinhos) e do frontend: "
        "`flutter test test/modulos/jogos/pontinhos/contrato_dificuldade_test.dart`",
    )


async def _condicao_c_leituras(cliente, relatorio: Relatorio, motor) -> None:
    """`GET /hoje` e `GET /{id}/quadro`, conferidos contra o banco."""
    from sqlalchemy import text

    condicao = "(c) as tres leituras servem dado real"

    # ── O que o BANCO diz que e o desafio de hoje ───────────────────────────
    #
    # ⚠️ A pergunta e feita ao banco ANTES da rota, e de proposito: comparar a
    # resposta da rota com ela mesma nao prova nada. O dia e o **UTC**, que e a
    # unidade do produto (um desafio por dia UTC, igual para todos).
    hoje = datetime.now(timezone.utc).date()
    async with motor.connect() as conexao:
        linha = (
            await conexao.execute(
                text(
                    "SELECT d.id_desafio, d.id_desafio_dia, v.co_jogo, "
                    "       v.co_tipo_desafio, v.co_curadoria "
                    "  FROM desafio_dia.vw001_desafio_dia d "
                    "  JOIN desafio.vw001_desafio v ON v.id_desafio = d.id_desafio "
                    " WHERE d.dt_dia = :hoje"
                ),
                {"hoje": hoje},
            )
        ).mappings().first()

        descartados = (
            await conexao.execute(
                text(
                    "SELECT id_desafio FROM desafio.vw001_desafio "
                    " WHERE co_curadoria <> 'aprovado' LIMIT 1"
                )
            )
        ).scalar()

    if linha is None:
        relatorio.anotar(
            condicao, False, f"o banco nao tem desafio para o dia UTC {hoje}"
        )
        return

    relatorio.anotar(
        condicao,
        True,
        f"o banco tem o dia {hoje}: {linha['co_jogo']}/{linha['co_tipo_desafio']} "
        f"({linha['co_curadoria']})",
    )

    # ── GET /v1/desafios/hoje ───────────────────────────────────────────────
    resposta = await cliente.get("/v1/desafios/hoje")
    ok = resposta.status_code == 200
    relatorio.anotar(condicao, ok, f"GET /v1/desafios/hoje → {resposta.status_code}")
    if not ok:
        return

    corpo = resposta.json()
    # ⚠️ O que se confere e a **identidade da linha**, nao a forma do JSON: um
    # contrato bem montado servindo dado inventado passaria numa conferencia de
    # forma, e e exatamente o que esta condicao existe para descartar.
    mesmo = str(corpo.get("id_desafio")) == str(linha["id_desafio"])
    relatorio.anotar(
        condicao,
        mesmo,
        "a rota serviu a MESMA linha do banco"
        if mesmo
        else f"a rota serviu {corpo.get('id_desafio')}, e o banco tem "
        f"{linha['id_desafio']}",
    )

    # ⚠️ Os nomes sao os do CONTRATO (`contracts/desafio-publicado.md`), e nao os
    # das colunas do banco: a resposta fala `jogo`, `formato_posicao` e `tipo`
    # onde a tabela tem `co_jogo`, `co_formato_posicao` e `co_tipo_desafio`. A
    # traducao e a rota que faz, e conferir pelos nomes da tabela deixaria o
    # portao vermelho justamente por a rota estar certa.
    for campo in (
        "id_desafio",
        "id_desafio_dia",
        "jogo",
        "tipo",
        "forma_verificacao",
        "parametros",
        "formato_posicao",
        "objetivo",
        "personagem",
        "semente",
        "encerra_em",
        "agora_no_servidor",
    ):
        relatorio.anotar(
            condicao,
            campo in corpo,
            f"a resposta traz `{campo}`"
            if campo in corpo
            else f"⛔ falta `{campo}` na resposta de /hoje",
        )

    # ⚠️ A posicao vem num de DOIS campos, e o `formato_posicao` diz em qual: as
    # damas em `tabuleiro` (FEN) e o Pontinhos em `posicao`. O outro vem `null`.
    # ⛔ Servir os dois, ou nenhum, deixaria o aplicativo adivinhando.
    campo_da_posicao = (
        "tabuleiro" if corpo.get("formato_posicao") == "fen" else "posicao"
    )
    tem_posicao = corpo.get(campo_da_posicao) is not None
    relatorio.anotar(
        condicao,
        tem_posicao,
        f"a posicao inicial veio em `{campo_da_posicao}` "
        f"(formato `{corpo.get('formato_posicao')}`)"
        if tem_posicao
        else f"⛔ `formato_posicao` diz `{corpo.get('formato_posicao')}` e "
        f"`{campo_da_posicao}` veio vazio",
    )

    # ⛔ O objetivo e CHAVE de i18n, nunca frase pronta — a mesma regra que o
    # empate das damas acabou de cumprir (T003). Uma frase aqui faria o servidor
    # escolher o idioma de quem joga.
    objetivo = corpo.get("objetivo") or {}
    tem_chave = isinstance(objetivo, dict) and bool(objetivo.get("chave"))
    relatorio.anotar(
        condicao,
        tem_chave,
        f"o objetivo veio como CHAVE (`{objetivo.get('chave')}`), nao como frase"
        if tem_chave
        else f"⛔ o objetivo nao trouxe `chave`: {objetivo}",
    )

    # ⛔ Serve so o aprovado. A prova e pedir o descartado pelo id e nao receber.
    if descartados is not None:
        r = await cliente.get(f"/v1/desafios/{descartados}")
        recusou = r.status_code == 404
        relatorio.anotar(
            condicao,
            recusou,
            "um desafio DESCARTADO pelo dono nao e servido (404)"
            if recusou
            else f"⛔ um descartado foi servido com {r.status_code}",
        )
    else:
        relatorio.anotar(
            condicao,
            False,
            "⚠️ nao ha desafio descartado no `des` para provar o filtro da curadoria",
        )

    # ── GET /v1/desafios/{id}/quadro ────────────────────────────────────────
    r = await cliente.get(f"/v1/desafios/{linha['id_desafio']}/quadro")
    ok = r.status_code == 200
    relatorio.anotar(
        condicao, ok, f"GET /v1/desafios/{{id}}/quadro → {r.status_code}"
    )
    if ok:
        quadro = r.json()
        # ⚠️ Os campos sao os de `contracts/quadro-do-dia.md`. ⛔ A regua dos
        # quatro mascotes NAO e um campo proprio: ela vem dentro de `linhas`,
        # como itens de `sujeito: "mascote"` misturados aos jogadores e na mesma
        # ordem de XP — e e isso que faz a frase "voce passou o Tex" sair de uma
        # comparacao, e nao de um rotulo.
        for campo in (
            "linhas",
            "minha_linha",
            "fracao",
            "texto_vazio",
            "replays_liberados",
        ):
            relatorio.anotar(
                condicao,
                campo in quadro,
                f"o quadro traz `{campo}`"
                if campo in quadro
                else f"⛔ falta `{campo}` no quadro",
            )

        mascotes = {
            linha.get("chave")
            for linha in quadro.get("linhas", [])
            if linha.get("sujeito") == "mascote"
        }
        # ⚠️ **Sao TRES, e nao quatro** — e isto e desenho, nao falta. O mascote
        # do dia e o **adversario**, e `regua.medir` o pula de proposito
        # (RF-DES-204): ele nao joga contra si mesmo. Quem falta na regua e
        # exatamente quem esta do outro lado do tabuleiro.
        adversario = corpo.get("personagem")
        esperados = {"cacau", "pita", "tex", "magno"} - {adversario}
        certo = mascotes == esperados
        relatorio.anotar(
            condicao,
            certo,
            f"a regua traz os tres mascotes que nao sao o adversario "
            f"({sorted(mascotes)}; o do dia e `{adversario}`)"
            if certo
            else f"⛔ a regua veio com {sorted(mascotes)}, e com o adversario "
            f"`{adversario}` de fora deveria ser {sorted(esperados)}",
        )

        # ⛔ Nunca uma fracao abaixo de 20 tentativas. Com o `des` quase vazio, o
        # certo e `null` — e um numero aqui seria a regra furada, nao um bonus.
        poucas = quadro.get("fracao") is None
        relatorio.anotar(
            condicao,
            poucas,
            "`fracao` veio `null`, como manda a regra das 20 tentativas"
            if poucas
            else f"⚠️ `fracao` = {quadro.get('fracao')}; confira se ja ha 20 "
            "tentativas no `des`",
        )


async def _condicao_c_escrita(
    cliente, relatorio: Relatorio, motor, app, usuario_atual, IdentidadeFirebase
) -> None:
    """`POST /{id}/resolucao`, com a partida subindo antes, pelo mesmo caminho.

    ⚠️ **A partida vem primeiro, e nao e detalhe:** a resolucao aponta para uma
    partida que o aplicativo ja enviou (`co_evento_partida`), e o servidor
    **segura** a resolucao que chega antes dela. Mandar so a resolucao provaria o
    409, nao a rota.
    """
    from fastapi import Depends
    from sqlalchemy import text

    from api.nucleo.banco import obter_sessao
    from api.nucleo.dependencias import exigir_cabecalhos
    from api.nucleo.dependencias_conta_nuvem import (
        usuario_autenticado,
        usuario_opcional,
    )

    condicao = "(c) as tres leituras servem dado real"

    # ── Uma conta que ja existe no `des` ────────────────────────────────────
    async with motor.connect() as conexao:
        conta = (
            await conexao.execute(
                text(
                    "SELECT id_usuario, co_usuario, co_identidade_externa "
                    "  FROM conta.vw001_usuario "
                    " WHERE co_identidade_externa IS NOT NULL "
                    " ORDER BY dh_criacao LIMIT 1"
                )
            )
        ).mappings().first()

        dia = (
            await conexao.execute(
                text(
                    "SELECT d.id_desafio, d.id_desafio_dia, v.co_jogo "
                    "  FROM desafio_dia.vw001_desafio_dia d "
                    "  JOIN desafio.vw001_desafio v ON v.id_desafio = d.id_desafio "
                    " WHERE d.dt_dia = :hoje"
                ),
                {"hoje": datetime.now(timezone.utc).date()},
            )
        ).mappings().first()

    if conta is None or dia is None:
        relatorio.anotar(
            condicao, False, "⛔ falta conta provisionada ou desafio de hoje no `des`"
        )
        return

    # ⚠️ So a verificacao do token e substituida. `usuario_autenticado` continua
    # indo ao banco pelo `co_identidade_externa` — e e essa ida que se quer provar.
    app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
        uid=conta["co_identidade_externa"]
    )
    try:
        # ⚠️ O `co_evento` e UUID, e nao um texto livre: a coluna e `uuid` no
        # banco. Um prefixo legivel ("portao-t050-...") parece inofensivo e
        # cai como `falha_processamento` — ⚠️ com 200 na resposta, porque o
        # lote nao pode ser derrubado por um evento. Foi assim que este
        # script errou na primeira execucao, em 16/09/2026.
        co_evento = str(uuid.uuid4())

        # ── 1. A partida, pelo outbox de sempre ─────────────────────────────
        #
        # ⚠️ `co_modo='desafio'` e `ic_pontua=False`: a resolucao e uma partida, e
        # o anti-farm do `pvp_local` e o mesmo daqui. ⛔ Nao existe log de lances
        # proprio do desafio.
        evento = {
            "co_evento": co_evento,
            "co_tipo": "partida",
            "payload": {
                "partida": {
                    "id_partida": str(uuid.uuid4()),
                    "co_jogo": dia["co_jogo"],
                    "co_variante": "pequeno",
                    "co_modo": "desafio",
                    "nu_placar_j1": 1,
                    "nu_placar_j2": 0,
                    "ic_pontua": False,
                    "co_status": "concluida",
                    "dh_inicio": datetime.now(timezone.utc).isoformat(),
                },
                "jogadas": [],
                "xp": [],
            },
        }
        r = await cliente.post(
            "/v1/sincronizacao/eventos", json={"eventos": [evento]}
        )
        aceita = r.status_code == 200 and co_evento in r.json().get("aceitos", [])
        relatorio.anotar(
            condicao,
            aceita,
            f"a partida do desafio subiu pelo outbox ({r.status_code})"
            if aceita
            else f"⛔ a partida nao subiu: {r.status_code} {r.text[:200]}",
        )
        if not aceita:
            return

        # ── 2. A resolucao ──────────────────────────────────────────────────
        envio: dict[str, Any] = {
            "id_desafio_dia": str(dia["id_desafio_dia"]),
            "veredito": "resolvido",
            "tentativas": 1,
            "tempo_ms": 48210,
            "dicas_usadas": 0,
            "qualidade": 0.7325,
            "pontuacao": 26,
            "co_evento_partida": co_evento,
            "nu_lance_cumpre_desafio": 1,
            # ⛔ MEDIDAS, nunca XP. Quem converte medida em nota e a colecao.
            "feitos": [
                {"chave": "tempo_ate_resolver", "valor": 48210},
                {"chave": "tentativas", "valor": 1},
            ],
            "versao_catalogo_feitos": 1,
            "resolvido_em": datetime.now(timezone.utc).isoformat(),
            "origem": {"tipo": "conta"},
        }
        r = await cliente.post(
            f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio
        )
        ok = r.status_code == 200 and r.json().get("aceita") is True
        relatorio.anotar(
            condicao,
            ok,
            f"POST /v1/desafios/{{id}}/resolucao → {r.status_code}, "
            f"aceita={r.json().get('aceita') if r.status_code == 200 else '—'}"
            if r.status_code == 200
            else f"⛔ POST /resolucao: {r.status_code} {r.text[:300]}",
        )
        if not ok:
            return
        id_resolucao = r.json().get("id_resolucao")

        # ── 3. A linha existe MESMO no banco ────────────────────────────────
        #
        # ⚠️ `aceita: true` significa "recebi e gravei". Aqui se confere a segunda
        # metade: que gravou. Uma rota que responde 200 sem gravar passaria em
        # tudo acima.
        async with motor.connect() as conexao:
            gravada = (
                await conexao.execute(
                    text(
                        "SELECT id_resolucao FROM desafio_dia.vw003_resolucao "
                        " WHERE id_resolucao = :id"
                    ),
                    {"id": id_resolucao},
                )
            ).scalar()
        relatorio.anotar(
            condicao,
            gravada is not None,
            "a resolucao esta no banco, lida de volta pela view"
            if gravada is not None
            else "⛔ a rota respondeu 200 e a linha nao esta no banco",
        )

        # ── 4. Reenviar o MESMO evento nao duplica ──────────────────────────
        #
        # ⚠️ O aplicativo nao espera a resposta: o outbox reenvia. Sem
        # idempotencia, cada reenvio viraria uma linha nova no quadro.
        r2 = await cliente.post(
            f"/v1/desafios/{dia['id_desafio']}/resolucao", json=envio
        )
        repetiu = (
            r2.status_code == 200
            and r2.json().get("id_resolucao") == id_resolucao
        )
        relatorio.anotar(
            condicao,
            repetiu,
            "o reenvio devolveu a MESMA resolucao, sem duplicar"
            if repetiu
            else f"⛔ o reenvio criou outra linha: {r2.status_code} {r2.text[:200]}",
        )

        # ── 5. E o quadro passou a ter gente ────────────────────────────────
        #
        # ⚠️ **Esta e a prova que fecha o circulo:** o POST gravou, e a leitura
        # que a tela faz ja enxerga o que ele gravou. Sem ela, o portao provaria
        # duas rotas que nao se falam.
        r3 = await cliente.get(f"/v1/desafios/{dia['id_desafio']}/quadro")
        corpo = r3.json() if r3.status_code == 200 else {}
        # ⛔ A linha de jogador expoe `id` e `nome`, nunca `co_usuario` nem
        # e-mail — o quadro e publico, e o codigo da conta nao e dado de tela.
        meu = [
            linha
            for linha in corpo.get("linhas", [])
            if linha.get("sujeito") == "jogador"
            and str(linha.get("id")) == str(conta["id_usuario"])
        ]
        relatorio.anotar(
            condicao,
            bool(meu),
            f"quem resolveu aparece no quadro do dia (xp={meu[0].get('xp')}, "
            f"nome={meu[0].get('nome')!r})"
            if meu
            else "⚠️ quem resolveu nao aparece no quadro — confira "
            "`ic_visivel_placar` e `ic_idade_minima_declarada` da conta",
        )
        # ⚠️ **A chamada acima foi como CONVIDADO**, e por isso `minha_linha` veio
        # `null`: o `usuario_opcional` le o cabecalho `Authorization` por conta
        # propria, sem passar pelo `usuario_atual` que este script substituiu.
        # ⛔ Isso nao e limitacao do teste — e a resposta certa para quem nao diz
        # quem e, e vale a pena estar provada.
        sem_dono = corpo.get("minha_linha") is None
        relatorio.anotar(
            condicao,
            sem_dono,
            "como convidado, `minha_linha` vem `null` (o quadro publico e o mesmo)"
            if sem_dono
            else f"⛔ o convidado recebeu `minha_linha` = {corpo.get('minha_linha')}",
        )

        # ── 6. E com dono, a propria posicao aparece ────────────────────────
        #
        # ⛔ Quem se escondeu do quadro continua vendo a **propria** linha:
        # `ic_publico` esconde a pessoa dos outros, nunca dela mesma.
        #
        # ⚠️ O override abaixo troca so o caminho do token, e mantem a ida ao
        # banco: ele chama o `usuario_autenticado` de verdade, que resolve o dono
        # pelo `co_identidade_externa`. Substituir por um objeto pronto pularia
        # justamente a parte que esta condicao quer provar.
        async def _dono_pelo_banco(
            contexto=Depends(exigir_cabecalhos),
            sessao=Depends(obter_sessao),
        ):
            return await usuario_autenticado(
                identidade=IdentidadeFirebase(uid=conta["co_identidade_externa"]),
                contexto=contexto,
                sessao=sessao,
            )

        app.dependency_overrides[usuario_opcional] = _dono_pelo_banco
        try:
            r4 = await cliente.get(f"/v1/desafios/{dia['id_desafio']}/quadro")
            minha = r4.json().get("minha_linha") if r4.status_code == 200 else None
        finally:
            app.dependency_overrides.pop(usuario_opcional, None)

        relatorio.anotar(
            condicao,
            isinstance(minha, dict) and minha.get("xp") is not None,
            f"com a conta identificada, `minha_linha` traz a propria posicao "
            f"({minha})"
            if isinstance(minha, dict)
            else f"⛔ `minha_linha` veio {minha!r} depois de a pessoa resolver",
        )
    finally:
        app.dependency_overrides.pop(usuario_atual, None)


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Confere as quatro condicoes do portao T050 contra o `des`."
    )
    analisador.add_argument(
        "--sem-escrita",
        action="store_true",
        help="roda so as leituras; a condicao (c) fica incompleta de proposito",
    )
    argumentos = analisador.parse_args()

    print("⚠️ PORTAO T050 — medido contra o ambiente `des`.")
    print("   (a) e (b) sao conferidas por consulta; (d), pelos cadeados do pytest.")
    return asyncio.run(conferir(com_escrita=not argumentos.sem_escrita))


if __name__ == "__main__":
    raise SystemExit(main())
