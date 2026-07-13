"""Pacote de persistência do log de partidas (spec 006 — Conta na Nuvem).

Grava, dentro da mesma transação do evento de sincronização, o núcleo genérico
(schema ``partida``: partida/jogada/xp_partida) e a extensão do Pontinhos
(schema ``jogo_pontinhos``). O dono é o ``id_usuario`` do token — que já é o
pseudônimo, porque a exclusão de conta ANONIMIZA a linha em vez de deletá-la
(o antigo ``co_anonimo`` das filhas foi removido na migração 0007).

Esqueleto criado na Fase 1 (T002). Implementação na US2 (T040), somente após o
portão G2 (validação do DDL) liberar as tabelas.
"""
