"""Conteúdo da área de Governança: ISO 38500, riscos, RACI, COBIT, auditoria, ética, nuvem."""

PRINCIPIOS = [
    {
        "chave": "responsabilidade",
        "nome": "Responsabilidade",
        "ideia": "Papéis e responsabilidades claros sobre o uso da TI.",
        "como": "Quatro perfis com permissões verificadas no servidor; mudanças relevantes passam pela aprovação de outro perfil.",
        "evidencia": "Matriz de permissões (docs/ARQUITETURA.md), RACI e testes de RBAC.",
        "lacuna": "O Responsável pela Saúde Bucal pode propor mudança em qualquer unidade; falta confirmar se deve haver escopo por unidade.",
    },
    {
        "chave": "estrategia",
        "nome": "Estratégia",
        "ideia": "A TI apoia os objetivos da organização.",
        "como": "Concentra o cadastro da rede e oferece visão consolidada para planejar.",
        "evidencia": "Dashboard, views e relatórios do banco.",
        "lacuna": "Metas e indicadores formais da Secretaria não estão definidos no projeto.",
    },
    {
        "chave": "aquisicao",
        "nome": "Aquisição",
        "ideia": "Investimentos em TI e em ativos decididos com base em informação.",
        "como": "Registra equipamentos, situação e manutenções com custo, o que informa decisões de reposição e compra.",
        "evidencia": "Cadastro de equipamentos e histórico de manutenções.",
        "lacuna": "Não há módulo de compras nem de contratos; o sistema informa a decisão, não a executa.",
    },
    {
        "chave": "desempenho",
        "nome": "Desempenho",
        "ideia": "A TI entrega o nível de serviço necessário.",
        "como": "Classifica cada unidade pelo percentual de equipamentos operantes e mostra manutenções abertas.",
        "evidencia": "Regra de classificação das unidades (menos de 50% Crítica, menos de 80% Atenção) e indicadores de manutenção.",
        "lacuna": "Sem metas de disponibilidade do próprio sistema nem monitoramento com alertas.",
    },
    {
        "chave": "conformidade",
        "nome": "Conformidade",
        "ideia": "A TI respeita leis, normas e políticas internas.",
        "como": "Trilha de auditoria imutável, página de privacidade completa, Meus dados e pedidos de titulares (LGPD, art. 18).",
        "evidencia": "docs/SEGURANCA.md, docs/LGPD.md e a tela de Pedidos de titulares.",
        "lacuna": "O encarregado precisa ser designado e informado em LGPD_ENCARREGADO_NOME e LGPD_ENCARREGADO_EMAIL; a base legal precisa de confirmação jurídica.",
    },
    {
        "chave": "comportamento",
        "nome": "Comportamento humano",
        "ideia": "O uso da TI respeita as pessoas envolvidas.",
        "como": "Fluxo de aprovação com revisão por outra pessoa, mensagens claras e perfis com o mínimo de acesso necessário.",
        "evidencia": "Fluxo de aprovações e telas ajustadas após teste de uso com cada perfil.",
        "lacuna": "Sem treinamento formal; feedback de usuários reais ainda não foi coletado.",
    },
]

ESCALA_RISCO = "Probabilidade e impacto de 1 a 5. Nível = P × I: 1 a 5 baixo, 6 a 12 médio, 15 a 25 alto. Valores são estimativas do grupo e devem ser revistas periodicamente."

