// O TABULEIRO do Jogo dos Pontinhos - as regras, em Dart puro.
//
// Este arquivo é a fonte da verdade do ESTADO de uma partida, e ele vale para os
// dois lados: o aplicativo embarca uma cópia byte-idêntica, e o servidor joga
// com este mesmo código compilado (T093). Ele espelha fielmente a representação
// descrita em `contrato_codificacao_pontinhos.json`:
//
//   • A partida é guardada numa MATRIZ de inteiros de tamanho
//     (2*linhas+1) × (2*colunas+1), onde `linhas`/`colunas` são caixas.
//   • Pontos fixos da grade (posição par×par) carregam SEMPRE o valor 8.
//   • Traços HORIZONTAIS ficam em posição par×ímpar (rótulo "H_linha_coluna").
//   • Traços VERTICAIS ficam em posição ímpar×par (rótulo "V_linha_coluna").
//   • Interior de CAIXA fica em posição ímpar×ímpar.
//   • Durante a partida: 0 = vazio, +1 = Jogador 1, -1 = Jogador 2 (contexto 3).
//
// Manter esta representação idêntica à do backend é o que permite normalizar a
// matriz e enviá-la à CNN sem traduções frágeis.
//
// ── ⚠️ POR QUE AQUI O JOGADOR É UM SINAL (+1/-1), E NÃO UM `enum` ───────────
//
// No aplicativo existe o enum `Jogador` (`lib/core/jogos/jogador.dart`), que é
// do **hub**: o log de partidas e o Jogo da Velha o usam. Ele ⛔ pode entrar
// aqui - um arquivo espelhado que importasse de uma pasta que só existe no
// aplicativo não compilaria no laboratório nem no servidor, e é a mesma razão
// pela qual `oraculo_de_finais_damas.dart` mudou de casa em 27/08/2026.
//
// Então o motor fala em **sinal**, que é justamente o que vai para a matriz, e o
// aplicativo põe o enum por cima numa subclasse de três linhas
// (`logica/estado_pontinhos.dart`). ⛔ Nada de tradução no meio do caminho: o
// sinal é o dado, e o enum é a conveniência de quem desenha a tela.
library;

/// Os dois sinais que uma jogada grava na matriz.
///
/// São os mesmos do contrato da CNN e do log de partidas. ⚠️ **Não confundir
/// com o `nu_jogador` do payload de sincronização**, que é `1`/`2`: o sinal é do
/// tabuleiro, o número é do protocolo.
const int sinalJogador1 = 1;
const int sinalJogador2 = -1;

/// Resultado final de uma partida (independente de quem é humano/CPU).
///
/// ⚠️ Mora no motor, e não na camada de tela, porque quem sabe dizer quem venceu
/// é quem conta as caixas - e quem conta as caixas é este arquivo.
enum FimPartida { venceuJ1, venceuJ2, empate }

/// Estado mutável de uma partida de pontinhos.
///
/// ⚠️ **O nome não é `TabuleiroPontinhos` de propósito**: esse já é o widget que
/// DESENHA o tabuleiro no aplicativo (`lib/shared/tabuleiro_pontinhos.dart`), e
/// duas classes com o mesmo nome obrigariam toda tela que usa as duas a importar
/// uma delas com prefixo. O nome escolhido espelha o do laboratório em Python -
/// `EstadoTabuleiro`, em `jogos/jogo_pontinhos/motor/tabuleiro_pontinhos.py`.
///
/// Não depende de Flutter: pode ser testado por testes de unidade, reutilizado
/// pela tela de 2 jogadores, pelo modo CPU e pelo servidor de lances.
class EstadoTabuleiroPontinhos {
  /// Cria um tabuleiro VAZIO com [linhas] × [colunas] caixas.
  ///
  /// O construtor já preenche os pontos fixos da grade com 8 (par×par), como
  /// exige o contrato. Todo o resto começa em 0 (vazio).
  EstadoTabuleiroPontinhos({required this.linhas, required this.colunas})
      : altura = 2 * linhas + 1,
        largura = 2 * colunas + 1,
        // `List.generate(n, (i) => ...)` cria uma lista de n itens. Aqui,
        // geramos `altura` linhas, cada uma com `largura` colunas, aplicando a
        // regra: posição par×par recebe 8 (ponto fixo), senão 0 (vazio).
        matriz = List.generate(
          2 * linhas + 1,
          (r) => List.generate(
            2 * colunas + 1,
            (c) => (r.isEven && c.isEven) ? 8 : 0,
          ),
        );

