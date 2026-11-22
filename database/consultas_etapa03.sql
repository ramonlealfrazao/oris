USE oris_db;


SELECT u.id,
       u.nome      AS unidade,
       u.bairro,
       u.situacao,
       COUNT(DISTINCT CASE WHEN s.situacao = 'ATIVO'   THEN s.id END) AS servicos_ativos,
       COUNT(DISTINCT CASE WHEN e.situacao = 'ATIVO'   THEN e.id END) AS equip_ativos,
       COUNT(DISTINCT CASE WHEN e.situacao = 'INATIVO' THEN e.id END) AS equip_inativos,
       ROUND(100 * COUNT(DISTINCT CASE WHEN e.situacao = 'ATIVO' THEN e.id END)
                 / NULLIF(COUNT(DISTINCT e.id), 0), 1)                AS pct_equip_operantes
  FROM unidades u
  LEFT JOIN servicos     s ON s.unidade_id = u.id
  LEFT JOIN equipamentos e ON e.unidade_id = u.id
 WHERE ('ATIVA' IS NULL OR u.situacao = 'ATIVA')
 GROUP BY u.id, u.nome, u.bairro, u.situacao
 ORDER BY equip_ativos DESC, u.nome;

SELECT COALESCE(u.bairro, '(sem bairro)')                      AS bairro,
       COUNT(*)                                                AS unidades,
       SUM(u.situacao = 'ATIVA')                               AS ativas,
       ROUND(100 * SUM(u.situacao = 'ATIVA') / COUNT(*), 1)    AS pct_ativas,
       COALESCE(SUM(eq.qtd), 0)                                AS equip_ativos,
       ROUND(AVG(COALESCE(eq.qtd, 0)), 2)                      AS media_equip_por_unidade
  FROM unidades u
  LEFT JOIN (SELECT unidade_id, COUNT(*) AS qtd
               FROM equipamentos
              WHERE situacao = 'ATIVO'
              GROUP BY unidade_id) AS eq
         ON eq.unidade_id = u.id
 GROUP BY COALESCE(u.bairro, '(sem bairro)')
HAVING COUNT(*) >= 2
 ORDER BY unidades DESC, bairro;

SELECT u.id,
       u.nome,
       u.cnes,
       u.bairro,
       (SELECT COUNT(*)
          FROM servicos s
         WHERE s.unidade_id = u.id
           AND s.situacao = 'ATIVO')                AS servicos_ativos,
       DATEDIFF(UTC_TIMESTAMP(), u.updated_at)      AS dias_sem_atualizacao
  FROM unidades u
 WHERE u.situacao = 'ATIVA'
   AND NOT EXISTS (SELECT 1
                     FROM equipamentos e
                    WHERE e.unidade_id = u.id
                      AND e.situacao = 'ATIVO')
 ORDER BY servicos_ativos DESC, u.nome;

WITH equip_bairro AS (
    SELECT COALESCE(u.bairro, '(sem bairro)') AS bairro,
           COUNT(e.id)                        AS qtd
      FROM equipamentos e
      JOIN unidades u ON u.id = e.unidade_id
     WHERE e.situacao = 'ATIVO'
     GROUP BY COALESCE(u.bairro, '(sem bairro)')
)
SELECT RANK() OVER (ORDER BY qtd DESC)                         AS posicao,
       bairro,
       qtd                                                     AS equip_ativos,
       ROUND(100 * qtd / SUM(qtd) OVER (), 1)                  AS pct_do_total,
       ROUND(100 * SUM(qtd) OVER (ORDER BY qtd DESC, bairro
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                 / SUM(qtd) OVER (), 1)                        AS pct_acumulado
  FROM equip_bairro
 ORDER BY posicao, bairro;

SELECT sol.nome                                                  AS solicitante,
       sol.perfil,
       COUNT(*)                                                  AS total,
       SUM(a.status = 'PENDENTE')                                AS pendentes,
       SUM(a.status = 'APROVADO')                                AS aprovadas,
       SUM(a.status = 'REJEITADO')                               AS rejeitadas,
       ROUND(100 * SUM(a.status = 'APROVADO')
                 / NULLIF(SUM(a.status <> 'PENDENTE'), 0), 1)    AS taxa_aprovacao_pct,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, a.created_at, a.approved_at)) / 60, 1)
                                                                 AS horas_medias_decisao,
       GROUP_CONCAT(DISTINCT apr.nome ORDER BY apr.nome SEPARATOR ', ')
                                                                 AS revisores
  FROM alteracoes a
  JOIN usuarios sol      ON sol.id = a.usuario_id
  LEFT JOIN usuarios apr ON apr.id = a.approved_by
 WHERE a.created_at >= UTC_TIMESTAMP() - INTERVAL 90 DAY
 GROUP BY sol.id, sol.nome, sol.perfil
 ORDER BY total DESC, solicitante;

