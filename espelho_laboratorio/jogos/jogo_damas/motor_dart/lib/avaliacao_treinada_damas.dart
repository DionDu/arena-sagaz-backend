/// A avaliação **treinada** no aparelho: lê o arquivo de pesos e dá a nota.
///
/// Port de `../../motor/avaliacao_treinada_damas.py`, e vale a regra de sempre:
/// **decisão nasce no Python**, que é o motor de referência; este arquivo
/// obedece. O que difere aqui é só o que a linguagem exige.
///
/// O que este arquivo faz, em três linhas
/// ---------------------------------------
/// 1. lê `pesos_padroes_<modalidade>.bin` a partir de bytes;
/// 2. expande as tabelas esparsas para vetores densos de 390.625 posições;
/// 3. avalia uma posição somando nove leituras de vetor mais o material.
///
/// Nenhuma multiplicação de matriz, nenhuma exponencial, nenhum runtime de
/// inferência. É por isso que esta avaliação roda num celular simples — e é a
/// diferença central em relação a uma CNN (§5.5 de
/// `../../docs/como_funciona_a_ia_de_damas.md`).
///
/// ⚠️ Nada de `dart:io` aqui, de propósito
/// ----------------------------------------
/// A biblioteca recebe **bytes** ([lerPesosDosPadroes]), nunca um caminho de
/// arquivo. No app os pesos chegam por `rootBundle.load(...)`, que devolve um
/// `ByteData` e não tem sistema de arquivos por baixo; num teste chegam de um
/// `Uint8List` montado na hora; na bancada do PC, de `File.readAsBytesSync`.
/// Quem tem `dart:io` é o binário de linha de comando (`bin/`), não isto.
///
/// A geometria vem do ARQUIVO, e não deste código
/// -----------------------------------------------
/// As nove janelas — quais casas, em que ordem, qual tabela, se inverte o ponto
/// de vista — estão gravadas no `.bin` e são lidas de lá. Este arquivo **não tem
/// uma cópia** delas.
///
/// É deliberado, e é a lição do contrato de codificação do Jogo dos Pontinhos
/// aplicada mais cedo: duas cópias de uma geometria divergem em silêncio, e o
/// sintoma é uma avaliação plausível e errada. Com a geometria dentro do arquivo,
/// pesos e geometria não podem se separar.
///
/// A convenção de sinal é a mesma da avaliação manual
/// ---------------------------------------------------
/// [avaliarTreinado] devolve a nota **do ponto de vista de quem tem a vez**, em
/// centésimos de pedra — igual a `avaliacao_damas.dart`. É o que permite a arena
/// da etapa 9 trocar uma avaliação pela outra sem tocar na busca.
library;

import 'dart:convert' show utf8;
import 'dart:typed_data';

import 'tabuleiro_damas.dart';

/// Os oito bytes que abrem o arquivo. Terminam em `\n` de propósito — se o
/// arquivo for transferido em modo texto entre Windows e Unix, o `\n` viaja como
/// `\r\n`, a magia deixa de bater e o arquivo é recusado na primeira leitura em
/// vez de ser lido com todos os deslocamentos deslizados em um byte. Truque
/// emprestado do PNG.
final Uint8List magiaDosPesos =
    Uint8List.fromList(utf8.encode('DAMAPAD\n'));

/// A versão do **layout** que este código sabe ler. A magia diz "é um arquivo de
/// padrões de damas"; a versão diz "e está neste arranjo de campos".
const int versaoDosPesos = 1;

/// Quantos estados uma casa pode ter dentro de uma janela: vazia, minha pedra,
/// minha dama, pedra dele, dama dele.
const int estadosPorCasa = 5;

/// Casas jogáveis dentro do quadrado 4×4 de uma janela.
const int casasPorJanela = 8;

/// `5⁸` — as fotografias possíveis de uma janela, e portanto o tamanho de cada
/// tabela.
const int entradasPorTabela = 390625;

/// minhas pedras · minhas damas · pedras dele · damas dele.
///
/// A ordem é contrato com o conjunto de treino: trocar duas colunas dá um motor
/// que valoriza as peças do adversário, e nada dá erro.
const int colunasDeMaterial = 4;

