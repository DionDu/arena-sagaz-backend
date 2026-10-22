"""T124c (spec 010), passo 4 - por que o "bloquear" não dá escada.

═══════════════════════════════════════════════════════════════════════════
A PERGUNTA
═══════════════════════════════════════════════════════════════════════════

O desafio é *"Bloqueie 3 ameaças do adversário e não perca"*
(`quatro_bloquear`, em `RECEITAS_FORA_DO_AR`). A régua de 20/10 deu FOLGA e
0 de 3 dias na escada; o perseguidor (histórico do backend, "2026-10-21 (9)")
não mudou isso: Cacau 0,33 · Pita 0,47 · Tex 0,50 · Magno 0,43 - o Magno
ABAIXO do Tex. Este script é um DIAGNÓSTICO, e não uma posição nova: antes de
mexer em qualquer botão, ele mede o que acontece dentro das partidas.

A hipótese (minha, de 21/10): quem joga melhor vence cedo, e o adversário cria
menos ameaças para bloquear. Se for isso, a falha do Magno é "não perdeu, mas
bloqueou menos de 3", e a do Cacau é "perdeu". Se não for, os números mostram
outra coisa (o Magno ignorando ameaças, por exemplo), e a decisão é outra.

Por partida, do ponto de vista de quem resolve:

  * **turnos com ameaça**: as vezes em que, na vez dele, o adversário tinha
    uma casa JOGÁVEL que fecharia quatro em linha (a ameaça que se bloqueia);
  * **turnos com ameaça dupla**: duas ou mais dessas casas (uma só se tapa);
  * **bloqueios**: os lances que ocuparam uma casa de ameaça do adversário -
    a mesma conta do medidor do desafio (`feitos_quatro.medir`,
    `ameacas_bloqueadas`), conferida partida a partida;
  * **venceu no lugar**: havia ameaça, e ele venceu em vez de bloquear;
  * **ignoradas**: havia ameaça, e ele não bloqueou nem venceu (um erro);
  * o desfecho (venceu · empatou · perdeu) e quantos meios-lances durou.

⚠️ **As partidas são as da régua, pelo caminho da régua.** A posição sai de
`gerador.gerar_candidatos` (o tipo em avaliação, com os botões de
`EDITORIAL_FORA_DO_AR`), a bancada de `gerador.bancada`, e cada partida de
`regua.tentativa_com_motor` - a mesma função que o job e a bancada do editorial
chamam. O script só troca o `julgar` por um que GUARDA a fita e devolve o
julgamento verdadeiro. Uma segunda escrita do laço mediria outra partida.

E, ao contrário da régua, os QUATRO personagens jogam contra os QUATRO
adversários: o relatório mostra a tabela inteira, e a "visão da régua" (quem
resolve diferente do adversário do dia) num bloco à parte.

═══════════════════════════════════════════════════════════════════════════
OS CONTROLES, ANTES DOS NÚMEROS
═══════════════════════════════════════════════════════════════════════════

  * **as partidas montadas à mão** (`CONTROLES`): um bloqueio, uma ameaça
    ignorada, uma ameaça dupla e uma vitória no lugar do bloqueio, cada uma
    com a contagem que tem de sair. Se uma falhar, o script PARA antes de
    abrir o motor: a tabela mediria o instrumento;
  * **partida a partida**, a contagem de bloqueios do script tem de bater com
    a do medidor de produção, e o veredito da régua com a conta "bloqueou 3 e
    não perdeu". O relatório diz em quantas partidas bateu; fora de N de N,
    não se lê o resto.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomável, todos os núcleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\diagnosticar_bloquear_quatro.py

Cada DIA concluído (uma posição, as 16 combinações × as execuções) vira uma
linha do diário `medicoes/diagnosticar_bloquear_quatro/diario.jsonl`; rodar de
novo pula o que já está lá. O relatório sai em `relatorio.txt`, na mesma pasta,
reescrito a cada execução a partir do diário inteiro. Opções: `--dias 30`,
`--execucoes 5` (por par quem resolve × adversário), `--processos N` (padrão:
todos os núcleos), `--pasta` (outra pasta de saída; o ensaio usa).
⚠️ Mudar `--execucoes` com o diário cheio mistura duas amostras: apague a pasta
antes (ou mova-a).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

# ⚠️ Um script em `scripts/` não é pacote instalado: sem isto, `from job import
# ...` falha. `parents[1]` sobe de `scripts/este_arquivo.py` para a raiz.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows é cp1252; sem isto o primeiro `×` derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job import editorial as editorial_mod  # noqa: E402
from job import gerador as gerador_mod  # noqa: E402
from job import regua as regua_mod  # noqa: E402
from job.perfil import NIVEL_POR_PERSONAGEM  # noqa: E402
from job.tipos_de_desafio import RECEITAS_FORA_DO_AR  # noqa: E402
from motores.nucleo import recursos_por_thread  # noqa: E402
from motores.quatro import feitos_quatro  # noqa: E402
from motores.quatro.motor_quatro import MotorQuatro, ler_sequencia  # noqa: E402

PASTA_PADRAO = RAIZ / "medicoes" / "diagnosticar_bloquear_quatro"

CO_TIPO = "quatro_bloquear"

#: O 1º dia da amostra: o mesmo `DIA_BASE` de `medir_variantes_do_editorial.py`,
#: e então os três primeiros dias são as posições da régua de 20/10.
DIA_BASE = date(2026, 10, 1)

#: Os quatro personagens, do mais fraco ao mais forte (a ordem do relatório).
PERSONAGENS = tuple(NIVEL_POR_PERSONAGEM)

#: Quantas ameaças o desafio pede (o número do editorial, lido na hora).
AMEACAS = editorial_mod.EDITORIAL_FORA_DO_AR[CO_TIPO][0].parametros["ameacas"]

#: As partidas montadas à mão, com a contagem que o script TEM de achar.
#: Todas a partir do tabuleiro vazio: quem resolve é o jogador 1, que começa.
#: O jogador 2 empilha três na coluna 1 (ameaça em (1,4)); o 1 joga na 7 e na 6.
_TRES_NA_COLUNA_1 = "s7s1s7s1s6s1"
#: O jogador 2 deita três na linha de baixo (colunas 2 a 4): (1,1) e (5,1) livres.
_TRES_DEITADAS = "s7s2s7s3s6s4"
#: O jogador 1 tem três na coluna 7 e o 2 três na coluna 1, com a vez do 1.
_OS_DOIS_AMEACAM = "s7s1s7s1s7s1"

CONTROLES: dict[str, tuple[str, dict[str, int]]] = {
    "bloqueio": (
        _TRES_NA_COLUNA_1 + "s1",
        {"turnos_com_ameaca": 1, "turnos_com_dupla": 0, "bloqueios": 1, "ignoradas": 0},
    ),
    "ignorada": (
        _TRES_NA_COLUNA_1 + "s2",
        {"turnos_com_ameaca": 1, "bloqueios": 0, "ignoradas": 1, "venceu_no_lugar": 0},
    ),
    "dupla": (
        _TRES_DEITADAS + "s1",
        {"turnos_com_ameaca": 1, "turnos_com_dupla": 1, "bloqueios": 1},
    ),
    "venceu_no_lugar": (
        _OS_DOIS_AMEACAM + "s7",
        {"turnos_com_ameaca": 1, "bloqueios": 0, "ignoradas": 0, "venceu_no_lugar": 1},
    ),
}


def analisar_partida(
    motor: MotorQuatro, lances_iniciais: Sequence[str], fita: Sequence[str]
) -> dict[str, Any]:
    """Conta as ameaças e os bloqueios de UMA partida, do lado de quem resolve.

    Args:
        motor: o árbitro da modalidade.
        lances_iniciais: a posição publicada (`("s4", "s4", ...)`).
        fita: os lances jogados depois dela, dos dois lados.

    ⚠️ A partida é refeita por `feitos_quatro._reproduzir` e as casas de ameaça
    saem de `feitos_quatro.casas_de_ameaca`: as funções do medidor do desafio,
    e não uma segunda escrita delas. A única coisa nova é a pergunta "havia
    ameaça na vez dele?", que o medidor não faz (ele só conta o que se tapou).
    """
    pessoa, passos, estado = feitos_quatro._reproduzir(motor, lances_iniciais, fita)
    dimensoes = motor.regras.dimensoes
    contagem = Counter()
    for antes, _lance, depois in passos:
        # Só os lances de quem resolve: os de quem tinha a vez ANTES deles.
        if antes.vez != pessoa:
            continue
        # As casas jogáveis agora: a de cima de cada coluna que não encheu.
        # `enumerate(..., 1)` numera as colunas de 1 a 7, como o motor.
        jogaveis = {
            (coluna, len(pilha) + 1)
            for coluna, pilha in enumerate(antes.colunas, 1)
            if len(pilha) < dimensoes.altura
        }
        do_adversario = feitos_quatro.casas_de_ameaca(dimensoes, antes, -pessoa)
        minhas = feitos_quatro.casas_de_ameaca(dimensoes, antes, pessoa)
        # `&` é a interseção de conjuntos: as ameaças que se pode tapar já.
        ameacas = jogaveis & do_adversario
        casa = feitos_quatro._casa_ocupada(antes, depois)
        if ameacas:
            contagem["turnos_com_ameaca"] += 1
        if len(ameacas) >= 2:
            contagem["turnos_com_dupla"] += 1
        # O bloqueio é a regra do medidor: a casa ocupada era de ameaça.
        if casa is not None and casa in do_adversario:
            contagem["bloqueios"] += 1
        elif ameacas:
            # Havia o que tapar, e ele não tapou: ou venceu ali, ou errou.
            if casa in minhas:
                contagem["venceu_no_lugar"] += 1
            else:
                contagem["ignoradas"] += 1

    desfecho = motor.regras.desfecho(motor.tabuleiro(estado))
    if desfecho is None:
        resultado = "em_aberto"
    elif desfecho.vencedor is None:
        resultado = "empatou"
    else:
        resultado = "venceu" if desfecho.vencedor == pessoa else "perdeu"
    medidas = feitos_quatro.medir(motor, lances_iniciais, fita)
    return {
        # `dict(Counter)` perde as chaves zeradas; o `get` as devolve.
        **{
            chave: contagem.get(chave, 0)
            for chave in (
                "turnos_com_ameaca",
                "turnos_com_dupla",
                "bloqueios",
                "venceu_no_lugar",
                "ignoradas",
            )
        },
        "resultado": resultado,
        "meios_lances": len(fita),
        # O número do medidor de produção, para o controle partida a partida.
        "bloqueios_do_medidor": int(medidas["ameacas_bloqueadas"]),
    }


def conferir_controles(motor: MotorQuatro | None = None) -> list[str]:
    """As falhas dos controles montados à mão (vazio = o instrumento mede)."""
    motor = motor or MotorQuatro("tradicional")
    falhas: list[str] = []
    for nome, (sequencia, esperado) in CONTROLES.items():
        obtido = analisar_partida(motor, (), ler_sequencia(sequencia))
        for chave, valor in esperado.items():
            if obtido[chave] != valor:
                falhas.append(f"{nome}: {chave} = {obtido[chave]}, esperado {valor}")
        if obtido["bloqueios"] != obtido["bloqueios_do_medidor"]:
            falhas.append(f"{nome}: o script e o medidor discordam nos bloqueios")
    return falhas


def cumpriria(partida: dict[str, Any]) -> bool:
    """A conta do desafio, refeita à mão: bloqueou o bastante, e não perdeu.

    ⚠️ Só serve ao CONTROLE: o veredito que conta é o da régua (`cumpriu`). Uma
    partida em aberto não cumpre ("e não perca" pede o fim).
    """
    return partida["bloqueios"] >= AMEACAS and partida["resultado"] in ("venceu", "empatou")


def _jogar_o_dia(indice: int, execucoes: int) -> dict[str, Any]:
    """Gera a posição do dia e joga as 16 combinações, [execucoes] vezes cada."""
    dia = DIA_BASE + timedelta(days=indice)
    publicacao = editorial_mod.EDITORIAL_FORA_DO_AR[CO_TIPO][0]
    receita = RECEITAS_FORA_DO_AR[CO_TIPO]
    # ⛔ O tipo do dia tem de ser ESTE: marcar os outros como recentes é o botão
    # que força a escolha (o mesmo de `medir_variantes_do_editorial.medir`).
    outros = [t for t in gerador_mod.tipos_do_jogo(receita.co_jogo) if t != CO_TIPO]
    candidatos = gerador_mod.gerar_candidatos(
        dia,
        parametros=publicacao.parametros,
        quantos=1,
        tipos_recentes=outros,
        maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
        minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances or 0,
        lances_de_preparo=publicacao.nu_lances_de_preparo,
        personagens_possiveis=publicacao.co_personagens,
        receita_em_avaliacao=receita,
    )
    linha: dict[str, Any] = {"indice": indice, "dia": dia.isoformat()}
    if not candidatos:
        linha["sem_candidato"] = True
        return linha
    candidato = candidatos[0]
    bancada = gerador_mod.bancada(candidato)
    iniciais = tuple(candidato.estado_inicial.lances)
    linha["lances"] = "".join(iniciais)
    linha["personagem_do_dia"] = candidato.co_personagem

    partidas: list[dict[str, Any]] = []
    for adversario in PERSONAGENS:
        # O `julgar` da bancada, embrulhado: a régua o chama a cada lance com a
        # fita inteira, e a última fita vista é a partida jogada.
        vista: dict[str, list] = {"fita": []}

        def julgar(fita, vista=vista):
            vista["fita"] = list(fita)
            return bancada.julgar(fita)

        tentar = regua_mod.tentativa_com_motor(
            jogador=bancada.jogador,
            estado_inicial=bancada.estado_inicial,
            julgar=julgar,
            nu_semente=candidato.nu_semente,
            maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
            co_personagem_do_dia=adversario,
            solucionador=bancada.solucionador,
        )
        for quem_resolve in PERSONAGENS:
            for execucao in range(1, execucoes + 1):
                vista["fita"] = []
                cumpriu = tentar(quem_resolve, execucao)
                lances = [passo["lance"] for passo in vista["fita"]]
                partida = analisar_partida(bancada.arbitro, iniciais, lances)
                partida.update(
                    {
                        "resolve": quem_resolve,
                        "adversario": adversario,
                        "execucao": execucao,
                        "cumpriu": cumpriu,
                    }
                )
                partidas.append(partida)
    linha["partidas"] = partidas
    return linha


def medir_dia(unidade: tuple[int, int]) -> dict[str, Any]:
    """Um dia inteiro, numa thread própria que morre no fim.

    ⚠️ O motor Dart do Quatro é um por THREAD (`jogador_compartilhado`). Rodando
    o dia numa thread que termina, `liberar_de_threads_mortas` fecha o processo
    dela - sem isso cada processo do pool guardaria o seu até o fim, e um
    Ctrl+C os deixaria órfãos (memória "pool-fechado-deixa-os-processos").
    """
    indice, execucoes = unidade
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=1) as uma_thread:
        linha = uma_thread.submit(_jogar_o_dia, indice, execucoes).result()
    recursos_por_thread.liberar_de_threads_mortas()
    linha["execucoes"] = execucoes
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


# ═══════════════════════════════════════════════════════════════════════════
# O relatório
# ═══════════════════════════════════════════════════════════════════════════


def resumir(partidas: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """As taxas e as médias de um grupo de partidas (todas no denominador)."""
    n = len(partidas)
    if n == 0:
        return {"n": 0}

    def taxa(condicao) -> float:
        return sum(1 for p in partidas if condicao(p)) / n

    def media(chave: str) -> float:
        return sum(p[chave] for p in partidas) / n

    # Quantas partidas bloquearam 0, 1, 2, 3 e 4 ou mais (a última junta).
    faixas = Counter(min(p["bloqueios"], 4) for p in partidas)
    return {
        "n": n,
        "cumpriu": taxa(lambda p: p["cumpriu"]),
        "perdeu": taxa(lambda p: p["resultado"] == "perdeu"),
        # A falha da hipótese: não perdeu, e bloqueou menos que o pedido.
        "poucas": taxa(lambda p: p["resultado"] != "perdeu" and p["bloqueios"] < AMEACAS),
        "venceu": taxa(lambda p: p["resultado"] == "venceu"),
        "ameacas": media("turnos_com_ameaca"),
        "duplas": media("turnos_com_dupla"),
        "bloqueios": media("bloqueios"),
        "ignoradas": media("ignoradas"),
        "no_lugar": media("venceu_no_lugar"),
        "meios_lances": media("meios_lances"),
        "faixas": [faixas.get(k, 0) for k in range(5)],
    }


def _linha_da_tabela(rotulo: str, r: dict[str, Any]) -> str:
    """Uma linha da tabela: o rótulo e o resumo do grupo."""
    if r["n"] == 0:
        return f"  {rotulo:<14} (sem partidas)"
    faixas = "|".join(f"{v:>3}" for v in r["faixas"])
    return (
        f"  {rotulo:<14} {r['n']:>4}  {r['cumpriu']:5.2f}  {r['perdeu']:5.2f}"
        f"  {r['poucas']:5.2f}  {r['venceu']:5.2f}   {r['ameacas']:4.1f}"
        f"  {r['duplas']:4.1f}  {r['bloqueios']:4.1f}  {r['ignoradas']:4.1f}"
        f"  {r['no_lugar']:4.1f}   {r['meios_lances']:4.1f}   {faixas}"
    )


CABECALHO_DA_TABELA = (
    "  quem resolve      n  cumpr  perdeu <3 s/p  venceu  ameaç dupla  bloq  ignor"
    "  lugar  meios-l   bloqueios 0|1|2|3|4+"
)


def relatorio(linhas: Sequence[dict[str, Any]]) -> str:
    """O relatório inteiro, a partir do diário."""
    medidas = [l for l in linhas if not l.get("sem_candidato")]
    sem = len(linhas) - len(medidas)
    partidas = [p for l in medidas for p in l["partidas"]]
    execucoes = sorted({l.get("execucoes") for l in medidas})
    saida = [
        "Diagnóstico do bloquear (Quatro, T124c passo 4)",
        f'desafio: "Bloqueie {AMEACAS} ameaças do adversário e não perca" · '
        f"{len(medidas)} posições ({sem} dias sem candidato) · execuções por par: "
        f"{execucoes} · {len(partidas)} partidas",
        "",
        "⛔ CONTROLES (fora de N de N, não leia o resto):",
        f"   bloqueios do script = os do medidor do desafio: "
        f"{sum(p['bloqueios'] == p['bloqueios_do_medidor'] for p in partidas)} de {len(partidas)}",
        f"   veredito da régua = 'bloqueou {AMEACAS} e não perdeu': "
        f"{sum(p['cumpriu'] == cumpriria(p) for p in partidas)} de {len(partidas)}",
        "",
        "Colunas: cumpr = cumpriu o desafio · perdeu · <3 s/p = bloqueou menos de "
        f"{AMEACAS} SEM perder · venceu (taxas sobre n) | médias por partida: "
        "ameaç = turnos em que havia ameaça jogável do adversário · dupla = turnos "
        "com duas ou mais · bloq = bloqueios · ignor = ameaças nem tapadas nem "
        "vencidas · lugar = venceu em vez de tapar · meios-l = duração",
        "",
        "═══ NA VISÃO DA RÉGUA (quem resolve diferente do adversário do dia) ═══",
        CABECALHO_DA_TABELA,
    ]
    for quem in PERSONAGENS:
        grupo = [p for p in partidas if p["resolve"] == quem and p["adversario"] != quem]
        saida.append(_linha_da_tabela(quem, resumir(grupo)))
    for adversario in PERSONAGENS:
        saida += ["", f"═══ ADVERSÁRIO DO DIA: {adversario} ═══", CABECALHO_DA_TABELA]
        for quem in PERSONAGENS:
            grupo = [
                p for p in partidas if p["resolve"] == quem and p["adversario"] == adversario
            ]
            # O par que a régua não mede (o mascote contra ele mesmo) leva "=".
            rotulo = f"{quem} (=)" if quem == adversario else quem
            saida.append(_linha_da_tabela(rotulo, resumir(grupo)))
    return "\n".join(saida) + "\n"


def ler_diario(diario: Path) -> list[dict[str, Any]]:
    """As linhas já medidas (vazio na 1ª execução)."""
    if not diario.is_file():
        return []
    return [json.loads(l) for l in diario.read_text(encoding="utf-8").splitlines() if l]


def pendentes(feitas: Sequence[dict[str, Any]], dias: int) -> list[int]:
    """Os índices de dia que ainda não estão no diário (a identidade é o índice)."""
    vistos = {l["indice"] for l in feitas}
    return [i for i in range(dias) if i not in vistos]


def principal(argumentos: Sequence[str]) -> int:
    """Confere os controles, mede o que falta e escreve o relatório."""
    leitor = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    leitor.add_argument("--dias", type=int, default=30)
    leitor.add_argument("--execucoes", type=int, default=5)
    leitor.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    leitor.add_argument("--pasta", type=Path, default=PASTA_PADRAO)
    args = leitor.parse_args(argumentos)

    falhas = conferir_controles()
    if falhas:
        print("⛔ [controle] o instrumento não mede; nada foi jogado:")
        for falha in falhas:
            print(f"   {falha}")
        return 1
    print(f"[controle] as {len(CONTROLES)} partidas montadas à mão contam certo.")

    args.pasta.mkdir(parents=True, exist_ok=True)
    diario_caminho = args.pasta / "diario.jsonl"
    faltam = pendentes(ler_diario(diario_caminho), args.dias)
    print(
        f"{args.dias - len(faltam)} dias já no diário; {len(faltam)} a medir, em "
        f"{args.processos} processos ({len(PERSONAGENS) ** 2 * args.execucoes} "
        "partidas por dia).",
        flush=True,
    )
    inicio = time.time()
    if faltam:
        with multiprocessing.Pool(min(args.processos, len(faltam))) as pool, open(
            diario_caminho, "a", encoding="utf-8"
        ) as diario:
            unidades = [(i, args.execucoes) for i in faltam]
            for n, linha in enumerate(pool.imap_unordered(medir_dia, unidades), 1):
                # Uma linha por dia, gravada na hora: é o que torna a medição
                # retomável se a janela fechar no meio.
                diario.write(json.dumps(linha, ensure_ascii=False) + "\n")
                diario.flush()
                print(
                    f"[{n}/{len(faltam)}] {linha['dia']} {linha['segundos']} s · "
                    f"{time.time() - inicio:.0f} s no total",
                    flush=True,
                )
    texto = relatorio(ler_diario(diario_caminho))
    (args.pasta / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
