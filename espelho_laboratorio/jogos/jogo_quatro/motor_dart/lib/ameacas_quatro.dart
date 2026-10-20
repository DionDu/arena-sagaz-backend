// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// O conceito de "ameaça" (a casa vazia que completaria a linha) é o da
// literatura pública do jogo (Allis, 1988).
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// As AMEAÇAS de uma posição: as casas vazias onde uma peça a mais de alguém
// completa uma linha de `alinhar`. Servem a dois clientes (spec 010, T029):
//
// - a heurística da busca (T030), que pesa as ameaças de cada lado quando a
//   visão acaba antes do fim da partida;
// - o poder Radar (fase 3, RF-QTR-131), que mostra essas casas na tela.
//
// Uma ameaça é "jogável agora" quando a casa é a primeira livre da coluna (a
// próxima peça solta ali cai nela), e "no ar" quando ainda há casas vazias
// embaixo dela. A ameaça no ar é a que decide os finais: quem tem a ameaça na
// linha certa (ver a paridade em `heuristica_quatro.dart`) costuma ganhar
// quando as colunas enchem.
//
// Só a GEOMETRIA entra aqui (as dimensões e os bits): a conta vale para
// qualquer modalidade em que as peças fiquem empilhadas a partir do fundo,
// inclusive a sonda dos testes, que tira peças por baixo.

import 'modalidade_gravidade_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// Uma casa onde alguém completa a linha com uma peça a mais.
final class AmeacaQuatro {
  /// A casa (coluna e linha 1-based, linha 1 = a de baixo).
  final CasaQuatro casa;

  /// O Jogador 1 (azul) completa a linha nesta casa.
  final bool doJ1;

  /// O Jogador 2 (vermelho) completa a linha nesta casa.
  final bool doJ2;

  /// A casa é a primeira livre da coluna: a próxima peça solta ali cai nela.
  /// `false` = "no ar" (há casa vazia embaixo).
  final bool jogavelAgora;

  /// Cria a ameaça. Pelo menos um dos dois jogadores completa a linha nela.
  const AmeacaQuatro({
    required this.casa,
    required this.doJ1,
    required this.doJ2,
    required this.jogavelAgora,
  });

  /// Os dois jogadores completam uma linha nesta casa (a casa é disputada).
  bool get deAmbos => doJ1 && doJ2;

  @override
  bool operator ==(Object other) =>
      other is AmeacaQuatro &&
      other.casa == casa &&
      other.doJ1 == doJ1 &&
      other.doJ2 == doJ2 &&
      other.jogavelAgora == jogavelAgora;

  @override
  int get hashCode => Object.hash(casa, doJ1, doJ2, jogavelAgora);

  @override
  String toString() {
    final dono = deAmbos ? 'ambos' : (doJ1 ? 'J1' : 'J2');
    return 'Ameaca$casa $dono ${jogavelAgora ? 'jogável' : 'no ar'}';
  }
}

/// As ameaças de [posicao], na ordem das casas: coluna 1 de baixo para cima,
/// depois a coluna 2, e assim por diante.
///
/// Uma casa aparece UMA vez, mesmo que complete mais de uma linha, ou linhas
/// dos dois jogadores (aí [AmeacaQuatro.deAmbos]).
///
/// Recebe as [regras] (e não só as dimensões) para ter a mesma assinatura dos
/// outros cálculos do motor; só as dimensões delas são usadas.
List<AmeacaQuatro> ameacas(
    RegrasDaModalidadeQuatro regras, PosicaoQuatro posicao) {
  final dimensoes = regras.dimensoes;
  final doJ1 = casasDeAmeacaQuatro(dimensoes, posicao.pecasDoJ1, posicao.mascara);
  final doJ2 = casasDeAmeacaQuatro(dimensoes, posicao.pecasDoJ2, posicao.mascara);
  final jogaveis = casasJogaveisQuatro(dimensoes, posicao.mascara);
  final lista = <AmeacaQuatro>[];
  // Percorre os bits ligados de `doJ1 | doJ2`, do menor para o maior (o bit
  // menor é a casa de baixo da coluna 1, como na numeração do bitboard).
  var todas = doJ1 | doJ2;
  while (todas != 0) {
    // `todas & -todas` isola o bit ligado mais baixo (truque do complemento
    // de dois); `bitLength - 1` dá o número dele.
    final bit = todas & -todas;
    lista.add(AmeacaQuatro(
      casa: casaDoBit(dimensoes, bit.bitLength - 1),
      doJ1: doJ1 & bit != 0,
      doJ2: doJ2 & bit != 0,
      jogavelAgora: jogaveis & bit != 0,
    ));
    todas &= ~bit; // apaga o bit e segue para o próximo
  }
  return lista;
}

/// Os bits das casas VAZIAS onde uma peça a mais de [pecas] completa uma linha
/// de `alinhar`. [mascara] são as casas ocupadas (de qualquer um).
///
/// É a versão em bits de [ameacas], para quem conta milhões de posições (a
/// heurística): `casasQueAlinhariamQuatro` dá as casas que formariam a linha,
/// ocupadas ou não; o `& ~mascara` deixa só as vazias, e o `&` com o tabuleiro
/// tira o que transbordou para as sentinelas ou para fora da última coluna.
int casasDeAmeacaQuatro(DimensoesQuatro dimensoes, int pecas, int mascara) =>
    casasQueAlinhariamQuatro(dimensoes, pecas) &
    ~mascara &
    mascaraDoTabuleiro(dimensoes);

/// Os bits das casas onde uma peça cairia AGORA: a primeira casa livre de cada
/// coluna que ainda tem lugar.
///
/// Somar o bit do fundo de cada coluna à máscara faz o "vai um" subir pela
/// coluna até a primeira casa vazia (a mesma conta de `aplicar`); numa coluna
/// cheia o "vai um" cai na sentinela, que o `&` com o tabuleiro apaga.
int casasJogaveisQuatro(DimensoesQuatro dimensoes, int mascara) {
  var fundos = 0;
  for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
    fundos |= bitDoFundo(dimensoes, coluna);
  }
  return (mascara + fundos) & mascaraDoTabuleiro(dimensoes);
}
