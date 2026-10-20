// O MOTOR DO APARELHO, ATENDENDO O SERVIDOR — um pedido por linha (T102).
//
// ── Por que este programa existe ────────────────────────────────────────────
//
// O Desafio do Dia precisa que o servidor jogue o Quatro em Linha EXATAMENTE
// como o aparelho joga: o gabarito do desafio é uma partida contra Cacau, Pita,
// Tex ou Magno, e a pessoa tem de poder segui-lo lance a lance. As damas e o
// Pontinhos ensinaram o mesmo, cada um com um episódio de divergência: a mesma
// regra escrita duas vezes (em Dart no app e em Python no servidor) acaba
// discordando, e o Pontinhos discordava SEM ERRO (o lance saía plausível).
//
// ⛔ Por isso o Quatro em Linha não tem segunda escrita: o servidor decide com
// este pacote compilado, byte a byte o código que o aparelho embarca
// (`contracts/motor-quatro.md` §4, RF-QTR-041). O Python continua dono do
// ÁRBITRO (lances legais, desfecho), que não escolhe lance nenhum.
//
// ── O que viaja ─────────────────────────────────────────────────────────────
//
// O `PedidoDeLanceQuatro` do contrato (§3), em JSON, com os nomes de lá:
//
//   {"comando":"decidir","lances":"s4s4s3","modalidade":"tradicional",
//    "tetoDeNos":48000,"epsilon":0.1,"percebe":{"vencer":0.9,...},
//    "aberturaDoMagno":null,"semente":12345,"limiteMs":null,"id":7}
//   → {"lance":"s5","acao":"busca_melhor","nosVisitados":47210,
//      "profundidadeAtingida":9,"motivoParada":"nos","tempoBuscaMs":38,
//      "avaliacaoJ1":-12,"id":7}
//
// O `buscar` é o mesmo pedido SEM a política (`escolherLance`): o melhor lance
// da busca, sem ε nem filtros nem sorteio. É o que as provas do job usam ("há
// vitória forçada?"), e não o que um personagem joga.
//
// ── Por que os números do nível viajam no pedido ────────────────────────────
//
// O teto, o ε, o "percebe" e a abertura do Magno moram no contrato do jogo, e
// é o CHAMADOR quem os lê (o motor não abre arquivo, §3). Assim o mesmo motor
// serve ao app (asset), à bancada (caminho) e ao servidor (espelho), e o pedido
// sozinho descreve o lance: lido no log, ele se refaz.
//
// ── Por que o contrato entra pela linha de comando ──────────────────────────
//
// As REGRAS da modalidade (largura, altura, quantas alinhar) também vêm do
// contrato, e elas não mudam de um lance para o outro. Então o executável lê o
// contrato uma vez, na abertura, pelo caminho que o servidor lhe passa:
//
//   servidor_de_lances_quatro --contrato <caminho do contrato_quatro.json>
//
// ⚠️ E anuncia o SHA-256 dos bytes que leu. O servidor confere contra o
// contrato do espelho dele: sem isso, um executável apontado para um contrato
// de outra versão jogaria outro tabuleiro com toda a confiança.
//
// ── Como rodar ──────────────────────────────────────────────────────────────
//
//   dart run bin/compilar_servidor_de_lances_quatro.dart
//
// e depois, para experimentar à mão (um JSON por linha):
//
//   echo {"comando":"buscar","lances":"","modalidade":"tradicional","tetoDeNos":1000} | bin/servidor_de_lances_quatro.exe --contrato ../contrato/contrato_quatro.json

import 'dart:convert';
import 'dart:io';

// O `crypto` é dependência de DESENVOLVIMENTO de propósito (`pubspec.yaml`):
// o que viaja para o app são os arquivos de `lib/`, que não o usam; `bin/`
// fica no laboratório e no servidor. Daí o aviso calado.
// ignore: depend_on_referenced_packages
import 'package:crypto/crypto.dart';
import 'package:motor_quatro/busca_quatro.dart';
import 'package:motor_quatro/catalogo_modalidades_quatro.dart';
import 'package:motor_quatro/politica_dificuldade_quatro.dart';
import 'package:motor_quatro/posicao_quatro.dart';
import 'package:motor_quatro/regras_da_modalidade_quatro.dart';

import '_resumo_do_motor_quatro.g.dart';

/// A versão do PROTOCOLO desta fronteira - não a do motor.
///
/// ⚠️ Ela sobe quando o formato do pedido ou da resposta muda de forma que o
/// outro lado precise saber. O servidor confere na abertura: sem isto, um
/// backend novo conversando com um executável velho receberia respostas
/// plausíveis e erradas, que é o pior modo de falha possível.
const int versaoDoProtocoloQuatro = 1;

