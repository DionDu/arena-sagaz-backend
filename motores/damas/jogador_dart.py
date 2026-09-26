"""O MOTOR DO APARELHO, JOGANDO PELO SERVIDOR (25/09/2026).

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE O SERVIDOR DEIXOU DE JOGAR COM O PORT PYTHON
═══════════════════════════════════════════════════════════════════════════

Até 25/09/2026 o gabarito e a régua eram jogados pelo port Python do motor, e o
aparelho jogava com o Dart (ou com o Rust, que é conferido contra o Dart). Os
dois liam os mesmos parâmetros do mesmo contrato — `teto_de_nos: 288000` e
`tempo_maximo: 10.0` — e mesmo assim escolhiam lances diferentes.

⚠️ **A causa não era o port: era o RELÓGIO.** O Python é ~40x mais lento, então
os 10 segundos de rede de segurança mordiam **todo lance** no servidor e **nunca**
no aparelho. Medido na posição que abriu o caso:

    Python, como estava   19-23    124.928 nós   profundidade 11   (10,0 s, estourou)
    Python, sem relógio   16-20    288.001 nós   profundidade 12   (29,8 s)
    Dart, este módulo     16-20    288.001 nós   profundidade 12   (0,7 s)
    Rust, no aparelho     16-20    288.001 nós   profundidade 12   (0,1 s)

⚠️ **Python e Dart batem até no número de acertos na tabela de transposição**
(27.908). Dois motores só chegam ao mesmo número de acertos se visitarem as
mesmas posições na mesma ordem — o port sempre foi fiel; o que o traía era a
coleira.

O diagnóstico inteiro, com a investigação passo a passo, está em
`docs/investigacao_paridade_motores.md`.

═══════════════════════════════════════════════════════════════════════════
⛔ O SERVIDOR JOGA SEM RELÓGIO, E ISSO É DECISÃO
═══════════════════════════════════════════════════════════════════════════

`tempo_maximo` não é enviado. A rede de segurança existe no aparelho porque há
**alguém esperando na tela**; aqui não há. E mantê-la reintroduziria exatamente o
defeito que este módulo fecha: o ponto de parada passaria a depender da carga da
máquina, e o **mesmo desafio daria lances diferentes em duas execuções** — com o
agravante de que nada no dado denunciaria.

⚠️ Sem relógio, quem manda é só o teto de nós, que é o mesmo dos dois lados. É o
que torna o gabarito reprodutível (RF-DES-208).

═══════════════════════════════════════════════════════════════════════════
⚠️ A TRAVA: O EXECUTÁVEL PRECISA PROVAR DE QUE CÓDIGO SAIU
═══════════════════════════════════════════════════════════════════════════

Pedido do dono, no mesmo dia: *"Importante também termos algum mecanismo que
garanta que o motor Dart compilado que vai jogar no servidor seja o mesmo
embarcado no App."*

Um executável é opaco. Quem corrigir uma regra no motor e esquecer de recompilar
deixaria o servidor gerando gabaritos com o motor **antigo**, e o sintoma seria o
mesmo que custou esta investigação: o gabarito não bate com a partida.

A corrente que fecha isso:

    app        == laboratório   `paridade_motor_test.dart`, SHA-256 dos 16
                                arquivos de `lib/` — já existia
    espelho    == laboratório   `scripts/espelhar_laboratorio.py` + o manifesto
    executável == espelho       ESTE módulo, na abertura do processo
    ───────────────────────────────────────────────────────────────────────
    logo, executável == app

⛔ **A conferência é na ABERTURA, e falha alto.** Recusar na hora custa uma
mensagem; descobrir depois custa uma fila inteira de desafios gerados com o motor
errado — e eles já estariam no banco, indistinguíveis dos bons.
"""

from __future__ import annotations

import atexit
import functools
import hashlib
import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]

#: Os fontes do motor Dart, espelhados do laboratório. São a REFERÊNCIA contra a
#: qual o carimbo do executável é conferido.
FONTES_DO_MOTOR_DART = (
    RAIZ / "espelho_laboratorio" / "jogos" / "jogo_damas" / "motor_dart" / "lib"
)

