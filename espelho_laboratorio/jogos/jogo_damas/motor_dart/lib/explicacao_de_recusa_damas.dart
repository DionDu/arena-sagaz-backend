/// Por que **este** lance não é permitido — a resposta que o app mostra ao
/// jogador.
///
/// ## O problema que este módulo resolve
///
/// O app já sabe recusar um lance ilegal: basta perguntar ao motor a lista de
/// lances legais e ver se o tentado está nela. O que ele **não** sabe é *por
/// quê* — e em damas o porquê é quase sempre uma regra de **obrigatoriedade**,
/// justamente a categoria que o jogador casual não conhece.
///
/// Sem isto, o app teria duas saídas ruins:
///
/// 1. dizer só *"movimento inválido"*, que não ensina nada e parece bug;
/// 2. **reimplementar as regras em Dart** para deduzir o motivo — e duas
///    implementações da mesma regra divergem. É a lição que este projeto já
///    pagou duas vezes (a base de finais em 26/07, o limite de empate anglo em
///    28/07).
///
/// Aqui a dedução é feita **com o próprio gerador**, comparando as listas que
/// ele produz. Nenhuma regra é reescrita: o que se faz é observar *qual filtro*
/// comeu o lance tentado.
///
/// ## Como a dedução funciona
///
/// O gerador produz duas listas, e a diferença entre elas conta a história:
///
/// - [gerarCapturas] — **todas** as sequências de captura completas, sem filtro;
/// - [gerarLances] — o que sobra depois da Lei da Maioria e da Lei da Qualidade.
///
/// Daí saem os casos:
///
/// | onde o lance tentado está | o que aconteceu |
/// |---|---|
/// | em `gerarLances` | é legal — nada a explicar |
/// | não é captura, mas há capturas | captura é obrigatória |
/// | em `gerarCapturas`, com menos peças que o máximo | Lei da Maioria |
/// | em `gerarCapturas`, no máximo, mas com menos damas | Lei da Qualidade |
/// | é **prefixo** de uma sequência completa | parou no meio da captura |
/// | em lugar nenhum | o lance não existe (geometria, peça própria, recuo…) |
///
/// ## O identificador é o que o app usa
///
/// A [RecusaDeLance.mensagem] sai daqui em português e serve de **referência**,
/// não de string de produção: o app tem três idiomas e a tradução é dele. O que
/// o app deve consumir é o [RecusaDeLance.identificador] — estável, em
/// `snake_case` — e as casas a destacar.
///
/// ## Port do Python: as duas diferenças, e por que existem
///
/// O módulo de referência é `../motor/explicacao_de_recusa_damas.py`, e a
/// tradução é literal **menos** dois pontos, que o Dart obriga:
///
/// 1. **A igualdade de [Lance].** Em Python `Lance` é uma `dataclass(frozen)`,
///    e `lance in lista` compara por valor de graça. Em Dart a classe não
///    implementa `==`, então `List.contains` compararia por **identidade** — e
///    um lance montado pela tela nunca seria o mesmo objeto que o gerador
///    devolveu. Toda comparação aqui passa por [_mesmoLance]. Trocar isso por
///    `contains` faz **todos** os lances legais virarem "lance inexistente", e o
///    app explica a regra errada com toda a confiança.
/// 2. **`damasCapturadas` é pública** em `regras_damas.dart`. Em Dart o `_`
///    esconde de outros arquivos, não de outras classes — ver a justificativa no
///    doc dela.
library;

import 'regras_damas.dart';
import 'tabuleiro_damas.dart';

/// Por que o lance foi recusado, e o que o app deve mostrar.
class RecusaDeLance {
  /// A regra que recusou, em `snake_case`.
  ///
  /// **É isto que o app consome** — a chave para escolher a mensagem no idioma
  /// do jogador. Os valores possíveis estão em [identificadoresDeRecusa].
  final String identificador;

  /// O texto em português, já com os números concretos.
  ///
  /// Serve de referência para a tradução e para depurar; **não é string de
  /// produção** — o app tem três idiomas e monta a frase a partir do
  /// [identificador].
  final String mensagem;

  /// As casas que o tabuleiro deve acender.
  ///
  /// O que elas significam muda com a regra: nas capturas obrigatórias são as
  /// peças que **podem** comer; na Lei da Maioria, o caminho da sequência que
  /// ele deveria ter jogado.
  final List<int> casasADestacar;