/// Os comandos que este executável atende, na ordem em que a mensagem de erro
/// os lista.
const List<String> comandosDoServidorQuatro = ['decidir', 'buscar'];

/// Quem atende os pedidos: o contrato já lido e as regras de cada modalidade.
///
/// As regras são carregadas na PRIMEIRA vez que um pedido as cita, e não na
/// abertura: uma modalidade ainda não medida (com o marcador `teto_de_nos: 0`)
/// não pode impedir o servidor de jogar as outras. Ela falha no pedido que a
/// cita, com a mensagem do catálogo.
final class ServidorDeLancesQuatro {
  /// O contrato do jogo, já decodificado.
  final Map<String, Object?> contrato;

  /// As regras já carregadas, por id de modalidade.
  final Map<String, RegrasDaModalidadeQuatro> _regras = {};

  /// Cria o servidor sobre o [contrato] já lido.
  ServidorDeLancesQuatro(this.contrato);

  /// Os ids que o contrato declara, em ordem alfabética (para a abertura).
  List<String> get modalidadesDeclaradas {
    final porModalidade = contrato['por_modalidade'];
    if (porModalidade is! Map<String, Object?>) return const [];
    return porModalidade.keys.toList()..sort();
  }

  /// As regras da modalidade [id], carregadas uma vez.
  ///
  /// Lança [ModalidadeDesconhecida] ou [ContratoQuatroInvalido], que
  /// [responder] transforma em resposta de erro.
  RegrasDaModalidadeQuatro regrasDe(String id) =>
      // `putIfAbsent` só chama a função quando a chave ainda não existe: é o
      // cache em uma linha.
      _regras.putIfAbsent(id, () => carregarModalidade(contrato, id));

  /// Responde a um pedido já decodificado. Nunca lança: todo problema volta
  /// como `{"erro": ...}`, porque um pedido malformado não pode derrubar o
  /// processo (derrubar faria a régua inteira parar no meio por uma linha).
  Map<String, Object?> responder(Map<String, Object?> pedido) {
    try {
      return _responder(pedido);
    } on _PedidoInvalido catch (erro) {
      return {'erro': erro.mensagem};
    } on ModalidadeDesconhecida catch (erro) {
      return {'erro': 'modalidade desconhecida: $erro'};
    } on ContratoQuatroInvalido catch (erro) {
      return {'erro': 'contrato inválido: $erro'};
    } on LanceIlegalQuatro catch (erro) {
      return {'erro': 'sequência de lances ilegal: $erro'};
    } on ArgumentError catch (erro) {
      // A política recusa `percebe` com situação desconhecida ou chance fora
      // de 0 a 1, e o ε fora de 0 a 1.
      return {'erro': 'pedido recusado pelo motor: ${erro.message} '
          '(${erro.name} = ${erro.invalidValue})'};
    }
  }

  Map<String, Object?> _responder(Map<String, Object?> pedido) {
    final comando = pedido['comando'] ?? 'decidir';
    if (comando is! String || !comandosDoServidorQuatro.contains(comando)) {
      throw _PedidoInvalido('comando desconhecido: "$comando". '
          'O motor conhece: ${comandosDoServidorQuatro.join(", ")}.');
    }

    final regras = regrasDe(_texto(pedido, 'modalidade'));
    final lances = _texto(pedido, 'lances');

    // A partida é reproduzida aqui, ANTES da busca, para que uma sequência
    // ilegal ou uma partida já terminada voltem com uma mensagem que diz isso
    // (e não com o erro de algum ponto lá dentro da busca).
    final posicao = PosicaoQuatro.deLances(regras, lances);
    if (regras.desfecho(posicao) != null) {
      throw _PedidoInvalido('a partida já acabou: não há lance a escolher.');
    }

    // ⛔ O servidor joga SÓ pelo teto de nós. Um limite de tempo faria o lance
    // depender da velocidade da máquina, e o gabarito deixaria de ser o lance
    // que o aparelho joga (§3: `limiteMs` é `null` no servidor). Recusar, em
    // vez de ignorar, é para o erro do chamador aparecer.
    if (pedido['limiteMs'] != null) {
      throw _PedidoInvalido('"limiteMs" tem de ser null no servidor: ele '
          'joga só pelo teto de nós, para o lance não depender da máquina.');
    }

    final tetoDeNos = _inteiro(pedido, 'tetoDeNos');
    if (tetoDeNos <= 0) {
      throw _PedidoInvalido('"tetoDeNos" tem de ser positivo (veio $tetoDeNos).');
    }

    if (comando == 'buscar') {
      // Só a busca: sem ε, sem filtros, sem sorteio. A semente não é usada,
      // e por isso não é exigida.
      final resposta = escolherLance(
        PedidoDeLanceQuatro(
            lances: lances, modalidade: regras.id, tetoDeNos: tetoDeNos),
        regras,
      );
      return respostaEmJson(resposta);
    }

    // `decidir`: o personagem inteiro. ⚠️ O ε, o "percebe" e a semente são
    // OBRIGATÓRIOS, e não têm padrão: um campo esquecido pelo chamador faria a
    // Cacau jogar como o Magno (ε zero, tudo percebido pela busca) sem erro
    // nenhum, que é o defeito que esta fronteira existe para impedir.
    final resposta = escolherLanceDoNivel(
      PedidoDeLanceQuatro(
        lances: lances,
        modalidade: regras.id,
        tetoDeNos: tetoDeNos,
        epsilon: _numero(pedido, 'epsilon'),
        percebe: _percebe(pedido),
        aberturaDoMagno: _abertura(pedido),
        semente: _inteiro(pedido, 'semente'),
        limiteMs: null,
      ),
      regras,
    );
    return respostaEmJson(resposta);
  }
}

