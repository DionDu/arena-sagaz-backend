/// Os empates que as Regras Oficiais **declaram**, e que a matemática não vê.
///
/// Port de `../tablebase/empates_declarados_damas.py`. O Python continua sendo a
/// referência: regra nova nasce lá.
///
/// O problema, em uma frase
/// ------------------------
/// A análise retrógrada resolve o jogo e diz quem ganha. Mas as Regras Oficiais
/// brasileiras declaram **empatados** certos finais em que um lado ganharia se
/// jogasse à vontade — porque o regulamento lhe dá um número limitado de lances
/// para concluir. Três damas contra uma dama na grande diagonal é o caso famoso:
/// ganha em jogo irrestrito, e é empate pela regra.
///
/// > **Uma base sem estas regras mente.** Ela reprovaria lances corretos do motor
/// > na medição do Sagaz, e faria o app perder finais que o jogador brasileiro
/// > sabe de cor que são empate.
///
/// O que muda na natureza do cálculo
/// ---------------------------------
/// Estas regras **não perguntam "quem ganha?"** — perguntam **"ganha em quantos
/// lances?"**. Por isso a retrógrada mede a *distância* até o fim, e não só o
/// resultado. Uma base vitória/derrota/empate pura não tem como aplicá-las.
///
/// ⚠️ Duas ambiguidades que NÃO foram resolvidas sozinhas
/// ------------------------------------------------------
/// 1. **"após executados 5 lances" — 5 de cada lado, ou 5 no total?** O RESUMO
///    das regras (item 18) diz "5 lances **de cada jogador**", e é essa a leitura
///    adotada. Se a certa for 5 no total, a base declara empate tarde demais.
/// 2. **Art. 100 — a dama solitária tem de estar na grande diagonal quando?**
///    Adotado "na posição avaliada". Se a leitura certa for "o tempo todo", a
///    base declara empate em posições demais.
///
/// As duas se resolvem contra o Aurora Borealis, que tem base de finais para as
/// brasileiras. É pendência declarada, não suposição escondida.
library;

import 'dart:typed_data';

import 'indice_damas.dart';
import 'tabuleiro_damas.dart';

/// Um empate declarado pelo regulamento, como dado conferível.
///
/// Mesmo padrão das cláusulas de captura: o texto oficial **copiado**, onde
/// achá-lo, e o efeito expresso em número. Parafrasear regra é como o erro entra.
class RegraDeEmpate {
  final String identificador;
  final String ondeNoDocumento;
  final String textoOficial;

  /// Quantos lances o lado forte tem para concluir.
  final int limiteEmLances;

  /// Os códigos de material a que a regra se aplica (ver [codigoDeMaterial]).
  /// Vazio quando a regra vale por um critério e não por uma lista.
  final Set<int> materiais;

  /// Se verdadeiro, a regra vale para **qualquer** fatia sem pedras.
  final bool soDamas;

  /// Condição extra do art. 100, conferida posição a posição e não por fatia.
  final bool exigeDamaSolitariaNaGrandeDiagonal;

  const RegraDeEmpate({
    required this.identificador,
    required this.ondeNoDocumento,
    required this.textoOficial,
    required this.limiteEmLances,
    this.materiais = const {},
    this.soDamas = false,
    this.exigeDamaSolitariaNaGrandeDiagonal = false,
  });

  bool valeParaFatia(Fatia fatia) {
    if (soDamas) return fatia.totalDePedras == 0;
    return materiais.contains(fatia.codigo);
  }

  /// Quantos meios-lances o lado forte tem, contados desta posição.
  ///
  /// Se o **forte** é quem joga, ele gasta 5 lances seus intercalados por 4 do
  /// adversário — 9 meios-lances. Se quem joga é o **fraco**, entram 5 do forte
  /// intercalados por 5 do fraco — 10.
  int limiteEmMeiosLances(bool quemTemAVezEstaGanhando) =>
      quemTemAVezEstaGanhando ? 2 * limiteEmLances - 1 : 2 * limiteEmLances;
}

/// Acrescenta o espelho de cada combinação, em código.
///
/// O regulamento descreve os finais de um lado só ("duas damas contra dama"),
/// mas eles valem com as cores trocadas. Esquecer o espelho faria a regra valer
/// só quando as brancas fossem o lado forte — viés silencioso e absurdo.
Set<int> _nosDoisSentidos(List<List<int>> combinacoes) {
  final codigos = <int>{};
  for (final c in combinacoes) {
    codigos.add(codigoDeMaterial(c[0], c[1], c[2], c[3]));
    codigos.add(codigoDeMaterial(c[2], c[3], c[0], c[1]));
  }
  return codigos;
}

/// A regra geral dos finais só de damas.
///
/// Repare por que ela cabe numa base de finais apesar de falar de *histórico*:
/// numa fatia sem pedras, **todo** lance é de dama, e qualquer captura muda de
/// fatia. Dentro da fatia o contador nunca zera — então "ganhar em até 20 lances
/// a partir daqui" é exatamente o que a regra pede.
final RegraDeEmpate vinteLancesSoDeDamas = RegraDeEmpate(
  identificador: 'art_97b_vinte_lances',
  ondeNoDocumento: 'Art. 97b; RESUMO DAS REGRAS, item 16',
  textoOficial: 'for verificado no tabuleiro de 64 casas, que durante 20 '
      '(vinte) lances sucessivos foram feitos apenas movimentos de damas, sem '
      'qualquer tipo de captura ou deslocamento de pedras',
  limiteEmLances: 20,
  soDamas: true,
);

