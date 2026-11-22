USE oris_db;

ALTER TABLE unidades
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE servicos
    MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE equipamentos
    MODIFY COLUMN situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    ADD COLUMN descricao_situacao TEXT NULL;

ALTER TABLE alteracoes
    ADD COLUMN motivo_rejeicao TEXT NULL;
