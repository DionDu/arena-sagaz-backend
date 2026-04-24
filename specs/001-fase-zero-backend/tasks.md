# Tasks: Backend Arena Sagaz — Fase Zero e Infraestrutura de Dados

**Input**: Design documents from `specs/001-fase-zero-backend/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api-v1.md ✅

**Tests**: Incluídos conforme o Princípio III da Constituição (testes unitários para `minimax.py`, `tabuleiro.py`, cálculo de XP e geração de JWT; testes de integração com banco real para todos os endpoints).

**Organization**: Tarefas agrupadas por jornada de usuário para possibilitar implementação e teste independentes de cada jornada.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências)
- **[Story]**: Jornada de usuário correspondente (US1–US5)
- Caminhos exatos incluídos em todas as descrições

---

## Phase 1: Setup (Infraestrutura Compartilhada)

**Objetivo**: Inicialização do projeto e criação da estrutura de diretórios definida no plano.

- [x] T001 Criar estrutura completa de diretórios: `api/banco/migrations/`, `api/auth/`, `api/usuarios/`, `api/partidas/`, `api/ranking/`, `api/trofeus/`, `api/nucleo/`, `gerador_dados/simulador/`, `tests/unitarios/`, `tests/integracao/`, `sql/`, `dados/`, `modelos/`
- [x] T002 [P] Criar `requirements.txt` com todas as dependências: FastAPI, SQLAlchemy[asyncio], Alembic, Pydantic v2, python-jose[cryptography], bcrypt, asyncpg, NumPy, Matplotlib, Pygame, tflite-runtime, pytest, pytest-asyncio, httpx, pytest-cov
- [x] T003 [P] Criar `.env.example` com variáveis: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRACAO_MINUTOS=60`, `REFRESH_TOKEN_EXPIRACAO_DIAS=30`, `XP_BONUS_VITORIA=20`, `AMBIENTE=desenvolvimento`
- [x] T004 [P] Criar `.gitignore` cobrindo: `dados/`, `modelos/`, `__pycache__/`, `.env`, `*.pyc`, `.pytest_cache/`, `*.npz`, `*.tflite`
- [x] T005 [P] Criar `Dockerfile` para deploy no Railway: imagem `python:3.11-slim`, instalação de dependências, `CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- [x] T006 [P] Criar `railway.json` com configuração de health check: `healthcheckPath: "/v1/health"`, `restartPolicyType: "ON_FAILURE"`
- [x] T007 Inicializar Alembic: criar `alembic.ini` apontando para `api/banco/migrations/` e configurar `api/banco/migrations/env.py` com engine assíncrono

**Checkpoint**: Estrutura do projeto criada — pronta para desenvolvimento das fases fundacional e de jornadas.

---

## Phase 2: Foundacional (Pré-requisitos Bloqueantes)

**Objetivo**: Infraestrutura central que DEVE estar completa antes que qualquer jornada de usuário possa ser implementada.

**⚠️ CRÍTICO**: Nenhuma jornada pode começar antes que esta fase esteja concluída.

- [x] T008 Criar `api/configuracao.py` com `Pydantic BaseSettings`: campos `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRACAO_MINUTOS`, `REFRESH_TOKEN_EXPIRACAO_DIAS`, `XP_BONUS_VITORIA`, `AMBIENTE`; leitura automática do arquivo `.env`
- [x] T009 [P] Criar `api/nucleo/log.py`: handler Python `logging` que serializa para JSON com campos obrigatórios `timestamp` (ISO 8601), `nivel`, `modulo`, `mensagem`; campos opcionais `usuario_id`, `rota`, `duracao_ms`
- [x] T010 [P] Criar `api/nucleo/excecoes.py`: hierarquia de exceções de domínio (`ErroNegocio`, `ErroConflito`, `ErroNaoAutorizado`, `ErroNaoEncontrado`) e handlers FastAPI que as convertem para respostas JSON no formato `{"detalhe": "...", "codigo": "..."}`
- [x] T011 [P] Criar `api/nucleo/seguranca.py`: funções `gerar_hash_senha(senha)`, `verificar_senha(senha, hash)` com bcrypt; `criar_token_acesso(dados)`, `verificar_token_acesso(token)` com python-jose HS256; `gerar_refresh_token()` com `secrets.token_urlsafe(32)` e `criar_hash_token(token)` com SHA-256
- [x] T012 Criar `api/banco/conexao.py`: engine SQLAlchemy assíncrono com `asyncpg`, `AsyncSession`, factory `get_sessao()` como context manager; configurar `create_async_engine` com pool adequado (pool_size=20, max_overflow=10)
- [x] T013 Criar `api/nucleo/dependencias.py`: dependência FastAPI `get_sessao` (injeta `AsyncSession`), `usuario_atual` (extrai e valida JWT do header Authorization, retorna modelo `Usuario`)
- [x] T014 Criar `api/main.py`: instanciar `FastAPI(title="Arena Sagaz API", version="1.0.0")`; registrar todos os sub-routers com prefixo `/v1`; adicionar middleware de logging de requisições HTTP (método, rota, status, duração)
- [x] T015 [P] Criar `tests/conftest.py`: fixtures `engine_teste` (SQLite async ou PostgreSQL Docker), `sessao_teste`, `cliente_http` (httpx AsyncClient apontando para app de testes), `usuario_autenticado` (cria usuário e retorna token JWT)

**Checkpoint**: Base pronta — implementação das jornadas pode começar em paralelo.

---

## Phase 3: Jornada 1 — Gerador de Massa de Dados (Prioridade: P1) 🎯 MVP

**Objetivo**: Script CLI que gera 50.000 pares (estado, rótulo ótimo) por tamanho de tabuleiro usando Minimax com Poda Alpha-Beta, com persistência em `.npz` e suporte a checkpoint.

**Teste Independente**: Executar `python gerador_dados/gerador.py --tamanho pequeno --total 100 --profundidade 7` e verificar que 100 registros válidos são gravados em `dados/dataset_pequeno_0001.npz` e que o arquivo de checkpoint `dados/checkpoint_pequeno.json` contém `"total_gerado": 100`.

### Implementação — Jornada 1

- [x] T016 [US1] Criar `gerador_dados/tabuleiro.py`: classe `EstadoTabuleiro` com atributos `linhas`, `colunas`, `matriz` (NumPy int8, dims `(2*H+1, 2*W+1)`); métodos `tracos_disponiveis()`, `aplicar_traco(label)`, `desfazer_traco(label)`, `caixas_fechadas_por(jogador)`, `esta_terminal()`, `clonar()`; valores de célula: `8` (ponto), `0` (vazio), `9` (aresta preenchida), `1` (caixa J1), `-1` (caixa J2); labels formato `H_linha_coluna` e `V_linha_coluna`. *(Nota Speckit/Claude: Bug nos eixos H/V foi corrigido para que as caixas sejam de fato fechadas)*
- [x] T017 [P] [US1] Criar `tests/unitarios/test_tabuleiro.py`: testar geração de estado inicial para os 3 tamanhos, aplicação/desfazimento de traços horizontais e verticais, contagem correta de caixas fechadas, detecção de estado terminal, impossibilidade de traço duplicado
- [x] T018 [US1] Criar `gerador_dados/minimax.py`: função `minimax(estado, profundidade, alpha, beta, maximizando)` recursiva com Poda Alpha-Beta; função de avaliação `avaliar(estado)` = `caixas_ia - caixas_humano`; função `melhor_jogada(estado, profundidade)` que retorna o label do traço ótimo; respeitar turno extra quando jogador fecha caixa
- [x] T019 [P] [US1] Criar `tests/unitarios/test_minimax.py`: testar que Minimax fecha caixa com 3 lados preenchidos (cenário óbvio), evita dar caixa ao adversário, retorna resultado correto em estado terminal, executa sem travar para profundidade 3 em tabuleiro Pequeno
- [x] T020 [US1] Criar `gerador_dados/gerador.py`: CLI com argparse (`--tamanho` {pequeno,medio,grande}, `--total` int, `--profundidade` int=7, `--retomar` flag); gerar estados aleatórios válidos (preenchimento parcial aleatório ≤ 50% dos traços), calcular rótulo via `melhor_jogada()`, acumular em lotes de 5.000 registros, salvar em `dados/dataset_{tamanho}_{lote:04d}.npz` com arrays `estados`, `rotulos`, `indices`; atualizar `dados/checkpoint_{tamanho}.json` após cada lote; log de progresso com quantidade gerada, tempo decorrido e estimativa de conclusão (RF-007). *(Nota Speckit/Claude: O script original foi totalmente refatorado para utilizar ProcessPoolExecutor/multiprocessing, resolvendo o gargalo de performance e permitindo o uso de 14 threads para gerar os dados muito mais rapidamente)*
- [x] T021 [US1] Adicionar validação em `gerador_dados/gerador.py`: garantir unicidade de estados via hash SHA-256 da matriz achatada (conjunto em memória por lote); ao retomar, carregar índices já gerados do checkpoint e pular duplicatas; tratar `KeyboardInterrupt` salvando checkpoint parcial antes de encerrar

**Checkpoint**: Jornada 1 funcional e testável independentemente. `python gerador_dados/gerador.py --tamanho pequeno --total 50000` deve completar sem erros.

---

## Phase 4: Jornada 2 — Abstração Visual (Prioridade: P1)

**Objetivo**: Módulo de conversão de matriz de estado em imagem PNG para inspeção visual da codificação do dataset.

**Teste Independente**: Criar manualmente uma `numpy.ndarray` int8 com estado conhecido, chamar `matriz_para_png(estado, "saida.png")` e verificar que a imagem gerada tem as cores corretas: azul `#0057B7` para J1, vermelho `#C1392B` para J2, preto para pontos, branco para vazios.

