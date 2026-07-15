"""Semeia jogadores fictícios no ranking do ambiente **des**.

Para que serve
--------------
O placar de líderes precisa aparecer **cheio** nas capturas de tela das lojas e do
site: pódio com os três primeiros e uma lista descendo do 4º em diante. Num banco
de desenvolvimento com duas contas de teste, o pódio fica vazio e a tela não mostra
o que ela realmente é.

Regras que este script se impõe
-------------------------------
1. **Só toca no `des`.** Lê `DATABASE_URL_DES` de `debug-bancos/ambientes.env` e,
   antes de escrever, confere que o DSN **não é** o do `prd`. Semear o produção
   sujaria o ranking real e os logs de treino da IA.
2. **Tudo o que ele cria, ele sabe apagar.** Cada conta fictícia nasce com
   `co_identidade_externa = 'semente:<n>'` — é a marca que permite o `--limpar`
   remover exatamente o que foi semeado, e nada mais.
3. **Sem PII.** As contas não têm e-mail. São apelidos e XP, nada mais.

Uso
---
    .venv\\Scripts\\python ferramentas/semear_ranking_des.py            # semeia
    .venv\\Scripts\\python ferramentas/semear_ranking_des.py --limpar   # desfaz
    .venv\\Scripts\\python ferramentas/semear_ranking_des.py --minha-posicao 8

O `--minha-posicao` decide onde a **sua** conta fica no placar: o script conta
quantos jogadores precisam ficar acima de você e distribui o XP em volta do seu.
É o que faz a barra "VOCÊ" mostrar um número plausível (`#14`) em vez de `#1`.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import re
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
AMBIENTES_ENV = RAIZ_BACKEND.parent / "debug-bancos" / "ambientes.env"

# O console do Windows abre em cp1252, que não sabe escrever emoji nem "→": sem
# isto, o script morre com UnicodeEncodeError ANTES de fazer qualquer coisa útil.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001 — terminal exótico: seguimos sem reconfigurar
    pass

# Marca das contas semeadas. É a chave do `--limpar`: sem ela, apagar significaria
# adivinhar quais linhas são nossas, e adivinhar num banco não é uma opção.
PREFIXO_SEMENTE = "semente:"

# Apelidos plausíveis, no espírito do jogo. Nenhum é nome de pessoa real.
#
# São DUAS listas porque os nomes do topo não são iguais aos do fim: os três
# primeiros vão para o **pódio**, em letra grande, e são o que mais se lê na
# captura da loja. Ali entram nomes do JOGO. As piadas de rede neural ficam para
# o meio da lista, onde soam como jogadores de verdade e não como enfeite.
APELIDOS_DESTAQUE = [
    "LordeTraco", "Minimaxer", "MenteAfiada", "MestreDosPontos", "ReiDaArena",
    "DamaDeFerro", "OlhoDeLince", "Estrategista", "FioDeNavalha", "CacaCaixas",
    "ZugzwangZe", "CaixaFechada99", "UltimaLinha", "ContraAtaque", "Gambito",
]
APELIDOS = [
    "PontoFinal", "RedeNeural", "GatoDeSchrodinger", "Cadeia_Longa",
    "TicTacToeVet", "BoxMaster", "DotDotDot", "Sacrificio", "ParidadePura",
    "CorrenteDupla", "ArenaWolf", "PixelPaladin", "Cacau_Fan", "PitaPro",
    "MagnoRival", "TracoLimpo", "NoveDeOuros", "CaixaPreta", "SegundoTempo",
    "PontoCego", "Tabuleiro7", "VirouOJogo", "Fechador", "SacaCaixa",
    "AlfaBeta", "PodaProfunda", "HeuristicaX", "SoftmaxSam", "TensorTina",
    "GradienteG", "EpochEva", "BatchBoss", "DropoutDan", "ReluRui",
    "AdamOtimista", "PerdaZero", "AcuraciaAna", "ValidacaoVal", "OverfitOtto",
    "SementeFixa", "LoteQuente", "CamadaOculta", "PesoLeve", "ViesBaixo",
    "ConvKid", "PoolingPaulo", "FlattenFlavia", "DenseDenis", "SigmoidSil",
]

# Semente fixa do sorteio: rodar o script duas vezes tem de dar o MESMO placar.
# Sem isto, refazer as capturas depois de um ajuste de layout traria outros nomes
# e outros XPs, e as imagens já aprovadas deixariam de casar com as novas.
SEMENTE_PADRAO = 20260714


# ─────────────────────────────────────────────────────────────────────────────
# Conexão — e a trava que impede escrever no lugar errado
# ─────────────────────────────────────────────────────────────────────────────
def ler_ambientes() -> dict[str, str]:
    """Lê `debug-bancos/ambientes.env` (fora dos repositórios, com as duas URLs)."""
    if not AMBIENTES_ENV.is_file():
        sys.exit(
            f"Não achei {AMBIENTES_ENV}.\n"
            "Copie `ambientes.env.exemplo` para `ambientes.env` e preencha as duas URLs."
        )
    valores: dict[str, str] = {}
    for linha in AMBIENTES_ENV.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip()
    return valores


def normalizar_dsn(dsn: str) -> str:
    """asyncpg conecta em `postgresql://…` (sem o sufixo de driver do SQLAlchemy)."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgres://"
    )


