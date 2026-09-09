"""🔒 CADEADO 2 — a camada de motores não conhece desafio (RF-DES-165/166).

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE CADEADO NUNCA PULA
═══════════════════════════════════════════════════════════════════════════

Nenhum teste deste arquivo tem `skipif`, `xfail` ou qualquer saída de emergência,
e isso é deliberado. Um cadeado que pula "com motivo" fica **verde e cego** — o
defeito que RF-DES-143a existe para corrigir, e que o portão de aceite do servidor
(T050) conta como **vermelho**.

Ele também não importa o pacote `motores` para inspecioná-lo: lê os arquivos e os
analisa com `ast`, a árvore sintática do próprio Python. ⚠️ A diferença importa —
importar para conferir importações faria o teste **executar** o import proibido
antes de reprová-lo, e um `import fastapi` no topo de um módulo seria "aprovado"
só porque a biblioteca está instalada no ambiente de teste.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE PROÍBE, E POR QUÊ
═══════════════════════════════════════════════════════════════════════════

⛔ **Web** (`fastapi`, `starlette`, `uvicorn`, `pydantic`) — um motor que precise
   da API não serve ao job em batch, que é um container sem porta nem rota
   (RF-DES-011a), e não serviria a um bot de PvP amanhã.
⛔ **Banco** (`sqlalchemy`, `asyncpg`, `alembic`, `psycopg`) — RF-DES-162 manda o
   estado chegar **por valor**. Um motor que consulte o banco guarda sessão, e
   sessão é o oposto de "não guarda nada entre chamadas".
⛔ **A própria aplicação** (`api.`, `job.`, `migrations.`) — é a direção do
   import que está sendo travada: `api/` e `job/` importam `motores/`; nunca o
   contrário. É o mesmo cadeado de direção que RF-DES-159 pede no app, entre
   `lib/core/desafios/` e `lib/modulos/desafio_do_dia/`.
"""

import ast
from pathlib import Path