RISCOS = [
    {"id": "R1", "risco": "Cadastro de unidades e equipamentos desatualizado leva a decisão errada sobre a rede", "origem": "Natureza do processo", "p": 4, "i": 4},
    {"id": "R2", "risco": "Perda de dados por falta de backup testado", "origem": "Pendência de SR2 em docs/SEGURANCA.md", "p": 3, "i": 5},
    {"id": "R3", "risco": "Conta comprometida (senha fraca, sem MFA)", "origem": "SEC-019; QA S4", "p": 3, "i": 4},
    {"id": "R4", "risco": "Dependências com vulnerabilidades conhecidas", "origem": "QA S5 (pip-audit)", "p": 3, "i": 4},
    {"id": "R5", "risco": "Equipamento crítico parado sem que a gestão perceba", "origem": "Operação da rede", "p": 3, "i": 4},
    {"id": "R6", "risco": "Servidor fora do ar (o Learner Lab desliga ao fim da sessão)", "origem": "docs/AWS_DEPLOY.md", "p": 5, "i": 2},
    {"id": "R7", "risco": "Trilha de auditoria apagada por quem tem privilégio no banco (TRUNCATE ou DROP)", "origem": "Limite do SEC-017", "p": 2, "i": 5},
    {"id": "R8", "risco": "Sessão continua válida após o logout; logout por GET", "origem": "QA S1, S2; SEC-012", "p": 3, "i": 3},
    {"id": "R9", "risco": "Dados pessoais na trilha (e-mail digitado em login falho) sem prazo máximo de guarda", "origem": "SEC-021", "p": 3, "i": 3},
    {"id": "R10", "risco": "Baixa adoção ou uso incorreto por falta de treinamento e de teste com usuários reais", "origem": "docs/VALIDACAO_REQUISITOS_SEGURANCA.md", "p": 3, "i": 3},
    {"id": "R11", "risco": "Descoberta de e-mails cadastrados pelo tempo de resposta do login", "origem": "QA S3", "p": 3, "i": 2},
    {"id": "R12", "risco": "Responsável pela Saúde Bucal propõe alteração em unidade que não é dele", "origem": "QA S10", "p": 3, "i": 2},
]

MITIGACAO = [
    {"risco": "R1", "acao": "Revisão mensal do cadastro com as unidades; manter o fluxo de aprovação.", "responsavel": "Gestão da Informação", "prazo": "Curto", "mexe": "Não"},
    {"risco": "R2", "acao": "Definir rotina de backup do banco (dump agendado para o S3 versionado) e testar a restauração a cada trimestre.", "responsavel": "Equipe técnica", "prazo": "Curto", "mexe": "AWS; testar antes em cópia"},
    {"risco": "R3", "acao": "Política de senha mais forte (recusar senhas comuns, limite de 72 bytes do bcrypt) e MFA ou delegação ao provedor OIDC.", "responsavel": "Equipe técnica", "prazo": "Médio", "mexe": "Código; branch separada"},
    {"risco": "R4", "acao": "Atualizar PyJWT, cryptography e Flask, rodar a suíte e repetir o pip-audit.", "responsavel": "Equipe técnica", "prazo": "Médio", "mexe": "Dependências; branch separada"},
    {"risco": "R5", "acao": "Acompanhar semanalmente a classificação Crítica e Atenção e as manutenções abertas; definir quem age em cada caso.", "responsavel": "Gestor e Gestão da Informação", "prazo": "Curto", "mexe": "Não"},
    {"risco": "R6", "acao": "Ligar o laboratório com 10 minutos de antecedência antes de demonstrações; documentar o religamento.", "responsavel": "Equipe técnica", "prazo": "Curto", "mexe": "Não"},
    {"risco": "R7", "acao": "Revisar os privilégios do usuário do banco (sem DROP, ALTER, TRIGGER) e rodar o teste dos triggers no MySQL 8.", "responsavel": "Equipe técnica", "prazo": "Curto", "mexe": "AWS; testar em cópia"},
    {"risco": "R8", "acao": "Invalidar a sessão no logout e trocar o logout para POST com token CSRF.", "responsavel": "Equipe técnica", "prazo": "Médio", "mexe": "Código; branch separada"},
    {"risco": "R9", "acao": "Meus dados, exportação, anonimização e prazo de retenção configurável já existem. Falta designar o encarregado e fixar o prazo máximo de guarda.", "responsavel": "Administrador e encarregado", "prazo": "Curto", "mexe": "Não (variáveis de ambiente)"},
    {"risco": "R10", "acao": "Treinamento curto por perfil e feedback de ao menos um usuário de cada perfil.", "responsavel": "Grupo", "prazo": "Curto", "mexe": "Não"},
    {"risco": "R11", "acao": "Igualar o tempo de resposta do login para usuário inexistente.", "responsavel": "Equipe técnica", "prazo": "Médio", "mexe": "Código; branch separada"},
    {"risco": "R12", "acao": "Confirmar com o professor e a Secretaria se o perfil deve ser limitado à própria unidade.", "responsavel": "Grupo", "prazo": "Curto (decisão)", "mexe": "Só a implementação"},
]

