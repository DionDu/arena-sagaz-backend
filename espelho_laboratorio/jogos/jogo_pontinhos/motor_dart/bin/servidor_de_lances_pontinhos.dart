// O MOTOR DO APARELHO, ATENDENDO O SERVIDOR — um pedido por linha (T093).
//
// ── Por que este programa existe ────────────────────────────────────────────
//
// Até 28/09/2026 o gerador de desafios jogava o Pontinhos com uma **segunda
// escrita** da política, em Python, sobre a mesma CNN. E as duas escritas
// divergiam em dois pontos:
//
//   • o **sorteador** - Mersenne Twister no Python, xorshift no Dart: ⛔ mesma
//     semente, sequências diferentes;
//   • a **ordem** das listas sobre as quais se sorteia - o Python desempatava
//     por rótulo, o aplicativo não.
//
// ⛔ **E a divergência do Pontinhos não dá erro.** Nas damas ela apareceu porque
// o gabarito não batia; aqui o lance sai plausível, a partida corre até o fim, e
// a única evidência seria o gabarito do desafio não ser seguível lance a lance
// contra Cacau, Pita ou Tex.
//
// ⛔ **A correção não é ajustar números: é parar de ter dois motores.** Este
// programa faz o servidor decidir com **o código que o aparelho embarca** - este
// pacote, byte a byte.
//
// ── ⚠️ O QUE ESTE PROGRAMA NÃO FAZ: A INFERÊNCIA ────────────────────────────
//
// A rede continua sendo rodada pelo Python (`ai-edge-litert`), e a fronteira
// entre os dois passa pelos **números da rede**: este programa monta o tensor de
// 12 canais, o Python o alimenta ao modelo, e a saída volta para cá, onde a
// política decide.
//
// Três razões, em ordem de peso:
//
//   1. ⚠️ **A inferência é a única peça do Pontinhos que JÁ TINHA prova de
//      paridade.** `scripts/conferir_runtime_inferencia.py` compara a saída do
//      runtime do servidor com a do runtime do aplicativo contra uma referência
//      versionada, e é **portão do build** da imagem do job desde a T001. O que
//      não tinha prova - a política, a ordenação e o sorteador - é justamente o
//      que este programa passou a decidir.
//   2. ⛔ **O `tflite_flutter` é um pacote Flutter** e não compila num binário
//      Dart puro; abrir a `libtensorflowlite_c` por FFI traria um **terceiro**
//      runtime (Linux x86-64, dentro da imagem) - diferente tanto do
//      `ai-edge-litert` quanto do que o aparelho Android carrega. Ou seja: ⛔
//      compraria paridade de inferência nenhuma, e ainda acrescentaria um
//      artefato binário à imagem, com trava própria para manter.
//   3. ⚠️ A `.tflite` e o mapeamento **já viajam no espelho** e já entram no
//      `co_versao_motor` pelo manifesto de hashes.
//
// ── Por que um processo que fica vivo, e não um comando por lance ───────────
//
// A régua mede 20 execuções por mascote, e uma partida tem dezenas de lances.
// Subir um processo por lance pagaria a partida do Dart (carregar o executável,
// aquecer) milhares de vezes. Aqui o processo sobe uma vez e responde enquanto
// for alimentado.
//
// ⚠️ **Uma linha de texto por pedido, uma por resposta.** É a mesma decisão da
// fronteira do motor de damas e da do motor Rust: texto, e não estrutura binária
// compartilhada. Texto se lê no log, se cola num relatório de defeito e não
// obriga os dois lados a concordarem sobre layout de memória.
//
// ── O diálogo, por lance ────────────────────────────────────────────────────
//
//   1. {"comando":"canais","lances":[...]}
//      → {"tensor":[144 floats], "disponiveis":[...], "vez_de":1, ...}
//   2. (o Python roda a CNN sobre o tensor)
//   3. {"comando":"decidir","lances":[...],"nivel":"facil","semente":7,
//       "softmax":[...],"mapeamento":{"H_0_1":0,...}}
//      → {"lance":"H_0_1","co_acao":"cnn_argmax_absoluto","ranqueados":[...]}
//
// Há ainda o `ranquear`, que é o passo 3 **sem política**: ele devolve só a
// ordem dos traços, e é o motor cru - o adversário que o `MotorPontinhos` do
// servidor chama quando quer a opinião da rede, e não a jogada de um nível.
//
// ── Como rodar ──────────────────────────────────────────────────────────────
//
//   dart run bin/compilar_servidor_de_lances_pontinhos.dart
//
// e depois, para experimentar à mão (um JSON por linha):
//
//   echo {"comando":"canais","lances":[]} | bin/servidor_de_lances_pontinhos.exe

