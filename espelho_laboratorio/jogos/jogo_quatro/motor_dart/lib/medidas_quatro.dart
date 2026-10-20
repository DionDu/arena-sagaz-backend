// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// As MEDIDAS de uma partida (spec 010, T031; RF-QTR-142, RF-QTR-153,
// RF-QTR-153a, R-18, R-19): números lidos do tabuleiro, que outros transformam
// em XP, em feito e em conquista. ⚠️ Aqui não há XP nenhum: medida é medida,
// e quem converte é quem agrupa (`lib/core/feitos/` no app, o job no servidor).
//
// Moram no motor porque são REGRA DE CONTAGEM: o app (o XP e os feitos) e o
// servidor (as medidas de saída do desafio) contam do mesmo jeito só se lerem
// a mesma função. Uma segunda escrita, em outro lugar, é a forma de todos os
// episódios de divergência entre o aparelho e o servidor.
//
// Duas famílias:
//
// 1. **As peças encostadas** ([pecasEncostadas]): quantas peças de uma cor têm
//    pelo menos uma vizinha da MESMA cor, nas oito direções. Cada peça conta
//    uma vez, por mais vizinhas que tenha. É a qualidade do XP do jogo.
// 2. **As medidas do fim** ([medirFimDePartidaQuatro]): como a partida
//    terminou (vertical, diagonal, quantas peças o vencedor usou, quantas
//    linhas o último lance fechou, a maior linha, quantas casas sobraram).
//    São a matéria dos feitos próprios (Torre, Escada Torta, Relâmpago, Golpe
//    Duplo, Linha de Cinco) e da conquista que a escada decide.
// 3. **As medidas da fita** ([medirFitaQuatro], spec 010, T106): o que a
//    PESSOA fez num desafio, depois da posição publicada (os lances dela, os
//    da coluna do meio, as ameaças que ela bloqueou, e se perdeu). São o
//    critério de três tipos do Desafio do Dia, e o servidor as conta com o
//    mesmo resultado, conferido pelos vetores de paridade.

import 'ameacas_quatro.dart';
import 'heuristica_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// Quantas peças da [cor] (`+1` = Jogador 1, `-1` = Jogador 2) estão
/// encostadas em outra peça da mesma cor, em qualquer das oito direções
/// (lados, cima e baixo, e as quatro diagonais).
///
/// Cada peça conta UMA vez (RF-QTR-153a): a peça com três vizinhas vale 1,
/// e não 3. Por isso o máximo é o número de peças da cor (21 por cor no
/// 7 × 6, quando o tabuleiro enche).
///
/// Como a conta funciona, com bits: para cada uma das quatro direções, com o
/// deslocamento `d` (quantos bits separam uma casa da vizinha nela),
/// `pecas >> d` traz para o lugar de cada casa o bit da vizinha de um lado, e
/// `pecas << d` o da vizinha do outro. O "ou" de tudo isso marca as casas que
/// têm alguma vizinha da cor; o "e" com as peças fica só com as peças
/// encostadas. A linha de sentinela (sempre vazia) no topo de cada coluna é o
/// que impede uma vizinha de "dar a volta" de uma coluna para a outra.
int pecasEncostadas(PosicaoQuatro posicao, int cor) {
  if (cor != 1 && cor != -1) {
    throw ArgumentError.value(cor, 'cor', 'só +1 (J1) ou -1 (J2)');
  }
  final pecas = cor == 1 ? posicao.pecasDoJ1 : posicao.pecasDoJ2;
  final altura = posicao.dimensoes.altura;
  var comVizinha = 0;
  // Vertical (1 bit), horizontal (uma coluna inteira, `altura + 1` bits) e as
  // duas diagonais (`altura + 2` e `altura`), cada uma nos dois sentidos.
  for (final d in [1, altura + 1, altura + 2, altura]) {
    comVizinha |= (pecas >> d) | (pecas << d);
  }
  // O `& pecas` também descarta o que o `<<` empurrou para fora do tabuleiro.
  return contarBitsQuatro(pecas & comVizinha);
}

/// Em que direção corre uma linha vencedora.
enum DirecaoDaLinhaQuatro {
  /// Peças empilhadas na mesma coluna (o feito "Torre").
  vertical,

  /// Peças lado a lado na mesma linha do tabuleiro.
  horizontal,

  /// Peças numa diagonal, subindo ou descendo (o feito "Escada Torta").
  diagonal,
}

/// A direção de [linha], lida das casas dela: mesma coluna é vertical, mesma
/// linha é horizontal, e o resto (coluna e linha mudando juntas) é diagonal.
DirecaoDaLinhaQuatro direcaoDaLinhaQuatro(LinhaQuatro linha) {
  final primeira = linha.casas.first;
  final segunda = linha.casas[1];
  if (primeira.coluna == segunda.coluna) return DirecaoDaLinhaQuatro.vertical;
  if (primeira.linha == segunda.linha) return DirecaoDaLinhaQuatro.horizontal;
  return DirecaoDaLinhaQuatro.diagonal;
}

