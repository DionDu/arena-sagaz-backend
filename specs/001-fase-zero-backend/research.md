# Pesquisa Técnica: Backend Arena Sagaz — Fase Zero

**Branch**: `001-fase-zero-backend` | **Data**: 2026-04-19
**Plano**: [plan.md](plan.md)

---

## 1. Algoritmo Minimax com Poda Alpha-Beta para o Jogo dos Pontinhos

**Decisão**: Implementar Minimax recursivo com Poda Alpha-Beta pura, sem heurística
de posição (função de avaliação = diferença de caixas fechadas no estado terminal
ou no limite de profundidade).

**Fundamentação**:
- O Jogo dos Pontinhos possui fator de ramificação igual ao número de traços
  disponíveis (31 para Pequeno, 49 para Médio, 82 para Grande).
- A profundidade 7 com poda Alpha-Beta reduz o número de nós explorados de `b^d`
  para aproximadamente `b^(d/2)`, tornando viável a geração sem GPU.
- A pontuação de avaliação no limite de profundidade será `caixas_ia - caixas_humano`,
  garantindo que o algoritmo priorize fechamentos e bloqueios mesmo sem explorar
  o estado final completo.

**Alternativas Consideradas**:
- MCTS (Monte Carlo Tree Search): descartado — requer muitas simulações aleatórias
  para convergir; qualidade do rótulo inferior para datasets pequenos (50k).
- Minimax sem poda: descartado — intratável para tabuleiro Grande sem limite de
  profundidade razoável.

**Implicação para RF-004**: O limite padrão de profundidade 7 se aplica a todos
os tamanhos. Para o tabuleiro Grande, estima-se tempo médio de 0,5–2 s por estado
com profundidade 7; ajuste empírico durante a geração.
*(Nota Speckit/Claude: Originalmente planejado como single-thread, o gerador foi refatorado para utilizar `ProcessPoolExecutor` (multiprocessing), aproveitando até 100% da CPU e reduzindo o tempo do tabuleiro pequeno de 21 horas para menos de 2 horas. As lógicas dos eixos H/V também foram consertadas em tabuleiro.py pois as caixas adjacentes não estavam sendo reconhecidas corretamente)*

---

## 2. Representação do Estado do Tabuleiro (Matriz Numérica)

**Decisão**: Matriz NumPy de inteiros de 8 bits (`numpy.int8`) com dimensões
`(2*H+1, 2*W+1)`, onde `H` = número de linhas de caixas e `W` = colunas.

**Fundamentação**:
- `int8` cobre o intervalo [-128, 127], suficiente para os valores `{-1, 0, 1, 8, 9}`.
- Uso de `int8` reduz o tamanho do dataset em 75% comparado a `int32` (≈ 580 MB
  vs 2,3 GB para 150k registros totais com matrizes de tamanho Grande).
- A estrutura espelho da matriz (pontos em índices pares, traços/caixas em índices
  ímpares) é natural para CNNs convolucionais — padrões visuais são diretamente
  codificados na geometria da matriz.

**Formato de Persistência**: `.npz` comprimido (NumPy archive) por lote de 5.000
registros, com um arquivo de índice `.json` por tamanho de tabuleiro rastreando
checkpoints.

---

## 3. Abstração Visual (Matriz → PNG)

**Decisão**: Matplotlib com `imshow` e mapa de cores personalizado; cada célula
renderizada como quadrado de pixels com borda de separação.

**Fundamentação**:
- Matplotlib é a biblioteca padrão do ecossistema Python para visualização
  científica; sem dependências adicionais.
- A renderização por `imshow` converte naturalmente a matriz numérica em imagem
  colorida com mapeamento de valor → cor.
- Resolução de saída: 200×200 px (tabuleiro Pequeno) a 400×400 px (Grande),
  suficiente para inspeção visual no TCC.

**Mapeamento de cores**:
- `8` (ponto fixo) → preto `#000000`
- `0` (vazio) → branco `#FFFFFF`
- `9` (aresta/traço preenchido) → cinza `#808080`
- `1` (caixa fechada pelo Jogador 1 / IA) → azul `#0057B7`
- `-1` (caixa fechada pelo Jogador 2 / Humano) → vermelho `#C1392B`

---

## 4. Simulador Tático

**Decisão**: Pygame como biblioteca de interface gráfica do simulador.
*(Nota Speckit/Claude: Pygame-CE foi utilizado e bugs na lógica de renderização `_desenhar` e conversão de `mx/my` nos eixos do tabuleiro foram corrigidos para o simulador mostrar visualmente o preenchimento de cada traço (azul ou vermelho) assim como os quadrados preenchidos, não apenas círculos e pontos).*

**Fundamentação**:
- Pygame é mais adequado que Tkinter para atualização de tela em tempo real com
  cliques em regiões específicas (grade de traços).
