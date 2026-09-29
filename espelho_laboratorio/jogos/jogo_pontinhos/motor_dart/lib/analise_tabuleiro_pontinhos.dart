// Análises ESTRUTURAIS do tabuleiro do Jogo dos Pontinhos (lógica PURA).
//
// São funções "olho clínico" sobre o estado: dado um traço, ele FECHA caixa? ele
// ENTREGA caixa ao adversário? quais traços fecham caixa agora? Ficam aqui, num
// módulo neutro, porque são usadas em DOIS lugares:
//   • pela política de dificuldade da CPU (Fase A "gulosa": sempre capturar);
//   • pelo oráculo de reserva (heurística), para ranquear lances.
//
// Manter num só lugar evita duplicar a regra de "grau da caixa" (nº de lados
// preenchidos) em vários arquivos.
//
// ⚠️ **A ORDEM de [capturasDisponiveis] é parte do comportamento**, e não um
// detalhe: é sobre ela que a Fase A sorteia. Duas implementações que devolvessem
// as mesmas capturas em ordens diferentes escolheriam lances diferentes com a
// mesma semente - e é justamente esse tipo de divergência que levou este código
// para dentro do motor (T093).

import 'tabuleiro_pontinhos.dart';

/// Quantas caixas o traço [label] FECHARIA imediatamente (0, 1 ou 2)?
///
/// Um traço pode fechar até duas caixas de uma vez (quando as duas caixas
/// vizinhas a ele já tinham 3 lados).
int caixasQueFecharia(EstadoTabuleiroPontinhos e, String label) {
  final (r, c) = e.coordenadaDoLabel(label);
  // As caixas vizinhas a uma aresta dependem da sua orientação:
  //   • H_r_c (r par) → caixa de cima (r-1) e de baixo (r+1), mesma coluna;
  //   • V_r_c (r ímpar) → caixa da esquerda (c-1) e da direita (c+1), mesma linha.
  final vizinhas = r.isEven
      ? [(r - 1, c), (r + 1, c)]
      : [(r, c - 1), (r, c + 1)];
  var n = 0;
  for (final (br, bc) in vizinhas) {
    if (_ladosDaCaixa(e, br, bc) == 3) n++; // já tem 3 → este 4º fecha
  }
  return n;
}

/// Colocar [label] deixaria alguma caixa vizinha (ainda aberta) com 3 lados -
/// ou seja, ENTREGARIA uma captura de graça ao adversário?
bool criaCaixaDeTres(EstadoTabuleiroPontinhos e, String label) {
  final (r, c) = e.coordenadaDoLabel(label);
  final vizinhas = r.isEven
      ? [(r - 1, c), (r + 1, c)]
      : [(r, c - 1), (r, c + 1)];
  for (final (br, bc) in vizinhas) {
    // Se a caixa tinha 2 lados, este traço a leva a 3 (perigoso).
    if (_ladosDaCaixa(e, br, bc) == 2) return true;
  }
  return false;
}

/// Lista, em ordem canônica, todos os traços disponíveis que FECHAM ao menos
/// uma caixa agora. É a base da "Fase A" (captura gulosa) da CPU.
List<String> capturasDisponiveis(EstadoTabuleiroPontinhos e) {
  return [
    for (final label in e.tracosDisponiveis())
      if (caixasQueFecharia(e, label) > 0) label,
  ];
}

// Conta quantos dos 4 lados da caixa em (r, c) já estão ocupados. Posições fora
// da matriz (borda) ou que não são interior de caixa retornam -1 (não é caixa).
int _ladosDaCaixa(EstadoTabuleiroPontinhos e, int r, int c) {
  if (r <= 0 || r >= e.altura - 1 || c <= 0 || c >= e.largura - 1) return -1;
  if (r.isEven || c.isEven) return -1;
  var n = 0;
  if (e.matriz[r - 1][c] != 0) n++;
  if (e.matriz[r + 1][c] != 0) n++;
  if (e.matriz[r][c - 1] != 0) n++;
  if (e.matriz[r][c + 1] != 0) n++;
  return n;
}
