"""Pacote de sincronização offline<->servidor (spec 006 — Conta na Nuvem).

Expõe os endpoints ``/v1`` que recebem os eventos da outbox do app (upload de
delta comprimido com gzip) e o merge convidado->conta. A persistência do log de
partidas em si vive em :mod:`api.partidas`; o ranking/XP em :mod:`api.ranking`.

Esqueleto criado na Fase 1 (T002). Endpoints implementados na US1 (T032/T033),
somente após o portão G2 (validação do DDL) liberar as tabelas.
"""
