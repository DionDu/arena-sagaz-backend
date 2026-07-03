"""Pacote de persistência do log de partidas (spec 006 — Conta na Nuvem).

Grava, dentro da mesma transação do evento de sincronização, o núcleo genérico
(schema ``partida``: partida/jogada/xp_partida) e a extensão do Pontinhos
(schema ``jogo_pontinhos``). Preserva o ``co_anonimo`` do J1 (LGPD, FR-024).

Esqueleto criado na Fase 1 (T002). Implementação na US2 (T040), somente após o
portão G2 (validação do DDL) liberar as tabelas.
"""
