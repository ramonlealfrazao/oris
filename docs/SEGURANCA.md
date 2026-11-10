# ORIS - Relatório de Segurança (Fase 12)

Este documento registra a auditoria técnica de segurança realizada no
projeto ORIS ao final da Fase 11, os achados encontrados, o que foi
corrigido, e as recomendações que ficam como melhoria futura (fora do
escopo deste projeto acadêmico).

> Este relatório reflete uma revisão feita pela própria equipe sobre o
> código-fonte. Não
> substitui um pentest profissional nem uma auditoria de terceiros.

## Metodologia

A auditoria revisou, sistematicamente, cada rota da aplicação
(`app/routes/`), os models (`app/models/`), os serviços
(`app/services/`), os templates (`app/templates/`), a configuração
(`config.py`, `.env.example`, `.gitignore`) e as dependências
(`requirements.txt`), cobrindo: autenticação, RBAC, IDOR, CSRF, XSS,
SQL Injection, upload de planilhas, auditoria/integridade,
administração de usuários, fluxo de importação + aprovação,
validação de entrada, tratamento de erros, secrets e dependências.

## Achados

| ID | Achado | Severidade | Situação |
|----|--------|------------|----------|
| SEC-001 | `CSRFProtect` não estava registrado globalmente - `{{ csrf_token() }}` usado sem `FlaskForm` em `alteracoes/lista.html` quebrava a página para um aprovador real vendo alterações de outra pessoa | ALTO | Corrigido na Fase 10 |
| SEC-002 | `login_required` não reverificava se o usuário continuava ativo a cada requisição (só `roles_required` fazia isso) - uma sessão antiga de usuário desativado ainda acessava telas de só-consulta | MÉDIO | Corrigido na Fase 11 |
| SEC-003 | Nenhum header HTTP de segurança nas respostas (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`) | MÉDIO | **Corrigido nesta fase** |
| SEC-004 | Sem página de erro 500 amigável - em caso de erro inesperado sem `errorhandler`, o Flask usaria a página padrão do Werkzeug | BAIXO | **Corrigido nesta fase** |
| SEC-005 | Nenhuma proteção contra tentativas repetidas de login (força bruta) | MÉDIO | **Corrigido nesta fase** (rate limiting leve, em memória, sem Redis) |
| SEC-006 | Nenhuma página de transparência/privacidade documentando finalidade, dados tratados e retenção | INFORMATIVO (LGPD) | **Corrigido nesta fase** (`/privacidade`) |
| SEC-007 | `cryptography` presente no `requirements.txt` sem import direto no código da aplicação | INFORMATIVO | Documentado - é dependência transitiva legítima do `PyMySQL` para o método de autenticação padrão do MySQL 8 (`caching_sha2_password`); sem ela, a conexão ao MySQL real falha. Mantida. |
| SEC-008 | Risco de *formula injection* (`=`, `+`, `-`, `@`) em arquivos gerados com dados vindos de planilhas | INFORMATIVO | **Agora aplicável e mitigado (Fase 14)**: o ORIS passou a gerar CSVs (`/relatorios`). `app/services/relatorio_service.py::sanitizar_celula` prefixa com apóstrofo toda célula iniciada por `=`, `+`, `-`, `@`, TAB ou CR. Coberto por testes. |
| SEC-009 | `SECRET_KEY` com valor padrão público no código: se faltasse no `.env` em produção, cookies de sessão e tokens CSRF poderiam ser forjados | ALTO | **Corrigido na revisão pós-Etapa 03** - `create_app` recusa iniciar sem DEBUG/TESTING se a chave for vazia ou igual à padrão (`tests/test_secret_key_producao.py`) |
| SEC-010 | Rate limit de login sem limpeza: `bloqueado()` criava entradas até para emails que nunca falharam e nada expirava, permitindo crescimento ilimitado de memória (DoS) | MÉDIO | **Corrigido** - consulta sem efeito colateral, purga de chaves expiradas e teto `MAX_CHAVES` (`tests/test_rate_limit.py`) |
| SEC-011 | Respostas da API v1 (dependentes de sessão) sem `Cache-Control`, podendo ser guardadas por proxy/navegador compartilhado | BAIXO | **Corrigido** - `Cache-Control: no-store` em todo o blueprint `/api` (`tests/test_api_seguranca.py`) |
| SEC-012 | `GET /logout` encerra a sessão sem token CSRF: um site externo pode deslogar o usuário (logout CSRF) | INFORMATIVO | Não corrigido - efeito limitado (sem perda de dados). Melhoria futura: tornar o logout `POST` com token CSRF, o que exige alterar o menu de todos os templates |
| SEC-013 | Busca em `/bd/unidades` usa `LIKE` sem escapar `%` e `_` do termo digitado | INFORMATIVO | Não corrigido - o valor é parametrizado (sem injeção); só altera o casamento da própria busca do usuário |
| SEC-014 | Contas vindas de LDAP/OIDC (Fase 14) | — | Mitigado: TLS obrigatório no LDAP e HTTPS no OIDC; PKCE + `state` + `nonce` validados; conta externa nunca autentica com senha local; sincronização nunca altera conta LOCAL; último administrador protegido; erro de SSO genérico (sem vazar detalhes). |
| SEC-015 | Exportação para o S3 (Fase 14) | — | Mitigado: credenciais fora do código (cadeia padrão AWS), criptografia SSE-S3, chave do objeto sem texto do usuário, URL pré-assinada de 15 min, exportação restrita a ADMINISTRADOR/GESTAO_INFORMACAO e auditada. |
| SEC-016 | O `id_token` do OIDC era lido sem verificar assinatura nem `exp`/`iat`: token com assinatura falsa, adulterado, expirado ou com `alg: none` era aceito. A especificação (OIDC Core 3.1.3.7) dispensa a assinatura quando o token vem direto do endpoint por TLS, mas essa premissa cai com `OIDC_ALLOW_INSECURE` e não cobre token vencido | MÉDIO | **Corrigido** - assinatura verificada contra o JWKS do provedor (`jwks_uri` só em https), apenas algoritmos RS/PS/ES, `exp`/`iat`/`iss`/`aud`/`sub` obrigatórios, tolerância de relógio de 60 s (`tests/test_oidc_assinatura.py`, 12 testes; 10 falhavam antes). **Validado em 10/11/2026 contra um Keycloak 26 real** na AWS (login de ADMINISTRADOR e GESTOR via SSO, assinatura do `id_token` verificada pelo JWKS do provedor) |
| SEC-017 | A trilha de auditoria só era imutável pela ausência de rota: quem tivesse acesso ao banco podia alterar ou apagar o log | ALTO | **Corrigido** - triggers `trg_auditorias_bu`/`trg_auditorias_bd` barram UPDATE e DELETE (erro 1644) em `etapa05_objetos.sql`; validado em MariaDB 10.6 (`tests/test_auditoria_imutavel.py`). **Limite:** `TRUNCATE` e `DROP TABLE` não disparam triggers - o usuário do banco da aplicação não deve ter `DROP`, `ALTER` nem `TRIGGER`. **Falta** rodar no MySQL 8 do grupo |
| SEC-018 | Nenhuma verificação de integridade com hash genérico (SHA-256) em importação e exportação | BAIXO | **Corrigido em parte** - exportação ao S3 envia `ChecksumSHA256` (o S3 recusa objeto corrompido) e metadado; download traz `X-Content-SHA256`; importação grava o hash do arquivo na auditoria (evidência, sem checksum do remetente para comparar) (`tests/test_integridade_sha256.py`) |
| SEC-019 | Sem autenticação multifator (MFA) | MÉDIO | **Não corrigido** - fora do escopo desta etapa; pendência para a próxima entrega (TOTP) ou delegar ao provedor OIDC da Prefeitura |
| SEC-020 | Sem `Strict-Transport-Security` e sem redirecionamento HTTP→HTTPS; o cookie só é `Secure` com `ProductionConfig` | MÉDIO | **Corrigido na implantação AWS** - o Caddy termina o TLS (certificado Let's Encrypt automático), redireciona HTTP→HTTPS e envia `Strict-Transport-Security: max-age=31536000`, `X-Content-Type-Options: nosniff`; o cookie de sessão sai `Secure; HttpOnly; SameSite=Lax`. Validado em 10/11/2026 no servidor real (`curl -I` mostrou HTTP/2 200 + HSTS). **Limite:** vale para a implantação AWS (`docker-compose.aws.yml`); rodar a aplicação sozinha em HTTP continua sem essas proteções |
| SEC-021 | A trilha de auditoria não registrava a origem (IP), o resultado (sucesso/falha) nem as tentativas de login que falham (que não têm usuário vinculado) - três dos cinco elementos obrigatórios de um audit trail (quem, o quê, quando, **de onde**, **resultado**) | MÉDIO | **Corrigido** - colunas `origem_ip`, `resultado` e `identificador_tentado`; `usuario_id` passou a aceitar NULL; falhas de login (senha errada, usuário inexistente/inativo, conta de diretório, OIDC) e bloqueios por excesso de tentativas viram `LOGIN_FALHA`/`LOGIN_BLOQUEADO`; os triggers também gravam o IP; a tela de auditoria exibe e filtra por resultado (`tests/test_auditoria_origem_resultado.py`, 9 testes + 1 de banco). A senha digitada nunca é gravada e o motivo real da falha só aparece na trilha, nunca para quem tenta o login. **Limites:** o IP é o `remote_addr` da requisição - atrás de proxy reverso ou Docker ele mostra o IP do proxy/gateway, até configurar o proxy confiável (não usamos `X-Forwarded-For` sem proxy conhecido, pois é forjável); um atacante pode encher a trilha com tentativas, mitigado pelo rate limit de login |
| SEC-022 | Criptografia em repouso do MySQL não é feita pela aplicação | INFORMATIVO | **Atendido na implantação AWS** - o banco (volume Docker) e o certificado ficam no disco EBS da instância, criptografado (AES-256, chave KMS padrão `aws/ebs`), confirmado no console em 10/11/2026; o S3 usa SSE-S3 (AES256). **Limite:** fora da AWS (ex.: rodar em outro servidor) a criptografia de disco depende do ambiente |
| - | RBAC de todas as rotas (`/usuarios`, `/auditoria`, `/alteracoes`, `/unidades`, `/servicos`, `/equipamentos`, `/importacao`, `/dashboard`) | - | Revisado - todas as rotas mutáveis usam `roles_required` com o(s) perfil(is) corretos; nenhuma rota depende só de esconder o link do menu |
| - | API REST v1 (`/api/v1/*`, somente leitura) | - | Revisado - todos os endpoints de dados exigem sessão válida **e usuário ativo** (401 em JSON); métodos de escrita não existem; paginação limitada a 200 itens; filtros `situacao` validados por whitelist (400). **Decisão a confirmar com o grupo:** qualquer perfil autenticado lê a API (não há RBAC por perfil na leitura); como ela expõe só dados da rede e nenhum dado pessoal, foi mantido assim |
| - | Módulo Banco de Dados (`/bd/*`) | - | Revisado - leitura exige login; inserir/alterar/excluir exigem `ADMINISTRADOR` ou `GESTAO_INFORMACAO` (403 para os demais, coberto em `test_etapa03_bd.py`); exclusão por `POST` com token CSRF |
| - | IDOR (acesso a registros por ID) | - | Revisado - todo endpoint com `<id>` usa um `_buscar_..._ou_404`, retornando 404 para inexistente e 403 (via RBAC) para quem não tem permissão; o ORIS não tem modelo de "dono do registro", então não há isolamento por usuário a criar |
| - | XSS | - | Revisado - nenhum uso de `\|safe` ou `Markup()` com dados de usuário em nenhum template; autoescape do Jinja nunca foi desativado |
| - | SQL Injection | - | Revisado (atualizado após a Etapa 03) - o código do ORM (`app/models`, `app/routes`, `app/services`) usa só SQLAlchemy. O módulo `app/bd/` usa **SQL explícito via PyMySQL**, sempre parametrizado (`%s` / `%(nome)s`); nenhuma consulta é montada por concatenação ou f-string. O teste `tests/test_bd_sql_estatico.py` (análise de AST) impede regressão. Parâmetros de consulta passam por whitelist em `ler_parametros` |
| - | Secrets no código/histórico do projeto | - | Revisado - `.env` nunca foi commitado (confirmado via `git log`), `.env.example` só tem placeholders, nenhuma senha real ou token está no código-fonte ou nos testes |

### Nota sobre um achado fora do código-fonte

Durante o desenvolvimento deste projeto (fora do escopo desta
auditoria de código), um token de acesso do GitHub foi colado
em canais fora do repositório em várias ocasiões, para viabilizar
o `git push`. Esse token **nunca foi salvo no repositório** (era
removido da configuração local do Git logo após o uso), mas ficou
exposto fora do repositório. Isso já foi sinalizado
repetidamente durante o desenvolvimento, recomendando a revogação do
token - reforça-se aqui essa recomendação, caso ainda não tenha sido
feita.

## Controles implementados

- **Autenticação:** login/logout, bcrypt (salt gerenciado
  automaticamente pela biblioteca), usuário inativo bloqueado no
  login e em qualquer área protegida, mensagem de erro genérica,
  rate limiting leve por (IP, email).
- **RBAC:** decorators `login_required`/`roles_required`, sempre
  verificados no backend, nunca só na interface.
- **CSRF:** `CSRFProtect` global, cobrindo tanto formulários
  `FlaskForm` quanto os formulários simples do importador.
- **Auditoria:** somente leitura (sem rota de edição/exclusão),
  acesso restrito a ADMINISTRADOR/GESTAO_INFORMACAO, nunca registra
  senha/hash, viaja na mesma transação da operação que descreve.
- **Validação de entrada:** todos os formulários e a leitura de
  planilhas validam no backend (campos obrigatórios, formato de CNES,
  UF, enumerações de situação, existência de relacionamentos) - nunca
  dependem só da validação HTML do navegador.
- **Upload seguro:** extensão validada contra lista fechada, tamanho
  e número de linhas limitados, nome de arquivo gerado pelo servidor,
  pasta temporária dedicada, remoção do arquivo após uso, mensagens
  de erro que nunca expõem caminhos internos.
- **Sessão:** cookies `HttpOnly`, `SameSite=Lax`, `Secure` em
  produção; `session.clear()` no login (mitiga session fixation) e no
  logout.
- **Headers HTTP:** `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` e uma `Content-Security-Policy` básica em toda
  resposta.
- **Proteção de secrets:** `SECRET_KEY` e credenciais de banco vêm do
  `.env` (nunca hardcoded, nunca versionado). Em produção a aplicação
  **não inicia** com `SECRET_KEY` vazia ou igual ao valor padrão de
  desenvolvimento.
- **LGPD/proteção de dados:** ver seção correspondente no
  `README.md` - finalidade, minimização, retenção e página de
  transparência (`/privacidade`).

## Política de retenção da trilha de auditoria

- Prazo mínimo de guarda: **1 ano** (referência do material de Auditoria: Marco Civil da Internet, art. 13, e PCI DSS; a LGPD exige guardar apenas o necessário - revisar com o encarregado de dados).
- A aplicação **não apaga nem altera** registros (triggers `trg_auditorias_bu`/`trg_auditorias_bd`). Arquivamento ou expurgo após o prazo é tarefa do administrador do banco, fora da aplicação, com backup testado antes (pendência de SR2).
- O identificador digitado em logins falhos pode conter dado pessoal (e-mail): tratar a trilha como dado pessoal (acesso restrito a ADMINISTRADOR e GESTAO_INFORMACAO).

## Limitações conhecidas (dependem do ambiente de produção)

- **HTTPS/TLS:** o código já está preparado (`SESSION_COOKIE_SECURE`
  fica `True` em `ProductionConfig`), mas o ambiente de execução real
  (servidor web, proxy reverso, certificado) precisa fornecer TLS —
  isso está fora do que uma aplicação Flask sozinha controla.
- **MFA e HSTS:** ainda não implementados (SEC-019 e SEC-020); ver
  `docs/VALIDACAO_REQUISITOS_SEGURANCA.md`.
- **Rate limiting:** a implementação atual é em memória, por
  processo - não é compartilhada entre múltiplos processos/workers
  nem sobrevive a um restart (a memória é limitada por `MAX_CHAVES` e as
  entradas expiradas são descartadas). Para produção com múltiplos workers,
  recomenda-se um backend compartilhado (ex.: Redis) - deliberadamente
  fora do escopo desta fase.
- **Content-Security-Policy com `unsafe-inline`:** vários templates
  usam pequenos handlers inline (`onchange="this.form.submit()"`) em
  filtros de listagem. Uma CSP realmente restrita exigiria mover esse
  JavaScript para arquivos `.js` próprios - planejado para a futura
  fase de UX/UI, não feito agora para não redesenhar templates fora
  do escopo desta fase.
- **DEBUG em produção:** o código já diferencia `DevelopmentConfig`
  (`DEBUG=True`) de `ProductionConfig` (`DEBUG=False`); cabe a quem
  fizer o deploy garantir que `FLASK_ENV=production` seja usado de
  fato no ambiente real.
- **Dependências:** nenhuma foi identificada como não utilizada ou
  duplicada; nenhuma atualização de versão foi considerada
  criticamente necessária para esta fase - evitou-se atualizar
  indiscriminadamente para não correr o risco de quebrar o projeto
  por mudanças incompatíveis sem necessidade concreta.
