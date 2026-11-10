# Validação dos requisitos de segurança e auditoria (Entrega 11)

Responsável: Iago Figueirôa Soares. Fontes: "Requisitos de segurança" (21 requisitos), slides SR1 de Governança e Auditoria (Humberto) e `docs/ORIS_Requisitos_do_Professor.pdf`.
Detalhe de cada achado: `docs/SEGURANCA.md` (SEC-016 a SEC-022).

## Situação por tema

| Tema | Situação | Evidência |
|---|---|---|
| Autenticação OIDC (assinatura, `exp`, `iat`, `iss`, `aud`, `nonce`, PKCE) | **Atende e validado em Keycloak real** (AWS, 10/11/2026) + testes automatizados com provedor simulado | `app/services/oidc_service.py`, `tests/test_oidc_assinatura.py` (12 testes) |
| Audit trail: quem, o quê, quando, **de onde (IP)** e **resultado**, incluindo login falho | **Atende** (IP é o da requisição; atrás de proxy/Docker mostra o do proxy) | `tests/test_auditoria_origem_resultado.py`, SEC-021 |
| Trilha de auditoria imutável | **Atende com limite** (TRUNCATE/DROP não disparam trigger; restringir privilégios do usuário do banco) | `database/etapa05_objetos.sql`, `tests/test_auditoria_imutavel.py` |
| Integridade com hash (SHA-256) | **Atende em parte** (verificação ativa só no upload ao S3; na importação o hash é só evidência) | `app/utils/integridade.py`, `tests/test_integridade_sha256.py` |
| Criptografia e acesso aos arquivos exportados (S3) | **Atende e validado em S3 real** (10/11/2026): SSE-S3 AES256, bucket privado, acesso direto = `AccessDenied`, só por URL pré-assinada que expira em 15 min; credencial pela função IAM da instância, sem chave em arquivo | `app/services/armazenamento_service.py`, bucket `oris-relatorios-iago-2026` |
| Senhas, CSRF, RBAC, rate limit | **Atende** (já existente) | `docs/SEGURANCA.md` |
| MFA | **Não atende** | SEC-019, pendente (SR2) |
| HTTPS/HSTS/redirecionamento | **Atende na AWS** (Caddy + Let's Encrypt; validado no servidor real) | SEC-020, `docs/AWS_DEPLOY.md` |
| Retenção de 1 ano | **Política documentada** (a aplicação nunca apaga; expurgo é do DBA) | `docs/SEGURANCA.md` |
| Criptografia em repouso do MySQL | **Atende na AWS** (disco EBS criptografado, confirmado no console); fora da aplicação | SEC-022 |

## Evidências na AWS (10/11/2026)

- LDAP: 4 usuários criados com perfil do grupo; execução repetida sem alterações; usuário sem grupo ignorado.
- OIDC: login SSO de ADMINISTRADOR e GESTOR; acesso registrado na auditoria com IP e origem.
- S3: arquivo exportado, criptografado (SSE-S3), acesso direto negado (`AccessDenied`).
- HTTPS com HSTS; senha pública dos usuários demo recusada.

## O que ainda não foi validado

- **S3, LDAP e OIDC reais: validados** (10/11/2026): S3 privado com URL pré-assinada; `sincronizar-ldap` contra OpenLDAP real (STARTTLS + CA própria); login SSO contra Keycloak real. Os testes automatizados continuam usando simulações.
- Triggers testados em MariaDB 10.6; falta rodar em MySQL 8 (`ORIS_TEST_MYSQL=1 pytest tests/test_auditoria_imutavel.py`).
- Feedback de usuários reais: ainda não coletado; só há o retorno de um colega do grupo.
- Itens de SR2 (CNES, backup testado, hospedagem) ainda não tratados.