import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:motor_pontinhos/analise_tabuleiro_pontinhos.dart';
import 'package:motor_pontinhos/dificuldade_pontinhos.dart';
import 'package:motor_pontinhos/encoding_cnn_pontinhos.dart';
import 'package:motor_pontinhos/politica_dificuldade_pontinhos.dart';
import 'package:motor_pontinhos/tabuleiro_pontinhos.dart';

import '_resumo_do_motor_pontinhos.g.dart';

/// A versão do PROTOCOLO desta fronteira - não a do motor.
///
/// ⚠️ Ela sobe quando o formato do pedido ou da resposta muda de forma que o
/// outro lado precise saber. O servidor confere na abertura: sem isto, um
/// backend novo conversando com um executável velho receberia respostas
/// plausíveis e erradas, que é o pior modo de falha possível.
const int versaoDoProtocolo = 1;

/// O único tabuleiro que a CNN embarcada atende (RF-DES-018d).
///
/// ⛔ **Recusar os outros é o ponto.** O modelo de 12 canais foi treinado no
/// 4×3; um tabuleiro maior chegaria aqui, montaria um tensor de outra forma e a
/// inferência falharia longe daqui - ou pior, devolveria números plausíveis.
const int linhasDoTabuleiro = kLinhas;
const int colunasDoTabuleiro = kColunas;

/// Reproduz a partida a partir da sequência de traços marcados.
///
/// ⚠️ **O estado do Pontinhos é a SEQUÊNCIA, e não a posição.** O turno extra -
/// quem fecha caixa joga de novo - faz "de quem é a vez" depender da história, e
/// não há atalho a partir do desenho final do tabuleiro. É o mesmo que
/// `EstadoPontinhos._partida` faz do lado Python.
///
/// Lança [FormatException] se um lance repetir um traço já ocupado: um estado
/// impossível ⛔ se constrói em silêncio.
EstadoTabuleiroPontinhos _reproduzir(List<String> lances) {
  final estado = EstadoTabuleiroPontinhos(
    linhas: linhasDoTabuleiro,
    colunas: colunasDoTabuleiro,
  );
  for (var i = 0; i < lances.length; i++) {
    final lance = lances[i];
    if (!estado.tracosDisponiveis().contains(lance)) {
      throw FormatException(
        'lance ${i + 1} da sequência ("$lance") não está disponível. '
        'Disponíveis: ${estado.tracosDisponiveis().join(", ")}.',
      );
    }
    final fechadas = estado.aplicarTracoDe(lance, estado.vezSinal);
    // Fechou caixa, joga de novo. É a regra que faz o placar e a vez dependerem
    // da ordem, e não só do desenho final do tabuleiro.
    if (fechadas == 0) estado.passarVez();
  }
  return estado;
}

