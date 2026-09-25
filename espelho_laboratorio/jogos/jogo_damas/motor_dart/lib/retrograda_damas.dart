/// Análise retrógrada em Dart: o resultado **exato** de todo final com poucas
/// peças, rápido o bastante para passar de 3 peças.
///
/// Port de `../tablebase/retrograda_damas.py`, e como sempre neste projeto: **o
/// Python é a referência**, este é a versão rápida. O teste
/// `testes/test_paridade_dart_damas.py` compara as duas bases **byte a byte** —
/// é a escrituração dupla que já pegou mais de um erro aqui.
///
/// A ideia, que inverte o sentido normal de pensar sobre um jogo
/// --------------------------------------------------------------
/// Um motor de busca olha para a frente e chuta. Aqui se olha para **trás** e se
/// sabe:
///
/// 1. **Comece pelo que já está decidido.** Quem não tem lance legal perdeu.
/// 2. **Ande um lance para trás.** Uma posição é **vitória** se existe *algum*
///    lance meu que leva a uma posição já marcada como derrota do adversário. É
///    **derrota** se *todos* os meus lances levam a vitórias dele.
/// 3. **Repita até nada mais mudar.** O que sobrou sem marca é **empate**.
///
/// O que este port muda além da linguagem
/// --------------------------------------
/// A tradução literal do Python daria talvez 7× de ganho — e 7× não resolve. O
/// que resolve são três mudanças de estrutura, todas com o mesmo tema: **tirar
/// alocação do laço quente**.
///
/// 1. **Um tabuleiro só.** [Reconstrutor] monta cada posição no mesmo objeto, em
///    vez de criar um por índice.
/// 2. **Fatia identificada por número, não por nome.** A consulta ao sucessor
///    caía num `Map<String, …>`, e montar a String custava mais que a consulta.
///    Ver [codigoDeMaterial].
/// 3. **A lista de pendentes encolhe.** O laço de camadas do Python varre todos
///    os índices toda vez; aqui a lista dos ainda-indecisos é compactada a cada
///    camada, e as camadas fundas custam quase nada.
///
/// Uma simplificação que precisa ser justificada
/// ---------------------------------------------
/// O Python guarda a lista **inteira** de sucessores externos de cada posição.
/// Aqui ela é reduzida a dois números: a menor distância entre os sucessores
/// externos que são **derrota**, e a maior entre os que são **vitória**.
///
/// Isso não perde informação, e o motivo é a monotonia das camadas:
///
/// - **Vitória** dispara na camada em que existe um sucessor-derrota àquela
///   distância. A primeira vez que isso acontece é na *menor* dessas distâncias
///   — e nesse instante a posição sai da lista. Distâncias maiores nunca são
///   consultadas.
/// - **Derrota** exige que *todos* os sucessores sejam vitória; então basta saber
///   se algum externo **não** é (o que bloqueia a derrota para sempre) e, se
///   todos forem, qual a maior distância entre eles.
///
/// O que garante que o raciocínio está certo não é ele estar escrito aqui: é a
/// base em Dart bater byte a byte com a base em Python.
library;

import 'dart:typed_data';

import 'empates_declarados_damas.dart';
import 'indice_damas.dart';
import 'regras_damas.dart';
import 'tabuleiro_damas.dart';

/// Devolvido por [BaseDeFinais.consultar] quando a posição tem material demais
/// para estar na base.
///
/// ⚠️ Quem chama **precisa** tratar: confundir "fora da base" com "empate" faria
/// o motor achar que toda posição de meio-jogo é equilibrada.
const int foraDaBase = -1;

/// Marca, em `_maxVitoriaExterna`, que a derrota está bloqueada: existe um
/// sucessor externo que não é vitória do adversário.
const int _externoBloqueiaADerrota = -2;

// ---------------------------------------------------------------------------
// Vetores que crescem
// ---------------------------------------------------------------------------

/// Um `Int32List` que cresce, dobrando de tamanho.
///
/// Existe porque a alternativa — `List<int>` — guarda cada número como elemento
/// de lista genérica, e numa fatia de dezenas de milhões de posições a diferença
/// entre 4 bytes e 8 bytes por sucessor decide se a fatia cabe na memória.
class _VetorInt32 {
  Int32List _dados = Int32List(1024);
  int _quantos = 0;

  int get quantos => _quantos;

  void adicionar(int valor) {
    if (_quantos == _dados.length) {
      final maior = Int32List(_dados.length * 2);
      maior.setRange(0, _dados.length, _dados);
      _dados = maior;
    }
    _dados[_quantos++] = valor;
  }

  int operator [](int i) => _dados[i];