/// A resposta do motor em JSON, com os nomes do contrato (§3).
Map<String, Object?> respostaEmJson(RespostaDeLanceQuatro resposta) => {
      'lance': resposta.lance,
      'acao': resposta.acao,
      'nosVisitados': resposta.nosVisitados,
      'profundidadeAtingida': resposta.profundidadeAtingida,
      'motivoParada': resposta.motivoParada,
      // ⚠️ É o único campo que muda de uma máquina para outra: ele informa,
      // e nenhuma comparação de paridade pode usá-lo.
      'tempoBuscaMs': resposta.tempoBuscaMs,
      'avaliacaoJ1': resposta.avaliacaoJ1,
    };

/// Um pedido que não diz o que precisa dizer. Vira resposta de erro.
final class _PedidoInvalido implements Exception {
  final String mensagem;
  _PedidoInvalido(this.mensagem);
}

/// O campo [nome] como texto, ou a recusa dizendo qual falta.
String _texto(Map<String, Object?> pedido, String nome) {
  final valor = pedido[nome];
  if (valor is! String) {
    throw _PedidoInvalido('o pedido precisa de "$nome" (texto); veio $valor.');
  }
  return valor;
}

/// O campo [nome] como inteiro. Um `4.0` do JSON é aceito; um `4.5` não.
int _inteiro(Map<String, Object?> pedido, String nome) {
  final valor = pedido[nome];
  // `num` é o tipo-pai de `int` e `double` em Dart; o `jsonDecode` entrega
  // `int` para `4` e `double` para `4.0`.
  if (valor is! num || valor != valor.truncate()) {
    throw _PedidoInvalido('o pedido precisa de "$nome" (inteiro); veio $valor.');
  }
  return valor.toInt();
}

/// O campo [nome] como número real.
double _numero(Map<String, Object?> pedido, String nome) {
  final valor = pedido[nome];
  if (valor is! num) {
    throw _PedidoInvalido('o pedido precisa de "$nome" (número); veio $valor.');
  }
  return valor.toDouble();
}

/// O `percebe` do pedido: um objeto de situação → chance. Obrigatório (pode
/// ser `{}`, que é "a busca decide tudo", como o Magno).
Map<String, double> _percebe(Map<String, Object?> pedido) {
  final valor = pedido['percebe'];
  if (valor is! Map<String, Object?>) {
    throw _PedidoInvalido(
        'o pedido "decidir" precisa de "percebe" (objeto); veio $valor.');
  }
  return {
    for (final MapEntry(:key, :value) in valor.entries)
      key: value is num
          ? value.toDouble()
          : throw _PedidoInvalido('"percebe.$key" tem de ser número.'),
  };
}