#: A versão do protocolo que este módulo sabe falar. Tem de bater com
#: `versaoDoProtocolo` em `bin/servidor_de_lances_damas.dart`.
#:
#: ⚠️ **2 (25/09/2026): a base de finais.** Um executável da versão 1 ignoraria
#: `pasta_da_base` **em silêncio** e devolveria um lance buscado onde o aparelho
#: responde pela base — que é o pior modo de falha possível.
VERSAO_DO_PROTOCOLO = 2


#: A variável de ambiente que aponta para a base de finais, quando ela não está
#: no espelho.
#:
#: ═══════════════════════════════════════════════════════════════════════════
#: ⛔ É A BASE DO APLICATIVO, E NÃO A DO LABORATÓRIO — elas NÃO respondem igual
#: ═══════════════════════════════════════════════════════════════════════════
#:
#: O laboratório grava a base crua, com as **41** fatias de cada modalidade. O
#: que viaja no APK é o formato empacotado, com **23** — metade sai por simetria
#: de cor, e o resto é gzip por fatia (37,6 MB viram 2,3 MB). Ver
#: `motor_dart/bin/empacotar_base_damas.dart`.
#:
#: ⚠️ **E as duas dão respostas diferentes onde uma fatia falta.** `consultar`
#: devolve `foraDaBase` — *"não sei"* — para uma fatia ausente, e o motor então
#: **busca** em vez de responder. Apontar isto para `ia/dados/` faria o servidor
#: jogar finais que o aparelho de ninguém joga: mais base, não menos, e mesmo
#: assim divergente.
#:
#: ⚠️ **Ela é ESPELHADA para dentro deste repositório**, em
#: `espelho_laboratorio/base_finais_damas/`, pelo mesmo mecanismo e pelo mesmo
#: motivo que o `.tflite` do Pontinhos: o Railway constrói a imagem a partir
#: daqui, e o que não estiver aqui dentro não existe na nuvem (RF-DES-148).
#:
#: ⛔ **E o espelho é a ÚNICA origem em runtime.** Ler direto dos assets do
#: aplicativo funcionaria na máquina do dono e não na nuvem — e uma segunda
#: origem consultada em tempo de execução é exatamente como duas versões passam a
#: existir sem ninguém decidir. Quem garante que a cópia é fiel é
#: `scripts/espelhar_laboratorio.py` (que copia) e o manifesto de hashes (que
#: confere, sem precisar do aplicativo no disco).
VARIAVEL_DA_BASE = "BASE_FINAIS_DAMAS"

#: Onde a base espelhada mora, dentro deste repositório.
BASE_NO_ESPELHO = RAIZ / "espelho_laboratorio" / "base_finais_damas"

#: Quantas peças a base cobre. ⚠️ **4, e é o que o aplicativo embarca** — o
#: laboratório tem `brasileira_5` no disco, e usá-la aqui seria outro adversário.
PECAS_NA_BASE = 4


class MotorDartIndisponivel(RuntimeError):
    """Não há executável utilizável — e a mensagem diz como fazer um."""


class MotorDartDivergente(RuntimeError):
    """O executável não saiu dos fontes que este backend tem.

    ⛔ **Não é aviso, é recusa.** Gerar desafios com um motor que não é o do
    aparelho é o defeito que este módulo existe para impedir.
    """