  /// Uma **vista** dos elementos preenchidos, do tamanho exato.
  ///
  /// Vista e não cópia de propósito: copiar centenas de milhões de sucessores
  /// dobraria o pico de memória bem no pior momento. O preço é a folga alocada
  /// na última duplicação continuar presa até a fatia acabar — o que é aceitável
  /// porque o vetor morre junto com ela.
  Int32List compactar() => Int32List.sublistView(_dados, 0, _quantos);
}

// ---------------------------------------------------------------------------
// A base
// ---------------------------------------------------------------------------

/// As fatias resolvidas, prontas para consulta.
///
/// Guarda dois vetores por fatia:
///
/// - **valores** — vitória, derrota ou empate. Um byte por posição, quando dois
///   bits bastariam; o empacotamento é da etapa 8, quando o tamanho passa a
///   importar.
/// - **distâncias** — em quantos meios-lances a partida acaba com jogo perfeito.
///   Existe porque as **regras de empate declarado** (arts. 97 a 100) não
///   perguntam "quem ganha?", perguntam "ganha **em quantos lances?**".
///
/// A indexação é pelo [codigoDeMaterial], não pelo nome: é consulta de laço
/// quente.
class BaseDeFinais {
  final Regulamento regulamento;

  final List<Uint8List?> _valores =
      List<Uint8List?>.filled(totalDeCodigosDeMaterial, null);
  final List<Int16List?> _distancias =
      List<Int16List?>.filled(totalDeCodigosDeMaterial, null);
  final List<Fatia?> _fatias =
      List<Fatia?>.filled(totalDeCodigosDeMaterial, null);

  /// As fatias guardadas, na ordem em que foram resolvidas.
  final List<Fatia> ordem = [];

  BaseDeFinais({this.regulamento = brasileiras});

  void guardar(Fatia fatia, Uint8List valores, Int16List distancias) {
    final codigo = fatia.codigo;
    if (_valores[codigo] == null) ordem.add(fatia);
    _valores[codigo] = valores;
    _distancias[codigo] = distancias;
    _fatias[codigo] = fatia;
  }

  bool tem(Fatia fatia) => _valores[fatia.codigo] != null;

  Uint8List? valoresDe(Fatia fatia) => _valores[fatia.codigo];

  Int16List? distanciasDe(Fatia fatia) => _distancias[fatia.codigo];

  /// O resultado exato desta posição, do ponto de vista de quem tem a vez.
  ///
  /// [foraDaBase] quando a posição tem material demais — e isso vale também para
  /// uma posição de **meio de jogo**, com dezenas de peças. É chamada assim, de
  /// fora do domínio da base, desde a T185 parte 2a; até 2026-08-25 ela
  /// **estourava** nesse caso, apesar desta promessa. Ver [semCodigoDeMaterial].
  int consultar(Tabuleiro tabuleiro, {Indexador? indexador}) {
    final codigo = codigoDaPosicao(tabuleiro);
    if (codigo == semCodigoDeMaterial) return foraDaBase;
    final fatia = _fatias[codigo];
    if (fatia == null) {
      final provisoria = fatiaDoCodigo(codigo);
      if (!provisoria.temOsDoisLados) {
        // Um dos lados ficou sem peça: a partida acabou naquele lance.
        return tabuleiro.casasDe(tabuleiro.vez).isEmpty ? derrota : vitoria;
      }
      return foraDaBase;
    }
    final i = (indexador ?? Indexador()).indiceEm(fatia, tabuleiro);
    return _valores[codigo]![i];
  }

  /// Em quantos meios-lances a partida acaba, com jogo perfeito.
  ///
  /// [semDistancia] quando a base não sabe — inclusive para material que não tem
  /// código, pelo mesmo motivo de [consultar].
  int distanciaDe(Tabuleiro tabuleiro, {Indexador? indexador}) {
    final codigo = codigoDaPosicao(tabuleiro);
    if (codigo == semCodigoDeMaterial) return semDistancia;
    final fatia = _fatias[codigo];
    if (fatia == null) return semDistancia;
    return _distancias[codigo]![
        (indexador ?? Indexador()).indiceEm(fatia, tabuleiro)];
  }

  int get totalDePosicoes {
    var total = 0;
    for (final fatia in ordem) {
      total += _valores[fatia.codigo]!.length;
    }
    return total;
  }

  /// Quantas posições de cada resultado a base tem, somando todas as fatias.
  /// Indexado por [derrota], [empate], [vitoria].
  List<int> contarResultados() {
    final contagem = List<int>.filled(3, 0);
    for (final fatia in ordem) {
      for (final valor in _valores[fatia.codigo]!) {
        contagem[valor]++;
      }
    }
    return contagem;
  }
}