### Implementação — Jornada 2

- [x] T022 [US2] Criar `gerador_dados/visualizador.py`: função `matriz_para_png(matriz, caminho_saida, resolucao=200)` usando Matplotlib `imshow` com mapa de cores customizado (`8`→preto, `0`→branco, `1`→azul `#0057B7`, `-1`→vermelho `#C1392B`); função `lote_para_png(matrizes, diretorio_saida, prefixo="estado")` que gera uma PNG por matriz com nome `{prefixo}_{indice:05d}.png`; aceitar tanto `ndarray` quanto caminho para arquivo `.npy`
- [x] T023 [P] [US2] Criar `tests/unitarios/test_visualizador.py`: testar que `matriz_para_png` gera arquivo PNG no caminho especificado, que pixels correspondentes a `1` têm cor azul e `-1` têm cor vermelha (verificar pixel RGB via PIL/imageio), que `lote_para_png` gera N arquivos para N matrizes
- [x] T024 [P] [US2] Adicionar logging em `gerador_dados/visualizador.py`: log INFO ao iniciar e concluir lote, WARNING se diretório de saída não existir (criando-o automaticamente), ERROR se matriz tiver formato inválido

**Checkpoint**: Jornada 2 funcional. `python -c "from gerador_dados.visualizador import matriz_para_png; ..."` deve gerar PNG corretamente.

