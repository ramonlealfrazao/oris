# ORIS no Docker - guia para a apresentação ao vivo

## O que é cada peça (para explicar)

| Peça | Função |
|---|---|
| `Dockerfile` | Receita da imagem da aplicação: Python 3.12, dependências, usuário sem privilégios (não roda como root) e servidor `gunicorn` |
| `docker-compose.yml` | Sobe **dois contêineres**: `db` (MySQL 8) e `app` (ORIS). A app só inicia depois que o banco responde (healthcheck) |
| `docker/entrypoint.py` | Ao ligar: espera o banco, cria tabelas/triggers/views, carrega dados fictícios **só se o banco estiver vazio** e liga o servidor |
| Volume `oris_db_data` | Guarda o banco; os dados sobrevivem a reinícios |

Decisões de segurança que valem citar: o banco **não é exposto** ao computador (só a app o alcança); a app só escuta em `127.0.0.1`; nenhum segredo vai dentro da imagem (`.env` está no `.dockerignore`); a `SECRET_KEY` é gerada na partida se não for informada; o MySQL sobe com `log-bin-trust-function-creators=1` (sem isso o MySQL 8 recusa criar os triggers de auditoria, erro 1419).

## Antes do dia (faça 1 vez, com internet)

1. Instalar o **Docker Desktop** (Windows: habilitar WSL 2 quando ele pedir) e abri-lo até aparecer "Engine running".
2. Na pasta do projeto: `docker compose up --build` e esperar a linha `[oris] ligando o servidor`. Isso baixa as imagens (precisa de internet, leva alguns minutos). Depois `Ctrl+C`.
3. Ensaiar o roteiro abaixo **duas vezes**. Na apresentação, as imagens já estarão em cache e subir leva ~1 minuto.
4. Porta 5000 ocupada? Use `$env:ORIS_PORT=5001` (PowerShell) antes do comando e abra `localhost:5001`.

## Roteiro ao vivo (PowerShell, na pasta do projeto)

| Passo | Comando / ação | O que dizer |
|---|---|---|
| 1 | `docker compose up --build -d` | "Um comando sobe app e banco." |
| 2 | `docker compose ps` | Mostra `db` e `app` como **healthy** |
| 3 | `docker compose logs app` | Mostra: banco respondeu -> tabelas e triggers criados -> dados de demonstração -> servidor ligado |
| 4 | Abrir `http://localhost:5000` e entrar com `admin.demo@oris.example` / `Oris@2026` | Login com perfil ADMINISTRADOR (RBAC) |
| 5 | Dashboard, Unidades, Equipamentos, Auditoria | Mostrar que a ação de login aparece na trilha |
| 6 | `docker compose exec db mysql -uroot -proot-demo-troque oris_db -e "UPDATE auditorias SET acao='X' LIMIT 1;"` | **Resultado esperado: `ERROR 1644 ... auditorias e imutavel`.** O próprio banco barra a adulteração do log |
| 7 | `docker compose down` (mantém dados) ou `docker compose down -v` (zera tudo) | Encerra |

Usuários de demonstração (senha `Oris@2026`): `admin.demo`, `gi.demo`, `rsb.demo`, `gestor.demo` @oris.example - um por perfil.

## Se algo der errado

| Sintoma | Causa provável | Ação |
|---|---|---|
| `error during connect` / "docker daemon is not running" | Docker Desktop fechado | Abrir o Docker Desktop e esperar "Engine running" |
| `port is already allocated` | Algo usa a porta 5000 | `$env:ORIS_PORT=5001` e repetir |
| Login volta para a mesma tela | Cookie `Secure` sem HTTPS | Confirmar `SESSION_COOKIE_SECURE` = false (padrão do compose, só para demo) |
| Banco com dados estranhos | Volume antigo | `docker compose down -v` e subir de novo |
| App reinicia em loop | Veja `docker compose logs app` | A mensagem do entrypoint diz o motivo |

## Limites honestos (se perguntarem)

- É uma configuração de **demonstração**: HTTP em localhost, senhas de demo e `SESSION_COOKIE_SECURE=false`. Em produção: HTTPS no proxy, `SECRET_KEY`, `DB_PASSWORD` e `DB_ROOT_PASSWORD` fortes e `SESSION_COOKIE_SECURE=true`.
- Ainda não sobem no compose: LDAP, OIDC e S3 reais (pendentes de validação com servidores reais).
- MFA, HSTS e IP de origem na auditoria seguem como pendências registradas em `docs/SEGURANCA.md`.
