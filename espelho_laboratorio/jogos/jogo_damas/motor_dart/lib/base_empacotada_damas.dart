// A BASE DE FINAIS NO FORMATO DO APP — lida do disco, fatia por fatia, e só
// quando alguém pergunta.
//
// ── O que este arquivo é ───────────────────────────────────────────────────
//
// Um [OraculoDeFinais] que responde a partir da pasta que
// `motor_dart/bin/empacotar_base_damas.dart` grava — a mesma que viaja dentro
// do app. Do lado de fora ele é idêntico ao [OraculoEmMemoria]: as mesmas duas
// perguntas, as mesmas respostas.
//
// ── ⚠️ Por que ele está no motor espelhado, e o outro não estava ───────────
//
// Até 27/08/2026 quem lia esta base morava em `damas/tablebase/`, no app, e
// falava com o `AssetBundle` do Flutter. Isso bastava enquanto **só a tela**
// perguntava à base (a consulta na raiz, T185 parte 2a).
//
// O *probing* mudou o quadro: quem pergunta agora é `busca_damas.dart`, que é
// **arquivo espelhado** — cópia byte-idêntica do laboratório. Um arquivo do
// motor não pode importar de uma pasta que só existe no app, e o laboratório
// precisa ler exatamente o **mesmo** asset que o aparelho lê, ou o cadeado de
// equivalência (`conferir_equivalencia_com_rust.dart`) estaria comparando dois
// motores que leem bases diferentes.
//
// Por isso a leitura é de **disco**, e não de `AssetBundle`:
//
//   • no laboratório, a pasta é a do repositório do app;
//   • no aparelho, é a pasta de suporte para onde o app **extraiu** o asset uma
//     vez (`tablebase/extrair_base_damas.dart`);
//   • no motor Rust, é a mesma pasta, aberta com `std::fs` — ver
//     `motor_rust/src/base_finais.rs`.
//
// Uma fonte, um formato, três leitores que têm obrigação de concordar.
//
// ── ⚠️ Por que TUDO aqui é síncrono ────────────────────────────────────────
//
// Porque a consulta acontece **dentro da árvore de busca**, milhares de vezes
// por lance. Um `Future` ali contaminaria `_negamax` inteiro, e um `await` por
// nó custaria mais que a busca que ele pretende poupar.
//
// ── As duas preguiças, e o motivo de cada uma ──────────────────────────────
//
// **1. O arquivo só é lido na primeira pergunta daquela fatia.** A busca roda
// num isolate novo a cada lance; ler as 46 fatias da modalidade (2,4 MB) em
// toda jogada custaria o disco inteiro para usar duas ou três delas.
//
// **2. Aberta uma vez, a fatia não volta a fechar.** Quem perguntou uma vez
// costuma perguntar de novo no nó seguinte. O pior caso é conhecido e não é
// perigoso: uma busca que passeasse por todas as fatias abriria 21,8 MB — muito,
// mas é o número de uma imagem grande, não o de um vazamento.
library;

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'espelho_damas.dart';
import 'indice_damas.dart';
import 'oraculo_de_finais_damas.dart';
import 'regras_damas.dart';
import 'retrograda_damas.dart';
import 'tabuleiro_damas.dart';

/// Quantos bytes um vetor de distâncias ocupa: 2 por índice (`int16`).
const int bytesPorDistancia = 2;

/// Algo no que foi lido não bate com o que a numeração do motor espera.
///
/// É sempre **defeito de operação, não de usuário**: uma base gravada por outra
/// versão da indexação, um arquivo truncado, um regulamento trocado. Por isso a
/// mensagem diz o arquivo e os dois números, e não só "erro ao carregar".
class BaseDeFinaisInvalida implements Exception {
  final String mensagem;

  const BaseDeFinaisInvalida(this.mensagem);

  @override
  String toString() => 'BaseDeFinaisInvalida: $mensagem';
}

/// Uma linha do `manifesto.json`: uma fatia gravada e quantos índices ela tem.
class EntradaDeFatia {
  /// O nome da fatia, no formato de quatro dígitos `pb db pp dp` (pedras
  /// brancas, damas brancas, pedras pretas, damas pretas) — o mesmo que
  /// [Fatia.nome] produz. Ex.: `0101` é "1 dama × 1 dama".
  final String nome;