import pytest

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` até a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
PASTA_MOTORES = RAIZ_BACKEND / "motores"

# Prefixos de módulo proibidos. A comparação é por **prefixo de caminho pontuado**
# (`api.desafios` casa com `api`, mas `apizinha` não casa) — ver `_e_proibido`.
PREFIXOS_PROIBIDOS = (
    # Web / transporte
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "httpx",
    "requests",
    # Banco / persistência
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "psycopg",
    "psycopg2",
    "aiosqlite",
    # A aplicação em volta — a direção do import
    "api",
    "job",
    "migrations",
    "tests",
)


def _arquivos_de_motores() -> list[Path]:
    """Todos os `.py` sob `motores/`, exceto caches do interpretador.

    ⚠️ Varrer a pasta em vez de listar arquivos à mão é o que faz este cadeado
    **cobrir o jogo que ainda não existe**. Uma lista escrita à mão fica verde e
    cega quando alguém acrescenta um motor novo — já custou quatro fluxos de fim
    de partida no app, e a lição está no `CLAUDE.md`.
    """
    return sorted(p for p in PASTA_MOTORES.rglob("*.py") if "__pycache__" not in p.parts)


def _e_proibido(modulo: str) -> str | None:
    """Devolve o prefixo proibido que `modulo` viola, ou `None` se está limpo."""
    for prefixo in PREFIXOS_PROIBIDOS:
        # Ou é exatamente o módulo, ou é um pacote pai dele (`api.desafios`).
        if modulo == prefixo or modulo.startswith(prefixo + "."):
            return prefixo
    return None


def _modulos_importados(caminho: Path) -> list[tuple[int, str]]:
    """Lê o arquivo e devolve `(linha, módulo)` de cada import que ele faz.

    Trata as duas formas do Python:
      · `import x.y`        → nó `ast.Import`,     módulo `x.y`
      · `from x.y import z` → nó `ast.ImportFrom`, módulo `x.y`

    ⚠️ Import **relativo** (`from . import papeis`, `level > 0`) é ignorado de
    propósito: ele é interno a `motores/`, que é justamente o que se quer permitir.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for apelido in no.names:
                achados.append((no.lineno, apelido.name))
        elif isinstance(no, ast.ImportFrom):
            if no.level and no.level > 0:
                continue  # relativo: interno à camada
            if no.module:
                achados.append((no.lineno, no.module))
    return achados


def test_a_pasta_de_motores_existe_e_tem_codigo():
    """Guarda contra o pior modo de falha deste cadeado: varrer o vazio.

    Se `motores/` sumisse ou fosse renomeada, todos os testes abaixo passariam
    sem examinar arquivo nenhum, e o cadeado ficaria verde por não ter o que
    olhar. Este teste é o que impede isso.
    """
    assert PASTA_MOTORES.is_dir(), f"a camada de motores sumiu de {PASTA_MOTORES}"
    assert _arquivos_de_motores(), "nenhum .py encontrado sob motores/"


@pytest.mark.parametrize(
    "caminho", _arquivos_de_motores(), ids=lambda p: p.name
)
def test_arquivo_de_motor_nao_importa_nada_proibido(caminho: Path):
    """RF-DES-165 — nem web, nem banco, nem a aplicação em volta."""
    for linha, modulo in _modulos_importados(caminho):
        violado = _e_proibido(modulo)
        assert violado is None, (
            f"{caminho.relative_to(RAIZ_BACKEND)}:{linha} importa '{modulo}'.\n"
            f"A camada de motores não pode depender de '{violado}' (RF-DES-165):\n"
            "  · web/banco → o job é um container sem rota e sem sessão;\n"
            "  · api/job   → a direção do import é de fora para dentro, só."
        )


def test_nenhum_modulo_de_motor_se_chama_desafio():
    """A camada não sabe o que é 'desafio', 'dia', 'coleção' ou 'resolução'.

    ⚠️ Conferimos o **nome do arquivo**, não o texto: as docstrings falam de
    desafio o tempo todo, e devem mesmo — é o contexto que explica por que a
    fronteira existe. O que não pode é um módulo *ser* de desafio.
    """
    proibidas_no_nome = ("desafio", "resolucao", "quadro", "colecao", "curadoria")
    for caminho in _arquivos_de_motores():
        nome = caminho.stem.lower()
        for palavra in proibidas_no_nome:
            assert palavra not in nome, (
                f"{caminho.relative_to(RAIZ_BACKEND)} tem '{palavra}' no nome — "
                "a camada de motores não conhece desafio (RF-DES-165)."
            )


def test_nenhuma_rota_declarada_dentro_de_motores():
    """RF-DES-166 — ⛔ nenhum endpoint de motor nesta entrega.

    Procura os decoradores que criariam uma rota (`@app.get`, `@router.post`, …)
    e o próprio `APIRouter`. Sem `fastapi` importado eles não funcionariam, mas o
    teste é escrito de forma independente do import: o cadeado tem de acusar a
    **intenção**, mesmo que ela ainda não compile.
    """
    verbos = {"get", "post", "put", "patch", "delete", "head", "options"}
    for caminho in _arquivos_de_motores():
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            # `@algo.get(...)` é uma Call cujo `func` é um Attribute.
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                if no.func.attr in verbos and isinstance(no.func.value, ast.Name):
                    if no.func.value.id in {"app", "router", "roteador"}:
                        pytest.fail(
                            f"{caminho.relative_to(RAIZ_BACKEND)}:{no.lineno} declara "
                            f"rota '{no.func.value.id}.{no.func.attr}' — "
                            "⛔ nenhum endpoint de motor nesta entrega (RF-DES-166)."
                        )
            if isinstance(no, ast.Name) and no.id == "APIRouter":
                pytest.fail(
                    f"{caminho.relative_to(RAIZ_BACKEND)}:{no.lineno} usa APIRouter — "
                    "⛔ motores/ é camada importada, não serve rota (RF-DES-166)."
                )


def test_este_cadeado_nao_tem_saida_de_emergencia():
    """O cadeado que confere a si mesmo.

    ⚠️ Um pulo acrescentado aqui num dia apertado deixaria o arquivo verde para
    sempre, e ninguém notaria — é exatamente o defeito de RF-DES-143a. Então o
    próprio arquivo é lido em busca das marcas que permitiriam pular.

    ⚠️ **A conferência é por `ast`, não por busca de texto**, e a primeira versão
    ensinou por quê: procurar a string "@pytest.mark.skip" dentro do arquivo
    encontra a **própria linha que procura**, e o cadeado reprova a si mesmo. A
    árvore sintática enxerga decoradores e chamadas, não literais.
    """
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)

    # Nomes que, como último pedaço de um decorador ou de uma chamada, pulariam
    # o teste: `@pytest.mark.skip`, `@pytest.mark.skipif`, `@pytest.mark.xfail`,
    # `pytest.skip(...)`, `@unittest.skip`.
    marcas_de_pulo = {"skip", "skipif", "xfail"}

    def _nome_final(no: ast.AST) -> str | None:
        """Último identificador de um `a.b.c` ou de um `a.b.c(...)`."""
        if isinstance(no, ast.Call):
            return _nome_final(no.func)
        if isinstance(no, ast.Attribute):
            return no.attr
        if isinstance(no, ast.Name):
            return no.id
        return None

    for no in ast.walk(arvore):
        # 1) Decoradores de função (`@pytest.mark.skipif(...)`).
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorador in no.decorator_list:
                nome = _nome_final(decorador)
                assert nome not in marcas_de_pulo, (
                    f"{no.name} ganhou o decorador '{nome}'. "
                    "⛔ Cadeado de nível de CI não pula: verde e cego é pior "
                    "que vermelho (RF-DES-143a)."
                )
        # 2) Chamadas diretas (`pytest.skip("motivo")`) em qualquer lugar.
        if isinstance(no, ast.Call):
            alvo = no.func
            if isinstance(alvo, ast.Attribute) and alvo.attr == "skip":
                assert False, (
                    f"linha {no.lineno}: chamada a .skip(). "
                    "⛔ Este cadeado falha ou passa, nunca pula."
                )