/// O que sai de [resolverFatia].
class FatiaResolvida {
  final Uint8List valores;
  final Int16List distancias;

  /// Quantas camadas de distância o laço de ponto fixo percorreu.
  final int camadas;

  /// Quantos índices caíram no vão da numeração (nunca são consultados).
  final int vaos;

  const FatiaResolvida(this.valores, this.distancias, this.camadas, this.vaos);
}

/// Resolve uma fatia inteira, supondo as menores já resolvidas.
///
/// Devolve um resultado e uma distância por índice, do ponto de vista de **quem
/// tem a vez** naquela posição. A distância é em meios-lances até o fim da
/// partida, e é [semDistancia] no empate.
FatiaResolvida resolverFatia(
  Fatia fatia,
  BaseDeFinais base, {
  Regulamento regulamento = brasileiras,
}) {
  final tamanho = fatia.tamanho;
  final valores = Uint8List(tamanho)..fillRange(0, tamanho, desconhecido);
  final distancias = Int16List(tamanho)..fillRange(0, tamanho, semDistancia);

  final reconstrutor = Reconstrutor(fatia);
  final indexador = Indexador();
  final desfazer = DesfazerLance();
  final tabuleiro = reconstrutor.tabuleiro;

  // Os pendentes: os índices que têm lance legal e ainda não têm resposta.
  final pendIndice = _VetorInt32();
  final pendMinDerrotaExterna = _VetorInt32();
  final pendMaxVitoriaExterna = _VetorInt32();
  final pendInicioDosInternos = _VetorInt32();
  final internos = _VetorInt32();

  var vaos = 0;
  var maiorDistancia = -1;

  /// A maior distância que chega de FORA da fatia — o teto de verdade do laço
  /// de camadas. Ver o critério de parada, adiante, e o bug de 2026-07-28.
  var maiorDistanciaExterna = -1;

  // --- varredura inicial: gera os lances UMA vez ---------------------------
  for (var indice = 0; indice < tamanho; indice++) {
    if (!reconstrutor.reconstruir(indice)) {
      valores[indice] = empate; // vão da numeração: nunca consultado
      vaos++;
      continue;
    }

    final lances = gerarLances(tabuleiro, regulamento);
    if (lances.isEmpty) {
      valores[indice] = derrota; // sem lance legal, perdeu
      distancias[indice] = 0; // a partida acaba aqui mesmo
      if (maiorDistancia < 0) maiorDistancia = 0;
      continue;
    }

    var minDerrotaExterna = -1;
    var maxVitoriaExterna = -1;
    final inicio = internos.quantos;

    for (final lance in lances) {
      aplicarNoLugar(tabuleiro, lance, desfazer);
      final codigoAlvo = codigoDaPosicao(tabuleiro);

      if (codigoAlvo == fatia.codigo) {
        internos.adicionar(indexador.indiceEm(fatia, tabuleiro));
        desfazerNoLugar(tabuleiro, desfazer);
        continue;
      }

      final resultado = base.consultar(tabuleiro, indexador: indexador);
      if (resultado == foraDaBase) {
        desfazerNoLugar(tabuleiro, desfazer);
        throw StateError(
          'a fatia ${fatiaDoCodigo(codigoAlvo).nome} não estava resolvida '
          'quando ${fatia.nome} precisou dela — ordem de dependência quebrada',
        );
      }
      final distancia = _distanciaExterna(base, tabuleiro, resultado,
          codigoAlvo: codigoAlvo, indexador: indexador);
      desfazerNoLugar(tabuleiro, desfazer);

      if (distancia > maiorDistanciaExterna) maiorDistanciaExterna = distancia;

      if (resultado == derrota) {
        if (minDerrotaExterna < 0 || distancia < minDerrotaExterna) {
          minDerrotaExterna = distancia;
        }
        maxVitoriaExterna = _externoBloqueiaADerrota;
      } else if (resultado == vitoria) {
        if (maxVitoriaExterna != _externoBloqueiaADerrota &&
            distancia > maxVitoriaExterna) {
          maxVitoriaExterna = distancia;
        }
      } else {
        // Empate externo: quem tem a vez nunca pode estar em derrota total.
        maxVitoriaExterna = _externoBloqueiaADerrota;
      }
    }

    pendIndice.adicionar(indice);
    pendMinDerrotaExterna.adicionar(minDerrotaExterna);
    pendMaxVitoriaExterna.adicionar(maxVitoriaExterna);
    pendInicioDosInternos.adicionar(inicio);
  }
  pendInicioDosInternos.adicionar(internos.quantos); // sentinela do último

  final indices = pendIndice.compactar();
  final minDerrota = pendMinDerrotaExterna.compactar();
  final maxVitoria = pendMaxVitoriaExterna.compactar();
  final inicioDos = pendInicioDosInternos.compactar();
  final sucessoresInternos = internos.compactar();

  // --- propagação POR CAMADA DE DISTÂNCIA ----------------------------------
  //
  // ⚠️ A primeira versão disto (em Python) iterava até o ponto fixo percorrendo
  // os índices em ordem, marcando cada posição assim que a condição batesse. O
  // **resultado** saía certo — o ponto fixo não depende da ordem —, mas a
  // **distância** saía dependente dela: uma vitória podia ser descoberta por um
  // caminho longo antes de o curto existir.
  //
  // Isso apareceu como uma assimetria: fatias espelhadas davam os mesmos
  // resultados e distâncias diferentes. Não era detalhe — os arts. 97 a 100
  // perguntam exatamente "ganha em quantos lances?", e uma distância inflada
  // declara empate onde não há.
  //
  // A correção é processar em camadas: primeiro tudo que se decide em 1
  // meio-lance, depois em 2, e assim por diante. Aí a primeira marca que uma
  // posição recebe é, por construção, a de distância mínima.
  final ativos = Int32List(indices.length);
  for (var i = 0; i < ativos.length; i++) {
    ativos[i] = i;
  }
  var quantosAtivos = ativos.length;

  var camada = 0;
  while (true) {
    var mudou = false;
    var escrita = 0;

    for (var leitura = 0; leitura < quantosAtivos; leitura++) {
      final slot = ativos[leitura];
      final primeiro = inicioDos[slot];
      final ultimo = inicioDos[slot + 1];

      // Vitória em `camada + 1`: existe um sucessor que é derrota EXATAMENTE em
      // `camada`. Como as camadas anteriores já foram esgotadas, esta é a
      // vitória mais curta possível para esta posição.
      var vence = minDerrota[slot] == camada;
      if (!vence) {
        for (var k = primeiro; k < ultimo; k++) {
          final i = sucessoresInternos[k];
          if (valores[i] == derrota && distancias[i] == camada) {
            vence = true;
            break;
          }
        }
      }
      if (vence) {
        valores[indices[slot]] = vitoria;
        distancias[indices[slot]] = camada + 1;
        maiorDistancia = camada + 1;
        mudou = true;
        continue; // sai da lista de ativos
      }

      // Derrota em `camada + 1`: **todos** os sucessores já são vitória, e o
      // mais distante deles está exatamente em `camada` — quem perde resiste o
      // máximo que puder.
      if (maxVitoria[slot] != _externoBloqueiaADerrota) {
        var maximo = maxVitoria[slot];
        var todosVitoria = true;
        for (var k = primeiro; k < ultimo; k++) {
          final i = sucessoresInternos[k];
          if (valores[i] != vitoria) {
            todosVitoria = false;
            break;
          }
          if (distancias[i] > maximo) maximo = distancias[i];
        }
        if (todosVitoria && maximo == camada) {
          valores[indices[slot]] = derrota;
          distancias[indices[slot]] = camada + 1;
          maiorDistancia = camada + 1;
          mudou = true;
          continue;
        }
      }

      ativos[escrita++] = slot;
    }
    quantosAtivos = escrita;

    camada++;
    // Uma camada vazia não encerra sozinha: uma derrota longa pode depender de
    // vitórias ainda mais longas. Só se para quando nada mais é decidível.
    //
    // ⚠️ CORRIGIDO EM 2026-07-28 — mesmo bug do Python, porque o port foi fiel.
    // O teto olhava só as distâncias já atribuídas DENTRO da fatia e ignorava as
    // que chegam de fora. Fatia cujas posições internas se decidem em ~16
    // camadas, mas com sucessores externos a 32 ou 40 meios-lances do fim,
    // parava na camada 17 — e as posições que dependiam deles viravam EMPATE no
    // fecho abaixo. Base que responde "empate" com confiança sobre posição
    // ganha: o pior erro possível deste projeto, e ele não dá exceção nenhuma.
    final teto =
        maiorDistancia > maiorDistanciaExterna ? maiorDistancia : maiorDistanciaExterna;
    if (!mudou && camada > teto) break;
    if (quantosAtivos == 0) break;
    if (camada > tamanho) break; // trava de segurança
  }

  // O que sobrou sem marca é empate: ninguém força nada.
  for (var indice = 0; indice < tamanho; indice++) {
    if (valores[indice] == desconhecido) valores[indice] = empate;
  }

  return FatiaResolvida(valores, distancias, camada, vaos);
}

