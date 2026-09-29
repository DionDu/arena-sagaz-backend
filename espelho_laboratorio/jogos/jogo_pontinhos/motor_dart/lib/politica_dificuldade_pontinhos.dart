// A POLÍTICA DE DIFICULDADE do Pontinhos: o que se faz com os números da rede.
//
// ── ⚠️ ESTE ARQUIVO É O CORAÇÃO DA T093 (28/09/2026) ────────────────────────
//
// A CNN sozinha **não é o nível**: ela é uma só, é determinística, e dada a
// mesma matriz devolve sempre a mesma distribuição. O que separa Cacau, Pita,
// Tex e Magno é o que está aqui - com que frequência a CPU erra de propósito, e
// se ela fecha caixa de graça sem pensar.
//
// Até 28/09/2026 esta política existia **duas vezes**: em Dart, no aplicativo
// (`logica/oraculo.dart`), e em Python, no servidor (`motores/pontinhos/
// politica.py`). E as duas divergiam em dois pontos que ninguém havia decidido:
//
//   1. **O SORTEADOR.** O Python usa o Mersenne Twister e o Dart, um xorshift.
//      ⛔ **Mesma semente, sequências diferentes** - então nem a semente
//      publicada do desafio fazia os dois jogarem a mesma partida.
//   2. **A ORDEM das listas sorteadas.** O `topo` e o `resto` saem do
//      ranqueamento, e o Python o ordenava com desempate por rótulo
//      (`key=(-p, rotulo)`) enquanto o aplicativo ordena só pela nota. Com
//      empates - e há empates, é para isso que o arredondamento existe - os dois
//      sorteavam sobre listas em ordens diferentes.
//
// ⛔ **A correção não é ajustar um lado: é parar de ter dois.** Desde a T093 o
// servidor decide com ESTE arquivo, compilado, e a pergunta *"será que alguém
// mudou um lado só?"* deixa de existir.
//
// ⚠️ **E quem cedeu foi o servidor**, como manda a decisão do dono de 26/09/2026
// (`docs/DECISOES-do-dono.md` §8zj item 5): o comportamento que ficou é o do
// aplicativo, porque é ele que está no aparelho das pessoas. Em particular, a
// ordenação continua **sem** desempate por rótulo - acrescentá-lo "melhoraria" o
// servidor e mudaria o que o aparelho joga hoje.

import 'dart:math';

import 'analise_tabuleiro_pontinhos.dart';
import 'dificuldade_pontinhos.dart';
import 'tabuleiro_pontinhos.dart';

/// Um traço candidato com a sua pontuação (quanto MAIOR, melhor) na visão do
/// oráculo. Para a CNN, [score] é a probabilidade do lance; para a heurística de
/// reserva do aplicativo, é um valor sintético por categoria.
///
/// Guardamos o score (não só a ordem) porque a política de dificuldade precisa
/// dele: para saber o que é "o topo" (e o que é erro), ela compara os scores -
/// lances praticamente idênticos ao melhor contam como topo. Ver [escolherLance].
class LanceRanqueado {
  const LanceRanqueado(this.label, this.score);

  /// Rótulo do traço (ex.: "H_2_1").
  final String label;

  /// Pontuação do lance (maior = melhor).
  final double score;
}

/// Valores canônicos de `co_acao` (COMO a CPU decidiu o lance), espelhando o
/// `specs/006-conta-nuvem/data-model.md`. São gravados na coluna
/// `jogo_pontinhos_tb002_jogada.co_acao` (telemetria da IA - FR-020/021).
abstract final class AcaoCpu {
  /// Fechou uma caixa de graça na fase gulosa (Cacau/Pita/Tex, Fase A). Não
  /// consulta a CNN para ESTE lance - é instinto.
  static const capturaGulosa = 'captura_gulosa';

  /// **Erro de propósito**: a CPU sorteou dentro do `epsilon` e jogou um traço
  /// aleatório FORA do topo da CNN (Fase B tática, Cacau/Pita/Tex).
  /// É o código que marca a "burrice controlada" que define a dificuldade.
  static const cnnEpsilonAleatorio = 'cnn_epsilon_aleatorio';