/// Responde ao pedido `canais`: o tensor de entrada da rede, já montado.
///
/// Devolve também o que o outro lado precisa para saber se ainda há jogo -
/// assim o Python não reimplementa a regra de fim de partida para perguntar.
Map<String, dynamic> _responderCanais(EstadoTabuleiroPontinhos estado) {
  // `partidaParaDataset` NÃO altera a matriz da partida: ela devolve uma matriz
  // nova. Normalizar por cima corromperia o estado (o marcador do jogador 2
  // viraria do jogador 1), e o contrato traz esse aviso em caixa alta.
  final mDs = partidaParaDataset(estado.matriz);
  final canais = extrairCanais(mDs); // (4, 3, 12) em {0.0, 1.0}
  return {
    // `achatar` entrega os 144 valores na ordem (r, c, k), que é o layout do
    // tensor `(1, 4, 3, 12)` que o modelo espera.
    'tensor': achatar(canais).toList(),
    'linhas': linhasDoTabuleiro,
    'colunas': colunasDoTabuleiro,
    'canais': kCanais,
    'disponiveis': estado.tracosDisponiveis(),
    'capturas': capturasDisponiveis(estado),
    'vez_de': estado.vezSinal,
    'placar': {'1': estado.pontosJ1, '-1': estado.pontosJ2},
    'acabou': estado.acabou,
  };
}

/// O ranqueamento pedido, ou a queixa de que faltou material para fazê-lo.
///
/// ⚠️ O mapeamento e a softmax viajam em CADA pedido, de propósito: sem estado
/// guardado entre chamadas, a resposta não depende da ordem em que os pedidos
/// chegaram, e o que falta falha **aqui** - e não três lances adiante, com o
/// ranqueamento zerado em silêncio.
({List<LanceRanqueado>? lances, String? erro}) _ranqueamentoDoPedido(
  EstadoTabuleiroPontinhos estado,
  Map<String, dynamic> pedido,
) {
  final comando = pedido['comando'];
  final mapeamentoBruto = pedido['mapeamento'] as Map<String, dynamic>?;
  if (mapeamentoBruto == null) {
    return (
      lances: null,
      erro: 'o pedido "$comando" precisa do "mapeamento" (rótulo → índice).',
    );
  }
  final indiceDoLabel = {
    for (final e in mapeamentoBruto.entries) e.key: (e.value as num).toInt(),
  };

  final softmaxBruta = pedido['softmax'] as List?;
  if (softmaxBruta == null) {
    return (
      lances: null,
      erro: 'o pedido "$comando" precisa da "softmax" (a saída da rede).',
    );
  }
  final softmax = [for (final v in softmaxBruta) (v as num).toDouble()];

  final ranqueados = ranquearDaSoftmax(
    estado: estado,
    softmax: softmax,
    indiceDoLabel: indiceDoLabel,
  );
  if (ranqueados.isEmpty) {
    return (lances: null, erro: 'a partida já acabou: não há traço a escolher.');
  }
  return (lances: ranqueados, erro: null);
}

/// Responde ao pedido `ranquear`: os traços disponíveis, do melhor ao pior.
///
/// ⛔ **Sem política nenhuma** - é o motor cru, o que o `MotorPontinhos` do
/// servidor sempre chamou de `ranquear`. Quem transforma isto em Cacau, Pita,
/// Tex e Magno é o pedido `decidir`.
Map<String, dynamic> _responderRanquear(
  EstadoTabuleiroPontinhos estado,
  Map<String, dynamic> pedido,
) {
  final (lances: ranqueados, erro: erro) =
      _ranqueamentoDoPedido(estado, pedido);
  if (ranqueados == null) return {'erro': erro};
  return {
    'ranqueados': [
      for (final l in ranqueados) {'label': l.label, 'score': l.score},
    ],
  };
}