/// A distância de um sucessor que caiu em outra fatia.
///
/// Quando a captura zerou um dos lados, a fatia nem existe na base: a partida
/// acabou naquele lance, e a distância é 0.
int _distanciaExterna(
  BaseDeFinais base,
  Tabuleiro depois,
  int resultado, {
  required int codigoAlvo,
  required Indexador indexador,
}) {
  if (resultado == empate) return semDistancia;
  if (!fatiaDoCodigo(codigoAlvo).temOsDoisLados) return 0;
  return base.distanciaDe(depois, indexador: indexador);
}

/// Relato do que uma fatia custou. Vira linha de tabela e alimenta as figuras.
class RelatorioDaFatia {
  final Fatia fatia;
  final int indices;
  final int vaos;
  final int camadas;
  final int vitorias;
  final int derrotas;
  final int empates;
  final int declaradosEmpate;
  final Duration duracao;

  const RelatorioDaFatia({
    required this.fatia,
    required this.indices,
    required this.vaos,
    required this.camadas,
    required this.vitorias,
    required this.derrotas,
    required this.empates,
    required this.declaradosEmpate,
    required this.duracao,
  });

  /// Índices por segundo — a medida que decide se a base cabe no tempo de um
  /// ser humano. É ela que aparece na figura 34.
  double get indicesPorSegundo =>
      duracao.inMicroseconds == 0 ? 0 : indices * 1e6 / duracao.inMicroseconds;