---

## Phase 5: Jornada 3 — Simulador Tático (Prioridade: P1)

**Objetivo**: Interface Pygame para partida completa Humano vs CNN (ou vs Minimax), exibindo tempo de decisão da IA e placar final.

**Teste Independente**: Executar `python gerador_dados/simulador/simulador_tatico.py --modo minimax --tamanho pequeno` — janela Pygame deve abrir mostrando grade do tabuleiro Pequeno; clicar em traço deve registrar jogada e exibir resposta do Minimax em < 1s; ao final da partida, placar correto deve ser exibido.

### Implementação — Jornada 3

- [x] T025 [US3] Criar `gerador_dados/simulador/simulador_tatico.py`: inicialização Pygame com janela redimensionável; renderização da grade do tabuleiro como grade de cliques (traços horizontais e verticais como regiões clicáveis); ciclo de turno (humano → IA → verificar fim); exibir placar de caixas em tempo real; exibir tempo de decisão da IA em ms após cada jogada (RF-012). *(Nota Speckit/Claude: Corrigido bug visual em Pygame e adicionado desenho das linhas efetivas e dos quadrados preenchidos que não estavam sendo renderizados pelas lógicas anteriores)*
- [x] T026 [US3] Adicionar suporte a dois modos de oponente em `gerador_dados/simulador/simulador_tatico.py`: `--modo cnn` carrega modelo `.tflite` via `tflite-runtime`, chama `interpreter.invoke()` com estado atual como entrada e seleciona traço de maior logit entre os disponíveis; `--modo minimax` usa `melhor_jogada()` com profundidade configurável via `--profundidade`; argumento `--modelo` especifica caminho do arquivo `.tflite`
- [x] T027 [US3] Adicionar validação de modelo em `gerador_dados/simulador/simulador_tatico.py`: ao iniciar com `--modo cnn`, verificar que o arquivo `.tflite` existe e tem tamanho > 0; exibir mensagem de erro descritiva e encerrar com código 1 se inválido (RF-015)
- [x] T028 [US3] Implementar lógica de fim de partida em `gerador_dados/simulador/simulador_tatico.py`: detectar quando todos os traços estão preenchidos, calcular caixas de cada jogador, exibir tela de resultado com vencedor e placar final, oferecer opção de nova partida (RF-014)
- [x] T029 [P] [US3] Adicionar alternância de modo durante sessão em `gerador_dados/simulador/simulador_tatico.py`: tecla `M` alterna entre modo CNN e Minimax sem reiniciar a partida; exibir modo atual na interface; registrar tempo médio de decisão da sessão no log ao encerrar (RF-013)