  /// Número de caixas na vertical e na horizontal.
  final int linhas;
  final int colunas;

  /// Dimensões da matriz expandida (altura × largura).
  final int altura;
  final int largura;

  /// A matriz de estado (fonte da verdade). `List<List<int>>` = lista de linhas.
  final List<List<int>> matriz;

  /// Pontos (caixas fechadas) de cada jogador. Atualizados em [aplicarTracoDe].
  int pontosJ1 = 0;
  int pontosJ2 = 0;

  /// De quem é a vez, como **sinal** (`+1` / `-1`). Começa sempre no Jogador 1.
  int vezSinal = sinalJogador1;

  /// Último traço jogado (rótulo, ex.: "H_2_1") - usado para destacar na tela e,
  /// na política, para saber se a partida já começou.
  /// `String?` = pode ser nulo (nenhuma jogada ainda).
  String? ultimoTraco;

  /// Total de caixas do tabuleiro (= linhas × colunas).
  int get totalCaixas => linhas * colunas;

  /// `true` quando todas as caixas foram fechadas (fim de jogo).
  bool get acabou => (pontosJ1 + pontosJ2) >= totalCaixas;

  /// Resultado final. Só faz sentido consultar quando [acabou] é `true`.
  FimPartida get resultado {
    if (pontosJ1 > pontosJ2) return FimPartida.venceuJ1;
    if (pontosJ2 > pontosJ1) return FimPartida.venceuJ2;
    return FimPartida.empate;
  }

  // ----------------------------------------------------------------------
  // Rótulos canônicos dos traços
  // ----------------------------------------------------------------------

  /// Gera TODOS os rótulos de traço na ORDEM CANÔNICA (linha a linha, da
  /// esquerda para a direita), intercalando H_ e V_. Esta ordem é SAGRADA: é a
  /// mesma usada para treinar a CNN e a que o `mapeamento_*.json` assume. Mudar
  /// para ordem alfabética invalida as predições do modelo (ver contrato).
  List<String> todosLabelsCanonicos() {
    final labels = <String>[];
    for (var r = 0; r < altura; r++) {
      for (var c = 0; c < largura; c++) {
        // par×ímpar → traço horizontal; ímpar×par → traço vertical.
        if (r.isEven && c.isOdd) {
          labels.add('H_${r}_$c');
        } else if (r.isOdd && c.isEven) {
          labels.add('V_${r}_$c');
        }
      }
    }
    return labels;
  }

  /// Rótulos dos traços AINDA DISPONÍVEIS (valor 0 na matriz), em ordem canônica.
  List<String> tracosDisponiveis() {
    return todosLabelsCanonicos()
        .where((label) => _valorDoLabel(label) == 0)
        .toList();
  }

  /// Quantos traços já foram marcados neste tabuleiro.
  ///
  /// Somando 1, é o **número de ordem do próximo lance** - e é isso que a tela
  /// usa para pedir a semente daquele lance quando a partida é a resolução de um
  /// desafio (RF-DES-210).
  ///
  /// ⚠️ **É uma conta do TABULEIRO, não um contador da tela**, e de propósito: o
  /// poder "voltar jogada" desfaz lances, e um contador que só cresce faria a
  /// CPU responder de outro jeito à **mesma** posição depois de um retorno - a
  /// partida deixaria de ser reproduzível justamente para quem voltou.
  int get tracosMarcados =>
      todosLabelsCanonicos().length - tracosDisponiveis().length;