  Map<String, Object> paraMapa() => {
        'fatia': fatia.nome,
        'descricao': fatia.toString(),
        'indices': indices,
        'vaos': vaos,
        'camadas': camadas,
        'vitorias': vitorias,
        'derrotas': derrotas,
        'empates': empates,
        'declarados_empate': declaradosEmpate,
        'segundos': duracao.inMicroseconds / 1e6,
        'indices_por_segundo': indicesPorSegundo,
      };
}

/// Resolve todas as fatias com até [totalDePecas] peças, na ordem de dependência.
///
/// [aplicarRegrasDeEmpate] diz se os arts. 97 a 100 entram. O padrão segue o
/// regulamento — **ligado nas brasileiras, desligado nas anglo-americanas**, que
/// não têm esses artigos. Passar explicitamente serve para medir o que a regra
/// muda, comparando as duas bases.
///
/// A aplicação acontece **fatia a fatia, logo depois de resolvê-la**, e não no
/// fim. Tem de ser assim: as fatias grandes decidem consultando o resultado das
/// pequenas, e uma regra que chegasse atrasada as deixaria decidindo em cima de
/// vitórias que o regulamento não reconhece.
BaseDeFinais construirBase(
  int totalDePecas, {
  Regulamento regulamento = brasileiras,
  bool? aplicarRegrasDeEmpate,
  void Function(RelatorioDaFatia relatorio, Uint8List valores,
          Int16List distancias)?
      aoResolverFatia,
}) {
  // O padrão sai do CAMPO do regulamento, não do nome dele: até 2026-07-29 era
  // `identificador == 'brasileira'`, e a Damas de Casa teria recebido uma base
  // sem os empates declarados — uma base que aponta vitória onde a modalidade
  // manda empatar.
  final comRegras =
      aplicarRegrasDeEmpate ?? regulamento.empatesDeclaradosPorPosicao;
  final base = BaseDeFinais(regulamento: regulamento);

  for (final fatia in fatiasAte(totalDePecas)) {
    final relogio = Stopwatch()..start();
    final resolvida = resolverFatia(fatia, base, regulamento: regulamento);
    var declarados = 0;
    if (comRegras) {
      declarados = aplicarEmpatesDeclarados(
          fatia, resolvida.valores, resolvida.distancias);
    }
    base.guardar(fatia, resolvida.valores, resolvida.distancias);
    relogio.stop();

    if (aoResolverFatia != null) {
      var vitorias = 0, derrotas = 0, empates = 0;
      for (final valor in resolvida.valores) {
        if (valor == vitoria) {
          vitorias++;
        } else if (valor == derrota) {
          derrotas++;
        } else {
          empates++;
        }
      }
      aoResolverFatia(
          RelatorioDaFatia(
        fatia: fatia,
        indices: fatia.tamanho,
        vaos: resolvida.vaos,
        camadas: resolvida.camadas,
        vitorias: vitorias,
        derrotas: derrotas,
        empates: empates,
        declaradosEmpate: declarados,
        duracao: relogio.elapsed,
      ),
          resolvida.valores,
          resolvida.distancias);
    }
  }
  return base;
}