/// O arquivo de pesos não é o que este código espera.
///
/// Exceção própria para que quem carrega possa distinguir "o recurso está
/// corrompido" de "há um bug no motor" — no app isso é a diferença entre uma
/// mensagem ao usuário e um relatório de falha.
class ArquivoDePesosInvalido implements Exception {
  final String motivo;
  const ArquivoDePesosInvalido(this.motivo);

  @override
  String toString() => 'ArquivoDePesosInvalido: $motivo';
}

/// Uma região do tabuleiro e como lê-la. Espelha a `Janela` do Python.
class JanelaDePadroes {
  /// `L<linha>C<coluna>` do canto do quadrado — nome geométrico, porque quem
  /// depura quer saber *onde* a janela está.
  final String identificador;

  /// As oito casas jogáveis, **na ordem de leitura**. A ordem define o índice.
  final Uint8List casas;

  /// Em qual das cinco tabelas esta janela lê.
  final String tabela;

  /// Se esta é a janela **derivada** da órbita da rotação de 180°, e portanto lê
  /// "minha peça" como "peça dele".
  final bool inverteOPontoDeVista;

  const JanelaDePadroes({
    required this.identificador,
    required this.casas,
    required this.tabela,
    required this.inverteOPontoDeVista,
  });
}

/// Os pesos prontos para consultar, em centésimos de pedra.
class PesosDosPadroes {
  /// `{nome: vetor de 390.625}`. Densos: consultar é um acesso a vetor.
  ///
  /// `Int16List` e não `Int32List` porque é o que o arquivo traz e o que o
  /// aparelho aguenta: 3,73 MB para as cinco. A leitura devolve `int` de 64 bits
  /// já com sinal, então somar nove delas não estoura.
  final Map<String, Int16List> tabelas;

  /// A geometria lida do arquivo, na ordem em que a avaliação soma.
  final List<JanelaDePadroes> janelas;

  /// Os quatro coeficientes de material, em centésimos.
  final Int16List material;

  /// O intercepto, em centésimos. É a vantagem de **ter a vez** — e é por isso
  /// que a nota treinada não é antissimétrica (ver [avaliarTreinadoAbsoluto]).
  final int vies;

  /// Quantos centésimos de pedra vale um logit do modelo.
  ///
  /// Não entra na conta da nota, que já está em centésimos. Viaja no arquivo para
  /// permitir voltar aos logits e, deles, à probabilidade de vitória — que é o
  /// que uma tela de análise mostraria.
  final double escalaLogitoParaCentesimos;

  /// A modalidade em que estes pesos foram treinados.
  ///
  /// Carregar os pesos das brasileiras num motor de anglo-americanas não daria
  /// erro nenhum. É por isso que o identificador viaja com os pesos: quem carrega
  /// pode comparar com o regulamento em uso e recusar.
  final String regulamento;

  /// Uma tabela pré-resolvida por janela, para o laço da avaliação não fazer
  /// busca em `Map` por posição avaliada.
  ///
  /// Parece detalhe e não é: a busca chama a avaliação centenas de milhares de
  /// vezes por segundo, e nove `tabelas[janela.tabela]` por chamada seriam nove
  /// cálculos de hash de String no caminho mais quente do motor. Resolver uma vez
  /// na carga é o mesmo truque das tabelas por casa da avaliação manual.
  final List<Int16List> _tabelaDaJanela;

  PesosDosPadroes._({
    required this.tabelas,
    required this.janelas,
    required this.material,
    required this.vies,
    required this.escalaLogitoParaCentesimos,
    required this.regulamento,
  }) : _tabelaDaJanela = [
          for (final janela in janelas) tabelas[janela.tabela]!,
        ];

  /// Quantas entradas de tabela têm peso. Serve a relatório e à bancada.
  int contarEntradasNaoNulas() {
    var total = 0;
    for (final tabela in tabelas.values) {
      for (final valor in tabela) {
        if (valor != 0) total++;
      }
    }
    return total;
  }
}