**Checkpoint**: Jornada 3 funcional. Simulador inicia, aceita jogadas do humano e responde com IA; placar correto ao final.

---

## Phase 6: Jornada 5 — Autenticação e Criação de Conta (Prioridade: P2)

**Objetivo**: Endpoints `POST /v1/usuarios`, `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/logout` e `GET /v1/usuarios/eu` funcionais com banco de dados real.

**Nota**: Esta jornada é pré-requisito para a Jornada 4 (sincronização de partidas).

**Teste Independente**: Executar sequência via httpx: criar conta → login → usar token para `GET /v1/usuarios/eu` → refresh token → logout; verificar que token revogado retorna 401.

### Implementação — Jornada 5

- [x] T030 [P] [US5] Criar `api/usuarios/modelo.py`: modelos SQLAlchemy `Usuario` (tabela `usuarios`) e `TokenRefresh` (tabela `tokens_refresh`) com todas as colunas do data-model.md; índices definidos; relacionamento `Usuario.tokens_refresh` com `cascade="all, delete-orphan"`
- [x] T031 [US5] Criar primeira migração Alembic em `api/banco/migrations/versions/`: criar tabelas `usuarios` e `tokens_refresh` com todas as constraints e índices do data-model.md; incluir `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")` para `gen_random_uuid()`
- [x] T032 [P] [US5] Criar `api/usuarios/esquemas.py`: `CriarUsuarioEntrada` (apelido 3–50 chars regex `^[a-zA-Z0-9_]+$`, email EmailStr, senha ≥ 8 chars), `UsuarioSaida` (id, apelido, email, nivel, xp_total, criado_em), `UsuarioComTokenSaida` (herda UsuarioSaida + acesso_token, refresh_token, expira_em)
- [x] T033 [P] [US5] Criar `api/auth/esquemas.py`: `LoginEntrada` (email, senha), `TokenSaida` (acesso_token, refresh_token, tipo_token="bearer", expira_em), `RefreshEntrada` (refresh_token), `TokenAcessoSaida` (acesso_token, tipo_token, expira_em), `LogoutEntrada` (refresh_token)
- [x] T034 [US5] Criar `api/usuarios/servico.py`: `criar_usuario(sessao, dados)` — verificar unicidade de email e apelido (lançar `ErroConflito` com códigos `EMAIL_DUPLICADO`/`APELIDO_DUPLICADO`), hashear senha com bcrypt, persistir `Usuario`, criar entrada inicial em `ranking` (pontuacao=0), gerar e retornar tokens JWT + refresh
- [x] T035 [US5] Criar `api/auth/servico.py`: `autenticar(sessao, email, senha)` — buscar usuário, verificar senha, lançar `ErroNaoAutorizado` genérico se falhar; `renovar_token(sessao, refresh_token)` — verificar hash SHA-256 no banco, checar expiração e revogação, retornar novo JWT; `revogar_token(sessao, refresh_token)` — marcar `revogado=True`
- [x] T036 [US5] Criar `api/usuarios/rotas.py`: `POST /usuarios` chama `servico.criar_usuario()` retorna 201; `GET /usuarios/eu` (protegido, depende de `usuario_atual`) retorna perfil com ranking embutido (consulta JOIN `ranking`)
- [x] T037 [US5] Criar `api/auth/rotas.py`: `POST /auth/login` retorna `TokenSaida` 200; `POST /auth/refresh` retorna `TokenAcessoSaida` 200; `POST /auth/logout` (protegido) retorna mensagem 200; registrar routers em `api/main.py`
- [x] T038 [P] [US5] Criar `tests/unitarios/test_seguranca.py`: testar `gerar_hash_senha`/`verificar_senha` (hash diferente do original, verificação correta/incorreta), `criar_token_acesso`/`verificar_token_acesso` (payload preservado, token expirado lança exceção), `gerar_refresh_token` (comprimento ≥ 32 bytes, único em duas chamadas)
- [x] T039 [P] [US5] Criar `tests/integracao/test_usuarios.py`: testar criação com dados válidos (201 + tokens), email duplicado (409 `EMAIL_DUPLICADO`), apelido duplicado (409 `APELIDO_DUPLICADO`), senha curta (422), `GET /usuarios/eu` com token válido (200), sem token (401)
- [x] T040 [P] [US5] Criar `tests/integracao/test_auth.py`: testar login com credenciais corretas (200 + tokens), credenciais erradas (401), refresh com token válido (200 novo JWT), refresh com token expirado/revogado (401), logout (200 + token revogado retorna 401)