RACI_COLUNAS = ["Administrador", "Gestão da Informação", "Resp. Saúde Bucal", "Gestor", "Equipe técnica"]

RACI = [
    ("Propor criação ou edição de unidade, serviço ou equipamento", ["C", "A", "R", "I", "-"]),
    ("Aprovar ou rejeitar uma alteração", ["R", "A/R", "I", "I", "-"]),
    ("Importar planilhas", ["C", "A", "R", "I", "-"]),
    ("Consultar dashboard e baixar relatório CSV", ["I", "R", "R", "A/R", "-"]),
    ("Exportar relatório ao S3", ["A", "R", "-", "I", "C"]),
    ("Criar, desativar e alterar perfil de usuários", ["A/R", "C", "I", "I", "C"]),
    ("Atender pedidos de titulares (LGPD)", ["A/R", "C", "-", "-", "-"]),
    ("Sincronizar usuários do LDAP", ["A", "I", "-", "-", "R"]),
    ("Revisar a trilha de auditoria", ["A", "R", "-", "I", "C"]),
    ("Manter servidor, backup, atualizações e dependências", ["I", "I", "-", "-", "A/R"]),
]

RACI_LEGENDA = "R executa, A responde pelo resultado (um por linha), C é consultado, I é informado. Equipe técnica opera a implantação e o banco e não tem perfil no sistema."

COBIT = [
    ("APO01 - Estrutura de gestão de I&T", "Perfis, responsabilidades e matriz de permissões documentadas", "Política formal aprovada pela Secretaria"),
    ("APO12 - Gestão de riscos", "Relatório de segurança com severidade, QA com achados priorizados e matriz de riscos nesta área", "Revisão periódica da matriz"),
    ("APO14 - Gestão de dados", "Minimização, validação de entrada, importação com prévia e confirmação, hash SHA-256", "Dono dos dados e rotina de revisão da qualidade do cadastro"),
    ("BAI09 - Gestão de ativos", "Cadastro de equipamentos com situação, manutenções preventivas e corretivas e custo", "Registro do descarte e da vida útil"),
    ("DSS05 - Serviços de segurança", "bcrypt, RBAC, CSRF, rate limit, HTTPS com HSTS, criptografia em repouso (EBS e S3)", "MFA, política de senha mais forte, dependências atualizadas"),
    ("DSS06 - Controles dos processos de negócio", "Fluxo de aprovação (pendente, aprovado, rejeitado) e trilha de auditoria", "Escopo por unidade para o Responsável pela Saúde Bucal"),
    ("MEA01 - Monitoramento de desempenho e conformidade", "Dashboard, indicadores de manutenção, testes automáticos e os indicadores desta área", "Monitoramento do servidor e alertas"),
    ("MEA03 - Conformidade com requisitos externos", "Página de privacidade, Meus dados, pedidos de titulares e retenção da trilha", "Encarregado designado e base legal confirmada"),
]

COBIT_NOTA = "O objetivo APO10 (gestão de fornecedores) só se aplica ao ORIS em relação à AWS, como fornecedor de nuvem (ver Nuvem)."