  /// Converte um rótulo "H_r_c"/"V_r_c" no par (linha, coluna) da matriz.
  /// Retorna um RECORD `(int r, int c)`.
  (int, int) coordenadaDoLabel(String label) {
    // `split('_')` quebra "H_2_1" em ["H", "2", "1"]. `int.parse` converte texto
    // em número.
    final partes = label.split('_');
    return (int.parse(partes[1]), int.parse(partes[2]));
  }

  // Lê o valor atual da matriz na posição apontada pelo rótulo.
  int _valorDoLabel(String label) {
    final (r, c) = coordenadaDoLabel(label);
    return matriz[r][c];
  }

  // ----------------------------------------------------------------------
  // Aplicar uma jogada
  // ----------------------------------------------------------------------

  /// Aplica o traço [label] como jogada de quem joga com [sinal] (`+1` / `-1`).
  ///
  /// Grava o sinal na aresta, verifica as caixas vizinhas e fecha as que ficaram
  /// completas (4 lados), creditando os pontos. Devolve QUANTAS caixas foram
  /// fechadas nesta jogada (0, 1 ou 2).
  ///
  /// Regra clássica: quem fecha ao menos uma caixa JOGA DE NOVO. Por isso esta
  /// função NÃO troca a vez - quem chama decide isso a partir do retorno.
  int aplicarTracoDe(String label, int sinal) {
    final (r, c) = coordenadaDoLabel(label);
    // Defesa: ignora se a aresta já está ocupada (jogada inválida).
    if (matriz[r][c] != 0) return 0;

    // 1) Marca a aresta com o sinal do jogador.
    matriz[r][c] = sinal;
    ultimoTraco = label;

    // 2) Descobre quais caixas vizinhas podem ter sido completadas.
    //    H_r_c (r par): caixas acima [r-1][c] e abaixo [r+1][c].
    //    V_r_c (r ímpar): caixas à esquerda [r][c-1] e à direita [r][c+1].
    final vizinhas = <(int, int)>[];
    if (r.isEven) {
      vizinhas..add((r - 1, c))..add((r + 1, c));
    } else {
      vizinhas..add((r, c - 1))..add((r, c + 1));
    }

    // 3) Para cada caixa vizinha válida e completa, fecha-a e credita ponto.
    var fechadas = 0;
    for (final (br, bc) in vizinhas) {
      if (_caixaCompleta(br, bc) && matriz[br][bc] == 0) {
        matriz[br][bc] = sinal; // interior recebe o dono
        fechadas++;
        if (sinal == sinalJogador1) {
          pontosJ1++;
        } else {
          pontosJ2++;
        }
      }
    }
    return fechadas;
  }

  // Uma caixa vive em posição ímpar×ímpar. Está completa quando suas 4 arestas
  // (cima, baixo, esquerda, direita) estão ocupadas (não-zero). Posições fora
  // da matriz não são caixas válidas.
  bool _caixaCompleta(int r, int c) {
    if (r <= 0 || r >= altura - 1 || c <= 0 || c >= largura - 1) return false;
    if (r.isEven || c.isEven) return false; // não é interior de caixa
    return matriz[r - 1][c] != 0 && // aresta de cima
        matriz[r + 1][c] != 0 && // aresta de baixo
        matriz[r][c - 1] != 0 && // aresta da esquerda
        matriz[r][c + 1] != 0; // aresta da direita
  }

  /// Avança o turno para o oponente. Chamado quando a jogada NÃO fechou nenhuma
  /// caixa.
  void passarVez() => vezSinal = -vezSinal;

  // ----------------------------------------------------------------------
  // Cópia da matriz (para a CNN normalizar sem corromper o estado)
  // ----------------------------------------------------------------------

  /// Devolve uma CÓPIA PROFUNDA da matriz. O contrato exige que a normalização
  /// para a CNN seja feita sobre uma cópia - nunca sobre a matriz da partida,
  /// ou o marcador do Jogador 2 (-1) "viraria" Jogador 1 e corromperia o jogo.
  List<List<int>> copiaMatriz() {
    return [for (final linha in matriz) List<int>.from(linha)];
  }
}