def _sha256_do_arquivo(caminho: Path) -> str:
    """O SHA-256 de um arquivo, em hexadecimal.

    ⚠️ Lê em **bytes**: ler como texto passaria pela tradução de fim de linha do
    Windows, e o hash descreveria algo que não está no disco.
    """
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def resumo_dos_fontes(pasta: Path = FONTES_DO_MOTOR_DART) -> str:
    """O resumo dos fontes Dart — a MESMA fórmula do lado Dart.

    ⚠️ **A fórmula está escrita duas vezes**, aqui e em
    `motor_dart/bin/compilar_servidor_de_lances.dart`, e não há como evitar: são
    linguagens diferentes conferindo uma à outra. O que impede as duas de
    divergirem em silêncio é que **divergir é justamente o que elas detectam** —
    uma fórmula mudada de um lado só faz a abertura falhar na hora.

    A ordem é alfabética por nome, e o material é `nome:hash` por linha.
    """
    if not pasta.is_dir():
        raise MotorDartIndisponivel(
            f"não achei os fontes do motor Dart em {pasta}.\n"
            "Rode, na máquina do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    hashes = {
        arquivo.name: _sha256_do_arquivo(arquivo)
        for arquivo in sorted(pasta.glob("*.dart"), key=lambda a: a.name)
    }
    material = "\n".join(f"{nome}:{hash_}" for nome, hash_ in hashes.items())
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def caminho_do_executavel() -> Path:
    """Onde está o executável do motor Dart.

    A ordem de procura, e cada degrau tem um motivo:

      1. `MOTOR_DART_DAMAS` no ambiente — é como a máquina de outra pessoa (ou um
         contêiner) aponta para o binário dela sem editar código;
      2. o laboratório vizinho — o caso normal na máquina do dono, onde os três
         repositórios moram lado a lado.

    Raises:
        MotorDartIndisponivel: com a receita de como compilar.
    """
    do_ambiente = os.environ.get("MOTOR_DART_DAMAS")
    if do_ambiente:
        caminho = Path(do_ambiente)
        if caminho.is_file():
            return caminho
        raise MotorDartIndisponivel(
            f"MOTOR_DART_DAMAS aponta para {caminho}, que não existe."
        )

    nome = (
        "servidor_de_lances_damas.exe"
        if os.name == "nt"
        else "servidor_de_lances_damas"
    )
    vizinho = (
        RAIZ.parent / "ia" / "jogos" / "jogo_damas" / "motor_dart" / "bin" / nome
    )
    if vizinho.is_file():
        return vizinho

    raise MotorDartIndisponivel(
        f"não achei o motor Dart compilado (procurei em {vizinho}).\n"
        "Rode, na máquina do dono:\n"
        "  cd ..\\ia\\jogos\\jogo_damas\\motor_dart\n"
        "  dart run bin\\compilar_servidor_de_lances.dart"
    )


class BaseDeFinaisIndisponivel(RuntimeError):
    """Não há a base que o aparelho embarca — e o nível pedido precisa dela.

    ⛔ **Não é aviso, é recusa.** O Magno do aparelho consulta a base em todo
    final de até 4 peças; gerar um gabarito sem ela publica uma partida que o
    adversário do dia não vai jogar.
    """


@functools.lru_cache(maxsize=None)
def pasta_da_base_de_finais(co_modalidade: str) -> Path:
    """A pasta da base **daquela modalidade**, na forma que o aparelho carrega.

    ⚠️ **Memorizada** (`lru_cache`): ela lê e decodifica o manifesto, e o job a
    chamaria uma vez por lance — dezenas de milhares de vezes por dia, para
    responder sempre a mesma coisa.

    A ordem de procura, e cada degrau tem um motivo:

      1. `BASE_FINAIS_DAMAS` no ambiente — a saída para quem guarda a base fora
         do repositório;
      2. o **espelho**, que é o caminho normal nos dois lugares: na máquina do
         dono e dentro da imagem do Railway. ⚠️ É o mesmo arquivo que o
         aplicativo embarca, copiado por `scripts/espelhar_laboratorio.py` e
         conferido pelo manifesto de hashes.

    Raises:
        BaseDeFinaisIndisponivel: não há pasta, ou há e é a **crua** do
            laboratório. ⚠️ A segunda recusa é a que importa: a base crua abre
            sem queixa, responde mais posições que a do aplicativo e faria o
            servidor jogar finais que ninguém joga. Quem as separa é a chave
            `empacotado_em` do manifesto, que só o empacotador escreve.
    """
    do_ambiente = os.environ.get(VARIAVEL_DA_BASE)
    raiz = Path(do_ambiente) if do_ambiente else BASE_NO_ESPELHO

    pasta = raiz / f"{co_modalidade}_{PECAS_NA_BASE}"
    manifesto = pasta / "manifesto.json"
    if not manifesto.is_file():
        raise BaseDeFinaisIndisponivel(
            f"não achei a base de finais de {co_modalidade} (procurei o "
            f"manifesto em {manifesto}).\n"
            f"É a base que o APLICATIVO embarca, espelhada para cá. Traga-a "
            f"com:\n"
            f"  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py\n"
            f"Se ela mora fora do repositório, aponte {VARIAVEL_DA_BASE} para a "
            f"pasta que contém os `<modalidade>_{PECAS_NA_BASE}`."
        )

    declarado = json.loads(manifesto.read_text(encoding="utf-8"))
    if "empacotado_em" not in declarado:
        raise BaseDeFinaisIndisponivel(
            f"a base em {pasta} é a CRUA do laboratório, e o aparelho embarca a "
            f"empacotada. Elas não respondem igual: a do aplicativo tem metade "
            f"das fatias (o resto sai por simetria de cor), e onde falta uma "
            f"fatia a resposta é `foraDaBase` — o motor busca em vez de "
            f"responder. Aponte {VARIAVEL_DA_BASE} para "
            f"`arena-sagaz-frontend/assets/jogos/damas/base_finais`."
        )
    return pasta


