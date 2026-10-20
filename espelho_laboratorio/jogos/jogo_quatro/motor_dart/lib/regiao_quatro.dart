// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A REGIÃO de uma coluna (spec 010, T032; RF-QTR-132, R-17): esquerda, meio
// ou direita. É o 1º passo da dica do Desafio do Dia ("a jogada boa está no
// meio"), antes de a dica mostrar a coluna.
//
// Mora no motor, e não na tela, porque é regra do tabuleiro: o servidor e o
// app têm de concordar sobre onde fica o "meio". E sai da LARGURA, e não de
// uma tabela escrita à mão, para valer na sonda dos testes (6 colunas) e numa
// variante de tabuleiro maior sem mudar uma linha.
//
// A divisão: cada lado fica com `largura ÷ 3` colunas (a divisão inteira, que
// joga fora o resto), e o meio fica com o que sobra. O resto vai sempre para o
// meio, então as duas pontas têm sempre o mesmo tamanho:
//
//   largura 7: 1-2 · 3-5 · 6-7   (2 · 3 · 2, a decisão do dono, spec ponto 7)
//   largura 6: 1-2 · 3-4 · 5-6   (2 · 2 · 2)
//   largura 8: 1-2 · 3-6 · 7-8   (2 · 4 · 2)
//   largura 9: 1-3 · 4-6 · 7-9   (3 · 3 · 3)

import 'regras_da_modalidade_quatro.dart';

/// As três regiões do tabuleiro, da esquerda para a direita.
enum RegiaoQuatro {
  /// As colunas da ponta esquerda.
  esquerda,

  /// As colunas do meio.
  meio,

  /// As colunas da ponta direita.
  direita,
}

/// A região da [coluna] (1-based) no tabuleiro das [regras].
///
/// Coluna fora do tabuleiro é recusada com `ArgumentError`: uma dica que
/// apontasse para uma coluna que não existe é defeito de quem chamou, e não
/// um caso a esconder.
RegiaoQuatro regiaoDaColuna(RegrasDaModalidadeQuatro regras, int coluna) {
  final largura = regras.dimensoes.largura;
  if (coluna < 1 || coluna > largura) {
    throw ArgumentError.value(
        coluna, 'coluna', 'fora do tabuleiro de $largura colunas');
  }
  // `~/` é a divisão inteira do Dart (7 ~/ 3 = 2).
  final lado = largura ~/ 3;
  if (coluna <= lado) return RegiaoQuatro.esquerda;
  if (coluna > largura - lado) return RegiaoQuatro.direita;
  return RegiaoQuatro.meio;
}
