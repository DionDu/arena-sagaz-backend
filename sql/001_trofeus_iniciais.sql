-- Troféus iniciais do Arena Sagaz
-- Executar com: psql -h localhost -U arena -d arena_sagaz -f sql/001_trofeus_iniciais.sql

INSERT INTO trofeus (id, codigo, nome, descricao, criterio)
VALUES
  (gen_random_uuid(), 'primeira_vitoria', 'Primeira Vitória', 'Vença sua primeira partida.', 'vitorias >= 1'),
  (gen_random_uuid(), 'dez_vitorias', 'Dez Vitórias', 'Acumule 10 vitórias.', 'vitorias >= 10'),
  (gen_random_uuid(), 'cem_vitorias', 'Centurião', 'Acumule 100 vitórias.', 'vitorias >= 100'),
  (gen_random_uuid(), 'sagaz_master', 'Sagaz Master', 'Vença uma partida no modo Sagaz.', 'vitoria em modo sagaz'),
  (gen_random_uuid(), 'primeiro_login', 'Bem-vindo!', 'Crie sua conta e faça o primeiro login.', 'conta criada'),
  (gen_random_uuid(), 'partidas_50', 'Dedicado', 'Jogue 50 partidas.', 'partidas_jogadas >= 50'),
  (gen_random_uuid(), 'partidas_200', 'Veterano', 'Jogue 200 partidas.', 'partidas_jogadas >= 200')
ON CONFLICT (codigo) DO NOTHING;