PLANO_AUDITORIA = [
    ("Semanal", "Revisar LOGIN_FALHA e LOGIN_BLOQUEADO: muitos erros para o mesmo e-mail ou IP, ou logins em horário incomum", "Filtro por resultado na tela de auditoria", "Gestão da Informação"),
    ("Semanal", "Revisar a administração de usuários (criação, desativação, troca de perfil, redefinição de senha)", "Filtro por ação", "Gestão da Informação; Administrador confirma"),
    ("Semanal", "Conferir pedidos de titulares abertos e vencidos", "Tela de pedidos de titulares", "Administrador"),
    ("Mensal", "Conferir aprovações e rejeições: quem aprovou o quê, rejeições sem justificativa, pendências paradas", "Tela de aprovações e trilha", "Gestão da Informação"),
    ("Mensal", "Rodar pip-audit e registrar as dependências com aviso", "Saída do comando guardada", "Equipe técnica"),
    ("Trimestral", "Revisar contas ativas, perfis e contas sincronizadas do LDAP; desativar quem saiu", "Lista de usuários contra lista de pessoas autorizadas", "Administrador"),
    ("Trimestral", "Confirmar que o usuário do banco da aplicação não tem DROP, ALTER nem TRIGGER e que os triggers da trilha estão ativos", "Consulta aos privilégios; UPDATE na trilha deve falhar (erro 1644)", "Equipe técnica"),
    ("Trimestral", "Teste de restauração de backup do banco", "Registro do teste", "Equipe técnica"),
    ("Anual", "Arquivar ou expurgar registros além do prazo, depois de backup testado; rever este plano e a matriz de riscos", "Ata", "Administrador e Gestão da Informação"),
]

CHECKLIST_AUDITORIA = [
    "Todos os logins bem-sucedidos são de usuários conhecidos e ativos?",
    "Há ações de administração sem pedido correspondente?",
    "Houve alteração aprovada sem passar pelo fluxo normal?",
    "Os registros do período têm IP, resultado e data coerentes, sem lacunas de dias?",
    "O que foi encontrado foi registrado, com responsável e prazo de correção?",
]

ATALHOS_AUDITORIA = [
    ("Falhas de login", "auditoria.listar", {"resultado": "FALHA"}),
    ("Bloqueios por excesso de tentativas", "auditoria.listar", {"acao": "LOGIN_BLOQUEADO"}),
    ("Aprovações", "auditoria.listar", {"acao": "APROVAR_ALTERACAO"}),
    ("Rejeições", "auditoria.listar", {"acao": "REJEITAR_ALTERACAO"}),
    ("Troca de perfil", "auditoria.listar", {"acao": "ALTERAR_PERFIL"}),
    ("Pedidos de titulares", "lgpd.solicitacoes", {}),
]

TRILHA_ELEMENTOS = [
    ("Quem", "usuario_id", "Nulo em login com usuário inexistente; nesse caso vale identificador_tentado. A senha nunca é gravada."),
    ("O quê", "acao, tabela, registro_id, descricao, valor_anterior, valor_novo", "Grava a operação e o antes e depois do dado, na mesma transação."),
    ("Quando", "data_hora", "Preenchida pelo servidor."),
    ("De onde", "origem_ip", "IP da requisição; atrás de proxy mostra o do proxy até configurar um proxy confiável."),
    ("Resultado", "resultado", "Falhas de login viram LOGIN_FALHA e bloqueios viram LOGIN_BLOQUEADO."),
]

TRILHA_INTEGRIDADE = [
    "Sem rota de edição ou exclusão na aplicação; a tela de auditoria é somente leitura.",
    "Triggers trg_auditorias_bu e trg_auditorias_bd barram UPDATE e DELETE no banco (SEC-017).",
    "TRUNCATE e DROP TABLE não disparam triggers; por isso o usuário do banco da aplicação não deve ter DROP, ALTER nem TRIGGER.",
    "Hash SHA-256 na exportação ao S3 e na importação de planilhas (SEC-018).",
    "Acesso restrito a Administrador e Gestão da Informação; retenção mínima configurável (LGPD_RETENCAO_AUDITORIA_ANOS).",
    "Não implementado: encadeamento de hashes entre registros, que protegeria contra quem controla o banco.",
]

