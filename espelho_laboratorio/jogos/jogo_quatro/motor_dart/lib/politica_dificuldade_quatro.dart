// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A POLÍTICA de dificuldade (spec 010, T033 e T034; RF-QTR-070 a RF-QTR-082,
// R-07, R-08; e a §8zzzf de `docs/DECISOES-do-dono.md`): o que transforma o
// melhor lance que a busca enxerga no lance que CADA personagem joga.
//
// Os quatro personagens são o MESMO motor (RF-QTR-070). O que os separa vem
// do contrato, nível a nível, e chega aqui dentro do `PedidoDeLanceQuatro`:
//
//   - o teto de nós (quanto a busca enxerga; usado pela busca);
//   - o ε: a chance de, de propósito, NÃO jogar o melhor lance;
//   - a chance de PERCEBER cada uma de três situações (o `percebe`):
//       · `vencer`: ele tem quatro na mão;
//       · `bloquear`: o adversário tem quatro na mão;
//       · `nao_jogar_sob_ameaca`: há uma casa logo abaixo de uma vitória do
//         adversário (a peça dele cairia em cima, na casa que vence);
//   - a abertura do Magno: as chances de cada coluna no 1º lance da partida.
//
// ── Perceber, ou não (§8zzzf, 14/10/2026) ───────────────────────────────────
//
// Até ali os três eram uma lista "nunca erra", tudo ou nada. O dono pediu
// probabilidades: *"a Cacau poderia ter uma minúscula chance de deixar a
// vitória escapar. Pita uma chance menor ainda. Já Tex e Magno nunca perderiam
// a vitória"*, e o mesmo, em outras doses, para bloquear e para jogar sob
// ameaça. Num turno em que a situação EXISTE, sorteia-se se o personagem a
// percebe:
//
//   - percebeu: o filtro vale, como antes (joga a vitória; tapa a do outro;
//     não joga sob a ameaça);
//   - não percebeu a VITÓRIA: os lances que vencem saem da escolha, e ele
//     joga outro (`vitoria_perdida`);
//   - não percebeu a VITÓRIA DO OUTRO: os lances que a tapam saem da escolha
//     (`bloqueio_perdido`);
//   - não percebeu a casa SOB AMEAÇA: os lances que a criam passam a valer, a
//     olhos dele, o mesmo que o melhor, e entram no sorteio dos empatados; se
//     um deles sair, o motivo é `jogou_sob_ameaca`.
//
// ⚠️ As duas primeiras FORÇAM o erro, e a terceira não, de propósito. Não ver
// a vitória (a própria ou a do outro) é não ver o lance que decide: a busca o
// acharia sozinha, e por isso ele sai da escolha. Já a casa de baixo é um
// perigo que se deixa de notar: ela "parece um lance como outro qualquer", e
// não um lance que se procura. Forçá-la faria a Cacau dar a vitória de
// presente a cada vez que uma ameaça sua ficasse no ar.
//
// Uma situação sem chave no `percebe` é a de antes sem o filtro: nada é
// sorteado, nada é forçado, e a busca decide sozinha (é o caso do pedido da
// bancada, que mede só a busca). Com chance 1, o filtro vale sempre, sem
// sorteio: o Tex e o Magno com `vencer` = 1 nunca deixam a vitória escapar.
//
// ⚠️ A percepção sorteia num gerador PRÓPRIO, derivado da semente do lance
// ([_sementeDaPercepcao]), e só quando a situação existe: os sorteios de
// sempre (a abertura, o ε, os empates) continuam saindo da sequência de
// antes, e uma partida sem nenhuma situação dessas joga exatamente os mesmos
// lances que jogava.
//
// ⚠️ É aqui, e não na busca, porque a busca tem de continuar sendo a mesma
// conta em todo lugar: a bancada do aparelho mediu `escolherLance`, e o teto
// do Magno saiu dela. A política só escolhe ENTRE os lances que a busca já
// avaliou, e sorteia com a SEMENTE do lance (recebida de fora: o motor nunca
// a deriva), então a mesma partida dá os mesmos lances no aparelho, no replay
// e no servidor do desafio.
//
// O caminho de um lance, em ordem:
//
//   1. a busca, com os empates da raiz (`buscarComEmpates`);
//   2. `vencer`: com 4 na mão e percebendo, joga a vitória
//      (`vitoria_imediata`), e acabou; sem perceber, as vitórias saem;
//   3. `bloquear` e `nao_jogar_sob_ameaca` separam os lances PERMITIDOS (os
//      percebidos restringem; o bloqueio não percebido tira os que tapam); um
//      filtro que não deixaria lance nenhum é ignorado, porque jogar é
//      obrigatório;
//   4. a abertura do Magno, só no 1º lance da partida (`abertura_sorteada`);
//   5. o ε, entre os permitidos que não empatam com o melhor
//      (`epsilon_aleatorio`); sem nenhum, segue para o melhor;
//   6. o sorteio entre os empatados com o melhor (`empate_sorteado`), com as
//      casas sob ameaça junto quando ela não foi percebida;
//   7. o melhor (`busca_melhor`).
//
// O motivo registrado, do mais forte ao mais fraco: um descuido que mudou o
// lance (`vitoria_perdida`, `bloqueio_perdido`, `jogou_sob_ameaca`); depois o
// bloqueio, quando foi ele que restringiu a escolha (`bloqueio_imediato`,
// qualquer que tenha sido o passo que escolheu entre os bloqueios); depois o
// passo que escolheu. Os códigos são EXATAMENTE os de
// `contracts/motor-quatro.md` §3, que são as linhas de
// `jogo_quatro.tb901_jogada_acao` no banco.