- O simulador não precisa de widgets de UI complexos (botões, campos de texto);
  apenas renderização de grade e captura de cliques de mouse.
- Tkinter seria suficiente mas tem limitações de desempenho para re-render frequente
  da grade inteira após cada jogada.
- A interface é exclusivamente para laboratório — não há requisito de portabilidade
  ou empacotamento.

**Alternativa considerada**: Jupyter Notebook com ipywidgets — descartado pela
complexidade de setup e latência de interação.

---

## 5. Estrutura da API FastAPI

**Decisão**: Arquitetura por módulo de domínio (`usuarios/`, `auth/`, `partidas/`,
`ranking/`), cada um com suas próprias rotas, esquemas Pydantic, serviços e
modelos SQLAlchemy. Router principal em `api/main.py` agrega todos os sub-routers
com prefixo `/v1`.

**Fundamentação**:
- Separação por domínio facilita testes unitários isolados por módulo.
- SQLAlchemy assíncrono (`asyncpg`) é necessário para suportar o volume de 500
  requisições simultâneas definido em CS-006 sem bloqueio de I/O.
- Alembic gerencia migrações de esquema de forma controlada e versionada.

**Estratégia de Camadas**:
```
Rota (FastAPI) → Serviço (lógica de negócio) → Repositório (SQLAlchemy) → Banco
```
- Camada de serviço contém toda lógica de negócio (cálculo de XP, atualização de
  ranking, validações de negócio).
- Camada de rota valida entrada via Pydantic e delega ao serviço.
- Testes unitários mockam o repositório; testes de integração usam banco real
  (PostgreSQL em contêiner Docker local).

---

## 6. Autenticação JWT com Refresh Token

**Decisão**: `python-jose` para geração/validação de JWT (HS256); refresh tokens
armazenados como hashes bcrypt na tabela `tokens_refresh`.

**Fundamentação**:
- `python-jose` é a biblioteca JWT recomendada no ecossistema FastAPI; bem
  documentada e ativamente mantida.
- Refresh tokens opacos (não JWT) armazenados como hashes impedem vazamento de
  informações mesmo em caso de dump do banco.
- A tabela `tokens_refresh` permite revogação explícita (logout, troca de senha).
- Access token: HS256, payload com `sub` (usuario_id), `exp`, `iat`.
- Refresh token: 32 bytes aleatórios (`secrets.token_urlsafe(32)`), armazenado
  como hash SHA-256 no banco.

---

## 7. Hospedagem no Railway

**Decisão**: Um serviço Railway para a API FastAPI + um serviço Railway PostgreSQL
gerenciado. Variáveis de ambiente para todas as configurações sensíveis.

**Fundamentação**:
- Railway suporta deploy por Dockerfile ou Nixpacks; Dockerfile permite controle
  total da imagem de produção.
- Banco PostgreSQL gerenciado pelo Railway elimina overhead de administração de
  infraestrutura para um projeto de TCC.
- O health check em `GET /v1/health` é configurado como `healthcheckPath` no
  `railway.json` para reinicialização automática em caso de falha.
- Variáveis de ambiente gerenciadas via painel Railway: `DATABASE_URL`,
  `JWT_SECRET`, `JWT_EXPIRACAO_MINUTOS`, `REFRESH_TOKEN_EXPIRACAO_DIAS`.

---

## 8. Logging Estruturado

**Decisão**: `python-logging` com handler customizado que serializa para JSON;
integração via middleware FastAPI para logar todas as requisições HTTP.

**Fundamentação**:
- Railway agrega logs de stdout; JSON estruturado permite filtragem e busca no
  painel de logs do Railway sem ferramentas adicionais.
- Campos obrigatórios por log: `timestamp` (ISO 8601), `nivel`, `modulo`,
  `mensagem`, e campos opcionais contextuais (`usuario_id`, `rota`, `duracao_ms`).
- Para o gerador de dados, o log também registra progresso: `registros_gerados`,
  `tempo_decorrido_s`, `estimativa_restante_s`.

---

## 9. Estratégia de Testes

**Decisão**: pytest com três categorias:
1. **Testes Unitários** (`tests/unitarios/`): lógica pura sem I/O externo — Minimax,
   cálculo de XP, validação de estado do tabuleiro, geração de tokens.
2. **Testes de Integração** (`tests/integracao/`): endpoints FastAPI com banco
   PostgreSQL real em Docker (via `pytest-asyncio` + `httpx.AsyncClient`).
3. **Testes de Contrato** (incluídos nos de integração): validam schemas de
   entrada/saída dos endpoints contra as definições em `contracts/`.

**Cobertura mínima alvo**: 80% nas camadas de serviço (`servico.py`) e domínio
(`minimax.py`, `tabuleiro.py`), conforme Princípio III da Constituição.