/// As medidas de uma partida TERMINADA (vitória ou empate).
///
/// Tudo é contado do tabuleiro final e do [DesfechoQuatro]; nada aqui sabe
/// quem é a pessoa e quem é a CPU. Quem lê decide de que lado está.
final class MedidasDoFimQuatro {
  /// `+1`, `-1`, ou `null` no empate.
  final int? vencedor;

  /// Alguma linha vencedora é vertical (o feito "Torre").
  final bool vitoriaVertical;

  /// Alguma linha vencedora é diagonal (o feito "Escada Torta").
  final bool vitoriaDiagonal;

  /// Quantas peças o vencedor pôs no tabuleiro (o feito "Relâmpago" é vencer
  /// com 4). Zero no empate.
  final int pecasDoVencedor;

  /// Quantas linhas o último lance fechou (o feito "Golpe Duplo" é 2 ou
  /// mais). Zero no empate.
  ///
  /// Numa partida jogada, toda linha vencedora passa pela última peça (a
  /// partida acaba na primeira linha formada), e duas linhas na MESMA
  /// direção que passam pela mesma peça já são uma linha só, mais comprida.
  /// Então "duas linhas" aqui é sempre "duas direções diferentes".
  final int linhasNoLanceFinal;

  /// O tamanho da maior linha vencedora (o feito "Linha de Cinco" é 5 ou
  /// mais). Zero no empate.
  final int maiorLinha;

  /// Quantas casas ficaram vazias no fim (a conquista "Na Última Casa" é
  /// vencer com 0 ou 1). Zero no empate, que é o tabuleiro cheio.
  final int casasRestantes;

  /// As peças encostadas de cada cor ([pecasEncostadas]).
  final int pecasEncostadasDoJ1;
  final int pecasEncostadasDoJ2;

  /// Cria as medidas (quem monta é [medirFimDePartidaQuatro]).
  const MedidasDoFimQuatro({
    required this.vencedor,
    required this.vitoriaVertical,
    required this.vitoriaDiagonal,
    required this.pecasDoVencedor,
    required this.linhasNoLanceFinal,
    required this.maiorLinha,
    required this.casasRestantes,
    required this.pecasEncostadasDoJ1,
    required this.pecasEncostadasDoJ2,
  });

  /// As peças encostadas de [cor] (`+1` ou `-1`): atalho para quem tem a cor
  /// da pessoa na mão.
  int pecasEncostadasDe(int cor) =>
      cor == 1 ? pecasEncostadasDoJ1 : pecasEncostadasDoJ2;

  @override
  String toString() => 'MedidasDoFimQuatro(vencedor=$vencedor, '
      'vertical=$vitoriaVertical, diagonal=$vitoriaDiagonal, '
      'pecasDoVencedor=$pecasDoVencedor, linhas=$linhasNoLanceFinal, '
      'maior=$maiorLinha, restantes=$casasRestantes, '
      'encostadas=$pecasEncostadasDoJ1/$pecasEncostadasDoJ2)';
}

/// As medidas da partida que terminou em [posicao], jogada pelas [regras].
///
/// Quem diz se terminou, e como, é a própria modalidade (`regras.desfecho`):
/// assim ninguém mede com um desfecho de outra posição. Partida que não
/// terminou é recusada com `ArgumentError`, porque medir no meio daria
/// números de uma partida que ainda pode mudar.
MedidasDoFimQuatro medirFimDePartidaQuatro(
    RegrasDaModalidadeQuatro regras, PosicaoQuatro posicao) {
  final desfecho = regras.desfecho(posicao);
  if (desfecho == null) {
    throw ArgumentError('a partida ainda não terminou:\n$posicao');
  }
  final dimensoes = posicao.dimensoes;
  final ocupadas = contarBitsQuatro(posicao.mascara);
  final vencedor = desfecho.vencedor;
  final direcoes = desfecho.linhas.map(direcaoDaLinhaQuatro).toSet();
  return MedidasDoFimQuatro(
    vencedor: vencedor,
    vitoriaVertical: direcoes.contains(DirecaoDaLinhaQuatro.vertical),
    vitoriaDiagonal: direcoes.contains(DirecaoDaLinhaQuatro.diagonal),
    pecasDoVencedor: switch (vencedor) {
      null => 0,
      1 => contarBitsQuatro(posicao.pecasDoJ1),
      _ => contarBitsQuatro(posicao.pecasDoJ2),
    },
    linhasNoLanceFinal: desfecho.linhas.length,
    // `fold` percorre as linhas guardando o maior tamanho visto (começa em 0,
    // que é o que fica no empate, sem linha nenhuma).
    maiorLinha: desfecho.linhas
        .fold(0, (maior, l) => l.casas.length > maior ? l.casas.length : maior),
    // No empate o tabuleiro está cheio, e a conta dá 0 sozinha.
    casasRestantes: dimensoes.casas - ocupadas,
    pecasEncostadasDoJ1: pecasEncostadas(posicao, 1),
    pecasEncostadasDoJ2: pecasEncostadas(posicao, -1),
  );
}