def host_do(dsn: str) -> str:
    """Só `host:porta` — para imprimir sem vazar a senha."""
    m = re.search(r"@([^/]+)", dsn)
    return m.group(1) if m else "?"


def dsn_do_des() -> str:
    """O DSN do `des`, **provado** que não é o do `prd`.

    A trava é literal: se as duas URLs coincidirem (por um copiar-e-colar errado no
    `ambientes.env`), o script para. Um seed no produção entraria no ranking real e
    nos logs de treino da IA junto com os dados de usuários de verdade — e não há
    desfazer bonito para isso.
    """
    amb = ler_ambientes()
    des = normalizar_dsn(amb.get("DATABASE_URL_DES", ""))
    prd = normalizar_dsn(amb.get("DATABASE_URL_PRD", ""))
    if not des:
        sys.exit("`DATABASE_URL_DES` está vazio em ambientes.env.")
    if prd and host_do(des) == host_do(prd):
        sys.exit(
            "ABORTADO: o host do `des` é o MESMO do `prd` em ambientes.env.\n"
            f"  des → {host_do(des)}\n  prd → {host_do(prd)}\n"
            "Corrija o arquivo antes de semear."
        )
    return des


async def conectar(dsn: str):
    import asyncpg  # dependência do venv do backend

    return await asyncpg.connect(dsn, timeout=20)


# ─────────────────────────────────────────────────────────────────────────────
# Semear / limpar
# ─────────────────────────────────────────────────────────────────────────────
async def limpar(conn) -> int:
    """Apaga **só** as contas semeadas (as marcadas com `semente:`)."""
    # A progressão tem FK para o usuário → sai primeiro.
    await conn.execute(
        """
        DELETE FROM progressao.tb001_progressao_usuario
         WHERE id_usuario IN (
               SELECT id_usuario FROM conta.tb001_usuario
                WHERE co_identidade_externa LIKE $1
         )
        """,
        PREFIXO_SEMENTE + "%",
    )
    r = await conn.execute(
        "DELETE FROM conta.tb001_usuario WHERE co_identidade_externa LIKE $1",
        PREFIXO_SEMENTE + "%",
    )
    # asyncpg devolve "DELETE <n>".
    return int(r.split()[-1])


async def meu_xp(conn) -> tuple[str | None, int]:
    """XP da conta REAL de maior pontuação (a sua, no `des`).

    "Real" = qualquer conta que não seja semente. É em torno dela que o XP dos
    fictícios é distribuído, para a barra "VOCÊ" mostrar uma posição plausível.
    """
    linha = await conn.fetchrow(
        """
        SELECT u.no_exibicao, g.nu_xp_total
          FROM progressao.tb001_progressao_usuario g
          JOIN conta.tb001_usuario u ON u.id_usuario = g.id_usuario
         WHERE COALESCE(u.co_identidade_externa, '') NOT LIKE $1
           AND u.ic_anonimizado = FALSE
         ORDER BY g.nu_xp_total DESC
         LIMIT 1
        """,
        PREFIXO_SEMENTE + "%",
    )
    if linha is None:
        return None, 0
    return linha["no_exibicao"], int(linha["nu_xp_total"])


def gerar_xps(quantos: int, xp_alvo: int, acima: int) -> list[int]:
    """XPs fictícios: `acima` valores acima do seu, o resto abaixo.

    Todos **distintos** de propósito: o ranking usa `DENSE_RANK()`, e XP repetido
    faria dois jogadores dividirem a mesma posição — o que existe de verdade, mas
    numa captura de tela só parece defeito.
    """
    usados = {xp_alvo}
    xps: list[int] = []

    def novo(minimo: int, maximo: int) -> int:
        for _ in range(200):
            v = random.randint(minimo, maximo)
            if v not in usados:
                usados.add(v)
                return v
        # Espaço apertado: anda para cima até achar um livre.
        v = maximo
        while v in usados:
            v += 1
        usados.add(v)
        return v

    # Acima de você: sobe até ~4× o seu XP (topo do pódio bem destacado).
    teto = max(xp_alvo * 4, xp_alvo + 40_000, 50_000)
    for i in range(acima):
        # Distribui em faixas para o pódio ter uma diferença visível do 4º em diante.
        piso = xp_alvo + 1 + int((teto - xp_alvo) * (acima - 1 - i) / max(acima, 1) * 0.85)
        xps.append(novo(piso, max(piso + 1, teto)))

    # Abaixo de você: cai até quase zero, mas sempre > 0 (a VIEW só lista XP > 0).
    abaixo = quantos - acima
    for i in range(abaixo):
        teto_i = max(1, int(xp_alvo * (1 - (i + 1) / (abaixo + 1))))
        xps.append(novo(1, max(1, teto_i)))

    return sorted(xps, reverse=True)


