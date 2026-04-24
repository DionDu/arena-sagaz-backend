-- Selos de progressão de nível do Arena Sagaz
-- Executar com: psql -h localhost -U arena -d arena_sagaz -f sql/002_selos_iniciais.sql

INSERT INTO trofeus (id, codigo, nome, descricao, criterio)
VALUES
  (gen_random_uuid(), 'nivel_5', 'Nível 5', 'Alcance o nível 5.', 'nivel >= 5'),
  (gen_random_uuid(), 'nivel_10', 'Nível 10', 'Alcance o nível 10.', 'nivel >= 10'),
  (gen_random_uuid(), 'nivel_25', 'Nível 25', 'Alcance o nível 25.', 'nivel >= 25'),
  (gen_random_uuid(), 'nivel_50', 'Meio Centenário', 'Alcance o nível 50.', 'nivel >= 50'),
  (gen_random_uuid(), 'nivel_100', 'Lendário', 'Alcance o nível 100.', 'nivel >= 100')
ON CONFLICT (codigo) DO NOTHING;