/// Um cursor sobre os bytes, que avança sozinho.
///
/// A alternativa seria um punhado de `getInt32(deslocamento)` com os
/// deslocamentos calculados à mão — mais curto e muito mais frágil. Este cursor é
/// o gêmeo da classe `_Leitor` do Python, e os dois lados leem o arquivo com o
/// mesmo desenho: é o que permite acrescentar um campo sem recontar cinquenta
/// posições em duas linguagens.
class _Leitor {
  final ByteData _dados;
  final Uint8List _bytes;
  int posicao = 0;

  _Leitor(Uint8List bytes)
      : _bytes = bytes,
        // `offsetInBytes` e `lengthInBytes`: o `Uint8List` pode ser uma *janela*
        // sobre um buffer maior (é o caso do `ByteData` do `rootBundle`). Ignorar
        // isso leria a partir do começo do buffer e não da lista recebida.
        _dados = ByteData.view(
            bytes.buffer, bytes.offsetInBytes, bytes.lengthInBytes);

  void _exigir(int quantos) {
    if (posicao + quantos > _bytes.length) {
      throw ArquivoDePesosInvalido(
          'o arquivo acabou antes do esperado (queria $quantos bytes na posição '
          '$posicao, e ele tem ${_bytes.length})');
    }
  }

  int uint8() {
    _exigir(1);
    return _dados.getUint8(posicao++);
  }

  int uint16() {
    _exigir(2);
    final valor = _dados.getUint16(posicao, Endian.little);
    posicao += 2;
    return valor;
  }

  int int16() {
    _exigir(2);
    final valor = _dados.getInt16(posicao, Endian.little);
    posicao += 2;
    return valor;
  }

  int int32() {
    _exigir(4);
    final valor = _dados.getInt32(posicao, Endian.little);
    posicao += 4;
    return valor;
  }

  int uint32() {
    _exigir(4);
    final valor = _dados.getUint32(posicao, Endian.little);
    posicao += 4;
    return valor;
  }

  int int64() {
    _exigir(8);
    final valor = _dados.getInt64(posicao, Endian.little);
    posicao += 8;
    return valor;
  }

  double float32() {
    _exigir(4);
    final valor = _dados.getFloat32(posicao, Endian.little);
    posicao += 4;
    return valor;
  }

  Uint8List bytes(int quantos) {
    _exigir(quantos);
    // `sublist` e não `Uint8List.view`: a cópia é minúscula (8 casas, um nome de
    // tabela) e desatrelar do buffer original evita que o arquivo inteiro fique
    // vivo na memória por causa de uma fatia de oito bytes.
    final fatia = _bytes.sublist(posicao, posicao + quantos);
    posicao += quantos;
    return fatia;
  }

  /// Um bloco `uint16` de tamanho seguido dos bytes do texto, em UTF-8.
  String texto() => utf8.decode(bytes(uint16()));
}