/// Os cinco finais que o art. 99 lista, com as cores nos dois sentidos.
///
/// A lista veio do RESUMO item 18 somado aos diagramas do art. 99 — os dois
/// trechos se completam, e nenhum deles sozinho traz as cinco combinações.
final RegraDeEmpate finaisDeclaradosEmpatados = RegraDeEmpate(
  identificador: 'art_99_cinco_lances',
  ondeNoDocumento: 'Art. 99; RESUMO DAS REGRAS, item 18',
  textoOficial: 'Os finais de duas damas contra dama, uma dama e uma pedra '
      'contra uma dama ou uma dama contra uma dama são considerados empatados '
      'após executados 5 (cinco) lances no máximo, no tabuleiro de 64 ou 100 '
      'casas.',
  limiteEmLances: 5,
  materiais: _nosDoisSentidos([
    [0, 2, 0, 2], // 2 damas × 2 damas
    [0, 2, 0, 1], // 2 damas × 1 dama
    [0, 2, 1, 1], // 2 damas × 1 dama e 1 pedra
    [0, 1, 0, 1], // 1 dama × 1 dama
    [0, 1, 1, 1], // 1 dama × 1 dama e 1 pedra
  ]),
);

/// O caso famoso, e o que mais surpreende quem não conhece o regulamento.
///
/// Três damas contra uma **ganham** em jogo irrestrito. Pela regra brasileira,
/// com a dama solitária na grande diagonal, é **empate**.
final RegraDeEmpate tresDamasContraUmaNaGrandeDiagonal = RegraDeEmpate(
  identificador: 'art_100_grande_diagonal',
  ondeNoDocumento: 'Art. 100 (tabuleiro de 64 casas)',
  textoOficial: 'No tabuleiro de 64 casas os finais de três damas ou duas '
      'damas e uma pedra ou uma dama e duas pedras, contra uma dama localizada '
      'na grande diagonal são considerados empatados após executados 5 (cinco) '
      'lances no máximo.',
  limiteEmLances: 5,
  materiais: _nosDoisSentidos([
    [0, 3, 0, 1], // 3 damas × 1 dama
    [1, 2, 0, 1], // 2 damas e 1 pedra × 1 dama
    [2, 1, 0, 1], // 1 dama e 2 pedras × 1 dama
  ]),
  exigeDamaSolitariaNaGrandeDiagonal: true,
);

/// Na ordem em que devem ser tentadas: **da mais apertada para a mais frouxa**.
///
/// As fatias do art. 99 também são fatias só de damas, então as duas regras se
/// aplicam às mesmas posições. Vale a de limite menor — cinco lances, não vinte.
final List<RegraDeEmpate> regrasDeEmpate = [
  finaisDeclaradosEmpatados,
  tresDamasContraUmaNaGrandeDiagonal,
  vinteLancesSoDeDamas,
];

/// A regra de empate mais apertada que vale para esta fatia, se houver.
RegraDeEmpate? regraAplicavel(Fatia fatia) {
  RegraDeEmpate? escolhida;
  for (final regra in regrasDeEmpate) {
    if (!regra.valeParaFatia(fatia)) continue;
    if (escolhida == null || regra.limiteEmLances < escolhida.limiteEmLances) {
      escolhida = regra;
    }
  }
  return escolhida;
}

/// O lado fraco tem exatamente uma dama, e ela está na grande diagonal?
///
/// "Lado fraco" aqui é o que tem **só uma dama e nenhuma pedra** — é assim que o
/// art. 100 descreve o defensor.
bool _damaSolitariaEstaNaGrandeDiagonal(Tabuleiro tabuleiro, Fatia fatia) {
  for (final lado in const [brancas, pretas]) {
    final pedras =
        lado == brancas ? fatia.pedrasBrancas : fatia.pedrasPretas;
    final damas = lado == brancas ? fatia.damasBrancas : fatia.damasPretas;
    if (pedras != 0 || damas != 1) continue;

    final procurada = lado == brancas ? damaBranca : damaPreta;
    for (var casa = 1; casa <= nCasas; casa++) {
      if (tabuleiro.ler(casa) == procurada) {
        return grandeDiagonal.contains(casa);
      }
    }
  }
  return false;
}

/// Converte em empate as vitórias que o regulamento não deixa concluir.
///
/// Altera [valores] **no lugar** e devolve quantas posições mudaram.
///
/// Precisa rodar **logo depois** de a fatia ser resolvida e **antes** de qualquer
/// fatia maior consultá-la: as fatias grandes decidem olhando o resultado das
/// pequenas, e se a regra chegar atrasada elas terão decidido em cima de
/// vitórias que não existem.
int aplicarEmpatesDeclarados(
  Fatia fatia,
  Uint8List valores,
  Int16List distancias, {
  Reconstrutor? reconstrutor,
}) {
  final regra = regraAplicavel(fatia);
  if (regra == null) return 0;

  // Só a regra do art. 100 precisa olhar o tabuleiro; nas outras, reconstruir
  // 292 milhões de posições à toa seria o custo da etapa inteira.
  final monta = regra.exigeDamaSolitariaNaGrandeDiagonal
      ? (reconstrutor ?? Reconstrutor(fatia))
      : null;

  var mudadas = 0;
  for (var indice = 0; indice < fatia.tamanho; indice++) {
    final resultado = valores[indice];
    if (resultado == empate) continue;

    final distancia = distancias[indice];
    if (distancia < 0) continue;

    final limite = regra.limiteEmMeiosLances(resultado == vitoria);
    if (distancia <= limite) continue;

    if (monta != null) {
      if (!monta.reconstruir(indice)) continue;
      if (!_damaSolitariaEstaNaGrandeDiagonal(monta.tabuleiro, fatia)) continue;
    }

    // Nem vitória nem derrota: o regulamento declarou empate antes de o jogo
    // perfeito conseguir concluir.
    valores[indice] = empate;
    mudadas++;
  }
  return mudadas;
}
