# Laboratório visual: LDAP + OIDC (Keycloak) + S3 na AWS

Guia para montar, **pela interface gráfica**, tudo o que os requisitos 2, 3 e 4 pedem, e para
demonstrar ao professor. O terminal aparece só em 2 comandos de uma linha (Fases 6 e 7).

| Fase | O que fazemos | Onde (tela) | Requisito |
|---|---|---|---|
| 1 | Criar o servidor | Console da AWS | base |
| 2 | Esperar a instalação automática | Console da AWS | base |
| 3 | Criar pessoas e grupos no LDAP | phpLDAPadmin | 3 (LDAP) |
| 4 | Trazer o LDAP para as tabelas do ORIS | ORIS → Usuários → Diretório LDAP | 3 (LDAP → tabelas locais) |
| 5 | Criar o login institucional ligado ao LDAP | Console do Keycloak | 3 (OIDC) |
| 6 | Entrar no ORIS pelo SSO | ORIS | 2 e 3 (RBAC + OIDC) |
| 7 | Exportar relatório para o S3 | Console da AWS + ORIS | 4 (nuvem, API autenticada) |
| 8 | Código do celular no SSO | Console do Keycloak | MFA |

**Como as peças conversam:** o **LDAP** é o cadastro central (pessoas, senhas e grupos). O **Keycloak** é a
portaria: mostra a tela de login, confere a senha **no LDAP** e entrega ao ORIS um bilhete assinado (token
OIDC). O **ORIS** confere a assinatura do bilhete e transforma o **grupo** em **perfil** (RBAC).

---

## Fase 1 - Criar o servidor (console da AWS)

1. AWS Academy → Learner Lab → **Start Lab** → bolinha verde → clique em **AWS**. Região: **N. Virginia (us-east-1)**.
2. **Endereço fixo primeiro:** EC2 → **Elastic IPs** → **Allocate Elastic IP address** → **Allocate**. Anote o IP (ex.: `54.123.45.67`).
3. **Seu IP:** abra https://checkip.amazonaws.com no navegador e anote. Só esse IP vai abrir os consoles de administração.
4. Baixe `docker/lab/user-data.sh` do GitHub, abra no Bloco de Notas e preencha as 3 linhas do topo:
   `ELASTIC_IP`, `MEU_IP` e `SENHA_ADMIN` (só letras, números e `- _ . @`, no mínimo 12 caracteres).
5. EC2 → **Instances** → **Launch instances**:

| Campo | Valor | Por quê |
|---|---|---|
| Name | `oris-lab` | identificar |
| Application and OS Images | **Ubuntu Server 24.04 LTS** | onde o Docker roda |
| Instance type | **t3.medium** | o Keycloak precisa de ~2 GB de memória |
| Key pair | **vockey** | padrão do Learner Lab |
| Network settings | **Allow SSH**, **Allow HTTPS**, **Allow HTTP** | 80/443 para o site com cadeado; SSH para o terminal pelo navegador |
| Configure storage | **20 GiB**, em **Advanced** → **Encrypted** | criptografia em repouso |
| Advanced details → IAM instance profile | **LabInstanceProfile** | acesso ao S3 **sem chave no código** |
| Advanced details → **User data** | cole o `user-data.sh` preenchido | instala tudo sozinho |

6. **Launch instance**. Logo em seguida: **Elastic IPs** → selecione o IP → **Actions** → **Associate Elastic IP address** → Instance `oris-lab` → **Associate**.

## Fase 2 - Esperar a instalação (console da AWS)

1. EC2 → Instances → marque `oris-lab` → **Actions** → **Monitor and troubleshoot** → **Get system log**.
2. Atualize de vez em quando até aparecer `[oris-lab] PRONTO` e os três endereços (5 a 10 minutos):
   - ORIS: `https://54-123-45-67.sslip.io`
   - Keycloak: `https://kc.54-123-45-67.sslip.io/admin`
   - phpLDAPadmin: `https://ldap.54-123-45-67.sslip.io`
3. O cadeado (HTTPS) pode levar mais 1 ou 2 minutos para ficar pronto na primeira vez.

> O **sslip.io** é um serviço gratuito em que o nome já contém o IP: `54-123-45-67.sslip.io` aponta para `54.123.45.67`.
> Assim temos um nome de verdade, exigido para o certificado HTTPS, sem comprar domínio.

## Fase 3 - Pessoas e grupos no LDAP (phpLDAPadmin)

