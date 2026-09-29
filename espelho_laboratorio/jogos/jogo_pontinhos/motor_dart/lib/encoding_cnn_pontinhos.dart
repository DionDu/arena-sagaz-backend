// Codificação da entrada da CNN de 12 canais (porte FIEL do backend).
//
// Espelha `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`
// (função `extrair_canais`) e o `_partida_para_dataset` do simulador. É lógica
// PURA (sem TFLite, sem Flutter), então roda em qualquer plataforma e pode ser
// testada por testes de unidade — inclusive comparando com o backend.
//
// Pipeline do modo "Contra a CPU" (ver contrato_codificacao_pontinhos.json):
//   matriz da partida {-1,0,1,8}
//     → partidaParaDataset → {0,1,8,9}
//     → extrairCanais       → tensor (4,3,12) em {0.0,1.0}
//     → (1,4,3,12) float32  → TFLite Interpreter
//
// IMPORTANTE: o modelo foi treinado num encoding NEUTRO (não distingue dono do
// traço). Por isso a conversão para dataset transforma qualquer marca (±1) em
// "ocupado" (9 na aresta, 1 na caixa) — exatamente como o backend.
//
// ── ⚠️ DESDE A T093 (28/09/2026) É ESTE ARQUIVO QUE O SERVIDOR USA ──────────
//
// Ele morava só no aplicativo, e o servidor montava os canais com
// `extrair_canais` do laboratório, em Python. Eram duas escritas da mesma conta.
// Elas não haviam divergido - mas a BFS no grafo dual é exatamente o tipo de
// código que uma segunda escrita erra em silêncio, e o sintoma seria o
// adversário do desafio ranquear os lances de outro jeito, sem nada acusar.
//
// ⚠️ **O que o servidor ainda faz em Python é a INFERÊNCIA**, e só ela: ele
// recebe daqui o tensor já montado, chama o `ai-edge-litert` e devolve a saída
// da rede para a política decidir. Essa é a única peça do Pontinhos que já tinha
// prova de paridade antes da T093 - `scripts/conferir_runtime_inferencia.py`
// compara os dois runtimes contra uma referência versionada, e é portão do
// build da imagem do job.

import 'dart:typed_data';

/// Número de caixas (linhas × colunas) e de canais do modelo pequeno.
const int kLinhas = 4;
const int kColunas = 3;
const int kCanais = 12;

/// Converte a matriz da PARTIDA (`{-1, 0, 1, 8}`) para o formato do DATASET
/// (`{0, 1, 8, 9}`), que é o esperado por [extrairCanais].
///
/// Regras (idênticas a `_partida_para_dataset` do backend):
///   • posição par×par   → 8 (ponto fixo da grade);
///   • posição ímpar×ímpar → 1 se a caixa está fechada (≠0), senão 0;
///   • demais (arestas)  → 9 se ocupada (≠0), senão 0.
List<List<int>> partidaParaDataset(List<List<int>> m) {
  final h = m.length;
  final w = m[0].length;
  // `List.generate` cria a matriz de saída do mesmo tamanho.
  return List.generate(h, (r) {
    return List.generate(w, (c) {
      if (r.isEven && c.isEven) return 8;
      if (r.isOdd && c.isOdd) return m[r][c] != 0 ? 1 : 0;
      return m[r][c] != 0 ? 9 : 0;
    });
  });
}

// Coordenada de caixa (linha, coluna). Records `(int, int)` têm igualdade
// estrutural em Dart, então servem como chave de Map/Set.
typedef _Caixa = (int, int);

