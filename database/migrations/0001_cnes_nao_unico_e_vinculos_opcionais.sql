USE oris_db;

ALTER TABLE unidades
    DROP INDEX uk_unidades_cnes,
    ADD INDEX ix_unidades_cnes (cnes);

ALTER TABLE unidades
    ADD COLUMN unidade_e_mista BOOLEAN NOT NULL DEFAULT FALSE AFTER cnes;

ALTER TABLE servicos
    MODIFY COLUMN unidade_id INT NULL;

ALTER TABLE equipamentos
    MODIFY COLUMN unidade_id INT NULL;