1. Abra `https://ldap.<seu-dominio>` → **login** → Login DN: `cn=admin,dc=oris,dc=local` → senha: a `SENHA_ADMIN`.
2. Na árvore da esquerda: `dc=oris,dc=local` → `ou=usuarios` → **Create a child entry** → **Default** →
   marque o objectClass **inetOrgPerson** → **Proceed**.
3. **RDN:** escolha **uid**. Preencha: `uid` = `ana.admin`, `cn` = `Ana Administradora`, `sn` = `Administradora`,
   `mail` = `ana.admin@oris.example`, `userPassword` = uma senha (tipo **ssha**) → **Create Object** → **Commit**.
4. Repita para: `bruno.gestao`, `carla.saude`, `davi.gestor` e **`eva.semgrupo`** (esta não vai em grupo nenhum).
5. Grupos: `ou=grupos` → **Create a child entry** → **Default** → objectClass **groupOfNames** → RDN **cn** →
   `cn` = `oris-admin`, `member` = clique no ícone e escolha `uid=ana.admin,ou=usuarios,dc=oris,dc=local` → **Create Object** → **Commit**.
6. Repita: `oris-gestao` (bruno), `oris-saude` (carla), `oris-gestor` (davi).

**O que dizer ao professor:** o LDAP é uma árvore. Pessoas ficam em `ou=usuarios`, grupos em `ou=grupos`, e o grupo
guarda a lista de membros (`member`). É assim que funciona o Active Directory de uma prefeitura.

## Fase 4 - LDAP → tabelas do ORIS (tela do ORIS)

1. Abra o ORIS e entre com `admin.demo@oris.example` e a `SENHA_ADMIN`. Cadastre o **MFA** com o celular (QR code).
2. **Usuários** → **Diretório LDAP**. Confira a conexão: **TLS ligada** e **certificado validado**.
3. **Simular**: a tabela mostra quem será criado e com qual perfil. A Eva aparece como **sem grupo mapeado: não entra**.
4. **Sincronizar agora**: as contas aparecem em "Contas que vieram do LDAP" e a ação `SINCRONIZAR_LDAP` vai para a **Auditoria**.
5. Teste ao vivo: no phpLDAPadmin, tire o Davi do grupo `oris-gestor` → sincronize → ele fica **desativado** no ORIS.

**Requisito 3 (primeira metade):** consumo de credenciais via LDAP populando as tabelas locais `usuarios`, `grupos` e `usuario_grupos`.

## Fase 5 - Login institucional no Keycloak (console do Keycloak)

Abra `https://kc.<seu-dominio>/admin` → usuário `admin` → senha `SENHA_ADMIN`.

**5.1 Realm:** menu do canto superior esquerdo (`master`) → **Create realm** → Realm name `oris` → **Create**.
O realm é o "espaço de login" do ORIS, separado do administrativo.

**5.2 Ligar ao LDAP:** **User federation** → **Add LDAP providers**:

| Campo | Valor |
|---|---|
| UI display name | `ldap-oris` |
| Vendor | **Other** |
| Connection URL | `ldap://ldap.oris.local:389` → **Test connection** |
| Enable StartTLS | **On** (conexão cifrada; o Keycloak confia na CA do laboratório) |
| Bind DN / Bind credentials | `cn=admin,dc=oris,dc=local` / `SENHA_ADMIN` → **Test authentication** |
| Edit mode | **READ_ONLY** (o Keycloak só lê o LDAP) |
| Users DN | `ou=usuarios,dc=oris,dc=local` |
| Username / RDN LDAP attribute | `uid` / `uid` |
| UUID LDAP attribute | `entryUUID` |
| User object classes | `inetOrgPerson` |
| Search scope | **One Level** |
| Import users | **On** |
| Trust Email (Advanced settings) | **On** (o ORIS exige e-mail verificado) |

**Save**.

**5.3 Mapeadores do LDAP** (aba **Mappers** do `ldap-oris` → **Add mapper**):
- **grupos**, tipo **group-ldap-mapper**: LDAP Groups DN `ou=grupos,dc=oris,dc=local`, Group Name LDAP Attribute `cn`,
  Group Object Classes `groupOfNames`, Membership LDAP Attribute `member`, Membership attribute type `DN`,
  Membership User LDAP Attribute `uid`, Mode **READ_ONLY** → **Save** → menu **Action** → **Sync LDAP groups to Keycloak**.
- **ldap_uid**, tipo **user-attribute-ldap-mapper**: User Model Attribute `ldap_uid`, LDAP Attribute `uid`,
  Read Only **On**, Always Read Value From LDAP **On** → **Save**.

**5.4 Declarar o atributo:** **Realm settings** → **User profile** → **Create attribute** → nome `ldap_uid`,
quem pode editar e ver: **só admin** → **Create**. (O usuário não consegue alterar esse valor.)

