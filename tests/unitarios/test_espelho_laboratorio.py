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
import re
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

    # Ficam de fora os arquivos que uma FERRAMENTA gera na pasta, e que nem o
    # `.gitignore` nem o `.dockerignore` deixam sair da máquina: o `__pycache__`
    # do Python e, nos motores Dart, o `.dart_tool/` e o `pubspec.lock` que o
    # analisador do editor cria sozinho ao abrir a pasta (`pub get`). Sem isso o
    # teste falhava na máquina de quem só abriu o motor no editor, sem nada ter
    # nascido dentro do espelho.
    no_disco = {
        p.relative_to(ESPELHO).as_posix()
        for p in ESPELHO.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and ".dart_tool" not in p.parts
        and p.name != "pubspec.lock"
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


#: Os motores Dart que o espelho TEM de trazer, um por jogo que o job joga com o
#: código do aparelho. ⚠️ Lista escrita à mão de propósito: é ela que faz um
#: motor inteiro que sumisse do espelho reprovar aqui, em vez de o teste abaixo
#: passar por não achar nada para conferir.
MOTORES_DART_ESPERADOS = ("jogo_damas", "jogo_pontinhos", "jogo_quatro")

# Um `import` ou `export` de Dart: `import 'package:x/y.dart';`, `import 'y.dart'`.
# O grupo 1 é o texto entre aspas (simples ou duplas).
_IMPORT_DART = re.compile(r"""^\s*(?:import|export)\s+['"]([^'"]+)['"]""", re.M)


def test_cada_motor_dart_espelhado_tem_os_imports_dentro_do_espelho():
    """A prova, do lado Dart, de que a LISTA de arquivos espelhados está completa.

    É o irmão de `test_o_motor_espelhado_importa_de_verdade`: lá o Python importa
    o motor de damas; aqui, sem compilar nada, confere-se que todo `import` dos
    arquivos Dart espelhados (`lib/` e `bin/`) aponta para um arquivo que ESTÁ no
    espelho. Um arquivo novo em `lib/` esquecido na lista de
    `espelhar_laboratorio.py` faria o `dart compile` falhar **no build da imagem
    do Railway**, e não aqui.

    O que fica de fora, e por quê:
      - `dart:` e pacotes de terceiros (`package:crypto/...`): o `pub get` da
        imagem os traz;
      - os `.g.dart`: são o carimbo, que o compilador do servidor de lances
        reescreve no build a partir dos mesmos `lib/` (copiado daqui, ele poderia
        descrever outro conjunto).
    """
    for jogo in MOTORES_DART_ESPERADOS:
        pacote = ESPELHO / "jogos" / jogo / "motor_dart"
        pubspec = pacote / "pubspec.yaml"
        assert pubspec.is_file(), f"o espelho não traz o motor Dart de {jogo}"
        # O nome do pacote é o que `package:<nome>/` resolve para `lib/`.
        nome = re.search(r"^name:\s*(\S+)", pubspec.read_text("utf-8"), re.M)
        assert nome, f"{pubspec} sem `name:`"
        prefixo = f"package:{nome.group(1)}/"

        arquivos = sorted((pacote / "lib").glob("*.dart")) + sorted(
            (pacote / "bin").glob("*.dart")
        )
        assert arquivos, f"o motor Dart de {jogo} veio sem arquivos"
        for arquivo in arquivos:
            for alvo in _IMPORT_DART.findall(arquivo.read_text("utf-8")):
                if alvo.startswith(prefixo):
                    destino = pacote / "lib" / alvo[len(prefixo):]
                elif alvo.startswith(("dart:", "package:")):
                    continue
                else:
                    if alvo.endswith(".g.dart"):
                        continue
                    destino = arquivo.parent / alvo
                assert destino.resolve().is_file(), (
                    f"{arquivo.relative_to(ESPELHO)} importa '{alvo}', que não "
                    "está no espelho. Acrescente-o a `ARQUIVOS` em "
                    f"`scripts/espelhar_laboratorio.py` e rode:\n"
                    f"  {COMANDO_PARA_REESPELHAR}"
                )


def test_o_contrato_do_quatro_viaja_no_espelho():
    """O executável do Quatro em Linha recebe o contrato por `--contrato`.

    Sem ele no espelho, o job abriria o motor sem saber o tabuleiro. E ele tem
    de ser JSON com ao menos uma modalidade: um arquivo vazio passaria pelo
    manifesto (que só confere bytes contra bytes) e falharia na abertura.
    """
    contrato = ESPELHO / "jogos" / "jogo_quatro" / "contrato" / "contrato_quatro.json"
    assert contrato.is_file(), f"o espelho não traz {contrato.relative_to(ESPELHO)}"
    dados = json.loads(contrato.read_text(encoding="utf-8"))
    assert dados["por_modalidade"], "o contrato do Quatro veio sem modalidade"


# ── O motor Rust do xadrez (spec 012, T060) ─────────────────────────────────

CRATE_DO_XADREZ_NO_ESPELHO = ESPELHO / "jogos" / "jogo_xadrez" / "motor_rust"

# Uma declaração de módulo em ARQUIVO PRÓPRIO: `mod busca;` ou `pub mod busca;`.
# O `;` no fim é o que a separa de um módulo escrito ali mesmo (`mod testes {`),
# que não tem arquivo. O grupo 1 é o nome do módulo.
_MOD_RUST = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", re.M)


def _onde_mora_o_modulo(arquivo: Path, nome: str) -> tuple[Path, Path]:
    """Os dois lugares onde o Rust procura o `mod nome;` declarado em `arquivo`.

    Numa **raiz de crate** (`lib.rs`, `main.rs`, cada `src/bin/*.rs`) e num
    `mod.rs`, o módulo mora ao lado: `nome.rs` ou `nome/mod.rs`. Em qualquer
    outro arquivo `x.rs`, ele mora numa pasta com o nome do arquivo: `x/nome.rs`.
    """
    raiz_de_crate = arquivo.name in ("lib.rs", "main.rs", "mod.rs") or (
        arquivo.parent.name == "bin" and arquivo.parent.parent.name == "src"
    )
    pasta = arquivo.parent if raiz_de_crate else arquivo.parent / arquivo.stem
    return pasta / f"{nome}.rs", pasta / nome / "mod.rs"


def test_o_motor_rust_do_xadrez_tem_cada_modulo_dentro_do_espelho():
    """A prova, do lado Rust, de que a LISTA de arquivos espelhados está completa.

    O irmão Rust do teste dos imports Dart: todo `mod x;` de todo `.rs`
    espelhado aponta para um arquivo que ESTÁ no espelho. Um módulo novo no
    laboratório esquecido na lista faria o `cargo build` falhar no build da
    imagem do Railway (T061), e não aqui.
    """
    src = CRATE_DO_XADREZ_NO_ESPELHO / "src"
    assert (src / "lib.rs").is_file(), "o espelho não traz o motor Rust do xadrez"
    assert (src / "bin" / "servidor_de_lances_xadrez.rs").is_file(), (
        "o espelho não traz o executável do servidor (src/bin/)"
    )
    for compilacao in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml"):
        assert (CRATE_DO_XADREZ_NO_ESPELHO / compilacao).is_file(), compilacao

    arquivos = sorted(src.rglob("*.rs"))
    modulos = 0
    for arquivo in arquivos:
        for nome in _MOD_RUST.findall(arquivo.read_text("utf-8")):
            modulos += 1
            um, outro = _onde_mora_o_modulo(arquivo, nome)
            assert um.is_file() or outro.is_file(), (
                f"{arquivo.relative_to(ESPELHO)} declara `mod {nome};`, que não "
                "está no espelho. Acrescente-o a `ARQUIVOS_ESPELHADOS` em "
                f"`scripts/espelhar_laboratorio.py` e rode:\n"
                f"  {COMANDO_PARA_REESPELHAR}"
            )
    # Sem esta guarda, uma expressão regular quebrada passaria sem achar módulo.
    assert modulos >= 10, f"achei só {modulos} `mod` no crate do xadrez"


def test_o_espelho_do_xadrez_e_exatamente_o_que_o_carimbo_le():
    """Nada espelhado que o carimbo ignore, e nada que o carimbo leia faltando.

    O `ProcessoDart` confere o executável contra o resumo de `PADROES_RUST`
    sobre ESTA pasta. Um arquivo a mais no espelho (um teste, um script do app)
    seria compilado sem entrar no resumo; um a menos faria o resumo descrever
    outro motor. Os dois conjuntos têm de ser o mesmo.
    """
    from motores.nucleo.processo_dart import PADROES_RUST, hashes_dos_fontes

    no_espelho = {
        a.relative_to(CRATE_DO_XADREZ_NO_ESPELHO).as_posix()
        for a in CRATE_DO_XADREZ_NO_ESPELHO.rglob("*")
        if a.is_file()
    }
    assert set(hashes_dos_fontes(CRATE_DO_XADREZ_NO_ESPELHO, PADROES_RUST)) == no_espelho


def test_o_contrato_do_xadrez_viaja_no_espelho():
    """O executável do xadrez recebe o contrato por `--contrato`, como o Quatro."""
    contrato = ESPELHO / "jogos" / "jogo_xadrez" / "contrato" / "contrato_xadrez.json"
    assert contrato.is_file(), f"o espelho não traz {contrato.relative_to(ESPELHO)}"
    dados = json.loads(contrato.read_text(encoding="utf-8"))
    assert dados["por_modalidade"], "o contrato do xadrez veio sem modalidade"


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