/// A `aberturaDoMagno` do pedido: `null`, ou um objeto coluna → chance.
///
/// ⚠️ Em JSON a chave de um objeto é sempre texto; a coluna `"4"` vira o
/// inteiro 4 aqui, e uma chave que não é número é recusada.
Map<int, double>? _abertura(Map<String, Object?> pedido) {
  final valor = pedido['aberturaDoMagno'];
  if (valor == null) return null;
  if (valor is! Map<String, Object?>) {
    throw _PedidoInvalido('"aberturaDoMagno" tem de ser null ou objeto.');
  }
  return {
    for (final MapEntry(:key, :value) in valor.entries)
      (int.tryParse(key) ??
              (throw _PedidoInvalido(
                  '"aberturaDoMagno": a chave "$key" não é coluna.'))):
          value is num
              ? value.toDouble()
              : throw _PedidoInvalido('"aberturaDoMagno.$key" tem de ser número.'),
  };
}

/// A linha de apresentação: a primeira coisa que sai, antes de qualquer
/// pedido. O servidor a lê e RECUSA a conversa se o protocolo, o resumo do
/// motor ou o contrato não forem os dele.
Map<String, Object?> aberturaDoServidorQuatro(
        ServidorDeLancesQuatro servidor, String sha256DoContrato) =>
    {
      'pronto': true,
      'versao_do_protocolo': versaoDoProtocoloQuatro,
      'motor': 'dart',
      'jogo': 'quatro',
      'comandos': comandosDoServidorQuatro,
      'modalidades': servidor.modalidadesDeclaradas,
      // ⚠️ Os bytes do contrato que este processo leu. O servidor compara com
      // o do espelho dele.
      'sha256_do_contrato': sha256DoContrato,
      // ⚠️ De que fontes este binário saiu. O backend compara este resumo com
      // o dos arquivos que ele tem no espelho e RECUSA a conversa se
      // divergirem: é a trava que impede gerar gabaritos com um motor velho,
      // depois de alguém corrigir a política e esquecer de recompilar.
      'resumo_do_motor': resumoDoMotorQuatro,
      'arquivos_do_motor': hashesDoMotorQuatro,
    };

/// O laço do processo: escreve a apresentação e responde uma linha por linha.
///
/// Recebe a entrada e a saída por parâmetro (e não `stdin`/`stdout` direto)
/// para o teste conversar com ele sem subir um processo. Termina quando a
/// entrada acaba.
Future<void> atenderQuatro(ServidorDeLancesQuatro servidor,
    String sha256DoContrato, Stream<String> linhas, StringSink saida) async {
  saida.writeln(jsonEncode(aberturaDoServidorQuatro(servidor, sha256DoContrato)));

  // `await for` lê o `Stream` uma linha de cada vez, na ordem: o pedido
  // seguinte só é lido depois de o anterior ser respondido.
  await for (final linha in linhas) {
    if (linha.trim().isEmpty) continue;
    Map<String, Object?> resposta;
    Object? id;
    try {
      final pedido = jsonDecode(linha);
      if (pedido is! Map<String, Object?>) {
        throw const FormatException('o pedido tem de ser um objeto JSON');
      }
      id = pedido['id'];
      resposta = servidor.responder(pedido);
    } catch (erro) {
      // ⛔ Um JSON malformado também NÃO derruba o processo.
      resposta = {'erro': 'pedido inválido: $erro'};
    }
    // O identificador viaja de volta sem ser interpretado: é o que permite ao
    // servidor casar resposta com pedido sem depender da ordem.
    if (id != null) resposta['id'] = id;
    saida.writeln(jsonEncode(resposta));
  }
}

Future<void> main(List<String> argumentos) async {
  final i = argumentos.indexOf('--contrato');
  final caminho =
      i >= 0 && i + 1 < argumentos.length ? argumentos[i + 1] : null;
  if (caminho == null) {
    stderr.writeln('uso: servidor_de_lances_quatro --contrato '
        '<caminho do contrato_quatro.json>');
    exit(2);
  }
  final arquivo = File(caminho);
  if (!arquivo.existsSync()) {
    stderr.writeln('não achei o contrato em $caminho.');
    exit(2);
  }

  // Lê em BYTES: o hash descreve o arquivo do disco, sem tradução de fim de
  // linha, e é o mesmo que o Python calcula com `read_bytes()`.
  final bytes = arquivo.readAsBytesSync();
  final contrato = jsonDecode(utf8.decode(bytes)) as Map<String, Object?>;

  // ⚠️ `utf8.decoder` explícito: sem ele o Dart lê a entrada na codificação do
  // sistema, e no Windows isso é cp1252 - uma mensagem com acento voltaria
  // corrompida ao Python.
  await atenderQuatro(
    ServidorDeLancesQuatro(contrato),
    sha256.convert(bytes).toString(),
    stdin.transform(utf8.decoder).transform(const LineSplitter()),
    stdout,
  );
}