import 'dart:math';

import 'ameacas_quatro.dart';
import 'busca_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// A situação "ele tem quatro na mão": percebendo, joga a vitória.
const String filtroVencerQuatro = 'vencer';

/// A situação "o adversário tem quatro na mão": percebendo, tapa.
const String filtroBloquearQuatro = 'bloquear';

/// A situação "há uma casa logo abaixo de uma vitória do adversário":
/// percebendo, não joga nela (a peça dele cairia em cima, na casa que vence).
const String filtroNaoJogarSobAmeacaQuatro = 'nao_jogar_sob_ameaca';

/// Todas as situações que o motor conhece. Uma chave fora desta lista no
/// contrato é recusada: um erro de digitação no contrato não pode virar, em
/// silêncio, um personagem que erra o que não devia.
const Set<String> filtrosConhecidosQuatro = {
  filtroVencerQuatro,
  filtroBloquearQuatro,
  filtroNaoJogarSobAmeacaQuatro,
};

/// A semente do gerador da PERCEPÇÃO, derivada da semente do lance.
///
/// Um gerador separado deixa a sequência dos sorteios de sempre intacta (ver o
/// cabeçalho). O `^` (ou exclusivo bit a bit) com uma constante fixa dá outra
/// sequência para a mesma semente, igual em todo lugar que roda o motor; a
/// constante é a parte fracionária da razão áurea em 32 bits, a mesma usada
/// para espalhar números em tabelas de dispersão.
int _sementeDaPercepcao(int sementeDoLance) => sementeDoLance ^ 0x9E3779B9;