/// Responde ao pedido `decidir`: a política, sobre a saída da rede.
Map<String, dynamic> _responderDecidir(
  EstadoTabuleiroPontinhos estado,
  Map<String, dynamic> pedido,
) {
  final nivel = Dificuldade.daChave(pedido['nivel'] as String);

  final (lances: ranqueados, erro: erro) =
      _ranqueamentoDoPedido(estado, pedido);
  if (ranqueados == null) return {'erro': erro};

  // ⚠️ **Um `Random` NOVO por pedido**, semeado pelo chamador. Um sorteador de
  // vida longa responderia conforme quantos sorteios foram consumidos antes, e a
  // mesma posição daria lances diferentes na segunda medição - que é exatamente
  // o que a semente publicada do desafio existe para impedir (RF-DES-210).
  final semente = pedido['semente'];
  final rng = semente == null ? Random() : Random((semente as num).toInt());

  final decisao = escolherLance(estado, ranqueados, nivel, rng, temCnn: true);
  if (decisao == null) {
    return {'erro': 'a política não devolveu lance.'};
  }

  final (topo: topo, resto: _) = separarTopo(ranqueados);
  return {
    'lance': decisao.label,
    'co_acao': decisao.coAcao,
    // ⚠️ Estes três não são enfeite de log. É comparando o **ranqueamento** que
    // se descobre que dois lados concordaram no lance por sorte, com a rede
    // discordando por baixo - o mesmo papel que os "nós" cumprem nas damas.
    'ranqueados': [
      for (final l in ranqueados) {'label': l.label, 'score': l.score},
    ],
    'tamanho_do_topo': topo.length,
    'nivel': nivel.chave,
    'epsilon': nivel.epsilon,
    'usa_captura_gulosa': nivel.usaCapturaGulosa,
  };
}

/// Responde a um pedido já decodificado.
Map<String, dynamic> responder(Map<String, dynamic> pedido) {
  final comando = (pedido['comando'] ?? 'decidir') as String;

  final lances = (pedido['lances'] as List?)?.cast<String>() ?? const <String>[];
  final EstadoTabuleiroPontinhos estado;
  try {
    estado = _reproduzir(lances);
  } on FormatException catch (erro) {
    return {'erro': erro.message};
  }

  switch (comando) {
    case 'canais':
      return _responderCanais(estado);
    case 'ranquear':
      return _responderRanquear(estado, pedido);
    case 'decidir':
      return _responderDecidir(estado, pedido);
    default:
      return {
        'erro': 'comando desconhecido: "$comando". '
            'O motor conhece: canais, ranquear, decidir.',
      };
  }
}

void main(List<String> argumentos) {
  // ⚠️ `utf8.decoder` explícito: sem ele o Dart lê a entrada na codificação do
  // sistema, e no Windows isso é cp1252 - os rótulos são ASCII e sobreviveriam,
  // mas uma mensagem de erro com acento voltaria corrompida ao Python.
  final linhas = stdin.transform(utf8.decoder).transform(const LineSplitter());

  // A primeira coisa que sai é quem somos. O servidor lê esta linha antes de
  // mandar qualquer pedido, e é ela que impede um backend novo de conversar com
  // um executável antigo sem perceber.
  stdout.writeln(jsonEncode({
    'pronto': true,
    'versao_do_protocolo': versaoDoProtocolo,
    'motor': 'dart',
    'jogo': 'pontinhos',
    'linhas': linhasDoTabuleiro,
    'colunas': colunasDoTabuleiro,
    // ⚠️ **De que fontes este binário saiu.** O backend compara este resumo com
    // o dos arquivos que ele tem no espelho e RECUSA a conversa se divergirem -
    // é a trava que impede o servidor de gerar gabaritos com um motor velho,
    // depois de alguém corrigir a política e esquecer de recompilar.
    'resumo_do_motor': resumoDoMotorPontinhos,
    'arquivos_do_motor': hashesDoMotorPontinhos,
  }));

  linhas.listen((linha) {
    if (linha.trim().isEmpty) return;
    Map<String, dynamic> resposta;
    try {
      final pedido = jsonDecode(linha) as Map<String, dynamic>;
      resposta = responder(pedido);
      // O identificador viaja de volta sem ser interpretado: é o que permite ao
      // servidor casar resposta com pedido sem depender da ordem.
      if (pedido.containsKey('id')) resposta['id'] = pedido['id'];
    } catch (erro) {
      // ⛔ Um pedido malformado NÃO derruba o processo. Derrubar faria a régua
      // inteira parar no meio por causa de uma linha, e o custo de recomeçar é
      // de horas.
      resposta = {'erro': 'pedido inválido: $erro'};
    }
    stdout.writeln(jsonEncode(resposta));
  });
}
