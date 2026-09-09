"""🔒 CADEADO 6, NÍVEL DE CI — o espelho do laboratório (RF-DES-143a/148/149).

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE NÍVEL NUNCA PULA — E É EXATAMENTE ESSE O PONTO
═══════════════════════════════════════════════════════════════════════════

O cadeado que já existe do lado do app (`contrato_hash_test.dart`) compara a
cópia contra o laboratório e **pula com motivo** quando o `ia/` não está no disco.
No CI o `ia/` nunca está: os três repositórios são independentes. Resultado, e é
o defeito que RF-DES-143a existe para corrigir: **verde e cego**.

Aqui a conferência é contra o `MANIFESTO_HASHES.json` que viaja **dentro deste
mesmo repositório**. Não há como faltar; não há motivo para pular; ⛔ não há
`skipif` neste arquivo, e o último teste confere isso.

O que ele protege, em uma frase: que o job na nuvem rode **o mesmo motor** que o
laboratório mediu. Um arquivo do espelho editado à mão — para "consertar um
import", para "ajustar um número" — faria o Railway jogar damas de um jeito
ligeiramente diferente do medido, e nada denunciaria.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE NÃO É
═══════════════════════════════════════════════════════════════════════════

⚠️ **Ele não confere contra o laboratório** — não pode, e é por isso que existe.
Esse é o **nível local**, e quem o faz é
`.venv\\Scripts\\python scripts\\espelhar_laboratorio.py --conferir`, na máquina
onde os três repositórios convivem.
"""

import ast
import hashlib
import json
from pathlib import Path

import pytest

# `parents[2]` sobe de `tests/unitarios/este_arquivo.py` até a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

COMANDO_PARA_REESPELHAR = ".venv\\Scripts\\python scripts\\espelhar_laboratorio.py"


def _manifesto() -> dict:
    """O manifesto do espelho. Falha alto se ele não existir.

    ⚠️ Não usa `pytest.skip`: um espelho sem manifesto é o pior estado possível —
    a cópia existe e ninguém sabe do que ela é cópia.
    """
    assert CAMINHO_DO_MANIFESTO.exists(), (
        f"o espelho não tem manifesto ({CAMINHO_DO_MANIFESTO}). "
        f"Regere na máquina do dono:\n  {COMANDO_PARA_REESPELHAR}"
    )
    return json.loads(CAMINHO_DO_MANIFESTO.read_text(encoding="utf-8"))


# `parametrize` a partir do manifesto: cada arquivo vira um caso de teste com
# nome próprio, então a saída diz **qual** arquivo divergiu, e não só "o espelho".
_DECLARADOS = _manifesto()["arquivos"]


def test_o_espelho_existe_e_o_manifesto_declara_arquivos():
    """Guarda contra o pior modo de falha: um cadeado que varre o vazio.

    Se o espelho sumisse, ou se o manifesto ficasse com a lista vazia, todos os
    testes parametrizados abaixo simplesmente não existiriam — e a suíte passaria
    sem examinar arquivo nenhum.
    """
    assert ESPELHO.is_dir(), f"a pasta do espelho sumiu de {ESPELHO}"
    assert len(_DECLARADOS) >= 20, (
        f"o manifesto declara só {len(_DECLARADOS)} arquivos. O espelho do motor "
        "de damas tem mais de vinte — alguém encolheu a lista."
    )


@pytest.mark.parametrize(
    "declarado", _DECLARADOS, ids=lambda d: d["caminho"].replace("/", "·")
)
def test_arquivo_do_espelho_bate_com_o_sha256_declarado(declarado):
    """O coração do cadeado: bytes contra hash, sem o laboratório no disco."""
    caminho = ESPELHO / declarado["caminho"]

    assert caminho.exists(), (
        f"o manifesto declara {declarado['caminho']}, que não está no espelho.\n"
        f"Reespelhe na máquina do dono:\n  {COMANDO_PARA_REESPELHAR}"
    )

    conteudo = caminho.read_bytes()
    obtido = hashlib.sha256(conteudo).hexdigest()

    assert obtido == declarado["sha256"], (
        f"{declarado['caminho']} DIVERGIU do que o manifesto declara.\n"
        "  Ou alguém editou a cópia à mão — e ⛔ a cópia nunca se edita: a fonte "
        "da verdade é o código em ia/ (RF-DES-149) —,\n"
        "  ou algo converteu o fim de linha no caminho (ver .gitattributes).\n"
        f"Conserto: {COMANDO_PARA_REESPELHAR}"
    )
    assert len(conteudo) == declarado["tamanho_bytes"]