  /// Os lances que o jogador deveria ter escolhido.
  ///
  /// Vazio quando a recusa não aponta para uma alternativa específica (um lance
  /// geometricamente impossível, por exemplo).
  final List<Lance> lancesObrigatorios;

  const RecusaDeLance({
    required this.identificador,
    required this.mensagem,
    this.casasADestacar = const [],
    this.lancesObrigatorios = const [],
  });

  @override
  String toString() => '$identificador: $mensagem';
}

/// Todos os identificadores que [explicarRecusa] pode devolver.
///
/// Existe para que o app possa **provar** que traduziu todos: um `switch` sem
/// caso padrão sobre uma String não avisa nada, mas um teste que percorre esta
/// lista e cobra a chave de i18n avisa. Sem ela, o identificador novo aparece no
/// aparelho como texto faltando.
const List<String> identificadoresDeRecusa = [
  'captura_obrigatoria',
  'lei_da_maioria',
  'lei_da_qualidade',
  'sequencia_incompleta',
  'bloqueado_por_condenada',
  'lance_inexistente',
  'peca_sem_lance',
];

/// Os dois lances são o mesmo? Compara **por valor**, campo a campo.
///
/// ⚠️ Ver a diferença nº 1 no cabeçalho do arquivo. `List.contains` aqui usaria
/// identidade de objeto, e o lance que a tela montou nunca é o objeto que o
/// gerador criou.
bool _mesmoLance(Lance a, Lance b) {
  if (a.viraDama != b.viraDama) return false;
  if (a.caminho.length != b.caminho.length) return false;
  if (a.capturadas.length != b.capturadas.length) return false;
  for (var i = 0; i < a.caminho.length; i++) {
    if (a.caminho[i] != b.caminho[i]) return false;
  }
  for (var i = 0; i < a.capturadas.length; i++) {
    if (a.capturadas[i] != b.capturadas[i]) return false;
  }
  return true;
}

/// A lista contém algum lance igual a [procurado]?
bool _contem(List<Lance> lances, Lance procurado) {
  for (final lance in lances) {
    if (_mesmoLance(lance, procurado)) return true;
  }
  return false;
}

/// [tentado] é o começo de [completo], parado no meio do caminho?
///
/// Compara caminho **e** capturadas: uma captura múltipla é identificada pelas
/// duas coisas, e conferir só o caminho aceitaria uma sequência que passa pelas
/// mesmas casas tomando peças diferentes.
bool _ePrefixo(Lance tentado, Lance completo) {
  if (tentado.caminho.length >= completo.caminho.length) return false;
  for (var i = 0; i < tentado.caminho.length; i++) {
    if (tentado.caminho[i] != completo.caminho[i]) return false;
  }
  // Um caminho de N casas corresponde a N−1 capturas. A conferência existe
  // porque o lance tentado vem de fora do motor: a tela pode montar um caminho
  // longo com uma lista de capturadas curta, e o laço abaixo leria fora da
  // sequência do lance completo.
  if (tentado.capturadas.length != tentado.caminho.length - 1) return false;
  for (var i = 0; i < tentado.capturadas.length; i++) {
    if (tentado.capturadas[i] != completo.capturadas[i]) return false;
  }
  return true;
}

/// Todas as casas envolvidas nestes lances — caminho e peças tomadas.
///
/// Sem repetição e em ordem crescente, para o destaque do app ser estável: uma
/// lista que muda de ordem a cada chamada faria a animação piscar.
List<int> _casasDosLances(List<Lance> lances) {
  final casas = <int>{};
  for (final lance in lances) {
    casas.addAll(lance.caminho);
    casas.addAll(lance.capturadas);
  }
  return casas.toList()..sort();
}

/// As casas de origem distintas destes lances, em ordem crescente.
List<int> _origensDistintas(List<Lance> lances) {
  final origens = <int>{for (final lance in lances) lance.origem};
  return origens.toList()..sort();
}