// ── As medidas da fita (o desafio) ───────────────────────────────────────────

/// O que a pessoa fez num desafio, contado na FITA: os lances jogados depois
/// da posição publicada, dos dois lados (`contracts/desafio-quatro.md` §4).
///
/// "A pessoa" é quem tem a vez na posição publicada: é ela quem resolve.
final class MedidasDaFitaQuatro {
  /// Quem resolve: `+1` (Jogador 1) ou `-1` (Jogador 2).
  final int pessoa;

  /// Quantos lances a pessoa fez na fita (o critério do `quatro_vencer_em_n`).
  final int lancesDoJogador;

  /// Quantos lances da pessoa caíram na coluna do meio. Só existe coluna do
  /// meio em largura ÍMPAR; na par a conta é sempre 0 (o `quatro_sem_o_meio`
  /// só é gerado em largura ímpar).
  final int lancesNaColunaCentral;

  /// Quantos lances da pessoa ocuparam uma casa onde o adversário venceria
  /// no lance seguinte: uma ameaça dele jogável agora (a que o Radar mostra).
  /// Conta LANCES: um lance que ocupa a casa conta 1, mesmo que o adversário
  /// tivesse outra ameaça em outro lugar.
  final int ameacasBloqueadas;

  /// O predicado `quatro_perdeu`: a partida terminou com vitória do
  /// adversário da pessoa. Falso enquanto a partida não terminou e no empate.
  final bool perdeu;

  /// Cria as medidas.
  const MedidasDaFitaQuatro({
    required this.pessoa,
    required this.lancesDoJogador,
    required this.lancesNaColunaCentral,
    required this.ameacasBloqueadas,
    required this.perdeu,
  });
}

/// A coluna do meio da [largura], ou `null` quando ela é par (sem meio).
int? colunaCentralQuatro(int largura) => largura.isOdd ? (largura + 1) ~/ 2 : null;

/// Mede a [fita] de um desafio que partiu de [lancesIniciais] (as duas na
/// notação, `s4s4s3`), pelas [regras].
///
/// ⚠️ A fita conta a partir da posição publicada, e nunca do tabuleiro vazio:
/// os lances iniciais são de ninguém (`co_lances_iniciais`). Lança
/// `LanceIlegalQuatro` (ou `FormatException`) se a fita não se joga.
MedidasDaFitaQuatro medirFitaQuatro(
    RegrasDaModalidadeQuatro regras, String lancesIniciais, String fita) {
  var posicao = PosicaoQuatro.deLances(regras, lancesIniciais);
  final pessoa = posicao.jogadorDaVez;
  final dimensoes = regras.dimensoes;
  final meio = colunaCentralQuatro(dimensoes.largura);
  var lancesDoJogador = 0;
  var lancesNaColunaCentral = 0;
  var ameacasBloqueadas = 0;
  for (final lance in lerSequenciaQuatro(fita, regras.tiposDeLance)) {
    if (regras.desfecho(posicao) != null) {
      throw LanceIlegalQuatro('lance $lance depois do fim da partida');
    }
    final antes = posicao;
    posicao = regras.aplicar(posicao, lance);
    if (antes.jogadorDaVez != pessoa) continue;
    lancesDoJogador++;
    if (lance.coluna == meio) lancesNaColunaCentral++;
    // As casas de ameaça do adversário ANTES do lance (onde uma peça dele
    // formaria linha) e as que o lance ocupou (o bit novo da máscara; um lance
    // que não ocupa casa nova não bloqueia por ocupação). Não é preciso
    // filtrar as jogáveis: a casa que um lance ocupa era jogável por definição.
    final doAdversario = pessoa == 1 ? antes.pecasDoJ2 : antes.pecasDoJ1;
    final ameacasDoAdversario =
        casasDeAmeacaQuatro(dimensoes, doAdversario, antes.mascara);
    final ocupadas = posicao.mascara & ~antes.mascara;
    if (ameacasDoAdversario & ocupadas != 0) ameacasBloqueadas++;
  }
  final desfecho = regras.desfecho(posicao);
  return MedidasDaFitaQuatro(
    pessoa: pessoa,
    lancesDoJogador: lancesDoJogador,
    lancesNaColunaCentral: lancesNaColunaCentral,
    ameacasBloqueadas: ameacasBloqueadas,
    perdeu: desfecho != null && desfecho.vencedor == -pessoa,
  );
}
