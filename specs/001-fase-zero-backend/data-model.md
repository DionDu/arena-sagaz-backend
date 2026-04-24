# Modelo de Dados: Backend Arena Sagaz

**Branch**: `001-fase-zero-backend` | **Data**: 2026-04-19
**Spec**: [spec.md](spec.md) | **Pesquisa**: [research.md](research.md)

---

## Entidades do Banco de Dados (PostgreSQL)

### 1. `usuarios`

Representa a conta de um jogador registrado.

| Coluna            | Tipo                    | Restrições                        | Descrição                              |
|-------------------|-------------------------|-----------------------------------|----------------------------------------|
| `id`              | `UUID`                  | PK, padrão: `gen_random_uuid()`   | Identificador único do usuário         |
| `apelido`         | `VARCHAR(50)`           | NOT NULL, UNIQUE                  | Nome de exibição no ranking            |
| `email`           | `VARCHAR(255)`          | NOT NULL, UNIQUE                  | E-mail para autenticação               |
| `senha_hash`      | `VARCHAR(255)`          | NOT NULL                          | Hash bcrypt da senha                   |
| `nivel`           | `INTEGER`               | NOT NULL, padrão: `1`, mín: `1`   | Nível de progressão do jogador         |
| `xp_total`        | `INTEGER`               | NOT NULL, padrão: `0`, mín: `0`   | XP acumulado ao longo da vida          |
| `email_verificado`| `BOOLEAN`               | NOT NULL, padrão: `false`         | Indica se o e-mail foi confirmado      |
| `criado_em`       | `TIMESTAMPTZ`           | NOT NULL, padrão: `now()`         | Data de cadastro                       |
| `atualizado_em`   | `TIMESTAMPTZ`           | NOT NULL, padrão: `now()`         | Última atualização do registro         |

**Índices**: `ix_usuarios_email` (UNIQUE), `ix_usuarios_apelido` (UNIQUE)

---

### 2. `tokens_refresh`

Armazena tokens de renovação de sessão para suporte ao fluxo JWT + refresh.

| Coluna        | Tipo           | Restrições                     | Descrição                                        |
|---------------|----------------|--------------------------------|--------------------------------------------------|
| `id`          | `UUID`         | PK, padrão: `gen_random_uuid()`| Identificador do token                           |
| `usuario_id`  | `UUID`         | NOT NULL, FK → `usuarios.id`   | Dono do token                                    |
| `token_hash`  | `VARCHAR(255)` | NOT NULL, UNIQUE               | Hash SHA-256 do token opaco                      |
| `expira_em`   | `TIMESTAMPTZ`  | NOT NULL                       | Data/hora de expiração (padrão: +30 dias)        |
| `revogado`    | `BOOLEAN`      | NOT NULL, padrão: `false`      | Marcado como revogado no logout ou troca de senha|
| `criado_em`   | `TIMESTAMPTZ`  | NOT NULL, padrão: `now()`      | Data de criação                                  |

**Índices**: `ix_tokens_refresh_token_hash` (UNIQUE), `ix_tokens_refresh_usuario_id`

**ON DELETE**: `CASCADE` em `usuario_id` — tokens removidos junto com o usuário.

---

### 3. `partidas`

Registro imutável de cada partida concluída por um jogador autenticado.

| Coluna              | Tipo            | Restrições                          | Descrição                                          |
|---------------------|-----------------|-------------------------------------|----------------------------------------------------|
| `id`                | `UUID`          | PK, padrão: `gen_random_uuid()`     | Identificador da partida                           |
| `usuario_id`        | `UUID`          | NOT NULL, FK → `usuarios.id`        | Jogador autenticado desta partida                  |
| `modo_jogo`         | `VARCHAR(20)`   | NOT NULL, CHECK IN lista abaixo     | `'vs_cpu'` ou `'vs_humano_local'`                  |
| `tamanho_tabuleiro` | `VARCHAR(10)`   | NOT NULL, CHECK IN lista abaixo     | `'pequeno'`, `'medio'` ou `'grande'`               |
| `dificuldade`       | `VARCHAR(10)`   | NULLABLE, CHECK IN lista abaixo     | `'facil'`, `'normal'`, `'sagaz'` (NULL se humano)  |
| `caixas_jogador`    | `INTEGER`       | NOT NULL, mín: `0`                  | Caixas fechadas pelo jogador autenticado           |
| `caixas_adversario` | `INTEGER`       | NOT NULL, mín: `0`                  | Caixas fechadas pelo adversário                    |
| `resultado`         | `VARCHAR(10)`   | NOT NULL, CHECK IN lista abaixo     | `'vitoria'`, `'derrota'` ou `'empate'`             |
| `xp_obtido`         | `INTEGER`       | NOT NULL, mín: `0`                  | XP calculado e atribuído ao jogador                |
| `pontuacao_obtida`  | `INTEGER`       | NOT NULL, mín: `0`                  | Pontuação adicionada ao ranking                    |
| `jogado_em`         | `TIMESTAMPTZ`   | NOT NULL, padrão: `now()`           | Timestamp de conclusão da partida                  |