  /// Quantos índices a fatia tem. Serve de **conferência dupla**: tem de bater
  /// com o [Fatia.tamanho] calculado pelo motor. Se não bater, a base foi
  /// gravada por outra versão da numeração e **nenhum** byte dela vale — e é
  /// melhor descobrir isso antes de ler 38 MB do que depois.
  final int indices;

  const EntradaDeFatia({required this.nome, required this.indices});
}

/// O `manifesto.json` de uma base, já conferido.
class ManifestoDaBase {
  /// O identificador do regulamento (`brasileira`, `anglo`, …).
  final String regulamento;

  /// Quantas peças no total a base cobre (4 ou 5, hoje).
  final int totalDePecas;

  /// Quantas posições a base tem, somando todas as fatias. Vem do manifesto;
  /// serve para relatório, não para decisão.
  final int posicoes;

  /// As fatias gravadas, na ordem do manifesto.
  final List<EntradaDeFatia> fatias;

  const ManifestoDaBase({
    required this.regulamento,
    required this.totalDePecas,
    required this.posicoes,
    required this.fatias,
  });

  /// Lê o manifesto a partir do texto JSON.
  ///
  /// Estoura [BaseDeFinaisInvalida] com o campo que faltou — e não um
  /// `TypeError` de cast, que não diz nada a quem está operando.
  factory ManifestoDaBase.doJson(String texto) {
    final Object? cru;
    try {
      cru = jsonDecode(texto);
    } on FormatException catch (erro) {
      throw BaseDeFinaisInvalida('manifesto.json não é JSON válido: $erro');
    }
    if (cru is! Map<String, Object?>) {
      throw const BaseDeFinaisInvalida(
          'manifesto.json não é um objeto JSON no topo');
    }
    // `mapa` existe só para o Dart enxergar o tipo já promovido dentro da
    // função aninhada abaixo (a promoção do `is!` acima não atravessa closures).
    final mapa = cru;

    // `campo` centraliza a mensagem de erro: sem ele, cada cast daria um
    // `TypeError` cru, e quem lê o log não saberia qual campo faltou.
    T campo<T>(String nome) {
      final valor = mapa[nome];
      if (valor is! T) {
        throw BaseDeFinaisInvalida(
            'manifesto.json: falta o campo "$nome" (ou ele não é $T)');
      }
      return valor;
    }

    final listaCrua = campo<List<Object?>>('fatias');
    final fatias = <EntradaDeFatia>[];
    for (final item in listaCrua) {
      if (item is! Map<String, Object?>) {
        throw const BaseDeFinaisInvalida(
            'manifesto.json: uma entrada de "fatias" não é objeto');
      }
      final nome = item['fatia'];
      final indices = item['indices'];
      if (nome is! String || indices is! int) {
        throw BaseDeFinaisInvalida(
            'manifesto.json: entrada de fatia malformada: $item');
      }
      fatias.add(EntradaDeFatia(nome: nome, indices: indices));
    }

    return ManifestoDaBase(
      regulamento: campo<String>('regulamento'),
      totalDePecas: campo<int>('total_de_pecas'),
      posicoes: campo<int>('posicoes'),
      fatias: fatias,
    );
  }
}

/// Uma fatia como ela está no disco: o caminho dos dois arquivos, e o que já
/// foi aberto.
///
/// Os campos abertos começam `null` e são preenchidos na primeira pergunta.
/// `_tentei…` distingue "ainda não abri" de "abri e não havia" — sem isso, uma
/// base gravada sem distâncias tentaria abrir o arquivo ausente a cada nó.
class _FatiaNoDisco {
  final Fatia fatia;
  final File arquivoDeValores;
  final File arquivoDeDistancias;

  Uint8List? valores;
  bool tenteiOsValores = false;

  Int16List? distancias;
  bool tenteiAsDistancias = false;

  _FatiaNoDisco({
    required this.fatia,
    required this.arquivoDeValores,
    required this.arquivoDeDistancias,
  });
}

