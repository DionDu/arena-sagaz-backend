# Marca — arquivos vetoriais (SVG)

Logos da Arena Sagaz em **SVG** (vetor), para gerar PNGs em qualquer tamanho.

| Arquivo | Conteúdo | Cor da tinta | Uso |
|---|---|---|---|
| `emblema-escuro.svg` | só o emblema (coliseu + pontinhos) | escura (`#2B2218`) | fundos **claros** |
| `emblema-claro.svg`  | só o emblema | clara (`#F4EFE3`) | fundos **escuros** |
| `arena-sagaz-escuro.svg` | emblema + nome "Arena Sagaz" | escura | fundos **claros** |
| `arena-sagaz-claro.svg`  | emblema + nome "Arena Sagaz" | clara | fundos **escuros** |

A madeira (`#8A5A33` / contorno `#5E3D22`) e o **traço de ouro** (`#D9A441`) são
fixos nas quatro versões; "Sagaz" é sempre dourado. Fundo **transparente**.

## Como foram gerados (reprodutível)

- **Emblema:** espelha 1:1 a geometria de `lib/shared/emblema_arena.dart`
  (`EmblemaPainter`) — mesmos pontos, traços, arcos e cores. O desenho é
  **centralizado verticalmente** (folga igual em cima e embaixo).
- **Nome "Arena Sagaz":** fonte **Baloo 2** (peso 800), **convertida em contornos
  (paths)** via `fonttools` — por isso o SVG **não depende** de a fonte estar
  instalada para renderizar certo.

> Estes são arquivos de **marca** (fonte), não são carregados pelo app em runtime
> (o app desenha o emblema pelo vetor `EmblemaArena`). Servem para exportar PNGs,
> ícones de loja, materiais etc.