  /// Argmax da CNN com um único melhor lance (sem empate no topo). O Magno cai
  /// sempre aqui; os outros, quando o sorteio do `epsilon` NÃO deu erro.
  static const cnnArgmaxAbsoluto = 'cnn_argmax_absoluto';

  /// Argmax da CNN com empate no topo (após arredondar), sorteado entre os
  /// empatados.
  static const cnnArgmaxDesempatado = 'cnn_argmax_desempatado';

  /// **Abertura sorteada**: primeiro lance da partida, quando é a CPU quem abre.
  /// Só o Magno usa (os outros já variam pelo `epsilon`). Ver [escolherLance].
  static const cnnAberturaAleatoria = 'cnn_abertura_aleatoria';

  /// Decisão veio do oráculo de RESERVA (heurística, sem rede neural).
  static const heuristicaGulosa = 'heuristica_gulosa';

  /// APOSENTADO (2026-07-13): sorteio no "núcleo top-p", a política anterior à
  /// ε-greedy. Nenhum lance NOVO usa este código, mas ele continua existindo na
  /// dimensão do banco por causa das partidas já gravadas - não reciclar o nome.
  static const cnnNucleoTopP = 'cnn_nucleo_top_p';
}

/// A decisão da política de dificuldade: o traço escolhido + COMO foi escolhido
/// (`co_acao`). A `co_situacao` NÃO vive aqui de propósito: ela é derivada do
/// RESULTADO do lance (fechou caixa?) na hora de gravar o log - assim
/// [escolherLance] não precisa reinspecionar o tabuleiro (e continua testável
/// com rankings sintéticos).
class DecisaoLance {
  const DecisaoLance({required this.label, required this.coAcao});

  /// Rótulo do traço a jogar (ex.: `H_2_1`).
  final String label;

  /// COMO decidiu - um dos valores de [AcaoCpu].
  final String coAcao;
}

// Casas decimais usadas para arredondar os scores ao decidir o "empate no topo"
// (vale para TODOS os personagens: define o que conta como "o melhor lance").
// Calibrado por análise da CNN (tools/analise_empates_cnn_pontinhos.py): 3 casas
// reproduzem ~92% dos empates de uma tolerância relativa de 0,5%.
const int casasDoDesempate = 3;

/// Transforma a saída CRUA da rede no ranqueamento sobre o qual a política
/// decide: só os traços disponíveis, renormalizados para somar 1, do melhor
/// para o pior.
///
/// ⚠️ **Esta conta também existia dos dois lados** - em `oraculo_cnn_io.dart` e
/// em `MotorPontinhos.ranquear`, no Python -, e é ela que produz a ordem sobre a
/// qual se sorteia. Por isso subiu para o motor junto com a política: ordenar
/// diferente escolhe lance diferente, mesmo com a rede concordando número a
/// número.
///
/// [softmax] é o vetor cru do modelo (31 valores no tabuleiro pequeno), na ordem
/// do `mapeamento_*.json`; [indiceDoLabel] traduz rótulo → índice do neurônio.
/// Rótulo sem índice, ou índice além do vetor, vale zero - é o que o aplicativo
/// faz, e é defesa contra um mapeamento de outro tamanho de tabuleiro.
List<LanceRanqueado> ranquearDaSoftmax({
  required EstadoTabuleiroPontinhos estado,
  required List<double> softmax,
  required Map<String, int> indiceDoLabel,
}) {
  final disponiveis = estado.tracosDisponiveis();
  if (disponiveis.isEmpty) return const <LanceRanqueado>[];

  double probDe(String label) {
    final i = indiceDoLabel[label];
    return (i == null || i >= softmax.length) ? 0.0 : softmax[i];
  }

  // RENORMALIZA as probabilidades só sobre os lances disponíveis (para que somem
  // 1) - é a distribuição sobre a qual a política de dificuldade decide.
  final somaDisp = disponiveis.fold<double>(0, (acc, l) => acc + probDe(l));
  // Soma zero significa que a rede não pôs peso em nenhum traço livre.
  // Distribuir igualmente mantém a soma em 1; devolver zeros faria a política
  // sortear sobre uma distribuição vazia.
  double normDe(String label) =>
      somaDisp > 0 ? probDe(label) / somaDisp : 1.0 / disponiveis.length;

  return [
    for (final l in disponiveis) LanceRanqueado(l, normDe(l)),
  ]..sort((a, b) => b.score.compareTo(a.score));
}

