/// O que cada nível de dificuldade das damas significa **para quem joga**.
///
/// Por que separado de `busca_damas.dart`
/// ---------------------------------------
/// `Nivel`, lá, é o orçamento de **busca**: profundidade, quiescência, teto de
/// nós. São parâmetros do motor, e o motor não deve saber de apresentação.
///
/// Aqui ficam as decisões que o jogador percebe e que **não mudam a força**:
/// quanto tempo o personagem parece pensar, e quantos segundos o humano tem
/// para jogar. Misturá-las num objeto só faria mexer no relógio da tela parecer
/// mexer na dificuldade da IA.
///
/// Espelho de `../motor/politica_dificuldade_damas.py`. No app, os equivalentes
/// são `core/jogos/tempo_de_pensar.dart` (a espera) e
/// `politica_dificuldade_velha.dart` (o relógio).
///
/// ⚠️ Os números daqui são **estimativa declarada**, decidida com o dono em
/// 2026-08-14, e não medição. Só a Cacau tem número vindo de partida jogada.
library;

/// A chave que o app consulta para saber a base da espera.
///
/// Descrição cadastrada no console, palavra por palavra:
///
/// > Damas - delay e milisegundos para o personagem jogar. Este valor é
/// > multiplicado pelo parâmetro de cada personagem nos jogos e define após
/// > quanto tempo o personagem efetuará sua jogada após todos os cálculos
/// > (Minimax, busca CNN etc serem realizados).
///
/// O nome segue `delay_ms_personagem_pensando_<jogoId>`, como as chaves do
/// Pontinhos e da velha. Mudar o padrão faria o Hub — que percorre a lista de
/// jogos montando as chaves — procurar uma que ninguém criou, e cair no
/// *fallback* para sempre, em silêncio.
const String chaveRemoteConfigDoDelay = 'delay_ms_personagem_pensando_damas';

/// A base usada quando o Remote Config não responde, ou responde com lixo.
///
/// ⚠️ **Não é um número livre: existe um piso aritmético.** A espera do Magno é
/// `2,0 × base`, e ela precisa ser maior que o tempo que a busca dele realmente
/// leva — senão a pausa zera e o Magno vira o personagem mais LENTO da tela,
/// exatamente o oposto do que foi pedido.
///
/// ⚠️ **O quadro abaixo é de ANTES do motor nativo, e ficou histórico em
/// 26/08/2026.** Ele mede o motor **Dart** contra o teto de então (96.000), e
/// continua valendo para o que era: o Dart no aparelho de entrada não cabia na
/// espera-alvo do Magno nem com o teto antigo. O que mudou desde então:
///
/// * o teto do Magno subiu para **288.000** (`busca_damas.dart`);
/// * quem o executa é o **motor Rust**, ~10× mais rápido no mesmo ARM — no
///   Galaxy A04 (mais fraco que o A06 aqui) os 288.000 custam **0,74 s**, que
///   cabe nos 800 ms;
/// * onde o nativo não carregou, o Sagaz **não é ofertado** (T199), então o
///   caso da linha do A06 deixa de existir em campo.
///
/// A medição de 21/08/2026, em aparelhos reais, com a `bancada_aparelho`:
///
/// | aparelho | nós/s (Dart) | 96.000 nós custam | piso que a base precisaria ter |
/// |---|---|---|---|
/// | Galaxy A06 | 71.614 | **1,34 s** | **671 ms** |
/// | iPhone 15 Pro Max | 536.263 | 0,18 s | 90 ms |
///
/// O "Galaxy A35, 160.593 nós/s" que era o aparelho de referência declarado, e
/// de onde saiu o piso de **299 ms**, é **2,2× mais rápido** que o A06. Não é
/// aparelho de referência coisa nenhuma para o compromisso do produto, que é com
/// o `minSdk 24`.
///
/// ⚠️ **Os 299 ms acima são HISTÓRIA.** Desde 26/08/2026 o piso é **383 ms**, e
/// o aparelho de referência é o Galaxy A04 com o motor **nativo** — o único que
/// joga o Sagaz, por causa da trava da T199. Ver `logica/ritmo_damas.dart`, que
/// é quem guarda o número vivo; aqui ficam os multiplicadores, e eles não
/// mudaram.
///
/// A conta completa, com esta base — e as duas colunas de busca que a medição
/// separou:
///
/// | nível | multiplicador | espera-alvo | busca (iPhone 15 Pro Max) | busca (Galaxy A06) | pausa que sobra no A06 |
/// |---|---|---|---|---|---|
/// | Cacau | 5,0× | 2,00 s | ~0,00 s | ~0,00 s | 2,00 s |
/// | Pita | 4,0× | 1,60 s | ~0,00 s | ~0,00 s | 1,60 s |
/// | Tex | 3,0× | 1,20 s | ~0,00 s | ~0,01 s | 1,19 s |
/// | Magno | 2,0× | 0,80 s | 0,18 s | **1,34 s** | **0 — e estoura em 0,54 s** |
///
/// (A linha do Magno acima é a do **Dart com 96.000 nós**. Com o motor nativo e
/// os 288.000 de hoje, o Galaxy A04 — mais fraco que este A06 — gasta 0,74 s e
/// deixa 0,06 s de pausa. Aperta, mas não estoura.)
///
/// Repare que **só o Magno gasta busca de verdade**: os três primeiros param na
/// profundidade (1, 2 e 3) e visitam dezenas de nós, não milhares. Por isso a
/// inversão pedida pelo dono ("o Magno não pode ser o mais lento") se mantém no
/// iPhone e **se perde** no A06: lá ele é o único que estoura.
///
/// ⚠️ **O que NÃO se perdia no A06 era a força.** A rede de segurança do
/// `sagaz` é de 3 s, e 1,34 s não a dispara: o A06 completava os 96.000 nós e
/// enfrentava exatamente o mesmo Magno que o iPhone. É para isso que o
/// orçamento é em nós. O defeito medido aqui era de **ritmo**, e só.
///
/// ⚠️ **Com 288.000 isso deixa de ser verdade em Dart** — 4,02 s no A06, e a
/// rede de 3 s corta por volta dos 215.000 nós. É exatamente o motivo de a
/// T199 esconder o Sagaz onde o nativo não carregou: um nível cortado pelo
/// relógio é outro nível com o mesmo nome, e ninguém na tela saberia.
///
/// ⚠️ **Não conserte isto subindo a base pelo Remote Config sem pensar duas
/// vezes.** Levar a base a 700 ms devolveria o ritmo do Magno no A06 — e levaria
/// a Cacau a 3,5 s de espera por lance em *todos* os aparelhos, para consertar um
/// problema que só existe num deles. O caminho preferido é o inverso: fazer o
/// Magno caber (T192 — chegar mais fundo com os mesmos nós).
///
/// ⚠️ **Para desligar a espera pelo console, ponha `1`, não `0`** — zero é
/// indistinguível de "chave ausente" e cai no fallback, o oposto do pretendido.
const int baseFallbackMs = 400;