**Checkpoint**: Jornada 5 funcional. Fluxo completo de criação de conta, login, uso autenticado e logout testável de forma independente.

---

## Phase 7: Jornada 4 — Sincronização de Partidas e Ranking (Prioridade: P2)

**Objetivo**: Endpoints `POST /v1/partidas` (cálculo de XP + ranking) e `GET /v1/ranking` (top-100 paginado) funcionais.

**Teste Independente**: Autenticar, sincronizar partida vitória no modo Sagaz, verificar XP calculado corretamente (`(caixas × 1 + 20) × 2`), verificar posição no ranking atualizada; consultar `GET /v1/ranking` e verificar jogador aparece ordenado.

### Implementação — Jornada 4

- [x] T041 [P] [US4] Criar `api/partidas/modelo.py`: modelo SQLAlchemy `Partida` (tabela `partidas`) com todas as colunas e CHECK constraints do data-model.md; FK `usuario_id → usuarios.id` com `ON DELETE RESTRICT`; índices `ix_partidas_usuario_id`, `ix_partidas_jogado_em`
- [x] T042 [P] [US4] Criar `api/ranking/modelo.py`: modelo SQLAlchemy `Ranking` (tabela `ranking`) com FK `usuario_id → usuarios.id` UNIQUE; índice `ix_ranking_pontuacao_total DESC`
- [x] T043 [P] [US4] Criar `api/trofeus/modelo.py`: modelos SQLAlchemy `Trofeu` (tabela `trofeus`) e `UsuarioTrofeu` (tabela `usuario_trofeus`) com PK composta `(usuario_id, trofeu_id)`
- [x] T044 [US4] Criar migração Alembic para tabelas `partidas`, `ranking`, `trofeus`, `usuario_trofeus` em `api/banco/migrations/versions/`; garantir ordem de criação respeitando FKs
- [x] T045 [P] [US4] Criar `api/partidas/esquemas.py`: `SincronizarPartidaEntrada` com validações: `modo_jogo` Literal, `tamanho_tabuleiro` Literal, `dificuldade` opcional obrigatório se vs_cpu, `caixas_jogador`/`caixas_adversario` ≥ 0, validador de soma de caixas (12/20/35 para pequeno/medio/grande com código `CAIXAS_INVALIDAS`); `PartidaSaida` com xp_obtido, pontuacao_obtida, nivel_anterior, nivel_atual, xp_total, posicao_ranking, trofeus_conquistados
- [x] T046 [P] [US4] Criar `api/ranking/esquemas.py`: `EntradaRankingSaida` (posicao, apelido, nivel, pontuacao_total, vitorias, partidas_jogadas), `RankingSaida` (total, pagina, tamanho, jogadores)
- [x] T047 [US4] Criar `api/partidas/servico.py`: `sincronizar_partida(sessao, usuario, dados)` — calcular XP usando fórmula do data-model.md: `xp_base = caixas_jogador`, `bonus = XP_BONUS_VITORIA se vitoria`, `multiplicador = {facil:1.0, normal:1.5, sagaz:2.0, vs_humano:1.0}`, `xp_obtido = int((xp_base + bonus) × mult)`; persistir `Partida`; atualizar `Usuario.xp_total`, `Usuario.nivel` (nível = `xp_total // 100 + 1`); atualizar `Ranking` (upsert: incrementar pontuacao_total, partidas_jogadas, vitorias); retornar `PartidaSaida`
- [x] T048 [P] [US4] Criar `tests/unitarios/test_xp.py`: testar cálculo de XP para todos os multiplicadores (fácil, normal, sagaz, vs_humano), com e sem bônus de vitória, verificar arredondamento correto (`int()`), testar atualização de nível (limites de XP)
- [x] T049 [US4] Criar `api/ranking/servico.py`: `consultar_ranking(sessao, pagina, tamanho)` — query `SELECT ranking.*, usuarios.apelido, usuarios.nivel FROM ranking JOIN usuarios ORDER BY pontuacao_total DESC`; calcular `posicao` como offset+índice; retornar `RankingSaida` com paginação; validar `tamanho ≤ 100`
- [x] T050 [US4] Criar `api/partidas/rotas.py`: `POST /partidas` (protegido) chama `servico.sincronizar_partida()` retorna 201; registrar router em `api/main.py`
- [x] T051 [US4] Criar `api/ranking/rotas.py`: `GET /ranking` (público) chama `servico.consultar_ranking()` com query params `pagina` e `tamanho`; registrar router em `api/main.py`
- [x] T052 [P] [US4] Criar `tests/integracao/test_partidas.py`: testar sincronização válida (201 + XP correto), dificuldade ausente em vs_cpu (422), soma de caixas inválida (400 `CAIXAS_INVALIDAS`), sem autenticação (401), idempotência (duas sincronizações acumulam corretamente)
- [x] T053 [P] [US4] Criar `tests/integracao/test_ranking.py`: testar ranking com múltiplos usuários (ordem correta por pontuação), paginação (pagina 2 retorna próximos), tamanho máximo 100 (tamanho=200 retorna 422), ranking vazio (200 com lista vazia)