/// Extrai o tensor de 12 canais a partir da matriz no formato do DATASET
/// (`(9, 7)` com domínio `{0, 1, 8, 9}`).
///
/// Devolve uma lista aninhada `4 × 3 × 12` de `double` em `{0.0, 1.0}`, na mesma
/// ordem (r, c, k) do numpy do backend — pronta para virar o tensor de entrada.
List<List<List<double>>> extrairCanais(List<List<int>> mDs) {
  // Tensor de saída zerado (4×3×12).
  final canais = List.generate(
    kLinhas,
    (_) => List.generate(kColunas, (_) => List.filled(kCanais, 0.0)),
  );

  // ----- Canais 0..4: arestas geométricas + caixa fechada -----
  for (var r = 0; r < kLinhas; r++) {
    for (var c = 0; c < kColunas; c++) {
      canais[r][c][0] = mDs[2 * r][2 * c + 1] == 9 ? 1.0 : 0.0; // topo
      canais[r][c][1] = mDs[2 * r + 2][2 * c + 1] == 9 ? 1.0 : 0.0; // base
      canais[r][c][2] = mDs[2 * r + 1][2 * c] == 9 ? 1.0 : 0.0; // esquerda
      canais[r][c][3] = mDs[2 * r + 1][2 * c + 2] == 9 ? 1.0 : 0.0; // direita
      canais[r][c][4] = mDs[2 * r + 1][2 * c + 1] == 1 ? 1.0 : 0.0; // fechada
    }
  }

  // ----- Graus e estado de "fechada" de cada caixa -----
  final grauDe = <_Caixa, int>{};
  final fechadaDe = <_Caixa, bool>{};
  for (var r = 0; r < kLinhas; r++) {
    for (var c = 0; c < kColunas; c++) {
      final fechada = mDs[2 * r + 1][2 * c + 1] == 1;
      fechadaDe[(r, c)] = fechada;
      final g = _grau(mDs, r, c);
      grauDe[(r, c)] = g;
      // Canais 5 (grau 3) e 6 (grau 2) — só em caixas ABERTAS.
      if (!fechada) {
        if (g == 3) canais[r][c][5] = 1.0;
        if (g == 2) canais[r][c][6] = 1.0;
      }
    }
  }

  // ----- Canais 7..10: cadeias e loops via BFS no grafo dual -----
  final (adj, componentes) = _bfsDual(mDs, grauDe, fechadaDe);

  for (final comp in componentes) {
    if (comp.isEmpty) continue;
    final grausComp = {for (final u in comp) u: adj[u]!.length};
    final maxGrau = grausComp.values.reduce((a, b) => a > b ? a : b);

    final ehLoop =
        comp.length >= 3 && grausComp.values.every((g) => g == 2);
    final ehComplexa = maxGrau >= 3; // ramificação no componente

    if (ehComplexa) {
      // Tudo vira cadeia longa (canal 8).
      for (final (r, c) in comp) {
        canais[r][c][8] = 1.0;
      }
    } else if (ehLoop) {
      for (final (r, c) in comp) {
        canais[r][c][9] = 1.0;
      }
    } else {
      final comprimento = comp.length;
      if (comprimento == 1) {
        // Half-open mínimo: caixa grau-2 com exatamente 1 vizinha grau-3.
        final (r0, c0) = comp[0];
        var nAbertas = 0;
        for (final v in _vizinhasCaixa(r0, c0)) {
          if (_arestaLivreEntre(mDs, (r0, c0), v) && (grauDe[v] ?? -1) == 3) {
            nAbertas++;
          }
        }
        if (nAbertas == 1) canais[r0][c0][10] = 1.0;
        continue;
      }
      // Comprimento 2 → canal 7 (cadeia curta); ≥3 → canal 8 (cadeia longa).
      final slot = comprimento == 2 ? 7 : 8;
      for (final (r, c) in comp) {
        canais[r][c][slot] = 1.0;
      }
      // Canal 10: cadeia aberta com exatamente uma ponta capturável.
      final pontas = [for (final u in comp) if (grausComp[u] == 1) u];
      if (pontas.length == 2) {
        final pontasAbertas = _contarPontasAbertas(mDs, pontas, adj, grauDe);
        if (pontasAbertas == 1) {
          for (final (r, c) in comp) {
            canais[r][c][10] = 1.0;
          }
        }
      }
    }
  }

  // ----- Canal 11: paridade de cadeias longas (broadcast global) -----
  var nCadeiasLongas = 0;
  for (final comp in componentes) {
    if (_ehCadeiaLonga(comp, adj)) nCadeiasLongas++;
  }
  final paridadeImpar = (nCadeiasLongas % 2) == 1;
  for (var r = 0; r < kLinhas; r++) {
    for (var c = 0; c < kColunas; c++) {
      canais[r][c][11] = paridadeImpar ? 1.0 : 0.0;
    }
  }

  return canais;
}

/// Achata o tensor (4×3×12) em um [Float32List] de 144 valores na ordem
/// (r, c, k) — o layout esperado pelo tensor de entrada `(1, 4, 3, 12)`.
Float32List achatar(List<List<List<double>>> canais) {
  final out = Float32List(kLinhas * kColunas * kCanais);
  var i = 0;
  for (var r = 0; r < kLinhas; r++) {
    for (var c = 0; c < kColunas; c++) {
      for (var k = 0; k < kCanais; k++) {
        out[i++] = canais[r][c][k];
      }
    }
  }
  return out;
}

