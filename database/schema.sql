CREATE DATABASE IF NOT EXISTS oris_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE oris_db;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    perfil ENUM('ADMINISTRADOR', 'GESTAO_INFORMACAO', 'RESPONSAVEL_SAUDE_BUCAL', 'GESTOR') NOT NULL,
    ativo BOOL NOT NULL DEFAULT TRUE,
    origem ENUM('LOCAL', 'LDAP', 'OIDC') NOT NULL DEFAULT 'LOCAL',
    identificador_externo VARCHAR(255) NULL,
    mfa_ativo BOOL NOT NULL DEFAULT FALSE,
    mfa_segredo TEXT NULL,
    mfa_ultimo_passo BIGINT NULL,
    mfa_codigos_recuperacao TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_usuarios_email (email),
    KEY ix_usuarios_identificador_externo (identificador_externo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS grupos (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(150) NOT NULL,
    origem ENUM('LOCAL', 'LDAP', 'OIDC') NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_grupos_nome (nome),
    UNIQUE KEY uk_grupos_nome_origem (nome, origem)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuario_grupos (
    usuario_id INT NOT NULL,
    grupo_id INT NOT NULL,
    PRIMARY KEY (usuario_id, grupo_id),
    CONSTRAINT fk_usuario_grupos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE,
    CONSTRAINT fk_usuario_grupos_grupo FOREIGN KEY (grupo_id) REFERENCES grupos (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS unidades (
    id INT NOT NULL AUTO_INCREMENT,
    nome VARCHAR(200) NOT NULL,
    cnes VARCHAR(20) NOT NULL,
    unidade_e_mista BOOLEAN NOT NULL DEFAULT FALSE,
    tipo VARCHAR(100) NULL,
    endereco VARCHAR(255) NULL,
    bairro VARCHAR(100) NULL,
    cidade VARCHAR(100) NULL,
    uf VARCHAR(2) NULL,
    situacao ENUM('ATIVA', 'INATIVA', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVA',
    descricao_situacao TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_unidades_cnes (cnes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS servicos (
    id INT NOT NULL AUTO_INCREMENT,
    unidade_id INT NULL,
    nome VARCHAR(150) NOT NULL,
    situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    descricao_situacao TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_servicos_unidade_id (unidade_id),
    CONSTRAINT fk_servicos_unidade
        FOREIGN KEY (unidade_id) REFERENCES unidades (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS equipamentos (
    id INT NOT NULL AUTO_INCREMENT,
    unidade_id INT NULL,
    servico_id INT NULL,
    nome VARCHAR(150) NOT NULL,
    tipo VARCHAR(100) NULL,
    situacao ENUM('ATIVO', 'INATIVO', 'MANUTENCAO') NOT NULL DEFAULT 'ATIVO',
    descricao_situacao TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_equipamentos_unidade_id (unidade_id),
    KEY ix_equipamentos_servico_id (servico_id),
    CONSTRAINT fk_equipamentos_unidade
        FOREIGN KEY (unidade_id) REFERENCES unidades (id),
    CONSTRAINT fk_equipamentos_servico
        FOREIGN KEY (servico_id) REFERENCES servicos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS manutencoes (
    id INT NOT NULL AUTO_INCREMENT,
    equipamento_id INT NOT NULL,
    tipo ENUM('PREVENTIVA', 'CORRETIVA') NOT NULL,
    descricao VARCHAR(255) NOT NULL,
    data_abertura DATE NOT NULL,
    data_conclusao DATE NULL,
    custo DECIMAL(10, 2) NOT NULL DEFAULT 0,
    situacao ENUM('ABERTA', 'CONCLUIDA', 'CANCELADA') NOT NULL DEFAULT 'ABERTA',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_manutencoes_equipamento_id (equipamento_id),
    CONSTRAINT fk_manutencoes_equipamento
        FOREIGN KEY (equipamento_id) REFERENCES equipamentos (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS alteracoes (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NOT NULL,
    tabela VARCHAR(100) NOT NULL,
    registro_id INT NULL,
    operacao ENUM('CRIAR', 'EDITAR', 'ALTERAR_SITUACAO') NOT NULL,
    dados_novos TEXT NULL,
    descricao TEXT NULL,
    motivo_rejeicao TEXT NULL,
    status ENUM('PENDENTE', 'APROVADO', 'REJEITADO') NOT NULL DEFAULT 'PENDENTE',
    created_at DATETIME NOT NULL,
    approved_by INT NULL,
    approved_at DATETIME NULL,
    PRIMARY KEY (id),
    KEY ix_alteracoes_usuario_id (usuario_id),
    KEY ix_alteracoes_approved_by (approved_by),
    CONSTRAINT fk_alteracoes_usuario_criador
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
    CONSTRAINT fk_alteracoes_usuario_aprovador
        FOREIGN KEY (approved_by) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auditorias (
    id INT NOT NULL AUTO_INCREMENT,
    usuario_id INT NULL,
    acao VARCHAR(100) NOT NULL,
    tabela VARCHAR(100) NULL,
    registro_id INT NULL,
    descricao TEXT NULL,
    valor_anterior TEXT NULL,
    valor_novo TEXT NULL,
    data_hora DATETIME NOT NULL,
    origem_ip VARCHAR(45) NULL,
    resultado VARCHAR(10) NOT NULL DEFAULT 'SUCESSO',
    identificador_tentado VARCHAR(255) NULL,
    PRIMARY KEY (id),
    KEY ix_auditorias_usuario_id (usuario_id),
    CONSTRAINT fk_auditorias_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