/// A base de finais lida da pasta empacotada.
///
/// Construa com [BaseEmpacotada.doDisco]; o construtor é privado porque um
/// objeto meio carregado responderia [foraDaBase] a tudo, e "não sei" é
/// exatamente a resposta que não se quer receber por engano.
class BaseEmpacotada implements OraculoDeFinais {
  /// O regulamento desta base.
  ///
  /// ⚠️ **Não é decoração:** o índice de uma posição é o mesmo em todas as
  /// modalidades, mas o **valor** gravado muda — a anglo tem 28,7% de empates
  /// onde a brasileira tem 43,3%. Ler a base errada devolve uma resposta
  /// plausível e sem relação nenhuma com o jogo em curso.
  final Regulamento regulamento;

  /// Quantas peças a base cobre (4, hoje).
  final int totalDePecas;

  /// As fatias que vieram, pelo código de material.
  ///
  /// Lista indexada por código, e não `Map`: o código é um inteiro pequeno
  /// (0 a 6.560) e isto é consultado milhares de vezes por lance.
  final List<_FatiaNoDisco?> _porCodigo =
      List<_FatiaNoDisco?>.filled(totalDeCodigosDeMaterial, null);

  /// ⚠️ **A primeira queixa encontrada DURANTE a busca — e não um contador.**
  ///
  /// Arquivo truncado, ou tamanho que não bate com a numeração, são situações em
  /// que responder é pior que não responder. Só que estamos no meio da árvore, e
  /// lançar aqui mataria o lance. Então a posição vira [foraDaBase], a queixa
  /// fica gravada, e quem chamou a busca decide o que fazer com ela — no app,
  /// recusar o lance inteiro e jogar sem base.
  ///
  /// O que **não** pode acontecer é a busca seguir usando uma base corrompida em
  /// silêncio: a resposta dela chegaria vestida de certeza absoluta.
  String? queixa;

  BaseEmpacotada._({required this.regulamento, required this.totalDePecas});

  /// Quantas fatias vieram. Serve ao teste e ao diagnóstico.
  int get quantasFatias => _porCodigo.where((f) => f != null).length;

  /// O maior final coberto — é [totalDePecas], e o repasse é de uma linha.
  ///
  /// Quem lê este número é a **busca**, para saber a partir de quantas peças
  /// vale a pena perguntar. Sem ele, o *probing* perguntaria à base em todo nó
  /// da árvore e receberia [foraDaBase] milhões de vezes por lance.
  @override
  int get maximoDePecas => totalDePecas;

  @override
  int consultar(Tabuleiro tabuleiro, {Indexador? indexador}) {
    final codigo = codigoDaPosicao(tabuleiro);
    if (codigo == semCodigoDeMaterial) return foraDaBase;

    // Um lado sem peças: a partida acabou naquele lance, e a resposta sai da
    // regra sem abrir arquivo nenhum. Precisa vir ANTES da busca pela fatia —
    // ela não existe na numeração.
    final fatiaDoCodigoAtual = fatiaDoCodigo(codigo);
    if (!fatiaDoCodigoAtual.temOsDoisLados) {
      return tabuleiro.casasDe(tabuleiro.vez).isEmpty ? derrota : vitoria;
    }

    final alvo = _resolver(tabuleiro, codigo);
    if (alvo == null) return foraDaBase;

    final abertos = _abrirValores(alvo.fatia);
    if (abertos == null) return foraDaBase;

    final i = (indexador ?? Indexador()).indiceEm(alvo.fatia.fatia, alvo.posicao);
    if (i < 0 || i >= abertos.length) {
      _reclamar('índice $i fora do arquivo de valores de ${alvo.fatia.fatia.nome}');
      return foraDaBase;
    }
    return abertos[i];
  }

  @override
  int distanciaDe(Tabuleiro tabuleiro, {Indexador? indexador}) {
    final codigo = codigoDaPosicao(tabuleiro);
    if (codigo == semCodigoDeMaterial) return semDistancia;

    final alvo = _resolver(tabuleiro, codigo);
    if (alvo == null) return semDistancia;

    final abertas = _abrirDistancias(alvo.fatia);
    if (abertas == null) return semDistancia;

    final i = (indexador ?? Indexador()).indiceEm(alvo.fatia.fatia, alvo.posicao);
    if (i < 0 || i >= abertas.length) {
      _reclamar(
          'índice $i fora do arquivo de distâncias de ${alvo.fatia.fatia.nome}');
      return semDistancia;
    }
    return abertas[i];
  }