// ----------------------------- Helpers internos -----------------------------

// Grau da caixa (r, c): nº de arestas vizinhas ocupadas (==9). Caixa fechada = 4.
int _grau(List<List<int>> m, int r, int c) {
  if (m[2 * r + 1][2 * c + 1] == 1) return 4;
  var g = 0;
  if (m[2 * r][2 * c + 1] == 9) g++; // topo
  if (m[2 * r + 2][2 * c + 1] == 9) g++; // base
  if (m[2 * r + 1][2 * c] == 9) g++; // esquerda
  if (m[2 * r + 1][2 * c + 2] == 9) g++; // direita
  return g;
}

// Existe aresta LIVRE (==0) compartilhada entre as caixas ortogonais a e b?
bool _arestaLivreEntre(List<List<int>> m, _Caixa a, _Caixa b) {
  final (ra, ca) = a;
  final (rb, cb) = b;
  if (ra == rb && (ca - cb).abs() == 1) {
    final cMin = ca < cb ? ca : cb;
    return m[2 * ra + 1][2 * cMin + 2] == 0; // aresta vertical entre eles
  }
  if (ca == cb && (ra - rb).abs() == 1) {
    final rMin = ra < rb ? ra : rb;
    return m[2 * rMin + 2][2 * ca + 1] == 0; // aresta horizontal entre eles
  }
  return false;
}

// Caixas ortogonalmente adjacentes a (r, c), dentro do tabuleiro 4×3.
List<_Caixa> _vizinhasCaixa(int r, int c) {
  final cands = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)];
  return [
    for (final (rr, cc) in cands)
      if (rr >= 0 && rr < kLinhas && cc >= 0 && cc < kColunas) (rr, cc),
  ];
}

// Constrói o grafo dual (nós = caixas abertas de grau 2) e devolve (adj, componentes).
(Map<_Caixa, List<_Caixa>>, List<List<_Caixa>>) _bfsDual(
  List<List<int>> m,
  Map<_Caixa, int> grauDe,
  Map<_Caixa, bool> fechadaDe,
) {
  final nosGrau2 = <_Caixa>{
    for (final e in grauDe.entries)
      if (e.value == 2 && !(fechadaDe[e.key] ?? false)) e.key,
  };

  final adj = <_Caixa, List<_Caixa>>{for (final n in nosGrau2) n: <_Caixa>[]};
  for (final n in nosGrau2) {
    for (final v in _vizinhasCaixa(n.$1, n.$2)) {
      if (nosGrau2.contains(v) && _arestaLivreEntre(m, n, v)) {
        adj[n]!.add(v);
      }
    }
  }

  final visitado = <_Caixa>{};
  final componentes = <List<_Caixa>>[];
  for (final n in nosGrau2) {
    if (visitado.contains(n)) continue;
    final comp = <_Caixa>[];
    final fila = <_Caixa>[n]; // usado como fila (BFS)
    visitado.add(n);
    while (fila.isNotEmpty) {
      final u = fila.removeAt(0);
      comp.add(u);
      for (final v in adj[u]!) {
        if (!visitado.contains(v)) {
          visitado.add(v);
          fila.add(v);
        }
      }
    }
    componentes.add(comp);
  }
  return (adj, componentes);
}

// Cadeia longa = comprimento ≥3, não-loop e não-complexa (sem ramificação).
bool _ehCadeiaLonga(List<_Caixa> comp, Map<_Caixa, List<_Caixa>> adj) {
  if (comp.length < 3) return false;
  final graus = [for (final u in comp) adj[u]!.length];
  final ehLoop = graus.every((g) => g == 2);
  final ehComplexa = graus.reduce((a, b) => a > b ? a : b) >= 3;
  return !ehLoop && !ehComplexa;
}

// Conta quantas pontas da cadeia são "abertas" (capturáveis): saem por uma
// aresta livre para uma caixa de grau 3 fora do componente.
int _contarPontasAbertas(
  List<List<int>> m,
  List<_Caixa> pontas,
  Map<_Caixa, List<_Caixa>> adj,
  Map<_Caixa, int> grauDe,
) {
  var abertas = 0;
  for (final p in pontas) {
    final vizinhosDual = adj[p]!.toSet();
    for (final v in _vizinhasCaixa(p.$1, p.$2)) {
      if (vizinhosDual.contains(v)) continue;
      if (_arestaLivreEntre(m, p, v) && (grauDe[v] ?? -1) == 3) {
        abertas++;
        break; // uma aresta capturável basta
      }
    }
  }
  return abertas;
}
