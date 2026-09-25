// QUEM RESPONDE PELA BASE DE FINAIS — a interface que a busca e o app usam para
// perguntar à base sem saber onde ela está guardada.
//
// ── O problema que este arquivo resolve ────────────────────────────────────
//
// Duas perguntas, e só duas: *"qual o resultado desta posição?"* e *"em quantos
// meios-lances?"*. Quem as faz são dois clientes muito diferentes:
//
//   * a **consulta na raiz** do app (`consulta_base_finais_damas.dart`, T185
//     parte 2a), que decide o lance quando a posição da mesa já cabe na base;
//   * a **busca**, desde a T185 parte 2b, que pergunta lá dentro da árvore
//     quando um ramo desce até um final resolvido.
//
// E respondem duas implementações igualmente diferentes: no laboratório a base
// inteira está em memória ([BaseDeFinais], três vetores por fatia); no app o que
// viaja no APK é o formato empacotado — metade das fatias, cada uma comprimida,
// **9,08 MB nas quatro modalidades** contra 37,6 MB crus por modalidade.
//
// ⚠️ **Mas nenhum dos dois clientes pode saber disso.** É neles que moram as
// regras sutis — o empate declarado que não se deduz dos filhos, a distância que
// soma o próprio lance, o `foraDaBase` que não é empate. Se conhecessem o
// armazenamento, cada formato novo pediria uma segunda cópia dessas regras.
// Então conversam com esta **interface**, e as implementações respondem igual.
//
// ── ⚠️ Por que ela mora no MOTOR desde 27/08/2026 ──────────────────────────
//
// Ela nasceu em `arena-sagaz-frontend/lib/modulos/jogos/damas/tablebase/`, e
// aquele era o lugar certo enquanto só o app perguntava. Com o *probing* dentro
// da busca quem pergunta é `busca_damas.dart`, que é arquivo espelhado: um
// arquivo do motor não pode importar de uma pasta que só existe no app — o
// laboratório não compilaria.
//
// A cópia do app (`tablebase/oraculo_de_finais_damas.dart`) continua existindo,
// e virou **um reexporte de uma linha**, para que nenhum `import` antigo precise
// mudar de endereço.
//
// ── A prova de que respondem igual ─────────────────────────────────────────
//
// `test/modulos/jogos/damas/tablebase/oraculos_concordam_test.dart` faz as duas
// responderem à base de 3 peças **inteira**, posição por posição, valores e
// distâncias. Não é amostra: é a base toda, nas quatro modalidades.
library;

import 'indice_damas.dart';
import 'retrograda_damas.dart';
import 'tabuleiro_damas.dart';

/// Quem sabe responder o veredito exato de um final.
///
/// Duas perguntas, e as mesmas assinaturas de [BaseDeFinais] — de propósito: a
/// implementação em memória é um repasse de uma linha, e um leitor que conheça
/// uma das duas conhece a outra.
///
/// ⚠️ **Síncrona, e isso é um compromisso.** A consulta roda no meio da decisão
/// de um lance — e, desde a T185 parte 2b, dentro do laço mais quente do motor.
/// Um `Future` ali obrigaria toda a cadeia acima a ser assíncrona. O preço é que
/// quem lê de asset tem de ter os bytes **já em memória** antes da primeira
/// pergunta — ver `carregarOraculoEmpacotado`.
abstract interface class OraculoDeFinais {
  /// [derrota], [empate], [vitoria] ou [foraDaBase], para quem tem a vez.
  ///
  /// ⚠️ [foraDaBase] e [empate] são coisas completamente diferentes: o primeiro
  /// é *"não sei"*, o segundo é *"sei, e é empate"*. Confundi-los faria o app
  /// achar que todo meio-jogo está equilibrado.
  int consultar(Tabuleiro tabuleiro, {Indexador? indexador});

  /// Em quantos **meios-lances** a partida acaba com jogo perfeito, ou
  /// [semDistancia] quando a base não sabe (inclusive nos empates: ninguém
  /// "empata em 12 lances").
  int distanciaDe(Tabuleiro tabuleiro, {Indexador? indexador});

  /// Quantas peças, no total, o maior final coberto por esta base tem — **4**,
  /// hoje, nas quatro modalidades.
  ///
  /// ── Por que a interface precisa disto ──────────────────────────────────
  ///
  /// Sem este número, a busca teria de perguntar à base em **todo** nó para
  /// descobrir se ela sabe de alguma coisa, e a resposta seria [foraDaBase]
  /// milhões de vezes por lance. Com ele, a busca desce a contagem de peças pela
  /// recursão (custa uma subtração por lance, ver `_negamax`) e só pergunta
  /// quando pode haver resposta.
  ///
  /// ⚠️ Uma base carregada **pela metade** (poucas fatias, como faz
  /// `apenasAsFatias`) continua declarando o mesmo número: ele descreve o
  /// **formato**, não o que está no disco. Quem perguntar por uma fatia ausente
  /// recebe [foraDaBase], que é a resposta segura.
  int get maximoDePecas;
}

/// O oráculo que fala com a base **inteira em memória**.
///
/// É o que o laboratório e os testes usam: `construirBase(...)` devolve uma
/// [BaseDeFinais], e isto a veste com a interface. Repasse puro — nenhuma
/// decisão mora aqui, e é assim que tem de ser: se esta classe precisar de um
/// `if`, a diferença que ele trata pertence à interface, não a uma das pontas.
class OraculoEmMemoria implements OraculoDeFinais {
  final BaseDeFinais base;

  const OraculoEmMemoria(this.base);

  @override
  int consultar(Tabuleiro tabuleiro, {Indexador? indexador}) =>
      base.consultar(tabuleiro, indexador: indexador);

  @override
  int distanciaDe(Tabuleiro tabuleiro, {Indexador? indexador}) =>
      base.distanciaDe(tabuleiro, indexador: indexador);

  /// A maior fatia guardada manda — uma base montada só com as fatias de 3
  /// peças responde `3`, e a busca não a consulta com 4 no tabuleiro.
  ///
  /// `fold` percorre a lista acumulando um valor; aqui, o máximo. É calculado a
  /// cada chamada de propósito: [BaseDeFinais.guardar] pode acrescentar fatias
  /// depois de o oráculo existir, e um valor memorizado ficaria velho em
  /// silêncio. A lista tem dezenas de itens, não milhões.
  @override
  int get maximoDePecas => base.ordem.fold<int>(
        0,
        (maior, fatia) {
          final total = fatia.pedrasBrancas +
              fatia.damasBrancas +
              fatia.pedrasPretas +
              fatia.damasPretas;
          return total > maior ? total : maior;
        },
      );
}
