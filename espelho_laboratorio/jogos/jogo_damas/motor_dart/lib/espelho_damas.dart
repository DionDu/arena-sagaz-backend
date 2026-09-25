// O ESPELHO DA BASE DE FINAIS — a operação que corta o asset pela metade.
//
// ── A ideia, em uma frase ──────────────────────────────────────────────────
//
// Toda posição tem uma **gêmea**: o mesmo desenho com as cores trocadas e o
// tabuleiro de cabeça para baixo. São a mesma posição contada de dois jeitos —
// o lado forte continua sendo o lado que joga —, e por isso metade da base é
// dedutível da outra metade.
//
// ⚠️ **Isto não é "óbvio o bastante para dispensar medição".** A simetria foi
// conferida posição por posição, valores **e** distâncias, nas **quatro**
// modalidades, em `test/modulos/jogos/damas/tablebase/simetria_de_cor_test.dart`.
// Até 26/08/2026 só as brasileiras tinham sido conferidas, e a anglo — com a
// **dama curta**, a regra que mais muda o valor de um final — era exatamente a
// que faltava. Uma simetria que falhasse ali faria o Magno anunciar vitória em
// posição empatada **com certeza absoluta**, que é a pior forma de errar: a
// base não tem margem de dúvida para transmitir.
//
// ── O que ela vale ─────────────────────────────────────────────────────────
//
// Medido em 26/08/2026 sobre as bases de 4 peças, gzip por fatia:
// **9,08 MB nas quatro modalidades**, contra 18,2 MB sem ela.
//
// ── ⚠️ Este arquivo MUDOU DE CASA em 28/08/2026 — e o motivo importa ───────
//
// Ele nasceu em `damas/tablebase/`, no app, com um bloco explicando que o
// laboratório **não** precisava desta operação: lá a base inteira está no
// disco, e o espelho existia só por causa do tamanho do APK.
//
// Isso deixou de ser verdade quando o *probing* entrou na busca (T185 parte
// 2b). Quem lê a base empacotada passou a ser `base_empacotada_damas.dart`, que
// é **arquivo espelhado** — cópia byte-idêntica do laboratório —, e um arquivo
// do motor não pode importar de `tablebase/`, que só existe no app. Então o
// espelho subiu, e o endereço antigo virou um reexporte de uma linha.
//
// A fronteira do espelho **não é o assunto do arquivo, é o que ele conhece**:
// este aqui fala só de `Tabuleiro` e de nomes de fatia, e por isso pôde subir.
// Quem fala de `AssetBundle` (o extrator do asset) continua fora.
library;

import 'indice_damas.dart';
import 'tabuleiro_damas.dart';

/// A peça de cor trocada. O índice é a peça; o valor, a gêmea dela.
///
/// Tabela em vez de `switch` porque isto roda por casa, em laço quente: um
/// acesso a lista é mais barato que uma cadeia de comparações, e a tabela
/// também documenta o mapeamento inteiro numa olhada.
const List<int> pecaDeCorTrocada = <int>[
  vazia, // vazia continua vazia
  pedraPreta, // pedraBranca -> pedraPreta
  damaPreta, // damaBranca  -> damaPreta
  pedraBranca, // pedraPreta  -> pedraBranca
  damaBranca, // damaPreta   -> damaBranca
];

/// A mesma posição com as cores trocadas e o tabuleiro de cabeça para baixo.
///
/// São **duas** operações, e fazer só uma delas produz uma posição diferente em
/// vez da gêmea: trocar as cores sem girar deixaria as pretas subindo o
/// tabuleiro. A rotação de 180° é `casa -> nCasas + 1 - casa`, porque a
/// numeração corre da esquerda para a direita e de cima para baixo.
///
/// A vez também troca — é a mesma posição vista do outro lado, e quem joga
/// continua sendo quem jogava.
Tabuleiro espelhar(Tabuleiro tabuleiro) {
  final girado =
      Tabuleiro.vazio(vez: tabuleiro.vez == brancas ? pretas : brancas);
  for (var casa = 1; casa <= nCasas; casa++) {
    final peca = tabuleiro.ler(casa);
    if (peca != vazia) girado.escrever(nCasas + 1 - casa, pecaDeCorTrocada[peca]);
  }
  return girado;
}

/// O nome da fatia gêmea: `pb db pp dp` vira `pp dp pb db`.
///
/// O nome de uma fatia tem quatro dígitos, nessa ordem: pedras brancas, damas
/// brancas, pedras pretas, damas pretas. Espelhar é trocar os dois primeiros
/// pelos dois últimos — a mesma operação que [espelhar] faz no tabuleiro, dita
/// no vocabulário do catálogo.
String nomeDaFatiaGemea(String nome) => nome.substring(2) + nome.substring(0, 2);

/// Esta fatia é a que se **guarda**, das duas gêmeas?
///
/// O critério é arbitrário e por isso mesmo tem de ser **um só**, escrito num
/// lugar só: fica a de menor nome em ordem alfabética. Quem empacota e quem lê
/// chamam esta mesma função — se cada lado tivesse a sua regra, o dia em que
/// elas divergissem produziria uma base que carrega sem erro e responde a
/// posição errada.
///
/// Uma fatia **simétrica de si mesma** (`0101`, `1010`, …) é canônica: não há
/// gêmea a descartar.
bool fatiaEhCanonica(String nome) => nome.compareTo(nomeDaFatiaGemea(nome)) <= 0;

/// Quantas fatias uma base de [pecas] peças guarda, depois do corte.
///
/// Existe para o empacotador e o teste dizerem o mesmo número sem que nenhum
/// dos dois o escreva à mão.
int quantasFatiasCanonicas(int pecas) =>
    fatiasAte(pecas).where((f) => fatiaEhCanonica(f.nome)).length;