DILEMAS = [
    ("Descarte de equipamentos odontológicos", "O sistema marca um equipamento como inativo, mas não registra o que aconteceu com ele. Esses equipamentos geram resíduos que exigem tratamento adequado (a RDC ANVISA 222/2018 trata do gerenciamento de resíduos de serviços de saúde).", "Registrar o destino de cada equipamento inativado e exigir comprovante do descarte quando aplicável. Confirmar a regra com a vigilância sanitária local."),
    ("Classificação automática de unidades", "A regra que marca uma unidade como Crítica ou Atenção usa só o percentual de equipamentos operantes. Pode priorizar manutenção sem considerar a população atendida.", "Manter a regra pública, usar a classificação como apoio e não como decisão automática, e revisar o critério com a Secretaria."),
    ("Uso de IA em análises futuras", "O ORIS não usa IA hoje. Se algum dia um modelo sugerir prioridades, haverá risco de viés e de decisão sem explicação.", "Exigir revisão humana, explicação do critério e registro na trilha."),
    ("Dados de pacientes", "O sistema hoje não trata dados clínicos. Ampliar o escopo mudaria o risco, a base legal e o relatório de impacto.", "Manter a minimização: não adicionar esses dados sem nova análise de risco e de LGPD."),
    ("Monitoramento dos próprios usuários", "A trilha registra ações e IP de servidores públicos. Usada além da finalidade, vira vigilância.", "Declarar a finalidade (segurança e responsabilização), restringir o acesso e não usar a trilha para avaliar desempenho de pessoas."),
    ("Dados fictícios versus reais", "O ambiente de demonstração usa unidades e equipamentos fictícios. Misturar com dados reais levaria a decisões erradas.", "Separar os ambientes, identificar o que é demonstração e trocar as senhas de demonstração antes de qualquer uso real."),
]

NUVEM_INTRO = "A implantação atual está em uma instância EC2 (Ubuntu 24.04, t3.medium, IP elástico) no Learner Lab da AWS, com três contêineres: Caddy (HTTPS), aplicação (gunicorn) e MySQL 8 em volume no disco EBS criptografado. O S3 guarda os relatórios exportados."

NUVEM = [
    ("Instalações e hardware", "Data centers, servidores físicos, energia, rede", "-", "Da AWS"),
    ("Virtualização e serviços (EC2, EBS, S3, KMS)", "Disponibilidade e durabilidade dos serviços", "Escolher região, tipo de instância e configurar cada serviço", "Configurado"),
    ("Criptografia em repouso", "Fornecer AES-256 e a chave KMS padrão", "Ligar a criptografia no EBS e no S3", "Feito e confirmado no console em 10/11/2026"),
    ("Rede e firewall", "Fornecer o security group", "80 e 443 abertos, SSH só do EC2 Instance Connect, banco sem porta pública", "Feito"),
    ("Identidade e acesso", "Fornecer o IAM", "Permissões mínimas; a instância usa o LabInstanceProfile para o S3, sem chave em arquivo", "Feito; permissões amplas do Learner Lab"),
    ("Sistema operacional", "-", "Atualizações de segurança do Ubuntu e do Docker", "Sem rotina documentada"),
    ("TLS e aplicação", "-", "Certificado (Let's Encrypt via Caddy), HSTS, código, dependências, segredos no .env.aws", "TLS e HSTS validados; dependências com avisos (R4)"),
    ("Dados, usuários e perfis", "-", "Quem acessa, trilha de auditoria, retenção e LGPD", "Implementado no sistema; faltam encarregado e base legal confirmados"),
    ("Backup e recuperação", "Durabilidade do S3 e snapshots, se configurados", "Rotina de backup do banco e teste de restauração", "Pendente (R2)"),
    ("Monitoramento e alertas", "Fornecer CloudWatch e CloudTrail", "Habilitar e acompanhar", "Não há evidência no repositório"),
]

NUVEM_NOTA = "O Learner Lab é um ambiente de ensino: o servidor desliga ao fim da sessão (cerca de 4 horas), os dados e o IP elástico permanecem e os contêineres sobem sozinhos ao religar. Uma operação real pediria conta de produção, backup automatizado, monitoramento e revisão de permissões."