**CHECK constraints**:
- `modo_jogo IN ('vs_cpu', 'vs_humano_local')`
- `tamanho_tabuleiro IN ('pequeno', 'medio', 'grande')`
- `dificuldade IN ('facil', 'normal', 'sagaz') OR dificuldade IS NULL`
- `resultado IN ('vitoria', 'derrota', 'empate')`

**Índices**: `ix_partidas_usuario_id`, `ix_partidas_jogado_em`

**ON DELETE**: `RESTRICT` em `usuario_id` — não permite excluir usuário com partidas.

---

### 4. `ranking`

Visão agregada e materializada da pontuação de cada jogador. Atualizada
transacionalmente junto com cada sincronização de partida.

| Coluna             | Tipo          | Restrições                        | Descrição                          |
|--------------------|---------------|-----------------------------------|------------------------------------|
| `id`               | `UUID`        | PK, padrão: `gen_random_uuid()`   | Identificador do registro          |
| `usuario_id`       | `UUID`        | NOT NULL, FK → `usuarios.id`, UNIQUE | Jogador (1 linha por jogador)   |
| `pontuacao_total`  | `INTEGER`     | NOT NULL, padrão: `0`, mín: `0`   | Soma das pontuações de partidas    |
| `partidas_jogadas` | `INTEGER`     | NOT NULL, padrão: `0`, mín: `0`   | Total de partidas sincronizadas    |
| `vitorias`         | `INTEGER`     | NOT NULL, padrão: `0`, mín: `0`   | Total de vitórias                  |
| `atualizado_em`    | `TIMESTAMPTZ` | NOT NULL, padrão: `now()`         | Última atualização                 |

**Índices**: `ix_ranking_pontuacao_total DESC` (para consulta ordenada eficiente),
`ix_ranking_usuario_id` (UNIQUE)

---

### 5. `trofeus`

Catálogo de conquistas desbloqueáveis. Populado via carga SQL inicial.

| Coluna      | Tipo            | Restrições                      | Descrição                          |
|-------------|-----------------|---------------------------------|------------------------------------|
| `id`        | `UUID`          | PK, padrão: `gen_random_uuid()` | Identificador do troféu            |
| `codigo`    | `VARCHAR(50)`   | NOT NULL, UNIQUE                | Código interno (ex: `'primeira_vitoria'`) |
| `nome`      | `VARCHAR(100)`  | NOT NULL                        | Nome de exibição                   |
| `descricao` | `TEXT`          | NOT NULL                        | Descrição da conquista             |
| `criterio`  | `VARCHAR(255)`  | NOT NULL                        | Regra de desbloqueio               |

---

### 6. `usuario_trofeus`

Tabela de junção: troféus conquistados por cada usuário.

| Coluna          | Tipo          | Restrições                       | Descrição                      |
|-----------------|---------------|----------------------------------|--------------------------------|
| `usuario_id`    | `UUID`        | NOT NULL, FK → `usuarios.id`     | Usuário que conquistou         |
| `trofeu_id`     | `UUID`        | NOT NULL, FK → `trofeus.id`      | Troféu conquistado             |
| `conquistado_em`| `TIMESTAMPTZ` | NOT NULL, padrão: `now()`        | Momento da conquista           |

**PK composta**: `(usuario_id, trofeu_id)`

---

## Estrutura de Dados da Fase Zero (Arquivos Locais)

### Dataset de Treinamento (`.npz`)

Cada arquivo `.npz` armazena um lote de registros de treinamento:

```python
# Conteúdo de cada arquivo npz
{
    "estados":  numpy.ndarray,  # shape: (N, 2*H+1, 2*W+1), dtype=int8
    "rotulos":  numpy.ndarray,  # shape: (N,), dtype=str — ex: "H_0_1"
    "indices":  numpy.ndarray,  # shape: (N,), dtype=int32 — índice global do registro
}
```

**Convenção de nomes de arquivo**: `dataset_{tamanho}_{lote:04d}.npz`
Exemplo: `dataset_pequeno_0001.npz`, `dataset_grande_0010.npz`

### Arquivo de Índice de Checkpoint (`.json`)

Um arquivo por tamanho de tabuleiro, atualizado após cada lote:

```json
{
  "tamanho": "pequeno",
  "total_alvo": 50000,
  "total_gerado": 15000,
  "ultimo_lote": 3,
  "profundidade_minimax": 7,
  "iniciado_em": "2026-04-19T10:00:00Z",
  "atualizado_em": "2026-04-19T10:45:00Z"
}
```

---

## Fórmula de Cálculo de XP (RF-019)

```
xp_base      = caixas_fechadas_pelo_jogador × 1
bonus_vitoria = 20  (configurável via variável de ambiente XP_BONUS_VITORIA)
multiplicador = { 'facil': 1.0, 'normal': 1.5, 'sagaz': 2.0, 'vs_humano': 1.0 }

xp_obtido    = int((xp_base + bonus_vitoria_se_venceu) × multiplicador)
pontuacao    = xp_obtido  # pontuação de ranking = XP obtido nesta versão
```

---

## Diagrama de Relacionamentos (texto)

```
usuarios ──┬── 1:N ──► partidas
           ├── 1:1 ──► ranking
           ├── 1:N ──► tokens_refresh
           └── N:M ──► trofeus (via usuario_trofeus)

trofeus ───────────── N:M ──► usuarios (via usuario_trofeus)
```