/// O lance que o personagem do [pedido] joga, pelas [regras].
///
/// [bitsDaTabela] é o da busca (os testes o diminuem para rodar milhares de
/// lances). É esta a função que o isolate do app, o servidor do desafio e a
/// escada chamam; a bancada mede só a busca (`escolherLance`).
RespostaDeLanceQuatro escolherLanceDoNivel(
    PedidoDeLanceQuatro pedido, RegrasDaModalidadeQuatro regras,
    {int bitsDaTabela = bitsDaTabelaQuatro}) {
  for (final MapEntry(key: filtro, value: chance) in pedido.percebe.entries) {
    if (!filtrosConhecidosQuatro.contains(filtro)) {
      throw ArgumentError.value(filtro, 'percebe', 'situação desconhecida');
    }
    if (chance < 0 || chance > 1) {
      throw ArgumentError.value(chance, 'percebe.$filtro', 'fora de 0 a 1');
    }
  }
  if (pedido.epsilon < 0 || pedido.epsilon > 1) {
    throw ArgumentError.value(pedido.epsilon, 'epsilon', 'fora de 0 a 1');
  }

  // 1. A busca, que também diz quais lances empataram com o melhor.
  final (:resposta, :empatados) =
      buscarComEmpates(pedido, regras, bitsDaTabela: bitsDaTabela);
  final raiz = PosicaoQuatro.deLances(regras, pedido.lances);

  /// A resposta da busca com outro lance e outro motivo (os números da
  /// busca, nós, profundidade e avaliação, continuam os dela).
  RespostaDeLanceQuatro com(LanceQuatro lance, String acao) =>
      RespostaDeLanceQuatro(
        lance: escreverLanceQuatro(lance, regras.tiposDeLance),
        acao: acao,
        nosVisitados: resposta.nosVisitados,
        profundidadeAtingida: resposta.profundidadeAtingida,
        motivoParada: resposta.motivoParada,
        tempoBuscaMs: resposta.tempoBuscaMs,
        avaliacaoJ1: resposta.avaliacaoJ1,
      );

  // O gerador da percepção, e a pergunta "percebeu [filtro]?", feita só
  // quando a situação existe. `null` = o nível nem tem essa situação no
  // contrato (nada sorteado, nada forçado).
  final sorteioDaPercepcao = Random(_sementeDaPercepcao(pedido.semente));
  bool? percebeu(String filtro) {
    final chance = pedido.percebe[filtro];
    if (chance == null) return null;
    // Com chance 1 (ou 0) não há o que sortear: o gerador só anda quando a
    // resposta depende dele, para os números deste turno não dependerem de
    // situações que valem sempre o mesmo.
    if (chance >= 1) return true;
    if (chance <= 0) return false;
    return sorteioDaPercepcao.nextDouble() < chance;
  }

  // Os lances legais na ordem do centro, a mesma da busca.
  var legais = _naOrdemDoCentro(regras.lancesLegais(raiz), raiz.dimensoes);

  // 2. `vencer`: a busca já devolve a vitória na mão como melhor lance (é o
  // atalho dela, a 1ª coluna que vence na ordem do centro). Percebendo, só se
  // registra o motivo, e nada de ε nem de sorteio passa por cima. Sem
  // perceber, as vitórias saem da escolha (se sobrar algum lance).
  final vitorias = regras.lancesQueVencem(raiz).toSet();
  var vitoriaPerdida = false;
  if (vitorias.isNotEmpty) {
    final viu = percebeu(filtroVencerQuatro);
    if (viu == true) {
      return com(lerLanceQuatro(resposta.lance, regras.tiposDeLance),
          'vitoria_imediata');
    }
    if (viu == false) {
      final semVitoria = [
        for (final l in legais)
          if (!vitorias.contains(l)) l
      ];
      if (semVitoria.isNotEmpty) {
        legais = semVitoria;
        vitoriaPerdida = true;
      }
    }
  }

  // A semente do LANCE, e um `Random` novo para ele: o mesmo pedido sorteia
  // sempre a mesma coisa. O 1º número é tirado sempre, para a sequência de
  // sorteios não depender de qual passo abaixo o usa.
  final sorteio = Random(pedido.semente);
  final u = sorteio.nextDouble();

  // 3. O que cada lance faz com as vitórias do adversário: quais TAPAM uma
  // que ele já tinha, e quais CRIAM uma nova (a casa de baixo).
  final efeitos = _efeitosNasAmeacas(regras, raiz, legais);
  final filtros = <String>{};
  var bloqueioPerdido = false;
  if (efeitos.ameacado) {
    final viu = percebeu(filtroBloquearQuatro);
    if (viu == true) filtros.add(filtroBloquearQuatro);
    if (viu == false) {
      // Sem perceber, ele joga um lance que NÃO tapa (se houver algum: com
      // todos tapando, tapar é inevitável e não é descuido).
      final naoTapam = [
        for (final l in legais)
          if (!efeitos.tapam.contains(l)) l
      ];
      if (naoTapam.isNotEmpty) {
        legais = naoTapam;
        bloqueioPerdido = true;
      }
    }
  }
  var sobAmeacaNaoPercebida = false;
  if (legais.any(efeitos.criam.contains)) {
    final viu = percebeu(filtroNaoJogarSobAmeacaQuatro);
    if (viu == true) filtros.add(filtroNaoJogarSobAmeacaQuatro);
    if (viu == false) sobAmeacaNaoPercebida = true;
  }
  final (:permitidos, :bloqueou) =
      lancesPermitidosQuatro(regras, raiz, legais, filtros);
  bool permitido(LanceQuatro l) => permitidos.contains(l);

  // O melhor que os filtros deixam: o da busca, se ele passa; senão, o 1º
  // permitido. (A busca descarta sozinha o lance que entrega a vitória ao
  // outro, então o melhor dela só fura um filtro quando TODOS os lances
  // perdem, ou quando um descuido tirou o lance dela da escolha: aí fica o
  // 1º na ordem do centro.)
  final melhorDaBusca = lerLanceQuatro(resposta.lance, regras.tiposDeLance);
  final melhor =
      permitido(melhorDaBusca) ? melhorDaBusca : permitidos.first;
  // O grupo dos que valem o mesmo que o melhor, na ordem do centro: assim o
  // sorteio depende só de QUAIS lances empataram, e não da ordem em que a
  // busca os experimentou. Com a casa sob ameaça não percebida, os lances
  // que a criam entram no grupo: a olhos dele, valem o mesmo.
  final iguais = _naOrdemDoCentro({
    melhor,
    ...empatados.where(permitido),
    if (sobAmeacaNaoPercebida) ...permitidos.where(efeitos.criam.contains),
  }.toList(), raiz.dimensoes);

  /// O motivo a registrar quando o passo [acao] escolheu o [lance]: um
  /// descuido que mudou o lance passa à frente de tudo; depois, o bloqueio,
  /// porque foi ele que limitou a escolha.
  RespostaDeLanceQuatro escolhido(LanceQuatro lance, String acao) {
    if (vitoriaPerdida) return com(lance, 'vitoria_perdida');
    if (bloqueioPerdido) return com(lance, 'bloqueio_perdido');
    if (sobAmeacaNaoPercebida && efeitos.criam.contains(lance)) {
      return com(lance, 'jogou_sob_ameaca');
    }
    return com(lance, bloqueou ? 'bloqueio_imediato' : acao);
  }

  // 4. A abertura do Magno: só no 1º lance da PARTIDA (o tabuleiro vazio).
  // Quando a pessoa abre, o 1º lance do Magno já é o 2º da partida, e não há
  // sorteio (R-08); num desafio, a posição publicada já tem lances.
  final abertura = pedido.aberturaDoMagno;
  if (abertura != null && raiz.lancesJogados == 0) {
    final sorteado = _sortearPorPeso(permitidos, abertura, u);
    if (sorteado != null) return escolhido(sorteado, 'abertura_sorteada');
  }

  // 5. O ε: errar de propósito, mas só entre os lances que os filtros
  // permitem e que não valem o mesmo que o melhor (sortear um empatado não
  // seria erro nenhum).
  if (u < pedido.epsilon) {
    final candidatos = [
      for (final l in permitidos)
        if (!iguais.contains(l)) l
    ];
    if (candidatos.isNotEmpty) {
      return escolhido(candidatos[sorteio.nextInt(candidatos.length)],
          'epsilon_aleatorio');
    }
  }

  // 6. Os empates exatos, sorteados com a semente (RF-QTR-082).
  if (iguais.length > 1) {
    return escolhido(
        iguais[sorteio.nextInt(iguais.length)], 'empate_sorteado');
  }

  // 7. O melhor.
  return escolhido(melhor, 'busca_melhor');
}