**Checkpoint**: Jornada 4 funcional. Fluxo completo: autenticar → sincronizar partida → verificar XP → consultar ranking.

---

## Phase 8: Polish e Preocupações Transversais

**Objetivo**: Health check, dados iniciais SQL, testes de integração transversais e validação do quickstart.

- [x] T054 [P] Criar endpoint `GET /v1/health` em `api/main.py` (ou módulo dedicado `api/nucleo/rotas.py`): tentar query `SELECT 1` no banco; retornar `{"status": "ok", "banco_de_dados": "ok", "versao": "1.0.0"}` (200) ou `{"status": "degradado", "banco_de_dados": "indisponivel", "versao": "1.0.0"}` (503)
- [x] T055 [P] Criar `tests/integracao/test_health.py`: testar resposta 200 com banco disponível, verificar campos `status`, `banco_de_dados`, `versao` no JSON
- [x] T056 [P] Criar `sql/001_trofeus_iniciais.sql`: INSERT com dados de 5+ troféus iniciais (ex: `primeira_vitoria`, `dez_vitorias`, `primeiro_login`, `sagaz_master`) com `codigo`, `nome`, `descricao`, `criterio`; usar `INSERT INTO trofeus ... ON CONFLICT (codigo) DO NOTHING`
- [x] T057 [P] Criar `sql/002_selos_iniciais.sql`: INSERT com dados de selos iniciais de progressão (ex: `nivel_5`, `nivel_10`, `nivel_25`); mesmo padrão de upsert seguro
- [x] T058 Adicionar migração Alembic para carga inicial de troféus e selos em `api/banco/migrations/versions/`: executar os scripts SQL via `op.execute()` ou `op.bulk_insert()`
- [x] T059 [P] Revisar todos os módulos `servico.py` e adicionar log estruturado JSON: INFO em operações bem-sucedidas (criação de usuário, sincronização de partida, consulta de ranking), WARNING em tentativas com dados inválidos, ERROR em falhas de banco — usando `api/nucleo/log.py`
- [x] T060 [P] Adicionar log de progresso detalhado em `gerador_dados/gerador.py`: a cada 1.000 registros gerados, emitir JSON com `registros_gerados`, `total_alvo`, `porcentagem`, `tempo_decorrido_s`, `estimativa_restante_s` (RF-007). *(Nota Speckit/Claude: O log de progresso foi alterado para emitir a cada 50 registros ao invés de 1.000 para dar melhor feedback ao pesquisador após a refatoração para multiprocessing)*
- [x] T061 Executar validação completa do `specs/001-fase-zero-backend/quickstart.md`: seguir passo a passo, confirmar que todos os comandos executam sem erros, atualizar o guia se algum passo estiver desatualizado