/// Por que este lance não é permitido. `null` quando ele **é** legal.
///
/// Devolver `null` para lance legal é de propósito: o app chama esta função só
/// depois de o lance falhar na lista, e um `null` inesperado aqui é sinal de que
/// as duas verificações discordaram — vale tratar como defeito, não ignorar.
///
/// - [tabuleiro]: a posição **antes** do lance.
/// - [tentado]: o que o jogador tentou fazer.
/// - [regulamento]: qual modalidade está em jogo. As respostas mudam com ela — a
///   Lei da Maioria não existe nas anglo-americanas nem nas damas de casa, e a
///   Lei da Qualidade só existe nas portuguesas.
/// As casas que ficam **entre** duas casas da mesma diagonal, sem elas.
///
/// Geometria pura, não regra: é a mesma pergunta que a dama faz ao deslizar.
/// Devolve lista vazia quando as duas casas não estão na mesma diagonal — não é
/// erro, é a resposta certa para um par que não se enxerga.
List<int> _casasEntre(int origem, int destino) {
  for (final direcao in const [
    cimaEsquerda,
    cimaDireita,
    baixoEsquerda,
    baixoDireita,
  ]) {
    final diagonal = raio(origem, direcao);
    final indice = diagonal.indexOf(destino);
    if (indice >= 0) return diagonal.sublist(0, indice);
  }
  return const [];
}

/// As peças já comidas que **este** lance atravessa ou pisa depois de comê-las.
///
/// É o que o art. 15 barra: a peça capturada fica no tabuleiro até o lance
/// terminar, então a casa onde ela está é casa fechada. Percorre-se o lance
/// perna a perna; em cada uma, olha-se se alguma peça comida **antes** daquela
/// perna cai no trecho percorrido (ou na casa de pouso).
///
/// `capturadas.sublist(0, i)` é o que já saiu de circulação quando a perna `i`
/// começa — a vítima da própria perna é `capturadas[i]`, e essa, claro, não
/// conta.
List<int> _condenadasQueFecham(Lance lance) {
  final culpadas = <int>{};
  for (var i = 0; i < lance.caminho.length - 1; i++) {
    if (i == 0) continue; // na primeira perna ainda não há peça comida
    final anteriores = lance.capturadas.sublist(0, i);
    final de = lance.caminho[i];
    final para = lance.caminho[i + 1];
    final trecho = [..._casasEntre(de, para), para];
    for (final casa in trecho) {
      if (anteriores.contains(casa)) culpadas.add(casa);
    }
  }
  final lista = culpadas.toList()..sort();
  return lista;
}

/// A recusa do **art. 15**, se for o caso — ou `null`.
///
/// Gera as capturas duas vezes: a normal (com o Tema Turco, que é a regra) e uma
/// **fantasma**, em que as peças já tomadas contam como casa vazia. Um lance que
/// existe só na segunda foi barrado pela peça condenada, e por nada mais — a
/// diferença entre as duas gerações é exatamente essa.
///
/// [tentados] é uma lista porque [explicarGesto] chega aqui com vários (um gesto
/// de duas casas pode corresponder a mais de uma sequência), e [explicarRecusa],
/// com um só.
///
/// As casas a destacar são as condenadas que **de fato** fecham o caminho — ver
/// [_condenadasQueFecham]. Acender a peça culpada é o que ensina: ela está ali,
/// na tela, com a marca de condenada, e é a resposta visual à pergunta "por que
/// não dá para passar?". Se nenhuma for identificada, acendem-se todas as
/// comidas pelo lance fantasma: menos preciso, mas ainda verdadeiro — todas elas
/// estão no tabuleiro naquele instante.
RecusaDeLance? _bloqueioPorCondenada(
  Tabuleiro tabuleiro,
  Regulamento regulamento,
  List<Lance> tentados,
) {
  final fantasmas =
      gerarCapturas(tabuleiro, regulamento, condenadasBloqueiam: false);
  if (fantasmas.isEmpty) return null;

  final reais = gerarCapturas(tabuleiro, regulamento);
  final candidatos = <Lance>[];
  for (final lance in fantasmas) {
    if (_contem(reais, lance)) continue;
    for (final tentado in tentados) {
      if (_mesmoLance(tentado, lance) || _ePrefixo(tentado, lance)) {
        candidatos.add(lance);
        break;
      }
    }
  }
  if (candidatos.isEmpty) return null;

  final condenadas = <int>{};
  for (final lance in candidatos) {
    condenadas.addAll(_condenadasQueFecham(lance));
  }
  if (condenadas.isEmpty) {
    for (final lance in candidatos) {
      condenadas.addAll(lance.capturadas);
    }
  }

  return RecusaDeLance(
    identificador: 'bloqueado_por_condenada',
    mensagem: 'A peça que você já comeu continua no tabuleiro até o lance '
        'terminar, e ela fecha esse caminho (art. 15).',
    casasADestacar: condenadas.toList()..sort(),
  );
}