/// O que cada lance de [legais] faz com as vitórias do adversário em [raiz].
///
/// As vitórias que contam são as casas onde ele vence já no lance seguinte
/// (as ameaças dele que estão jogáveis, pela T029):
///
/// - [ameacado]: ele tem pelo menos uma agora;
/// - [tapam]: os lances depois dos quais alguma delas deixa de existir (o
///   lance que vence na hora conta como tapar: a partida acaba nele, e o
///   outro não chega a jogar);
/// - [criam]: os lances que criam uma nova, que é jogar na casa de baixo de
///   uma ameaça dele (a peça dele cairia em cima, exatamente na casa que
///   vence). O lance que vence na hora nunca cria.
({bool ameacado, Set<LanceQuatro> tapam, Set<LanceQuatro> criam})
    _efeitosNasAmeacas(RegrasDaModalidadeQuatro regras, PosicaoQuatro raiz,
        List<LanceQuatro> legais) {
  final dimensoes = raiz.dimensoes;

  /// As casas onde o adversário (com as peças [pecasDoOutro]) vence no lance
  /// seguinte, com as casas ocupadas [mascara].
  int vitoriasDoOutro(int pecasDoOutro, int mascara) =>
      casasDeAmeacaQuatro(dimensoes, pecasDoOutro, mascara) &
      casasJogaveisQuatro(dimensoes, mascara);

  // ANTES: as peças do adversário são as de quem NÃO tem a vez (a máscara
  // sem as minhas).
  final antes = vitoriasDoOutro(raiz.mascara ^ raiz.pecasDaVez, raiz.mascara);
  final vencem = regras.lancesQueVencem(raiz).toSet();
  final tapam = <LanceQuatro>{};
  final criam = <LanceQuatro>{};
  for (final l in legais) {
    if (vencem.contains(l)) {
      tapam.add(l);
      continue;
    }
    // DEPOIS do lance: na posição nova a vez é dele, então as peças "da vez"
    // são as dele. Lidas de lá, e não de antes, porque um lance que TIRA peça
    // faz a coluna descer, e as peças dele descem junto.
    final filho = regras.aplicar(raiz, l);
    final depois = vitoriasDoOutro(filho.pecasDaVez, filho.mascara);
    // Tapa = alguma casa que vencia antes deixou de vencer (`antes & ~depois`
    // são as que sumiram); cria = alguma que não vencia passou a vencer.
    if (antes & ~depois != 0) tapam.add(l);
    if (depois & ~antes != 0) criam.add(l);
  }
  return (ameacado: antes != 0, tapam: tapam, criam: criam);
}