**Checkpoint Final**: Todos os critérios de sucesso (CS-001–CS-007) verificáveis. Projeto pronto para implantação no Railway.

---

## Dependencies & Execution Order

### Dependências entre Fases

- **Setup (Phase 1)**: Sem dependências — pode iniciar imediatamente
- **Foundacional (Phase 2)**: Depende de Setup — BLOQUEIA todas as jornadas
- **Jornada 1 (Phase 3)**: Depende apenas de Foundacional (Phase 2)
- **Jornada 2 (Phase 4)**: Depende de Jornada 1 (usa `EstadoTabuleiro` de `tabuleiro.py`)
- **Jornada 3 (Phase 5)**: Depende de Jornada 1 (usa `minimax.py` e `tabuleiro.py`)
- **Jornada 5 (Phase 6)**: Depende de Foundacional (Phase 2) — independente das Jornadas 1–3
- **Jornada 4 (Phase 7)**: Depende de Jornada 5 (requer autenticação funcional)
- **Polish (Phase 8)**: Depende de todas as fases anteriores

### Dependências entre Jornadas

- **Jornada 1 (US1, P1)**: Pode iniciar após Foundacional — sem dependências de outras jornadas
- **Jornada 2 (US2, P1)**: Depende da Jornada 1 (`EstadoTabuleiro` de `tabuleiro.py`)
- **Jornada 3 (US3, P1)**: Depende da Jornada 1 (`minimax.py`, `tabuleiro.py`)
- **Jornada 5 (US5, P2)**: Pode iniciar após Foundacional, **em paralelo** com Jornadas 1–3
- **Jornada 4 (US4, P2)**: Depende da Jornada 5 (autenticação necessária)