/// Aplica a política de [dificuldade] sobre um [ranking] (com scores) e devolve
/// o lance escolhido. Usa [rng] para a aleatoriedade e [estado] para detectar
/// capturas (Fase A). Devolve `null` se não há jogada possível.
///
/// A política é **ε-greedy** (ver a doc de [Dificuldade], que é a fonte da
/// verdade sobre os números e o porquê), com uma exceção antes dela:
///
///   FASE 0 (abertura) — só o Magno, e só quando ELE abre a partida:
///     joga um traço sorteado uniformemente. Ver a nota longa no corpo da função.
///
///   FASE A (gulosa) — só para quem tem `usaCapturaGulosa` (Cacau/Pita/Tex):
///     se dá para fechar alguma caixa AGORA, fecha, sem consultar a CNN. Capturar
///     caixa de graça é instinto, não habilidade. Como fechar caixa dá turno extra,
///     o laço da tela completa a cadeia inteira sozinho.
///     O Magno NÃO passa por aqui: ele decide tudo pela rede, e por isso é o único
///     capaz de sacrificar as 2 últimas caixas de uma cadeia (a dupla-cruz).
///
///   FASE B (tática) — todos:
///     sorteia um número em [0,1). Se cair abaixo do `epsilon`, joga um traço
///     ALEATÓRIO fora do topo (o "erro de propósito"); senão, joga o melhor lance
///     da CNN — desempatando por sorteio quando vários empatam no topo (scores
///     iguais ao arredondar a [casasDoDesempate] casas).
///     Como o Magno tem `epsilon == 0`, a fase B degenera no argmax puro para ele.
///
/// [temCnn] diz se o [ranking] veio de uma CNN (define se `co_acao` é `cnn_*`
/// ou `heuristica_gulosa`).
DecisaoLance? escolherLance(
  EstadoTabuleiroPontinhos estado,
  List<LanceRanqueado> ranking,
  Dificuldade dificuldade,
  Random rng, {
  required bool temCnn,
}) {
  if (ranking.isEmpty) return null;

  // ----- FASE 0 (abertura): o Magno abrindo a partida sorteia o 1º traço -----
  //
  // POR QUE existe. Num tabuleiro virgem a CNN é determinística: dada a mesma
  // entrada (matriz vazia), ela devolve sempre a mesma softmax, e o argmax cai
  // sempre no mesmo traço. Como o Magno tem `epsilon == 0`, ele abria TODAS as
  // partidas com a mesma aresta — repetitivo e previsível para quem joga.
  //
  // POR QUE é seguro. Na abertura, os 31 traços são equivalentes por simetria
  // (o tabuleiro vazio é simétrico), então nenhum lance é melhor que o outro:
  // sortear não enfraquece o Magno. Além disso, o encoding NÃO é canonicalizado
  // (não há rotação/espelhamento antes da inferência — ver
  // `encoding_cnn_pontinhos.dart`), logo o traço sorteado é diretamente jogável,
  // sem conversão de coordenadas.
  //
  // ESCOPO. Só o Magno, e SÓ quando é ele quem abre. Se o oponente abriu, no
  // turno do Magno `ultimoTraco` já não é nulo e ele segue CNN + argmax, como
  // sempre. Os outros personagens não passam por aqui porque o `epsilon` deles
  // (0.80/0.50/0.14) já dá variedade na abertura.
  //
  // `estado.ultimoTraco == null` é o sinal exato de "ninguém jogou ainda". O
  // sorteio usa o próprio `ranking`, que JÁ É a lista de lances legais (o
  // oráculo só ranqueia traços disponíveis) — assim a função continua testável
  // com rankings sintéticos.
  //
  // ⚠️ E ele sorteia sobre o `ranking`, que está **ordenado pela nota** - e não
  // sobre a ordem canônica do tabuleiro. É indiferente para a força (na abertura
  // os traços são equivalentes), mas ⛔ é indiferente para QUAL traço sai: era
  // uma das duas divergências com o servidor, que sorteava na ordem canônica.
  if (dificuldade == Dificuldade.sagaz && estado.ultimoTraco == null) {
    final label = ranking[rng.nextInt(ranking.length)].label;
    return DecisaoLance(
      label: label,
      // Sem CNN (oráculo de reserva) a decisão não é "da rede": mantém o código
      // heurístico, para a telemetria não sugerir que houve inferência.
      coAcao: temCnn ? AcaoCpu.cnnAberturaAleatoria : AcaoCpu.heuristicaGulosa,
    );
  }

  // ----- FASE A (gulosa): fecha caixa de graça sem pensar -----
  if (dificuldade.usaCapturaGulosa) {
    final capturas = capturasDisponiveis(estado);
    if (capturas.isNotEmpty) {
      final label = capturas[rng.nextInt(capturas.length)];
      // Não olhou a CNN para ESTE lance ⇒ sempre `captura_gulosa`, mesmo com CNN.
      return DecisaoLance(label: label, coAcao: AcaoCpu.capturaGulosa);
    }
  }

  // ----- FASE B (tática): ε-greedy sobre o ranking -----
  // Separa o "topo" (o melhor lance + os que empatam com ele) do "resto".
  final (topo: topo, resto: resto) = separarTopo(ranking);

  // `nextDouble()` devolve um número em [0,1). Cair abaixo do epsilon = errar de
  // propósito. Com epsilon 0 (Magno) a condição é sempre falsa; com 0.80 (Cacau),
  // acontece em ~80% das jogadas táticas.
  final vaiErrar = rng.nextDouble() < dificuldade.epsilon;

  // Se TODOS os lances empatam no topo, não existe "fora do topo" para errar —
  // qualquer escolha é ótima. Aí o ε não tem o que fazer e caímos no topo.
  if (vaiErrar && resto.isNotEmpty) {
    final label = resto[rng.nextInt(resto.length)].label;
    return DecisaoLance(
      label: label,
      coAcao: temCnn ? AcaoCpu.cnnEpsilonAleatorio : AcaoCpu.heuristicaGulosa,
    );
  }

  // Acertou (ou não tinha como errar): joga o melhor lance.
  final label = topo[rng.nextInt(topo.length)].label;
  final coAcao = temCnn
      ? (topo.length > 1
          ? AcaoCpu.cnnArgmaxDesempatado
          : AcaoCpu.cnnArgmaxAbsoluto)
      : AcaoCpu.heuristicaGulosa;
  return DecisaoLance(label: label, coAcao: coAcao);
}