/// Lê os pesos a partir dos bytes do arquivo, conferindo tudo que pode conferir.
///
/// São cinco recusas, e cada uma existe porque o erro que ela pega daria uma
/// avaliação **plausível e errada** — a categoria de defeito mais cara deste
/// projeto:
///
/// 1. **magia diferente** — não é este formato, ou veio corrompido em modo texto;
/// 2. **versão diferente** — é este formato, em outro arranjo de campos;
/// 3. **geometria diferente** — a tabela foi treinada com um recorte de tabuleiro
///    que este código não usa;
/// 4. **contagem de entradas** diferente da anunciada no cabeçalho;
/// 5. **soma dos valores** diferente da anunciada — pega byte-order trocada e
///    truncamento, os dois erros que não mudam o *tamanho* do arquivo.
PesosDosPadroes lerPesosDosPadroes(Uint8List cru) {
  final leitor = _Leitor(cru);

  final magia = leitor.bytes(magiaDosPesos.length);
  for (var indice = 0; indice < magiaDosPesos.length; indice++) {
    if (magia[indice] != magiaDosPesos[indice]) {
      throw ArquivoDePesosInvalido(
          'magia $magia — esperava $magiaDosPesos. Se a diferença for um '
          'carriage return, o arquivo foi transferido em modo texto.');
    }
  }

  final versao = leitor.uint16();
  if (versao != versaoDosPesos) {
    throw ArquivoDePesosInvalido(
        'versão de layout $versao; este código lê a $versaoDosPesos');
  }

  final estados = leitor.uint16();
  final casasNaJanela = leitor.uint16();
  final numeroDeTabelas = leitor.uint16();
  final numeroDeJanelas = leitor.uint16();
  final entradas = leitor.uint32();
  if (estados != estadosPorCasa ||
      casasNaJanela != casasPorJanela ||
      entradas != entradasPorTabela) {
    throw ArquivoDePesosInvalido(
        'geometria do arquivo ($estados estados, $casasNaJanela casas por '
        'janela, $entradas entradas) diferente da deste código '
        '($estadosPorCasa, $casasPorJanela, $entradasPorTabela)');
  }

  final escala = leitor.float32();
  final vies = leitor.int16();
  final material = Int16List(colunasDeMaterial);
  for (var coluna = 0; coluna < colunasDeMaterial; coluna++) {
    material[coluna] = leitor.int16();
  }

  final totalAnunciado = leitor.int32();
  final somaAnunciada = leitor.int64();
  final regulamento = utf8.decode(leitor.bytes(leitor.uint16()));

  final janelas = <JanelaDePadroes>[];
  for (var numero = 0; numero < numeroDeJanelas; numero++) {
    final identificador = leitor.texto();
    final tabela = leitor.texto();
    final inverte = leitor.uint8() != 0;
    janelas.add(JanelaDePadroes(
      identificador: identificador,
      casas: leitor.bytes(casasPorJanela),
      tabela: tabela,
      inverteOPontoDeVista: inverte,
    ));
  }

  final tabelas = <String, Int16List>{};
  var totalLido = 0;
  var somaLida = 0;
  for (var numero = 0; numero < numeroDeTabelas; numero++) {
    final nome = leitor.texto();
    final quantas = leitor.int32();
    // A expansão do esparso para o denso, feita uma vez na carga: o aparelho paga
    // 3,73 MB de RAM e ganha leitura em tempo constante pelo resto da partida.
    final tabela = Int16List(entradasPorTabela);
    for (var entrada = 0; entrada < quantas; entrada++) {
      final indice = leitor.int32();
      final valor = leitor.int16();
      if (indice < 0 || indice >= entradasPorTabela) {
        throw ArquivoDePesosInvalido(
            'a tabela $nome traz o índice $indice, fora de '
            '0..${entradasPorTabela - 1}');
      }
      tabela[indice] = valor;
      somaLida += valor;
    }
    totalLido += quantas;
    tabelas[nome] = tabela;
  }

  if (totalLido != totalAnunciado) {
    throw ArquivoDePesosInvalido(
        'o cabeçalho anuncia $totalAnunciado entradas não nulas e o corpo traz '
        '$totalLido');
  }
  if (somaLida != somaAnunciada) {
    throw ArquivoDePesosInvalido(
        'a soma de verificação não bate: o cabeçalho diz $somaAnunciada e os '
        'valores somam $somaLida');
  }

  // Uma janela cuja tabela não veio no arquivo daria `null` no laço da avaliação
  // — melhor descobrir aqui, com o nome da janela na mensagem.
  for (final janela in janelas) {
    if (!tabelas.containsKey(janela.tabela)) {
      throw ArquivoDePesosInvalido(
          'a janela ${janela.identificador} lê a tabela ${janela.tabela}, que '
          'não veio no arquivo');
    }
  }

  return PesosDosPadroes._(
    tabelas: tabelas,
    janelas: janelas,
    material: material,
    vies: vies,
    escalaLogitoParaCentesimos: escala,
    regulamento: regulamento,
  );
}

/// O dígito de 0 a 4 que uma casa contribui ao índice da janela.
///
/// "Minha" e "dele" são relativos ao [pontoDeVista], e não às cores absolutas. É
/// isso que faz a mesma tabela servir aos dois lados — sem isso seriam dez
/// tabelas, cada uma vendo metade dos exemplos de treino.
int estadoDaCasa(Tabuleiro tabuleiro, int casa, int pontoDeVista) {
  final conteudo = tabuleiro.ler(casa);
  if (conteudo == vazia) return 0;
  final minhas = pontoDeVista == brancas;
  switch (conteudo) {
    case pedraBranca:
      return minhas ? 1 : 3;
    case damaBranca:
      return minhas ? 2 : 4;
    case pedraPreta:
      return minhas ? 3 : 1;
    default: // damaPreta
      return minhas ? 4 : 2;
  }
}