SELECT u.cnes,
       COUNT(*)                                              AS registros,
       GROUP_CONCAT(u.nome ORDER BY u.nome SEPARATOR ' | ')  AS unidades,
       SUM(u.unidade_e_mista)                                AS marcadas_como_mista,
       CASE WHEN SUM(u.unidade_e_mista) = COUNT(*) THEN 'OK'
            ELSE 'REVISAR: há registro sem a marcação de unidade mista'
       END                                                   AS diagnostico
  FROM unidades u
 GROUP BY u.cnes
HAVING COUNT(*) > 1
 ORDER BY registros DESC, u.cnes;

SELECT e.id,
       e.nome   AS equipamento,
       ue.nome  AS unidade_do_equipamento,
       s.nome   AS servico,
       us.nome  AS unidade_do_servico
  FROM equipamentos e
  JOIN servicos      s  ON s.id  = e.servico_id
  LEFT JOIN unidades ue ON ue.id = e.unidade_id
  LEFT JOIN unidades us ON us.id = s.unidade_id
 WHERE NOT (e.unidade_id <=> s.unidade_id)
 ORDER BY e.nome;


START TRANSACTION;

INSERT INTO unidades
        (nome, cnes, unidade_e_mista, tipo, endereco, bairro, cidade, uf,
         situacao, created_at, updated_at)
    VALUES
        ('USF Exemplo Etapa 03', '9199999', 0, 'Unidade de Saúde da Família', 'Rua Exemplo 100', 'Várzea', 'Recife', 'PE', 'ATIVA', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_unidade = LAST_INSERT_ID();

UPDATE unidades
       SET nome = 'USF Exemplo Etapa 03', cnes = '9199999', unidade_e_mista = 0, tipo = 'Unidade de Saúde da Família',
           endereco = 'Rua Exemplo 100', bairro = 'Várzea', cidade = 'Recife', uf = 'PE',
           situacao = 'MANUTENCAO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_unidade;

INSERT INTO servicos (nome, unidade_id, situacao, created_at, updated_at)
    VALUES ('Atenção Básica em Saúde Bucal', @id_unidade, 'ATIVO', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_servico = LAST_INSERT_ID();

UPDATE servicos
       SET nome = 'Atenção Básica em Saúde Bucal', unidade_id = @id_unidade, situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_servico;

INSERT INTO equipamentos
        (nome, tipo, unidade_id, servico_id, situacao, created_at, updated_at)
    VALUES ('Autoclave 21 L #1', 'Autoclave', @id_unidade, @id_servico, 'ATIVO', UTC_TIMESTAMP(), UTC_TIMESTAMP());

SET @id_equip = LAST_INSERT_ID();

UPDATE equipamentos
       SET nome = 'Autoclave 21 L #1', tipo = 'Autoclave', unidade_id = @id_unidade, servico_id = @id_servico,
           situacao = 'INATIVO', updated_at = UTC_TIMESTAMP()
     WHERE id = @id_equip;

DELETE FROM equipamentos WHERE id = @id_equip;

DELETE FROM servicos WHERE id = @id_servico;

DELETE FROM unidades WHERE id = @id_unidade;


ROLLBACK;