### Dentro de Cada Jornada

- Modelos SQLAlchemy antes de serviços
- Serviços antes de rotas
- Implementação principal antes de integração
- Testes unitários podem ser escritos em paralelo com implementação (arquivos separados)

### Oportunidades de Paralelismo

- Todas as tasks [P] dentro de uma fase podem rodar em paralelo
- **Paralelismo máximo**: Jornadas 1–3 (Fase Zero) e Jornada 5 (API de usuários) podem ser desenvolvidas simultaneamente após Phase 2
- Modelos SQLAlchemy de diferentes domínios (T030, T041, T042, T043) podem ser criados em paralelo

---

## Parallel Example: Jornada 1 (Fase Zero)

```bash
# Modelos e testes em paralelo após T016:
Task: "Criar tests/unitarios/test_tabuleiro.py"   # T017 [P]
Task: "Criar gerador_dados/minimax.py"             # T018 (depende de T016)

# Após T018, em paralelo:
Task: "Criar tests/unitarios/test_minimax.py"      # T019 [P]
Task: "Criar gerador_dados/gerador.py"             # T020 (depende de T016, T018)
```

## Parallel Example: API (Jornadas 4 e 5)

```bash
# Após Phase 2, em paralelo:
Task: "Criar api/usuarios/modelo.py"               # T030 [P]
Task: "Criar api/usuarios/esquemas.py"             # T032 [P]
Task: "Criar api/auth/esquemas.py"                 # T033 [P]

# Após T030:
Task: "Criar migração Alembic usuarios/tokens"     # T031
Task: "Criar api/usuarios/servico.py"              # T034

# Após Phase 6 concluída, em paralelo:
Task: "Criar api/partidas/modelo.py"               # T041 [P]
Task: "Criar api/ranking/modelo.py"                # T042 [P]
Task: "Criar api/trofeus/modelo.py"                # T043 [P]
Task: "Criar api/partidas/esquemas.py"             # T045 [P]
Task: "Criar api/ranking/esquemas.py"              # T046 [P]
```

---

## Implementation Strategy

### MVP (Jornada 1 apenas — Fase Zero Completa)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundacional (**crítico — bloqueia tudo**)
3. Completar Phase 3: Jornada 1 (gerador de dados com Minimax)
4. **PARAR E VALIDAR**: Executar `python gerador_dados/gerador.py --tamanho pequeno --total 100` — verificar `.npz` e checkpoint
5. Resultado: Dataset de treino gerado — pré-requisito do TCC cumprido

### Entrega Incremental

1. Setup + Foundacional → Base pronta
2. Jornada 1 → Gerador de dados funcional → **Validar independentemente** (MVP!)
3. Jornada 2 → Visualizador → Inspecionar dataset gerado
4. Jornada 3 → Simulador → Validar CNN (Go/No-Go do TCC)
5. Jornada 5 → Auth API → Base para produto
6. Jornada 4 → Sincronização de partidas → Ranking global
7. Polish → Deploy Railway

### Estratégia com Equipe Paralela

Com dois desenvolvedores após Phase 2:
- **Dev A**: Jornadas 1 → 2 → 3 (Fase Zero, scripts locais)
- **Dev B**: Jornada 5 → 4 (API FastAPI + banco)

As duas trilhas são completamente independentes após Phase 2.

---

## Notes

- `[P]` = arquivos diferentes, sem dependências entre si — podem rodar em paralelo
- Label `[USN]` mapeia tarefa para jornada de usuário para rastreabilidade
- Cada jornada é independentemente testável sem depender das outras
- Fazer commit após cada tarefa ou grupo lógico de tarefas
- Parar nos checkpoints para validar a jornada de forma isolada
- Testes de integração usam banco PostgreSQL real (Docker local): `docker run -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:15`
- Evitar: tarefas vagas, conflitos no mesmo arquivo, dependências entre jornadas que quebrem a independência