/// A fotografia desta janela como número de 0 a 390.624.
///
/// Um número na base 5, com a primeira casa da janela como dígito **menos**
/// significativo: `índice = d₀·5⁰ + d₁·5¹ + … + d₇·5⁷`.
///
/// O laço vai da última casa para a primeira multiplicando por 5 a cada passo
/// (regra de Horner), o que dá o mesmo resultado sem calcular potência nenhuma —
/// e é exatamente o laço que o Python executa.
int indiceDaJanela(
    Tabuleiro tabuleiro, JanelaDePadroes janela, int pontoDeVista) {
  final vista = janela.inverteOPontoDeVista
      ? (pontoDeVista == brancas ? pretas : brancas)
      : pontoDeVista;
  var indice = 0;
  for (var posicao = janela.casas.length - 1; posicao >= 0; posicao--) {
    indice = indice * estadosPorCasa +
        estadoDaCasa(tabuleiro, janela.casas[posicao], vista);
  }
  return indice;
}

/// A nota em centésimos de pedra, do ponto de vista pedido.
///
/// A conta inteira: **o viés, mais uma leitura de tabela por janela, mais o
/// material.** Nove somas e quatro multiplicações por posição.
int avaliarTreinadoDoPontoDeVista(
    PesosDosPadroes pesos, Tabuleiro tabuleiro, int pontoDeVista) {
  var total = pesos.vies;

  final janelas = pesos.janelas;
  for (var numero = 0; numero < janelas.length; numero++) {
    final janela = janelas[numero];
    total += pesos._tabelaDaJanela[numero]
        [indiceDaJanela(tabuleiro, janela, pontoDeVista)];
  }

  // O material numa passada só pelas 32 casas. Contar por `casasDe` alocaria uma
  // lista por avaliação, e o coletor de lixo apareceria na medição da bancada —
  // foi o que aconteceu com a versão anterior da avaliação manual.
  var minhasPedras = 0;
  var minhasDamas = 0;
  var pedrasDele = 0;
  var damasDele = 0;
  final souBrancas = pontoDeVista == brancas;
  for (var casa = 1; casa <= nCasas; casa++) {
    switch (tabuleiro.casas[casa - 1]) {
      case pedraBranca:
        souBrancas ? minhasPedras++ : pedrasDele++;
      case damaBranca:
        souBrancas ? minhasDamas++ : damasDele++;
      case pedraPreta:
        souBrancas ? pedrasDele++ : minhasPedras++;
      case damaPreta:
        souBrancas ? damasDele++ : minhasDamas++;
    }
  }

  total += pesos.material[0] * minhasPedras +
      pesos.material[1] * minhasDamas +
      pesos.material[2] * pedrasDele +
      pesos.material[3] * damasDele;
  return total;
}

/// A nota **do ponto de vista de quem tem a vez** — o que a busca negamax espera.
///
/// Mesma assinatura e mesma convenção de sinal de `avaliacao_damas.avaliar`, e é
/// isso que permite a arena da etapa 9 trocar uma pela outra sem mexer na busca.
int avaliarTreinado(PesosDosPadroes pesos, Tabuleiro tabuleiro) =>
    avaliarTreinadoDoPontoDeVista(pesos, tabuleiro, tabuleiro.vez);

/// A nota sempre do ponto de vista das **brancas**, para log e relatório.
///
/// ⚠️ **Cuidado que não existe na avaliação manual: a treinada não é
/// antissimétrica.** Negar a nota de quem tem a vez não dá a nota do outro lado,
/// porque o viés é a vantagem de *ter a vez* e não muda de sinal com a cor.
///
/// As duas notas são coerentes **dentro** de um lance, que é o que log e
/// relatório precisam. Comparar notas absolutas de posições com vez diferente
/// carrega o dobro do viés — poucos centésimos, e está escrito aqui para não ser
/// descoberto como "bug" seis meses depois.
int avaliarTreinadoAbsoluto(PesosDosPadroes pesos, Tabuleiro tabuleiro) {
  final nota = avaliarTreinado(pesos, tabuleiro);
  return tabuleiro.vez == brancas ? nota : -nota;
}