  /// Em qual fatia guardada esta posição está — a dela, ou a da gêmea.
  ///
  /// Devolve `null` quando nem uma nem outra vieram (base parcial), e isso é
  /// situação legítima: quem chama trata como *"não sei, busque normalmente"*.
  _Alvo? _resolver(Tabuleiro tabuleiro, int codigo) {
    final direta = _porCodigo[codigo];
    if (direta != null) return _Alvo(direta, tabuleiro);

    // A fatia não veio: ou é a metade descartada por simetria, ou a base é
    // parcial. Nos dois casos a pergunta certa é a mesma — a gêmea veio?
    final gemea = espelhar(tabuleiro);
    final codigoDaGemea = codigoDaPosicao(gemea);
    if (codigoDaGemea == semCodigoDeMaterial) return null;

    final espelhada = _porCodigo[codigoDaGemea];
    if (espelhada == null) return null;
    return _Alvo(espelhada, gemea);
  }

  /// Abre (uma vez) os valores desta fatia. `null` se ela não pode ser lida.
  Uint8List? _abrirValores(_FatiaNoDisco f) {
    if (f.tenteiOsValores) return f.valores;
    f.tenteiOsValores = true;

    final bytes = _descomprimir(f.arquivoDeValores);
    if (bytes == null) return null;

    final esperado = f.fatia.tamanho;
    if (bytes.length != esperado) {
      _reclamar('${f.arquivoDeValores.path} tem ${bytes.length} bytes e a '
          'numeração pede $esperado');
      return null;
    }
    f.valores = bytes;
    return bytes;
  }

  /// Abre (uma vez) as distâncias desta fatia. `null` se ela não veio com elas.
  ///
  /// Base gravada sem distâncias é situação legítima — o construtor da base tem
  /// a opção —, e nesse caso quem consulta desiste em vez de escolher "qualquer
  /// vitória", que faria o Magno empurrar peça até os arts. 97-100 declararem
  /// empate.
  Int16List? _abrirDistancias(_FatiaNoDisco f) {
    if (f.tenteiAsDistancias) return f.distancias;
    f.tenteiAsDistancias = true;

    if (!f.arquivoDeDistancias.existsSync()) return null;

    final cru = _descomprimir(f.arquivoDeDistancias);
    if (cru == null) return null;

    final esperado = f.fatia.tamanho;
    if (cru.length != esperado * bytesPorDistancia) {
      _reclamar('${f.arquivoDeDistancias.path} tem ${cru.length} bytes e a '
          'numeração pede ${esperado * bytesPorDistancia}');
      return null;
    }

    // Dois bytes por índice, little-endian e **com sinal** — o mesmo layout que
    // `construir_base_damas.dart` grava e que o motor Rust lê. `ByteData` é a
    // forma de ler bytes crus como números respeitando a ordem declarada.
    final visao = ByteData.sublistView(cru);
    final aberto = Int16List(esperado);
    for (var i = 0; i < esperado; i++) {
      aberto[i] = visao.getInt16(i * bytesPorDistancia, Endian.little);
    }
    f.distancias = aberto;
    return aberto;
  }

  /// Lê um `.gz` inteiro, ou `null` (com queixa) se ele não puder ser lido.
  Uint8List? _descomprimir(File arquivo) {
    try {
      // `GZipCodec.decode` devolve `List<int>`; o motor quer `Uint8List` — e a
      // diferença não é cosmética: uma `List<int>` genérica gasta 8 bytes por
      // entrada onde a tipada gasta 1.
      return Uint8List.fromList(gzip.decode(arquivo.readAsBytesSync()));
    } catch (erro) {
      _reclamar('não li ${arquivo.path}: $erro');
      return null;
    }
  }

  /// Guarda a **primeira** queixa. As seguintes seriam consequência dela.
  void _reclamar(String motivo) => queixa ??= motivo;