RecusaDeLance? explicarRecusa(
  Tabuleiro tabuleiro,
  Lance tentado, [
  Regulamento regulamento = brasileiras,
]) {
  final legais = gerarLances(tabuleiro, regulamento);
  if (_contem(legais, tentado)) return null;

  final todasAsCapturas = gerarCapturas(tabuleiro, regulamento);

  // --- 1. captura obrigatória ---------------------------------------------
  //
  // Vem primeiro porque é a regra que o jogador mais esbarra, e a única em que a
  // peça obrigada pode estar do outro lado do tabuleiro — longe de onde ele
  // estava olhando.
  if (!tentado.eCaptura && todasAsCapturas.isNotEmpty) {
    final origens = _origensDistintas(todasAsCapturas);
    final quantas = origens.length;
    return RecusaDeLance(
      identificador: 'captura_obrigatoria',
      mensagem: 'Você é obrigado a comer. '
          '${quantas == 1 ? 'Esta peça pode comer:' : 'Estas $quantas peças podem comer:'}',
      casasADestacar: origens,
      lancesObrigatorios: legais,
    );
  }

  // --- 2. a captura existe, mas foi filtrada ------------------------------
  if (_contem(todasAsCapturas, tentado)) {
    var maximo = 0;
    for (final lance in todasAsCapturas) {
      if (lance.quantasCapturas > maximo) maximo = lance.quantasCapturas;
    }

    if (tentado.quantasCapturas < maximo) {
      final maiores = [
        for (final lance in todasAsCapturas)
          if (lance.quantasCapturas == maximo) lance
      ];
      final n = tentado.quantasCapturas;
      return RecusaDeLance(
        identificador: 'lei_da_maioria',
        mensagem: 'Essa captura come $n ${n != 1 ? 'peças' : 'peça'}, e há uma '
            'que come $maximo. Você é obrigado a comer o maior número.',
        casasADestacar: _casasDosLances(maiores),
        lancesObrigatorios: maiores,
      );
    }

    // Mesmo número de peças e ainda assim recusado: só a Lei da Qualidade
    // explica, e ela só existe nas portuguesas/espanholas.
    return RecusaDeLance(
      identificador: 'lei_da_qualidade',
      mensagem: 'As duas capturas comem $maximo '
          '${maximo != 1 ? 'peças' : 'peça'}, mas uma delas come a dama. Você é '
          'obrigado a comer a peça mais valiosa.',
      casasADestacar: _casasDosLances(legais),
      lancesObrigatorios: legais,
    );
  }

  // --- 3. parou no meio de uma captura múltipla ---------------------------
  final continuacoes = [
    for (final lance in todasAsCapturas)
      if (_ePrefixo(tentado, lance)) lance
  ];
  if (continuacoes.isNotEmpty) {
    return RecusaDeLance(
      identificador: 'sequencia_incompleta',
      mensagem: 'A captura ainda não terminou — dá para comer mais.',
      casasADestacar: _casasDosLances(continuacoes),
      lancesObrigatorios: continuacoes,
    );
  }

  // --- 3b. o art. 15 fechou o caminho -------------------------------------
  //
  // A peça capturada **não sai do tabuleiro no momento do salto**: fica onde
  // está, condenada, e continua bloqueando a passagem até o lance inteiro
  // terminar. Quem está aprendendo conta as peças que já comeu como se elas
  // tivessem sumido, e então tenta um caminho que passa por cima de uma delas.
  final recusaDoArtigo15 =
      _bloqueioPorCondenada(tabuleiro, regulamento, [tentado]);
  if (recusaDoArtigo15 != null) return recusaDoArtigo15;

  // --- 4. o lance simplesmente não existe ---------------------------------
  //
  // Geometria errada, casa ocupada, salto sobre peça própria, pedra tentando
  // comer de recuo onde a modalidade não deixa. Aqui não há uma regra única a
  // citar — o que ajuda o jogador é ver o que aquela peça PODE fazer.
  final daMesmaPeca = [
    for (final lance in legais)
      if (lance.origem == tentado.origem) lance
  ];
  if (daMesmaPeca.isNotEmpty) {
    final destinos = <int>{for (final lance in daMesmaPeca) lance.destino};
    return RecusaDeLance(
      identificador: 'lance_inexistente',
      mensagem: 'Esta peça não pode ir para aí. Ela pode ir para:',
      casasADestacar: destinos.toList()..sort(),
      lancesObrigatorios: daMesmaPeca,
    );
  }

  return const RecusaDeLance(
    identificador: 'peca_sem_lance',
    mensagem: 'Esta peça não tem nenhum movimento agora.',
  );
}