/// Parte o [ranking] em ("topo", "resto"): o topo são o melhor lance e todos os
/// que empatam com ele (scores iguais ao arredondar a [casasDoDesempate]
/// casas); o resto é todo o restante. O topo NUNCA é vazio.
///
/// O arredondamento evita tratar como "pior" um lance que a CNN considera
/// praticamente idêntico ao melhor (ex.: 0,4001 × 0,4004) - sem ele, a CPU
/// "erraria" escolhendo um lance tão bom quanto o argmax, o que não é erro nenhum.
///
/// O tipo de retorno é um **record** (`(topo: ..., resto: ...)`), a forma do Dart
/// de devolver mais de um valor sem criar uma classe só para isso.
({List<LanceRanqueado> topo, List<LanceRanqueado> resto}) separarTopo(
  List<LanceRanqueado> ranking,
) {
  // pow(10, 3) = 1000. Arredondar a 3 casas = round(score*1000)/1000.
  final fator = pow(10, casasDoDesempate).toDouble();
  double arred(double s) => (s * fator).roundToDouble() / fator;

  final maxArred = ranking.map((l) => arred(l.score)).reduce(max);

  final topo = <LanceRanqueado>[];
  final resto = <LanceRanqueado>[];
  for (final l in ranking) {
    (arred(l.score) == maxArred ? topo : resto).add(l);
  }
  return (topo: topo, resto: resto);
}