/// Quantas vezes a base cada personagem espera — **decrescente com a força**.
///
/// Decisão do dono: *"quero que o usuário tenha a percepção de que os
/// personagens mais burros ficam mais tempo pensando, enquanto o Magno joga
/// mais rápido. Não quero que o Magno seja mais lento que os demais."*
///
/// ⚠️ **São diferentes dos multiplicadores dos outros dois jogos** (2,0 · 1,7 ·
/// 1,4 · 1,0), e a diferença é deliberada: lá a razão entre o mais lento e o
/// mais rápido é 2,0×; aqui é **2,5×**, para a inversão continuar visível apesar
/// de o Magno gastar 0,6 s de busca real. Nos outros jogos o motor decide em
/// microssegundos e a espera é toda encenação — em damas, metade da espera do
/// Magno é trabalho de verdade.
const Map<String, double> multiplicadorDoDelay = {
  'cacau': 5.0,
  'pita': 4.0,
  'tex': 3.0,
  'sagaz': 2.0,
};

/// Quanto deve durar o intervalo **inteiro** entre o lance do humano e o da CPU.
///
/// É `multiplicador × base`, na forma do hub. É o intervalo TOTAL — busca mais
/// encenação —, não a pausa; quem calcula a pausa é [pausaDeEncenacaoMs].
int esperaAlvoMs(String identificadorDoNivel, [int baseMs = baseFallbackMs]) {
  final multiplicador = multiplicadorDoDelay[identificadorDoNivel];
  if (multiplicador == null) return 0;
  return (multiplicador * baseMs).round();
}

/// Quanto a tela deve esperar **depois** de a busca terminar.
///
/// [msDaBusca] é quanto ela realmente levou, **neste** aparelho.
///
/// **Nunca devolve negativo**: quando a busca já passou do alvo — celular lento,
/// ou posição cara —, a resposta é zero e o jogador simplesmente esperou mais.
/// Somar uma pausa por cima aí seria castigar duas vezes quem tem o aparelho
/// pior.
///
/// Por que subtrair a busca, em vez de somar a espera ao que ela levou
/// --------------------------------------------------------------------
/// Porque somar inverteria a ordem pedida. A busca do Magno custa 0,60 s e a da
/// Cacau custa ~0,00 s: com espera somada, o Magno seria sempre o mais lento da
/// tela. Subtraindo, o intervalo total é o que o multiplicador manda,
/// **independentemente do aparelho**.
int pausaDeEncenacaoMs(String identificadorDoNivel, double msDaBusca,
    [int baseMs = baseFallbackMs]) {
  final restante = esperaAlvoMs(identificadorDoNivel, baseMs) - msDaBusca;
  return restante > 0 ? restante.round() : 0;
}

/// Traduz o valor **bruto** da chave na base a usar.
///
/// Chave ausente devolve `0` no SDK do Firebase, e negativo não faz sentido para
/// uma espera — os dois casos caem no fallback. Espelha `interpretarBaseDePensar`
/// do app de propósito: é a mesma regra, e precisa dar o mesmo resultado dos
/// dois lados.
int interpretarBaseDoRemoteConfig(int bruto) =>
    bruto > 0 ? bruto : baseFallbackMs;

/// Quantos segundos o jogador tem por lance. `null` = sem relógio.
///
/// ⚠️ **A Cacau não tem relógio**, e é regra do hub, não esquecimento
/// (RF-VLH-012): quem está aprendendo não deve jogar contra o tempo.
///
/// Os segundos são **mais generosos que nos outros dois jogos** — 30/25/20 aqui
/// contra 15/10/7 na velha e 20/15/10 no Pontinhos. O motivo está no tabuleiro:
/// o 3×3 tem no máximo 9 casas e a decisão é quase imediata; em damas 8×8 há até
/// 20 lances legais e é preciso varrer quatro diagonais para não deixar peça
/// pendurada.
const Map<String, int?> timerDoHumanoSegundos = {
  'cacau': null,
  'pita': 30,
  'tex': 25,
  'sagaz': 20,
};