/// A mesma explicação, a partir do que o **app** sabe: duas casas.
///
/// ## O problema
///
/// [explicarRecusa] recebe um [Lance] — caminho inteiro e peças tomadas. A tela
/// não tem isso: o jogador toca numa peça e toca numa casa, e pronto. Montar o
/// caminho no app seria escrever regra de damas fora do motor, que é justamente
/// o que este módulo existe para evitar.
///
/// ## A saída
///
/// Todo lance candidato sai do **gerador**. Procura-se, entre o que ele
/// produziu, o que casa com o gesto — nesta ordem:
///
/// 1. um lance **legal** com esse par de casas → não há o que explicar;
/// 2. uma **captura completa** que termina nessa casa → é uma captura que algum
///    filtro cortou (Lei da Maioria ou da Qualidade);
/// 3. um **prefixo** de captura múltipla que passa por essa casa → o jogador
///    parou no meio. É o caso da casa 10 que o dono encontrou no iPhone em
///    17/08: a dama de 19 come duas peças e pousa em 17, e a 10 é só passagem;
/// 4. nada casa → o gesto vira um lance simples fictício, e a explicação cai no
///    ramo de captura obrigatória ou de lance inexistente.
///
/// `origem == destino` é caso legítimo, e é como a tela pergunta *"por que esta
/// peça não anda?"* quando alguém toca numa peça travada: nenhum lance começa e
/// termina na mesma casa, então o gesto cai direto no passo 4.
RecusaDeLance? explicarGesto(
  Tabuleiro tabuleiro,
  int origem,
  int destino, [
  Regulamento regulamento = brasileiras,
]) {
  final legais = gerarLances(tabuleiro, regulamento);
  for (final lance in legais) {
    if (lance.origem == origem && lance.destino == destino) return null;
  }

  final todasAsCapturas = gerarCapturas(tabuleiro, regulamento);

  // 2. Captura completa com esse par de casas. Havendo mais de uma (possível com
  //    dama, por caminhos diferentes), fica a que come mais: é a que o jogador
  //    teria escolhido, e a que produz a explicação mais útil.
  Lance? melhorCompleta;
  for (final lance in todasAsCapturas) {
    if (lance.origem != origem || lance.destino != destino) continue;
    if (melhorCompleta == null ||
        lance.quantasCapturas > melhorCompleta.quantasCapturas) {
      melhorCompleta = lance;
    }
  }
  if (melhorCompleta != null) {
    return explicarRecusa(tabuleiro, melhorCompleta, regulamento);
  }

  // 3. Prefixo: a casa é uma parada INTERMEDIÁRIA de alguma captura múltipla. O
  //    laço começa em 1 e para antes do fim de propósito — a primeira posição do
  //    caminho é a origem, e a última já foi coberta pelo passo 2.
  for (final lance in todasAsCapturas) {
    for (var k = 1; k < lance.caminho.length - 1; k++) {
      if (lance.caminho[k] != destino) continue;
      return explicarRecusa(
        tabuleiro,
        Lance(lance.caminho.sublist(0, k + 1), lance.capturadas.sublist(0, k)),
        regulamento,
      );
    }
  }

  // 3b. O art. 15: o gesto corresponde a uma captura que só existiria se a peça
  //     já comida tivesse saído do tabuleiro na hora do salto.
  //
  //     Aqui não dá para montar um `Lance` e perguntar — o app tem duas casas.
  //     Então os candidatos saem da geração fantasma: todo lance dela que comece
  //     na origem e **passe ou termine** no destino é uma continuação que o
  //     jogador poderia estar tentando.
  final fantasmas =
      gerarCapturas(tabuleiro, regulamento, condenadasBloqueiam: false);
  final candidatos = <Lance>[];
  for (final lance in fantasmas) {
    if (lance.origem != origem) continue;
    for (var k = 1; k < lance.caminho.length; k++) {
      if (lance.caminho[k] == destino) {
        candidatos.add(lance);
        break;
      }
    }
  }
  if (candidatos.isNotEmpty) {
    final recusa = _bloqueioPorCondenada(tabuleiro, regulamento, candidatos);
    if (recusa != null) return recusa;
  }

  // 4. O gesto não corresponde a lance nenhum do gerador.
  return explicarRecusa(tabuleiro, Lance([origem, destino], const []), regulamento);
}