def test_nenhum_arquivo_do_espelho_ficou_de_fora_do_manifesto():
    """O outro sentido da conferência, e o que pega o caso mais perigoso.

    O teste acima percorre o **manifesto**: um arquivo acrescentado ao espelho
    sem entrar no manifesto passaria despercebido por ele — e seria exatamente
    onde alguém poria código próprio dentro de uma pasta que promete ser cópia.
    """
    declarados = {d["caminho"] for d in _DECLARADOS}
    declarados.add("MANIFESTO_HASHES.json")  # ele não declara a si mesmo

    no_disco = {
        p.relative_to(ESPELHO).as_posix()
        for p in ESPELHO.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }

    sobrando = sorted(no_disco - declarados)
    assert not sobrando, (
        "há arquivo no espelho que o manifesto não declara:\n  "
        + "\n  ".join(sobrando)
        + f"\n⛔ Nada nasce dentro do espelho. Se veio do laboratório, acrescente-o "
        f"a ARQUIVOS_ESPELHADOS e reespelhe:\n  {COMANDO_PARA_REESPELHAR}"
    )


def test_o_motor_espelhado_importa_de_verdade():
    """A prova de que a LISTA de arquivos espelhados está completa.

    ⚠️ A lista em `espelhar_laboratorio.py` é escrita à mão — espelhar o `ia/`
    inteiro traria centenas de megabytes de notebooks e datasets para dentro da
    imagem do Railway. O preço de escrevê-la à mão é poder esquecer um arquivo, e
    o sintoma seria um `ImportError` **na nuvem, de madrugada**, quando o desafio
    do dia deveria ter sido gerado.

    Este teste paga esse preço aqui: importa o motor a partir do espelho, do
    mesmo jeito que o job vai importar.
    """
    import sys

    # `insert(0, ...)` põe o espelho na frente do caminho de busca, para que o
    # `jogos.jogo_damas...` resolvido seja o do espelho e não outro qualquer.
    sys.path.insert(0, str(ESPELHO))
    try:
        from jogos.jogo_damas.motor.busca_damas import NIVEIS
        from jogos.jogo_damas.motor.regras_damas import REGULAMENTOS
        from jogos.jogo_damas.motor.tabuleiro_damas import Tabuleiro
    finally:
        sys.path.remove(str(ESPELHO))

    # As quatro modalidades e os quatro níveis: se o espelho carregou meio motor,
    # alguma destas listas vem curta.
    assert list(REGULAMENTOS) == ["brasileira", "anglo", "portuguesa", "casa"]
    assert list(NIVEIS) == ["cacau", "pita", "tex", "sagaz"]
    assert Tabuleiro.inicial() is not None


def test_o_espelho_nao_e_uma_dependencia_de_caminho_disfarcada():
    """⛔ O que não estiver no repositório do backend não existe na nuvem.

    O modo de falha que este teste pega é sutil e tentador: alguém "resolve" um
    arquivo faltando pondo `sys.path.append('../ia')` — ou um `.pth` — dentro do
    espelho. Funciona na máquina do dono, passa em todos os outros testes daqui,
    e **quebra só no Railway**, onde `../ia` não existe.
    """
    for caminho in ESPELHO.rglob("*.py"):
        if "__pycache__" in caminho.parts:
            continue
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            # Qualquer literal de texto que suba um nível de pasta ou cite o
            # laboratório pelo nome.
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                texto = no.value
                for marca in ("../ia", "..\\ia", "arena-sagaz/ia"):
                    assert marca not in texto, (
                        f"{caminho.relative_to(ESPELHO)}:{no.lineno} cita "
                        f"'{marca}'. ⛔ O espelho é cópia versionada, nunca "
                        "dependência de caminho para outro repositório "
                        "(RF-DES-148)."
                    )


def test_este_cadeado_nao_tem_saida_de_emergencia():
    """O cadeado que confere a si mesmo (RF-DES-143a).

    A conferência é por `ast`, e não por busca de texto: procurar a string
    "@pytest.mark.skip" dentro do arquivo encontraria a própria linha que
    procura, e o cadeado reprovaria a si mesmo — lição do cadeado 2, no mesmo dia.
    """
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
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
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorador in no.decorator_list:
                nome = _nome_final(decorador)
                assert nome not in marcas_de_pulo, (
                    f"{no.name} ganhou o decorador '{nome}'. ⛔ Cadeado de nível "
                    "de CI não pula: verde e cego é pior que vermelho."
                )
        if isinstance(no, ast.Call):
            alvo = no.func
            if isinstance(alvo, ast.Attribute) and alvo.attr == "skip":
                raise AssertionError(
                    f"linha {no.lineno}: chamada a .skip(). "
                    "⛔ Este cadeado falha ou passa, nunca pula."
                )