**5.5 Trazer as pessoas:** volte em **User federation** → `ldap-oris` → **Action** → **Sync all users**. Em **Users**, a Ana e os outros aparecem.

**5.6 O client do ORIS:** **Clients** → **Create client**:
1. Client type **OpenID Connect**, Client ID `oris` → **Next**.
2. **Client authentication On**, **Standard flow On**, **Direct access grants Off** → **Next**.
3. Valid redirect URIs `https://<seu-dominio>/login/oidc/callback`, Web origins `https://<seu-dominio>` → **Save**.
4. Aba **Advanced** → **Proof Key for Code Exchange Code Challenge Method** = **S256** → **Save**.
5. Aba **Client scopes** → `oris-dedicated` → **Configure a new mapper**:
   - **Group Membership**: Name `groups`, Token Claim Name `groups`, **Full group path Off**, ID token e userinfo **On**.
   - **User Attribute**: Name `ldap_uid`, User Attribute `ldap_uid`, Token Claim Name `ldap_uid`, ID token e userinfo **On**.
6. Aba **Credentials** → copie o **Client Secret**.

## Fase 6 - Entrar pelo SSO (ORIS)

1. EC2 → `oris-lab` → **Connect** → **EC2 Instance Connect** → **Connect** e rode (troque pelo segredo copiado):
   ```
   sudo sh /opt/oris/docker/lab/configurar.sh oidc COLE_O_CLIENT_SECRET
   ```
2. Na tela de login do ORIS aparece **Entrar com login institucional (SSO)**. Entre como `ana.admin` com a **senha do LDAP**.
3. A Ana entra como **ADMINISTRADOR** na mesma conta criada pela sincronização. Davi entra como **GESTOR** e recebe **403** em `/auditoria`.
4. `eva.semgrupo` é **negada**, com mensagem genérica. Tudo aparece na **Auditoria**.

**Requisito 3 (segunda metade) + Requisito 2:** credenciais via OIDC (Authorization Code + PKCE, assinatura do token
verificada) e o grupo do diretório vira o perfil do RBAC.

## Fase 7 - Relatórios no S3 (console da AWS + ORIS)

1. Console da AWS → **S3** → **Create bucket**: nome `oris-relatorios-<seu-nome>-2026`, região us-east-1,
   **Block all public access** marcado, **Bucket Versioning: Enable**, **Default encryption: SSE-S3** → **Create bucket**.
2. No terminal (mesmo da Fase 6): `sudo sh /opt/oris/docker/lab/configurar.sh s3 oris-relatorios-<seu-nome>-2026`
3. ORIS (como Administrador) → **Relatórios** → **Exportar para o S3** → abra o link (vale 15 minutos).
4. Prova: no S3, abra o objeto → copie a **Object URL** e abra numa aba → **AccessDenied**. Só o link assinado do ORIS funciona.

**Requisito 4:** a autenticação na API da AWS é pela função IAM do servidor (requisições assinadas), sem chave no código;
o arquivo vai cifrado e com hash SHA-256 conferido pelo S3.

## Fase 8 - Código do celular no SSO (console do Keycloak)

**Users** → escolha a pessoa → **Required user actions** → **Configure OTP** → **Save**. No próximo login pelo SSO,
o Keycloak mostra um QR code. Para valer para todos os novos: **Authentication** → **Required actions** → **Configure OTP** → **Set as default action: On**.

---

## Se algo der errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Console do Keycloak ou phpLDAPadmin mostra "liberado só para o IP do laboratório" | Seu IP mudou (outra rede) | `sudo sh /opt/oris/docker/lab/configurar.sh ip NOVO_IP` |
| Site sem cadeado / erro de certificado | Elastic IP associado depois da instalação | Espere alguns minutos: o Caddy tenta de novo sozinho |
| Lab desligou | O Learner Lab desliga após ~4 h | **Start Lab**; tudo volta sozinho em ~3 min (os dados ficam) |
| "Test connection" do Keycloak falha | Certificado do LDAP | Confira se a Connection URL é `ldap.oris.local` (o nome do certificado) |
| Ver o que está rodando | | `sudo docker compose -f /opt/oris/docker-compose.lab.yml --env-file /opt/oris/.env.lab ps` |

**Limites deste laboratório:** o phpLDAPadmin conversa com o LDAP sem TLS, mas só dentro da rede interna do Docker;
os consoles de administração ficam abertos só para `MEU_IP`; a senha do `User data` fica visível no console da AWS
para quem tem acesso à conta. É um ambiente de estudo e demonstração, não de produção.