  /// Abre a base da pasta [pasta], conferindo que ela é da modalidade certa.
  ///
  /// ⚠️ **Lê só o manifesto.** Os arquivos de fatia ficam fechados até que
  /// alguém pergunte por eles.
  ///
  /// Devolve `null` quando não há base nesta pasta — e isso **não** é erro: um
  /// app construído sem o asset, ou um laboratório sem a base copiada, correm
  /// com busca normal, como sempre correram.
  ///
  /// ⚠️ **Mas LANÇA [BaseDeFinaisInvalida] em base inconsistente**: manifesto de
  /// outra modalidade, fatia com contagem de índices diferente da que a
  /// numeração deste motor gera, fatia não-canônica. Essas são situações em que
  /// responder é pior que não responder — a resposta seria plausível e errada.
  static BaseEmpacotada? doDisco({
    required String pasta,
    required Regulamento regulamento,
  }) {
    final arquivoDoManifesto = File('$pasta/manifesto.json');
    if (!arquivoDoManifesto.existsSync()) return null;

    final manifesto =
        ManifestoDaBase.doJson(arquivoDoManifesto.readAsStringSync());
    if (manifesto.regulamento != regulamento.identificador) {
      throw BaseDeFinaisInvalida(
          'o asset em "$pasta" é da modalidade "${manifesto.regulamento}" e foi '
          'pedido como "${regulamento.identificador}" — o índice é o mesmo, mas '
          'o VALOR de cada posição muda de um regulamento para outro');
    }

    final base = BaseEmpacotada._(
      regulamento: regulamento,
      totalDePecas: manifesto.totalDePecas,
    );

    // As fatias saem de `fatiasAte`, a mesma função que a construção usou.
    // Reconstruí-las a partir do nome (dígito a dígito) seria uma segunda
    // implementação da mesma convenção — e é assim que quem grava e quem lê
    // deixam de concordar.
    final porNome = <String, Fatia>{
      for (final fatia in fatiasAte(manifesto.totalDePecas)) fatia.nome: fatia,
    };

    for (final entrada in manifesto.fatias) {
      final fatia = porNome[entrada.nome];
      if (fatia == null) {
        throw BaseDeFinaisInvalida(
            'o manifesto traz a fatia "${entrada.nome}", que a numeração deste '
            'motor não gera para ${manifesto.totalDePecas} peças');
      }

      // A conferência mais barata do mundo, e a que pega a pior falha: o
      // manifesto diz quantos índices a fatia tem, e o motor calcula o mesmo
      // número por conta própria. Divergiram, a base é de outra numeração.
      if (entrada.indices != fatia.tamanho) {
        throw BaseDeFinaisInvalida(
            'a fatia ${entrada.nome} diz ter ${entrada.indices} índices no '
            'manifesto e ${fatia.tamanho} na numeração deste motor — o asset foi '
            'gravado por outra versão da indexação');
      }

      // ⚠️ Uma fatia não-canônica no manifesto significa que quem empacotou e
      // quem lê discordam sobre qual das gêmeas se guarda. O asset até
      // funcionaria (a fatia está lá), mas a metade que ele acha que descartou
      // estaria faltando — e o defeito só apareceria naquelas posições.
      if (!fatiaEhCanonica(entrada.nome)) {
        throw BaseDeFinaisInvalida(
            'a fatia ${entrada.nome} não é canônica, e o asset só deveria trazer '
            'as canônicas — a gêmea dela é ${nomeDaFatiaGemea(entrada.nome)}. '
            'O empacotador e o leitor discordam sobre qual metade se guarda.');
      }

      base._porCodigo[fatia.codigo] = _FatiaNoDisco(
        fatia: fatia,
        arquivoDeValores: File('$pasta/${entrada.nome}.valores.gz'),
        arquivoDeDistancias: File('$pasta/${entrada.nome}.distancias.gz'),
      );
    }

    return base;
  }
}

/// Uma fatia guardada mais a posição a consultar nela — que pode ser a gêmea.
class _Alvo {
  final _FatiaNoDisco fatia;
  final Tabuleiro posicao;
  const _Alvo(this.fatia, this.posicao);
}