class JogadorDart:
    """Um processo do motor Dart, vivo, respondendo a pedidos de lance.

    ⚠️ **O processo fica vivo de propósito.** A régua mede 20 execuções por
    mascote, e uma partida tem dezenas de lances: subir um processo por lance
    pagaria a partida do executável milhares de vezes.

    Use como contexto, para o processo ser encerrado mesmo se algo estourar::

        with JogadorDart() as jogador:
            lance = jogador.escolher_lance(...)
    """

    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or caminho_do_executavel()
        self._processo = subprocess.Popen(
            [str(self._caminho)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # ⛔ O stderr fica SEPARADO. Juntá-lo ao stdout misturaria um aviso
            # solto do runtime do Dart com as respostas JSON, e o cliente leria
            # lixo no lugar de um lance.
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._abertura = self._conferir_a_abertura()

    # ── A trava ──────────────────────────────────────────────────────────────

    def _conferir_a_abertura(self) -> dict[str, Any]:
        """Lê a linha de apresentação e recusa um executável que não seja o nosso."""
        linha = self._processo.stdout.readline()  # type: ignore[union-attr]
        if not linha:
            erro = self._processo.stderr.read()  # type: ignore[union-attr]
            raise MotorDartIndisponivel(
                f"o motor Dart em {self._caminho} não respondeu na abertura.\n{erro}"
            )
        abertura = json.loads(linha)

        if abertura.get("versao_do_protocolo") != VERSAO_DO_PROTOCOLO:
            raise MotorDartDivergente(
                f"o executável fala o protocolo {abertura.get('versao_do_protocolo')} "
                f"e este backend fala o {VERSAO_DO_PROTOCOLO}. Recompile o motor."
            )

        esperado = resumo_dos_fontes()
        recebido = abertura.get("resumo_do_motor")
        if recebido != esperado:
            # ⚠️ A mensagem nomeia **quais** arquivos divergiram. "O resumo não
            # bate" manda procurar em dezesseis arquivos; o nome manda direto ao que
            # mudou — e costuma responder sozinho se falta recompilar ou falta
            # espelhar.
            do_exe: dict[str, str] = abertura.get("arquivos_do_motor", {})
            daqui = {
                arquivo.name: _sha256_do_arquivo(arquivo)
                for arquivo in sorted(FONTES_DO_MOTOR_DART.glob("*.dart"))
            }
            diferentes = sorted(
                nome
                for nome in set(do_exe) | set(daqui)
                if do_exe.get(nome) != daqui.get(nome)
            )
            raise MotorDartDivergente(
                f"o executável em {self._caminho} não saiu dos fontes deste "
                f"backend.\n"
                f"  divergem: {', '.join(diferentes) or '(a lista de arquivos)'}\n"
                f"  esperado: {esperado[:16]}\n"
                f"  recebido: {str(recebido)[:16]}\n"
                "Recompile o motor e espelhe de novo:\n"
                "  cd ..\\ia\\jogos\\jogo_damas\\motor_dart\n"
                "  dart run bin\\compilar_servidor_de_lances.dart\n"
                "  cd ..\\..\\..\\..\\arena-sagaz-backend\n"
                "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
            )
        return abertura

    @property
    def resumo_do_motor(self) -> str:
        """O resumo dos fontes com que este executável foi compilado.

        ⚠️ Serve para ir ao BANCO, junto do desafio: é o que responde, meses
        depois, *"este gabarito saiu de que motor?"* sem depender do Git.
        """
        return self._abertura["resumo_do_motor"]

    @property
    def morreu(self) -> bool:
        """O processo saiu (por erro, ou porque alguém o encerrou).

        ⚠️ Serve ao processo compartilhado: um motor morto precisa ser
        substituído, e não reusado até o pedido seguinte estourar com
        `MotorDartIndisponivel` no meio de uma medição de horas.
        """
        return self._processo.poll() is not None

    # ── O uso ────────────────────────────────────────────────────────────────

    def pedir(self, pedido: dict[str, Any]) -> dict[str, Any]:
        """Manda um pedido e devolve a resposta decodificada."""
        if self._processo.poll() is not None:
            raise MotorDartIndisponivel(
                f"o motor Dart morreu (código {self._processo.returncode}). "
                f"stderr: {self._processo.stderr.read()}"  # type: ignore[union-attr]
            )
        self._processo.stdin.write(json.dumps(pedido) + "\n")  # type: ignore[union-attr]
        self._processo.stdin.flush()  # type: ignore[union-attr]
        linha = self._processo.stdout.readline()  # type: ignore[union-attr]
        if not linha:
            raise MotorDartIndisponivel(
                "o motor Dart não respondeu ao pedido. "
                f"stderr: {self._processo.stderr.read()}"  # type: ignore[union-attr]
            )
        return json.loads(linha)

    def escolher_lance(
        self,
        *,
        co_modalidade: str,
        fen_inicial: str,
        lances: tuple[str, ...] | list[str],
        parametros: Any,
        semente: int | None = None,
        pasta_da_base: Path | None = None,
    ) -> dict[str, Any]:
        """O lance que o motor do aparelho joga nesta partida, neste nível.

        Args:
            parametros: o que `contrato_damas.parametros_do_nivel()` devolve.
                ⚠️ **Os números vêm do CONTRATO, não daqui e não do Dart.** É o
                contrato a declaração única dos níveis, e repetir qualquer um
                destes valores neste arquivo criaria mais uma cópia de um número
                que já mora em quatro lugares.

        Returns:
            A resposta inteira — `lance`, `nos`, `profundidade`, `nota`, `ms`.
            ⚠️ Devolve tudo, e não só o lance: é comparando **nós** e
            **profundidade** que se descobre que dois motores pararam em pontos
            diferentes, e foi assim que o defeito de 25/09/2026 apareceu.

        Raises:
            ValueError: se o motor recusar a partida (lance ilegal, posição
                terminal). ⚠️ Falha alto: um estado impossível não se constrói em
                silêncio.
        """
        resposta = self.pedir(
            {
                "modalidade": co_modalidade,
                "fen_inicial": fen_inicial,
                "lances": list(lances),
                "profundidade": parametros.profundidade,
                "teto_de_nos": parametros.teto_de_nos,
                # ⛔ `tempo_maximo` NÃO vai. Ver o cabeçalho deste módulo.
                "ruido": parametros.ruido,
                "extensao_de_captura": parametros.extensao_de_captura,
                "chance_de_errar": parametros.chance_de_errar,
                "margem_do_erro": parametros.margem_do_erro,
                "semente": semente,
                # ⚠️ **Caminho de pasta, e não bytes.** É como o aparelho a
                # entrega ao isolate e ao motor Rust: quem lê os arquivos é o
                # motor, do outro lado da fronteira. Passar os bytes por aqui
                # mandaria 2,3 MB por lance pelo `stdin`.
                #
                # `None` significa **sem base**, e é o estado de todo nível que
                # não seja o Magno — no aparelho também.
                "pasta_da_base": str(pasta_da_base) if pasta_da_base else None,
            }
        )
        if "erro" in resposta:
            raise ValueError(f"o motor Dart recusou: {resposta['erro']}")
        return resposta

    # ── O fim ────────────────────────────────────────────────────────────────

    def encerrar(self) -> None:
        """Fecha a entrada e espera o processo sair."""
        if self._processo.poll() is None:
            try:
                self._processo.stdin.close()  # type: ignore[union-attr]
                self._processo.wait(timeout=5)
            except Exception:
                self._processo.kill()

    def __enter__(self) -> "JogadorDart":
        return self

    def __exit__(self, *_) -> None:
        self.encerrar()


# ═══════════════════════════════════════════════════════════════════════════
# O PROCESSO COMPARTILHADO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Um processo por processo Python, e não um por partida.** O job mede a
# régua com 20 execuções por mascote, e cada execução é uma partida inteira: o
# gerador faz dezenas de milhares de chamadas a `escolher_lance` num dia. Subir
# um executável por chamada pagaria a partida do Dart (carregar o binário,
# conferir o carimbo) esse tanto de vezes.
#
# ⛔ **E ele NÃO carrega estado de partida.** O `Buscador` nasce dentro de cada
# pedido, do outro lado: o que se reaproveita aqui é o processo, não a tabela de
# transposição. Reaproveitar a tabela faria o mesmo nível jogar diferente
# conforme a ordem em que as posições foram perguntadas — é a mesma nota que
# `MotorDamas` já carrega, e vale igual do lado Dart.
#
# ⚠️ **Quando o job roda em vários processos** (o `--processos` da maratona), cada
# um monta o seu: esta variável é global do *processo*, e `multiprocessing` no
# Windows parte de um interpretador novo. É o que se quer — um executável por
# trabalhador, sem nenhum recurso compartilhado entre eles.
#
# ⛔ **Num sistema que use `fork`** (Linux, o padrão do `multiprocessing` lá), o
# filho herdaria este processo já aberto, e **dois Python escreveriam no mesmo
# `stdin`** — as respostas voltariam trocadas, sem erro nenhum. Quem for
# paralelizar fora do Windows precisa de `spawn`, ou de chamar `encerrar()` no
# filho antes do primeiro lance. Hoje não é o caso.

#: ⛔ **UM MOTOR POR THREAD, e não um por processo.**
#:
#: ⚠️ A fronteira com o motor é um `stdin`/`stdout` de linha única: quem escreve
#: um pedido **espera** a resposta antes do próximo. Duas threads dividindo o
#: mesmo processo receberiam as respostas trocadas — e trocadas sem erro nenhum,
#: que é o pior modo de falha possível.
#:
#: ⚠️ **E é isso que destrava a máquina.** Com um motor por thread, N threads são
#: N processos do executável calculando ao mesmo tempo, e o Python fica parado no
#: `readline()` de cada um — o GIL é liberado durante a espera de E/S, então não
#: há disputa. Sem isto, os 16 núcleos do PC do dono ficavam com **um** ocupado, e
#: a régua de um candidato de damas levava 285 s.
#:
#: `threading.local()` é um objeto cujos atributos são **por thread**: cada uma
#: enxerga só o que ela mesma guardou ali.
_por_thread = threading.local()

#: Todos os motores já abertos, para poder fechá-los na saída do processo.
#:
#: ⚠️ Um `atexit.register` por motor vazaria registros numa execução com muitas
#: threads; uma lista e um único registro bastam.
_abertos: list[JogadorDart] = []
_cadeado = threading.Lock()


def _encerrar_todos() -> None:
    """Fecha todos os motores abertos — chamado uma vez, na saída do processo."""
    with _cadeado:
        for jogador in _abertos:
            jogador.encerrar()


atexit.register(_encerrar_todos)


def jogador_compartilhado() -> JogadorDart:
    """O motor Dart **desta thread**, subindo-o na primeira vez que for pedido.

    ⚠️ **Preguiçoso de propósito.** Quem só usa o papel de *árbitro* do
    `MotorDamas` (o auditor de resoluções, por exemplo) nunca escolhe um lance —
    e não deve pagar um executável, nem falhar por não ter um.

    ⚠️ **Nem um pool, nem uma fila.** Uma thread que já tem motor o reusa; uma
    thread nova paga a partida do executável uma vez (~200 ms, mais a conferência
    do carimbo). Num `ThreadPoolExecutor` as threads são reaproveitadas, então o
    custo é pago uma vez por worker, e não por execução.

    Raises:
        MotorDartIndisponivel: não há executável compilado.
        MotorDartDivergente: há, mas não saiu dos fontes deste backend.
    """
    meu = getattr(_por_thread, "jogador", None)
    if meu is not None and not meu.morreu:
        return meu

    meu = JogadorDart()
    _por_thread.jogador = meu
    with _cadeado:
        _abertos.append(meu)
    return meu