async def semear(conn, quantos: int, minha_posicao: int) -> None:
    nome_real, xp_real = await meu_xp(conn)

    if nome_real is None or xp_real == 0:
        print(
            "⚠️  Nenhuma conta real com XP no `des`. Vou semear mesmo assim, mas a\n"
            "    barra 'VOCÊ' não vai aparecer na captura — jogue uma partida logada\n"
            "    no app `des` e rode de novo para se posicionar no meio do placar."
        )
        xp_alvo = 5_000
        acima = quantos  # todos acima de um alvo fictício
    else:
        xp_alvo = xp_real
        # Para você ficar na posição N, precisam existir N-1 pessoas acima.
        acima = max(0, min(minha_posicao - 1, quantos))
        print(f"👤  Sua conta no des: {nome_real!r} com {xp_real} XP")

    total_apelidos = len(APELIDOS_DESTAQUE) + len(APELIDOS)
    if quantos > total_apelidos:
        sys.exit(f"Só tenho {total_apelidos} apelidos; peça no máximo isso.")

    # Os XPs saem ORDENADOS (maior primeiro), e os apelidos são pareados na mesma
    # ordem — então os primeiros nomes da lista são os que sobem ao pódio. Daí os
    # de destaque virem antes.
    xps = gerar_xps(quantos, xp_alvo, acima)
    destaques = random.sample(APELIDOS_DESTAQUE, min(quantos, len(APELIDOS_DESTAQUE)))
    resto = random.sample(APELIDOS, quantos - len(destaques))
    apelidos = destaques + resto

    for i, (apelido, xp) in enumerate(zip(apelidos, xps), start=1):
        partidas = max(1, xp // 220 + random.randint(0, 8))
        vitorias = int(partidas * random.uniform(0.35, 0.75))
        empates = random.randint(0, max(0, partidas - vitorias) // 4)
        derrotas = partidas - vitorias - empates

        id_usuario = await conn.fetchval(
            """
            INSERT INTO conta.tb001_usuario
                   (co_usuario, co_identidade_externa, no_exibicao, dt_nascimento,
                    co_provedor_principal, co_idioma_preferido)
            VALUES ($1, $2, $3, $4, 'email', $5)
            RETURNING id_usuario
            """,
            codigo_usuario(i),
            f"{PREFIXO_SEMENTE}{i}",
            apelido,
            # Maior de 13 — senão a VIEW o esconde do placar (`ic_publico`).
            _nascimento_adulto(),
            random.choice(["pt", "en", "es"]),
        )
        await conn.execute(
            """
            INSERT INTO progressao.tb001_progressao_usuario
                   (id_usuario, nu_xp_total, nu_partidas, nu_vitorias,
                    nu_derrotas, nu_empates, nu_sequencia_atual, ic_visivel_placar)
            VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
            """,
            id_usuario, xp, partidas, vitorias, derrotas, empates,
            random.randint(0, 9),
        )

    print(f"🌱  {quantos} jogadores semeados (XP de {xps[0]} a {xps[-1]}).")
    if nome_real:
        print(f"📍  Sua posição no placar deve ficar em ~#{acima + 1}.")


def codigo_usuario(i: int) -> str:
    """`co_usuario` de 8 caracteres, no formato que o app exibe. `SEM` no começo
    torna a conta reconhecível a olho nu numa consulta ao banco."""
    return f"SEM{i:05d}"


def _nascimento_adulto():
    import datetime as dt

    hoje = dt.date.today()
    anos = random.randint(18, 45)
    return dt.date(hoje.year - anos, random.randint(1, 12), random.randint(1, 28))


async def principal() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limpar", action="store_true",
                   help="remove as contas semeadas e sai")
    p.add_argument("--quantos", type=int, default=60,
                   help="quantos jogadores fictícios criar (padrão: 60)")
    p.add_argument("--minha-posicao", type=int, default=14,
                   help="em que posição do placar a SUA conta deve cair (padrão: 14)")
    p.add_argument("--semente", type=int, default=SEMENTE_PADRAO,
                   help="semente do sorteio; fixa por padrão, para o placar ser "
                        "SEMPRE o mesmo (as capturas precisam ser refazíveis)")
    args = p.parse_args()

    random.seed(args.semente)
    dsn = dsn_do_des()
    print(f"🔌  des → {host_do(dsn)}")
    conn = await conectar(dsn)
    try:
        # Semear sempre limpa antes: rodar duas vezes não pode empilhar 120 contas.
        apagados = await limpar(conn)
        if apagados:
            print(f"🧹  {apagados} contas semeadas anteriormente foram removidas.")
        if args.limpar:
            print("✅  Limpeza concluída. O banco voltou a ter só as contas reais.")
            return
        await semear(conn, args.quantos, args.minha_posicao)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(principal())