/// Os lances de [legais] que os [filtros] permitem em [raiz], na mesma ordem,
/// e se o filtro `bloquear` foi o que restringiu ([bloqueou]).
///
/// [filtros] são as situações PERCEBIDAS neste turno (a política já sorteou;
/// aqui elas só valem):
///
/// - `bloquear`: se o adversário tem vitória jogável, ficam só os lances que
///   tapam pelo menos uma (a casa deixa de ser uma vitória jogável para ele);
/// - `nao_jogar_sob_ameaca`: saem os lances que CRIAM uma vitória jogável
///   para ele.
///
/// Um filtro que tiraria todos os lances é ignorado: jogar é obrigatório, e
/// numa posição em que todos perdem qualquer lance serve.
///
/// Pública porque o teste a confere lance a lance.
({List<LanceQuatro> permitidos, bool bloqueou}) lancesPermitidosQuatro(
    RegrasDaModalidadeQuatro regras,
    PosicaoQuatro raiz,
    List<LanceQuatro> legais,
    Set<String> filtros) {
  final efeitos = _efeitosNasAmeacas(regras, raiz, legais);
  var permitidos = legais;
  var bloqueou = false;
  if (filtros.contains(filtroBloquearQuatro) && efeitos.ameacado) {
    final tapam = [
      for (final l in permitidos)
        if (efeitos.tapam.contains(l)) l
    ];
    if (tapam.isNotEmpty) {
      permitidos = tapam;
      bloqueou = true;
    }
  }
  if (filtros.contains(filtroNaoJogarSobAmeacaQuatro)) {
    final seguros = [
      for (final l in permitidos)
        if (!efeitos.criam.contains(l)) l
    ];
    if (seguros.isNotEmpty) permitidos = seguros;
  }
  return (permitidos: permitidos, bloqueou: bloqueou);
}

/// [lances] na ordem do centro para as bordas (`ordemDoCentroQuatro`), a
/// mesma em que a busca os experimenta. Dentro da mesma coluna, a ordem em
/// que vieram.
List<LanceQuatro> _naOrdemDoCentro(
    List<LanceQuatro> lances, DimensoesQuatro dimensoes) {
  final ordem = ordemDoCentroQuatro(dimensoes.largura);
  final lugar = {for (var i = 0; i < ordem.length; i++) ordem[i]: i};
  final indices = [for (var i = 0; i < lances.length; i++) i];
  // O índice original desempata, para a ordem não depender do `sort`.
  indices.sort((a, b) {
    final porColuna = lugar[lances[a].coluna]! - lugar[lances[b].coluna]!;
    return porColuna != 0 ? porColuna : a - b;
  });
  return [for (final i in indices) lances[i]];
}

/// Sorteia um dos [lances] com os [pesos] por coluna (as chances da
/// abertura), usando [u] (um número de 0 a 1, já sorteado).
///
/// Só entram as colunas dos [lances] (as que estão livres e que os filtros
/// permitem): o peso das outras é redistribuído entre elas, pela soma. Sem
/// nenhum peso positivo, devolve `null` e quem chama segue sem abertura.
///
/// As colunas são percorridas da 1 para a última, e não na ordem do `Map`:
/// o sorteio não pode depender de como o contrato escreveu o mapa.
LanceQuatro? _sortearPorPeso(
    List<LanceQuatro> lances, Map<int, double> pesos, double u) {
  final emOrdem = [...lances]..sort((a, b) => a.coluna - b.coluna);
  var total = 0.0;
  for (final l in emOrdem) {
    total += pesos[l.coluna] ?? 0;
  }
  if (total <= 0) return null;
  // Uma régua de 0 a `total`, com um trecho por coluna do tamanho do peso
  // dela: a coluna sorteada é a do trecho onde `u × total` cai.
  final alvo = u * total;
  var acumulado = 0.0;
  LanceQuatro? ultimoComPeso;
  for (final l in emOrdem) {
    final peso = pesos[l.coluna] ?? 0;
    if (peso <= 0) continue;
    acumulado += peso;
    ultimoComPeso = l;
    if (alvo < acumulado) return l;
  }
  // Só chega aqui por arredondamento (a soma das parcelas ficou um fio
  // abaixo do total): fica a última coluna que tinha peso.
  return ultimoComPeso;
}
